import copy
import dataclasses

import pytest
from dtx_to_wif import read_pattern_file

from base_loom_server.compute_tabby import compute_tabby_shaft_words
from base_loom_server.reduced_pattern import (
    NUM_ITEMS_FOR_REPEAT_SEPARATOR,
    Pick,
    ReducedPattern,
    reduced_pattern_from_pattern_data,
)
from base_loom_server.testutils import ALL_PATTERN_PATHS
from base_loom_server.utils import bits_from_bitmask

# Dict of field name: default value
EXPECTED_DEFAULTS = dict(
    pick_number=0,
    pick_repeat_number=1,
    end_number0=0,
    end_number1=0,
    end_repeat_number=1,
)

EXPECTED_PICK_0 = Pick(shaft_word=0, color=0)


def test_basics() -> None:
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(name=filepath.name, data=full_pattern)

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
            assert full_pattern.weft_colors.get(i + 1, full_pattern.weft.color) == pick.color + 1

        for i, color in enumerate(reduced_pattern.warp_colors):
            assert full_pattern.warp_colors.get(i + 1, full_pattern.warp.color) == color + 1

        for end_number0, shaft_set in full_pattern.threading.items():
            pruned_shaft_set = shaft_set - {0}
            assert pruned_shaft_set
            shaft = max(pruned_shaft_set) if len(pruned_shaft_set) > 1 else pruned_shaft_set.pop()
            assert shaft - 1 == reduced_pattern.threading[end_number0 - 1]

        assert len(reduced_pattern.tabby_picks) == 2
        expected_tabby_shaft_words = compute_tabby_shaft_words(threading=reduced_pattern.threading)
        for i in range(2):
            assert reduced_pattern.tabby_picks[i].shaft_word == expected_tabby_shaft_words[i]

        # Test ReducedPattern.picks
        if full_pattern.liftplan:
            assert len(full_pattern.liftplan) == len(reduced_pattern.picks)
            for pick_number, shaft_set_from_liftplan in full_pattern.liftplan.items():
                pick = reduced_pattern.picks[pick_number - 1]
                shaft_set_from_pick = set(bits_from_bitmask(pick.shaft_word))
                assert shaft_set_from_liftplan == shaft_set_from_pick
        else:
            assert len(full_pattern.treadling) == len(reduced_pattern.picks)
            for pick_number, treadle_set in full_pattern.treadling.items():
                shaft_set_from_treadles: set[int] = set()
                for treadle in treadle_set - {0}:
                    shaft_set_from_treadles |= full_pattern.tieup[treadle]
                pick = reduced_pattern.picks[pick_number - 1]
                shaft_set_from_pick = set(bits_from_bitmask(pick.shaft_word))
                assert shaft_set_from_treadles == shaft_set_from_pick


def test_color_table() -> None:
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(name=filepath.name, data=full_pattern)
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
        full_color_scale = 255 / (full_pattern.color_range[1] - full_pattern.color_range[0])
        for i, color in enumerate(reduced_pattern.color_table):
            assert color.startswith("#")
            assert len(color) == 7
            reduced_rgbstrs = [color[1 + 2 * rgbi : 3 + 2 * rgbi] for rgbi in range(3)]
            reduced_rgbvalues = [int(color_str, base=16) for color_str in reduced_rgbstrs]
            full_rgbvalues = full_pattern.color_table[i + 1]
            expected_reduced_rgbvalues = [
                int((full_rgbvalues[rgbi] - min_full_color) * full_color_scale) for rgbi in range(3)
            ]
            assert reduced_rgbvalues == expected_reduced_rgbvalues


