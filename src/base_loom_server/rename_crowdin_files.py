# ruff: noqa: T201
import argparse
import pathlib
from importlib.resources.abc import Traversable

# Dict of language name in English, language name in the native language
LANGUAGE_DICT = {
    "Danish": "Dansk",
    "Dutch": "Nederlands",
    "English, United Kingdom": "English (UK)",
    "English, Canada": "English (CA)",
    "French, Quebec": "Français du Québec",
    "Finnish": "Suomi",
    "French": "Français",
    "German": "Deutsch",
    "Italian": "Italiano",
    "Norwegian": "Norsk",
    "Spanish": "Español",
    "Swedish": "Svenska",
}


def _rename_crowdin_files(in_dir: Traversable) -> None:
    """Implement rename_crowdin_files.

    Args:
        in_dir: Path to a directory containing the translation files from crowdin.
           The files may (and usually or always will be) arranged a set of subfolders,
           with one file per subfolder. The file names will be {language}.json
           where language is the name of the language in English.
           Files in the "locales" directory are ignored.

    Raises:
        RuntimeError: If the same new language name is found twice.
    """
    outdir = in_dir.joinpath("locales")
    outdir.mkdir(exist_ok=True)  # type: ignore[attr-defined]

    # A dict of new_name: original path
    names_seen: dict[str, pathlib.Path] = dict()

    for old_path in in_dir.glob("**/*.json"):  # type: ignore[attr-defined]
        if old_path.parent == outdir:
            continue

        new_name = LANGUAGE_DICT.get(old_path.stem)
        if new_name is None:
            print(f"WARNING: skipping {old_path} because {old_path.stem} is not in LANGUAGE_DICT")
            continue

        previous_path = names_seen.get(new_name)
        if previous_path is not None:
            raise RuntimeError(f"{new_name} found twice: in {previous_path} and {old_path}")

        names_seen[new_name] = old_path
        new_path = outdir.joinpath(f"{new_name}.json")
        old_path.replace(new_path)
        print(f"Moved {old_path} to {new_path}")


def rename_crowdin_files() -> None:
    """Process translation files from crowdin.

    Rename crowdin files to the language name in the original language,
    and move them to a subfolder of in_dir named "locales" (which is created, if necesary).
    The user can then copy any of these files to "locales" in the base_loom_server package.
    """
    parser = argparse.ArgumentParser(
        description="Move and rename translation files from crowdin to a new locales subdirectory"
    )
    parser.add_argument("in_dir", type=pathlib.Path, help="Folder containing crowdin translation files")
    args = parser.parse_args()
    _rename_crowdin_files(in_dir=args.in_dir)
