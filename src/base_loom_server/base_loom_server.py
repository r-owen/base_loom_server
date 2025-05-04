from __future__ import annotations

__all__ = [
    "BaseLoomServer",
    "DEFAULT_DATABASE_PATH",
    "MOCK_PORT_NAME",
]

import abc
import asyncio
import dataclasses
import enum
import json
import logging
import pathlib
import tempfile
from types import SimpleNamespace, TracebackType
from typing import Any, Type

from dtx_to_wif import read_pattern_data
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from serial_asyncio import open_serial_connection  # type: ignore

from . import client_replies
from .base_mock_loom import BaseMockLoom
from .client_replies import MessageSeverityEnum, ModeEnum, ShaftStateEnum
from .constants import LOG_NAME
from .mock_streams import StreamReaderType, StreamWriterType
from .pattern_database import PatternDatabase
from .reduced_pattern import ReducedPattern, reduced_pattern_from_pattern_data
from .utils import compute_num_within_and_repeats, compute_total_num

# The maximum number of patterns that can be in the history
MAX_PATTERNS = 25

DEFAULT_DATABASE_PATH = pathlib.Path(tempfile.gettempdir()) / "pattern_database.sqlite"

MOCK_PORT_NAME = "mock"


class CloseCode(enum.IntEnum):
    """WebSocket close codes

    A small subset of
    https://www.rfc-editor.org/rfc/rfc6455.html#section-7.4
    """

    NORMAL = 1000
    GOING_AWAY = 1001
    ERROR = 1011


class CommandError(Exception):
    pass


