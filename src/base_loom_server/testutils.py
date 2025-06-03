import base64
import contextlib
import dataclasses
import importlib.resources
import itertools
import pathlib
import random
import sys
import tempfile
from collections.abc import Generator, Iterable
from importlib.resources.abc import Traversable
from types import SimpleNamespace
from typing import Any, TypeAlias

import pytest
from dtx_to_wif import read_pattern_file
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from starlette.testclient import WebSocketTestSession

from .base_loom_server import BaseLoomServer
from .base_mock_loom import BaseMockLoom
from .enums import ConnectionStateEnum, MessageSeverityEnum, ModeEnum, ShaftStateEnum
from .reduced_pattern import (
    DEFAULT_THREAD_GROUP_SIZE,
    NUM_ITEMS_FOR_REPEAT_SEPARATOR,
    ReducedPattern,
    reduced_pattern_from_pattern_data,
)
from .utils import compute_total_num

WebSocketType: TypeAlias = WebSocket | WebSocketTestSession

_PKG_NAME = "base_loom_server"
TEST_DATA_FILES = importlib.resources.files(_PKG_NAME).joinpath("test_data")

# in Python 3.11 mypy complains: "Traversable" has no attribute "glob"
ALL_PATTERN_PATHS = (
    list(TEST_DATA_FILES.glob("*.wif"))  # type: ignore
    + list(TEST_DATA_FILES.glob("*.dtx"))  # type: ignore
    + list(TEST_DATA_FILES.glob("*.wpo"))  # type: ignore
)


def assert_replies_equal(reply: dict[str, Any], expected_reply: dict[str, Any]) -> None:
    for key, value in expected_reply.items():
        if value is not None and reply.get(key) != value:
            raise AssertionError(
                f"{reply=} != {expected_reply}: failed on field {key!r}"
            )


@dataclasses.dataclass
class Client:
    test_client: TestClient
    loom_server: BaseLoomServer
    mock_loom: BaseMockLoom
    websocket: WebSocketType

    def send_dict(self, datadict: dict[str, Any]):
        """Write a dict as json"""
        self.websocket.send_json(datadict)

    def receive_dict(self) -> dict[str, Any]:
        """Read json as a dict"""
        data: Any = self.websocket.receive_json()
        assert isinstance(data, dict)
        return data


def change_direction(client: Client) -> None:
    """Command the loom to weave or thread in the opposite direction,
    and read and check the reply, if one is expected.

    Use a software command, if the loom supports that,
    else an oob command.

    Args:
        client: Client fixture.
    """
    expected_direction_reply = True
    client.mock_loom.command_threading_event.clear()
    if client.loom_server.enable_software_direction:
        direction_forward = not client.loom_server.direction_forward
        replies = send_command(
            client, dict(type="direction", forward=direction_forward)
        )
    else:
        expected_direction_reply = client.loom_server.loom_reports_direction
        direction_forward = not client.mock_loom.direction_forward
        replies = send_command(client, dict(type="oobcommand", command="d"))

    if expected_direction_reply:
        assert len(replies) == 2
        assert replies[0]["type"] == "Direction"
        assert replies[0]["forward"] == direction_forward
    else:
        assert len(replies) == 1
        # Give the loom client time to process the command
        client.mock_loom.command_threading_event.wait(timeout=1)


def command_next_end(
    client: Client,
    expected_end_number0: int,
    expected_end_number1: int,
    expected_repeat_number: int,
    jump_pending: bool = False,
) -> None:
    """Command the next threading end group and test the replies.

    Ignore info-level StatusMessage

    Args:
        client: Client fixture.
        expected_end_number0: Expected end number of the next end group.
        expected_repeat_number: Expected repeat number of the next end group.
        jump_pending: Is a jump pending?
    """
    pattern = client.loom_server.current_pattern
    assert pattern is not None

    client.mock_loom.command_threading_event.clear()

    replies = send_command(client, dict(type="oobcommand", command="n"))
    assert len(replies) == 1
    # Give the loom client time to process the command
    client.mock_loom.command_threading_event.wait(timeout=1)

    expected_shaft_word = pattern.get_threading_shaft_word()
    expected_replies: list[dict[str, Any]] = []
    if jump_pending:
        expected_replies += [
            dict(
                type="JumpEndNumber",
                end_number=None,
                end_repeat_number=None,
            ),
        ]
    num_ends_in_pattern = len(pattern.threading)
    expected_total_end_number0 = compute_total_num(
        num_within=expected_end_number0,
        repeat_number=expected_repeat_number,
        repeat_len=num_ends_in_pattern,
    )
    expected_total_end_number1 = compute_total_num(
        num_within=expected_end_number1,
        repeat_number=expected_repeat_number,
        repeat_len=num_ends_in_pattern,
    )
    expected_replies += [
        dict(
            type="CurrentEndNumber",
            end_number0=expected_end_number0,
            end_number1=expected_end_number1,
            total_end_number0=expected_total_end_number0,
            total_end_number1=expected_total_end_number1,
            end_repeat_number=expected_repeat_number,
        ),
    ]
    if client.loom_server.loom_reports_motion:
        expected_replies += [
            dict(
                type="ShaftState",
                state=ShaftStateEnum.MOVING,
                shaft_word=None,
            ),
            dict(
                type="ShaftState",
                state=ShaftStateEnum.MOVING,
                shaft_word=None,
            ),
        ]
    expected_replies += [
        dict(
            type="ShaftState",
            state=ShaftStateEnum.DONE,
            shaft_word=expected_shaft_word,
        ),
    ]
    for expected_reply in expected_replies:
        reply = client.receive_dict()
        if (
            reply["type"] == "ServerMessage"
            and reply["severity"] == MessageSeverityEnum.INFO
        ):
            # Ignore info-level status messages
            continue
        assert_replies_equal(reply, expected_reply)


