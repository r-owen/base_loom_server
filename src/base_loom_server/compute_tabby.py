from itertools import pairwise

# Maximum starting points for walking through the threading
# in compute_tabby_shaft_word1. This keeps the compute time sane.
MAX_ITER = 5


def compute_num_transitions(tabby_shaft_word: int, threading: list[int]) -> int:
    """Compute the number of transitions produced by a tabby shaft word.

    The largest possible value is len(threading_shaft_words) - 1.

    Args:
        tabby_shaft_word: Tabby shaft word.
        threading: 0-based shaft number for each warp end.
    """
    threading_shaft_words = [1 << shaft for shaft in threading]
    return _basic_compute_num_transitions(
        tabby_shaft_word=tabby_shaft_word, threading_shaft_words=threading_shaft_words
    )


def _basic_compute_num_transitions(tabby_shaft_word: int, threading_shaft_words: list[int]) -> int:
    """Implementation of compute_num_transitions.

    Args:
        tabby_shaft_word: Tabby shaft word.
        threading_shaft_words: Shaft word for each warp end.
    """
    is_up_list = [bool(tsw & tabby_shaft_word) for tsw in threading_shaft_words]
    return sum(1 for val1, val2 in pairwise(is_up_list) if val1 != val2)


def compute_tabby_shaft_word1(threading: list[int]) -> int:
    """Compute which shaft_set should go up for the best tabby pick 1.

    Args:
        threading: 0-based shaft number for each warp end.

    Returns:
        shaft_word: Which shaft_set should be up for pick 1, 3, 5... of tabby.

    Raises:
        ValueError if there are fewer than 2 threaded warp ends,
            or if the warp ends are threaded on fewer than 2 different shaft_set.

    Notes:
        The algorithm is as follows:

        Make a pruned version of the threading with no no repeating ends.

        Check the most common case: if all even (pruned) warp ends
        are threaded on a separate set of shafts than all odd warp ends,
        (a case that allows optimal interlacement) then return
        a tabby shaft word that raises every shaft in the odd warp ends set.

        If that fails, use a harder and less ideal algorithm:
        Loop through the (pruned) warp ends. For each shaft that
        has not been seen before, append it to a list of seen shafts.
        Then make a tabby shaft word that raises every other shaft
        of the seen shafts.

        Try this several times, from different starting points
        in the threading, and pick the tabby shaft word that gives
        the most consecutive transitions.
    """
    if len(threading) <= 1:
        raise ValueError("Need at least 2 threaded warp ends to weave tabby.")
    num_threaded_shafts = len(set(threading))
    if num_threaded_shafts <= 1:
        raise ValueError("Need at least 2 threaded shafts to weave tabby.")

    # Prune repeating duplicate ends
    pruned_threading: list[int] = []
    prev_end = 0
    for end in threading:
        if end != prev_end:
            prev_end = end
            pruned_threading.append(end)

    # Try the common case that the odd warp ends are on one set of shafts
    # and the even warp ends are on another set of shafts, with no overlap
    odd_ends_shaft_set = set(pruned_threading[::2])
    even_ends_shaft_set = set(pruned_threading[1::2])
    if even_ends_shaft_set & odd_ends_shaft_set == set():
        tabby_shaft_word = 0
        for shaft in odd_ends_shaft_set:
            tabby_shaft_word |= 1 << shaft
        return tabby_shaft_word

    # Try the harder and less ideal algorithm.
    optimal_num_transitions = len(pruned_threading) - 1
    threading_shaft_words = [1 << shaft for shaft in threading]

    # Try starting at several different points in the threading,
    # in order to get a somewhat better result.
    best_num_transitions = 0
    best_tabby_shaft_word = 0
    num_threads = len(pruned_threading)
    start_interval = ((num_threads - 1) // MAX_ITER) + 1
    if num_threads < MAX_ITER * 2:
        # Not many threads; don't worry about limiting the number of iterations.
        start_interval = 1
    niter = 0
    for start_index in range(0, num_threads, start_interval):
        niter += 1
        seen_shaft_set: set[int] = set()
        seen_shaft_arr: list[int] = []
        for shaft in pruned_threading[start_index:] + pruned_threading[:start_index]:
            if shaft in seen_shaft_set:
                continue
            seen_shaft_set.add(shaft)
            seen_shaft_arr.append(shaft)
            if len(seen_shaft_set) == num_threaded_shafts:
                # We have seen all the shafts; stop
                break

        tabby_shaft_word = 0
        for shaft in seen_shaft_arr[::2]:
            tabby_shaft_word |= 1 << shaft

        num_transitions = _basic_compute_num_transitions(
            tabby_shaft_word=tabby_shaft_word, threading_shaft_words=threading_shaft_words
        )
        if num_transitions > best_num_transitions:
            best_num_transitions = num_transitions
            best_tabby_shaft_word = tabby_shaft_word
            if num_transitions == optimal_num_transitions:
                # As good as it gets
                break
    return best_tabby_shaft_word


def compute_tabby_shaft_word2(tabby_shaft_word1: int, threading: list[int]) -> int:
    """Compute tabby_shaft_word2 as the complement of tabby_shaft_word1.

    Args:
        tabby_shaft_word1: tabby shaft word computed by compute_tabby_shaft_word1.
        threading: The shaft (0-based) for each warp end.

    Returns:
        tabby_shaft_word2: which shaft_set should be up picks 2, 4, 6... of tabby.
            The complement tabby_shaft_word1, will all shaft_set beyond max_threaded_shaft_number
            set to 0.

    Raises:
        ValueError if max_threaded_shaft_number < 2.

    Notes:
        Takes threading instead of max_threaded_shaft_number for two reasons:

        * It proved too easy to mis-compute the value. Threading is 0-based
            and it was too easy to pass in max(threading), which is 1 too small.
        * We may wish to switch to using a sparse mask of threaded shafts,
            lowering all unused shafts, not just those beyond the last threaded shaft.
    """
    if tabby_shaft_word1 < 1:
        raise ValueError(f"{tabby_shaft_word1=} must be positive")
    max_threaded_shaft_number = max(threading) + 1  # threading is 0-based
    if max_threaded_shaft_number <= 1:
        raise ValueError(f"{max_threaded_shaft_number=} must be > 1")

    all_shaft_set_mask = (1 << max_threaded_shaft_number) - 1
    tabby_shaft_word2 = ~tabby_shaft_word1 & all_shaft_set_mask
    if tabby_shaft_word2 < 1:
        raise ValueError(f"Result is invalid; check {tabby_shaft_word1=} and {threading=}")
    return tabby_shaft_word2


def compute_tabby_shaft_words(threading: list[int]) -> tuple[int, int]:
    """Compute tabby_shaft_words 1 and 2.

    Args:
        threading: 0-based shaft number for each warp end.

    Returns:
        (shaft_word1, shaft_word2): Which shaft_set should be up for the two picks of tabby
            (word 1 is for picks 1, 3, 5.., word 2 is for picks 2, 4, 6...).

    Raises:
        ValueError if there are fewer than 2 threaded warp ends,
            or if the warp ends are threaded on fewer than 2 different shaft_set.
    """
    tabby_shaft_word1 = compute_tabby_shaft_word1(threading=threading)
    tabby_shaft_word2 = compute_tabby_shaft_word2(tabby_shaft_word1=tabby_shaft_word1, threading=threading)
    return (tabby_shaft_word1, tabby_shaft_word2)
