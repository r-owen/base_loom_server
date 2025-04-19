import copy
import dataclasses

import pytest
from dtx_to_wif import read_pattern_file

from base_loom_server.reduced_pattern import (
    NUM_ITEMS_FOR_REPEAT_SEPARATOR,
    Pick,
    ReducedPattern,
    reduced_pattern_from_pattern_data,
    shaft_set_from_shaft_word,
)
from base_loom_server.testutils import ALL_PATTERN_PATHS

# Dict of field name: default value
EXPECTED_DEFAULTS = dict(
    pick_number=0,
    pick_repeat_number=1,
    end_number0=0,
    end_number1=0,
    end_repeat_number=1,
)


def shaft_set_from_reduced(
    reduced_pattern: ReducedPattern, pick_number: int
) -> set[int]:
    """Get the shaft set for a specified 1-based pick_number."""
    reduced_pick = reduced_pattern.picks[pick_number - 1]
    return set(shaft_set_from_shaft_word(reduced_pick.shaft_word))


def test_basics() -> None:
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=filepath.name, data=full_pattern
        )

        assert reduced_pattern.type == "ReducedPattern"
        assert reduced_pattern.name == filepath.name
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.pick_repeat_number == 1

        # Check default values for specific fields
        for field_name, value in EXPECTED_DEFAULTS.items():
            assert getattr(reduced_pattern, field_name) == value
        assert reduced_pattern.separate_weaving_repeats == (
            len(reduced_pattern.picks) > NUM_ITEMS_FOR_REPEAT_SEPARATOR
        )
        assert reduced_pattern.separate_threading_repeats == (
            len(reduced_pattern.threading) > NUM_ITEMS_FOR_REPEAT_SEPARATOR
        )

        for i, pick in enumerate(reduced_pattern.picks):
            assert (
                full_pattern.weft_colors.get(i + 1, full_pattern.weft.color)
                == pick.color + 1
            )

        for i, color in enumerate(reduced_pattern.warp_colors):
            assert (
                full_pattern.warp_colors.get(i + 1, full_pattern.warp.color)
                == color + 1
            )

        for end_number0, shaft_set in full_pattern.threading.items():
            shaft_set -= {0}
            if len(shaft_set) > 1:
                shaft = max(shaft_set)
            else:
                shaft = shaft_set.pop()
            assert shaft - 1 == reduced_pattern.threading[end_number0 - 1]

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


def test_color_table() -> None:
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
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


def test_from_dict() -> None:
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
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


