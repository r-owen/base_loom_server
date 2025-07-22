import html
import importlib.resources
import json
import logging
from collections.abc import KeysView
from importlib.resources.abc import Traversable

PKG_FILES = importlib.resources.files("base_loom_server")
LOCALE_FILES = PKG_FILES.joinpath("locales")

# Translation keys that provide metadata instead of phrases to translate.
METADATA_KEYS = {"_direction", "_language_code"}


def get_language_names() -> list[str]:
    """Get a sorted list of all language files found in LOCALE_FILES.

    Omit "default.json".
    """
    return sorted(
        filepath.stem
        for filepath in LOCALE_FILES.glob("*.json")  # type: ignore[attr-defined]
        if filepath.stem != "default"
    )


def get_default_dict() -> dict[str, str]:
    """Get the default translation dict."""
    filepath = LOCALE_FILES.joinpath("default.json")
    return _basic_read_one_translation_file(filepath)


def get_translation_dict(
    language: str,
    *,
    logger: logging.Logger | None = None,
    html_escape: bool = True,
    dir_: Traversable = LOCALE_FILES,
) -> dict[str, str]:
    """Get the translation dict for the specified language.

    All missing phrases use the phrase from "default.json".

    Args:
        language: Name of one of the available language files,
            or "English" for English. Must not be "" or "default".
        logger: Logger, which is created if None.
        dir_: Directory containing the non-default translation files.
            Use the default value except in unit tests.
        html_escape: Run the values through html.escape?

    Raises:
        FileNotFoundError: If a file is not found.
    """
    if language in ("", "default"):
        raise RuntimeError(f"Invalid value for {language=}")

    if logger is None:
        logger = logging.getLogger()

    translation_dict = get_default_dict()
    valid_keys = set(translation_dict.keys())

    language_file = dir_.joinpath(f"{language}.json")
    language_dict = read_one_translation_file(
        translation_file=language_file, valid_keys=valid_keys, logger=logger
    )
    translation_dict.update(language_dict)
    if html_escape:
        translation_dict = {key: html.escape(value, quote=True) for key, value in translation_dict.items()}
    return translation_dict


def _basic_read_one_translation_file(translation_file: Traversable) -> dict[str, str]:
    """Read one translation file and return as a dict of phrase: translation.

    The file format is a dict of str: dict where dict includes the "message" key.
    Other than acting on that assumption, it performs no checking.

    Args:
        translation_file: Path to translation file.
    """
    raw_dict = json.loads(translation_file.read_text(encoding="utf_8"))
    return {key: value["message"] for key, value in raw_dict.items()}


def read_one_translation_file(
    translation_file: Traversable,
    valid_keys: set[str] | KeysView[str],
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
    raw_translation_dict = _basic_read_one_translation_file(translation_file)
    translation_dict = {key: value for key, value in raw_translation_dict.items() if key in valid_keys}
    extra_keys = raw_translation_dict.keys() - translation_dict.keys()
    if extra_keys:
        extra_keys_str = ", ".join(sorted(extra_keys))
        logger.warning(f"Ignoring invalid keys in {translation_file}: {extra_keys_str}")
    return translation_dict
