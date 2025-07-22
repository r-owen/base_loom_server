# Version History

## 0.29 2025-07-22

* Add (preliminary) translations for more languages.
* Use crowdin for translations. As a result:

  * Change the format of translation files (to "Chrome JSON").
  * Update the translation instructions.
  * Remove support for one translation file extending another.

* html-encode translated strings for improved safety.

## 0.28 2025-07-10

* Support dark mode.
  Use the browser's dark/light setting (there is no manual override at this time).
* Make button text black on iOS.
* Fix a few minor bugs found by pyright.
* Fix a few minor issues found by running mypy in strict mode.

## 0.27.1 2025-07-08

* Fix images on the main documentation page.
* Fix the version of ruff in pyproject.toml.

## 0.27 2025-07-07

Changes for maintainers and authors of loom-specific packages:

* Refactor testutils: Client is a normal class, instead of a dataclass,
  and the free functions that took a Client as the first argument are now methods of that class.
  Unit tests that use internal details of testutils may need some changes,
  but not if the code simply uses BaseTestLoomServer to test the loom server.
* Some functions now require named arguments for most or all arguments.
  This especially applies to methods with boolean arguments and/or many arguments.
* Improve mypy configuration to make it pickier and to allow it to be run with `mypy .`.
* Switch to ruff for checking and formatting.

## 0.26.1 2025-07-06

* Add screen shots to the documentation.
* Add a "Hide" button to the debug controls that are shown when using a mock loom.
  This makes it easier to see what the display will look like with a real loom.
  Refresh the display to restore the debug controls.

Changes for maintainers and authors of loom-specific packages:

* Change the type hint for `BaseLoomServer.__aenter__` and `BaseMockLoom.__aenter__` to `typing.Self`.
  This makes it easier to write an async context manager that returns a subclass,
  since you can now specify the actual subclass returned.

## 0.26 2025-07-05

* Add a Language setting to the Settings panel.
* Properly support right-to-left languages.
* Increased the size of checkboxes.

Changes for maintainers and authors of loom-specific packages:

* Warning: most loom-specific packages will need trivial changes, including  `toika_loom_server` and `seguin_loom_server`.
* BaseLoomServer and subclasses no longer have the `translation_dict` constructor argument.
  As a result, loom-specific packages that override the constructor must be updated.
  You can simply delete that one constructor argument, but it is better to replace the entire constructor override
  with an override of the new `__post_init__` method, as per the next item.
