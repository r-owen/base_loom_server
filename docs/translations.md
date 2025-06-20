# Translations

[base_loom_server](https://pypi.org/project/base-loom-server/) supports foreign language translations (for the web display, but not this documentation).

At present only one translation available: is a rather poor French translation.
Help from others to add and improve language support would be most welcome.

Each language is supported by a separate yaml file in `src/locales`.

Each translation file must have name *language_code*.js, where  *language_code* is a standard language code as reported by the Python `locale` library.
Here is one [list of codes](https://stackoverflow.com/questions/3191664/list-of-all-locales-and-their-short-codes).
On macOS and unix you can see a list of supported locales with terminal command `locale -a`.

The file `src/locales/default.yaml` lists all the words and phrases for which translations are wanted. The values provide a description that may help to understand the word or phrase. These values are ignored by the software.The keys are the same in each translation file, but the values are the translated word or phrase. A good way to start is to copy `src/locales/default.yaml` to the new language file, then replace each value string with the translated string.

An incomplete file is better than none; missing entries will be shown in English.

It is possible to have two files for a given language: one that uses a more general language code, and the other that uses a more specific code. If you do this, the more general file is read first, then the more specific file. Thus the more specific file need only have entries that differ from the general file.

In order for a translation file to be used, the locale of the server computer must be set correctly.
