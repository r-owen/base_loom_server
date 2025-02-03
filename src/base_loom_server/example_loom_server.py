from __future__ import annotations

__all__ = ["BaseLoomServer"]

import pathlib

from .base_loom_server import BaseLoomServer
from .client_replies import MessageSeverityEnum, ShaftStateEnum
from .example_mock_loom import ExampleMockLoom
from .reduced_pattern import Pick


class CommandError(Exception):
    pass


class ExampleLoomServer(BaseLoomServer):
    """Example loom server.

    The preferred way to create and run this is to call
    the amain method.

    Parameters
    ----------
    mock_loom_type : Type[BaseMockLoom]
        Base mock loom class
    serial_port : str
        The name of the serial port, e.g. "/dev/tty0".
        If the name is "mock" then use a mock loom.
    translation_dict : dict[str, str]
        Translation dict.
    reset_db : bool
        If True, delete the old database and create a new one.
        A rescue aid, in case the database gets corrupted.
    verbose : bool
        If True, log diagnostic information.
    name : str
        User-assigned loom name.
    db_path : pathlib.Path | None
        Path to pattern database.
        Intended for unit tests, to avoid stomping on the real database.
    """

    def __init__(
        self,
        serial_port: str,
        translation_dict: dict[str, str],
        reset_db: bool,
        verbose: bool,
        name: str = "example",
        db_path: pathlib.Path | None = None,
    ) -> None:
        super().__init__(
            mock_loom_type=ExampleMockLoom,
            serial_port=serial_port,
            translation_dict=translation_dict,
            reset_db=reset_db,
            verbose=verbose,
            name=name,
            db_path=db_path,
        )
        self.loom_error_flag = False

    async def write_shafts_to_loom(self, pick: Pick) -> None:
        """Send a shaft_word to the loom"""
        await self.write_to_loom(f"C{pick.shaft_word:08x}")

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
