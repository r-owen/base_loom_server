from __future__ import annotations

__all__ = ["BaseMockLoom"]

import abc
import asyncio
import logging
import threading
from types import TracebackType
from typing import Type

from .constants import LOG_NAME
from .mock_streams import (
    MockStreamReader,
    MockStreamWriter,
    StreamReaderType,
    StreamWriterType,
    open_mock_connection,
)

DIRECTION_NAMES = {True: "weave", False: "unweave"}


class BaseMockLoom(abc.ABC):
    """Base class for a dobby loom similator.

    Parameters
    ----------
    verbose : bool
        If True, log diagnostic information.

    Notes
    -----
    The user controls a mock loom by:

    * Call reader.create_writer() to create a command writer.
    * Call writer.create_reader() to create a reply reader.
    * Read replies from the reply reader.
    * Write commands to the command writer.
    """

    terminator = b"\n"
    motion_duration: float = 1  # seconds

    def __init__(self, verbose: bool = True) -> None:
        self.log = logging.getLogger(LOG_NAME)
        self.verbose = verbose
        self.moving = False
        self.pick_wanted = False
        self.shaft_word = 0
        self.weave_forward = True
        self.writer: StreamWriterType | None = None
        self.reader: StreamReaderType | None = None
        self.done_task: asyncio.Future = asyncio.Future()
        self.move_task: asyncio.Future = asyncio.Future()
        self.read_loop_task: asyncio.Future = asyncio.Future()
        self.start_task = asyncio.create_task(self.start())

        # This event is set whenever a command is received.
        # It is solely intended for tests, and is used as follows:
        # * Clear the event
        # * Send a command to the loom
        # * Wait for the event before checking loom state
        # It is needed for testing looms that do not output
        # state information, such as Toika ES.
        self.command_event = asyncio.Event()

        # A threading version for use with fastapi.testclient.TestClient
        # which is, alas, synchronous.
        self.command_threading_event = threading.Event()

    async def start(self) -> None:
        self.reader, self.writer = open_mock_connection(terminator=self.terminator)
        self.read_loop_task = asyncio.create_task(self.read_loop())

    async def close(self, cancel_read_loop=True) -> None:
        self.start_task.cancel()
        if cancel_read_loop:
            self.read_loop_task.cancel()
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        if not self.done_task.done():
            self.done_task.set_result(None)

    @abc.abstractmethod
    async def handle_read_bytes(self, read_bytes: bytes) -> None:
        """Handle one command from the web server."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def report_direction(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def report_motion_state(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def report_pick_wanted(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def report_shafts(self) -> None:
        raise NotImplementedError

    async def basic_read(self) -> bytes:
        """Read one command to the loom.

        Perform no error checking, except that self.reader exists.
        """
        assert self.reader is not None  # make mypy happy
        return await self.reader.readuntil(self.terminator)

    async def oob_command(self, cmd: str):
        """Run an oob_command, specified by cmd[0]"""
        if not cmd:
            return
        cmdchar = cmd[0]
        method = getattr(self, f"oob_command_{cmdchar}", None)
        if method is None:
            self.log.warning(f"{self}: unrecognized oob command: {cmd!r}")
            return
        await method(cmd)

    async def oob_command_c(self, cmd: str):
        """Close the connection"""
        if self.verbose:
            self.log.info(f"{self}: oob close command")

        asyncio.create_task(self.close())

    async def oob_command_d(self, cmd: str):
        """Toggle weave direction"""
        self.weave_forward = not self.weave_forward
        await self.report_direction()
        if self.verbose:
            self.log.info(
                f"{self}: oob toggle weave direction to: "
                f"{DIRECTION_NAMES[self.weave_forward]}"
            )

    async def oob_command_n(self, cmd: str):
        """Request next pick"""
        if self.verbose:
            self.log.info(f"{self}: oob request next pick")
        self.pick_wanted = True
        await self.report_pick_wanted()

    async def open_client_connection(self) -> tuple[StreamReaderType, StreamWriterType]:
        await self.start_task
        assert self.writer is not None
        assert self.reader is not None
        # The isinstance tests make mypy happy, and might catch
        # a future bug if I figure out how to use virtual serial ports.
        if isinstance(self.writer, MockStreamWriter) and isinstance(
            self.reader, MockStreamReader
        ):
            await self.report_initial_status()
            return (
                self.writer.create_reader(),
                self.reader.create_writer(),
            )
        else:
            raise RuntimeError(
                f"Bug: {self.reader=} and {self.writer=} must both be mock streams"
            )

    def connected(self) -> bool:
        return (
            self.reader is not None
            and self.writer is not None
            and not self.reader.at_eof()
            and not self.writer.is_closing()
        )

    async def move(self, shaft_word: int) -> None:
        self.moving = True
        await self.report_motion_state()
        await asyncio.sleep(self.motion_duration)
        self.moving = False
        self.shaft_word = shaft_word
        await self.report_shafts()
        await self.report_motion_state()

    async def read_loop(self) -> None:
        """Read commands from the loom server."""
        try:
            while self.connected():
                assert self.reader is not None  # make mypy happy
                cmd_bytes = await self.basic_read()
                if not cmd_bytes:
                    # Connection has closed
                    break
                self.command_event.set()
                self.command_threading_event.set()
                await self.handle_read_bytes(cmd_bytes)

        except Exception:
            self.log.exception(f"{self}: read_loop failed; giving up")
            await self.close(cancel_read_loop=False)

    async def report_initial_status(self) -> None:
        """Report initial status."""
        await self.report_direction()
        await self.report_motion_state()
        await self.report_pick_wanted()

    async def set_shaft_word(self, shaft_word: int) -> None:
        """Set shafts to raise"""
        # Ignore the command unless a pick is wanted
        if not self.pick_wanted:
            return
        self.pick_wanted = False
        await self.report_pick_wanted()
        self.move_task.cancel()
        if self.verbose:
            self.log.info(f"{self}: raise shafts {self.shaft_word:08x}")
        self.move_task = asyncio.create_task(self.move(shaft_word=shaft_word))

    async def set_weave_forward(self, weave_forward: bool) -> None:
        self.weave_forward = bool(weave_forward)
        if self.verbose:
            self.log.info(f"{self}: set {weave_forward=} by software")
        await self.report_direction()

    async def write(self, data: bytes | bytearray | str) -> None:
        """Issue the specified data, which should not be terminated"""
        if self.verbose:
            self.log.info(f"{self}: send reply {data!r}")
        if self.connected():
            data_bytes: bytes = data.encode() if isinstance(data, str) else bytes(data)
            assert self.writer is not None
            self.writer.write(data_bytes + self.terminator)
            await self.writer.drain()

    def __repr__(self) -> str:
        return type(self).__name__

    async def __aenter__(self) -> BaseMockLoom:
        await self.start()
        return self

    async def __aexit__(
        self,
        type: Type[BaseException] | None,
        value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()