def test_from_dict() -> None:
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(name=filepath.name, data=full_pattern)
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
        pickdict_righttype["type"] = "Weft thread"
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
    group_size_numbers = (1, 2, 5)
    # Test with and without separating threading repeats; alternate cases
    separate_repeats = False
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(name=filepath.name, data=full_pattern)
        num_ends = len(reduced_pattern.threading)

        separate_repeats = not separate_repeats
        reduced_pattern.separate_threading_repeats = separate_repeats
        assert reduced_pattern.end_number0 == 0
        assert reduced_pattern.end_number1 == 0
        assert reduced_pattern.end_repeat_number == 1

        # Check invalid end_number0
        for end_number0 in (-1, num_ends + 1):
            with pytest.raises(IndexError):
                reduced_pattern.check_end_number(end_number0)
            for thread_group_size in group_size_numbers:
                reduced_pattern.thread_group_size = thread_group_size
                with pytest.raises(IndexError):
                    reduced_pattern.set_current_end_number(end_number0)
            assert reduced_pattern.end_number0 == 0
            assert reduced_pattern.end_repeat_number == 1

        # Check invalid end_number1
        for end_number0 in (0, 1, num_ends - 1, num_ends):
            for end_number1 in (-1, 0, end_number0 - 1, num_ends + 1):
                if end_number0 == 0 and end_number1 == 0:
                    continue
                for thread_group_size in group_size_numbers:
                    reduced_pattern.thread_group_size = thread_group_size
                    with pytest.raises(IndexError):
                        reduced_pattern.set_current_end_number(end_number0, end_number1=end_number1)
            assert reduced_pattern.end_number0 == 0
            assert reduced_pattern.end_repeat_number == 1

        # Check invalid thread_group_size
        initial_thread_group_size = reduced_pattern.thread_group_size
        for thread_group_size in (-1, 0):
            with pytest.raises(ValueError):
                reduced_pattern.thread_group_size = thread_group_size
            assert reduced_pattern.thread_group_size == initial_thread_group_size

        # Test set_current_end_number and get_threading_shaft_word
        for thread_group_size in group_size_numbers:
            reduced_pattern.thread_group_size = thread_group_size
            # Test get_threading_group
            for end_number0 in (0, 1, num_ends - 1, num_ends):
                reduced_pattern.set_current_end_number(end_number0=end_number0)
                if end_number0 == 0:
                    expected_end_number1 = 0
                elif end_number0 + thread_group_size > num_ends:
                    # + 1 because the range is [end_number0, end_number1)
                    # as is typical for ranges, and end_number is 1-based
                    expected_end_number1 = num_ends
                else:
                    expected_end_number1 = end_number0 + thread_group_size - 1

                assert reduced_pattern.end_number1 == expected_end_number1

                shaft_word = reduced_pattern.get_threading_shaft_word()
                if end_number0 == 0:
                    assert shaft_word == 0
                else:
                    expected_shaft_word = 0
                    shaft_set: set[int] = set()
                    for end_number in range(end_number0, expected_end_number1 + 1):
                        shaft_index = reduced_pattern.threading[end_number - 1]
                        if shaft_index < 0 or shaft_index in shaft_set:
                            continue
                        shaft_set.add(shaft_index)
                        expected_shaft_word += 1 << shaft_index
                    assert shaft_word == expected_shaft_word

        # Test compute_end_number and increment_end_number
        for thread_group_size in group_size_numbers:
            reduced_pattern.thread_group_size = thread_group_size

            # Use nominal_expected_end_number0 to avoid warnings
            # about overwriting a loop variable.
            for nominal_expected_end_number0 in (0, 1, num_ends - 1, num_ends):
                expected_end_number0 = nominal_expected_end_number0
                expected_repeat_number = 1
                reduced_pattern.set_current_end_number(
                    end_number0=expected_end_number0,
                    end_number1=None,
                    end_repeat_number=expected_repeat_number,
                )
                expected_end_number1 = reduced_pattern.end_number1
                assert reduced_pattern.end_number0 == expected_end_number0
                assert reduced_pattern.end_repeat_number == expected_repeat_number

                # Increment low to high through 3rd repeat
                while expected_repeat_number < 3:
                    if expected_end_number1 == num_ends:
                        # Start a new repeat
                        if separate_repeats:
                            expected_end_number0 = 0
                            expected_end_number1 = 0
                        else:
                            expected_end_number0 = 1
                            expected_end_number1 = min(num_ends, thread_group_size)
                        expected_repeat_number += 1
                    elif expected_end_number0 == 0:
                        expected_end_number0 = 1
                        expected_end_number1 = min(num_ends, thread_group_size)
                    else:
                        expected_end_number0 = min(num_ends, expected_end_number0 + thread_group_size)
                        expected_end_number1 = min(num_ends, expected_end_number0 + thread_group_size - 1)
                    assert (
                        expected_end_number0,
                        expected_end_number1,
                        expected_repeat_number,
                    ) == reduced_pattern.compute_next_end_numbers(thread_low_to_high=True)
                    reduced_pattern.increment_end_number(thread_low_to_high=True)
                    assert reduced_pattern.end_number0 == expected_end_number0
                    assert reduced_pattern.end_number1 == expected_end_number1
                    assert reduced_pattern.end_repeat_number == expected_repeat_number

                # Increment to beginning
                while True:
                    if expected_end_number0 == 0 and expected_repeat_number == 1:
                        break

                    if expected_end_number0 == 1 and expected_repeat_number == 1 and not separate_repeats:
                        # Special case; go to end_number0 = 0,
                        # even though not separating repeats.
                        expected_end_number0 = 0
                        expected_end_number1 = 0
                    elif expected_end_number0 == 1 and separate_repeats:
                        expected_end_number0 = 0
                        expected_end_number1 = 0
                    elif (expected_end_number0 == 0 and separate_repeats) or (
                        expected_end_number0 == 1 and not separate_repeats
                    ):
                        expected_end_number0 = max(1, num_ends + 1 - thread_group_size)
                        expected_end_number1 = min(num_ends, expected_end_number0 + thread_group_size - 1)
                        expected_repeat_number -= 1
                    else:
                        expected_end_number1 = expected_end_number0 - 1
                        expected_end_number0 = max(1, expected_end_number0 - thread_group_size)
                    assert (
                        expected_end_number0,
                        expected_end_number1,
                        expected_repeat_number,
                    ) == reduced_pattern.compute_next_end_numbers(thread_low_to_high=False)
                    reduced_pattern.increment_end_number(thread_low_to_high=False)
                    assert reduced_pattern.end_number0 == expected_end_number0
                    assert reduced_pattern.end_number1 == expected_end_number1
                    assert reduced_pattern.end_repeat_number == expected_repeat_number

                # Sanity-check the backwards loop
                assert reduced_pattern.end_number0 == 0
                assert reduced_pattern.end_number1 == 0
                assert reduced_pattern.end_repeat_number == 1

                # At the beginning; test going past it
                with pytest.raises(IndexError):
                    reduced_pattern.compute_next_end_numbers(thread_low_to_high=False)
                with pytest.raises(IndexError):
                    reduced_pattern.increment_end_number(thread_low_to_high=False)
                assert reduced_pattern.pick_number == 0
                assert reduced_pattern.pick_repeat_number == 1
                assert reduced_pattern.tabby_pick_number == 0
                assert reduced_pattern.end_number0 == 0
                assert reduced_pattern.end_number1 == 0
                assert reduced_pattern.end_repeat_number == 1


