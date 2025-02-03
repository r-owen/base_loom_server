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
from typing import Deque, TypeAlias

DEFAULT_TERMINATOR = b"\n"


class StreamData:
    """Data contained in a mock stream."""

    def __init__(self) -> None:
        self.closed_event = asyncio.Event()
        self.data_available_event = asyncio.Event()
        self.queue: Deque[bytes] = collections.deque()

    def _is_closed(self):
        """Return true if this stream has been closed."""
        return self.closed_event.is_set()


class BaseMockStream:
    """Base class for MockStreamReader and MockStreamWriter.

    Parameters
    ----------
    sd : StreamData
        Stream data to use; if None create new.
    terminator : bytes
        Required terminator.
    """

    def __init__(
        self, sd: StreamData | None = None, terminator: bytes = DEFAULT_TERMINATOR
    ):
        if sd is None:
            sd = StreamData()
        self.sd = sd
        self.terminator = terminator
        self.sibling_sd: weakref.ProxyType[StreamData] | None = None


class MockStreamReader(BaseMockStream):
    """Minimal mock stream reader that only supports line-oriented data.

    Parameters
    ----------
    sd : StreamData
        Stream data to use; if None create new.
    terminator : bytes
        Required terminator. Calls to `readuntil` will raise
        AssertionError if the separator is not in the terminator.

    Intended to be created using `open_mock_connection` for pair of streams,
    or `create_writer` to create a writer that will write to this reader.
    """

    def at_eof(self) -> bool:
        return not self.sd.queue and self.sd._is_closed()

    async def readline(self) -> bytes:
        while not self.sd.queue:
            if self.sd._is_closed():
                return b""
            self.sd.data_available_event.clear()
            await self.sd.data_available_event.wait()
        data = self.sd.queue.popleft()
        if not self.sd.queue:
            self.sd.data_available_event.clear()
        return data

    async def readuntil(self, separator: bytes = b"\n") -> bytes:
        if separator not in self.terminator:
            raise AssertionError(
                f"readuntil {separator=} not in required terminator {self.terminator!r}"
            )

        return await self.readline()

    def create_writer(self) -> MockStreamWriter:
        return MockStreamWriter(sd=self.sd, terminator=self.terminator)


class MockStreamWriter(BaseMockStream):
    """Minimal mock stream writer that only allows writing terminated data.

    Parameters
    ----------
    sd : StreamData
        Stream data to use; if None create new.
    terminator : bytes
        Required terminator. Calls to `write` with data that is not
        correctly terminated will raise AssertionError.

    Intended to be created `open_mock_connection` for a new pair,
    or `create_reader` to create a reader that will read from this writer.
    """

    def close(self) -> None:
        self.sd.closed_event.set()
        if self.sibling_sd and not self.sibling_sd._is_closed():
            self.sibling_sd.closed_event.set()

    def is_closing(self) -> bool:
        return self.sd._is_closed()

    async def drain(self) -> None:
        if self.is_closing():
            return
        self.sd.data_available_event.set()

    async def wait_closed(self) -> None:
        await self.sd.closed_event.wait()

    def write(self, data: bytes) -> None:
        if not data.endswith(self.terminator):
            raise AssertionError(
                f"Cannot write {data=}: it must end with {self.terminator!r}"
            )
        if self.is_closing():
            return
        self.sd.queue.append(data)

    def _set_sibling_data(self, reader: MockStreamReader) -> None:
        self.sibling_sd = weakref.proxy(reader.sd)

    def create_reader(self) -> MockStreamReader:
        return MockStreamReader(sd=self.sd, terminator=self.terminator)


StreamReaderType: TypeAlias = asyncio.StreamReader | MockStreamReader
StreamWriterType: TypeAlias = asyncio.StreamWriter | MockStreamWriter


def open_mock_connection(
    terminator=DEFAULT_TERMINATOR,
) -> tuple[MockStreamReader, MockStreamWriter]:
    """Create a mock stream reader, writer pair.

    To create a stream that writes to the returned reader,
    call reader.create_writer, and similarly for the returned writer.
    """
    reader = MockStreamReader(terminator=terminator)
    writer = MockStreamWriter(terminator=terminator)
    writer._set_sibling_data(reader=reader)
    return (reader, writer)
