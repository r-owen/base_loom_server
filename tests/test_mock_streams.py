import asyncio
from collections.abc import Generator

import pytest

from base_loom_server import mock_streams

TEST_BYTES = (
    b"one line",
    b"another line",
    b" \t \ta line with leading whitespace and an embedded null \0",
)

TEST_TERMINATORS = (b"", b"\r", b"\n", b"\r\n")


def data_iterator(terminator: bytes) -> Generator[bytes]:
    for data in TEST_BYTES:
        yield data + terminator


async def test_open_mock_connection() -> None:
    """Test the linkage in the streams from open_mock_connection."""
    reader_a, writer_b = mock_streams.open_mock_connection()
    assert reader_a.sibling_sd is None
    assert writer_b.sibling_sd is not None
    assert not reader_a.at_eof()
    assert not writer_b.is_closing()

    writer_b.close()
    assert reader_a.at_eof()
    assert writer_b.is_closing()


async def test_reader_from_writer() -> None:
    writer = mock_streams.MockStreamWriter()
    reader = writer.create_reader()
    await check_reader_writer(reader, writer)

    for terminator in TEST_TERMINATORS:
        writer = mock_streams.MockStreamWriter(terminator=terminator)
        reader = writer.create_reader()
        await check_reader_writer(reader, writer)


async def test_writer_from_reader() -> None:
    reader = mock_streams.MockStreamReader()
    writer = reader.create_writer()
    await check_reader_writer(reader, writer)

    for terminator in TEST_TERMINATORS:
        reader = mock_streams.MockStreamReader(terminator=terminator)
        writer = reader.create_writer()
        await check_reader_writer(reader, writer)


async def test_mismatched_terminator() -> None:
    data = b"test data"
    for terminator in TEST_TERMINATORS:
        for other_terminator in TEST_TERMINATORS:
            writer = mock_streams.MockStreamWriter(terminator=terminator)
            reader = writer.create_reader()

            # When the terminator is not empty,
            # data written must end with the terminator
            write_data = data + other_terminator
            if terminator != b"" and not other_terminator.endswith(terminator):
                with pytest.raises(AssertionError):
                    writer.write(write_data)
            else:
                # Allowed
                writer.write(write_data)
                if reader.terminator != b"":
                    reply = await reader.readline()
                else:
                    reply = await reader.readexactly(len(write_data))
                assert reply == write_data

            write_data = data + terminator
            writer.write(write_data)
            if other_terminator == b"":
                reply = await reader.readexactly(len(write_data))
                assert reply == data + terminator
            elif other_terminator in terminator:
                reply = await reader.readuntil(other_terminator)
                assert reply == data + terminator
            else:
                with pytest.raises(AssertionError):
                    await reader.readuntil(other_terminator)


async def test_invalid_operations() -> None:
    """Test read and write methods that should fail."""
    for terminator in TEST_TERMINATORS:
        writer = mock_streams.MockStreamWriter(terminator=terminator)
        reader = writer.create_reader()

        # readuntil requires a non-empty terminator
        with pytest.raises(AssertionError):
            await reader.readuntil(b"")

        for offset in (-2, -1, 1, 2):
            write_data = b"some data" + terminator
            writer.write(write_data)
            await writer.drain()
            if offset > 0:
                # reading too little data
                with pytest.raises(asyncio.IncompleteReadError):
                    await reader.readexactly(len(write_data) + offset)
            else:
                # reading too much data
                with pytest.raises(AssertionError):
                    await reader.readexactly(len(write_data) + offset)
        if terminator == b"":
            # readline requires a non-empty terminator
            with pytest.raises(AssertionError):
                await reader.readline()
        else:
            # if the writer has a non-empty terminator
            # then the data sent must be correctly terminated
            incorrectly_terminated_data = b"some data"
            with pytest.raises(AssertionError):
                writer.write(incorrectly_terminated_data)


async def check_reader_writer(
    reader: mock_streams.MockStreamReader, writer: mock_streams.MockStreamWriter
) -> None:
    """Check a reader and the writer that writes to it.

    Note that this is not the pair returned by `open_mock_connection`,
    but rather the reader obtained from writer.create_reader or vice-versa.
    """
    assert reader.terminator == writer.terminator
    is_terminated = reader.terminator != b""
    data_list = list(data_iterator(terminator=reader.terminator))
    assert not reader.at_eof()
    assert not writer.is_closing()
    assert len(reader.sd.queue) == 0

    # Alternate between writing and reading with readuntil
    for data in data_list:
        writer.write(data)
        assert len(reader.sd.queue) == 1
        if is_terminated:
            read_data = await reader.readuntil(reader.terminator)
        else:
            read_data = await reader.readexactly(len(data))
        assert read_data == data
        assert not reader.at_eof()
        assert not writer.is_closing()
        assert len(reader.sd.queue) == 0

    # Queue up a batch of writes,
    # then close the writer,
    # then read all of them with readline
    for data in data_list:
        writer.write(data)
    await writer.drain()
    assert len(reader.sd.queue) == len(data_list)
    for i, data in enumerate(data_list):
        assert reader.sd.queue[i] == data

    writer.close()
    assert not reader.at_eof()
    assert writer.is_closing()
    for i, data in enumerate(data_list):
        is_last_read = i + 1 == len(data_list)
        if is_terminated:
            read_data = await reader.readline()
        else:
            read_data = await reader.readexactly(len(data))
        assert read_data == data
        if is_last_read:
            assert reader.at_eof()
        else:
            assert not reader.at_eof()
        assert writer.is_closing()
    assert len(reader.sd.queue) == 0

    # further writing should be a no-op
    writer.write(data_list[0])
    await writer.drain()
    assert len(writer.sd.queue) == 0


class StreamClosedWatcher:
    """Await writer.wait_closed() and wait_done=True when seen."""

    def __init__(self, writer: mock_streams.MockStreamWriter) -> None:
        self.writer = writer
        self.wait_done = False
        self.wait_task = asyncio.create_task(self.do_wait_closed())

    async def do_wait_closed(self) -> None:
        """Wait for the writer to close and set self.wait_done True."""
        await self.writer.wait_closed()
        self.wait_done = True
