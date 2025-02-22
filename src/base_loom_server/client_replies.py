import dataclasses
import enum


class ConnectionStateEnum(enum.IntEnum):
    """Client websocket connection state."""

    DISCONNECTED = 0
    CONNECTED = 1
    CONNECTING = 2
    DISCONNECTING = 3


class MessageSeverityEnum(enum.IntEnum):
    """Severity for text messages"""

    INFO = 1
    WARNING = 2
    ERROR = 3


class ModeEnum(enum.IntEnum):
    WEAVE = 1
    THREAD = 2
    TEST = 3


class ShaftStateEnum(enum.IntEnum):
    """Shaft state"""

    UNKNOWN = 0
    DONE = 1
    MOVING = 2
    ERROR = 3


@dataclasses.dataclass
class CommandProblem:
    """A problem with a command from the client"""

    type: str = dataclasses.field(init=False, default="CommandProblem")
    message: str
    severity: MessageSeverityEnum


@dataclasses.dataclass
class CurrentEndNumbers:
    """The current threading end numbers and repeat number

    The range of end numbers is [end_number0, end_number1).
    If end_number0 is 0 then end_number1 will also be zero
    (no threads in range).
    """

    type: str = dataclasses.field(init=False, default="CurrentEndNumber")
    end_number0: int
    end_number1: int
    end_repeat_number: int


@dataclasses.dataclass
class CurrentPickNumber:
    """The current weaving pick and repeat numbers"""

    type: str = dataclasses.field(init=False, default="CurrentPickNumber")
    pick_number: int
    pick_repeat_number: int


@dataclasses.dataclass
class JumpEndNumber:
    """Pending end and repeat numbers"""

    type: str = dataclasses.field(init=False, default="JumpEndNumber")
    end_number0: int | None = None
    end_number1: int | None = None
    end_repeat_number: int | None = None


@dataclasses.dataclass
class JumpPickNumber:
    """Pending pick and repeat numbers"""

    type: str = dataclasses.field(init=False, default="JumpPickNumber")
    pick_number: int | None = None
    pick_repeat_number: int | None = None


@dataclasses.dataclass
class LoomConnectionState:
    """The state of the server's connection to the loom"""

    type: str = dataclasses.field(init=False, default="LoomConnectionState")
    state: ConnectionStateEnum
    reason: str = ""


@dataclasses.dataclass
class Mode:
    """The mode of the server"""

    type: str = dataclasses.field(init=False, default="Mode")
    mode: ModeEnum


@dataclasses.dataclass
class ShaftState:
    """Shaft status

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
    """Status message"""

    type: str = dataclasses.field(init=False, default="StatusMessage")
    message: str
    severity: MessageSeverityEnum


@dataclasses.dataclass
class PatternNames:
    """The list of loaded patterns (including the current pattern)"""

    type: str = dataclasses.field(init=False, default="PatternNames")
    names: list[str]


@dataclasses.dataclass
class ThreadDirection:
    """The threading direction"""

    type: str = dataclasses.field(init=False, default="ThreadDirection")
    low_to_high: bool


@dataclasses.dataclass
class ThreadGroupSize:
    """The threading group size"""

    type: str = dataclasses.field(init=False, default="ThreadGroupSize")
    group_size: int


@dataclasses.dataclass
class WeaveDirection:
    """The weaving direction"""

    type: str = dataclasses.field(init=False, default="WeaveDirection")
    forward: bool
