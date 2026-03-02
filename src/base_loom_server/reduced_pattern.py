from __future__ import annotations

__all__ = [
    "DEFAULT_THREAD_GROUP_SIZE",
    "NUM_ITEMS_FOR_REPEAT_SEPARATOR",
    "Pick",
    "ReducedPattern",
    "reduced_pattern_from_pattern_data",
]

import copy
import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from .compute_tabby import compute_tabby_shaft_words
from .utils import bitmask_from_bits

if TYPE_CHECKING:
    import dtx_to_wif

DEFAULT_THREAD_GROUP_SIZE = 1

# The number of picks or warp threads above which
# the repeat separator is, by default, enabled
# (so if the number is <= then no separator)
NUM_ITEMS_FOR_REPEAT_SEPARATOR = 20


def pop_and_check_type_field(typename: str, datadict: dict[str, Any]) -> None:
    typestr = datadict.pop("type", typename)
    if typestr != typename:
        raise TypeError(f"Wrong type: {typestr=!r} != {typename!r}")


@dataclasses.dataclass
class Pick:
    """One pick of a pattern.

    Args:
        color: Weft color, as an index into the color table.
        shaft_word: A bit mask, with bit 1 = shaft 0.
            The shaft is up if the bit is set.
    """

    color: int
    shaft_word: int

    @classmethod
    def from_dict(cls, datadict: dict[str, Any]) -> Pick:
        """Construct a Pick from a dict representation.

        The "type" field is optional, but checked if present.
        """
        pop_and_check_type_field("Weft thread", datadict)
        return cls(**datadict)


