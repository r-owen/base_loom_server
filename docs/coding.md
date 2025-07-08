# Coding

## Installing Source Code

* Install Python as explained in [Installing](installing.md).

* Download the source code from [github](https://github.com/r-owen/base_loom_server.git),
  or make a fork and git clone that.

* Inside the directory, do the following:

    * Make "editable installation" of the package.
      An editable installation runs from the source code,
      so changes you make to the source are used when you run or test the code,
      without the need to reinstall the package:

            pip install -e .'[dev]'
        
      where the single quotes around `[dev]` are required in zsh, but not in bash.
      `'[dev]'` installs development-related packages such as pytest
      (see the file `pyproject.toml` for the full list).
      
    * Activate the pre-commit hooks:

            pre-commit install
    
    * Run unit tests to test your installation:
    
            pytest

* You may run an example loom server with:

        run_example_loom <num_shafts> mock
  
  Please only specify the **mock** serial port; connecting it to a real loom will not work
  (`ExampleMockLoom` is loosely based on a Séguin loom, but is not compatible).

  `run_example_loom <num_shafts> mock` also accepts these command-line arguments:

    * `--reset-db` Reset the pattern database. Try this if you think the database is corrupted.

    * `--verbose` Print more diagnostic information.
  
  Note that the example loom server uses the same pattern database as
  [seguin_loom_server](https://pypi.org/project/seguin-loom-server/)
  and [toika_loom_server](https://pypi.org/project/toika-loom-server/).

* In mock mode the web page shows a few extra controls for debugging.

* Warning: the web server's automatic reload feature, which reloads Python code whenever you save changes,
  *does not work* with this software.
  Instead you have to kill the web server by typing control-C several times, until you get a terminal prompt, then run the server again.
  This may be a bug in uvicorn; see [this discussion](https://github.com/encode/uvicorn/discussions/2075) for more information.

## Writing a Loom Server

* Install the `base_loom_server` package either using pip, or from source (as described above).
  Source makes it easier to look through the code.

* Write a subclass of `BaseMockLoom` that emulates your loom.
  Two examples are `ExampleMockLoom` in this package and `MockLoom`
  in [toika_loom_server](https://pypi.org/project/toika-loom-server/).

  For simplicity and future compatibility, try to avoid overriding the constructor.
  Instead, perform loom-specific initialization by overriding the `__post_init__` method
  (which is normally a no-op in `BaseMockLoom`, so you need not call `super().__post_init__`).

* Write a subclass of `BaseLoomServer` that talks to the loom.
  Two examples are `ExampleLoomServer` in this package and `LoomServer`
  in [toika_loom_server](https://pypi.org/project/toika-loom-server/).

  For simplicity and future compatibility, try to avoid overriding the constructor.
  Instead, perform loom-specific initialization by overriding the `__post_init__` method
  (which is a no-op in `BaseLoomServer`, so you need not call `super().__post_init__`).

* Write a `main.py` like the one in `base_loom_server`, to run your loom server.

* Copy `tests/test_mock_loom.py` and modify it to suit your mock loom.

* The unit tests for your loom server should be able to use `testutils.BaseTestLoomServer`, as `tests/test_loom_server.py` does.

* Write a `pyproject.toml` like the one for [toika_loom_server](https://pypi.org/project/toika-loom-server/).