def test_pick_number() -> None:
    # Test with and without separating weaving repeats; alternate cases
    separate_repeats = False
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(name=filepath.name, data=full_pattern)
        separate_repeats = not separate_repeats
        reduced_pattern.separate_weaving_repeats = separate_repeats

        num_picks = len(reduced_pattern.picks)

        # Test check_pick_number, set_current_pick_number, and get_pick
        # on some bad values
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.pick_repeat_number == 1
        for pick_number in (-1, num_picks + 1):
            with pytest.raises(IndexError):
                reduced_pattern.check_pick_number(pick_number)
            with pytest.raises(IndexError):
                reduced_pattern.set_current_pick_number(pick_number)
            with pytest.raises(IndexError):
                reduced_pattern.get_pick(pick_number=pick_number)
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.pick_repeat_number == 1

        # Test check_pick_number and set_current_pick_number,
        # get_pick, and get_current_pick on some good values.
        for pick_number in (0, 1, num_picks - 1, num_picks):
            reduced_pattern.check_pick_number(pick_number)
            reduced_pattern.set_current_pick_number(pick_number)
            assert reduced_pattern.pick_number == pick_number
            assert reduced_pattern.pick_repeat_number == 1
            pick = reduced_pattern.get_pick(pick_number=pick_number)
            current_pick = reduced_pattern.get_current_pick()
            assert pick == current_pick
            if pick_number == 0:
                assert pick == EXPECTED_PICK_0
            else:
                assert pick == reduced_pattern.picks[pick_number - 1]

        # Go forward into repeat 3
        expected_pick_number = 0
        expected_repeat_number = 1
        reduced_pattern.set_current_pick_number(pick_number=expected_pick_number)
        reduced_pattern.pick_repeat_number = expected_repeat_number
        while expected_repeat_number < 3:
            expected_pick_number += 1
            if expected_pick_number > num_picks:
                expected_pick_number = 0 if separate_repeats else 1
                expected_repeat_number += 1
            assert (
                expected_pick_number,
                expected_repeat_number,
            ) == reduced_pattern.compute_next_pick_numbers(direction_forward=True)

            reduced_pattern.increment_pick_number(direction_forward=True)
            assert reduced_pattern.pick_number == expected_pick_number
            assert reduced_pattern.pick_repeat_number == expected_repeat_number

        # Go backwards to the beginning
        while True:
            if expected_pick_number == 0 and expected_repeat_number == 1:
                break

            if expected_pick_number == 1 and expected_repeat_number == 1 and not separate_repeats:
                # Special case: add separator at beginning,
                # even though we don't separate
                expected_pick_number = 0
            elif (expected_pick_number == 0 and separate_repeats) or (
                expected_pick_number == 1 and not separate_repeats
            ):
                expected_pick_number = num_picks
                expected_repeat_number -= 1
            else:
                expected_pick_number -= 1
            assert (
                expected_pick_number,
                expected_repeat_number,
            ) == reduced_pattern.compute_next_pick_numbers(direction_forward=False)

            reduced_pattern.increment_pick_number(direction_forward=False)
            assert reduced_pattern.pick_number == expected_pick_number
            assert reduced_pattern.pick_repeat_number == expected_repeat_number

            pick = reduced_pattern.get_pick(pick_number=expected_pick_number)
            assert pick == reduced_pattern.get_current_pick()
            if expected_pick_number == 0:
                assert pick == EXPECTED_PICK_0
            else:
                assert pick == reduced_pattern.picks[expected_pick_number - 1]

        # Sanity-check the backwards loop
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.pick_repeat_number == 1

        # At the beginning; try to go past it
        with pytest.raises(IndexError):
            reduced_pattern.compute_next_pick_numbers(direction_forward=False)
        with pytest.raises(IndexError):
            reduced_pattern.increment_pick_number(direction_forward=False)
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.pick_repeat_number == 1
        assert reduced_pattern.tabby_pick_number == 0
        assert reduced_pattern.end_number0 == 0
        assert reduced_pattern.end_number1 == 0
        assert reduced_pattern.end_repeat_number == 1