def test_end_number() -> None:
    GROUP_SIZE_NUMBERS = (1, 2, 5)
    # Test with and without separating threading repeats; alternate cases
    separate_repeats = False
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=filepath.name, data=full_pattern
        )
        separate_repeats = not separate_repeats
        reduced_pattern.separate_threading_repeats = separate_repeats
        num_ends = len(reduced_pattern.threading)
        NUM_ITER = 2
        assert num_ends > NUM_ITER  # for some tests below to work
        assert reduced_pattern.end_number0 == 0
        assert reduced_pattern.end_repeat_number == 1

        # Check invalid end_number0
        for end_number0 in (-1, num_ends + 1):
            with pytest.raises(IndexError):
                reduced_pattern.check_end_number(end_number0)
            for thread_group_size in GROUP_SIZE_NUMBERS:
                reduced_pattern.thread_group_size = thread_group_size
                with pytest.raises(IndexError):
                    reduced_pattern.set_current_end_number(end_number0)
            assert reduced_pattern.end_number0 == 0
            assert reduced_pattern.end_repeat_number == 1

        # Check invalid end_number1
        for end_number0 in (0, 1, num_ends - 1, num_ends):
            for end_number1 in (-1, 0, end_number0, num_ends + 2):
                if end_number0 == 0 and end_number1 == 0:
                    continue
                for thread_group_size in GROUP_SIZE_NUMBERS:
                    reduced_pattern.thread_group_size = thread_group_size
                    with pytest.raises(IndexError):
                        reduced_pattern.set_current_end_number(
                            end_number0,
                            end_number1=end_number1,
                        )
            assert reduced_pattern.end_number0 == 0
            assert reduced_pattern.end_repeat_number == 1

        # Check invalid thread_group_size
        initial_thread_group_size = reduced_pattern.thread_group_size
        for thread_group_size in (-1, 0):
            with pytest.raises(ValueError):
                reduced_pattern.thread_group_size = thread_group_size
            assert reduced_pattern.thread_group_size == initial_thread_group_size

        for thread_group_size in GROUP_SIZE_NUMBERS:
            reduced_pattern.thread_group_size = thread_group_size
            # Test get_threading_group
            for end_number0 in (0, 1, num_ends - 1, num_ends):
                reduced_pattern.set_current_end_number(end_number0=end_number0)
                if end_number0 == 0:
                    expected_end_number1 = 0
                elif end_number0 + thread_group_size > num_ends:
                    # + 1 because the range is [end_number0, end_number1)
                    # as is typical for ranges, and end_number is 1-based
                    expected_end_number1 = num_ends + 1
                else:
                    expected_end_number1 = end_number0 + thread_group_size

                assert reduced_pattern.end_number1 == expected_end_number1

                shaft_word = reduced_pattern.get_threading_shaft_word()
                expected_shaft_word = 0
                shaft_set: set[int] = set()
                for end_number in range(end_number0, expected_end_number1):
                    shaft_index = reduced_pattern.threading[end_number - 1]
                    if shaft_index < 0 or shaft_index in shaft_set:
                        continue
                    shaft_set.add(shaft_index)
                    expected_shaft_word += 1 << shaft_index
                assert shaft_word == expected_shaft_word

            for initial_end_number0 in (0, 1, num_ends - 1, num_ends):
                # Increment low to high
                reduced_pattern.thread_group_size = thread_group_size
                reduced_pattern.set_current_end_number(
                    end_number0=initial_end_number0,
                    end_repeat_number=1,
                )
                reduced_pattern.increment_end_number(thread_low_to_high=True)
                if initial_end_number0 == 0:
                    # The next group starts at one,
                    # regardless of thread_group_size
                    assert reduced_pattern.end_number0 == 1
                    assert reduced_pattern.end_repeat_number == 1
                elif initial_end_number0 + thread_group_size > num_ends:
                    # The group extends past the end, so reset to 0 or 1
                    # depending on separate_threading_repeats
                    assert reduced_pattern.end_number0 == 0 if separate_repeats else 1
                    assert reduced_pattern.end_repeat_number == 2
                else:
                    assert (
                        reduced_pattern.end_number0
                        == initial_end_number0 + thread_group_size
                    )
                    assert reduced_pattern.end_repeat_number == 1

                # Increment high to low
                reduced_pattern.thread_group_size = thread_group_size
                reduced_pattern.set_current_end_number(
                    initial_end_number0,
                    end_repeat_number=1,
                )
                reduced_pattern.increment_end_number(thread_low_to_high=False)
                if initial_end_number0 == 0 or (
                    initial_end_number0 == 1 and not separate_repeats
                ):
                    # The next group ends at num_ends + 1
                    # and repeat_number is decremented,
                    # regardless of thread_group_size
                    assert reduced_pattern.end_number1 == num_ends + 1
                    assert reduced_pattern.end_number0 == max(
                        reduced_pattern.end_number1 - thread_group_size, 1
                    )
                    assert reduced_pattern.end_repeat_number == 0
                elif initial_end_number0 == 1:
                    assert reduced_pattern.end_number0 == 0
                    assert reduced_pattern.end_number1 == 0
                    assert reduced_pattern.end_repeat_number == 1
                elif initial_end_number0 > thread_group_size:
                    assert (
                        reduced_pattern.end_number0
                        == initial_end_number0 - thread_group_size
                    )
                    assert (
                        reduced_pattern.end_number1
                        == reduced_pattern.end_number0 + thread_group_size
                    )
                    assert reduced_pattern.end_repeat_number == 1
                else:
                    assert reduced_pattern.end_number0 == max(
                        initial_end_number0 - thread_group_size, 1
                    )
                    assert reduced_pattern.end_number1 == initial_end_number0
                    assert reduced_pattern.end_repeat_number == 1

            for end_number1 in (initial_end_number0 + 1, num_ends + 1):
                for end_repeat_number in (-1, 0, 5):
                    if end_number1 > num_ends + 1:
                        continue
                    reduced_pattern.thread_group_size = thread_group_size
                    reduced_pattern.set_current_end_number(
                        end_number0=initial_end_number0,
                        end_number1=end_number1,
                        end_repeat_number=end_repeat_number,
                    )
                    assert reduced_pattern.end_number0 == initial_end_number0
                    assert reduced_pattern.end_number1 == end_number1
                    assert reduced_pattern.end_repeat_number == end_repeat_number


