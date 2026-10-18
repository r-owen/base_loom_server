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
        and the direction button on the loom,
        OR the loom does not support direction control at all.
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

    WEAVE_PATTERN = 1
    WEAVE_TABBY = 2
    THREAD = 3
    SETTINGS = 4


class RunStateEnum(enum.IntEnum):
    """The current run state.

    NOT_SUPPORTED indicates that start and stop controls and run state
    should not be displayed.
    """

    NOT_SUPPORTED = 0
    STARTING = 1
    RUNNING = 2
    STOPPING = 3
    STOPPED = 4


class ShaftStateEnum(enum.IntEnum):
    """The current shaft motion state.

    The following values may apply to most looms:

    * UNKNOWN: the initial state.
    * DONE: the weaving cycle is ready and the loom is ready for the next shed.
    * MOVING: the shafts are moving into their shed position.
    * ERROR: something went wrong. Abort this pick and try again.

    The following values may apply to looms with manually opened sheds:

    * READY: the solenoids are engaged and the loom is ready for the weaver to open the shed.
    * TIMED_OUT: the solenoids timed out while waiting the user to open the shed.
    * WAITING_FOR_CLOSE: the software is waiting for the user to close the shed.
    """

    UNKNOWN = 0
    DONE = 1
    MOVING = 2
    ERROR = 3
    READY = 4
    TIMED_OUT = 5
    WAITING_FOR_CLOSE = 6
