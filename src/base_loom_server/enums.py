import enum


class ConnectionStateEnum(enum.IntEnum):
    """Client websocket connection state."""

    DISCONNECTED = 0
    CONNECTED = 1
    CONNECTING = 2
    DISCONNECTING = 3


class DirectionControlEnum(enum.IntEnum):
    """What controls the direction (weave/unweave).

    * FULL: the direction can be changed by both the web interface
        and the direction button on the loom.
        If the loom supports this (e.g. Séguin), this is the only allowed
        value. For other looms (e.g. Toika) the direction must be
        one of the other values.
    * LOOM: the direction can only be changed by the direction button
        on the loom. The web browser only displays the direction.
    * SOFTWARE: the direction can only be changed by the web interface.
        The direction control on the loom is ignored.
    """

    FULL = 1
    LOOM = 2
    SOFTWARE = 3


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