* Added `__post__init__` methods to both `BaseLoomServer` and `BaseMockLoom`.
  These methods take no arguments and return None.
  They are intended to eliminate the need to override the constructor, which eliminates the duplication
  of constructor arguments, making it less likely that future changes will be needed as `base_loom_server` evolves.
  For example `toika_loom_server`'s `LoomServer` and `MockLoom` classes use this method to check
  that the number of shafts is a multiple of 8 (as required by Toika's API).
* Changed the language translation files as follows (see [Translations](translations.md) for details):

  * Each file name is the native name of the language, rather than the language code.
  * Added a few metadata entries.

## 0.25 2025-07-02

* Add a help link.
* Threading display improvements:

  * Show threaded ends darker than unthreaded ends.
  * Show repeats, if there is room.

* Fix two links in the documentation.

## 0.24 2025-06-26

* Prohibit weaving or threading beyond the beginning of the pattern.
* Eliminate the faint ghost display of picks < 0 in the Weaving panel. It is no longer as useful and was potentially confusing.
* Bug fix: threading direction did not take the new end1_on_right setting into account.
* Bug fix: status messages were not displayed.

Changes for maintainers and authors of loom-specific packages:

* Added a command-line script `check_translation_files` to check the completeness of language translation files.
* BaseLoomServer.handle_next_pick_request now returns a boolean indicating whether or not a new shed was sent to the loom.
  Loom-specific software for looms that do not report shaft state (e.g. Toika) should use this to decide whether or not to report the shaft state.

## 0.23.1 2025-06-25

* Fix display of setting "Warp thread 1"; it was not updated based on the reported value.

## 0.23 2025-06-23

* Add a setting to show warp end 1 on the right or left.

## 0.22 2025-06-20

* Display shaft state graphically.
* Improve display when changing orientation between portrait and landscape.

## 0.21.3 2025-06-18

* Bug fix: if the loom controlled direction, and the direction was forward, text for the direction buttons was gray, instead of black.

## 0.21.2 2025-06-17

* Bug fixes for uploading patterns:

  * The Upload button had no effect if used to upload the same file twice.
  * When uploading a file whose name matched the current file, the old version was still displayed.

* After drag-and-drop, restore the correct background color.

## 0.20.1 2025-06-17

* Fix a bug in the Settings panel triggered by the server being pickier about data types.

## 0.20.0 2025-06-17

* Improve the Weaving pattern display:

  * Show pattern over the entire height, showing pattern repeats, if needed, to fill the space.
    Woven parts (in the bottom half) will be dark.
    Rows with negative pick numbers are shown very lightly, as a hint as to the overall pattern.
  * If "Separate repeats" is checked, show gaps in the unwoven part in the top half (but not the woven part below).
    You can see the effect by jumping ahead far enough that the end of a repeat is shown in the top half,
    then checking and unchecking the "Separate repeats" box.

* Provide context in the translation file "default.json" to aid translators.
* Make settings handling more robust and add unit tests for it.

## 0.19.4 2025-06-11

* Bug fixes in Threading:

  * End numbers were not shown when displaying end 0.
  * When a jump is pending, the "Jump to warp thread" input box now shows the total end number
    (the same value you typed in), rather than the end number within the current pattern repeat.
* Change the threading display to show total end numbers along the top,
  rather than end numbers within the current pattern repeat.
* Further improve the display of the tab bar at the top of the window.
* Improve the display of popup menus, such as the Pattern menu.
* Improve the display of text input areas, such as "Jump to weft thread".
* For most controls with labels, you can now click on the label to activate the control.
  This is especially helpful for the "Separate repeats?" checkboxes.
* Specify the language in the HTML. This will be English,
  unless a translation file is present for the current locale.
* Fix some HTML errors (though few, if any, were visible).

## 0.19.3 2025-06-07

* Improve the display of the tab bar at the top of the window.

## 0.19.2 2025-06-07

* Improve the display of direction controls.

## 0.19.1 2025-06-04

* Add missing translation strings.

## 0.19.0 2025-06-3

* Add a new Settings panel which allows you to specify loom name, direction control, and new threading settings.
* Enhance threading support by adding settings for:
  * Thread right-to-left or left-to-right.
  * Thread back-to-front or front-to-back.
  * The defalt threading group size for newly loaded patterns.
* Automatically reset the pattern database if it changes in an incompatible way.
* Store the pattern database and new settings file in your home directory, instead of a temporary directory,
  so that the files will survive a reboot.
* **Breaking change**: remove command-line arguments "name" and "direction-control".
  Use the new Settings panel, instead.

## 0.18.3 2025-05-25

Expand unit tests.

## 0.18.2 2025-05-03

Add API documentation.

## 0.18.1 2025-04-28

Show the correct threading group size when you connect.

## 0.18.0 2025-04-28

Improve the threading display:

* Center the current group, even for patterns with short threading repeats.
* For ends not threaded on any shaft just show the thread without a shaft number.
  Formerly a truncated 0 was shown. Showing a whole 0 is possible, but likely more confusing.

Remove a source of flicker by only updating the visible pattern.

## 0.17.0 2025-04-27

Try to prevent an unwanted stale next-pick request when the loom server connects to the loom (which is when a user connects to the server).
Do this by purging the read buffer.

## 0.16.0 2025-04-25

Display total picks in Weaving and total ends in Threading.
Also jump to total picks in Weaving and total ends in Threading.

## 0.15.0 2025-04-19

Save threading group size with each pattern.

**Warning**: the database for this version is not compatible with older versions, so run the software with `--reset-db` if you have an older database.

Add a version history to the documentation.

## 0.14.0 2025-04-18

Display improvements:

* Avoid scroll bars, if possible.
* Make font size vary somewhat with window size.
* Avoid the search bar and tab controls at the bottom of the iPhone.
* In Threading move Group size to the right of Direction, to save space.

## 0.13.0 2025-04-18

Display improvements:

* Resize the weaving and threading pattern display to fill available space.
* Move the direction control and (for weaving) pick color, for easier access.

## 0.12.1 2025-04-14

Small display improvements.

## 0.12.0 2025-04-03

Support WeavePoint .wpo files.

Improve the display of white threads.

## 0.11.0 2025-04-02

Add a preliminary Finnish translation.

Fix a few issues with the installation instructions (especially those related to finding the loom's USB port on unix and macOS).

Thanks to Kalle Pihlajasaari for the translation and the doc bug reports.

## 0.10.0 2025-03-18

Add a `Separate repeats` checkbox to Weaving and Threading to control whether to include a separator pick (all shafts down) between repeats of weaving or threading.
  
The weaving and threading values are independent of each other, and are saved per pattern in the database.

The intial value for weaving/threading is "on" if the number of picks/ends > 20, else "off".
The idea being that the extra advance is helpful for long sequenced, but annoying for short sequences.

**Warning**: the database for this version is not compatible with older versions, so run the software with `--reset-db` if you have an older database.

## 0.9.1 2025-03-18

Display loom name and # shafts.

Improve error handling if a pattern file cannot be parsed.

## 0.9.0 2025-03-14

Add required command-line argument num_shafts.
This is needed in order for toika_loom_server to work correctly.

## 0.8.1 2025-03-05

Improve the fix for the Windows encoding issue.

## 0.8.0 2025-03-05

Work around an encoding issue on Windows.

## 0.7.1 2026-02-21

Fix a bug in the first threading group when threading high to low.

Improve the threading display.

## 0.7.0 2025-02-21

Add support for unterminated loom I/O.
This is needed for Toika looms.

## 0.6.0 2025-02-17

Improve support for Toika looms, and others that do not report direction.

Improve server unit tests.

## 0.5.2 2025-02-21

Update URLS in pyproject.toml.

## 0.5.1 2025-02-16

Add mkdocs-based documentation.

## 0.5.0 2025-02-16

Add support for threading.

**Warning**: the database for this version is not compatible with older versions, so run the software with `--reset-db` if you have an older database.

## 0.4.0 2025-02-13

Fix a bug that showed up with 32 or more shafts:
JavaScript bitwise operations were failing for large values of shaft_word (due to a notorious misfeature of JavaScript).

## 0.3.0 2025-02-08

Add threading fields to the pattern database. This is preliminary work to add a user interface to assist in threading the loom.

**Warning**: the database for this version is not compatible with older versions, so run the software with `--reset-db` if you have an older database.

## 0.2.1 2025-02-06

Improve dependencies to properly bring in uvicorn.

Improve the README to suggest that developers install with '[dev]'.

## 0.2 2025-02-05

Fix a display bug: patterns at pick 0 could not be displayed, due to an undefined variable.

## 0.1 2025-02-03

Initial prerelease.
