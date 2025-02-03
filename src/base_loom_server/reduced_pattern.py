from __future__ import annotations

__all__ = [
    "Pick",
    "ReducedPattern",
    "reduced_pattern_from_pattern_data",
    "read_full_pattern",
]

import copy
import dataclasses
import pathlib
from collections.abc import Iterable
from typing import Any

import dtx_to_wif


def pop_and_check_type_field(typename: str, datadict: dict[str, Any]) -> None:
    typestr = datadict.pop("type", typename)
    if typestr != typename:
        raise TypeError(f"Wrong type: {typestr=!r} != {typename!r}")


@dataclasses.dataclass
class Pick:
    """One pick of a pattern

    Parameters
    ----------
    color: weft color, as an index into the color table
    shaft_word: a bit mask, with bit 1 = shaft 0;
        the shaft is up if the bit is set
    """

    color: int
    shaft_word: int

    @classmethod
    def from_dict(cls, datadict: dict[str, Any]) -> Pick:
        """Construct a Pick from a dict representation.

        The "type" field is optional, but checked if present.
        """
        pop_and_check_type_field("Pick", datadict)
        return cls(**datadict)


@dataclasses.dataclass
class ReducedPattern:
    """A weaving pattern reduced to the bare essentials.

    Contains just enough information to allow loom control,
    with a simple display.

    Picks are accessed by pick number, which is 1-based.
    0 indicates that nothing has been woven.
    """

    type: str = dataclasses.field(init=False, default="ReducedPattern")
    name: str
    color_table: list[str]
    warp_colors: list[int]
    threading: list[int]
    picks: list[Pick]
    pick0: Pick
    pick_number: int = 0
    repeat_number: int = 1

    @classmethod
    def from_dict(cls, datadict: dict[str, Any]) -> ReducedPattern:
        """Construct a ReducedPattern from a dict.

        The "type" field is optional, but checked if present.
        """
        # Make a copy, so the caller doesn't see the picks field change
        datadict = copy.deepcopy(datadict)
        pop_and_check_type_field(typename="ReducedPattern", datadict=datadict)
        datadict["picks"] = [Pick.from_dict(pickdict) for pickdict in datadict["picks"]]
        datadict["pick0"] = Pick.from_dict(datadict["pick0"])
        return cls(**datadict)

    def increment_pick_number(self, weave_forward: bool) -> int:
        """Increment pick_number in the specified direction.

        Increment repeat_number as well, if appropriate.

        Return the new pick number.
        """
        if self.pick_number < 0 or self.pick_number > len(self.picks):
            raise RuntimeError(
                f"Bug: {self.pick_number=} out of range [0, {len(self.picks)}"
            )
        next_pick_number = self.pick_number + (1 if weave_forward else -1)
        if next_pick_number < 0:
            self.repeat_number -= 1
            next_pick_number = len(self.picks)
        elif next_pick_number > len(self.picks):
            self.repeat_number += 1
            next_pick_number = 0
        self.pick_number = next_pick_number
        return next_pick_number

    def get_current_pick(self) -> Pick:
        """Get the current pick.

        Raises
        ------
        IndexError
            If current pick number < 1 or > len(self.picks)
        """
        pick_number = self.pick_number
        if pick_number == 0:
            return self.pick0
        if pick_number < 0 or pick_number > len(self.picks):
            raise IndexError(f"{pick_number=} < 0 or > {len(self.picks)}")
        else:
            return self.picks[pick_number - 1]

    def get_pick(self, pick_number: int) -> Pick:
        """Get the specified pick"""
        if pick_number < 0:
            raise IndexError(f"{pick_number=} < 0")
        if pick_number > len(self.picks):
            raise IndexError(f"{pick_number=} > {len(self.picks)}")
        if pick_number == 0:
            return self.pick0
        return self.picks[pick_number - 1]

    def set_current_pick_number(self, pick_number: int) -> None:
        """Set pick_number.

        Parameters
        ----------
        pick_number : int
            The pick pick_number.

        Raise IndexError if pick_number < 0 or > num picks.
        """
        if pick_number < 0 or pick_number > len(self.picks):
            raise IndexError(f"{pick_number=} < 0 or > {len(self.picks)}")
        self.pick_number = pick_number


