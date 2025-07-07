import importlib.resources
import json
import logging
from collections.abc import KeysView
from importlib.resources.abc import Traversable

PKG_FILES = importlib.resources.files("base_loom_server")
LOCALE_FILES = PKG_FILES.joinpath("locales")

# Translation keys that provide metadata instead of phrases to translate.
METADATA_KEYS = {"_direction", "_extends", "_language_code"}


def get_language_names() -> list[str]:
    """Get a list of all language files found in LOCALE_FILES.

    Add "English" and omit "default.json".
    """
    filenames = [
        filepath.stem
        for filepath in LOCALE_FILES.glob("*.json")  # type: ignore[attr-defined]
        if filepath.stem != "default"
    ]
    return ["English", *sorted(filenames)]


def get_default_dict() -> dict[str, str]:
    """Get the default translation dict.

    The data in the file is mostly a dict of `word or phrase`: `context`
    where context is a hint to people doing the translation.
    For those items the returned data is `word or phrase`: `word or phrase`
    (the context is ignored).

    For keys in the METADATA_KEYS, the data is copied directly.
    """
    default_dict = json.loads(LOCALE_FILES.joinpath("default.json").read_text(encoding="utf_8"))
    translation_dict = {key: key for key in default_dict if key not in METADATA_KEYS}
    for key in METADATA_KEYS:
        translation_dict[key] = default_dict[key]
    return translation_dict


def get_translation_dict(
    language: str,
    logger: logging.Logger | None = None,
    dir_: Traversable = LOCALE_FILES,
) -> dict[str, str]:
    """Get the translation dict for the specified language.

    Args:
        language: Name of one of the available language files,
            or "English" for English. Must not be "" or "default".
        logger: Logger, which is created if None.
        dir_: Directory containing the non-default translation files.
            Use the default value except in unit tests.

    Raises:
        FileNotFoundError: If a file is not found.
        RecursionError: If a circular "_extends" reference is found.
    """
    if language in ("", "default"):
        raise RuntimeError(f"Invalid value for {language=}")

    if logger is None:
        logger = logging.getLogger()

    translation_dict = get_default_dict()
    valid_keys = set(translation_dict.keys())

    # Keep track of the language files read, in order to
    # prevent infinite recursion caused by translation dicts
    # extending each other in a circular fashion.
    languages_read: set[str] = set()
    dict_list: list[dict[str, str]] = []
    next_language = language
    while next_language not in {"", "default", "English"}:
        if next_language in languages_read:
            raise RecursionError(f"Circular reference for {language=}, found reading {next_language=}")
        next_file = dir_.joinpath(f"{next_language}.json")
        next_dict = read_one_translation_file(
            translation_file=next_file, valid_keys=valid_keys, logger=logger
        )
        dict_list.append(next_dict)
        languages_read.add(next_language)
        next_language = next_dict.get("_extends", "")

    # Apply the dicts in the correct order:
    # default dict is overridden by last dependency (the last _extends
    # in the chain), and so on up the (usually short) chain of dependencies.
    for next_dict in reversed(dict_list):
        translation_dict.update(next_dict)
    return translation_dict


def read_one_translation_file(
    translation_file: Traversable,
    valid_keys: set[str] | KeysView,
    logger: logging.Logger,
) -> dict[str, str]:
    """Read and parse one language translation file.

    Args:
        translation_file: Path to translation file.
        valid_keys: Keys that are allowed in the translation dict.
            Invalid keys are purged with a logged warning.
        logger: Logger.

    Returns:
        The translation dict: a dict of English word or phrase: translation.

    Raises:
        FileNotFoundError: If the file is not found.
    """
    if not translation_file.is_file():
        raise FileNotFoundError(f"Translation file {translation_file} not found")
    logger.info(f"Loading translation file {translation_file}")
    raw_translation_dict = json.loads(translation_file.read_text(encoding="utf_8"))
    translation_dict = {key: value for key, value in raw_translation_dict.items() if key in valid_keys}
    extra_keys = raw_translation_dict.keys() - translation_dict.keys()
    if extra_keys:
        extra_keys_str = ", ".join(sorted(extra_keys))
        logger.warning(f"Ignoring invalid keys in {translation_file}: {extra_keys_str}")
    return translation_dict
