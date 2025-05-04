# Version History

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



