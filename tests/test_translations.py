import importlib.resources
import json
import logging
import pathlib
import tempfile

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


def test_circular_extends() -> None:
    for suffix in ("a", "b", "c"):
        with pytest.raises(RecursionError):
            get_translation_dict(f"circular_{suffix}", dir_=TEST_DATA_FILES)


def test_get_default_dict() -> None:
    assert METADATA_KEYS == {"_direction", "_extends", "_language_code"}  # noqa: SIM300

    default_dict = get_default_dict()
    # All METADATA_KEYS should appear in the default dict
    assert METADATA_KEYS - default_dict.keys() == set()

    for key in METADATA_KEYS:
        assert key.startswith("_")

    for key, value in default_dict.items():
        if key not in METADATA_KEYS:
            assert value == key

    assert default_dict["_direction"] == "ltr"
    assert default_dict["_extends"] == ""
    assert default_dict["_language_code"] == "en"


def test_get_language_names() -> None:
    language_names = get_language_names()
    assert language_names[0] == "English"
    assert "default" not in language_names
    assert "" not in language_names


def test_extra_keys(caplog: pytest.LogCaptureFixture) -> None:
    default_dict = get_default_dict()
    logger = logging.getLogger()

    extra_key_name = "-- extra key for test_extra_keys --"
    assert extra_key_name not in default_dict

    with tempfile.TemporaryDirectory() as dirname:
        dir_ = pathlib.Path(dirname)
        filepath = dir_ / "extra_keys.json"
        extra_keys_dict = default_dict.copy()
        extra_keys_dict[extra_key_name] = "some value"
        with filepath.open("w") as f:
            json.dump(extra_keys_dict, f)
        data = read_one_translation_file(
            translation_file=filepath, valid_keys=default_dict.keys(), logger=logger
        )

    assert data.keys() == default_dict.keys()
    assert len(caplog.record_tuples) > 0
    for _root, level, text in caplog.record_tuples:
        if extra_key_name in text:
            assert level == logging.WARNING
            assert "invalid keys" in text
            break
    else:
        pytest.fail("Expected warning not found")


def test_missing_file() -> None:
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


def test_valid_extends() -> None:
    # a, b, and c all specify "Weave {suffix}"
    # b and c specify "Thread {suffix}"
    # only c specifies "Pattern {suffix}"
    for suffix, expected_results in {
        "a": {"Weave": "Weave a", "Thread": "Thread b", "Pattern": "Pattern c"},
        "b": {"Weave": "Weave b", "Thread": "Thread b", "Pattern": "Pattern c"},
        "c": {"Weave": "Weave c", "Thread": "Thread c", "Pattern": "Pattern c"},
    }.items():
        data = get_translation_dict(f"extends_{suffix}", dir_=TEST_DATA_FILES)
        for key, value in expected_results.items():
            assert data[key] == value