def test_pick_number() -> None:
    # Test with and without separating weaving repeats; alternate cases
    separate_repeats = False
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(
            name=filepath.name, data=full_pattern
        )
        separate_repeats = not separate_repeats
        reduced_pattern.separate_weaving_repeats = separate_repeats
        num_picks = len(reduced_pattern.picks)
        NUM_ITER = 3
        assert num_picks > NUM_ITER  # for some tests below to work
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.pick_repeat_number == 1
        for pick_number in (-1, num_picks + 1):
            with pytest.raises(IndexError):
                reduced_pattern.check_pick_number(pick_number)
            with pytest.raises(IndexError):
                reduced_pattern.set_current_pick_number(pick_number)
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.pick_repeat_number == 1
        for pick_number in (0, 1, num_picks - 1, num_picks):
            reduced_pattern.check_pick_number(pick_number)
            reduced_pattern.set_current_pick_number(pick_number)
            assert reduced_pattern.pick_number == pick_number
            assert reduced_pattern.pick_repeat_number == 1

        # Go forward, but not past the end,
        # then back up to the beginning (0 if separating repeats, else 1)
        # then back up past the beginning
        reduced_pattern.set_current_pick_number(0)
        for i in range(NUM_ITER):
            returned_pick_number = reduced_pattern.increment_pick_number(
                weave_forward=True
            )
            assert returned_pick_number == i + 1
            assert reduced_pattern.pick_number == returned_pick_number
            assert reduced_pattern.pick_repeat_number == 1
        end_num = 0 if separate_repeats else 1
        for i in range(NUM_ITER, end_num, -1):
            reduced_pattern.increment_pick_number(weave_forward=False)
            assert reduced_pattern.pick_number == i - 1
            assert reduced_pattern.pick_repeat_number == 1
        for i in range(NUM_ITER):
            reduced_pattern.increment_pick_number(weave_forward=False)
            assert reduced_pattern.pick_number == num_picks - i
            assert reduced_pattern.pick_repeat_number == 0

        # Go backwards from the end, but not past the beginning,
        # then go fowards to the end,
        # then go past the end
        reduced_pattern.set_current_pick_number(num_picks)
        for i in range(NUM_ITER):
            returned_pick_number = reduced_pattern.increment_pick_number(
                weave_forward=False
            )
            assert returned_pick_number == num_picks - i - 1
            assert reduced_pattern.pick_number == returned_pick_number
            assert reduced_pattern.pick_repeat_number == 0
        for i in range(NUM_ITER, 0, -1):
            reduced_pattern.increment_pick_number(weave_forward=True)
            assert reduced_pattern.pick_number == 1 + num_picks - i
            assert reduced_pattern.pick_repeat_number == 0
        offset = 0 if separate_repeats else 1
        for i in range(NUM_ITER):
            reduced_pattern.increment_pick_number(weave_forward=True)
            assert reduced_pattern.pick_number == i + offset
            assert reduced_pattern.pick_repeat_number == 1