@dataclasses.dataclass
class ReducedPattern:
    """A weaving pattern reduced to the bare essentials.

    Contains just enough information to allow loom control,
    with a simple display.

    Picks are accessed by pick number, which is 1-based.
    0 indicates that nothing has been woven.
    Similarly for tabby picks and warp ends.

    Shaft numbers in threading are 0-based.

    pick_number and end_number0/1 are within one pattern repeat,
    and repeats are tracked with related attributes.
    tabby_pick_number is different, since repeats of tabby are not tracked
    (as uninteresting), the value is a "total" pick number.
    """

    type: str = dataclasses.field(init=False, default="ReducedPattern")
    name: str
    color_table: list[str]
    warp_colors: list[int]
    threading: list[int]
    picks: list[Pick]
    tabby_picks: list[Pick]
    num_shafts: int
    # Keep track of where we are in weaving
    pick_number: int = 0
    pick_repeat_number: int = 1
    # Keep track of where we are in weaving tabby
    tabby_pick_number: int = 0
    # keep track of where we are in threading
    end_number0: int = 0
    end_number1: int = 0
    end_repeat_number: int = 1
    _thread_group_size: int = DEFAULT_THREAD_GROUP_SIZE

    separate_weaving_repeats: bool = False
    separate_threading_repeats: bool = False

    tabby_color: ClassVar[int] = 0

    @classmethod
    def from_dict(cls, datadict: dict[str, Any]) -> ReducedPattern:
        """Construct a ReducedPattern from a dict."""
        # Make a copy, so the caller doesn't see the picks field change
        datadict = copy.deepcopy(datadict)
        pop_and_check_type_field(typename="ReducedPattern", datadict=datadict)
        for picks_name in ("picks", "tabby_picks"):
            datadict[picks_name] = [Pick.from_dict(pickdict) for pickdict in datadict[picks_name]]
        return cls(**datadict)

    @property
    def num_ends(self) -> int:
        """How many warp ends are in the pattern."""
        return len(self.threading)

    @property
    def num_picks(self) -> int:
        """How many weft picks are in the pattern."""
        return len(self.picks)

    @property
    def thread_group_size(self) -> int:
        """Get the thread group size."""
        return self._thread_group_size

    @thread_group_size.setter
    def thread_group_size(self, value: int) -> None:
        value = int(value)
        if value < 1:
            raise ValueError(f"{value=} must be positive")
        self._thread_group_size = value

    def check_end_number(self, end_number0: int) -> None:
        """Raise IndexError if end_number0 out of range.

        The allowed range is 0 to self.len(self.threading), inclusive.
        See get_end_number for more information.
        """
        if end_number0 < 0:
            raise IndexError(f"{end_number0=} < 0")
        if end_number0 > len(self.threading):
            raise IndexError(f"{end_number0=} > {len(self.threading)}")

    def check_pick_number(self, pick_number: int) -> None:
        """Raise IndexError if pick_number out of range.

        The allowed range is 0 to self.len(self.picks), inclusive.
        See get_pick_number for more information.
        """
        if pick_number < 0:
            raise IndexError(f"{pick_number=} < 0")
        if pick_number > len(self.picks):
            raise IndexError(f"{pick_number=} > {len(self.picks)}")

    def compute_end_number1(self, end_number0: int) -> int:
        """Compute end_number1 given end_number0.

        Uses the current value of end_repeat_number.
        """
        self.check_end_number(end_number0)
        max_end_number = len(self.threading)
        if end_number0 == 0:
            return 0
        return min(end_number0 + self.thread_group_size - 1, max_end_number)

    def compute_next_end_numbers(self, *, thread_low_to_high: bool) -> tuple[int, int, int]:
        """Compute the next (end_number0, end_number1, end_repeat_number)
        in the specified direction.

        End number is 1-based, but 0 means at start or between repeats
        (in which case there are no threads in the group).

        Raises:
            IndexError: If trying to increment past the start of threading.
            IndexError: if self.end_number0 is invalid.
        """
        self.check_end_number(self.end_number0)

        max_end_number = len(self.threading)
        new_end_number0 = 0
        # Initialize new_end_number1 to None to allow set_current_end_number
        # to compute it, if possible (most cases below).
        new_end_number1 = None
        new_end_repeat_number = self.end_repeat_number
        if thread_low_to_high:
            if self.end_number0 == 0:
                new_end_number0 = 1
            elif self.end_number1 < max_end_number:
                new_end_number0 = self.end_number1 + 1
            else:
                # At the end of one repeat; start the next.
                new_end_number0 = 0 if self.separate_threading_repeats else 1
                new_end_repeat_number += 1
        else:
            # Thread high to low
            if self.end_number0 == 0 and self.end_repeat_number == 1:
                raise IndexError("At start of threading")

            if self.end_number0 == 1 and (self.separate_threading_repeats or self.end_repeat_number == 1):
                # We are at the beginning of a pattern repeat and
                # either we separate repeats or it is the very first.
                # Go to end 0.
                new_end_number0 = 0
            elif self.end_number0 == 0 or (self.end_number0 == 1 and not self.separate_threading_repeats):
                # Start the previous repeat.
                new_end_number1 = max_end_number
                new_end_number0 = max(new_end_number1 + 1 - self.thread_group_size, 1)
                new_end_repeat_number -= 1
            else:
                # We are still threading the current pattern repeat.
                # We must compute end_number1 because the available group
                # size may be smaller than the desired group size.
                new_end_number0 = max(self.end_number0 - self.thread_group_size, 1)
                new_end_number1 = self.end_number0 - 1
        if new_end_number1 is None:
            if new_end_number0 == 0:
                new_end_number1 = 0
            else:
                new_end_number1 = min(new_end_number0 + self.thread_group_size - 1, max_end_number)

        return (new_end_number0, new_end_number1, new_end_repeat_number)

    def compute_next_pick_numbers(self, *, direction_forward: bool) -> tuple[int, int]:
        """Compute (next pick_number, pick_repeat_number)
        in the specified direction.

        Raises:
            IndexError: If trying to back up past the start of weaving.
        """
        self.check_pick_number(self.pick_number)

        # Start by assuming we are not at the end of a pattern repeat.
        next_pick_repeat_number = self.pick_repeat_number
        delta_pick_number = 1 if direction_forward else -1
        next_pick_number = self.pick_number + delta_pick_number

        # Now handle end of pattern repeat, and check if backing up too far.
        if direction_forward:
            if self.pick_number == len(self.picks):
                # Advance past the end of a pattern repeat.
                next_pick_number = 0 if self.separate_weaving_repeats else 1
                next_pick_repeat_number += 1
        else:
            # Backing up.
            if self.pick_number == 0 and self.pick_repeat_number == 1:
                # At start of pattern; cannot back up.
                raise IndexError("At start of pattern")

            if self.pick_number == 1 and (self.separate_weaving_repeats or self.pick_repeat_number == 1):
                # We are at pick 1 and either separating weaving repeats or in repeat 1.
                # Back up to pick 0 without changing the pattern repeat:
                next_pick_number = 0
            elif self.pick_number == 0 or (self.pick_number == 1 and not self.separate_weaving_repeats):
                # We are either at pick 0, or at pick 1 and not separating pattern repeats.
                # Back up to the end of the previous pattern repeat.
                next_pick_number = len(self.picks)
                next_pick_repeat_number -= 1
        return (next_pick_number, next_pick_repeat_number)

    def get_current_pick(self) -> Pick:
        """Get the current pick."""
        return self.get_pick(self.pick_number)

    def get_current_tabby_pick(self) -> Pick:
        """Get the current tabby pick."""
        return self.get_tabby_pick(self.tabby_pick_number)

    def get_pick(self, pick_number: int) -> Pick:
        """Get the specified pick.

        Return a pick with shaft_word=0 if pick_number = 0,
        else return self.picks[pick_number-1] if pick_number in range.

        Raises:
            IndexError: If `pick_number` < 0 or > len(self.picks).
        """
        self.check_pick_number(pick_number)
        if pick_number == 0:
            return Pick(shaft_word=0, color=0)
        return self.picks[pick_number - 1]

    def get_tabby_pick(self, tabby_pick_number: int) -> Pick:
        """Get the specified tabby pick.

        Args:
            tabby_pick_number: Tabby pick number; must be non-negative

        Raises:
            IndexError if tabby_pick_number < 0
        """
        if tabby_pick_number < 0:
            raise IndexError(f"{tabby_pick_number=} must be >= 0")

        if tabby_pick_number == 0:
            return Pick(shaft_word=0, color=0)

        tabby_pick_index = (tabby_pick_number + 1) % 2  # num->index: 1->1, 2->0, 3->1, 4->0, ...
        return self.tabby_picks[tabby_pick_index]

    def get_threading_shaft_word(self) -> int:
        """Get current threading shaft word."""
        if self.end_number0 == 0:
            return 0
        # Shafts in threading are 0-based but bitmask_from_bits wants 1-based values
        shaft_nums = {self.threading[i] + 1 for i in range(self.end_number0 - 1, self.end_number1)}
        return bitmask_from_bits(shaft_nums)

    def increment_end_number(self, *, thread_low_to_high: bool) -> None:
        """Increment self.end_number0 in the specified direction.
        Increment end_repeat_number as well, if appropriate.

        End number is 1-based, but 0 means at start or between repeats
        (in which case there are no threads in the group).

        Raises:
            IndexError: If trying to increment past the start of threading.
            IndexError: if self.end_number0 is invalid.
        """
        end_number0, end_number1, end_repeat_number = self.compute_next_end_numbers(
            thread_low_to_high=thread_low_to_high
        )
        self.set_current_end_number(
            end_number0=end_number0,
            end_number1=end_number1,
            end_repeat_number=end_repeat_number,
        )

    def increment_pick_number(self, *, direction_forward: bool) -> None:
        """Increment pick_number in the specified direction.

        Update pick_repeat_number as well, if appropriate.

        Returns:
            pick_number: The new pick number.

        Raises:
            IndexError: If trying to back up past the start of weaving.
        """
        self.pick_number, self.pick_repeat_number = self.compute_next_pick_numbers(
            direction_forward=direction_forward
        )

    def increment_tabby_pick_number(self, *, direction_forward: bool) -> None:
        """Increment tabby_pick_number in the specified direction.

        Returns:
            tabby_pick_number: The new tabby pick number.

        Raises:
            IndexError: If trying to back up past the start of weaving.
        """
        delta = 1 if direction_forward else -1
        new_tabby_pick_number = self.tabby_pick_number + delta
        if new_tabby_pick_number < 0:
            raise IndexError(f"{new_tabby_pick_number=} must be >= 0")

        self.tabby_pick_number = new_tabby_pick_number

    def set_current_end_number(
        self,
        end_number0: int,
        end_number1: int | None = None,
        end_repeat_number: int | None = None,
    ) -> None:
        """Set end_number0, end_number1, and possibly end_repeat_number.

        Args:
            end_number0: New value for end_number0, the starting end number
                for a group of ends to thread.
                Must be in range 0 ≤ end_number0 ≤ num_shafts.
            end_number1: New value for end_number1. If None, compute it.
                If not None then the value must be:

                * 0, if end_number0 = 0.
                * Else in range end_number0 <= end_number1 ≤ num ends.
            end_repeat_number: New value for end_repeat_number.
                If None, use the current value.

        Raises:
            IndexError: If end_number0 < 0 or > len(self.threading).
            IndexError: If end_number1 not None and not valid.
        """
        self.check_end_number(end_number0)
        max_end_number = len(self.threading)
        if end_number1 is not None:
            if end_number0 == 0:
                if end_number1 != 0:
                    raise IndexError(f"{end_number1=} must be 0, since end_number0=0")
            elif end_number1 > max_end_number:
                raise IndexError(f"{end_number1=} must be <= {max_end_number}")
            elif end_number1 < end_number0:
                raise IndexError(f"{end_number1=} must be >= {end_number0=}")
            self.end_number1 = end_number1
        else:
            self.end_number1 = self.compute_end_number1(end_number0=end_number0)
        self.end_number0 = end_number0
        if end_repeat_number is not None:
            self.end_repeat_number = end_repeat_number

    def set_current_pick_number(self, pick_number: int) -> None:
        """Set pick_number.

        Args:
            pick_number: The pick number.

        Raises:
            IndexError if pick_number < 0 or > num picks.
        """
        self.check_pick_number(pick_number)
        self.pick_number = pick_number

    def set_current_tabby_pick_number(self, tabby_pick_number: int) -> None:
        """Set pick_number.

        Args:
            tabby_pick_number: The tabby pick number.

        Raises:
            IndexError if pick_number < 0 or > num picks.
        """
        if tabby_pick_number < 0:
            raise IndexError(f"{tabby_pick_number=} must be >= 0")
        self.tabby_pick_number = tabby_pick_number


