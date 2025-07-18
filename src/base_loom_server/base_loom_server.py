from __future__ import annotations

__all__ = ["BaseLoomServer", "DEFAULT_DATABASE_PATH", "MOCK_PORT_NAME"]

import abc
import asyncio
import copy
import dataclasses
import enum
import importlib.resources
import json
import logging
import pathlib
from types import SimpleNamespace, TracebackType
from typing import TYPE_CHECKING, Any, Self

from dtx_to_wif import read_pattern_data
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from serial_asyncio import open_serial_connection  # type: ignore[import-untyped]

from . import client_replies
from .constants import LOG_NAME
from .enums import ConnectionStateEnum, DirectionControlEnum, MessageSeverityEnum, ModeEnum, ShaftStateEnum
from .pattern_database import PatternDatabase
from .reduced_pattern import ReducedPattern, reduced_pattern_from_pattern_data
from .translations import get_language_names, get_translation_dict
from .utils import compute_num_within_and_repeats, compute_total_num

if TYPE_CHECKING:
    from .base_mock_loom import BaseMockLoom
    from .mock_streams import StreamReaderType, StreamWriterType

# The maximum number of patterns that can be in the history
MAX_PATTERNS = 25

DEFAULT_DATABASE_PATH = pathlib.Path.home() / "loom_server_database.sqlite"
SETTINGS_FILE_NAME = "loom_server_settings.json"

MAX_THREAD_GROUP_SIZE = 10

# Maximum weaving pattern data to log
MAX_LOG_PATTERN_LEN = 100


MOCK_PORT_NAME = "mock"

PKG_FILES = importlib.resources.files("base_loom_server")
LOCALE_FILES = PKG_FILES.joinpath("locales")


