import base64
import contextlib
import copy
import dataclasses
import importlib.resources
import itertools
import json
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

from .base_loom_server import MAX_THREAD_GROUP_SIZE, SETTINGS_FILE_NAME, BaseLoomServer
from .base_mock_loom import BaseMockLoom
from .enums import (
    ConnectionStateEnum,
    DirectionControlEnum,
    MessageSeverityEnum,
    ModeEnum,
    ShaftStateEnum,
)
from .reduced_pattern import (
    DEFAULT_THREAD_GROUP_SIZE,
    NUM_ITEMS_FOR_REPEAT_SEPARATOR,
    ReducedPattern,
    reduced_pattern_from_pattern_data,
)
from .utils import compute_total_num

WebSocketType: TypeAlias = WebSocket | WebSocketTestSession

_PKG_NAME = "base_loom_server"
TEST_DATA_FILES = importlib.resources.files(_PKG_NAME) / "test_data" / "pattern_files"

# in Python 3.11 mypy complains: "Traversable" has no attribute "glob"
ALL_PATTERN_PATHS: tuple[pathlib.Path, ...] = (
    *TEST_DATA_FILES.glob("*.wif"),  # type: ignore[attr-defined]
    *TEST_DATA_FILES.glob("*.dtx"),  # type: ignore[attr-defined]
    *TEST_DATA_FILES.glob("*.wpo"),  # type: ignore[attr-defined]
)


def assert_replies_equal(reply: dict[str, Any], expected_reply: dict[str, Any]) -> None:
    """Assert a portion of a reply matches the expected data.

    Only check items that are present in `expected_reply`.
    """
    for key, value in expected_reply.items():
        if value is not None and reply.get(key) != value:
            raise AssertionError(f"{reply=} != {expected_reply}: failed on field {key!r}")


