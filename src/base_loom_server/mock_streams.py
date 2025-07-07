from __future__ import annotations

__all__ = [
    "MockStreamReader",
    "MockStreamWriter",
    "open_mock_connection",
    "StreamReaderType",
    "StreamWriterType",
]

import asyncio
import collections
import weakref
from typing import TypeAlias

DEFAULT_TERMINATOR = b"\n"


class StreamData:
    """Data contained in a mock stream.

    Contains a queue of data and asyncio events to track data available
    and stream closing.
    """

    def __init__(self) -> None:
        self.closed_event = asyncio.Event()
        self.data_available_event = asyncio.Event()
        self.queue: collections.deque[bytes] = collections.deque()

    def is_closed(self) -> bool:
        """Return true if this stream has been closed."""
        return self.closed_event.is_set()


class BaseMockStream:
    """Base class for MockStreamReader and MockStreamWriter.

    Args:
        sd: Stream data to use; if None create new.
        terminator: Required terminator.
    """

    def __init__(self, sd: StreamData | None = None, terminator: bytes = DEFAULT_TERMINATOR) -> None:
        if sd is None:
            sd = StreamData()
        self.sd = sd
        self.terminator = terminator
        self.sibling_sd: weakref.ProxyType[StreamData] | None = None


class MockStreamReader(BaseMockStream):
    """Minimal mock stream reader that only supports line-oriented data
    and fixed-length unterminated messages.

    Intended to be created in one of two ways:

    * `open_mock_connection` to create a reader and writer that are linked
      in that closing the writer also closes the reader.
    * `MockStreamWriter.create_reader` to create a reader that reads from
       the writer.

    Args:
        sd: Stream data to use; if None create new.
        terminator: Required terminator. Calls to `readuntil` will raise
            `AssertionError` if the separator is not in the terminator.
    """

    def at_eof(self) -> bool:
        """Return true if closed and all buffered data has been read."""
        return not self.sd.queue and self.sd.is_closed()

    async def readexactly(self, n: int) -> bytes:
        """Read exactly n bytes (including a terminator, if any).

        Unlike `asyncio.StreamReader`, this assumes
        the message will be exactly n bytes long,
        and the terminator is checked if self.terminator != b"".

        Raises:
            AssertionError: If the message is too long.
            asyncio.IncompleteReadError: If the message is too short.
            AssertionError: If self.terminator is not blank and the message
                is not terminated with self.terminator.
        """
        while not self.sd.queue:
            if self.sd.is_closed():
                return b""
            self.sd.data_available_event.clear()
            await self.sd.data_available_event.wait()
        data = self.sd.queue.popleft()
        if not self.sd.queue:
            self.sd.data_available_event.clear()
        if len(data) != n:
            if len(data) < n:
                raise asyncio.IncompleteReadError(expected=n, partial=data)
            raise AssertionError(f"Read len({data=})={len(data)} > {n=}")
        if self.terminator and not data.endswith(self.terminator):
            raise AssertionError(f"Data {data=} does not end with {self.terminator=!r}")
        return data

    async def readline(self) -> bytes:
        """Read one line of data ending with self.terminator.

        Raises:
            AssertionError: If self.terminator is blank.
        """
        if not self.terminator:
            raise AssertionError("readline not allowed: self.terminator is blank")
        while not self.sd.queue:
            if self.sd.is_closed():
                return b""
            self.sd.data_available_event.clear()
            await self.sd.data_available_event.wait()
        data = self.sd.queue.popleft()
        if not self.sd.queue:
            self.sd.data_available_event.clear()
        return data

    async def readuntil(self, separator: bytes = b"\n") -> bytes:
        """Read until the specified value.

        Raises:
            AssertionError: If `separator` is blank.
            AssertionError: If `separator` not in self.terminator.
        """
        if separator == b"":
            raise AssertionError("readuntil must have a non-blank separator")
        if separator not in self.terminator:
            raise AssertionError(f"readuntil {separator=} not in required terminator {self.terminator!r}")

        return await self.readline()

    def create_writer(self) -> MockStreamWriter:
        """Create a MockStreamWriter that writes to this reader."""
        return MockStreamWriter(sd=self.sd, terminator=self.terminator)


class MockStreamWriter(BaseMockStream):
    """Minimal mock stream writer that only allows writing terminated data.

    Intended to be created in one of two ways:

    * `open_mock_connection` to create a reader and writer that are linked
      in that closing the writer also closes the reader.
    * `MockStreamReader.create_writer` to create a writer that writes to
       the reader.

    Args:
        sd: Stream data to use; if None create new.
        terminator: Required terminator. Calls to `write` with data that is not
            correctly terminated will raise `AssertionError`.
    """

    def close(self) -> None:
        """Close the writer."""
        self.sd.closed_event.set()
        if self.sibling_sd and not self.sibling_sd.is_closed():
            self.sibling_sd.closed_event.set()

    def is_closing(self) -> bool:
        """Return true if the writer is closed or being closed."""
        return self.sd.is_closed()

    async def drain(self) -> None:
        """Push the current data to the reader."""
        if self.is_closing():
            return
        self.sd.data_available_event.set()

    async def wait_closed(self) -> None:
        """Wait for closing to finish. A no-op if closed."""
        await self.sd.closed_event.wait()

    def write(self, data: bytes) -> None:
        """Write the specified data.

        Raises:
            AssertionError: If self.terminator is not empty
                and `data` is not properly terminated.
        """
        if self.terminator and not data.endswith(self.terminator):
            raise AssertionError(f"Cannot write {data=}: it must end with {self.terminator=!r}")
        if self.is_closing():
            return
        self.sd.queue.append(data)

    def _set_sibling_data(self, reader: MockStreamReader) -> None:
        self.sibling_sd = weakref.proxy(reader.sd)

    def create_reader(self) -> MockStreamReader:
        """Create a MockStreamReader that reads from this writer."""
        return MockStreamReader(sd=self.sd, terminator=self.terminator)


StreamReaderType: TypeAlias = asyncio.StreamReader | MockStreamReader
StreamWriterType: TypeAlias = asyncio.StreamWriter | MockStreamWriter


def open_mock_connection(
    terminator: bytes = DEFAULT_TERMINATOR,
) -> tuple[MockStreamReader, MockStreamWriter]:
    """Create a mock stream reader, writer pair.

    To create a stream that writes to the returned reader,
    call reader.create_writer, and similarly for the returned writer.
    """
    reader = MockStreamReader(terminator=terminator)
    writer = MockStreamWriter(terminator=terminator)
    writer._set_sibling_data(reader=reader)  # noqa: SLF001
    return (reader, writer)
