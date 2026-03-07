import itertools

import pytest

from base_loom_server.utils import (
    bitmask_from_bits,
    bits_from_bitmask,
    compute_num_within_and_repeats,
    compute_total_num,
    get_version,
    prune_duplicates,
)


def test_bitmask_functions() -> None:
    # Bits are 1-based and values < 1 are ignored
    for bits, expected_bitmask in (
        ([], 0),
        ([1], 0b1),
        ([2], 0b10),
        ([3, 1], 0b101),
    ):
        bitmask = bitmask_from_bits(bits)
        assert bitmask == expected_bitmask

        bits_with_ignored_values = [0, -1, -2, -99, *bits, 0, -1, -2, -99]
        bitmask = bitmask_from_bits(bits_with_ignored_values)
        assert bitmask == expected_bitmask

        bits_with_repeated_values = bits + bits
        bitmask = bitmask_from_bits(bits_with_repeated_values)
        assert bitmask == expected_bitmask

        bits_round_trip = bits_from_bitmask(bitmask)
        assert isinstance(bits_round_trip, list)
        assert sorted(bits) == bits_round_trip

    for bitmask in (0xFFFFFFFFFF, 0x101010101010, 0xFFFFFFFF, 0xFFFFFFFE, 0xF1F1, 0xF, 0xE, 0x1, 0x0):
        bits = bits_from_bitmask(bitmask)
        assert bitmask == bitmask_from_bits(bits)


def test_compute_num_within_and_repeats() -> None:
    for num_within, repeat_number, repeat_len in itertools.product(
        (-50, -33, -1, 0, 1, 33, 50), (-1, 0, 1), (1, 21, 33, 50)
    ):
        total_num = compute_total_num(num_within, repeat_number, repeat_len)
        new_num_within, new_repeat_num = compute_num_within_and_repeats(
            total_num=total_num, repeat_len=repeat_len
        )
        assert total_num == compute_total_num(
            num_within=new_num_within,
            repeat_number=new_repeat_num,
            repeat_len=repeat_len,
        )
        if total_num == 0:
            assert new_num_within == 0
            assert new_repeat_num == 1
        else:
            assert 1 <= new_num_within <= repeat_len
            if 1 <= num_within <= repeat_len:
                assert num_within == new_num_within
                assert repeat_number == new_repeat_num

    for total_num in (-1, 0, 1):
        with pytest.raises(ValueError):
            compute_num_within_and_repeats(total_num, 0)

        with pytest.raises(ValueError):
            compute_num_within_and_repeats(total_num, -1)


def test_compute_total_num() -> None:
    for num_within, repeat_number, repeat_len in itertools.product(
        (-50, -33, -1, 0, 1, 33, 50), (-1, 0, 1), (1, 21, 33, 50)
    ):
        total_num = compute_total_num(num_within, repeat_number, repeat_len)
        assert total_num == (repeat_number - 1) * repeat_len + num_within

        with pytest.raises(ValueError):
            compute_total_num(num_within, repeat_number, 0)

        with pytest.raises(ValueError):
            compute_total_num(num_within, repeat_number, -1)


def test_get_version() -> None:
    assert get_version("#_invalid_package_name") == "?"

    try:
        from base_loom_server import version  # noqa: PLC0415
    except ImportError:
        assert get_version("base_loom_server") == "?"
    else:
        assert get_version("base_loom_server") == getattr(version, "__version__", "?")


def test_prune_duplicates() -> None:
    for data in (
        [],
        [1, 1, 1, 2, 3, 3, 0, 3, 2, -1, -1],
        [-1, 2, 0, 1],
        [0, 55, 55, 22, 22, -1, -1, 55],
    ):
        pruned_data = prune_duplicates(data)
        # compare to a different implementation
        desired_pruned_data: list[int] = []
        prev_val: int | None = None
        for end in data:
            if end != prev_val:
                prev_val = end
                desired_pruned_data.append(end)

        assert pruned_data == desired_pruned_data
