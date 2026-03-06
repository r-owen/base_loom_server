import pytest

from base_loom_server.compute_tabby import (
    compute_num_transitions,
    compute_tabby_shaft_word1,
    compute_tabby_shaft_word2,
    compute_tabby_shaft_words,
)

# Dict of field name: default value
EXPECTED_DEFAULTS = dict(
    pick_number=0,
    pick_repeat_number=1,
    end_number0=0,
    end_number1=0,
    end_repeat_number=1,
)


def test_known_values() -> None:
    """Get the shaft set for a specified 1-based pick_number."""
    # Explicit values use 1-based shafts, for readability,
    # but internally the threading array uses 0-based shafts.
    for threading_1based, expected_shaft_word1, expected_shaft_word2, expected_num_transitions in (
        # Fully interlaced
        ([1, 2], 0b10, 0b01, 0),
        ([1, 2, 3, 4, 3, 2, 1], 0b1010, 0b0101, 0),
        ([1, 2, 3, 4, 1, 2, 3], 0b1010, 0b0101, 0),
        ([4, 3, 2, 1, 2, 3, 4], 0b1010, 0b0101, 0),
        ([2, 3, 4, 5, 4, 3, 2], 0b01010, 0b10101, 0),
        ([3, 4, 5, 6, 5, 4, 3], 0b010100, 0b101011, 0),
        ([1, 10, 3, 6], 0b1000100000, 0b0111011111, 0),
        ([2, 5, 4, 9], 0b000001010, 0b111110101, 0),
        ([2, 1, 2, 3, 4, 5], 0b01010, 0b10101, 0),
        # Some repeating warp ends; ignoring those
        # the fabric is fully interlaced.
        ([6, 5, 4, 3, 3, 4, 5], 0b101000, 0b010111, 5),
        ([5, 4, 3, 2, 2, 3, 4], 0b10100, 0b01011, 5),
        ([1, 1, 2, 2], 0b10, 0b01, 1),
        ([1, 1, 1, 2, 2, 3, 3, 3], 0b010, 0b101, 2),
        # Overshot (perfect interlacemet)
        ([1, 2, 1, 2, 3, 2, 3, 4, 3, 4, 1, 4, 1], 0b1010, 0b0101, 0),
        # Bronson lace (perfect interlacemet)
        ([1, 2, 1, 2, 1, 3, 1, 3, 1, 4, 1, 4], 0b1110, 0b0001, 0),
        # Canvas weave
        ([1, 2, 2, 1, 4, 3, 3, 4], 0b1010, 0b0101, 5),
        # Non-trivial cases. The even warp ends and odd warp ends
        # are not on unique sets of shafts (after purging repeating shafts).
        # These are the only test cases that exercise the
        # non-simple branch of the algorithm.
        ([1, 2, 3, 1, 2, 3], 0b101, 0b010, 4),
        ([1, 2, 4, 2, 3, 1], 0b0011, 0b1100, 4),
    ):
        threading = [shaft - 1 for shaft in threading_1based]
        if expected_num_transitions == 0:
            expected_num_transitions = len(threading) - 1  # noqa: PLW2901

        tabby_shaft_word1 = compute_tabby_shaft_word1(threading=threading)
        tabby_shaft_word2 = compute_tabby_shaft_word2(
            tabby_shaft_word1=tabby_shaft_word1, threading=threading
        )
        num_transitions = compute_num_transitions(tabby_shaft_word1, threading=threading)

        assert tabby_shaft_word1 == expected_shaft_word1
        assert tabby_shaft_word2 == expected_shaft_word2
        assert num_transitions == expected_num_transitions

        assert expected_shaft_word1, expected_shaft_word2 == compute_tabby_shaft_words(threading)


def test_invalid_values() -> None:
    # Use 0-based threading here, as readability is less important
    for threading in (
        # Need at least two threaded warp ends
        [],
        [0],
        [1],
        # Need at least two different threaded shafts
        [0, 0],
        [1, 1],
        [5, 5],
    ):
        with pytest.raises(ValueError):
            compute_tabby_shaft_word1(threading=threading)
        with pytest.raises(ValueError):
            compute_tabby_shaft_words(threading=threading)
        if len(threading) == 0:
            # No warp ends are threaded
            with pytest.raises(ValueError):
                compute_tabby_shaft_word2(tabby_shaft_word1=0b1, threading=threading)
        else:
            # Raise no shafts on tabby 1
            with pytest.raises(ValueError):
                compute_tabby_shaft_word2(tabby_shaft_word1=0, threading=threading)

            # Raise all shafts on tabby 1, so none are raised on tabby 2
            max_threaded_shaft_number = max(threading) + 1
            all_shafts_up = 2**max_threaded_shaft_number - 1
            with pytest.raises(ValueError):
                compute_tabby_shaft_word2(tabby_shaft_word1=all_shafts_up, threading=threading)