def command_next_pick(
    client: Client,
    expected_pick_number: int,
    expected_repeat_number: int,
    expected_shaft_word: int,
    jump_pending: bool = False,
) -> None:
    """Command the next pick and test the replies.

    Ignore info-level StatusMessage

    Args:
        client: Client fixture.
        expected_pick_number: Expected pick number of the next pick.
        expected_repeat_number: Expected repeat number of the next pick.
        expected_shaft_word: Expected shaft_word of the next pick.
        jump_pending: Is a jump pending?
    """
    replies = send_command(client, dict(type="oobcommand", command="n"))
    assert len(replies) == 1
    expected_replies: list[dict[str, Any]] = []
    if (
        not client.loom_server.enable_software_direction
        and not client.loom_server.loom_reports_direction
        and client.loom_server.direction_forward != client.mock_loom.direction_forward
    ):
        # Loom only reports direction when it asks for a pick
        # and the direction has changed
        expected_replies += [
            dict(
                type="Direction",
                forward=client.mock_loom.direction_forward,
            )
        ]
    if jump_pending:
        expected_replies += [
            dict(
                type="JumpPickNumber",
                pick_number=None,
                pick_repeat_number=None,
            ),
        ]
    expected_replies += [
        dict(
            type="CurrentPickNumber",
            pick_number=expected_pick_number,
            total_pick_number=None,
            pick_repeat_number=expected_repeat_number,
        ),
    ]
    if client.loom_server.loom_reports_motion:
        expected_replies += [
            dict(
                type="ShaftState",
                state=ShaftStateEnum.MOVING,
                shaft_word=None,
            ),
            dict(
                type="ShaftState",
                state=ShaftStateEnum.MOVING,
                shaft_word=None,
            ),
        ]
    expected_replies += [
        dict(
            type="ShaftState",
            state=ShaftStateEnum.DONE,
            shaft_word=expected_shaft_word,
        ),
    ]
    for expected_reply in expected_replies:
        reply = client.receive_dict()
        if (
            reply["type"] == "ServerMessage"
            and reply["severity"] == MessageSeverityEnum.INFO
        ):
            # Ignore info-level status messages
            continue
        assert_replies_equal(reply, expected_reply)


def select_pattern(
    client: Client,
    pattern_name: str,
    check_defaults: bool = True,
) -> ReducedPattern:
    """Tell the loom server to select a pattern.

    Read and check the expected replies and return the pattern.

    Args:
        client: Client test fixture.
        pattern_name: Pattern name.
        check_defaults: If true (the default), check that all pattern fields,
        that are updated as one weaves or threads (such as pick_value)
        have the expected default value. This is only appropriate for patterns
            that are newly loaded, or have not been woven on or threaded
            once loaded.

    Returns:
        current_pattern: the actual current_pattern in the loom server
            (rather than the one reconstructed from the ReducedPattern reply,
            so you can monitor internal changes).
    """
    expected_seen_types = {
        "CommandDone",
        "CurrentPickNumber",
        "CurrentEndNumber",
        "ReducedPattern",
        "SeparateThreadingRepeats",
        "SeparateWeavingRepeats",
        "ThreadGroupSize",
    }

    replies = send_command(client, dict(type="select_pattern", name=pattern_name))
    assert len(replies) == len(expected_seen_types)
    pattern_reply = replies[0]
    assert pattern_reply["type"] == "ReducedPattern"
    pattern_in_reply = ReducedPattern.from_dict(pattern_reply)
    if check_defaults:
        assert pattern_in_reply.pick_number == 0
        assert pattern_in_reply.pick_repeat_number == 1
        assert pattern_in_reply.end_number0 == 0
        assert pattern_in_reply.end_number1 == 0
        assert pattern_in_reply.end_repeat_number == 1
        assert pattern_in_reply.thread_group_size == DEFAULT_THREAD_GROUP_SIZE
        assert bool(pattern_in_reply.separate_threading_repeats) == (
            len(pattern_in_reply.threading) > NUM_ITEMS_FOR_REPEAT_SEPARATOR
        )
        assert bool(pattern_in_reply.separate_weaving_repeats) == (
            len(pattern_in_reply.picks) > NUM_ITEMS_FOR_REPEAT_SEPARATOR
        )
    seen_types: set[str] = {"ReducedPattern"}
    for reply_dict in replies[1:]:
        reply = SimpleNamespace(**reply_dict)
        match reply.type:
            case "CommandDone":
                assert reply.cmd_type == "select_pattern"
                assert reply.success
            case "CurrentPickNumber":
                assert reply.pick_number == pattern_in_reply.pick_number
                assert reply.pick_repeat_number == pattern_in_reply.pick_repeat_number
                assert reply.total_picks == compute_total_num(
                    num_within=pattern_in_reply.pick_number,
                    repeat_number=pattern_in_reply.pick_repeat_number,
                    repeat_len=len(pattern_in_reply.picks),
                )
            case "CurrentEndNumber":
                assert reply.end_number0 == pattern_in_reply.end_number0
                assert reply.end_number1 == pattern_in_reply.end_number1
                assert reply.end_repeat_number == pattern_in_reply.end_repeat_number
                assert reply.total_end_number0 == compute_total_num(
                    num_within=pattern_in_reply.end_number0,
                    repeat_number=pattern_in_reply.end_repeat_number,
                    repeat_len=pattern_in_reply.num_ends,
                )
                assert reply.total_end_number1 == compute_total_num(
                    num_within=pattern_in_reply.end_number1,
                    repeat_number=pattern_in_reply.end_repeat_number,
                    repeat_len=pattern_in_reply.num_ends,
                )
            case "SeparateThreadingRepeats":
                assert reply.separate == pattern_in_reply.separate_threading_repeats
            case "SeparateWeavingRepeats":
                assert reply.separate == pattern_in_reply.separate_weaving_repeats
            case "ThreadGroupSize":
                assert reply.group_size == pattern_in_reply.thread_group_size
            case _:
                raise AssertionError(f"Unexpected message type {reply.type}")
        seen_types.add(reply.type)
    assert seen_types == expected_seen_types
    assert client.loom_server.current_pattern is not None
    return client.loom_server.current_pattern