class CloseCode(enum.IntEnum):
    """WebSocket close codes.

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
        reset_db: If True, delete the old database and create a new one.
        verbose: If True, log diagnostic information.
        db_path: Path to the pattern database. Specify None for the
            default path. Unit tests specify a non-None value, to avoid
            stomping on the real database.
    """

    # Subclasses should override these, as necesary.
    # Definitely overide `default_name` and `mock_loom_type`.
    baud_rate = 9600
    default_name = "base"
    help_url = "https://r-owen.github.io/base_loom_server/"
    loom_reports_direction = True
    loom_reports_motion = True
    mock_loom_type: type[BaseMockLoom] | None = None
    supports_full_direction_control = True

    def __init__(
        self,
        *,
        num_shafts: int,
        serial_port: str,
        reset_db: bool,
        verbose: bool,
        db_path: pathlib.Path | None = None,
    ) -> None:
        if self.mock_loom_type is None:
            raise RuntimeError("Subclasses must set class variable 'mock_loom_type'")
        self.terminator = self.mock_loom_type.terminator
        self.log = logging.getLogger(LOG_NAME)
        if verbose:
            self.log.info(f"{self}({serial_port=!r}, {reset_db=!r}, {verbose=!r}, {db_path=!r})")

        self.serial_port = serial_port
        self.verbose = verbose
        self.loom_info = client_replies.LoomInfo(
            num_shafts=num_shafts,
            serial_port=serial_port,
            is_mock=serial_port == MOCK_PORT_NAME,
        )
        self.db_path: pathlib.Path = DEFAULT_DATABASE_PATH if db_path is None else db_path
        if reset_db:
            self.log.info(f"Resetting database {self.db_path} by request")
            self.reset_database()
        try:
            self.pattern_db = PatternDatabase(self.db_path)
        except Exception as e:
            self.log.warning(f"Resetting database {self.db_path} because open failed: {e!r}")
            self.reset_database()

        # Compute initial value for direction_control.
        # This value will be overridden by the settings file, if it exists.
        if self.supports_full_direction_control:
            direction_control = DirectionControlEnum.FULL
        elif self.loom_reports_direction:
            # We have to pick something for the initial default,
            # and it may as well be the loom.
            direction_control = DirectionControlEnum.LOOM
        else:
            # This value is required for unit tests, which want immediate
            # notification when the direction changes.
            direction_control = DirectionControlEnum.SOFTWARE

        self.settings = client_replies.Settings(
            loom_name=self.default_name,
            language="English",
            direction_control=direction_control,
            end1_on_right=True,
            thread_group_size=4,
            thread_right_to_left=True,
            thread_back_to_front=True,
        )
        self.settings_path = self.db_path.parent / SETTINGS_FILE_NAME
        self.translation_dict = get_translation_dict(language=self.settings.language, logger=self.log)
        self.load_settings()
        self.save_settings()

        self.websocket: WebSocket | None = None
        self.loom_connecting: bool = False
        self.loom_disconnecting: bool = False
        self.client_connected: bool = False
        self.shaft_state: ShaftStateEnum = (
            ShaftStateEnum.UNKNOWN if self.loom_reports_motion else ShaftStateEnum.DONE
        )
        self.shaft_word: int = 0
        self.mock_loom: BaseMockLoom | None = None
        self.loom_reader: StreamReaderType | None = None
        self.loom_writer: StreamWriterType | None = None
        self.read_client_task: asyncio.Future[None] = asyncio.Future()
        self.read_loom_task: asyncio.Future[None] = asyncio.Future()
        self.done_task: asyncio.Future[None] = asyncio.Future()
        self.current_pattern: ReducedPattern | None = None
        self.jump_pick = client_replies.JumpPickNumber()
        self.jump_end = client_replies.JumpEndNumber()
        self.mode = ModeEnum.WEAVE
        self.direction_forward: bool = True
        self.__post_init__()

    @abc.abstractmethod
    async def handle_loom_reply(self, reply_bytes: bytes) -> None:
        """Process one reply from the loom."""
        raise NotImplementedError

    @abc.abstractmethod
    async def write_shafts_to_loom(self, shaft_word: int) -> None:
        """Write the shaft word to the loom."""
        raise NotImplementedError

    @property
    def enable_software_direction(self) -> bool:
        """Is software direction control enabled?"""
        return self.settings.direction_control in {
            DirectionControlEnum.FULL,
            DirectionControlEnum.SOFTWARE,
        }

    @property
    def thread_low_to_high(self) -> bool:
        """Return True if threading (or unthreading) is currently low to high.

        Takes into account settings and self.direction_forward.
        """
        low_to_high = self.settings.thread_back_to_front == self.settings.thread_right_to_left
        if not self.settings.end1_on_right:
            low_to_high = not low_to_high
        if not self.direction_forward:
            low_to_high = not low_to_high
        return low_to_high

    def __post_init__(self) -> None:
        """Subclases may override this method, preferably instead of
        overriding the constructor.

        Called at the end of the constructor.

        By default this is a no-op so subclases need not call
        `super().__post_init__()`
        """

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
        """Run asynchronous startup tasks.

        Initialize the pattern database and connect to the loom.
        """
        await self.pattern_db.init()
        if not await self.pattern_db.check_schema():
            self.log.warning(f"Resetting database {self.db_path} because the schema is outdated")
            self.reset_database()
        await self.clear_jumps()
        # Restore current pattern, if any
        names = await self.pattern_db.get_pattern_names()
        if len(names) > 0:
            await self.select_pattern(names[-1])
        await self.connect_to_loom()

    async def close(self, *, stop_read_loom: bool = True, stop_read_client: bool = True) -> None:
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
            if self.loom_info.is_mock:
                assert self.mock_loom_type is not None  # make mypy happy
                self.mock_loom = self.mock_loom_type(
                    num_shafts=self.loom_info.num_shafts, verbose=self.verbose
                )
                assert self.mock_loom is not None  # make mypy happy
                self.loom_reader, self.loom_writer = await self.mock_loom.open_client_connection()
            else:
                self.loom_reader, self.loom_writer = await open_serial_connection(
                    url=self.loom_info.serial_port, baudrate=self.baud_rate
                )

                # try to purge input buffer
                transport = getattr(self.loom_writer, "transport", None)
                if transport is None:
                    self.log.warning(f"{self}: Could not flush read buffer; no transport found")
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
                        self.log.info(f"{self}: Read buffer did not need to be flushed; it was empty")

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
            self.log.info(f"{self}: a client was already connected; closing that connection")
            await self.disconnect_client()
        await websocket.accept()
        self.websocket = websocket
        self.read_client_task = asyncio.create_task(self.read_client_loop())
        if not self.loom_connected:
            try:
                await self.connect_to_loom()
            except Exception:
                # Note: connect_to_loom already reported the
                # (lack of) connection state, including the reason.
                # But log it here.
                self.log.exception(f"{self}: failed to reconnect to the loom")
        await self.done_task

    async def disconnect_client(self) -> None:
        """Disconnect the current client, if any."""
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
        """Disconnect the loom. A no-op if already disconnected."""
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

    async def clear_jump_end(self, *, force_output: bool = False) -> None:
        """Clear self.jump_end and report value if changed or force_output.

        Args:
            force_output: If true, report `JumpEndNumber`,
                even if it has not changed.
        """
        null_jump_end = client_replies.JumpEndNumber()
        do_report = force_output or self.jump_end != null_jump_end
        self.jump_end = null_jump_end
        if do_report:
            await self.report_jump_end()

    async def clear_jump_pick(self, *, force_output: bool = False) -> None:
        """Clear self.jump_pick and report value if changed or force_output.

        Args:
            force_output: If true, report `JumpPickNumber`,
                even if it has not changed.
        """
        null_jump_pick = client_replies.JumpPickNumber()
        do_report = force_output or self.jump_pick != null_jump_pick
        self.jump_pick = null_jump_pick
        if do_report:
            await self.report_jump_pick()

    async def clear_jumps(self, *, force_output: bool = False) -> None:
        """Clear all jumps and report values if changed or force_output."""
        await self.clear_jump_end(force_output=force_output)
        await self.clear_jump_pick(force_output=force_output)

    async def cmd_clear_pattern_names(
        self,
        command: SimpleNamespace,  # noqa: ARG002
    ) -> None:
        """Handle the clear_pattern_names command.

        Clear all patterns except the current pattern.
        """
        # Clear the pattern database
        # Then add the current pattern (if any)
        await self.pattern_db.clear_database()
        if self.current_pattern is not None:
            await self.add_pattern(self.current_pattern)
        else:
            await self.report_pattern_names()

    async def cmd_direction(self, command: SimpleNamespace) -> None:
        """Handle the direction command: set direction."""
        self.direction_forward = command.forward
        await self.report_direction()

    async def cmd_jump_to_end(self, command: SimpleNamespace) -> None:
        """Handle the jump_to_end command."""
        if self.current_pattern is None:
            raise CommandError(self.t("cannot jump") + ": " + self.t("no pattern"))
        if command.total_end_number0 is None:
            self.jump_end = client_replies.JumpEndNumber()
        else:
            if command.total_end_number0 < 0:
                raise CommandError(self.t("Number must be") + " >= 0")
            end_number0, end_repeat_number = compute_num_within_and_repeats(
                total_num=command.total_end_number0,
                repeat_len=self.current_pattern.num_ends,
            )
            end_number1 = self.current_pattern.compute_end_number1(end_number0=end_number0)
            total_end_number1 = compute_total_num(
                num_within=end_number1,
                repeat_number=end_repeat_number,
                repeat_len=self.current_pattern.num_ends,
            )

            self.jump_end = client_replies.JumpEndNumber(
                total_end_number0=command.total_end_number0,
                total_end_number1=total_end_number1,
                end_number0=end_number0,
                end_number1=end_number1,
                end_repeat_number=end_repeat_number,
            )
        await self.report_jump_end()

    async def cmd_jump_to_pick(self, command: SimpleNamespace) -> None:
        """Handle the jump_to_pick command."""
        if self.current_pattern is None:
            raise CommandError(self.t("cannot jump") + ": " + self.t("no pattern"))
        if command.total_pick_number is None:
            self.jump_pick = client_replies.JumpPickNumber()
        else:
            if command.total_pick_number < 0:
                raise CommandError(self.t("Number must be") + " >= 0")
            pick_number, pick_repeat_number = compute_num_within_and_repeats(
                total_num=command.total_pick_number,
                repeat_len=self.current_pattern.num_picks,
            )
            self.jump_pick = client_replies.JumpPickNumber(
                total_pick_number=command.total_pick_number,
                pick_number=pick_number,
                pick_repeat_number=pick_repeat_number,
            )
        await self.report_jump_pick()

    async def cmd_mode(self, command: SimpleNamespace) -> None:
        """Handle the mode command: set the mode."""
        self.mode = ModeEnum(command.mode)
        await self.report_mode()

    async def cmd_select_pattern(self, command: SimpleNamespace) -> None:
        """Handle the select_pattern command."""
        name = command.name
        await self.select_pattern(name)
        await self.clear_jumps()

    async def cmd_separate_threading_repeats(self, command: SimpleNamespace) -> None:
        """Handle the separate_threading_repeats command."""
        if self.current_pattern is None:
            return
        await self.pattern_db.update_separate_threading_repeats(
            pattern_name=self.current_pattern.name,
            separate_threading_repeats=command.separate,
        )
        self.current_pattern.separate_threading_repeats = command.separate
        await self.report_separate_threading_repeats()

    async def cmd_separate_weaving_repeats(self, command: SimpleNamespace) -> None:
        """Handle the separate_weaving_repeats command."""
        if self.current_pattern is None:
            return
        await self.pattern_db.update_separate_weaving_repeats(
            pattern_name=self.current_pattern.name,
            separate_weaving_repeats=command.separate,
        )
        self.current_pattern.separate_weaving_repeats = command.separate
        await self.report_separate_weaving_repeats()

    async def cmd_settings(self, command: SimpleNamespace) -> None:
        """Handle the settings command: set one or more settings."""
        bad_keys: list[str] = []
        new_settings = copy.copy(self.settings)
        # Use raw_value to avoid warnings about overwriting a loop variable.
        for key, raw_value in vars(command).items():
            value = raw_value
            # Check values
            if key == "type":
                continue

            if key == "direction_control":
                value = DirectionControlEnum(value)
                if self.supports_full_direction_control:
                    if value is not DirectionControlEnum.FULL:
                        raise CommandError(f"invalid {key}={value!r}: loom supports full direction control")
                elif value is DirectionControlEnum.FULL:
                    raise CommandError(
                        f"invalid {key}={value!r}: loom doesn't support full direction control"
                    )
            elif key == "language":
                if value != self.settings.language:
                    try:
                        self.translation_dict = get_translation_dict(language=value, logger=self.log)
                    except Exception as e:
                        raise CommandError(f"Failed to load language {value!r}: {e!r}") from e
            else:
                expected_type = dict(
                    loom_name=str,
                    end1_on_right=bool,
                    thread_group_size=int,
                    thread_right_to_left=bool,
                    thread_back_to_front=bool,
                ).get(key)
                if expected_type is None:
                    bad_keys.append(key)
                    continue
                if not isinstance(value, expected_type):
                    raise CommandError(f"invalid {key}={value!r}: must be type {expected_type}")
                if key == "thread_group_size":
                    assert isinstance(value, int)  # Make mypy happy
                    if value < 1 or value > MAX_THREAD_GROUP_SIZE:
                        raise CommandError(
                            f"invalid {key}={value!r}: must be in range [1, {MAX_THREAD_GROUP_SIZE}]"
                        )
            setattr(new_settings, key, value)
        if bad_keys:
            raise CommandError(f"Invalid settings names {bad_keys}")
        self.settings = new_settings
        await self.report_settings()
        self.save_settings()

    async def cmd_thread_group_size(self, command: SimpleNamespace) -> None:
        """Handle the thread_group_size command."""
        if self.current_pattern is None:
            return
        await self.pattern_db.update_thread_group_size(
            pattern_name=self.current_pattern.name,
            thread_group_size=command.group_size,
        )
        self.current_pattern.thread_group_size = command.group_size
        await self.report_thread_group_size()

    async def cmd_oobcommand(self, command: SimpleNamespace) -> None:
        """Handle the oob_command command.

        Send an out-of-band command to the mock loom.
        Ignored with a logged warning if the loom is not the mock loom.
        """
        if self.mock_loom is not None:
            await self.mock_loom.oob_command(command.command)
        else:
            self.log.warning(f"Ignoring oob command {command.command!r}: no mock loom")

    async def cmd_upload(self, command: SimpleNamespace) -> None:
        """Handle the upload command."""
        suffix = command.name[-4:]
        if self.verbose:
            cmd_data = command.data
            if len(cmd_data) > MAX_LOG_PATTERN_LEN:
                cmd_data = cmd_data[0:MAX_LOG_PATTERN_LEN] + "..."
            self.log.info(
                f"{self}: read weaving pattern {command.name!r}: data={cmd_data!r}",
            )
        pattern_data = read_pattern_data(command.data, suffix=suffix, name=command.name)
        pattern = reduced_pattern_from_pattern_data(name=command.name, data=pattern_data)
        # Check that the pattern does not require too many shafts.
        # max_shaft_num needs +1 because pattern.threading is 0-based.
        max_shaft_num = max(pattern.threading) + 1
        if max_shaft_num > self.loom_info.num_shafts:
            raise CommandError(
                f"Pattern {command.name!r} max shaft {max_shaft_num} > {self.loom_info.num_shafts}"
            )

        pattern.thread_group_size = self.settings.thread_group_size

        await self.add_pattern(pattern)

    def get_threading_shaft_word(self) -> int:
        """Get the current threading shaft word."""
        if self.current_pattern is None:
            return 0
        return self.current_pattern.get_threading_shaft_word()

    async def handle_next_pick_request(self) -> bool:
        """Handle next pick request from loom.

        Call this from handle_loom_reply.

        Figure out the next pick, send it to the loom,
        and report the current pick or end numbers to the client
        (if we were not at the beginning of the work).

        Returns:
            did_advance: True if the loom was sent the next set of shafts.
                False if in Setting mode, or no current pattern,
                or attemped to go beyond the start of the pattern.
        """
        if not self.current_pattern:
            return False

        did_advance = False
        match self.mode:
            case ModeEnum.WEAVE:
                # Command a new pick, if there is one.
                if self.jump_pick.pick_number is not None:
                    self.current_pattern.set_current_pick_number(self.jump_pick.pick_number)
                else:
                    try:
                        self.increment_pick_number()
                    except IndexError:
                        await self.write_to_client(
                            client_replies.StatusMessage(
                                message=self.t("At start of weaving"),
                                severity=MessageSeverityEnum.ERROR,
                            )
                        )
                        return False
                if self.jump_pick.pick_repeat_number is not None:
                    self.current_pattern.pick_repeat_number = self.jump_pick.pick_repeat_number
                pick = self.current_pattern.get_current_pick()
                await self.write_shafts_to_loom(pick.shaft_word)
                await self.clear_jumps()
                await self.report_current_pick_number()
                did_advance = True
            case ModeEnum.THREAD:
                # Advance to the next thread group, if there is one
                if self.jump_end.end_number0 is not None:
                    self.current_pattern.set_current_end_number(
                        end_number0=self.jump_end.end_number0,
                        end_number1=self.jump_end.end_number1,
                        end_repeat_number=self.jump_end.end_repeat_number,
                    )
                else:
                    try:
                        self.increment_end_number()
                    except IndexError:
                        await self.write_to_client(
                            client_replies.StatusMessage(
                                message=self.t("At start of threading"),
                                severity=MessageSeverityEnum.ERROR,
                            )
                        )
                        return False
                shaft_word = self.get_threading_shaft_word()
                await self.write_shafts_to_loom(shaft_word)
                await self.clear_jumps()
                await self.report_current_end_numbers()
                did_advance = True
            case ModeEnum.SETTINGS:
                self.log.warning("Next pick ignored in SETTINGS mode")
            case _:
                raise RuntimeError(f"Invalid mode={self.mode!r}.")
        return did_advance

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
        return self.current_pattern.increment_pick_number(direction_forward=self.direction_forward)

    def increment_end_number(self) -> None:
        """Increment end_number0 in the current direction."""
        if self.current_pattern is None:
            return
        self.current_pattern.increment_end_number(thread_low_to_high=self.thread_low_to_high)

    def load_settings(self) -> None:
        """Read the settings file, if it exists.

        Usable entries will replace the values in `self.settings`
        (which must already be set to a valid value).
        Unusable entries will be ignored, with a logged warning.
        """
        if not self.settings_path.exists():
            self.log.info(f"Settings file {self.settings_path} does not exist")
            return

        try:
            with self.settings_path.open("r", encoding="utf_8") as f:
                settings_dict = json.load(f)
        except Exception as e:
            self.log.warning(
                f"Deleting settings file {self.settings_path} because it could not be read as json: {e!r}"
            )
            self.settings_path.unlink()
            return

        # Use raw_value to avoid warnings about overwriting a loop variable.
        for key, raw_value in settings_dict.items():
            value = raw_value
            if key == "type":
                continue
            default_value = getattr(self.settings, key, None)
            if default_value is None:
                self.log.warning(f"Ignoring setting {key}={value!r}: uknown key")
                continue

            if key == "direction_control":
                try:
                    value = DirectionControlEnum(value)
                except Exception:
                    self.log.warning(f"Ignoring setting {key}={value!r}: invalid enum value")
                    continue

                if self.supports_full_direction_control:
                    if value is not DirectionControlEnum.FULL:
                        self.log.warning(
                            f"Ingoring setting {key}={value!r}: loom supports full direction control"
                        )
                        continue
                elif value is DirectionControlEnum.FULL:
                    self.log.warning(
                        f"Ignoring setting {key}={value!r}: loom doesn't support full direction control"
                    )
                    continue

            elif key == "language":
                try:
                    self.translation_dict = get_translation_dict(language=value, logger=self.log)
                except Exception as e:
                    self.log.error(f"Failed to load translation dict {value!r}: {e!r}")
                    continue

            if not isinstance(value, type(default_value)):
                self.log.warning(f"Ignoring setting {key}={value!r}: invalid value")
                continue

            if key == "thread_group_size" and (value < 1 or value > MAX_THREAD_GROUP_SIZE):
                self.log.warning(
                    f"Ignoring setting {key}={value!r}: not in range [1, {MAX_THREAD_GROUP_SIZE}"
                )
                continue

            setattr(self.settings, key, value)

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
                    continue

                # Parse the command
                cmd_type = data.get("type")
                try:
                    if cmd_type is None:
                        await self.report_command_problem(
                            message=f"Invalid command; no 'type' field: {data!r}",
                            severity=MessageSeverityEnum.WARNING,
                        )
                        continue
                    command = SimpleNamespace(**data)
                    if self.verbose:
                        msg_summary = str(command)
                        if command.type == "upload" and len(msg_summary) > MAX_LOG_PATTERN_LEN:
                            msg_summary = msg_summary[0:MAX_LOG_PATTERN_LEN] + "..."
                        self.log.info(f"{self}: read command {msg_summary}")
                    cmd_handler = getattr(self, f"cmd_{cmd_type}", None)
                except Exception as e:
                    message = f"command {data} failed: {e!r}"
                    self.log.exception(f"{self}: {message}")
                    await self.report_command_done(cmd_type=cmd_type, success=False, message=message)
                    continue

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
                    await self.report_command_done(cmd_type=cmd_type, success=False, message=str(e))
                except Exception as e:
                    message = f"command {command} unexpectedly failed: {e!r}"
                    self.log.exception(f"{self}: {message}")
                    await self.report_command_done(cmd_type=cmd_type, success=False, message=message)

        except asyncio.CancelledError:
            return
        except WebSocketDisconnect:
            self.log.info(f"{self}: client disconnected")
            return
        except Exception as e:
            self.log.exception(f"{self}: bug: client read looop failed")
            await self.report_command_problem(
                message="Client read loop failed; try refreshing",
                severity=MessageSeverityEnum.ERROR,
            )
            self.client_connected = False
            if self.websocket is not None:
                await self.close_websocket(self.websocket, code=CloseCode.ERROR, reason=repr(e))

    async def read_loom_loop(self) -> None:
        """Read and process replies from the loom."""
        try:
            if self.loom_reader is None:
                raise RuntimeError("No loom reader")  # noqa: TRY301
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

    async def report_command_done(self, *, cmd_type: str, success: bool, message: str = "") -> None:
        """Report completion of a command."""
        reply = client_replies.CommandDone(cmd_type=cmd_type, success=success, message=message)
        await self.write_to_client(reply)

    async def report_command_problem(self, message: str, severity: MessageSeverityEnum) -> None:
        """Report a CommandProblem to the client."""
        reply = client_replies.CommandProblem(message=message, severity=severity)
        await self.write_to_client(reply)

    async def report_current_pattern(self) -> None:
        """Report pattern to the client."""
        if self.current_pattern is not None:
            await self.write_to_client(self.current_pattern)

    async def report_initial_server_state(self) -> None:
        """Report server state.

        Called just after a client connects to the server.
        """
        await self.report_loom_connection_state()
        await self.write_to_client(self.loom_info)
        await self.report_language_names()
        await self.report_settings()
        await self.report_mode()
        await self.report_pattern_names()
        await self.report_direction()
        await self.clear_jumps(force_output=True)
        await self.report_current_pattern()
        await self.report_current_end_numbers()
        await self.report_current_pick_number()
        await self.report_separate_threading_repeats()
        await self.report_separate_weaving_repeats()
        await self.report_shaft_state()
        await self.report_thread_group_size()

    async def report_loom_connection_state(self, reason: str = "") -> None:
        """Report LoomConnectionState to the client."""
        if self.loom_connecting:
            state = ConnectionStateEnum.CONNECTING
        elif self.loom_disconnecting:
            state = ConnectionStateEnum.DISCONNECTING
        elif self.loom_connected:
            state = ConnectionStateEnum.CONNECTED
        else:
            state = ConnectionStateEnum.DISCONNECTED
        reply = client_replies.LoomConnectionState(state=state, reason=reason)
        await self.write_to_client(reply)

    async def report_pattern_names(self) -> None:
        """Report PatternNames to the client."""
        names = await self.pattern_db.get_pattern_names()
        reply = client_replies.PatternNames(names=names)
        await self.write_to_client(reply)

    async def report_current_pick_number(self) -> None:
        """Report CurrentPickNumber to the client.

        Also update pick information in the database.
        """
        if self.current_pattern is None:
            return
        await self.pattern_db.update_pick_number(
            pattern_name=self.current_pattern.name,
            pick_number=self.current_pattern.pick_number,
            pick_repeat_number=self.current_pattern.pick_repeat_number,
        )
        reply = client_replies.CurrentPickNumber(
            total_pick_number=compute_total_num(
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
            client_replies.ShaftState(state=self.shaft_state, shaft_word=self.shaft_word)
        )

    async def report_mode(self) -> None:
        """Report the current mode to the client."""
        await self.write_to_client(client_replies.Mode(mode=self.mode))

    async def report_separate_threading_repeats(self) -> None:
        """Report SeparateThreadingRepeats."""
        if self.current_pattern is None:
            return
        await self.write_to_client(
            client_replies.SeparateThreadingRepeats(separate=self.current_pattern.separate_threading_repeats)
        )

    async def report_separate_weaving_repeats(self) -> None:
        """Report SeparateWeavingRepeats."""
        if self.current_pattern is None:
            return
        await self.write_to_client(
            client_replies.SeparateWeavingRepeats(separate=self.current_pattern.separate_weaving_repeats)
        )

    async def report_settings(self) -> None:
        """Report Settings."""
        await self.write_to_client(self.settings)

    async def report_status_message(self, message: str, severity: MessageSeverityEnum) -> None:
        """Report a status message to the client."""
        await self.write_to_client(client_replies.StatusMessage(message=message, severity=severity))

    async def report_thread_group_size(self) -> None:
        """Report ThreadGroupSize."""
        if self.current_pattern is None:
            return
        client_reply = client_replies.ThreadGroupSize(group_size=self.current_pattern.thread_group_size)
        await self.write_to_client(client_reply)

    async def report_language_names(self) -> None:
        """Report LanguageNames."""
        client_reply = client_replies.LanguageNames(languages=get_language_names())
        await self.write_to_client(client_reply)

    async def report_direction(self) -> None:
        """Report Direction."""
        await self.write_to_client(
            client_replies.Direction(
                forward=self.direction_forward,
            )
        )

    def reset_database(self) -> None:
        """Reset the pattern database (write a new one)."""
        self.db_path.unlink(missing_ok=True)
        self.pattern_db = PatternDatabase(self.db_path)

    def save_settings(self) -> None:
        """Save the settings file."""
        datadict = dataclasses.asdict(self.settings)
        del datadict["type"]
        try:
            with self.settings_path.open("w", encoding="utf_8") as f:
                json.dump(datadict, f)
        except Exception as e:
            self.log.error(f"Could not write settings file {self.settings_path}: {e!r}")

    async def select_pattern(self, name: str) -> None:
        """Select the specified pattern."""
        try:
            pattern = await self.pattern_db.get_pattern(name)
        except LookupError:
            raise CommandError(f"select_pattern failed: no such pattern: {name}") from None
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

    # Use reply: Any because dataclasses are hard to type hint
    async def write_to_client(self, reply: Any) -> None:  # noqa: ANN401
        """Send a reply to the client.

        Args:
            reply: The reply to write, as a dataclass. It should have
                a "type" field whose value is a string.
        """
        reply_dict = dataclasses.asdict(reply)
        if self.verbose:
            reply_str = str(reply_dict)
            if reply.type == "ReducedPattern" and len(reply_str) > MAX_LOG_PATTERN_LEN:
                reply_str = reply_str[0:MAX_LOG_PATTERN_LEN] + "..."
        else:
            reply_str = ""

        if self.client_connected:
            assert self.websocket is not None  # make mypy happy
            if self.verbose:
                self.log.info(f"{self}: reply to client: {reply_str}")
            await self.websocket.send_json(reply_dict)
        elif self.verbose:
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
            self.log.info(f"{self}: sending command to loom: {data_bytes + self.terminator!r}")
        self.loom_writer.write(data_bytes + self.terminator)
        await self.loom_writer.drain()

    def __repr__(self) -> str:
        return type(self).__name__

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
