import itertools

import pytest

from base_loom_server.utils import compute_num_within_and_repeats, compute_total_num


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