class BaseLoomServer:
    """Base class for a web server that controls a dobby loom.

    Subclasses should not only provide implementations for the abstract
    methods, but should also override the class constants, as appropriate.

    Args:
        num_shafts: The number of shafts the loom has.
        serial_port: The name of the serial port, e.g. "/dev/tty0".
            If the name is "mock" then use a mock loom.
        translation_dict: Language translation dict.
        reset_db: If True, delete the old database and create a new one.
        verbose: If True, log diagnostic information.
        name: User-assigned loom name.
        db_path: Path to the pattern database. Specify None for the
            default path. Unit tests specify a non-None value, to avoid
            stomping on the real database.
        enable_software_weave_direction: Can the software control
            the weave direction? For Seguin looms, always specify True.
            For Toika looms, the user must make a choice between software
            or the loom.
    """

    # Subclasses should override these, as necesary.
    # Definitely overide `default_name` and `mock_loom_type`.
    baud_rate = 9600
    default_name = "base"
    loom_reports_direction = True
    loom_reports_motion = True
    mock_loom_type: type[BaseMockLoom] | None = None

    def __init__(
        self,
        *,
        num_shafts: int,
        serial_port: str,
        translation_dict: dict[str, str],
        reset_db: bool,
        verbose: bool,
        name: str | None = None,
        db_path: pathlib.Path | None = None,
        enable_software_weave_direction: bool = True,
    ) -> None:
        if self.mock_loom_type is None:
            raise RuntimeError("Subclasses must set class variable 'mock_loom_type'")
        self.terminator = self.mock_loom_type.terminator
        self.log = logging.getLogger(LOG_NAME)
        if verbose:
            self.log.info(
                f"{self}({serial_port=!r}, {reset_db=!r}, {verbose=!r}, {db_path=!r})"
            )
        if name is None:
            name = self.default_name
        self.serial_port = serial_port
        self.translation_dict = translation_dict
        self.verbose = verbose
        self.loom_info = client_replies.LoomInfo(name=name, num_shafts=num_shafts)
        self.db_path: pathlib.Path = (
            DEFAULT_DATABASE_PATH if db_path is None else db_path
        )
        if reset_db:
            self.db_path.unlink(missing_ok=True)
        self.pattern_db = PatternDatabase(self.db_path)
        self.enable_software_weave_direction = enable_software_weave_direction
        self.websocket: WebSocket | None = None
        self.loom_connecting = False
        self.loom_disconnecting = False
        self.client_connected = False
        self.shaft_state: ShaftStateEnum = ShaftStateEnum.UNKNOWN
        self.shaft_word = 0
        self.mock_loom: BaseMockLoom | None = None
        self.loom_reader: StreamReaderType | None = None
        self.loom_writer: StreamWriterType | None = None
        self.read_client_task: asyncio.Future = asyncio.Future()
        self.read_loom_task: asyncio.Future = asyncio.Future()
        self.done_task: asyncio.Future = asyncio.Future()
        self.current_pattern: ReducedPattern | None = None
        self.jump_pick = client_replies.JumpPickNumber()
        self.jump_end = client_replies.JumpEndNumber()
        self.mode = ModeEnum.WEAVE
        self.weave_forward = True
        self.thread_low_to_high = True

    @abc.abstractmethod
    async def handle_loom_reply(self, reply_bytes: bytes) -> None:
        """Process one reply from the loom."""
        raise NotImplementedError

    @abc.abstractmethod
    async def write_shafts_to_loom(self, shaft_word: int) -> None:
        """Write the shaft word to the loom."""
        raise NotImplementedError()

    @property
    def loom_connected(self) -> bool:
        """Return True if connected to the loom."""
        return not (
            self.loom_writer is None
            or self.loom_reader is None
            or self.loom_writer.is_closing()
            or self.loom_reader.at_eof()
        )

    async def start(self) -> None:
        await self.pattern_db.init()
        await self.clear_jumps()
        # Restore current pattern, if any
        names = await self.pattern_db.get_pattern_names()
        if len(names) > 0:
            await self.select_pattern(names[-1])
        await self.connect_to_loom()

    async def close(
        self, stop_read_loom: bool = True, stop_read_client: bool = True
    ) -> None:
        """Disconnect from client and loom and stop all tasks."""
        if self.loom_writer is not None:
            if stop_read_loom:
                self.read_loom_task.cancel()
            if stop_read_client:
                self.read_client_task.cancel()
            self.loom_writer.close()
        if self.mock_loom is not None:
            await self.mock_loom.close()
        if not self.done_task.done():
            self.done_task.set_result(None)

    async def add_pattern(self, pattern: ReducedPattern) -> None:
        """Add a pattern to pattern database.

        Also purge the MAX_PATTERNS oldest entries (excluding
        the current pattern, if any) and report the new list
        of pattern names to the client.
        """
        await self.pattern_db.add_pattern(pattern=pattern, max_entries=MAX_PATTERNS)
        await self.report_pattern_names()

    async def close_websocket(
        self, ws: WebSocket, code: CloseCode = CloseCode.NORMAL, reason: str = ""
    ) -> None:
        """Close a websocket using best effort and a short timeout."""
        if ws.client_state == WebSocketState.DISCONNECTED:
            return
        try:
            async with asyncio.timeout(0.1):
                await ws.close(code, reason)
        except Exception as e:
            self.log.warning(f"{self}: failed to close websocket: {e!r}")

    async def get_initial_loom_state(self) -> None:
        """Obtain the loom state.

        Called just after the server connects to the loom.

        Usually a no-op, because a well designed loom automatically
        reports its own state when software connects to it.
        """
        pass

    async def connect_to_loom(self) -> None:
        """Connect to the loom.

        If already connected to loom, disconnect first, since
        connecting again may indicate that something is wrong.
        """
        if self.loom_connected:
            await self.disconnect_from_loom()
        try:
            self.loom_connecting = True
            await self.report_loom_connection_state()
            if self.serial_port == MOCK_PORT_NAME:
                assert self.mock_loom_type is not None  # make mypy happy
                self.mock_loom = self.mock_loom_type(
                    num_shafts=self.loom_info.num_shafts, verbose=self.verbose
                )
                assert self.mock_loom is not None  # make mypy happy
                self.loom_reader, self.loom_writer = (
                    await self.mock_loom.open_client_connection()
                )
            else:
                self.loom_reader, self.loom_writer = await open_serial_connection(
                    url=self.serial_port, baudrate=self.baud_rate
                )

                # try to purge input buffer
                transport = getattr(self.loom_writer, "transport", None)
                if transport is None:
                    self.log.warning(
                        f"{self}: Could not flush read buffer; no transport found"
                    )
                else:
                    serial_instance = getattr(transport, "_serial", None)
                    if serial_instance is None:
                        self.log.warning(
                            f"{self}: Could not flush read buffer; no serial instance found in transport"
                        )
                    elif serial_instance.in_waiting > 0:
                        serial_instance.reset_input_buffer()
                        self.log.info(f"{self}: Read buffer flushed")
                    else:
                        self.log.info(
                            f"{self}: Read buffer did not need to be flushed; it was empty"
                        )

            self.loom_connecting = False
            await self.report_loom_connection_state()
            await self.get_initial_loom_state()
        except Exception as e:
            self.loom_connecting = False
            await self.report_loom_connection_state(reason=str(e))
            raise
        finally:
            self.loom_connecting = False

        self.read_loom_task = asyncio.create_task(self.read_loom_loop())

    async def run_client(self, websocket: WebSocket) -> None:
        """Run a client connection, closing any existing connection.

        Also open a connection to the loom, if that was closed.

        Args:
            websocket: Connection to the client.
        """
        if self.client_connected:
            self.log.info(
                f"{self}: a client was already connected; closing that connection"
            )
            await self.disconnect_client()
        await websocket.accept()
        self.websocket = websocket
        self.read_client_task = asyncio.create_task(self.read_client_loop())
        if not self.loom_connected:
            try:
                await self.connect_to_loom()
            except Exception as e:
                # Note: connect_to_loom already reported the
                # (lack of) connection state, including the reason.
                # But log it here.
                self.log.exception(f"{self}: failed to reconnect to the loom: {e!r}")
        await self.done_task

    async def disconnect_client(self, cancel_read_client_loop: bool = True) -> None:
        self.read_client_task.cancel()
        websocket = self.websocket
        self.websocket = None
        if websocket is not None:
            await self.close_websocket(
                websocket,
                code=CloseCode.GOING_AWAY,
                reason=self.t("another client took control"),
            )

    async def disconnect_from_loom(self) -> None:
        """Disconnect from the loom. A no-op if already disconnected."""

        if not self.loom_connected:
            return
        self.loom_disconnecting = True
        await self.report_loom_connection_state()
        try:
            if self.loom_writer is not None:
                self.loom_writer.close()
                self.loom_reader = None
                self.loom_writer = None
            self.mock_loom = None
        finally:
            self.loom_disconnecting = False
            await self.report_loom_connection_state()

    async def basic_read_loom(self) -> bytes:
        """Read one reply from the loom.

        Perform no error checking, except that self.loom_reader exists.
        """
        assert self.loom_reader is not None
        return await self.loom_reader.readuntil(self.terminator)

    async def clear_jump_end(self, force_output=False):
        """Clear self.jump_end and report value if changed or force_output

        Args:
            force_output: If true, report `JumpEndNumber`,
                even if it has not changed.
        """
        null_jump_end = client_replies.JumpEndNumber()
        do_report = force_output or self.jump_end != null_jump_end
        self.jump_end = null_jump_end
        if do_report:
            await self.report_jump_end()

    async def clear_jump_pick(self, force_output=False):
        """Clear self.jump_pick and report value if changed or force_output

        Args:
            force_output: If true, report `JumpPickNumber`,
                even if it has not changed.
        """
        null_jump_pick = client_replies.JumpPickNumber()
        do_report = force_output or self.jump_pick != null_jump_pick
        self.jump_pick = null_jump_pick
        if do_report:
            await self.report_jump_pick()

    async def clear_jumps(self, force_output=False):
        """Clear all jumps and report values if changed or force_output."""
        await self.clear_jump_end(force_output=force_output)
        await self.clear_jump_pick(force_output=force_output)

    async def cmd_clear_pattern_names(self, command: SimpleNamespace) -> None:
        # Clear the pattern database
        # Then add the current pattern (if any)
        await self.pattern_db.clear_database()
        if self.current_pattern is not None:
            await self.add_pattern(self.current_pattern)
        else:
            await self.report_pattern_names()

    async def cmd_file(self, command: SimpleNamespace) -> None:
        suffix = command.name[-4:]
        if self.verbose:
            self.log.info(
                f"{self}: read weaving pattern {command.name!r}: data={command.data[0:80]!r}...",
            )
        pattern_data = read_pattern_data(command.data, suffix=suffix, name=command.name)
        pattern = reduced_pattern_from_pattern_data(
            name=command.name, data=pattern_data
        )
        # max_shaft_num needs +1 because pattern.threading is 0-based
        max_shaft_num = max(pattern.threading) + 1
        if max_shaft_num > self.loom_info.num_shafts:
            raise CommandError(
                f"Pattern {command.name!r} max shaft {max_shaft_num} > {self.loom_info.num_shafts}"
            )
        await self.add_pattern(pattern)

    async def cmd_jump_to_end(self, command: SimpleNamespace) -> None:
        if self.current_pattern is None:
            raise CommandError(
                self.t("cannot jump to an end") + ": " + self.t("no pattern")
            )
        if command.total_end_number0 is None:
            self.jump_end = client_replies.JumpEndNumber()
        else:
            total_end_number0 = command.total_end_number0
            end_number0, end_repeat_number = compute_num_within_and_repeats(
                total_num=total_end_number0,
                repeat_len=self.current_pattern.num_ends,
            )
            end_number1 = self.current_pattern.compute_end_number1(
                end_number0=end_number0
            )
            total_end_number1 = compute_total_num(
                num_within=end_number1,
                repeat_number=end_repeat_number,
                repeat_len=self.current_pattern.num_ends,
            )

            self.jump_end = client_replies.JumpEndNumber(
                total_end_number0=total_end_number0,
                total_end_number1=total_end_number1,
                end_number0=end_number0,
                end_number1=end_number1,
                end_repeat_number=end_repeat_number,
            )
        await self.report_jump_end()

    async def cmd_jump_to_pick(self, command: SimpleNamespace) -> None:
        if self.current_pattern is None:
            raise CommandError(
                self.t("cannot jump to a pick") + ": " + self.t("no pattern")
            )
        if command.total_picks is None:
            self.jump_pick = client_replies.JumpPickNumber()
        else:
            pick_number, pick_repeat_number = compute_num_within_and_repeats(
                total_num=command.total_picks, repeat_len=self.current_pattern.num_picks
            )
            self.jump_pick = client_replies.JumpPickNumber(
                total_picks=command.total_picks,
                pick_number=pick_number,
                pick_repeat_number=pick_repeat_number,
            )
        await self.report_jump_pick()

    async def cmd_mode(self, command: SimpleNamespace) -> None:
        self.mode = ModeEnum(command.mode)
        await self.report_mode()

    async def cmd_select_pattern(self, command: SimpleNamespace) -> None:
        name = command.name
        if self.current_pattern is not None and self.current_pattern.name == name:
            return
        await self.select_pattern(name)
        await self.clear_jumps()

    async def cmd_separate_threading_repeats(self, command: SimpleNamespace) -> None:
        if self.current_pattern is None:
            return
        await self.pattern_db.update_separate_threading_repeats(
            pattern_name=self.current_pattern.name,
            separate_threading_repeats=command.separate,
        )
        self.current_pattern.separate_threading_repeats = command.separate
        await self.report_separate_threading_repeats()

    async def cmd_separate_weaving_repeats(self, command: SimpleNamespace) -> None:
        if self.current_pattern is None:
            return
        await self.pattern_db.update_separate_weaving_repeats(
            pattern_name=self.current_pattern.name,
            separate_weaving_repeats=command.separate,
        )
        self.current_pattern.separate_weaving_repeats = command.separate
        await self.report_separate_weaving_repeats()

    async def cmd_thread_direction(self, command: SimpleNamespace) -> None:
        self.thread_low_to_high = command.low_to_high
        await self.report_thread_direction()

    async def cmd_thread_group_size(self, command: SimpleNamespace) -> None:
        if self.current_pattern is None:
            return
        await self.pattern_db.update_thread_group_size(
            pattern_name=self.current_pattern.name,
            thread_group_size=command.group_size,
        )
        self.current_pattern.thread_group_size = command.group_size
        await self.report_thread_group_size()

    async def cmd_weave_direction(self, command: SimpleNamespace) -> None:
        self.weave_forward = command.forward
        await self.report_weave_direction()

    async def cmd_oobcommand(self, command: SimpleNamespace) -> None:
        if self.mock_loom is not None:
            await self.mock_loom.oob_command(command.command)
        else:
            self.log.warning(f"Ignoring oob command {command.command!r}: no mock loom")

    def get_threading_shaft_word(self) -> int:
        if self.current_pattern is None:
            return 0
        return self.current_pattern.get_threading_shaft_word()

    async def handle_next_pick_request(self) -> None:
        """Handle next pick request from loom.

        Call this from handle_loom_reply.

        Figure out the next pick, send it to the loom,
        and report the information to the client.
        """
        if not self.current_pattern:
            return
        match self.mode:
            case ModeEnum.WEAVE:
                # Command a new pick, if there is one.
                if self.jump_pick.pick_number is not None:
                    self.current_pattern.set_current_pick_number(
                        self.jump_pick.pick_number
                    )
                else:
                    self.increment_pick_number()
                if self.jump_pick.pick_repeat_number is not None:
                    self.current_pattern.pick_repeat_number = (
                        self.jump_pick.pick_repeat_number
                    )
                pick = self.current_pattern.get_current_pick()
                await self.write_shafts_to_loom(pick.shaft_word)
                await self.clear_jumps()
                await self.report_current_pick_number()
            case ModeEnum.THREAD:
                # Advance to the next thread group, if there is one
                if self.jump_end.end_number0 is not None:
                    self.current_pattern.set_current_end_number(
                        end_number0=self.jump_end.end_number0,
                        end_number1=self.jump_end.end_number1,
                        end_repeat_number=self.jump_end.end_repeat_number,
                    )
                else:
                    self.increment_end_number()

                shaft_word = self.get_threading_shaft_word()
                await self.write_shafts_to_loom(shaft_word)
                await self.clear_jumps()
                await self.report_current_end_numbers()
            case ModeEnum.TEST:
                raise RuntimeError("Test mode is not yet supported")
            case _:
                raise RuntimeError(f"Invalid mode={self.mode!r}.")

    def increment_pick_number(self) -> int:
        """Increment pick_number in the current direction.

        Increment pick_repeat_number as well, if appropriate.

        Return the new pick number. This will be 0 if
        pick_repeat_number changed,
        or if unweaving and pick_repeat_number
        would be decremented to 0.
        """
        if self.current_pattern is None:
            return 0
        return self.current_pattern.increment_pick_number(
            weave_forward=self.weave_forward
        )

    def increment_end_number(self) -> None:
        """Increment end_number0 in the current direction."""
        if self.current_pattern is None:
            return
        self.current_pattern.increment_end_number(
            thread_low_to_high=self.thread_low_to_high
        )

    async def read_client_loop(self) -> None:
        """Read and process commands from the client."""
        # report loom connection state
        # and (if connected) request loom status
        try:
            self.client_connected = True
            await self.report_initial_server_state()
            if not self.loom_connected:
                await self.connect_to_loom()
            while self.client_connected:
                assert self.websocket is not None
                try:
                    data = await self.websocket.receive_json()
                except json.JSONDecodeError:
                    self.log.info(f"{self}: ignoring invalid command: not json-encoded")

                # Parse the command
                try:
                    cmd_type = data.get("type")
                    if cmd_type is None:
                        await self.report_command_problem(
                            message=f"Invalid command; no 'type' field: {data!r}",
                            severity=MessageSeverityEnum.WARNING,
                        )
                        continue
                    command = SimpleNamespace(**data)
                    if self.verbose:
                        msg_summary = str(command)
                        if len(msg_summary) > 80:
                            msg_summary = msg_summary[0:80] + "..."
                        self.log.info(f"{self}: read command {msg_summary}")
                    cmd_handler = getattr(self, f"cmd_{cmd_type}", None)
                except Exception as e:
                    message = f"command {data} failed: {e!r}"
                    self.log.exception(f"{self}: {message}")
                    await self.report_command_done(
                        cmd_type=cmd_type, success=False, message=message
                    )

                # Execute the command
                try:
                    if cmd_handler is None:
                        await self.report_command_done(
                            cmd_type=cmd_type,
                            success=False,
                            message=f"Invalid command; unknown type {cmd_type!r}",
                        )
                        continue
                    await cmd_handler(command)
                    await self.report_command_done(cmd_type=cmd_type, success=True)
                except CommandError as e:
                    await self.report_command_done(
                        cmd_type=cmd_type, success=False, message=str(e)
                    )
                except Exception as e:
                    message = f"command {command} unexpectedly failed: {e!r}"
                    self.log.exception(f"{self}: {message}")
                    await self.report_command_done(
                        cmd_type=cmd_type, success=False, message=message
                    )

        except asyncio.CancelledError:
            return
        except WebSocketDisconnect:
            self.log.info(f"{self}: client disconnected")
            return
        except Exception as e:
            self.log.exception(f"{self}: bug: client read looop failed: {e!r}")
            await self.report_command_problem(
                message="Client read loop failed; try refreshing",
                severity=MessageSeverityEnum.ERROR,
            )
            self.client_connected = False
            if self.websocket is not None:
                await self.close_websocket(
                    self.websocket, code=CloseCode.ERROR, reason=repr(e)
                )

    async def read_loom_loop(self) -> None:
        """Read and process replies from the loom."""
        try:
            if self.loom_reader is None:
                raise RuntimeError("No loom reader")
            await self.get_initial_loom_state()
            while True:
                reply_bytes = await self.basic_read_loom()
                if self.verbose:
                    self.log.info(f"{self}: read loom reply: {reply_bytes!r}")
                if not reply_bytes:
                    self.log.warning("Reader closed; quit read_loom_loop")
                    return
                await self.handle_loom_reply(reply_bytes)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            message = f"Server stopped listening to the loom: {e!r}"
            self.log.exception(f"{self}: {message}")
            await self.report_command_problem(
                message=message,
                severity=MessageSeverityEnum.ERROR,
            )
            await self.disconnect_from_loom()

    async def report_command_done(
        self, cmd_type: str, success: bool, message: str = ""
    ) -> None:
        """Report completion of a command"""
        reply = client_replies.CommandDone(
            cmd_type=cmd_type, success=success, message=message
        )
        await self.write_to_client(reply)

    async def report_command_problem(
        self, message: str, severity: MessageSeverityEnum
    ) -> None:
        """Report a CommandProblem to the client."""
        reply = client_replies.CommandProblem(message=message, severity=severity)
        await self.write_to_client(reply)

    async def report_current_pattern(self) -> None:
        """Report pattern to the client"""
        if self.current_pattern is not None:
            await self.write_to_client(self.current_pattern)

    async def report_initial_server_state(self) -> None:
        """Report server state.

        Called just after a client connects to the server.
        """
        await self.report_loom_connection_state()
        await self.write_to_client(self.loom_info)
        await self.report_mode()
        await self.report_pattern_names()
        await self.report_weave_direction()
        await self.clear_jumps(force_output=True)
        await self.report_current_pattern()
        await self.report_current_end_numbers()
        await self.report_current_pick_number()
        await self.report_separate_threading_repeats()
        await self.report_separate_weaving_repeats()
        await self.report_shaft_state()
        await self.report_thread_direction()
        await self.report_thread_group_size()

    async def report_loom_connection_state(self, reason: str = "") -> None:
        """Report LoomConnectionState to the client."""
        if self.loom_connecting:
            state = client_replies.ConnectionStateEnum.CONNECTING
        elif self.loom_disconnecting:
            state = client_replies.ConnectionStateEnum.DISCONNECTING
        elif self.loom_connected:
            state = client_replies.ConnectionStateEnum.CONNECTED
        else:
            state = client_replies.ConnectionStateEnum.DISCONNECTED
        reply = client_replies.LoomConnectionState(state=state, reason=reason)
        await self.write_to_client(reply)

    async def report_pattern_names(self) -> None:
        """Report PatternNames to the client."""
        names = await self.pattern_db.get_pattern_names()
        reply = client_replies.PatternNames(names=names)
        await self.write_to_client(reply)

    async def report_current_pick_number(self) -> None:
        """Report CurrentPickNumber to the client.

        Also update pick information in the database."""
        if self.current_pattern is None:
            return
        await self.pattern_db.update_pick_number(
            pattern_name=self.current_pattern.name,
            pick_number=self.current_pattern.pick_number,
            pick_repeat_number=self.current_pattern.pick_repeat_number,
        )
        reply = client_replies.CurrentPickNumber(
            total_picks=compute_total_num(
                num_within=self.current_pattern.pick_number,
                repeat_number=self.current_pattern.pick_repeat_number,
                repeat_len=self.current_pattern.num_picks,
            ),
            pick_number=self.current_pattern.pick_number,
            pick_repeat_number=self.current_pattern.pick_repeat_number,
        )
        await self.write_to_client(reply)

    async def report_current_end_numbers(self) -> None:
        """Report CurrentEndNumber to the client.

        Also update threading information the database.
        """
        if self.current_pattern is None:
            return
        await self.pattern_db.update_end_number(
            pattern_name=self.current_pattern.name,
            end_number0=self.current_pattern.end_number0,
            end_number1=self.current_pattern.end_number1,
            end_repeat_number=self.current_pattern.end_repeat_number,
        )
        total_end_number0 = compute_total_num(
            num_within=self.current_pattern.end_number0,
            repeat_number=self.current_pattern.end_repeat_number,
            repeat_len=self.current_pattern.num_ends,
        )
        total_end_number1 = compute_total_num(
            num_within=self.current_pattern.end_number1,
            repeat_number=self.current_pattern.end_repeat_number,
            repeat_len=self.current_pattern.num_ends,
        )
        reply = client_replies.CurrentEndNumber(
            total_end_number0=total_end_number0,
            total_end_number1=total_end_number1,
            end_number0=self.current_pattern.end_number0,
            end_number1=self.current_pattern.end_number1,
            end_repeat_number=self.current_pattern.end_repeat_number,
        )
        await self.write_to_client(reply)

    async def report_jump_end(self) -> None:
        """Report JumpEndNumber to the client."""
        await self.write_to_client(self.jump_end)

    async def report_jump_pick(self) -> None:
        """Report JumpPickNumber to the client."""
        await self.write_to_client(self.jump_pick)

    async def report_shaft_state(self) -> None:
        """Report ShaftState to the client."""
        await self.write_to_client(
            client_replies.ShaftState(
                state=self.shaft_state, shaft_word=self.shaft_word
            )
        )

    async def report_mode(self) -> None:
        """Report the current mode to the client."""
        await self.write_to_client(client_replies.Mode(mode=self.mode))

    async def report_separate_threading_repeats(self) -> None:
        if self.current_pattern is None:
            return
        await self.write_to_client(
            client_replies.SeparateThreadingRepeats(
                separate=self.current_pattern.separate_threading_repeats
            )
        )

    async def report_separate_weaving_repeats(self) -> None:
        if self.current_pattern is None:
            return
        await self.write_to_client(
            client_replies.SeparateWeavingRepeats(
                separate=self.current_pattern.separate_weaving_repeats
            )
        )

    async def report_status_message(
        self, message: str, severity: MessageSeverityEnum
    ) -> None:
        """Report a status message to the client."""
        await self.write_to_client(
            client_replies.StatusMessage(message=message, severity=severity)
        )

    async def report_thread_direction(self) -> None:
        """Report ThreadDirection"""
        client_reply = client_replies.ThreadDirection(
            low_to_high=self.thread_low_to_high
        )
        await self.write_to_client(client_reply)

    async def report_thread_group_size(self) -> None:
        """Report ThreadGroupSize"""
        if self.current_pattern is None:
            return
        client_reply = client_replies.ThreadGroupSize(
            group_size=self.current_pattern.thread_group_size
        )
        await self.write_to_client(client_reply)

    async def report_weave_direction(self) -> None:
        """Report WeaveDirection"""
        client_reply = client_replies.WeaveDirection(forward=self.weave_forward)
        await self.write_to_client(client_reply)

    async def select_pattern(self, name: str) -> None:
        try:
            pattern = await self.pattern_db.get_pattern(name)
        except LookupError:
            raise CommandError(f"select_pattern failed: no such pattern: {name}")
        self.current_pattern = pattern
        await self.report_current_pattern()
        await self.report_current_end_numbers()
        await self.report_current_pick_number()
        await self.report_separate_threading_repeats()
        await self.report_separate_weaving_repeats()
        await self.report_thread_group_size()

    def t(self, phrase: str) -> str:
        """Translate a phrase, if possible."""
        if phrase not in self.translation_dict:
            self.log.warning(f"{phrase!r} not in translation dict")
        return self.translation_dict.get(phrase, phrase)

    async def write_to_client(self, reply: Any) -> None:
        """Send a reply to the client.

        Args:
            reply: The reply to write, as a dataclass. It should have
                a "type" field whose value is a string.
        """
        if self.client_connected:
            assert self.websocket is not None
            reply_dict = dataclasses.asdict(reply)
            if self.verbose:
                reply_str = str(reply_dict)
                if len(reply_str) > 120:
                    reply_str = reply_str[0:120] + "..."
                self.log.info(f"{self}: reply to client: {reply_str}")
            await self.websocket.send_json(reply_dict)
        else:
            if self.verbose:
                reply_str = str(reply)
                if len(reply_str) > 120:
                    reply_str = reply_str[0:120] + "..."
                self.log.info(f"{self}: do not send reply {reply_str}; not connected")

    async def write_to_loom(self, data: bytes | bytearray | str) -> None:
        """Send data to the loom.

        Args:
            data: The data to send, without a terminator.
                (This method will append the terminator).
        """
        if self.loom_writer is None or self.loom_writer.is_closing():
            raise RuntimeError("Cannot write to the loom: no connection.")
        data_bytes = data.encode() if isinstance(data, str) else bytes(data)
        if self.verbose:
            self.log.info(
                f"{self}: sending command to loom: {data_bytes + self.terminator!r}"
            )
        self.loom_writer.write(data_bytes + self.terminator)
        await self.loom_writer.drain()

    def __repr__(self) -> str:
        return type(self).__name__

    async def __aenter__(self) -> BaseLoomServer:
        await self.start()
        return self

    async def __aexit__(
        self,
        type: Type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
