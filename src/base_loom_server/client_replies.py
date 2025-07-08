import dataclasses

from .enums import (
    ConnectionStateEnum,
    DirectionControlEnum,
    MessageSeverityEnum,
    ModeEnum,
    ShaftStateEnum,
)


@dataclasses.dataclass
class CommandDone:
    """Report completion or failure of a command."""

    type: str = dataclasses.field(init=False, default="CommandDone")
    cmd_type: str
    success: bool
    message: str


@dataclasses.dataclass
class CommandProblem:
    """A problem with a command from the client."""

    type: str = dataclasses.field(init=False, default="CommandProblem")
    message: str
    severity: MessageSeverityEnum


@dataclasses.dataclass
class CurrentEndNumber:
    """The current threading end numbers and repeat number.

    The range of end numbers is end_number0 through end_number1,
    inclusive. If end_number0 is 0 then end_number1 will also be 0;
    this indicates the beginning, or a gap between pattern repeats.
    """

    type: str = dataclasses.field(init=False, default="CurrentEndNumber")
    total_end_number0: int
    total_end_number1: int
    end_number0: int
    end_number1: int
    end_repeat_number: int


@dataclasses.dataclass
class CurrentPickNumber:
    """The current total_pick_number, pick_number and pick_repeat_number."""

    type: str = dataclasses.field(init=False, default="CurrentPickNumber")
    total_pick_number: int
    pick_number: int
    pick_repeat_number: int


@dataclasses.dataclass
class Direction:
    """The weaving and threading direction."""

    type: str = dataclasses.field(init=False, default="Direction")
    forward: bool


@dataclasses.dataclass
class JumpEndNumber:
    """Pending end and repeat numbers."""

    type: str = dataclasses.field(init=False, default="JumpEndNumber")
    total_end_number0: int | None = None
    total_end_number1: int | None = None
    end_number0: int | None = None
    end_number1: int | None = None
    end_repeat_number: int | None = None


@dataclasses.dataclass
class JumpPickNumber:
    """Pending total_pick_number, pick_number, and pick_repeat_number.

    If total_pick_number is not None then pick_number and pick_repeat_number
    must also not be None.
    """

    type: str = dataclasses.field(init=False, default="JumpPickNumber")
    total_pick_number: int | None = None
    pick_number: int | None = None
    pick_repeat_number: int | None = None

    def __post_init__(self) -> None:
        if self.total_pick_number is not None and (
            self.pick_number is None or self.pick_repeat_number is None
        ):
            raise ValueError(
                f"{self.pick_number=} and {self.pick_repeat_number=} must not be None "
                f"if {self.total_pick_number=} is not None"
            )


@dataclasses.dataclass
class LanguageNames:
    """Supported languages."""

    type: str = dataclasses.field(init=False, default="LanguageNames")
    languages: list[str]


@dataclasses.dataclass
class LoomConnectionState:
    """The state of the server's connection to the loom."""

    type: str = dataclasses.field(init=False, default="LoomConnectionState")
    state: ConnectionStateEnum
    reason: str = ""


@dataclasses.dataclass
class LoomInfo:
    """Information about the loom."""

    type: str = dataclasses.field(init=False, default="LoomInfo")
    num_shafts: int
    serial_port: str
    is_mock: bool


@dataclasses.dataclass
class Mode:
    """The mode of the server."""

    type: str = dataclasses.field(init=False, default="Mode")
    mode: ModeEnum


@dataclasses.dataclass
class SeparateThreadingRepeats:
    """Separate weaving repeats?"""

    type: str = dataclasses.field(init=False, default="SeparateThreadingRepeats")
    separate: bool


@dataclasses.dataclass
class SeparateWeavingRepeats:
    """Separate weaving repeats?"""

    type: str = dataclasses.field(init=False, default="SeparateWeavingRepeats")
    separate: bool


@dataclasses.dataclass
class Settings:
    """Settings for the settings file (which apply to all patterns)."""

    type: str = dataclasses.field(init=False, default="Settings")
    language: str
    loom_name: str
    direction_control: DirectionControlEnum
    end1_on_right: bool
    thread_group_size: int
    thread_right_to_left: bool
    thread_back_to_front: bool


@dataclasses.dataclass
class ShaftState:
    """Shaft status.

    shaft_word is a bitmask:

    * bit 0 = shaft 1, etc.
    * bit value is 0 if shaft is up

    shaft_word is only meaningful if state = ShaftStateEnum.DONE
    """

    type: str = dataclasses.field(init=False, default="ShaftState")
    state: ShaftStateEnum
    shaft_word: int


@dataclasses.dataclass
class StatusMessage:
    """Status message."""

    type: str = dataclasses.field(init=False, default="StatusMessage")
    message: str
    severity: MessageSeverityEnum


@dataclasses.dataclass
class PatternNames:
    """The list of loaded patterns (including the current pattern)."""

    type: str = dataclasses.field(init=False, default="PatternNames")
    names: list[str]


@dataclasses.dataclass
class ThreadGroupSize:
    """The threading group size for the current pattern."""

    type: str = dataclasses.field(init=False, default="ThreadGroupSize")
    group_size: int