def test_tabby_pick_number() -> None:
    for filepath in ALL_PATTERN_PATHS:
        full_pattern = read_pattern_file(filepath)
        reduced_pattern = reduced_pattern_from_pattern_data(name=filepath.name, data=full_pattern)

        # Test check_tabby_pick_number, set_current_tabby_pick_number, and get_tabby_pick
        # on some bad values
        assert reduced_pattern.tabby_pick_number == 0
        for tabby_pick_number in (-1, -2, -10):
            with pytest.raises(IndexError):
                reduced_pattern.set_current_tabby_pick_number(tabby_pick_number)
            with pytest.raises(IndexError):
                reduced_pattern.get_tabby_pick(tabby_pick_number=tabby_pick_number)
        assert reduced_pattern.tabby_pick_number == 0

        # Test check_tabby_pick_number and set_current_tabby_pick_number,
        # get_tabby_pick, and get_current_tabby_pick on some good values.
        for tabby_pick_number in (0, 1, 2, 99, 100):
            reduced_pattern.set_current_tabby_pick_number(tabby_pick_number)
            assert reduced_pattern.tabby_pick_number == tabby_pick_number
            tabby_pick = reduced_pattern.get_tabby_pick(tabby_pick_number=tabby_pick_number)
            current_tabby_pick = reduced_pattern.get_current_tabby_pick()
            assert tabby_pick == current_tabby_pick
            tabby_pick_index = (tabby_pick_number + 1) % 2
            if tabby_pick_number == 0:
                assert tabby_pick == EXPECTED_PICK_0
            else:
                assert tabby_pick == reduced_pattern.tabby_picks[tabby_pick_index]

        # Go forward for awhile
        reduced_pattern.set_current_tabby_pick_number(tabby_pick_number=0)
        for expected_tabby_pick_number in range(1, 10):
            reduced_pattern.increment_tabby_pick_number(direction_forward=True)
            assert reduced_pattern.tabby_pick_number == expected_tabby_pick_number

        # Go backwards to the beginning
        while expected_tabby_pick_number > 0:
            expected_tabby_pick_number -= 1
            reduced_pattern.increment_tabby_pick_number(direction_forward=False)
            assert reduced_pattern.tabby_pick_number == expected_tabby_pick_number
            tabby_pick = reduced_pattern.get_tabby_pick(tabby_pick_number=expected_tabby_pick_number)
            assert tabby_pick == reduced_pattern.get_current_tabby_pick()
            tabby_pick_index = (expected_tabby_pick_number + 1) % 2
            if expected_tabby_pick_number == 0:
                assert tabby_pick == EXPECTED_PICK_0
            else:
                assert tabby_pick == reduced_pattern.tabby_picks[tabby_pick_index]

        # Sanity-check the backwards loop
        assert reduced_pattern.tabby_pick_number == 0

        # At the beginning; try to back up further
        with pytest.raises(IndexError):
            reduced_pattern.increment_tabby_pick_number(direction_forward=False)

        assert reduced_pattern.tabby_pick_number == 0
        assert reduced_pattern.pick_number == 0
        assert reduced_pattern.pick_repeat_number == 1
        assert reduced_pattern.end_number0 == 0
        assert reduced_pattern.end_number1 == 0
        assert reduced_pattern.end_repeat_number == 1
