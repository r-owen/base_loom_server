import functools
import itertools
import operator

from .utils import prune_duplicates

# Maximum number of starting points for iterations in compute_tabby_shaft_word1.
# Avoid very large values to keep compute time reasonable.
MAX_ITER_TABBY1 = 5


def compute_num_transitions(tabby_shaft_word: int, threading: list[int]) -> int:
    """Compute the number of transitions produced by a tabby shaft word.

    The largest possible value is len(threading_shaft_words) - 1.

    Args:
        tabby_shaft_word: Tabby shaft word.
        threading: Shaft index (0-based) for each warp end.
            Negative values are ignored (and adjacent duplicate values
            naturally do not affect the result).
    """
    threading_shaft_words = [1 << shaft for shaft in threading if shaft >= 0]
    return _compute_num_transitions_impl(
        tabby_shaft_word=tabby_shaft_word, threading_shaft_words=threading_shaft_words
    )


def _compute_num_transitions_impl(tabby_shaft_word: int, threading_shaft_words: list[int]) -> int:
    """Implementation of compute_num_transitions.

    Args:
        tabby_shaft_word: Tabby shaft word.
        threading_shaft_words: Shaft word for each warp end.
    """
    is_up_list = [bool(tsw & tabby_shaft_word) for tsw in threading_shaft_words]
    return sum(1 for val1, val2 in itertools.pairwise(is_up_list) if val1 != val2)


def compute_tabby_shaft_word1_simple(threading: list[int]) -> int:
    """Trivial tabby computation that may fail.

    Handle the trivial case that all even threads are on different
    shafts than all odd threads. Return 0 if that is not the case.

    Args:
        threading: Shaft index (0-based) for each warp end.
            Negative values and adjacent duplicates are ignored.

    Returns:
        Tabby shaft word, or 0 if the simple case is not satified.
    """
    # Ignore unthreaded shafts and duplicates
    pruned_threading = prune_duplicates([shaft for shaft in threading if shaft >= 0])
    num_threaded_shafts = len(set(threading))
    if len(threading) <= 1:
        raise ValueError("Need at least 2 threaded warp ends to weave tabby.")
    if num_threaded_shafts <= 1:
        raise ValueError("Need at least 2 threaded shafts to weave tabby.")

    threading_shaft_words = [1 << shaft for shaft in pruned_threading]
    return _compute_tabby_shaft_word1_simple_impl(threading_shaft_words=threading_shaft_words)


def _compute_tabby_shaft_word1_simple_impl(threading_shaft_words: list[int]) -> int:
    """Implementation of compute_tabby_shaft_word1_simple.

    Handle the trivial case that all even threads are on different
    shafts than all odd threads. Return 0 if that is not the case.

    Args:
        threading_shaft_words: Shaft words for each warp end.
            Duplicates should be removed.

    Returns:
        Tabby shaft word, or 0 if the simple case is not satified.
    """
    if len(threading_shaft_words) == 0:
        return 0

    tabby_shaft_word = 0
    odd_ends_shaft_word = functools.reduce(operator.or_, threading_shaft_words[0::2], 0)
    even_ends_shaft_word = functools.reduce(operator.or_, threading_shaft_words[1::2], 0)

    if even_ends_shaft_word & odd_ends_shaft_word == 0:
        min_shaft_word = min(threading_shaft_words)
        tabby_shaft_word = (
            even_ends_shaft_word if min_shaft_word & even_ends_shaft_word > 0 else odd_ends_shaft_word
        )

    return tabby_shaft_word


