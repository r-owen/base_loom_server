import contextlib
import dataclasses
import importlib.resources
import io
import pathlib
import random
import sys
import tempfile
from collections.abc import Generator, Iterable
from types import SimpleNamespace
from typing import Any, TypeAlias

import pytest
from dtx_to_wif import read_dtx, read_wif
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from starlette.testclient import WebSocketTestSession

from .base_loom_server import DEFAULT_THREAD_GROUP_SIZE, BaseLoomServer
from .base_mock_loom import BaseMockLoom
from .client_replies import (
    ConnectionStateEnum,
    MessageSeverityEnum,
    ModeEnum,
    ShaftStateEnum,
)
from .reduced_pattern import ReducedPattern, reduced_pattern_from_pattern_data

WebSocketType: TypeAlias = WebSocket | WebSocketTestSession

_PKG_NAME = "base_loom_server"
TEST_DATA_FILES = importlib.resources.files(_PKG_NAME).joinpath("test_data")

# in Python 3.11 mypy complains: "Traversable" has no attribute "glob"
ALL_PATTERN_PATHS = list(TEST_DATA_FILES.glob("*.wif")) + list(  # type: ignore
    TEST_DATA_FILES.glob("*.dtx")  # type: ignore
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


def change_weave_direction(client: Client):
    """Command the loom to weave in the specified direction,
    and read and check the reply, if one is expected.

    Use a software command, if the loom supports that,
    else an oob command.

    Parameters
    ----------
    client: Client
        Client fixture
    """
    expected_weave_direction_reply = True
    client.mock_loom.command_threading_event.set()
    if client.loom_server.enable_software_weave_direction:
        weave_forward = not client.loom_server.weave_forward
        client.send_dict(dict(type="weave_direction", forward=weave_forward))
    else:
        expected_weave_direction_reply = client.loom_server.loom_reports_direction
        weave_forward = not client.mock_loom.weave_forward
        client.send_dict(dict(type="oobcommand", command="d"))

    if expected_weave_direction_reply:
        reply = client.receive_dict()
        assert reply == dict(type="WeaveDirection", forward=weave_forward)
    else:
        # Give the loom client time to process the command
        client.mock_loom.command_threading_event.wait(timeout=1)


def command_next_pick(
    client: Client,
    expected_pick_number: int,
    expected_repeat_number: int,
    expected_shaft_word: int,
    jump_pending: bool = False,
) -> None:
    """Command the next pick and test the replies.

    Ignore info-level StatusMessage

    Parameters
    ----------
    client : Client
        client fixture
    expected_pick_number : int
        Expected pick number of the next pick
    expected_repeat_number : int
        Expected repeat number of the next pick
    expected_shaft_word : int
        Expected shaft_word of the pick.
    jump_pending : bool
        Is a jump pending?
    """
    client.send_dict(dict(type="oobcommand", command="n"))
    expected_replies: list[dict[str, Any]] = []
    if (
        not client.loom_server.enable_software_weave_direction
        and not client.loom_server.loom_reports_direction
        and client.loom_server.weave_forward != client.mock_loom.weave_forward
    ):
        # Loom only reports direction when it asks for a pick
        # and the direction has changed
        expected_replies += [
            dict(
                type="WeaveDirection",
                forward=client.mock_loom.weave_forward,
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
        for key, value in expected_reply.items():
            if value is not None:
                assert reply.get(key) == value


def select_pattern(
    client: Client,
    pattern_name: str,
    pick_number: int = 0,
    pick_repeat_number: int = 1,
) -> ReducedPattern:
    """Tell the loom server to select a pattern.

    Read and check the expected replies and return the pattern.

    Parameters
    ----------
    client : Client
        Client test fixture
    pattern_name : str
        Pattern name.
    pick_number : int
        Expected current pick number.
    pick_repeat_number : int
        Expected current repeat number.
    """
    client.send_dict(dict(type="select_pattern", name=pattern_name))
    reply_dict = client.receive_dict()
    assert reply_dict["type"] == "ReducedPattern"
    pattern = ReducedPattern.from_dict(reply_dict)
    assert pattern.pick_number == pick_number
    assert pattern.pick_repeat_number == pick_repeat_number
    seen_types: set[str] = set()
    expected_types = {"CurrentPickNumber", "CurrentEndNumber"}
    while True:
        reply_dict = client.receive_dict()
        reply = SimpleNamespace(**reply_dict)
        match reply.type:
            case "CurrentPickNumber":
                assert reply.pick_number == pick_number
                assert reply.pick_repeat_number == pick_repeat_number
            case "CurrentEndNumber":
                assert reply.end_number0 == pattern.end_number0
                assert reply.end_repeat_number == pattern.end_repeat_number
            case _:
                raise AssertionError(f"Unexpected message type {reply.type}")
        seen_types.add(reply.type)
        if seen_types == expected_types:
            break
    return pattern


def upload_pattern(
    client: Client, filepath: pathlib.Path, expected_names: Iterable[str]
) -> None:
    """Upload a pattern to the loom server.

    Check expected replies.

    Parameters
    ----------
    client: Client
        Test client
    filepath : pathlib.Path
        Path to pattern file
    expected_names : Iterable[str]
        Expected pattern names.
    """
    with open(filepath, "r") as f:
        data = f.read()
    client.send_dict(dict(type="file", name=filepath.name, data=data))
    reply_dict = client.receive_dict()
    assert reply_dict == dict(type="PatternNames", names=list(expected_names))


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

    def test_jump_to_pick(self) -> None:
        pattern_name = ALL_PATTERN_PATHS[3].name

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[2:5],
        ) as client:
            pattern = select_pattern(client=client, pattern_name=pattern_name)
            num_picks_in_pattern = len(pattern.picks)

            for pick_number in (0, 1, num_picks_in_pattern // 3, num_picks_in_pattern):
                for pick_repeat_number in (-1, 0, 1):
                    client.send_dict(
                        dict(
                            type="jump_to_pick",
                            pick_number=pick_number,
                            pick_repeat_number=pick_repeat_number,
                        )
                    )
                    reply = client.receive_dict()
                    assert reply == dict(
                        type="JumpPickNumber",
                        pick_number=pick_number,
                        pick_repeat_number=pick_repeat_number,
                    )

    def test_oobcommand(self) -> None:
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
                    expected_pick_number -= num_picks_in_pattern + 1
                    expected_repeat_number += 1
                expected_shaft_word = pattern.get_pick(expected_pick_number).shaft_word
                command_next_pick(
                    client=client,
                    expected_pick_number=expected_pick_number,
                    expected_repeat_number=expected_repeat_number,
                    expected_shaft_word=expected_shaft_word,
                )

            change_weave_direction(client=client)

            # Now go backwards at least two picks past the beginning
            end_pick_number = num_picks_in_pattern - 2
            while not (
                expected_pick_number == end_pick_number and expected_repeat_number == 0
            ):
                expected_pick_number -= 1
                if expected_pick_number < 0:
                    expected_pick_number += num_picks_in_pattern + 1
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
            change_weave_direction(client)
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
        with tempfile.NamedTemporaryFile() as f:
            with self.create_test_client(
                app=self.app,
                upload_patterns=ALL_PATTERN_PATHS,
                db_path=f.name,
            ) as client:
                # Select a few patterns; for each one jump to some random
                # pick (including actually going to that pick).
                assert len(ALL_PATTERN_PATHS) > 3
                for path in (ALL_PATTERN_PATHS[0], ALL_PATTERN_PATHS[3]):
                    pattern = select_pattern(client=client, pattern_name=path.name)
                    pattern_list.append(pattern)
                    pattern.pick_number = rnd.randrange(2, len(pattern.picks))
                    pattern.pick_repeat_number = rnd.randrange(-10, 10)
                    client.send_dict(
                        dict(
                            type="jump_to_pick",
                            pick_number=pattern.pick_number,
                            pick_repeat_number=pattern.pick_repeat_number,
                        )
                    )
                    reply = client.receive_dict()
                    assert reply == dict(
                        type="JumpPickNumber",
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
                db_path=f.name,
            ) as client:
                for pattern in pattern_list:
                    pattern = select_pattern(
                        client=client,
                        pattern_name=pattern.name,
                        pick_number=pattern.pick_number,
                        pick_repeat_number=pattern.pick_repeat_number,
                    )

            # Now try again, but this time reset the database
            with self.create_test_client(
                app=self.app,
                reset_db=True,
            ) as client:
                pass

    def test_select_pattern(self) -> None:
        # Read a pattern file in and convert the data to a ReducedPattern
        pattern_path = ALL_PATTERN_PATHS[1]
        pattern_name = ALL_PATTERN_PATHS[1].name
        with open(pattern_path, "r") as f:
            raw_pattern_data = f.read()
        if pattern_name.endswith(".dtx"):
            with io.StringIO(raw_pattern_data) as dtx_file:
                pattern_data = read_dtx(dtx_file)
        elif pattern_name.endswith(".wif"):
            with io.StringIO(raw_pattern_data) as wif_file:
                pattern_data = read_wif(wif_file)
        else:
            raise AssertionError("Unexpected unsupported file type: {pattern_path!s}")
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=pattern_name, data=pattern_data
        )

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:3],
        ) as client:
            returned_pattern = select_pattern(client=client, pattern_name=pattern_name)
            assert returned_pattern == reduced_pattern

    def test_upload(self) -> None:
        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS,
        ) as _:
            pass

    def test_weave_direction(self) -> None:
        pattern_name = ALL_PATTERN_PATHS[1].name

        with self.create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:4],
        ) as client:
            if not client.loom_server.enable_software_weave_direction:
                raise pytest.skip("Weave direction cannot be controlled by software")

            select_pattern(client=client, pattern_name=pattern_name)

            for forward in (False, True):
                client.send_dict(dict(type="weave_direction", forward=forward))
                reply = client.receive_dict()
                assert reply == dict(type="WeaveDirection", forward=forward)

    @classmethod
    @contextlib.contextmanager
    def create_test_client(
        cls,
        app: FastAPI | None,
        read_initial_state: bool = True,
        upload_patterns: Iterable[pathlib.Path] = (),
        reset_db: bool = False,
        db_path: pathlib.Path | str | None = None,
        expected_status_messages: Iterable[str] = (),
        expected_pattern_names: Iterable[str] = (),
        expected_current_pattern: ReducedPattern | None = None,
    ) -> Generator[Client, None]:
        """Create a test client fixture.

        Parameters
        ----------
        app : FastAPI
            Server application to test.
            If None then raises an error (BaseTestLoomServer needs
            this be be able to be None).
        read_initial_state : bool
            If true, read and check the initial server replies
            from the websocket. This is the most common case.
        upload_patterns : Iterable[pathlib.Path]
            Initial patterns to upload, if any.
        reset_db : bool
            Specify argument --reset-db?
            If False then you should also specify expected_pattern_names
        db_path : pathLib.Path | str | None
            --db-path argument value. If None, use a temp file.
            If not None and you expect the database to contain any patterns,
            then also specify expected_pattern_names and
            expected_current_pattern.
        expected_status_messages : Iterable[str]
            Expected status messages when the connection is made, in order.
            All should have severity level INFO.
        expected_pattern_names : Iterable[str]
            Expected pattern names, in order.
            Specify if and only if db_path is not None
            and you expect the database to contain any patterns.
        expected_current_pattern : ReducedPattern | None
            Expected_current_pattern. Specify if and only if
            db_path is not None and you expect the database
            to contain any patterns.
        """
        expected_pattern_names = list(expected_pattern_names)
        expected_status_messages = list(expected_status_messages)
        if app is None:
            raise AssertionError(
                "app is None but must be a FastAPI; "
                "you must set the app class property in your subclass"
            )
        with tempfile.NamedTemporaryFile() as f:
            argv = ["testutils", "mock", "--verbose"] + list(cls.extra_args)
            if reset_db:
                argv.append("--reset-db")
            if db_path is None:
                argv += ["--db-path", f.name]
            else:
                argv += ["--db-path", str(db_path)]
            sys.argv = argv

            with TestClient(app) as test_client:
                with test_client.websocket_connect("/ws") as websocket:
                    loom_server: BaseLoomServer = test_client.app.state.loom_server  # type: ignore
                    assert loom_server.mock_loom is not None
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
                            "Mode",
                            "PatternNames",
                            "ShaftState",
                            "ThreadDirection",
                            "ThreadGroupSize",
                            "WeaveDirection",
                        }
                        if expected_status_messages:
                            expected_types |= {"StatusMessage"}
                        if expected_current_pattern:
                            expected_types |= {
                                "ReducedPattern",
                                "CurrentPickNumber",
                                "CurrentEndNumber",
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
                                        reply.end_repeat_number
                                        == expected_current_pattern.end_repeat_number
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
                                case "JumpEndNumber":
                                    assert reply.end_number0 is None
                                    assert reply.end_repeat_number is None
                                case "JumpPickNumber":
                                    assert reply.pick_number is None
                                    assert reply.pick_repeat_number is None
                                case "LoomConnectionState":
                                    if reply.state not in good_connection_states:
                                        raise AssertionError(
                                            f"Unexpected state in {reply=}; "
                                            f"should be in {good_connection_states}"
                                        )
                                    elif reply.state != ConnectionStateEnum.CONNECTED:
                                        continue
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
                                case "ThreadDirection":
                                    assert reply.low_to_high
                                case "ThreadGroupSize":
                                    assert reply.group_size == DEFAULT_THREAD_GROUP_SIZE
                                case "WeaveDirection":
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
                    for path in upload_patterns:
                        expected_names.append(path.name)
                        upload_pattern(client, path, expected_names)

                    yield client
