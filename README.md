# Base package for web servers that control dobby multi-shaft looms

Such web servers are intended to allow you to control your loom from any phone, tablet or other device that has wifi and a web browser.

Used by [seguin_loom_server](<https://pypi.org/project/seguin-loom-server/)>)
and [toika_loom_server](https://pypi.org/project/toika-loom-server/).

## Installing this Package

* Install [Python](https://www.python.org/downloads/) 3.11 or later on the computer.

* Install this [base_loom_server](https://pypi.org/project/base-loom-server/) package on the computer with command: **pip install base_loom_server**

## Using this Package

* Subclass `BaseMockLoom`; see `ExampleMockLoom` for an example.
* Subclass `BaseLoomServer`; see `ExampleLoomServer` for an example.
* Write a `main.py` like the one in this package (which runs `ExampleLoomServer`).
* The unit tests for `BaseMockLoom` should be able to use `testutils.BaseTestLoomServer`, as `tests/test_loom_server.py` does.
* Write a `pyproject.toml` like the one for [toika_loom_server](https://pypi.org/project/toika-loom-server/), unless you would rather use a different distribution system.

## Remembering Patterns

The web server keeps track of the most recent 25 patterns you have used in a database
(including the most recent pick number and number of repeats, which are restored when you select a pattern).
The patterns in the database are displayed in the pattern menu.
If you shut down the server or there is a power failure, all this information should be retained.

You can reset the database by starting the server with the **--reset-db** argument.
You must reset the database if you upgrade this base_loom_server package and the new database format is incompatible
(in which case the server will fail at startup).
You may also want to reset the database if you are weaving a new project and don't want to see any of the saved patterns.

## Developer Tips

* Download the source code from [github](https://github.com/r-owen/base_loom_server.git),
  or make a fork and download that.

* Inside the directory, issue the following commands:

    * **pip install -e .'[dev]'** (the single quotes are required in zsh, but not in bash)
      to make an "editable installation" of the package.
      An editable installation runs from the source code, so changes you make to the source are used when you run or test the code, without the need to reinstall the package.
      **'[dev]'** installs development-related packages such as pytest (see the file `pyproject.toml` for the full list).

    * **pre-commit install** to activate the pre-commit hooks.
    
    * **pytest** to test your installation.

* You may run an example loom server with: **run_example_loom mock**.
  Please only specify the **mock** serial port; do not try to connect the example loom server
  to any real dobby loom, because it will not work.

  **run_example_loom mock** also accepts these command-line arguments:

    * **--reset-db** Reset the pattern database. Try this if you think the database is corrupted.

    * **--verbose** Print more diagnostic information.
  
  Note that the example loom server uses the same pattern database as
  [seguin_loom_server](<https://pypi.org/project/seguin-loom-server/)>)
  and [toika_loom_server](https://pypi.org/project/toika-loom-server/).

* In mock mode the web page shows a few extra controls for debugging.

* Warning: the web server's automatic reload feature, which reloads Python code whenever you save changes, *does not work* with this software.
  Instead you have to kill the web server by typing control-C several times, until you get a terminal prompt, then run the server again.
  This may be a bug in uvicorn; see [this discussion](https://github.com/encode/uvicorn/discussions/2075) for more information.