def compute_tabby_shaft_word1(threading: list[int]) -> int:
    """Compute which shaft_set should go up for the best tabby pick 1.

    Args:
        threading: Shaft index (0-based) for each warp end.
            Negative values and adjacent duplicates are ignored.

    Returns:
        shaft_word: Which shaft_set should be up for pick 1, 3, 5... of tabby.

    Raises:
        ValueError if there are fewer than 2 threaded warp ends,
            or if the warp ends are threaded on fewer than 2 different shaft_set.

    Notes:
        The algorithm works by examining transitions between adjacent warp ends, as follows:

        First make a pruned version of threading with no negative values
        (warp ends that are not threaded) and no repeating ends.

        Initialize tabby_shafts and seen_shafts to the first entry in the pruned threading.
        For each shaft in the rest of the pruned threading:
            If shaft is not in seen_shafts:
                Add it to seen_shafts
                If previous_shaft is not in tabby_shafts, put the new shaft in tabby_shafts.
            Set previous_shaft to shaft
        If the resulting tabby shaft word does not included the minimum threaded shaft,
        invert it to provide more predictable results.

        Try this several times, from different starting points in the threading,
        and pick the tabby that gives the most consecutive transitions.
    """
    # Ignore unthreaded shafts and duplicates
    pruned_threading = prune_duplicates([shaft for shaft in threading if shaft >= 0])
    num_threaded_shafts = len(set(threading))
    if len(threading) <= 1:
        raise ValueError("Need at least 2 threaded warp ends to weave tabby.")
    if num_threaded_shafts <= 1:
        raise ValueError("Need at least 2 threaded shafts to weave tabby.")

    threading_shaft_words = [1 << shaft for shaft in pruned_threading]

    # First try the simple algorithm. It is a common case, fast to evaluate,
    # and gives maximum interlacement if it works at all.
    try_tabby_word = _compute_tabby_shaft_word1_simple_impl(threading_shaft_words=threading_shaft_words)
    if try_tabby_word != 0:
        return try_tabby_word

    # Try the harder and less ideal algorithm.
    min_shaft_word = min(threading_shaft_words)
    max_threaded_shaft = max(pruned_threading)
    all_shafts_word = (1 << (max_threaded_shaft + 1)) - 1

    best_num_transitions = 0
    best_tabby_shaft_word = 0

    # Try starting at several different points in the threading,
    # in order to get a somewhat better result.
    num_threads = len(pruned_threading)
    start_interval = ((num_threads - 1) // MAX_ITER_TABBY1) + 1
    if num_threads < MAX_ITER_TABBY1 * 2:
        # Not many threads; don't worry about limiting the number of iterations.
        start_interval = 1
    niter = 0
    for start_index in range(0, num_threads, start_interval):
        niter += 1
        tabby_shaft_word = threading_shaft_words[start_index]
        seen_shafts_word = threading_shaft_words[start_index]
        num_seen_shafts = 1
        for prev_shaft_word, shaft_word in itertools.pairwise(
            itertools.chain(threading_shaft_words[start_index:], threading_shaft_words[:start_index])
        ):
            if shaft_word & seen_shafts_word > 0:
                continue
            seen_shafts_word |= shaft_word
            num_seen_shafts += 1
            if prev_shaft_word & tabby_shaft_word == 0:
                # The previous thread's shaft word is not part of the tabby word
                # so make this new thread's shaft part of the tabby word.
                tabby_shaft_word |= shaft_word
            if num_seen_shafts == num_threaded_shafts:
                # We have seen all shafts; stop
                break

        # Pick the tabby word that includes the lowest numbered threaded shaft
        if min_shaft_word & tabby_shaft_word == 0:
            tabby_shaft_word = ~tabby_shaft_word & all_shafts_word

        num_transitions = _compute_num_transitions_impl(
            tabby_shaft_word=tabby_shaft_word,
            threading_shaft_words=threading_shaft_words,
        )
        if num_transitions > best_num_transitions:
            best_num_transitions = num_transitions
            best_tabby_shaft_word = tabby_shaft_word
            if num_transitions == len(pruned_threading) - 1:
                break
    return best_tabby_shaft_word


def compute_tabby_shaft_word2(tabby_shaft_word1: int, threading: list[int]) -> int:
    """Compute tabby_shaft_word2 as the complement of tabby_shaft_word1.

    Args:
        tabby_shaft_word1: tabby shaft word computed by compute_tabby_shaft_word1.
        threading: Shaft index (0-based) for each warp end.
            Negative values and adjacent duplicates are ignored.

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

    all_shafts_mask = (1 << max_threaded_shaft_number) - 1
    tabby_shaft_word2 = ~tabby_shaft_word1 & all_shafts_mask
    if tabby_shaft_word2 < 1:
        raise ValueError(f"Result is invalid; check {tabby_shaft_word1=} and {threading=}")
    return tabby_shaft_word2


def compute_tabby_shaft_words(threading: list[int]) -> tuple[int, int]:
    """Compute tabby_shaft_words 1 and 2.

    Args:
        threading: Shaft index (0-based) for each warp end.
            Negative values and adjacent duplicates are ignored.

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
