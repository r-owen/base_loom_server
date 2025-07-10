import asyncio
import contextlib
from collections.abc import AsyncIterator

from base_loom_server.example_mock_loom import ExampleMockLoom
from base_loom_server.mock_streams import StreamReaderType, StreamWriterType

# speed up tests
ExampleMockLoom.motion_duration = 0.1


@contextlib.asynccontextmanager
async def create_loom(
    num_shafts: int = 16,
) -> AsyncIterator[tuple[ExampleMockLoom, StreamReaderType, StreamWriterType]]:
    """Create an ExampleMockLoom."""
    async with ExampleMockLoom(num_shafts=num_shafts, verbose=True) as loom:
        reader, writer = await loom.open_client_connection()
        for expected_value in ("u0", "m0"):
            reply = await read_reply(reader)
            assert reply == expected_value
        yield loom, reader, writer


async def read_reply(reader: StreamReaderType, timeout: float = 1) -> str:
    async with asyncio.timeout(timeout):
        reply_bytes = await reader.readuntil(ExampleMockLoom.terminator)
        assert reply_bytes[-1:] == ExampleMockLoom.terminator
        return reply_bytes[:-1].decode()


async def write_command(writer: StreamWriterType, command: str, timeout: float = 1) -> None:
    writer.write(command.encode() + ExampleMockLoom.terminator)
    async with asyncio.timeout(timeout):
        await writer.drain()


async def test_raise_shafts() -> None:
    async with create_loom() as (loom, reader, writer):
        for shaft_word in (0x0, 0x1, 0x5, 0xFE, 0xFF19, 0xFFFFFFFE, 0xFFFFFFFF):
            # Tell mock loom to request the next pick
            await loom.oob_command("n")
            reply = await read_reply(reader)
            assert reply == "p"
            # Send the requested shaft information
            loom.command_event.clear()
            await write_command(writer, f"C{shaft_word:08x}")
            for expected_reply in ("m1", f"c{shaft_word:08x}", "m0"):
                reply = await read_reply(reader)
                assert reply == expected_reply
            assert loom.shaft_word == shaft_word
        assert not loom.done_task.done()


async def test_oob_next_pick_and_toggle_direction() -> None:
    async with create_loom() as (loom, reader, writer):
        for expected_direction in (1, 0, 1, 0, 1):
            await loom.oob_command("d")
            reply = await read_reply(reader)
            assert reply == f"u{expected_direction}"
        assert not loom.done_task.done()


async def test_oob_close_connection() -> None:
    async with create_loom() as (loom, reader, writer):
        await loom.oob_command("c")
        async with asyncio.timeout(1):
            await loom.done_task
        assert loom.writer is not None
        assert loom.writer.is_closing()
        assert loom.reader is not None
        assert loom.reader.at_eof()
