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
        languages_seen: set[str] = set()
        dict_list: list[dict[str, str]] = []

        lang_dict = json.loads(filepath.read_text(encoding="utf_8"))
        report_problems(
            filepath=filepath,
            desired_keys=desired_keys,
            lang_dict=lang_dict,
            report_missing_keys=False,
        )
        dict_list.append(lang_dict)
        languages_seen.add(filepath.stem)

        prev_path = filepath
        while True:
            next_language_entry = lang_dict.get("_extends")
            if next_language_entry is None:
                break
            # Note: if "_extends" is present, it must have 2 keys: message and description
            # But if it does not, that is complained about elsewhere.
            next_language = next_language_entry.get("message")
            if not next_language:
                break
            if next_language in languages_seen:
                print(f"Circular dependency found in {next_language}; giving up on {prev_path.name}")
                break
            next_path = LOCALE_FILES.joinpath(f"{next_language}.json")
            if not next_path.is_file():
                print(f"Dependency {next_path} not found in {prev_path.name}; giving up")
                break
            lang_dict = json.loads(next_path.read_text(encoding="utf_8"))
            dict_list.append(lang_dict)
            report_problems(
                filepath=next_path,
                desired_keys=desired_keys,
                lang_dict=lang_dict,
                report_missing_keys=False,
            )

        # Ignore default_dict when producing full_dict
        # so we can detect missing keys
        full_dict_without_default: dict[str, str] = {}
        for subdict in reversed(dict_list):
            full_dict_without_default.update(subdict)
        report_problems(
            filepath=filepath,
            desired_keys=desired_keys,
            lang_dict=full_dict_without_default,
            report_missing_keys=True,
        )


KeysToIgnore = {"?", "_direction", "_extends", "_language_code"}


def report_problems(
    *,
    filepath: Traversable,
    desired_keys: set[str],
    lang_dict: dict[str, Any],
    report_missing_keys: bool,
) -> None:
    """Check for issues in one file and print the results to stdout."""
    bad_keys = {key for key, value in lang_dict.items() if value.keys() != {"message", "description"}}
    missing_keys: set[str] = desired_keys - lang_dict.keys() - KeysToIgnore if report_missing_keys else set()
    extra_keys = lang_dict.keys() - desired_keys
    blank_keys = {key for key, value in lang_dict.items() if value == ""}
    if bad_keys or missing_keys or extra_keys or blank_keys:
        print(f"{filepath.name} has one or more problems:")
        if bad_keys:
            print(f"    bad keys: {bad_keys}")
        if missing_keys:
            print(f"    missing keys: {missing_keys}")
        if extra_keys:
            print(f"    extra keys: {extra_keys}")
        if blank_keys:
            print(f"    blank entries: {blank_keys}")
    elif report_missing_keys:
        print(f"{filepath.name} is complete")
