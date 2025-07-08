import enum


class ConnectionStateEnum(enum.IntEnum):
    """Client websocket connection state."""

    DISCONNECTED = 0
    CONNECTED = 1
    CONNECTING = 2
    DISCONNECTING = 3


class DirectionControlEnum(enum.IntEnum):
    """What controls the direction (weave/unweave).

    * FULL: The direction can be changed by both the web interface
        and the direction button on the loom.
        If the loom supports this (e.g. Séguin), it is the only allowed value.
        If the loom does not (e.g. Toika), this value is prohibited.
    * LOOM: The direction can only be changed by the unweave button
        on the loom. The web browser only displays the direction.
    * SOFTWARE: The direction can only be changed by the web interface.
        The unweave button on the loom is ignored.
    """

    FULL = 1
    LOOM = 2
    SOFTWARE = 3


class MessageSeverityEnum(enum.IntEnum):
    """Severity for text messages."""

    INFO = 1
    WARNING = 2
    ERROR = 3


class ModeEnum(enum.IntEnum):
    """The current server mode."""

    WEAVE = 1
    THREAD = 2
    SETTINGS = 3


class ShaftStateEnum(enum.IntEnum):
    """The current shaft motion state."""

    UNKNOWN = 0
    DONE = 1
    MOVING = 2
    ERROR = 3
