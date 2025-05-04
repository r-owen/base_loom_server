__all__ = ["ExampleLoomServer"]

from .base_loom_server import BaseLoomServer
from .client_replies import MessageSeverityEnum, ShaftStateEnum
from .example_mock_loom import ExampleMockLoom


class ExampleLoomServer(BaseLoomServer):
    """Example loom server.

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
    """

    default_name = "example"
    mock_loom_type = ExampleMockLoom

    async def write_shafts_to_loom(self, shaft_word: int) -> None:
        """Send a shaft_word to the loom"""
        await self.write_to_loom(f"C{shaft_word:08x}")

    async def handle_loom_reply(self, reply_bytes: bytes) -> None:
        """Process one reply from the loom."""
        reply = reply_bytes.decode().strip()
        if not reply:
            return
        reply_char = reply[0]
        reply_data = reply[1:]
        match reply_char:
            case "c":
                # Shafts that are up
                self.shaft_word = int(reply_data, base=16)
                await self.report_shaft_state()
            case "m":
                # Loom moving
                self.moving = reply_data == "1"
                self.shaft_state = (
                    ShaftStateEnum.MOVING if reply_data == "1" else ShaftStateEnum.DONE
                )
                await self.report_shaft_state()
            case "p":
                # Next pick wanted
                await self.handle_next_pick_request()
            case "u":
                # Weave direction
                # The loom expects a new pick, as a result
                if reply_data == "0":
                    self.weave_forward = True
                elif reply_data == "1":
                    self.weave_forward = False
                else:
                    message = (
                        f"invalid loom reply {reply!r}: " "direction must be 0 or 1"
                    )
                    self.log.warning(f"LoomServer: {message}")
                    await self.report_command_problem(
                        message=message, severity=MessageSeverityEnum.WARNING
                    )
                    return
                await self.report_weave_direction()
