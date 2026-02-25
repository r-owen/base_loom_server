import itertools

import pytest

from base_loom_server.compute_tabby import (
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
    for threading, expected_shaft_word1, expected_shaft_word2 in (
        # Alternating even and odd
        ([1, 2], 0b01, 0b10),
        ([1, 2, 3, 4, 3, 2, 1], 0b0101, 0b1010),
        ([1, 2, 3, 4, 1, 2, 3], 0b0101, 0b1010),
        ([4, 3, 2, 1, 2, 3, 4], 0b0101, 0b1010),
        ([2, 3, 4, 5, 4, 3, 2], 0b01010, 0b10101),
        ([5, 4, 3, 2, 2, 3, 4], 0b01010, 0b10101),
        ([3, 4, 5, 6, 5, 4, 3], 0b010100, 0b101011),
        ([6, 5, 4, 3, 3, 4, 5], 0b010100, 0b101011),
        ([2, 1, 2, 3, 4, 5], 0b01010, 0b10101),
        ([1, 10, 3, 6], 0b0000000101, 0b1111111010),
        ([2, 5, 4, 9], 0b000001010, 0b111110101),
        # No true tabby available
        ([1, 1, 2, 2], 0b01, 0b10),
        ([1, 1, 1, 2, 2, 3, 3, 3], 0b010, 0b101),
    ):
        tabby_shaft_word1 = compute_tabby_shaft_word1(threading=threading)
        assert tabby_shaft_word1 == expected_shaft_word1
        max_threaded_shaft = max(threading)
        tabby_shaft_word2 = compute_tabby_shaft_word2(
            tabby_shaft_word1=tabby_shaft_word1, max_threaded_shaft=max_threaded_shaft
        )
        assert tabby_shaft_word2 == expected_shaft_word2
        assert compute_tabby_shaft_words(threading=threading) == (expected_shaft_word1, expected_shaft_word2)


def test_invalid_values() -> None:
    for threading in (
        # Need at least two threaded warp ends
        [],
        [0],
        [1],
        [0, 0],
        [0, 1],
        [1, 0],
        # Need at least two different threaded shafts
        [1, 1],
        [5, 5],
    ):
        with pytest.raises(ValueError):
            compute_tabby_shaft_word1(threading=threading)
        with pytest.raises(ValueError):
            compute_tabby_shaft_words(threading=threading)

    for tabby_shaft_word1, max_threaded_shaft in itertools.product((-1, 0, 1, 2), (-1, 0, 1, 2, 3)):
        if tabby_shaft_word1 > 0 and max_threaded_shaft > 1:
            # A valid combination
            continue
        with pytest.raises(ValueError):
            compute_tabby_shaft_word2(
                tabby_shaft_word1=tabby_shaft_word1, max_threaded_shaft=max_threaded_shaft
            )
