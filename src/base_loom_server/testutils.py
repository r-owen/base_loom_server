__all__ = ["create_test_client"]

import contextlib
import importlib.resources
import io
import pathlib
import random
import sys
import tempfile
from collections.abc import Generator, Iterable
from types import SimpleNamespace
from typing import Any, TypeAlias

from dtx_to_wif import read_dtx, read_wif
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
from starlette.testclient import WebSocketTestSession

from .client_replies import ConnectionStateEnum, MessageSeverityEnum, ShaftStateEnum
from .reduced_pattern import ReducedPattern, reduced_pattern_from_pattern_data

WebSocketType: TypeAlias = WebSocket | WebSocketTestSession

_PKG_NAME = "base_loom_server"
TEST_DATA_FILES = importlib.resources.files(_PKG_NAME).joinpath("test_data")

# in Python 3.11 mypy complains: "Traversable" has no attribute "glob"
ALL_PATTERN_PATHS = list(TEST_DATA_FILES.glob("*.wif")) + list(  # type: ignore
    TEST_DATA_FILES.glob("*.dtx")  # type: ignore
)


def receive_dict(websocket: WebSocketType) -> dict[str, Any]:
    """Wrapper around websocket.receive_json to make mypy happy"""
    data: Any = websocket.receive_json()
    assert isinstance(data, dict)
    return data


@contextlib.contextmanager
def create_test_client(
    app: FastAPI | None,
    read_initial_state: bool = True,
    upload_patterns: Iterable[pathlib.Path] = (),
    reset_db: bool = False,
    db_path: pathlib.Path | str | None = None,
    expected_status_messages: Iterable[str] = (),
    expected_pattern_names: Iterable[str] = (),
    expected_current_pattern: ReducedPattern | None = None,
) -> Generator[tuple[TestClient, WebSocketType], None]:
    """Create a test server, client, websocket. Return (client, websocket).

    Parameters
    ----------
    app : FastAPI
        Server application to test.
        If None then raises an error (BaseTestLoomServer needs
        this be be able to be None).
    read_initial_state : bool
        If true, read and check the initial server replies from the websocket
    upload_patterns : Iterable[pathlib.Path]
        Initial patterns to upload, if any.
    reset_db : bool
        Specify argument --reset-db?
        If False then you should also specify expected_pattern_names
    db_path : pathLib.Path | str | None
        --db-path argument value. If None, use a temp file.
        If non-None and you expect the database to contain any patterns,
        then also specify expected_pattern_names and expected_current_pattern.
    expected_status_messages : Iterable[str]
        Expected status messages when the connection is made, in order.
        All should have severity level INFO.
    expected_pattern_names : Iterable[str]
        Expected pattern names, in order.
        Specify if and only if db_path is not None
        and you expect the database to contain any patterns.
    expected_current_pattern : ReducedPattern | None
        Expected_current_pattern. Specify if and only if db_path is not None
        and you expect the database to contain any patterns.
    """
    expected_pattern_names = list(expected_pattern_names)
    expected_status_messages = list(expected_status_messages)
    if app is None:
        raise AssertionError(
            "app is None but must be a FastAPI; "
            "you must set the app class property in your subclass"
        )
    with tempfile.NamedTemporaryFile() as f:
        argv = ["testutils", "mock", "--verbose"]
        if reset_db:
            argv.append("--reset-db")
        if db_path is None:
            argv += ["--db-path", f.name]
        else:
            argv += ["--db-path", str(db_path)]
        sys.argv = argv

        with TestClient(app) as client:
            with client.websocket_connect("/ws") as websocket:

                if read_initial_state:
                    seen_types: set[str] = set()
                    expected_types = {
                        "JumpPickNumber",
                        "LoomConnectionState",
                        "PatternNames",
                        "ShaftState",
                        "WeaveDirection",
                    }
                    if expected_status_messages:
                        expected_types |= {"StatusMessage"}
                    if expected_current_pattern:
                        expected_types |= {"ReducedPattern", "CurrentPickNumber"}
                    good_connection_states = {
                        ConnectionStateEnum.CONNECTING,
                        ConnectionStateEnum.CONNECTED,
                    }
                    while True:
                        reply_dict = receive_dict(websocket)
                        reply = SimpleNamespace(**reply_dict)
                        num_status_messages_seen = 0
                        match reply.type:
                            case "CurrentPickNumber":
                                assert expected_current_pattern is not None
                                assert (
                                    reply.pick_number
                                    == expected_current_pattern.pick_number
                                )
                                assert (
                                    reply.repeat_number
                                    == expected_current_pattern.repeat_number
                                )
                            case "JumpPickNumber":
                                assert reply.pick_number is None
                                assert reply.repeat_number is None
                            case "LoomConnectionState":
                                if reply.state not in good_connection_states:
                                    raise AssertionError(
                                        f"Unexpected state in {reply=}; "
                                        f"should be in {good_connection_states}"
                                    )
                                elif reply.state != ConnectionStateEnum.CONNECTED:
                                    continue
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
                    upload_pattern(websocket, path, expected_names)

                yield (client, websocket)