def send_command(
    client: Client, cmd_dict: dict[str, Any], should_fail: bool = False
) -> list[dict[str, Any]]:
    """Issue a command and return all replies.

    The final reply will be CommandDone and its success flag is checked
    """
    client.send_dict(cmd_dict)
    replies = []
    while True:
        reply = client.receive_dict()
        replies.append(reply)
        if reply["type"] == "CommandDone":
            if should_fail == reply["success"]:
                if should_fail:
                    raise AssertionError(
                        f"Command {cmd_dict} succeeded, but should have failed"
                    )
                else:
                    raise AssertionError(f"Command {cmd_dict} failed")
            break
    return replies


def upload_pattern(
    client: Client,
    filepath: Traversable,
    expected_names: Iterable[str],
    should_fail=False,
) -> None:
    """Upload a pattern to the loom server.

    Check expected replies.

    Args:
        client: Test client.
        filepath: Path to pattern file.
        expected_names: Expected pattern names.
        should_fail: If true, upload should fail (and `expected_names`
            is ignored).
    """
    suffix = pathlib.Path(str(filepath)).suffix
    if suffix == ".wpo":
        raw_data = filepath.read_bytes()
        data = base64.b64encode(raw_data).decode("ascii")
    else:
        data = filepath.read_text()
    replies = send_command(
        client,
        dict(type="file", name=filepath.name, data=data),
        should_fail=should_fail,
    )
    if should_fail:
        assert len(replies) == 1
    else:
        assert len(replies) == 2
        assert replies[0] == dict(type="PatternNames", names=list(expected_names))


