__all__ = ["BaseMockLoom"]

from .base_mock_loom import BaseMockLoom


class ExampleMockLoom(BaseMockLoom):
    """Example dobby loom simulator.

    This is a slightly simplified version of the Séguin dobby loom.
    See the doc string for `BaseMockLoom` for usage instructions.

    Args:
        verbose: If True, log diagnostic information.
    """

    async def handle_read_bytes(self, read_bytes: bytes) -> None:
        """Handle one command from the web server."""
        cmd = read_bytes.decode().rstrip()
        if self.verbose:
            self.log.info(f"{self}: process client command {cmd!r}")
        if len(cmd) < 1:
            self.log.warning(f"{self}: invalid command {cmd!r}: must be at least 1 character")
            return
        cmd_char = cmd[0]
        cmd_data = cmd[1:]
        match cmd_char:
            case "C":
                # Specify which shafts to raise as a hex value
                try:
                    shaft_word = int(cmd_data, base=16)
                except Exception:
                    self.log.warning(f"{self}: invalid command {cmd!r}: data after =C not a hex value")
                    return
                await self.set_shaft_word(shaft_word)
            case "U":
                # Client commands unweave on/off
                # (as opposed to user pushing UNW button on the loom,
                # in which case the loom changes it and reports it
                # to the client).
                if cmd_data not in {"0", "1"}:
                    self.log.warning(f"{self}: invalid command {cmd!r}: arg must be 0 or 1")
                    return
                await self.set_direction_forward(direction_forward=cmd_data == "0")
            case _:
                self.log.warning(f"MockLoom: unrecognized command: {cmd!r}")

    async def report_direction(self) -> None:
        await self.write(f"u{int(not self.direction_forward)}")

    async def report_motion_state(self) -> None:
        await self.write(f"m{int(self.moving)}")

    async def report_pick_wanted(self) -> None:
        if self.pick_wanted:
            await self.write("p")

    async def report_shafts(self) -> None:
        await self.write(f"c{self.shaft_word:08x}")