def command_next_pick(
    websocket: WebSocketType,
    expected_pick_number: int,
    expected_repeat_number: int,
    expected_shaft_word: int,
    jump_pending: bool = False,
    motion_reported: bool = True,
) -> None:
    """Command the next pick and test the replies.

    Ignore info-level StatusMessage

    Parameters
    ----------
    websocket : WebSocketType
        websocket connection
    expected_pick_number : int
        Expected pick number of the next pick
    expected_repeat_number : int
        Expected repeat number of the next pick
    expected_shaft_word : int
        Expected shaft_word of the pick.
    jump_pending : bool
        Is a jump pending?
    motion_reported : bool
        Does the server output ShaftState messages with state MOVING?
    """
    websocket.send_json(dict(type="oobcommand", command="n"))
    expected_replies: list[dict[str, Any]] = []
    if jump_pending:
        expected_replies += [
            dict(
                type="JumpPickNumber",
                pick_number=None,
                repeat_number=None,
            ),
        ]
    expected_replies += [
        dict(
            type="CurrentPickNumber",
            pick_number=expected_pick_number,
            repeat_number=expected_repeat_number,
        ),
    ]
    if motion_reported:
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
        reply = receive_dict(websocket)
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
    websocket: WebSocketType,
    pattern_name: str,
    pick_number: int = 0,
    repeat_number: int = 1,
) -> ReducedPattern:
    """Tell the loom server to select a pattern.

    Read and check the expected replies and return the pattern.

    Parameters
    ----------
    websocket : WebSocketType
        Websocket connection to loom server.
    pattern_name : str
        Pattern name.
    pick_number : int
        Expected current pick number.
    repeat_number : int
        Expected current repeat number.
    """
    websocket.send_json(dict(type="select_pattern", name=pattern_name))
    reply = receive_dict(websocket)
    assert reply["type"] == "ReducedPattern"
    pattern = ReducedPattern.from_dict(reply)
    assert pattern.pick_number == pick_number
    assert pattern.repeat_number == repeat_number
    reply = receive_dict(websocket)
    assert reply == dict(
        type="CurrentPickNumber", pick_number=pick_number, repeat_number=repeat_number
    )
    return pattern


def upload_pattern(
    websocket: WebSocketType, filepath: pathlib.Path, expected_names: Iterable[str]
) -> None:
    """Upload a pattern to the loom server.

    Check expected replies.

    Parameters
    ----------
    websocket : WebSocketType
        Websocket connection to loom server.
    filepath : pathlib.Path
        Path to pattern file
    expected_names : Iterable[str]
        Expected pattern names.
    """
    with open(filepath, "r") as f:
        data = f.read()
    cmd = dict(type="file", name=filepath.name, data=data)
    websocket.send_json(cmd)
    reply_dict = receive_dict(websocket)
    assert reply_dict == dict(type="PatternNames", names=list(expected_names))


