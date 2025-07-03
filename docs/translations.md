# Translations

[base_loom_server](https://pypi.org/project/base-loom-server/) supports foreign language translations (for the web display, but not this documentation).

At present only a few translations are available, and none have been properly vetted.
Help from others to improve the existing translations and add new ones would be most welcome.
Weaving terminology is somewhat obscure, so translation tools may miss important subtleties. 

Each language is supported by a separate json file in `src/locales`.
The name of each translation file is the native name of the language, for example `Français.json`.

The file `src/locales/default.json` lists all the words and phrases for which translations are wanted.
the values are context, which are purely intended to help the translator understand the word or phrase; they are ignored by the software.
In addition to those entries there are a few [metadata keys](#metadata-keys).

The keys in the translation files are the same as in `default.json`, but the values are the translated word or phrase.
One way to start is to copy `src/locales/default.json` to the new language file, then replace each context string with the translated string.

To add or change translation files, fork the project on github.

If you are not confident of your translations, please append " (preliminary)", suitably translated, to the name.
For example: "Français (préliminaire).json".

An incomplete file is better than none. Missing entries will be shown in English.

## Metadata Keys

There are several optional keys that provide metadata:

* **_direction**: whether the language is read left-to-right (value `ltr`, the default) or right-to-left (value `rtl`).
* **_extends**: the name of another language file of which this is a variant, without the ".json" suffix.
  If you specify `_extends` then you need only specify the items that differ from the file named in `_extends`.
  For example file `Québécois.json` could specify `"_extends"="Français"`.
* **_language_code**: the ISO 639-1 language code for the language, e.g. `fr` for `Français`. Here is [one list](https://www.w3schools.com/tags/ref_language_codes.asp). This may help text-to-speech software. If omitted the value is "en".