class BaseTestLoomServer:
    """Base class for server tests.

    Subclasses must:
    * Set class property `app` to the FastAPI app for your loom server.
    * Have a name beginning with Test
    * Not have an `__init__` method
    """

    expected_status_messages = ()
    app: FastAPI | None = None
    extra_args = ()

    def test_jump_to_end(self) -> None:
        pattern_name = ALL_PATTERN_PATHS[4].name

        with self.create_test_client(
            app=self.app,
            num_shafts=32,
            upload_patterns=ALL_PATTERN_PATHS[2:5],
        ) as client:
            pattern = select_pattern(client=client, pattern_name=pattern_name)
            num_ends_in_pattern = len(pattern.threading)

            replies = send_command(client, dict(type="mode", mode=ModeEnum.THREAD))
            assert len(replies) == 2
            assert replies[0] == dict(type="Mode", mode=ModeEnum.THREAD)

            # post_action sets what to do after sending the jump_to_end cmd:
            # * cancel: cancel the jump_to_pick
            # * next: advance to the next end (thus accepting the jump)
            # * nothing: do nothing
            for (
                thread_group_size,
                post_action,
                end_number0,
                end_repeat_number,
            ) in itertools.product(
                (1, 4),
                ("cancel", "next", "nothing"),
                (0, 1, num_ends_in_pattern // 3, num_ends_in_pattern),
                (-1, 0, 1, 2),
            ):
                replies = send_command(
                    client, dict(type="thread_group_size", group_size=thread_group_size)
                )
                assert len(replies) == 2
                assert replies[0] == dict(
                    type="ThreadGroupSize", group_size=thread_group_size
                )
                assert pattern.thread_group_size == thread_group_size

                total_end_number0 = compute_total_num(
                    num_within=end_number0,
                    repeat_number=end_repeat_number,
                    repeat_len=num_ends_in_pattern,
                )
                replies = send_command(
                    client,
                    dict(type="jump_to_end", total_end_number0=total_end_number0),
                )
                assert len(replies) == 2
                jump_end_reply = SimpleNamespace(**replies[0])
                if total_end_number0 == 0:
                    # Jump to end_number0 0, repeat_number 1.
                    assert jump_end_reply == SimpleNamespace(
                        type="JumpEndNumber",
                        total_end_number0=0,
                        total_end_number1=0,
                        end_number0=0,
                        end_number1=0,
                        end_repeat_number=1,
                    )
                elif end_number0 == 0:
                    # Jump to end_number0 0, repeat_number not 1.
                    # Report the last end of the previous repeat,
                    # rather than the magic "0" end_number0
                    assert jump_end_reply == SimpleNamespace(
                        type="JumpEndNumber",
                        total_end_number0=total_end_number0,
                        total_end_number1=total_end_number0 + 1,
                        end_number0=num_ends_in_pattern,
                        end_number1=num_ends_in_pattern + 1,
                        end_repeat_number=end_repeat_number - 1,
                    )
                else:
                    end_delta = pattern.compute_end_number1(end_number0) - end_number0
                    # Jump to a nonzero end_number0.
                    assert jump_end_reply == SimpleNamespace(
                        type="JumpEndNumber",
                        total_end_number0=total_end_number0,
                        total_end_number1=total_end_number0 + end_delta,
                        end_number0=end_number0,
                        end_number1=end_number0 + end_delta,
                        end_repeat_number=end_repeat_number,
                    )
                match post_action:
                    case "cancel":
                        replies = send_command(
                            client, dict(type="jump_to_end", total_end_number0=None)
                        )
                        assert len(replies) == 2
                        jump_end_cancel_reply = SimpleNamespace(**replies[0])
                        assert jump_end_cancel_reply == SimpleNamespace(
                            type="JumpEndNumber",
                            total_end_number0=None,
                            total_end_number1=None,
                            end_number0=None,
                            end_number1=None,
                            end_repeat_number=None,
                        )
                    case "next":
                        # Test against jump_end_reply because we already
                        # checked that against expected values.
                        command_next_end(
                            client=client,
                            expected_end_number0=jump_end_reply.end_number0,
                            expected_end_number1=jump_end_reply.end_number1,
                            expected_repeat_number=jump_end_reply.end_repeat_number,
                            jump_pending=True,
                        )
                    case "nothing":
                        pass
                    case _:
                        raise RuntimeError(f"Unsupported {post_action=!r}")

    def test_jump_to_pick(self) -> None:
        pattern_name = ALL_PATTERN_PATHS[3].name

        with self.create_test_client(
            app=self.app,
            num_shafts=32,
            upload_patterns=ALL_PATTERN_PATHS[2:5],
        ) as client:
            pattern = select_pattern(client=client, pattern_name=pattern_name)
            num_picks_in_pattern = len(pattern.picks)

            # post_action sets what to do after sending the jump_to_pick cmd:
            # * cancel: cancel the jump_to_pick
            # * next: advance to the next pick (thus accepting the jump)
            # * nothing: do nothing
            for post_action, pick_number, pick_repeat_number in itertools.product(
                ("cancel", "next", "nothing"),
                (0, 1, num_picks_in_pattern // 3, num_picks_in_pattern),
                (-1, 0, 1, 2),
            ):
                total_picks = compute_total_num(
                    num_within=pick_number,
                    repeat_number=pick_repeat_number,
                    repeat_len=num_picks_in_pattern,
                )
                replies = send_command(
                    client,
                    dict(type="jump_to_pick", total_picks=total_picks),
                )
                assert len(replies) == 2
                jump_pick_reply = SimpleNamespace(**replies[0])
                if total_picks == 0:
                    # Jump to pick_number 0, repeat_number 1.
                    assert jump_pick_reply == SimpleNamespace(
                        type="JumpPickNumber",
                        total_picks=0,
                        pick_number=0,
                        pick_repeat_number=1,
                    )
                elif pick_number == 0:
                    # Jump to pick_number 0, repeat_number not 1.
                    # Report the last pick of the previous repeat,
                    # rather than the magic "0" pick_number
                    assert jump_pick_reply == SimpleNamespace(
                        type="JumpPickNumber",
                        total_picks=total_picks,
                        pick_number=num_picks_in_pattern,
                        pick_repeat_number=pick_repeat_number - 1,
                    )
                else:
                    # Jump to a nonzero pick_number.
                    assert jump_pick_reply == SimpleNamespace(
                        type="JumpPickNumber",
                        total_picks=total_picks,
                        pick_number=pick_number,
                        pick_repeat_number=pick_repeat_number,
                    )
                match post_action:
                    case "cancel":
                        replies = send_command(
                            client, dict(type="jump_to_pick", total_picks=None)
                        )
                        assert len(replies) == 2
                        jump_pick_cancel_reply = SimpleNamespace(**replies[0])
                        assert jump_pick_cancel_reply == SimpleNamespace(
                            type="JumpPickNumber",
                            total_picks=None,
                            pick_number=None,
                            pick_repeat_number=None,
                        )
                    case "next":
                        command_next_pick(
                            client=client,
                            expected_pick_number=jump_pick_reply.pick_number,
                            expected_repeat_number=jump_pick_reply.pick_repeat_number,
                            expected_shaft_word=pattern.get_pick(
                                jump_pick_reply.pick_number
                            ).shaft_word,
                            jump_pending=True,
                        )
                    case "nothing":
                        pass
                    case _:
                        raise RuntimeError(f"Unsupported {post_action=!r}")

    def test_next_end(self) -> None:
        pattern_name = ALL_PATTERN_PATHS[1].name

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:3],
        ) as client:
            pattern = select_pattern(client=client, pattern_name=pattern_name)
            num_ends_in_pattern = len(pattern.threading)

            replies = send_command(client, dict(type="mode", mode=ModeEnum.THREAD))
            assert len(replies) == 2
            assert replies[0] == dict(type="Mode", mode=ModeEnum.THREAD)

            for separate_threading_repeats, thread_group_size in itertools.product(
                (False, True),
                (
                    1,
                    2,
                    3,
                    num_ends_in_pattern - 1,
                    num_ends_in_pattern,
                    num_ends_in_pattern + 1,
                ),
            ):
                print(f"{separate_threading_repeats=}, {thread_group_size=}")
                pattern.set_current_end_number(end_number0=0, end_repeat_number=1)
                expected_end_number0 = 0
                expected_end_number1 = 0
                expected_repeat_number = 1

                # Start threading low to high
                assert client.loom_server.thread_low_to_high

                replies = send_command(
                    client,
                    dict(
                        type="separate_threading_repeats",
                        separate=separate_threading_repeats,
                    ),
                )
                assert len(replies) == 2
                assert replies[0] == dict(
                    type="SeparateThreadingRepeats", separate=separate_threading_repeats
                )
                assert pattern.separate_threading_repeats == separate_threading_repeats

                replies = send_command(
                    client, dict(type="thread_group_size", group_size=thread_group_size)
                )
                assert len(replies) == 2
                assert replies[0] == dict(
                    type="ThreadGroupSize", group_size=thread_group_size
                )
                assert pattern.thread_group_size == thread_group_size

                # Make enough low_to_high end advances to get into 3rd repeat
                expected_end_number0 = 0
                expected_repeat_number = 1
                while expected_repeat_number < 3:
                    if expected_end_number1 == 0:
                        expected_end_number0 = 1
                    elif expected_end_number1 <= num_ends_in_pattern:
                        expected_end_number0 = expected_end_number1
                    else:
                        # Wrap around
                        expected_end_number0 = (
                            0 if pattern.separate_threading_repeats else 1
                        )
                        expected_repeat_number += 1
                    if expected_end_number0 == 0:
                        expected_end_number1 = 0
                    else:
                        expected_end_number1 = min(
                            expected_end_number0 + thread_group_size,
                            num_ends_in_pattern + 1,
                        )
                    command_next_end(
                        client=client,
                        expected_end_number0=expected_end_number0,
                        expected_end_number1=expected_end_number1,
                        expected_repeat_number=expected_repeat_number,
                    )

                # Change to unthreading (high to low)
                change_direction(client)
                assert not client.loom_server.thread_low_to_high

                iter_past_beginning = 0
                while iter_past_beginning < 2:
                    if expected_end_number0 == 0 or (
                        expected_end_number0 == 1 and not separate_threading_repeats
                    ):
                        # Wrap around
                        expected_end_number1 = num_ends_in_pattern + 1
                        expected_end_number0 = max(
                            1, num_ends_in_pattern + 1 - thread_group_size
                        )
                        expected_repeat_number -= 1
                    elif expected_end_number0 == 1:
                        expected_end_number0 = 0
                        expected_end_number1 = 0
                    else:
                        expected_end_number1 = expected_end_number0
                        expected_end_number0 = max(
                            1, expected_end_number0 - thread_group_size
                        )
                    if expected_repeat_number <= 0:
                        iter_past_beginning += 1

                    command_next_end(
                        client=client,
                        expected_end_number0=expected_end_number0,
                        expected_end_number1=expected_end_number1,
                        expected_repeat_number=expected_repeat_number,
                    )
                assert expected_repeat_number <= 0

                # Go back to threading
                change_direction(client)
                assert client.loom_server.thread_low_to_high

    def test_next_pick(self) -> None:
        pattern_name = ALL_PATTERN_PATHS[2].name

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:3],
        ) as client:
            pattern = select_pattern(client=client, pattern_name=pattern_name)
            num_picks_in_pattern = len(pattern.picks)

            # Make enough forward picks to get into the 3rd repeat
            expected_pick_number = 0
            expected_repeat_number = 1
            i = 0
            while not (expected_repeat_number == 3 and expected_pick_number > 2):
                i += 1
                expected_pick_number += 1
                if expected_pick_number > num_picks_in_pattern:
                    expected_pick_number = 0 if pattern.separate_weaving_repeats else 1
                    expected_repeat_number += 1
                expected_shaft_word = pattern.get_pick(expected_pick_number).shaft_word
                command_next_pick(
                    client=client,
                    expected_pick_number=expected_pick_number,
                    expected_repeat_number=expected_repeat_number,
                    expected_shaft_word=expected_shaft_word,
                )

            change_direction(client=client)

            # Now go backwards at least two picks past the beginning
            end_pick_number = num_picks_in_pattern - 2
            while not (
                expected_pick_number == end_pick_number and expected_repeat_number == 0
            ):
                expected_pick_number -= 1
                if (expected_pick_number < 0) or (
                    expected_pick_number == 0 and not pattern.separate_weaving_repeats
                ):
                    expected_pick_number = num_picks_in_pattern
                    expected_repeat_number -= 1
                expected_shaft_word = pattern.get_pick(expected_pick_number).shaft_word
                command_next_pick(
                    client=client,
                    expected_pick_number=expected_pick_number,
                    expected_repeat_number=expected_repeat_number,
                    expected_shaft_word=expected_shaft_word,
                )
            assert expected_pick_number == end_pick_number
            assert expected_repeat_number == 0

            # Change direction to forward
            change_direction(client)
            expected_pick_number += 1

            expected_shaft_word = pattern.get_pick(expected_pick_number).shaft_word
            command_next_pick(
                client=client,
                expected_pick_number=expected_pick_number,
                expected_repeat_number=expected_repeat_number,
                expected_shaft_word=expected_shaft_word,
            )

    def test_pattern_persistence(self) -> None:
        rnd = random.Random(47)
        pattern_list = []
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = pathlib.Path(temp_dir) / "loom_server_database.sqlite"
            with self.create_test_client(
                app=self.app,
                upload_patterns=ALL_PATTERN_PATHS,
                db_path=db_path,
            ) as client:
                # Select a few patterns; for each one jump to some random
                # pick (including actually going to that pick).
                assert len(ALL_PATTERN_PATHS) > 3
                for path in (ALL_PATTERN_PATHS[0], ALL_PATTERN_PATHS[3]):
                    pattern = select_pattern(client=client, pattern_name=path.name)
                    pattern_list.append(pattern)
                    pattern.pick_number = rnd.randrange(2, len(pattern.picks))
                    pattern.pick_repeat_number = rnd.randrange(-10, 10)
                    pattern.thread_group_size = rnd.randrange(1, 10)
                    num_picks_in_pattern = len(pattern.picks)
                    total_picks = compute_total_num(
                        num_within=pattern.pick_number,
                        repeat_number=pattern.pick_repeat_number,
                        repeat_len=num_picks_in_pattern,
                    )
                    replies = send_command(
                        client,
                        dict(type="jump_to_pick", total_picks=total_picks),
                    )
                    assert len(replies) == 2
                    if total_picks == 0:
                        assert replies[0] == dict(
                            type="JumpPickNumber",
                            total_picks=0,
                            pick_number=0,
                            pick_repeat_number=1,
                        )
                    elif pattern.pick_number == 0 and total_picks != 0:
                        # Special case: report the last pick of the previous
                        # repeat, rather than the magic "0" pick_number
                        assert replies[0] == dict(
                            type="JumpPickNumber",
                            total_picks=total_picks,
                            pick_number=num_picks_in_pattern,
                            pick_repeat_number=pattern.pick_repeat_number - 1,
                        )
                    else:
                        assert replies[0] == dict(
                            type="JumpPickNumber",
                            total_picks=total_picks,
                            pick_number=pattern.pick_number,
                            pick_repeat_number=pattern.pick_repeat_number,
                        )
                    expected_pick_number = pattern.pick_number
                    expected_shaft_word = pattern.get_pick(
                        expected_pick_number
                    ).shaft_word
                    command_next_pick(
                        client=client,
                        jump_pending=True,
                        expected_pick_number=expected_pick_number,
                        expected_repeat_number=pattern.pick_repeat_number,
                        expected_shaft_word=expected_shaft_word,
                    )

                    replies = send_command(
                        client,
                        dict(
                            type="thread_group_size",
                            group_size=pattern.thread_group_size,
                        ),
                    )
                    assert len(replies) == 2
                    assert replies[0] == dict(
                        type="ThreadGroupSize",
                        group_size=pattern.thread_group_size,
                    )

            # This expects that first pattern 0 and then pattern 3
            # was selected from ALL_PATTERN_PATHS:
            all_pattern_names = [path.name for path in ALL_PATTERN_PATHS]
            expected_pattern_names = (
                all_pattern_names[1:3]
                + all_pattern_names[4:]
                + [all_pattern_names[0], all_pattern_names[3]]
            )
            expected_current_pattern = pattern_list[1]

            with self.create_test_client(
                app=self.app,
                reset_db=False,
                expected_pattern_names=expected_pattern_names,
                expected_current_pattern=expected_current_pattern,
                db_path=db_path,
            ) as client:
                for pattern in pattern_list:
                    returned_pattern = select_pattern(
                        client=client,
                        pattern_name=pattern.name,
                        check_defaults=False,
                    )
                    assert returned_pattern == pattern

            # Now try again, but this time reset the database
            with self.create_test_client(
                app=self.app,
                reset_db=True,
            ) as client:
                pass

    def test_select_pattern(self) -> None:
        # Read a pattern file in and convert the data to a ReducedPattern
        pattern_path = ALL_PATTERN_PATHS[1]
        pattern_data = read_pattern_file(pattern_path)
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=pattern_path.name, data=pattern_data
        )

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:3],
        ) as client:
            selected_pattern = select_pattern(
                client=client, pattern_name=pattern_path.name
            )
            assert selected_pattern == reduced_pattern

    def test_upload(self) -> None:
        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS,
        ) as _:
            pass

    def test_upload_too_many_shafts(self) -> None:
        # Pick a file with 18 shafts
        filename = "eighteen shaft liftplan.wif"
        filepath = TEST_DATA_FILES / filename
        with self.create_test_client(
            app=self.app,
            num_shafts=16,
        ) as client:
            upload_pattern(
                client=client, filepath=filepath, expected_names=[""], should_fail=True
            )

    def test_weave_direction(self) -> None:
        pattern_name = ALL_PATTERN_PATHS[1].name

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:4],
        ) as client:
            if not client.loom_server.enable_software_direction:
                raise pytest.skip("Weave direction cannot be controlled by software")

            select_pattern(client=client, pattern_name=pattern_name)

            for forward in (False, True):
                replies = send_command(client, dict(type="direction", forward=forward))
                assert len(replies) == 2
                assert replies[0]["type"] == "Direction"
                assert replies[0]["forward"] == forward

    @classmethod
    @contextlib.contextmanager
    def create_test_client(
        cls,
        app: FastAPI | None,
        num_shafts: int = 24,
        read_initial_state: bool = True,
        upload_patterns: Iterable[pathlib.Path] = (),
        reset_db: bool = False,
        db_path: pathlib.Path | str | None = None,
        expected_status_messages: Iterable[str] = (),
        expected_pattern_names: Iterable[str] = (),
        expected_current_pattern: ReducedPattern | None = None,
    ) -> Generator[Client]:
        """Create a test client fixture.

        Args:
            app: Server application to test. If None, raise an error.
            num_shafts: The number of shafts that the loom has.
            read_initial_state: If true, read and check the initial server
                replies from the websocket. This is the most common case.
            upload_patterns: Initial patterns to upload, if any.
            reset_db: Specify argument `--reset-db`?
                If False, you should also specify `expected_pattern_names`
            db_path: `--db-path` argument value. If None, use a temp file.
                If not None and you expect the database to contain any
                patterns, then also specify `expected_pattern_names`
                and `expected_current_pattern`.
            expected_status_messages: Expected status messages when
                the connection is made, in order.
                All should have severity level INFO.
            expected_pattern_names: Expected pattern names, in order.
                Specify if and only if `db_path` is not None
                and you expect the database to contain these patterns.
            expected_current_pattern: Expected_current_pattern.
                Specify if and only if `db_path` is not None and
                you expect the database to contain any patterns.
        """
        expected_pattern_names = list(expected_pattern_names)
        expected_status_messages = list(expected_status_messages)
        if app is None:
            raise AssertionError(
                "app is None but must be a FastAPI; "
                "you must set the app class property in your subclass"
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            if db_path is None:
                db_path = pathlib.Path(temp_dir) / "loom_server_database.sqlite"
            argv = ["testutils", str(num_shafts), "mock", "--verbose"] + list(
                cls.extra_args
            )
            if reset_db:
                argv.append("--reset-db")
            argv += ["--db-path", str(db_path)]
            sys.argv = argv

            with TestClient(app) as test_client:
                with test_client.websocket_connect("/ws") as websocket:
                    loom_server: BaseLoomServer = test_client.app.state.loom_server  # type: ignore
                    assert loom_server.mock_loom is not None
                    assert loom_server.settings.loom_name == loom_server.default_name
                    assert loom_server.loom_info.num_shafts == num_shafts

                    client = Client(
                        test_client=test_client,
                        websocket=websocket,
                        loom_server=loom_server,
                        mock_loom=loom_server.mock_loom,
                    )

                    if read_initial_state:
                        seen_types: set[str] = set()
                        expected_types = {
                            "JumpEndNumber",
                            "JumpPickNumber",
                            "LoomConnectionState",
                            "LoomInfo",
                            "Mode",
                            "PatternNames",
                            "Settings",
                            "ShaftState",
                            "Direction",
                        }
                        if expected_status_messages:
                            expected_types |= {"StatusMessage"}
                        if expected_current_pattern:
                            expected_types |= {
                                "CurrentPickNumber",
                                "CurrentEndNumber",
                                "ReducedPattern",
                                "SeparateWeavingRepeats",
                                "SeparateThreadingRepeats",
                                "ThreadGroupSize",
                            }
                        good_connection_states = {
                            ConnectionStateEnum.CONNECTING,
                            ConnectionStateEnum.CONNECTED,
                        }
                        while True:
                            reply_dict = client.receive_dict()
                            reply = SimpleNamespace(**reply_dict)
                            num_status_messages_seen = 0
                            match reply.type:
                                case "CurrentEndNumber":
                                    assert expected_current_pattern is not None
                                    assert (
                                        reply.end_number0
                                        == expected_current_pattern.end_number0
                                    )
                                    assert (
                                        reply.end_number1
                                        == expected_current_pattern.end_number1
                                    )
                                    assert (
                                        reply.end_repeat_number
                                        == expected_current_pattern.end_repeat_number
                                    )
                                    assert reply.total_end_number0 == compute_total_num(
                                        num_within=expected_current_pattern.end_number0,
                                        repeat_number=expected_current_pattern.end_repeat_number,
                                        repeat_len=expected_current_pattern.num_ends,
                                    )
                                    assert reply.total_end_number1 == compute_total_num(
                                        num_within=expected_current_pattern.end_number1,
                                        repeat_number=expected_current_pattern.end_repeat_number,
                                        repeat_len=expected_current_pattern.num_ends,
                                    )
                                case "CurrentPickNumber":
                                    assert expected_current_pattern is not None
                                    assert (
                                        reply.pick_number
                                        == expected_current_pattern.pick_number
                                    )
                                    assert (
                                        reply.pick_repeat_number
                                        == expected_current_pattern.pick_repeat_number
                                    )
                                    assert reply.total_picks == compute_total_num(
                                        num_within=expected_current_pattern.pick_number,
                                        repeat_number=expected_current_pattern.pick_repeat_number,
                                        repeat_len=len(expected_current_pattern.picks),
                                    )

                                case "JumpEndNumber":
                                    for field_name, value in vars(reply).items():
                                        if field_name == "type":
                                            continue
                                        assert value is None
                                case "JumpPickNumber":
                                    for field_name, value in vars(reply).items():
                                        if field_name == "type":
                                            continue
                                        assert value is None
                                case "LoomConnectionState":
                                    if reply.state not in good_connection_states:
                                        raise AssertionError(
                                            f"Unexpected state in {reply=}; "
                                            f"should be in {good_connection_states}"
                                        )
                                    elif reply.state != ConnectionStateEnum.CONNECTED:
                                        continue
                                case "LoomInfo":
                                    assert vars(reply) == dataclasses.asdict(
                                        loom_server.loom_info
                                    )
                                case "Mode":
                                    assert reply.mode == ModeEnum.WEAVE
                                case "PatternNames":
                                    assert reply.names == expected_pattern_names
                                case "ReducedPattern":
                                    if not expected_pattern_names:
                                        raise AssertionError(
                                            f"Unexpected message type {reply.type} "
                                            "because expected_current_pattern is None"
                                        )

                                    assert reply.name == expected_pattern_names[-1]
                                case "SeparateThreadingRepeats":
                                    assert expected_current_pattern is not None
                                    assert (
                                        reply.separate
                                        == expected_current_pattern.separate_threading_repeats
                                    )
                                case "SeparateWeavingRepeats":
                                    assert expected_current_pattern is not None
                                    assert (
                                        reply.separate
                                        == expected_current_pattern.separate_weaving_repeats
                                    )
                                case "Settings":
                                    assert vars(reply) == dataclasses.asdict(
                                        loom_server.settings
                                    )
                                case "ShaftState":
                                    assert reply.state == ShaftStateEnum.DONE
                                    assert reply.shaft_word == 0
                                case "StatusMessage":
                                    num_status_messages_seen += 1
                                    assert (
                                        reply.message
                                        == expected_status_messages[
                                            num_status_messages_seen - 1
                                        ]
                                    )
                                    assert reply.severity == MessageSeverityEnum.INFO
                                case "ThreadGroupSize":
                                    assert expected_current_pattern is not None
                                    assert (
                                        reply.group_size
                                        == expected_current_pattern.thread_group_size
                                    )
                                case "Direction":
                                    assert reply.forward
                                case _:
                                    raise AssertionError(
                                        f"Unexpected message type {reply.type}"
                                    )
                            seen_types.add(reply.type)
                            if (
                                seen_types == expected_types
                                and num_status_messages_seen
                                == len(expected_status_messages)
                            ):
                                break

                    expected_names: list[str] = []
                    for filepath in upload_patterns:
                        expected_names.append(filepath.name)
                        upload_pattern(
                            client=client,
                            filepath=filepath,
                            expected_names=expected_names,
                        )

                    yield client