class BaseTestLoomServer:
    """Base class for server tests.

    Subclasses must:
    * Set class property `app` to the FastAPI app for your loom server.
    * Have a name beginning with Test
    * Not have an `__init__` method
    """

    expected_status_messages = ()
    motion_reported = True
    app: FastAPI | None = None

    def test_jump_to_pick(self) -> None:
        pattern_name = ALL_PATTERN_PATHS[3].name

        with create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[2:5],
            expected_status_messages=self.expected_status_messages,
        ) as (
            client,
            websocket,
        ):
            pattern = select_pattern(websocket=websocket, pattern_name=pattern_name)
            num_picks_in_pattern = len(pattern.picks)

            for pick_number in (0, 1, num_picks_in_pattern // 3, num_picks_in_pattern):
                for repeat_number in (-1, 0, 1):
                    websocket.send_json(
                        dict(
                            type="jump_to_pick",
                            pick_number=pick_number,
                            repeat_number=repeat_number,
                        )
                    )
                    reply = receive_dict(websocket)
                    assert reply == dict(
                        type="JumpPickNumber",
                        pick_number=pick_number,
                        repeat_number=repeat_number,
                    )

    def test_oobcommand(self) -> None:
        pattern_name = ALL_PATTERN_PATHS[2].name

        with create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:3],
            expected_status_messages=self.expected_status_messages,
        ) as (
            client,
            websocket,
        ):
            pattern = select_pattern(websocket=websocket, pattern_name=pattern_name)
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
                    websocket=websocket,
                    motion_reported=self.motion_reported,
                    expected_pick_number=expected_pick_number,
                    expected_repeat_number=expected_repeat_number,
                    expected_shaft_word=expected_shaft_word,
                )

            websocket.send_json(dict(type="weave_direction", forward=False))
            reply = receive_dict(websocket)
            assert reply == dict(type="WeaveDirection", forward=False)

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
                    websocket=websocket,
                    motion_reported=self.motion_reported,
                    expected_pick_number=expected_pick_number,
                    expected_repeat_number=expected_repeat_number,
                    expected_shaft_word=expected_shaft_word,
                )
            assert expected_pick_number == end_pick_number
            assert expected_repeat_number == 0

            # Change direction to forward
            websocket.send_json(dict(type="weave_direction", forward=True))
            expected_pick_number += 1
            reply = receive_dict(websocket)
            assert reply == dict(type="WeaveDirection", forward=True)

            expected_shaft_word = pattern.get_pick(expected_pick_number).shaft_word
            command_next_pick(
                websocket=websocket,
                motion_reported=self.motion_reported,
                expected_pick_number=expected_pick_number,
                expected_repeat_number=expected_repeat_number,
                expected_shaft_word=expected_shaft_word,
            )

    def test_pattern_persistence(self) -> None:
        rnd = random.Random(47)
        pattern_list = []
        with tempfile.NamedTemporaryFile() as f:
            with create_test_client(
                app=self.app,
                upload_patterns=ALL_PATTERN_PATHS,
                db_path=f.name,
                expected_status_messages=self.expected_status_messages,
            ) as (
                client,
                websocket,
            ):
                # Select a few patterns; for each one jump to some random
                # pick (including actually going to that pick).
                assert len(ALL_PATTERN_PATHS) > 3
                for path in (ALL_PATTERN_PATHS[0], ALL_PATTERN_PATHS[3]):
                    pattern = select_pattern(
                        websocket=websocket, pattern_name=path.name
                    )
                    pattern_list.append(pattern)
                    pattern.pick_number = rnd.randrange(2, len(pattern.picks))
                    pattern.repeat_number = rnd.randrange(-10, 10)
                    websocket.send_json(
                        dict(
                            type="jump_to_pick",
                            pick_number=pattern.pick_number,
                            repeat_number=pattern.repeat_number,
                        )
                    )
                    reply = receive_dict(websocket)
                    assert reply == dict(
                        type="JumpPickNumber",
                        pick_number=pattern.pick_number,
                        repeat_number=pattern.repeat_number,
                    )
                    expected_pick_number = pattern.pick_number
                    expected_shaft_word = pattern.get_pick(
                        expected_pick_number
                    ).shaft_word
                    command_next_pick(
                        websocket=websocket,
                        motion_reported=self.motion_reported,
                        jump_pending=True,
                        expected_pick_number=expected_pick_number,
                        expected_repeat_number=pattern.repeat_number,
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

            with create_test_client(
                app=self.app,
                reset_db=False,
                expected_pattern_names=expected_pattern_names,
                expected_current_pattern=expected_current_pattern,
                db_path=f.name,
                expected_status_messages=self.expected_status_messages,
            ) as (
                client,
                websocket,
            ):
                for pattern in pattern_list:
                    pattern = select_pattern(
                        websocket=websocket,
                        pattern_name=pattern.name,
                        pick_number=pattern.pick_number,
                        repeat_number=pattern.repeat_number,
                    )

            # Now try again, but this time reset the database
            with create_test_client(
                app=self.app,
                reset_db=True,
                expected_status_messages=self.expected_status_messages,
            ) as (
                client,
                websocket,
            ):
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

        with create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:3],
            expected_status_messages=self.expected_status_messages,
        ) as (
            client,
            websocket,
        ):
            returned_pattern = select_pattern(
                websocket=websocket, pattern_name=pattern_name
            )
            assert returned_pattern == reduced_pattern

    def test_upload(self) -> None:
        with create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS,
            expected_status_messages=self.expected_status_messages,
        ) as (
            client,
            websocket,
        ):
            pass

    def test_weave_direction(self) -> None:
        # TO DO: expand this test to test commanding the same direction
        # multiple times in a row, once I know what mock loom ought to do.
        pattern_name = ALL_PATTERN_PATHS[1].name

        with create_test_client(
            app=self.app,
            upload_patterns=ALL_PATTERN_PATHS[0:4],
            expected_status_messages=self.expected_status_messages,
        ) as (
            client,
            websocket,
        ):
            select_pattern(websocket=websocket, pattern_name=pattern_name)

            for forward in (False, True):
                websocket.send_json(dict(type="weave_direction", forward=forward))
                reply = receive_dict(websocket)
                assert reply == dict(type="WeaveDirection", forward=forward)
