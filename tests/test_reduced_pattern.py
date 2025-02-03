import copy
import dataclasses
import pathlib

import pytest

from base_loom_server.reduced_pattern import (
    Pick,
    ReducedPattern,
    read_full_pattern,
    reduced_pattern_from_pattern_data,
    shaft_set_from_shaft_word,
)

datadir = pathlib.Path(__file__).parent / "data"


def shaft_set_from_reduced(
    reduced_pattern: ReducedPattern, pick_number: int
) -> set[int]:
    """Get the shaft set for a specified 1-based pick_number."""
    reduced_pick = reduced_pattern.picks[pick_number - 1]
    return set(shaft_set_from_shaft_word(reduced_pick.shaft_word))


def test_basics() -> None:
    for filepath in list(datadir.glob("*.wif")) + list(datadir.glob("*.dtx")):
        full_pattern = read_full_pattern(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=filepath.name, data=full_pattern
        )

        assert reduced_pattern.type == "ReducedPattern"
        assert reduced_pattern.name == filepath.name
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.repeat_number == 1

        for pick_number, weft_color in full_pattern.weft_colors.items():
            assert weft_color - 1 == reduced_pattern.picks[pick_number - 1].color

        for end_number, warp_color in full_pattern.warp_colors.items():
            assert warp_color - 1 == reduced_pattern.warp_colors[end_number - 1]

        for end_number, shaft_set in full_pattern.threading.items():
            shaft_set -= {0}
            if len(shaft_set) > 1:
                shaft = max(shaft_set)
            else:
                shaft = shaft_set.pop()
            assert shaft - 1 == reduced_pattern.threading[end_number - 1]

        # Test ReducedPattern.picks
        if full_pattern.liftplan:
            assert len(full_pattern.liftplan) == len(reduced_pattern.picks)
            for pick_number, shaft_set_from_liftplan in full_pattern.liftplan.items():
                assert shaft_set_from_liftplan == shaft_set_from_reduced(
                    reduced_pattern=reduced_pattern, pick_number=pick_number
                )
        else:
            assert len(full_pattern.treadling) == len(reduced_pattern.picks)
            for pick_number, treadle_set in full_pattern.treadling.items():
                shaft_set_from_treadles: set[int] = set()
                for treadle in treadle_set - {0}:
                    shaft_set_from_treadles |= full_pattern.tieup[treadle]
                assert shaft_set_from_treadles == shaft_set_from_reduced(
                    reduced_pattern=reduced_pattern, pick_number=pick_number
                )


def test_from_dict() -> None:
    for filepath in list(datadir.glob("*.wif")) + list(datadir.glob("*.dtx")):
        full_pattern = read_full_pattern(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=filepath.name, data=full_pattern
        )
        patterndict = dataclasses.asdict(reduced_pattern)
        for i, pickdict in enumerate(patterndict["picks"]):
            assert isinstance(pickdict, dict)
            pick = Pick.from_dict(pickdict)
            assert pick == reduced_pattern.picks[i]

        round_trip_pattern = ReducedPattern.from_dict(patterndict)
        assert round_trip_pattern == reduced_pattern

        # test right type
        patterndict_righttype = copy.deepcopy(patterndict)
        patterndict_righttype["type"] = "ReducedPattern"
        pattern_righttype = ReducedPattern.from_dict(patterndict_righttype)
        assert pattern_righttype == reduced_pattern

        pickdict_righttype = copy.deepcopy(patterndict["picks"][0])
        pickdict_righttype["type"] = "Pick"
        pick_righttype = Pick.from_dict(pickdict_righttype)
        assert pick_righttype == reduced_pattern.picks[0]

        # test no type
        patterndict_notype = copy.deepcopy(patterndict)
        patterndict_notype.pop("type", None)
        pattern_notype = ReducedPattern.from_dict(patterndict_notype)
        assert pattern_notype == reduced_pattern

        pickdict_notype = copy.deepcopy(patterndict["picks"][0])
        pickdict_notype.pop("type", None)
        pick_notype = Pick.from_dict(pickdict_notype)
        assert pick_notype == reduced_pattern.picks[0]

        # test wrong type
        patterndict_wrongtype = copy.deepcopy(patterndict)
        patterndict_wrongtype["type"] = "NotReducedPattern"
        with pytest.raises(TypeError):
            ReducedPattern.from_dict(patterndict_wrongtype)

        pickdict_wrongtype = copy.deepcopy(patterndict["picks"][0])
        pickdict_wrongtype["type"] = "NotPick"
        with pytest.raises(TypeError):
            Pick.from_dict(pickdict_wrongtype)


def test_color_table() -> None:
    for filepath in list(datadir.glob("*.wif")) + list(datadir.glob("*.dtx")):
        full_pattern = read_full_pattern(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=filepath.name, data=full_pattern
        )
        assert full_pattern.color_range is not None
        min_color_from_full, max_color_from_full = full_pattern.color_range
        # Note: all test files include white and black colors,
        # so check that these are present before and after conversion.
        assert (min_color_from_full,) * 3 in full_pattern.color_table.values()
        assert (max_color_from_full,) * 3 in full_pattern.color_table.values()
        assert "#000000" in reduced_pattern.color_table
        assert "#ffffff" in reduced_pattern.color_table

        # Check all colors in the color table.
        assert full_pattern.color_table is not None
        assert full_pattern.color_range is not None
        min_full_color = full_pattern.color_range[0]
        full_color_scale = 255 / (
            full_pattern.color_range[1] - full_pattern.color_range[0]
        )
        for i, color in enumerate(reduced_pattern.color_table):
            assert color.startswith("#")
            assert len(color) == 7
            reduced_rgbstrs = [color[1 + 2 * rgbi : 3 + 2 * rgbi] for rgbi in range(3)]
            reduced_rgbvalues = [
                int(color_str, base=16) for color_str in reduced_rgbstrs
            ]
            full_rgbvalues = full_pattern.color_table[i + 1]
            expected_reduced_rgbvalues = [
                int((full_rgbvalues[rgbi] - min_full_color) * full_color_scale)
                for rgbi in range(3)
            ]
            assert reduced_rgbvalues == expected_reduced_rgbvalues