def _smallest_shaft(shafts: set[int]) -> int:
    """Return the smallest non-zero shaft from a set of shafts.

    Return 0 if no non-zero shafts"""
    pruned_shafts = shafts - {0}
    if pruned_shafts:
        return list(sorted(shafts))[0]
    return 0


def reduced_pattern_from_pattern_data(
    name: str, data: dtx_to_wif.PatternData
) -> ReducedPattern:
    """Convert a dtx_to_wif.PatternData to a ReducedPattern.

    Parameters
    ----------
    name : str
        The name of the pattern to use (overrides the name
        in PatternData).
    data : dtx_to_wif.PatternData
        The pattern read by dtx_to_wif.

    The result is simpler and smaller, and can be sent to easily
    encoded and sent to javascript.

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
    num_warps = max(data.threading.keys())
    warps_from1 = list(range(1, num_warps + 1))
    num_wefts = (
        max(data.liftplan.keys()) if data.liftplan else max(data.treadling.keys())
    )
    wefts_from1 = list(range(1, num_wefts + 1))
    default_warp_color = data.warp.color if data.warp.color is not None else 1
    warp_colors = [
        data.warp_colors.get(warp, default_warp_color) - 1 for warp in warps_from1
    ]
    default_weft_color = data.weft.color if data.weft.color is not None else 2
    weft_colors = [
        data.weft_colors.get(weft, default_weft_color) - 1 for weft in wefts_from1
    ]

    if data.liftplan:
        shaft_sets = list(data.liftplan.get(weft, {}) - {0} for weft in wefts_from1)  # type: ignore
    else:
        shaft_sets = []
        for weft in wefts_from1:
            treadle_set = data.treadling.get(weft, {}) - {0}  # type: ignore
            shaft_sets.append(
                set.union(*(data.tieup[treadle] for treadle in treadle_set)) - {0}
            )
    if len(shaft_sets) != len(weft_colors):
        raise RuntimeError(
            f"{len(shaft_sets)=} != {len(weft_colors)=}\n{shaft_sets=}\n{weft_colors=}"
        )
    try:
        num_shafts = max(max(shaft_set) for shaft_set in shaft_sets if shaft_set)
    except (ValueError, TypeError):
        raise RuntimeError("No shafts are raised")
    threading = [
        _smallest_shaft(data.threading.get(warp, {0})) - 1 for warp in warps_from1
    ]
    all_shafts = set(range(1, num_shafts + 1))
    if data.is_rising_shed:
        shaft_words = [shaft_word_from_shaft_set(shaft_set) for shaft_set in shaft_sets]
    else:
        shaft_words = [
            shaft_word_from_shaft_set(all_shafts - shaft_set)
            for shaft_set in shaft_sets
        ]
    picks = [
        Pick(shaft_word=shaft_word, color=weft_color)
        for shaft_word, weft_color in zip(shaft_words, weft_colors)
    ]

    result = ReducedPattern(
        color_table=color_strs,
        name=name,
        warp_colors=warp_colors,
        threading=threading,
        picks=picks,
        pick0=Pick(shaft_word=0, color=default_weft_color),
    )
    return result


def read_full_pattern(path: pathlib.Path) -> dtx_to_wif.PatternData:
    readfunc = {
        ".wif": dtx_to_wif.read_wif,
        ".dtx": dtx_to_wif.read_dtx,
    }[path.suffix]
    with open(path, "r") as f:
        full_pattern = readfunc(f)
    return full_pattern


def shaft_word_from_shaft_set(shaft_set: Iterable[int]) -> int:
    """Convert a shaft set to a shaft word.

    A shaft set is a collection of 1-based shafts numbers
    for shafts that are up. If 0 is present, it is ignored.
    A shaft word is a bit mask, with bit 0 = shaft 1;
    if a bit is high, that shaft is up.
    """
    return sum(1 << shaft - 1 for shaft in shaft_set if shaft > 0)


def shaft_set_from_shaft_word(shaft_word: int) -> set[int]:
    """Convert a shaft word to a shaft set.

    See shaft_word_from_shaft_set for details.
    """
    bin_str = bin(shaft_word)[2:]
    return {i + 1 for i, bit in enumerate(reversed(bin_str)) if bit == "1"}
