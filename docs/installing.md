# Installing

This page gives instructions for installing a loom driver such as
such as [seguin_loom_server](https://pypi.org/project/seguin-loom-server/)
or [toika_loom_server](https://pypi.org/project/toika-loom-server/)
that is based on [base_loom_server](https://pypi.org/project/base-loom-server/).

See [Coding](coding.md) if you want to work on [base_loom_server](https://pypi.org/project/base-loom-server/) or use it to develop a new loom driver.

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

    From here on I will assume you are installing [toika_loom_server](https://pypi.org/project/toika-loom-server/).
    For [seguin_loom_server](https://pypi.org/project/seguin-loom-server/) replace "toika" with "seguin".
    On the command line:
    
        python -m pip install toika_loom_server

    Use `sudo` on Raspberry Pi to avoid having to hunt for the loom server executable in `~/.local/bin`:

        sudo python -m pip install toika_loom_server


4. Test the installation.

    Start with the mock loom (since it does not talk to your loom, and so avoids some complications).
    In a terminal:

        run_toika_server mock

    You should see the server start and you can connect to it with a web browser and try a few things out.
    Connect to the loom at `https://hostname.local/8000` where `hostname` is the host name you determined above
    (if the hostname ends with ".local", *don't* duplicate that).
    
    If `run_toika_server` is not found, the next step is to find out where pip installed it, and include the path as a prefix to the command:

    * On Raspberry Pi: if you did not install with `sudo` then it is probably in `~/.local/bin`:

        ~/.local/bin/run_toika_server mock

    * On Windows pip apparently installs executables in the Scripts sub-folder of the Python installation.
      To find Python you can try this command:
      
        where python
    
    or this:

        python -c "import os, sys; print(os.path.dirname(sys.executable))"
    
    Then look inside the Scripts subfolder of the reported path. The result may be something like this:

        C:\Python312\Scripts\run_toika_server mock

    To control the real loom, specify the name of the USB port you found above (prefixing the run command with any necessary path prefix):

        run_toika_server usb_port_name
