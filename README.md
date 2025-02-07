# Base package for web servers that control dobby multi-shaft looms

Such web servers are intended to allow you to control your loom from any phone, tablet or other device that has wifi and a web browser.

Used by [seguin_loom_server](<https://pypi.org/project/seguin-loom-server/)>)
and [toika_loom_server](https://pypi.org/project/toika-loom-server/).

## Installing this Package

You should only have to install this package if you want to examine or modify it.
If you are installing a loom driver such as
such as [seguin_loom_server](<https://pypi.org/project/seguin-loom-server/)>)
or [toika_loom_server](https://pypi.org/project/toika-loom-server/),
then you only need to install that package.
Doing so will pull in all dependencies.

Assuming you still want your own installation of base_loom_server:

* Install [Python](https://www.python.org/downloads/) 3.11 or later on the computer.

* If you are using python for other things, you may wish to make a virtual environment
  dedicated to your loom server software. Look up "python virtual environment" on line.

* Install this [base_loom_server](https://pypi.org/project/base-loom-server/) package on the computer with command:

  * On Raspberry Pi: **sudo pip install base_loom_server**
  * On most other computers: **pip install base_loom_server**

  If you have a Raspberry Pi then you have three choices for installation:

  * Use sudo for all pip install commands. This is simplest.
  * Add "~/.local/bin" to your PATH. You can read about that on line.
  * Prefix the run command with ".local/bin", e.g. **.local/bin/run_example_loom**.

## Using this Package to Write a Loom Server

* Write a subclass of `BaseMockLoom` that emulates your loom.
  Two examples are `ExampleMockLoom` in this package and `MockLoom`
  in [toika_loom_server](https://pypi.org/project/toika-loom-server/).

* Write a subclass of `BaseLoomServer` that talks to the loom.
  Two examples are `ExampleLoomServer` in this package and `LoomServer`
  in [toika_loom_server](https://pypi.org/project/toika-loom-server/).

* Write a `main.py` like the one in this package, to run your loom server.

* Copy `tests/test_mock_loom.py` and modify it to suit your mock loom.

* The unit tests for your loom server should be able to use `testutils.BaseTestLoomServer`, as `tests/test_loom_server.py` does.

* Write a `pyproject.toml` like the one for [toika_loom_server](https://pypi.org/project/toika-loom-server/).

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
  or make a fork and git clone that.

* Inside the directory, issue the following commands:

    * **pip install -e .'[dev]'** (the single quotes are required in zsh, but not in bash)
      to make an "editable installation" of the package.
      An editable installation runs from the source code,
      so changes you make to the source are used when you run or test the code,
      without the need to reinstall the package.
      **'[dev]'** installs development-related packages such as pytest
      (see the file `pyproject.toml` for the full list).

    * **pre-commit install** to activate the pre-commit hooks.
    
    * **pytest** to test your installation.

* You may run an example loom server with: **run_example_loom mock**.
  Please only specify the **mock** serial port; connecting it to a real loom will not work
  (`ExampleMockLoom` is loosely based on a Séguin loom, but is not compatible).

  **run_example_loom mock** also accepts these command-line arguments:

    * **--reset-db** Reset the pattern database. Try this if you think the database is corrupted.

    * **--verbose** Print more diagnostic information.
  
  Note that the example loom server uses the same pattern database as
  [seguin_loom_server](<https://pypi.org/project/seguin-loom-server/)>)
  and [toika_loom_server](https://pypi.org/project/toika-loom-server/).

* To run mypy run: ***MYPYPATH=src mypy .***. This avoids complaints about module name ambiguity.

* In mock mode the web page shows a few extra controls for debugging.

* Warning: the web server's automatic reload feature, which reloads Python code whenever you save changes, *does not work* with this software.
  Instead you have to kill the web server by typing control-C several times, until you get a terminal prompt, then run the server again.
  This may be a bug in uvicorn; see [this discussion](https://github.com/encode/uvicorn/discussions/2075) for more information.
