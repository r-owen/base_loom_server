import importlib.resources
import json
import pathlib
from typing import Any

PKG_FILES = importlib.resources.files("base_loom_server")
LOCALE_FILES = PKG_FILES.joinpath("locales")


def check_translation_files():
    """Check for issues in the language translation files.

    Report to stdout.
    """
    default_dict = json.loads(
        LOCALE_FILES.joinpath("default.json").read_text(encoding="utf_8")
    )
    desired_keys = {key for key in default_dict}

    for filepath in LOCALE_FILES.glob(  # pyright: ignore[reportAttributeAccessIssue]
        "*.json"
    ):
        if filepath.name == "default.json":
            continue

        if "_" in filepath.name:
            continue
        lang_dict = json.loads(filepath.read_text(encoding="utf_8"))
        report_problems(
            filepath=filepath, desired_keys=desired_keys, lang_dict=lang_dict
        )

        for (
            subfilepath
        ) in LOCALE_FILES.glob(  # pyright: ignore[reportAttributeAccessIssue]
            f"{filepath.stem}_*.json"
        ):
            subdict = json.loads(subfilepath.read_text(encoding="utf_8"))
            full_dict = lang_dict.copy()
            full_dict.update(subdict)
            report_problems(
                filepath=subfilepath, desired_keys=desired_keys, lang_dict=full_dict
            )


def report_problems(
    filepath: pathlib.Path, desired_keys: set[str], lang_dict: dict[str, Any]
) -> None:
    """Check for issues in one file and print the results to stdout."""
    missing_keys = desired_keys - lang_dict.keys() - {"?"}
    extra_keys = lang_dict.keys() - desired_keys
    blank_keys = {key: value for key, value in lang_dict.items() if value == ""}
    non_str_entries = {
        key: value for key, value in lang_dict.items() if not isinstance(value, str)
    }
    if missing_keys or extra_keys or blank_keys or non_str_entries:
        print(f"{filepath.name} has one or more problems:")
        if missing_keys:
            print(f"    missing keys: {missing_keys}")
        if extra_keys:
            print(f"    extra keys: {extra_keys}")
        if blank_keys:
            print(f"    blank entries: {blank_keys}")
        if non_str_entries:
            print(f"    non-str entries: {non_str_entries}")
    else:
        print(f"{filepath.name} is complete")
