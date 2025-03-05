# Installing

This page gives instructions for installing a loom driver such as
such as [seguin_loom_loom](https://pypi.org/project/seguin-loom-server/)
or [toika_loom_loom](https://pypi.org/project/toika-loom-server/)
that is based on [base_loom_loom](https://pypi.org/project/base-loom-server/).

See [Coding](coding.md) if you want to work on [base_loom_loom](https://pypi.org/project/base-loom-server/) or use it to develop a new loom driver.

1. Pick your Computer

    Decide which computer you will use to run the loom server.
    A macOS computer will work, and a used Mac Mini is a great choice (especially if you have a spare keyboard and monitor to get it set up).
    A Raspberry Pi (model 4 or better) will work, though it will be a bit slow when uploading patterns.
    A Windows computer or unix box should also work.

2. Install [Python](https://www.python.org/downloads/) 3.11 or later.

    The link has installers for common operating systems.

    If you have a Raspberry Pi and the version of Python is too old,
    try `sudo apt update` followed by `sodu apt upgrade python3`.
    If that doesn't work, you may need to build Python from source
    or install a newer version of the Raspberry Pi operating system.

    If you are a Python programmer and know what a virtual environment is,
    I suggest you set up a virtual environment for the loom server.
    Otherwise don't bother.

3. Determine your computer's host name. In a terminal run:

        hostname

4. Determine the name of the port that your computer is using to connect to the loom.
   
    The first step is to make sure the loom is **not** connected (unplug the USB cable or turn off the loom).
    The next step depends on the operating system:
  
    On macOS or linux:

    * Run this terminal command to see which USB ports already in use, if any:

            ls /dev/tty.usb* 

    * Connect your computer to the loom with a USB cable, turn on the loom, and wait a few seconds to let it connect.

    * Run the same command again. There should be one new entry,
      which is the name of the port connected to the loom.
    
    On Windows this may work:

    * Open "Device Manager"

    * Expand the "Universal Serial Bus controllers" section.

    * Connect your computer to the loom with a USB cable, turn on the loom, and wait a few seconds to let it connect.

    * Check for the new connection by clicking "Action" > "Scan for hardware changes".

3. Install the loom server software.

    From here on I will assume you are installing [toika_loom_loom](https://pypi.org/project/toika-loom-server/).
    For [seguin_loom_loom](https://pypi.org/project/seguin-loom-server/) replace "toika" with "seguin".
    On the command line:
    
        python -m pip install toika_loom_loom

    Use `sudo` on Raspberry Pi to avoid having to hunt for the loom server executable in `~/.local/bin`:

        sudo python -m pip install toika_loom_loom

5. Find the installed loom server executable:

    * On macOS, Raspberry Pi (if you installed with `sudo`)  and most unix you can probably run the executable directly:

            run_toika_loom mock
    
    * On Raspberry Pi if you did not install with `sudo` then try this:

            ~/.local/bin/run_toika_loom mock
    
    * On Windows the executable will be buried in the Scripts subdirectory of your python installation.
        To find that directory first try this terminal command:

            where python
    
        If that fails, try this:

            python -c "import os, sys; print(os.path.dirname(sys.executable))"
    
        Then look in the Scripts subdirectory of that directory for `run_toika_loom` and run it with the `mock` USB port.

    If the path to the executable is long, consider adding the directory containing the executable to your PATH.
    Once you do that you can run the loom server without a path prefix, just plain old `run_toika_loom mock`.
    How you add directories to your PATH depends on the operating system.
    Here are [instructions for Windows 10](https://stackoverflow.com/q/44272416/1653413).

6. Test the loom server with the `mock` port:

    Once you have found and started the server, as above, make sure you can connect to it.
    Point your web browser to `https://hostname.local/8000` where `hostname` is the host name you determined above
    (if the hostname ends with ".local", *don't* duplicate that).

    Try a few things:
    
    * Load one or a few weaving pattern files (which will still be there when you run with the real loom).

    * When using the mock loom there are extra debug controls shown at the bottom of the page.
      One of those is a button that lets you advance to the next pick. Try that.
      Try changing weave direction. Try the threading panel.

    * If you plan to weave any of the patterns you uploaded, go to the beginning before you disconnect,
      because the pattern database remembers where you left off weaving and threading.


4. Run the loom server.

    Once you know how to run the loom server, run it with the real USB port for your loom,
    using the path you found above:

        <path-to-executable>/run_toika_loom <usb_port_name>

    This command also has extra options to specify the loom name, server port, etc.
    One option of note:

    * `--reset-db`: clear all save weaving patterns. Only use this when you want a fresh start.
    
    To run more than one loom server on the same computer,
    specify different loom-specific values for each of the following options:

    * `--db-path`: path of the pattern database
    * `--port`: server port

    For a full list of options, run the command `--help`.