class Client:
    """Client for testing loom servers."""

    def __init__(
        self,
        test_client: TestClient,
        loom_server: BaseLoomServer,
        mock_loom: BaseMockLoom,
        websocket: WebSocketType,
    ) -> None:
        self.test_client = test_client
        self.loom_server = loom_server
        self.mock_loom = mock_loom
        self.websocket = websocket

    def send_dict(self, datadict: dict[str, Any]) -> None:
        """Write a dict as json."""
        self.websocket.send_json(datadict)

    def receive_dict(self) -> dict[str, Any]:
        """Read json as a dict."""
        data: Any = self.websocket.receive_json()
        assert isinstance(data, dict)
        return data

    def change_direction(self) -> None:
        """Command the loom to weave or thread in the opposite direction,
        and read and check the reply, if one is expected.

        Use a software command, if the loom supports that,
        else an oob command.

        Args:
            client: Client fixture.
        """
        expected_direction_reply = True
        self.mock_loom.command_threading_event.clear()
        if self.loom_server.enable_software_direction:
            direction_forward = not self.loom_server.direction_forward
            replies = self.send_command(dict(type="direction", forward=direction_forward))
        else:
            expected_direction_reply = self.loom_server.loom_reports_direction
            direction_forward = not self.mock_loom.direction_forward
            replies = self.send_command(dict(type="oobcommand", command="d"))

        if expected_direction_reply:
            assert len(replies) == 2  # noqa: PLR2004
            assert replies[0]["type"] == "Direction"
            assert replies[0]["forward"] == direction_forward
        else:
            assert len(replies) == 1
            # Give the loom self time to process the command
            self.mock_loom.command_threading_event.wait(timeout=1)

    def command_next_end(
        self,
        *,
        expected_end_number0: int,
        expected_end_number1: int,
        expected_repeat_number: int,
        jump_pending: bool = False,
    ) -> None:
        """Command the next threading end group and test the replies.

        Ignore info-level StatusMessage

        Args:
            expected_end_number0: Expected end number0 of the next end group.
            expected_end_number1: Expected end number1 of the next end group.
            expected_repeat_number: Expected repeat number of the next end group.
            jump_pending: Is a jump pending?
        """
        pattern = self.loom_server.current_pattern
        assert pattern is not None

        self.mock_loom.command_threading_event.clear()

        replies = self.send_command(dict(type="oobcommand", command="n"))
        assert len(replies) == 1
        # Give the loom client time to process the command
        self.mock_loom.command_threading_event.wait(timeout=1)

        expected_shaft_word = pattern.get_threading_shaft_word()
        expected_replies: list[dict[str, Any]] = []
        if jump_pending:
            expected_replies += [
                dict(
                    type="JumpEndNumber",
                    end_number0=None,
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
        if self.loom_server.loom_reports_motion:
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
            reply = self.receive_dict()
            if reply["type"] == "ServerMessage" and reply["severity"] == MessageSeverityEnum.INFO:
                # Ignore info-level status messages
                continue
            assert_replies_equal(reply, expected_reply)

    def command_next_pick(
        self,
        *,
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
        replies = self.send_command(dict(type="oobcommand", command="n"))
        assert len(replies) == 1
        expected_replies: list[dict[str, Any]] = []
        if (
            not self.loom_server.enable_software_direction
            and not self.loom_server.loom_reports_direction
            and self.loom_server.direction_forward != self.mock_loom.direction_forward
        ):
            # Loom only reports direction when it asks for a pick
            # and the direction has changed
            expected_replies += [
                dict(
                    type="Direction",
                    forward=self.mock_loom.direction_forward,
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
        if self.loom_server.loom_reports_motion:
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
            reply = self.receive_dict()
            if reply["type"] == "ServerMessage" and reply["severity"] == MessageSeverityEnum.INFO:
                # Ignore info-level status messages
                continue
            assert_replies_equal(reply, expected_reply)

    def command_settings(
        self,
        *,
        should_fail: bool = False,
        **settings: Any,  # noqa: ANN401
    ) -> None:
        """Send a setting command and check the replies."""
        settings_cmd = settings.copy()
        initial_settings = copy.copy(self.loom_server.settings)
        settings_cmd["type"] = "settings"
        replies = self.send_command(settings_cmd, should_fail=should_fail)
        if should_fail:
            assert len(replies) == 1
            assert self.loom_server.settings == initial_settings
        else:
            assert len(replies) == 2  # noqa: PLR2004
            reported_settings = replies[0]
            for key, value in settings.items():
                assert reported_settings[key] == value
            for key, value in reported_settings.items():
                assert getattr(self.loom_server.settings, key) == value
        expected_thread_low_to_high = (
            self.loom_server.settings.thread_back_to_front == self.loom_server.settings.thread_right_to_left
        )
        if not self.loom_server.direction_forward:
            expected_thread_low_to_high = not expected_thread_low_to_high
        if not self.loom_server.settings.end1_on_right:
            expected_thread_low_to_high = not expected_thread_low_to_high
        assert self.loom_server.thread_low_to_high == expected_thread_low_to_high

    def select_pattern(
        self,
        *,
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
                have the expected default value. This is only safe for patterns
                that are newly loaded, or have not been woven on or threaded
                since being loaded.

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

        replies = self.send_command(dict(type="select_pattern", name=pattern_name))
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
                    assert reply.total_pick_number == compute_total_num(
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
        assert self.loom_server.current_pattern is not None
        return self.loom_server.current_pattern

    def send_command(self, cmd_dict: dict[str, Any], *, should_fail: bool = False) -> list[dict[str, Any]]:
        """Issue a command and return all replies.

        Args:
            client: Test self.
            cmd_dict: Command to send, as a dict.
            should_fail: If true, upload should fail.

        Returns:
            replies: a list of replies (as dicts).
            The final reply will be CommandDone and its success flag is checked
        """
        self.send_dict(cmd_dict)
        replies: list[dict[str, Any]] = []
        while True:
            reply = self.receive_dict()
            replies.append(reply)
            if reply["type"] == "CommandDone":
                if should_fail == reply["success"]:
                    if should_fail:
                        raise AssertionError(f"Command {cmd_dict} succeeded, but should have failed")
                    raise AssertionError(f"Command {cmd_dict} failed")
                break
        return replies

    def upload_pattern(
        self,
        *,
        filepath: Traversable,
        expected_names: Iterable[str],
        should_fail: bool = False,
    ) -> None:
        """Upload a pattern to the loom server.

        Check expected replies.

        Args:
            client: Test self.
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
            data = filepath.read_text(encoding="utf_8")
        replies = self.send_command(
            dict(type="upload", name=filepath.name, data=data),
            should_fail=should_fail,
        )
        if should_fail:
            assert len(replies) == 1
        else:
            assert len(replies) == 2  # noqa: PLR2004
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
        """Test the jump_to_end command."""
        pattern_name = ALL_PATTERN_PATHS[4].name

        with self.create_test_client(
            app=self.app,
            num_shafts=32,
            upload_patterns=ALL_PATTERN_PATHS[2:5],
        ) as client:
            pattern = client.select_pattern(pattern_name=pattern_name)
            num_ends_in_pattern = len(pattern.threading)

            replies = client.send_command(dict(type="mode", mode=ModeEnum.THREAD))
            assert len(replies) == 2  # noqa: PLR2004
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
                (1, 2),
            ):
                replies = client.send_command(dict(type="thread_group_size", group_size=thread_group_size))
                assert len(replies) == 2  # noqa: PLR2004
                assert replies[0] == dict(type="ThreadGroupSize", group_size=thread_group_size)
                assert pattern.thread_group_size == thread_group_size

                total_end_number0 = compute_total_num(
                    num_within=end_number0,
                    repeat_number=end_repeat_number,
                    repeat_len=num_ends_in_pattern,
                )
                replies = client.send_command(
                    dict(type="jump_to_end", total_end_number0=total_end_number0),
                )
                assert len(replies) == 2  # noqa: PLR2004
                jump_end_reply = SimpleNamespace(**replies[0])
                if total_end_number0 == 0:
                    # Jump to warp thread_number0 0, repeat_number 1.
                    assert jump_end_reply == SimpleNamespace(
                        type="JumpEndNumber",
                        total_end_number0=0,
                        total_end_number1=0,
                        end_number0=0,
                        end_number1=0,
                        end_repeat_number=1,
                    )
                elif end_number0 == 0:
                    # Jump to warp thread_number0 0, repeat_number not 1.
                    # Report the last end of the previous repeat,
                    # rather than the magic "0" end_number0
                    assert jump_end_reply == SimpleNamespace(
                        type="JumpEndNumber",
                        total_end_number0=total_end_number0,
                        total_end_number1=total_end_number0,
                        end_number0=num_ends_in_pattern,
                        end_number1=num_ends_in_pattern,
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
                        replies = client.send_command(dict(type="jump_to_end", total_end_number0=None))
                        assert len(replies) == 2  # noqa: PLR2004
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
                        client.command_next_end(
                            expected_end_number0=jump_end_reply.end_number0,
                            expected_end_number1=jump_end_reply.end_number1,
                            expected_repeat_number=jump_end_reply.end_repeat_number,
                            jump_pending=True,
                        )
                    case "nothing":
                        pass
                    case _:
                        raise RuntimeError(f"Unsupported {post_action=!r}")

            # Test jumping to invalid ends, including
            # that the bad command doesn't change the pattern's end numbers.
            end_field_names = ("end_number0", "end_number1", "end_repeat_number")
            current_end_data = {
                field_name: getattr(client.loom_server.current_pattern, field_name)
                for field_name in end_field_names
            }
            for bad_total_end_number0 in (-1, -2):
                client.send_command(
                    dict(type="jump_to_end", total_end_number0=bad_total_end_number0),
                    should_fail=True,
                )
                for field_name in end_field_names:
                    assert (
                        getattr(client.loom_server.current_pattern, field_name)
                        == current_end_data[field_name]
                    )

    def test_jump_to_pick(self) -> None:
        """Test the jump_to_pick command."""
        pattern_name = ALL_PATTERN_PATHS[3].name

        with self.create_test_client(
            app=self.app,
            num_shafts=32,
            upload_patterns=ALL_PATTERN_PATHS[2:5],
        ) as client:
            pattern = client.select_pattern(pattern_name=pattern_name)
            num_picks_in_pattern = len(pattern.picks)

            # post_action sets what to do after sending the jump_to_pick cmd:
            # * cancel: cancel the jump_to_pick
            # * next: advance to the next pick (thus accepting the jump)
            # * nothing: do nothing
            for post_action, pick_number, pick_repeat_number in itertools.product(
                ("cancel", "next", "nothing"),
                (0, 1, num_picks_in_pattern // 3, num_picks_in_pattern),
                (1, 2),
            ):
                total_pick_number = compute_total_num(
                    num_within=pick_number,
                    repeat_number=pick_repeat_number,
                    repeat_len=num_picks_in_pattern,
                )
                replies = client.send_command(dict(type="jump_to_pick", total_pick_number=total_pick_number))
                assert len(replies) == 2  # noqa: PLR2004
                jump_pick_reply = SimpleNamespace(**replies[0])
                if total_pick_number == 0:
                    # Jump to pick_number 0, repeat_number 1.
                    assert jump_pick_reply == SimpleNamespace(
                        type="JumpPickNumber",
                        total_pick_number=0,
                        pick_number=0,
                        pick_repeat_number=1,
                    )
                elif pick_number == 0:
                    # Jump to pick_number 0, repeat_number not 1.
                    # Report the last pick of the previous repeat,
                    # rather than the magic "0" pick_number
                    assert jump_pick_reply == SimpleNamespace(
                        type="JumpPickNumber",
                        total_pick_number=total_pick_number,
                        pick_number=num_picks_in_pattern,
                        pick_repeat_number=pick_repeat_number - 1,
                    )
                else:
                    # Jump to a nonzero pick_number.
                    assert jump_pick_reply == SimpleNamespace(
                        type="JumpPickNumber",
                        total_pick_number=total_pick_number,
                        pick_number=pick_number,
                        pick_repeat_number=pick_repeat_number,
                    )
                match post_action:
                    case "cancel":
                        replies = client.send_command(dict(type="jump_to_pick", total_pick_number=None))
                        assert len(replies) == 2  # noqa: PLR2004
                        jump_pick_cancel_reply = SimpleNamespace(**replies[0])
                        assert jump_pick_cancel_reply == SimpleNamespace(
                            type="JumpPickNumber",
                            total_pick_number=None,
                            pick_number=None,
                            pick_repeat_number=None,
                        )
                    case "next":
                        client.command_next_pick(
                            expected_pick_number=jump_pick_reply.pick_number,
                            expected_repeat_number=jump_pick_reply.pick_repeat_number,
                            expected_shaft_word=pattern.get_pick(jump_pick_reply.pick_number).shaft_word,
                            jump_pending=True,
                        )
                    case "nothing":
                        pass
                    case _:
                        raise RuntimeError(f"Unsupported {post_action=!r}")

            # Test jumping to invalid picks, including
            # that the bad command doesn't change the pattern's pick numbers.
            pick_field_names = ("pick_number", "pick_repeat_number")
            current_pick_data = {
                field_name: getattr(client.loom_server.current_pattern, field_name)
                for field_name in pick_field_names
            }
            for bad_total_pick_number in (-1, -2):
                client.send_command(
                    dict(type="jump_to_pick", total_pick_number=bad_total_pick_number),
                    should_fail=True,
                )
                for field_name in pick_field_names:
                    assert (
                        getattr(client.loom_server.current_pattern, field_name)
                        == current_pick_data[field_name]
                    )

    def test_next_end(self) -> None:
        """Test advancing to the next end."""
        pattern_name = ALL_PATTERN_PATHS[1].name

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:3],
        ) as client:
            pattern = client.select_pattern(pattern_name=pattern_name)
            num_ends_in_pattern = len(pattern.threading)

            replies = client.send_command(dict(type="mode", mode=ModeEnum.THREAD))
            assert len(replies) == 2  # noqa: PLR2004
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
                print(  # noqa: T201
                    f"{separate_threading_repeats=}, {thread_group_size=}"
                )

                # Restore initial state that we care about.
                client.loom_server.settings.end1_on_right = True
                client.loom_server.settings.thread_back_to_front = True
                client.loom_server.settings.thread_right_to_left = True
                client.loom_server.direction_forward = True
                pattern.set_current_end_number(end_number0=0, end_repeat_number=1)
                expected_end_number0 = 0
                expected_end_number1 = 0
                expected_repeat_number = 1

                # Start threading low to high
                assert client.loom_server.thread_low_to_high

                replies = client.send_command(
                    dict(
                        type="separate_threading_repeats",
                        separate=separate_threading_repeats,
                    ),
                )
                assert len(replies) == 2  # noqa: PLR2004
                assert replies[0] == dict(
                    type="SeparateThreadingRepeats", separate=separate_threading_repeats
                )
                assert pattern.separate_threading_repeats == separate_threading_repeats

                replies = client.send_command(dict(type="thread_group_size", group_size=thread_group_size))
                assert len(replies) == 2  # noqa: PLR2004
                assert replies[0] == dict(type="ThreadGroupSize", group_size=thread_group_size)
                assert pattern.thread_group_size == thread_group_size

                # Make enough low_to_high end advances to get into 3rd repeat
                expected_end_number0 = 0
                expected_repeat_number = 1
                while expected_repeat_number < 3:  # noqa: PLR2004
                    (
                        expected_end_number0,
                        expected_end_number1,
                        expected_repeat_number,
                    ) = pattern.compute_next_end_numbers(thread_low_to_high=True)

                    client.command_next_end(
                        expected_end_number0=expected_end_number0,
                        expected_end_number1=expected_end_number1,
                        expected_repeat_number=expected_repeat_number,
                    )

                # Change to high-to-low
                client.change_direction()
                assert not client.loom_server.thread_low_to_high

                # Make enough advances to get to the beginning
                while True:
                    try:
                        (
                            expected_end_number0,
                            expected_end_number1,
                            expected_repeat_number,
                        ) = pattern.compute_next_end_numbers(thread_low_to_high=False)
                    except IndexError:
                        break

                    client.command_next_end(
                        expected_end_number0=expected_end_number0,
                        expected_end_number1=expected_end_number1,
                        expected_repeat_number=expected_repeat_number,
                    )
                assert expected_repeat_number == 1
                assert expected_end_number0 == 0

                # Another advance should be rejected,
                # without changing the end numbers in the pattern.
                client.send_command(dict(type="oobcommand", command="n"))
                reply = client.receive_dict()
                assert reply["message"] == "At start of threading"
                assert reply["severity"] == MessageSeverityEnum.ERROR
                assert pattern.end_number0 == expected_end_number0
                assert pattern.end_number1 == expected_end_number1
                assert pattern.end_repeat_number == expected_repeat_number

                # Toggle low_to_high by toggling end1_at_right
                client.command_settings(end1_on_right=not client.loom_server.settings.end1_on_right)
                assert client.loom_server.thread_low_to_high

                client.command_next_end(
                    expected_end_number0=1,
                    expected_end_number1=min(num_ends_in_pattern, thread_group_size),
                    expected_repeat_number=1,
                )

                # Toggle low_to_high by toggling thread_back_to_front
                client.command_settings(
                    thread_back_to_front=not client.loom_server.settings.thread_back_to_front,
                )
                assert not client.loom_server.thread_low_to_high

                client.command_next_end(
                    expected_end_number0=0,
                    expected_end_number1=0,
                    expected_repeat_number=1,
                )

                # Toggle low_to_high by toggling thread_right_to_left
                client.command_settings(
                    thread_right_to_left=not client.loom_server.settings.thread_right_to_left,
                )
                assert client.loom_server.thread_low_to_high

                client.command_next_end(
                    expected_end_number0=1,
                    expected_end_number1=min(num_ends_in_pattern, thread_group_size),
                    expected_repeat_number=1,
                )

    def test_next_pick(self) -> None:
        """Test advancing to the next pick."""
        pattern_name = ALL_PATTERN_PATHS[2].name

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:3],
        ) as client:
            pattern = client.select_pattern(pattern_name=pattern_name)

            # Make enough forward picks to get into the 3rd repeat
            expected_pick_number = 0
            expected_repeat_number = 1
            assert client.loom_server.direction_forward
            while True:
                expected_pick_number, expected_repeat_number = pattern.compute_next_pick_numbers(
                    direction_forward=True
                )
                expected_shaft_word = pattern.get_pick(expected_pick_number).shaft_word
                client.command_next_pick(
                    expected_pick_number=expected_pick_number,
                    expected_repeat_number=expected_repeat_number,
                    expected_shaft_word=expected_shaft_word,
                )
                if expected_repeat_number == 3:  # noqa: PLR2004
                    break

            client.change_direction()
            assert not client.loom_server.direction_forward

            # Now go backwards to the beginning
            while True:
                try:
                    expected_pick_number, expected_repeat_number = pattern.compute_next_pick_numbers(
                        direction_forward=False
                    )
                except IndexError:
                    break
                expected_shaft_word = pattern.get_pick(expected_pick_number).shaft_word
                client.command_next_pick(
                    expected_pick_number=expected_pick_number,
                    expected_repeat_number=expected_repeat_number,
                    expected_shaft_word=expected_shaft_word,
                )
            assert expected_pick_number == 0
            assert expected_repeat_number == 1

            # Another advance should be rejected,
            # without changing the pick numbers in the pattern.
            client.send_command(dict(type="oobcommand", command="n"))
            reply = client.receive_dict()
            assert reply["message"] == "At start of weaving"
            assert reply["severity"] == MessageSeverityEnum.ERROR
            assert pattern.pick_number == expected_pick_number
            assert pattern.pick_repeat_number == expected_repeat_number

            # Change direction to forward
            client.change_direction()
            assert client.loom_server.direction_forward

    def test_pattern_persistence(self) -> None:
        """Test pattern persistence, including current location.

        Check that the location is saved when it changes.
        """
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
                # pick and some random end_number0, including actually
                # going to that pick or end.
                assert len(ALL_PATTERN_PATHS) > 3  # noqa: PLR2004
                for path in (ALL_PATTERN_PATHS[0], ALL_PATTERN_PATHS[3]):
                    # If needed, go to weaving mode
                    if client.loom_server.mode != ModeEnum.WEAVE:
                        replies = client.send_command(dict(type="mode", mode=ModeEnum.WEAVE))
                        assert len(replies) == 2  # noqa: PLR2004
                        assert replies[0] == dict(type="Mode", mode=ModeEnum.WEAVE)

                    pattern = client.select_pattern(pattern_name=path.name)
                    num_ends_in_pattern = len(pattern.threading)
                    num_picks_in_pattern = len(pattern.picks)

                    pattern_list.append(pattern)
                    pick_number = rnd.randrange(0, num_picks_in_pattern)
                    pick_repeat_number = rnd.randrange(1, 10)
                    thread_group_size = rnd.randrange(1, 10)

                    end_number0 = rnd.randrange(0, num_ends_in_pattern)
                    end_number1 = (
                        0
                        if end_number0 == 0
                        else min(end_number0 + thread_group_size - 1, num_ends_in_pattern)
                    )
                    end_repeat_number = rnd.randrange(1, 10)

                    separate_threading_repeats = rnd.choice((True, False))
                    separate_weaving_repeats = rnd.choice((True, False))

                    if pattern.separate_threading_repeats != separate_threading_repeats:
                        replies = client.send_command(
                            dict(
                                type="separate_threading_repeats",
                                separate=separate_threading_repeats,
                            )
                        )
                        assert len(replies) == 2  # noqa: PLR2004
                        assert replies[0] == dict(
                            type="SeparateThreadingRepeats",
                            separate=separate_threading_repeats,
                        )

                    if pattern.separate_weaving_repeats != separate_weaving_repeats:
                        replies = client.send_command(
                            dict(
                                type="separate_weaving_repeats",
                                separate=separate_weaving_repeats,
                            ),
                        )
                        assert len(replies) == 2  # noqa: PLR2004
                        assert replies[0] == dict(
                            type="SeparateWeavingRepeats",
                            separate=separate_weaving_repeats,
                        )

                    total_pick_number = compute_total_num(
                        num_within=pick_number,
                        repeat_number=pick_repeat_number,
                        repeat_len=num_picks_in_pattern,
                    )
                    replies = client.send_command(
                        dict(type="jump_to_pick", total_pick_number=total_pick_number),
                    )
                    assert len(replies) == 2  # noqa: PLR2004
                    if total_pick_number == 0:
                        assert total_pick_number == 0
                        assert pick_number == 0
                        assert pick_repeat_number == 1
                    elif pick_number == 0 and total_pick_number != 0:
                        # Special case: report the last pick of the previous
                        # repeat, rather than the magic "0" pick_number
                        pick_number = num_picks_in_pattern
                        pick_repeat_number -= 1
                    assert replies[0] == dict(
                        type="JumpPickNumber",
                        total_pick_number=total_pick_number,
                        pick_number=pick_number,
                        pick_repeat_number=pick_repeat_number,
                    )
                    expected_shaft_word = pattern.get_pick(pick_number).shaft_word
                    client.command_next_pick(
                        jump_pending=True,
                        expected_pick_number=pick_number,
                        expected_repeat_number=pick_repeat_number,
                        expected_shaft_word=expected_shaft_word,
                    )

                    # Now advance to the desired end.
                    # First set mode to threading and set thread group size,
                    # Then jump to the pick and advance.
                    replies = client.send_command(dict(type="mode", mode=ModeEnum.THREAD))
                    assert len(replies) == 2  # noqa: PLR2004
                    assert replies[0] == dict(type="Mode", mode=ModeEnum.THREAD)

                    replies = client.send_command(
                        dict(
                            type="thread_group_size",
                            group_size=thread_group_size,
                        ),
                    )
                    assert len(replies) == 2  # noqa: PLR2004
                    assert replies[0] == dict(
                        type="ThreadGroupSize",
                        group_size=thread_group_size,
                    )

                    total_end_number0 = compute_total_num(
                        num_within=end_number0,
                        repeat_number=end_repeat_number,
                        repeat_len=num_ends_in_pattern,
                    )
                    total_end_number1 = compute_total_num(
                        num_within=end_number1,
                        repeat_number=end_repeat_number,
                        repeat_len=num_ends_in_pattern,
                    )
                    replies = client.send_command(
                        dict(type="jump_to_end", total_end_number0=total_end_number0),
                    )
                    if total_end_number0 == 0:
                        assert total_end_number1 == 0
                        assert end_number0 == 0
                        assert end_number1 == 0
                        assert end_repeat_number == 1
                    elif end_number0 == 0 and total_end_number0 != 0:
                        # Special case: report the last end of the previous
                        # repeat, rather than the magic "0" end_number0
                        end_repeat_number -= 1
                        end_number0 = num_ends_in_pattern
                        end_number1 = num_ends_in_pattern
                    assert replies[0] == dict(
                        type="JumpEndNumber",
                        total_end_number0=total_end_number0,
                        total_end_number1=total_end_number1,
                        end_number0=end_number0,
                        end_number1=end_number1,
                        end_repeat_number=end_repeat_number,
                    )

                    client.command_next_end(
                        jump_pending=True,
                        expected_end_number0=end_number0,
                        expected_end_number1=end_number1,
                        expected_repeat_number=end_repeat_number,
                    )

                    assert pattern.pick_number == pick_number
                    assert pattern.pick_repeat_number == pick_repeat_number
                    assert pattern.end_number0 == end_number0
                    assert pattern.end_number1 == end_number1
                    assert pattern.end_repeat_number == end_repeat_number
                    assert pattern.separate_threading_repeats == separate_threading_repeats
                    assert pattern.separate_weaving_repeats == separate_weaving_repeats

            # This expects that first pattern 0 and then pattern 3
            # was selected from ALL_PATTERN_PATHS:
            all_pattern_names = [path.name for path in ALL_PATTERN_PATHS]
            expected_pattern_names = (
                all_pattern_names[1:3] + all_pattern_names[4:] + [all_pattern_names[0], all_pattern_names[3]]
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
                    returned_pattern = client.select_pattern(
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
        """Test the select_pattern command."""
        # Read a pattern file in and convert the data to a ReducedPattern
        pattern_path = ALL_PATTERN_PATHS[1]
        pattern_data = read_pattern_file(pattern_path)
        reduced_pattern = reduced_pattern_from_pattern_data(name=pattern_path.name, data=pattern_data)

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:3],
        ) as client:
            selected_pattern = client.select_pattern(pattern_name=pattern_path.name)
            assert selected_pattern == reduced_pattern

    def test_settings_command(self) -> None:
        """Test the settings command."""
        with self.create_test_client(app=self.app) as client:
            initial_settings = copy.copy(client.loom_server.settings)
            if client.loom_server.supports_full_direction_control:
                assert initial_settings.direction_control is DirectionControlEnum.FULL
            else:
                assert initial_settings.direction_control is not DirectionControlEnum.FULL
            for direction_control, should_fail in {
                DirectionControlEnum.FULL: (
                    (DirectionControlEnum.LOOM, True),
                    (DirectionControlEnum.SOFTWARE, True),
                    (DirectionControlEnum.FULL, False),
                ),
                DirectionControlEnum.SOFTWARE: (
                    (DirectionControlEnum.LOOM, False),
                    (DirectionControlEnum.SOFTWARE, False),
                    (DirectionControlEnum.FULL, True),
                ),
                DirectionControlEnum.LOOM: (
                    (DirectionControlEnum.SOFTWARE, False),
                    (DirectionControlEnum.LOOM, False),
                    (DirectionControlEnum.FULL, True),
                ),
            }[initial_settings.direction_control]:
                client.command_settings(direction_control=direction_control, should_fail=should_fail)

            for loom_name in ("", "?", "Séguin Loom"):
                client.command_settings(loom_name=loom_name)

            for end1_on_right in (
                not initial_settings.end1_on_right,
                initial_settings.end1_on_right,
            ):
                client.command_settings(end1_on_right=end1_on_right)
            for bad_bool in ("hello", 0, 1):
                client.command_settings(
                    end1_on_right=bad_bool,
                    should_fail=True,
                )

            for thread_group_size in (1, 2, MAX_THREAD_GROUP_SIZE):
                client.command_settings(thread_group_size=thread_group_size)
            for bad_thread_group_size in (-1, 0, MAX_THREAD_GROUP_SIZE + 1):
                client.command_settings(thread_group_size=bad_thread_group_size, should_fail=True)

            for thread_back_to_front in (
                not initial_settings.thread_back_to_front,
                initial_settings.thread_back_to_front,
            ):
                client.command_settings(thread_back_to_front=thread_back_to_front)
            for bad_bool in ("hello", 0, 1):
                client.command_settings(
                    thread_back_to_front=bad_bool,
                    should_fail=True,
                )

            for thread_right_to_left in (
                not initial_settings.thread_right_to_left,
                initial_settings.thread_right_to_left,
            ):
                client.command_settings(thread_right_to_left=thread_right_to_left)
            for bad_bool in ("hello", 0, 1):
                client.command_settings(
                    thread_right_to_left=bad_bool,
                    should_fail=True,
                )

    def test_read_settings_file(self) -> None:
        """Test reading the settings file."""
        with self.create_test_client(app=self.app) as client:
            default_settings = copy.copy(client.loom_server.settings)
            supports_full_direction_control = client.loom_server.supports_full_direction_control

        # Test settings files with no  usable data.
        # The resulting settings should match the default.
        for unusable_settings_json in ("", "?", "} not json", "{'not_a_key': true}"):
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = pathlib.Path(temp_dir) / "loom_server_database.sqlite"
                settings_path = pathlib.Path(temp_dir) / SETTINGS_FILE_NAME

                with settings_path.open("w", encoding="utf_8") as f:
                    f.write(unusable_settings_json)

                with self.create_test_client(
                    app=self.app,
                    db_path=db_path,
                ) as client:
                    assert client.loom_server.settings_path == settings_path
                    assert client.loom_server.settings == default_settings
                    if supports_full_direction_control:
                        assert client.loom_server.settings.direction_control is DirectionControlEnum.FULL
                    else:
                        assert client.loom_server.settings.direction_control is not DirectionControlEnum.FULL

        # Test some valid settings files.
        if supports_full_direction_control:
            good_direction_control = DirectionControlEnum.FULL
        else:
            good_direction_control = (
                DirectionControlEnum.LOOM
                if default_settings.direction_control is DirectionControlEnum.SOFTWARE
                else DirectionControlEnum.SOFTWARE
            )
        for good_settings_dict in (
            dict(
                loom_name="a name",
                direction_control=good_direction_control,
                end1_on_right=False,
                thread_group_size=1,
                thread_back_to_front=False,
                thread_right_to_left=True,
                extra_key=14,
            ),
            dict(
                loom_name="",
                direction_control=good_direction_control,
                end1_on_right=True,
                thread_group_size=MAX_THREAD_GROUP_SIZE,
                thread_back_to_front=True,
                thread_right_to_left=False,
                different_extra_key="hello",
            ),
        ):
            with tempfile.TemporaryDirectory() as temp_dir:
                db_path = pathlib.Path(temp_dir) / "loom_server_database.sqlite"
                settings_path = pathlib.Path(temp_dir) / SETTINGS_FILE_NAME

                with settings_path.open("w", encoding="utf_8") as f:
                    json.dump(good_settings_dict, f)

                with self.create_test_client(
                    app=self.app,
                    db_path=db_path,
                ) as client:
                    for key, value in good_settings_dict.items():
                        if "extra" in key:
                            assert not hasattr(client.loom_server.settings, key)
                        else:
                            assert getattr(client.loom_server.settings, key) == value

    def test_upload(self) -> None:
        """Test the upload command."""
        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS,
        ) as _:
            pass

        # Test uploading a pattern file with too many shafts
        filename = "eighteen shaft liftplan.wif"
        filepath = TEST_DATA_FILES / filename
        with self.create_test_client(
            app=self.app,
            num_shafts=16,
        ) as client:
            client.upload_pattern(filepath=filepath, expected_names=[""], should_fail=True)

    def test_weave_direction(self) -> None:
        """Test changing the weave direction."""
        pattern_name = ALL_PATTERN_PATHS[1].name

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:4],
        ) as client:
            if not client.loom_server.enable_software_direction:
                raise pytest.skip("Weave direction cannot be controlled by software")

            client.select_pattern(pattern_name=pattern_name)

            for forward in (False, True):
                replies = client.send_command(dict(type="direction", forward=forward))
                assert len(replies) == 2  # noqa: PLR2004
                assert replies[0]["type"] == "Direction"
                assert replies[0]["forward"] == forward

    @classmethod
    @contextlib.contextmanager
    def create_test_client(
        cls,
        *,
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
                "app is None but must be a FastAPI; you must set the app class property in your subclass"
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            if db_path is None:
                db_path = pathlib.Path(temp_dir) / "loom_server_database.sqlite"
            argv = ["testutils", str(num_shafts), "mock", "--verbose", *cls.extra_args]
            if reset_db:
                argv.append("--reset-db")
            argv += ["--db-path", str(db_path)]
            sys.argv = argv

            with (
                TestClient(app) as test_client,
                test_client.websocket_connect("/ws") as websocket,
            ):
                loom_server: BaseLoomServer = (
                    test_client.app.state.loom_server  # type: ignore[attr-defined]
                )
                assert loom_server.mock_loom is not None
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
                        "LanguageNames",
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
                                assert reply.end_number0 == expected_current_pattern.end_number0
                                assert reply.end_number1 == expected_current_pattern.end_number1
                                assert reply.end_repeat_number == expected_current_pattern.end_repeat_number
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
                                assert reply.pick_number == expected_current_pattern.pick_number
                                assert reply.pick_repeat_number == expected_current_pattern.pick_repeat_number
                                assert reply.total_pick_number == compute_total_num(
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
                            case "LanguageNames":
                                assert "English" in reply.languages
                            case "LoomConnectionState":
                                if reply.state not in good_connection_states:
                                    raise AssertionError(
                                        f"Unexpected state in {reply=}; should be in {good_connection_states}"
                                    )
                                elif reply.state != ConnectionStateEnum.CONNECTED:
                                    continue
                            case "LoomInfo":
                                assert vars(reply) == dataclasses.asdict(loom_server.loom_info)
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
                                assert reply.separate == expected_current_pattern.separate_threading_repeats
                            case "SeparateWeavingRepeats":
                                assert expected_current_pattern is not None
                                assert reply.separate == expected_current_pattern.separate_weaving_repeats
                            case "Settings":
                                assert vars(reply) == dataclasses.asdict(loom_server.settings)
                            case "ShaftState":
                                assert reply.state == ShaftStateEnum.DONE
                                assert reply.shaft_word == 0
                            case "StatusMessage":
                                num_status_messages_seen += 1
                                assert reply.message == expected_status_messages[num_status_messages_seen - 1]
                                assert reply.severity == MessageSeverityEnum.INFO
                            case "ThreadGroupSize":
                                assert expected_current_pattern is not None
                                assert reply.group_size == expected_current_pattern.thread_group_size
                            case "Direction":
                                assert reply.forward
                            case _:
                                raise AssertionError(f"Unexpected message type {reply.type}")
                        seen_types.add(reply.type)
                        if seen_types == expected_types and num_status_messages_seen == len(
                            expected_status_messages
                        ):
                            break

                expected_names: list[str] = []
                for filepath in upload_patterns:
                    expected_names.append(filepath.name)
                    client.upload_pattern(
                        filepath=filepath,
                        expected_names=expected_names,
                    )

                yield client