def _smallest_shaft(shafts: set[int]) -> int:
    """Return the smallest non-zero shaft from a set of shafts.

    Return 0 if no non-zero shafts.
    """
    pruned_shafts = shafts - {0}
    if pruned_shafts:
        return sorted(shafts)[0]
    return 0


def reduced_pattern_from_pattern_data(name: str, data: dtx_to_wif.PatternData) -> ReducedPattern:
    """Convert a dtx_to_wif.PatternData to a ReducedPattern.

    Args:
        name: The name of the pattern to use.
        data: The pattern read by dtx_to_wif. The `name` field is ignored.

    The result is simpler and smaller, and can be sent to easily
    encoded and sent to JavaScript.

    Note that all input (PatternData) indices are 1-based
    and all output (ReducedPattern) indices are 0-based.
    """
    if data.color_table:
        # Note: PatternData promises to have color_range
        # if color_table is present.
        if data.color_range is None:
            raise RuntimeError("color_table specified, but color_range is None")

        # Compute a scaled version of the color table, where each
        # scaled r,g,b value is in range 0-255 (0-0xff) inclusive
        min_color = data.color_range[0]
        color_scale = 255 / (data.color_range[1] - min_color)
        # Note: PatternData promises that color_table
        # keys are 1, 2, ...N, with no missing keys,
        # so we can ignore the keys and just use the values.
        scaled_color_rgbs = (
            [int((value - min_color) * color_scale) for value in color_rgb]
            for color_rgb in data.color_table.values()
        )
        color_strs = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in scaled_color_rgbs]
        if len(color_strs) < 1:
            # Make sure we have at least 2 entries
            color_strs += ["#ffffff", "#000000"]
    else:
        color_strs = ["#ffffff", "#000000"]

    num_ends = max(data.threading.keys())
    end_numbers = list(range(1, num_ends + 1))
    threading = [_smallest_shaft(data.threading.get(end_number, {0})) - 1 for end_number in end_numbers]
    max_threaded_shaft = max(threading)

    num_picks = max(data.liftplan.keys()) if data.liftplan else max(data.treadling.keys())
    pick_numbers = list(range(1, num_picks + 1))
    default_warp_color = data.warp.color if data.warp.color is not None else 1
    warp_colors = [data.warp_colors.get(end_number, default_warp_color) - 1 for end_number in end_numbers]
    default_weft_color = data.weft.color if data.weft.color is not None else 2
    weft_colors = [data.weft_colors.get(weft, default_weft_color) - 1 for weft in pick_numbers]

    if data.liftplan:
        shaft_sets = [data.liftplan.get(weft, set()) - {0} for weft in pick_numbers]
    else:
        shaft_sets = []
        for weft in pick_numbers:
            treadle_set = data.treadling.get(weft, set()) - {0}
            shaft_sets.append(set.union(*(data.tieup[treadle] for treadle in treadle_set)) - {0})
    if len(shaft_sets) != len(weft_colors):
        raise RuntimeError(f"{len(shaft_sets)=} != {len(weft_colors)=}\n{shaft_sets=}\n{weft_colors=}")
    try:
        max_shaft_raised = max(max(shaft_set) for shaft_set in shaft_sets if shaft_set)
    except (ValueError, TypeError):
        raise RuntimeError("No shafts are raised") from None
    all_shafts = set(range(1, max_shaft_raised + 1))
    if data.is_rising_shed:
        shaft_words = [bitmask_from_bits(shaft_set) for shaft_set in shaft_sets]
    else:
        shaft_words = [bitmask_from_bits(all_shafts - shaft_set) for shaft_set in shaft_sets]
    picks = [
        Pick(shaft_word=shaft_word, color=weft_color)
        for shaft_word, weft_color in zip(shaft_words, weft_colors, strict=True)
    ]

    tabby_shaft_words = compute_tabby_shaft_words(threading)
    tabby_picks = [
        Pick(shaft_word=tabby_shaft_word, color=ReducedPattern.tabby_color)
        for tabby_shaft_word in tabby_shaft_words
    ]

    return ReducedPattern(
        color_table=color_strs,
        name=name,
        warp_colors=warp_colors,
        threading=threading,
        picks=picks,
        tabby_picks=tabby_picks,
        num_shafts=max(max_shaft_raised, max_threaded_shaft),
        separate_weaving_repeats=len(picks) > NUM_ITEMS_FOR_REPEAT_SEPARATOR,
        separate_threading_repeats=len(threading) > NUM_ITEMS_FOR_REPEAT_SEPARATOR,
    )
