import asyncio

import pytest

from base_loom_server import mock_streams

TEST_BYTES = (
    b"one line",
    b"another line",
    b" \t \ta line with leading whitespace and an embedded null \0",
)

TEST_TERMATORS = (b"\r", b"\n", b"\r\n")


def data_iterator(terminator: bytes):
    for data in TEST_BYTES:
        yield data + terminator


async def test_open_mock_connection() -> None:
    """Test the linkage in the streams from open_mock_connection"""
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

    for terminator in TEST_TERMATORS:
        writer = mock_streams.MockStreamWriter(terminator=terminator)
        reader = writer.create_reader()
        await check_reader_writer(reader, writer)


async def test_writer_from_reader() -> None:
    reader = mock_streams.MockStreamReader()
    writer = reader.create_writer()
    await check_reader_writer(reader, writer)

    for terminator in TEST_TERMATORS:
        reader = mock_streams.MockStreamReader(terminator=terminator)
        writer = reader.create_writer()
        await check_reader_writer(reader, writer)


async def test_mismatched_terminator() -> None:
    data = b"test data"
    for terminator in TEST_TERMATORS:
        for other_terminator in TEST_TERMATORS:
            writer = mock_streams.MockStreamWriter(terminator=terminator)
            reader = writer.create_reader()
            if other_terminator.endswith(terminator):
                # Allowed
                writer.write(data + other_terminator)
                reply = await reader.readline()
                assert reply == data + other_terminator
            else:
                with pytest.raises(AssertionError):
                    writer.write(data + other_terminator)

            writer.write(data + terminator)
            if other_terminator in terminator:
                # Allowed
                writer.write(data + terminator)
                reply = await reader.readuntil(other_terminator)
                assert reply == data + terminator
            else:
                with pytest.raises(AssertionError):
                    await reader.readuntil(other_terminator)


async def check_reader_writer(
    reader: mock_streams.MockStreamReader, writer: mock_streams.MockStreamWriter
):
    """Check a reader and the writer that writes to it.

    Note that this is not the pair returned by `open_mock_connection`,
    but rather the reader obtained from writer.create_reader or vice-versa.
    """
    assert reader.terminator == writer.terminator
    data_list = list(data_iterator(terminator=reader.terminator))
    assert not reader.at_eof()
    assert not writer.is_closing()
    assert len(reader.sd.queue) == 0

    # Alternate between appendline and until
    for data in data_list:
        writer.write(data)
        assert len(reader.sd.queue) == 1
        read_data = await reader.readuntil(reader.terminator)
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
        read_data = await reader.readuntil(reader.terminator)
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
    """Await writer.wait_closed() and wait_done=True when seen"""

    def __init__(self, writer: mock_streams.MockStreamWriter) -> None:
        self.writer = writer
        self.wait_done = False
        self.wait_task = asyncio.create_task(self.do_wait_closed())

    async def do_wait_closed(self) -> None:
        await self.writer.wait_closed()
        self.wait_done = True
