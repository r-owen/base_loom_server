import importlib.resources
import json
import logging

import pytest

from base_loom_server.translations import (
    LOCALE_FILES,
    METADATA_KEYS,
    get_default_dict,
    get_language_names,
    get_translation_dict,
    read_one_translation_file,
)

_PKG_NAME = "base_loom_server"
TEST_DATA_FILES = importlib.resources.files(_PKG_NAME) / "test_data" / "translation_files"


def test_get_default_dict() -> None:
    assert METADATA_KEYS == {"_direction", "_language_code"}  # noqa: SIM300

    default_dict = get_default_dict()
    # All METADATA_KEYS should appear in the default dict
    assert METADATA_KEYS - default_dict.keys() == set()

    for key in METADATA_KEYS:
        assert key.startswith("_")

    for key, value in default_dict.items():
        if key not in METADATA_KEYS:
            assert value == key

    assert default_dict["_direction"] == "ltr"
    assert default_dict["_language_code"] == "en"


def test_get_language_names() -> None:
    language_names = get_language_names()
    assert "English" in language_names
    assert "default" not in language_names
    assert "" not in language_names


def test_extra_keys(caplog: pytest.LogCaptureFixture) -> None:
    """Test that loading a file with extra keys produces a logged warning."""
    default_dict = get_default_dict()
    filepath = TEST_DATA_FILES.joinpath("extra_keys.json")
    raw_extra_data = json.loads(filepath.read_text(encoding="utf_8"))
    extra_key = "-- extra key for test_extra_keys --"
    assert extra_key in raw_extra_data
    assert extra_key not in default_dict

    logger = logging.getLogger()
    read_one_translation_file(translation_file=filepath, valid_keys=default_dict.keys(), logger=logger)
    assert len(caplog.record_tuples) > 0
    for _root, level, text in caplog.record_tuples:
        if extra_key in text:
            assert level == logging.WARNING
            assert "invalid keys" in text
            break
    else:
        pytest.fail("Expected warning not found")


def test_format() -> None:
    """Test the format of every real translation file.

    Ignore test translation file(s).
    """
    for filepath in LOCALE_FILES.glob("*.json"):  # type: ignore[attr-defined]
        raw_dict = json.loads(filepath.read_text(encoding="utf_8"))
        for key, value in raw_dict.items():
            assert isinstance(key, str)
            assert isinstance(value, dict)
            assert value.keys() == {"message", "description"}
            assert isinstance(value["message"], str)
            assert isinstance(value["description"], str)


def test_missing_file() -> None:
    """Test trying to load a translation file that does not exist."""
    logger = logging.getLogger()
    language_names = get_language_names()
    missing_name = "unlikely name for a language file"
    assert missing_name not in language_names

    default_dict = get_default_dict()

    with pytest.raises(FileNotFoundError):
        read_one_translation_file(
            translation_file=LOCALE_FILES / f"{missing_name}.json",
            valid_keys=default_dict.keys(),
            logger=logger,
        )

    with pytest.raises(FileNotFoundError):
        get_translation_dict(missing_name)
