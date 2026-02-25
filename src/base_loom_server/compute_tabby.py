from itertools import pairwise

# Minimum number of threaded shafts required to weave tabby
MIN_SHAFTS = 2


def compute_tabby_shaft_word1(threading: list[int]) -> int:
    """Compute which shafts should go up for the best tabby pick 1.

    The "best" tabby produces the greatest number of transitions between
    adjacent warp ends being up or down. More sophisticated definitions are possible,
    but this is simple and should almost always produce an acceptable tabby.

    Args:
        threading: List of 1-based shaft number for each warp end.
            Ends with shaft < 1 are ignored.

    Returns:
        shaft_word: Which shafts should be up for pick 1, 3, 5... of tabby.

    Raises:
        ValueError if there are fewer than 2 threaded warp ends,
            or if the warp ends are threaded on fewer than 2 different shafts.
    """
    threading_shaft_words = [1 << (shaft - 1) for shaft in threading if shaft > 0]
    if len(threading_shaft_words) < MIN_SHAFTS:
        raise ValueError(f"Invalid {threading=}: need at least two threaded warp ends to weave tabby.")
    if len(set(threading_shaft_words)) < MIN_SHAFTS:
        raise ValueError("Need at least two threaded shafts to weave tabby.")
    max_shaft_num = max(threading)
    best_shaft_word = 0
    best_num_transitions = 0
    for try_shaft_word in range(1, (1 << max_shaft_num) - 1):
        is_up_list = [bool(tsw & try_shaft_word) for tsw in threading_shaft_words]
        num_transitions = sum(1 for val1, val2 in pairwise(is_up_list) if val1 != val2)
        if num_transitions > best_num_transitions:
            best_num_transitions = num_transitions
            best_shaft_word = try_shaft_word
    return best_shaft_word


def compute_tabby_shaft_word2(tabby_shaft_word1: int, max_threaded_shaft: int) -> int:
    """Compute tabby_shaft_word2 as the complement of tabby_shaft_word1.

    Args:
        tabby_shaft_word1: tabby shaft word computed by compute_tabby_shaft_word1.
        max_threaded_shaft: max(threading); the maximum shaft number (1-based)
            that has any warp strings threaded on it. All bits beyond that
            will be 0.

    Returns:
        tabby_shaft_word2: which shafts should be up picks 2, 4, 6... of tabby.
            The complement tabby_shaft_word1, will all shafts beyond max_threaded_shaft
            set to 0.

    Raises:
        ValueError if max_threaded_shaft < 2.
    """
    if tabby_shaft_word1 < 1:
        raise ValueError(f"{tabby_shaft_word1=} must be positive")
    if max_threaded_shaft < MIN_SHAFTS:
        raise ValueError(f"{max_threaded_shaft=} must be > 1")
    all_shafts_mask = (1 << max_threaded_shaft) - 1
    return ~tabby_shaft_word1 & all_shafts_mask


def compute_tabby_shaft_words(threading: list[int]) -> tuple[int, int]:
    """Compute tabby_shaft_words 1 and 2.

    Args:
        threading: List of 1-based shaft number for each warp end.
            Ends with shaft < 1 are ignored.

    Returns:
        (shaft_word1, shaft_word2): Which shafts should be up for the two picks of tabby
            (word 1 is for picks 1, 3, 5.., word 2 is for picks 2, 4, 6...).

    Raises:
        ValueError if there are fewer than 2 threaded warp ends,
            or if the warp ends are threaded on fewer than 2 different shafts.
    """
    tabby_shaft_word1 = compute_tabby_shaft_word1(threading=threading)
    max_threaded_shaft = max(threading)
    tabby_shaft_word2 = compute_tabby_shaft_word2(
        tabby_shaft_word1=tabby_shaft_word1, max_threaded_shaft=max_threaded_shaft
    )
    return (tabby_shaft_word1, tabby_shaft_word2)
