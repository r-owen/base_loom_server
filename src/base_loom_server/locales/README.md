This directory contains phrase translation dictionaries.

Each file name (other than default.json) should be of the form *language*.json (more general)
or *language_country*.json (more specific), where *language* is a 2-letter lowercase language code
and *country* is a 2-letter uppercase country code.
For example fr.json and fr_CA.json.

If both files are present for the current locale, both files are read, with phrases in the more specific file overriding phrases in the more general file.

If neither file is present, or neither file defines a specific phrase, English is used.

The contents should be the same as default.json, except that the value of each key should be the translated phrase.
