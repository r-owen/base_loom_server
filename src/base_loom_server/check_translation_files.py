# ruff: noqa: T201
import importlib.resources
import json
from importlib.resources.abc import Traversable
from typing import Any

PKG_FILES = importlib.resources.files("base_loom_server")
LOCALE_FILES = PKG_FILES.joinpath("locales")


def check_translation_files() -> None:
    """Check for issues in the language translation files.

    Report to stdout.
    """
    default_dict = json.loads(LOCALE_FILES.joinpath("default.json").read_text(encoding="utf_8"))
    desired_keys = set(default_dict.keys())

    for filepath in LOCALE_FILES.glob("*.json"):  # type: ignore[attr-defined]
        lang_dict = json.loads(filepath.read_text(encoding="utf_8"))
        report_problems(
            filepath=filepath,
            desired_keys=desired_keys,
            lang_dict=lang_dict,
            report_missing_keys=not filepath.stem.startswith("English"),
        )


KeysToIgnore = {"?", "_direction", "_language_code"}


def report_problems(
    *,
    filepath: Traversable,
    desired_keys: set[str],
    lang_dict: dict[str, Any],
    report_missing_keys: bool,
) -> None:
    """Check for issues in one file and print the results to stdout."""
    bad_keys = {key for key, value in lang_dict.items() if value.keys() != {"message", "description"}}
    missing_keys: set[str] = desired_keys - lang_dict.keys() - KeysToIgnore
    extra_keys = lang_dict.keys() - desired_keys
    blank_keys = {key for key, value in lang_dict.items() if value == ""}
    if bad_keys or (missing_keys and report_missing_keys) or extra_keys or blank_keys:
        print(f"{filepath.name} has one or more problems:")
        if bad_keys:
            print(f"    bad keys: {bad_keys}")
        if missing_keys:
            print(f"    missing keys: {missing_keys}")
        if extra_keys:
            print(f"    extra keys: {extra_keys}")
        if blank_keys:
            print(f"    blank entries: {blank_keys}")
    elif missing_keys and not report_missing_keys:
        print(f"{filepath.name} is correct but not complete")
    else:
        print(f"{filepath.name} is complete")
