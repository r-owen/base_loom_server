def compute_num_within_and_repeats(total_num: int, repeat_len: int) -> tuple[int, int]:
    """Compute num_within and repeat_number from total_num and repeat_len
    such that total_num = (repeat_number - 1) * repeat_len + num_within.

    Args:
        total_num: Total count (e.g. picks or ends).
        repeat_len: Number of counts in one repeat; must be positive.

    Returns:
        A tuple consisting of:

        * num_within: Number of counts in range [1, repeat_len],
            or 0 if total_num == 0
        * repeat_num: 1 + number of full repeats (the first repeat has value 1)

    Raises:
        ValueError: If `repeat_len` ≤ 0.

    Notes:
        If total_num is 0 return (0, 0) because that is the most sensible
        thing to show when we haven't started weaving or threading.

        Otherwise, if total_num is exactly N repeats of repeat_len,
        return (repeat_len, N) rather than (0, N+1), because I want
        to display a pick or end that is in the pattern, rather
        than the mythical pick or repeat 0.
    """
    if repeat_len <= 0:
        raise ValueError(f"{repeat_len=} must be positive (or None)")

    zero_based_repeat_number, num_within = divmod(total_num, repeat_len)

    if num_within == 0 and total_num != 0:
        # Avoid num_within 0 unless total_num is also 0
        num_within = repeat_len
        zero_based_repeat_number -= 1

    return (num_within, zero_based_repeat_number + 1)


def compute_total_num(num_within: int, repeat_number: int, repeat_len: int) -> int:
    """Compute total_num from num_within, repeat_number, and repeat_len.

    This is basically the opposite of divmod, but handles None inputs
    and repeat_number is 1-based.

    Args:
        num_within: A value in range [-repeat_len, repeat_len].
        repeat_number: 1 + number of full repeats.
        repeat_len: Length of one repeat; must be positive or None.

    Returns:
        total_num = repeat_len * (repeat_number - 1) + num_within
    """
    if repeat_len <= 0:
        raise ValueError(f"{repeat_len=} must be positive (or None)")

    return repeat_len * (repeat_number - 1) + num_within
