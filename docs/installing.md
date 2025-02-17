# Installing

This page gives instructions for installing a loom driver such as
such as [seguin_loom_server](https://pypi.org/project/seguin-loom-server/)
or [toika_loom_server](https://pypi.org/project/toika-loom-server/)
that is based on [base_loom_server](https://pypi.org/project/base-loom-server/).

See [Coding](coding.md) if you want to work on [base_loom_server](https://pypi.org/project/base-loom-server/) or use it to develop a new loom driver.

1. Pick your Computer

    Decide which computer you will use to run the loom server.
    A macOS compute will work, and a used Mac Mini is a great choice (especially if you have a spare keyboard and monitor to get it set up).
    A Raspberry Pi (model 4 or better) will work, though it will be a bit slow when uploading patterns.
    A Windows computer or unix box should also work.

2. Install [Python](https://www.python.org/downloads/) 3.11 or later.

    The link has installers for common operating systems.

    Installing Python on Raspberry Pi is more difficult, though a new enough operating system may include a new enough Python.
    An easy way to install Python on Raspberry Pi is to use [this script](https://itheo.tech/installing-python-313-on-raspberry-pi-and-ubuntu).

3. Determine your computer's host name. In a terminal run:

        hostname

4. Determine the name of the port that your computer is using to connect to the loom.
  
    On macOS or linux:

    * Run this command to see which USB ports already in use, if any:

            ls /dev/tty.usb* 

    * Connect your computer to the loom with a USB cable.

    * Turn on the loom and wait a few seconds to let it connect.

    * Run the same command again. There should be one new entry,
      which is the name of the port connected to the loom.

3. Install the loom server software.

    From here on I will assume you are installing [toika_loom_server](https://pypi.org/project/toika-loom-server/). For [seguin_loom_server](https://pypi.org/project/seguin-loom-server/) replace "toika" with "seguin".
    
        sudo pip install toika_loom_server
    
    On some operating systems (including macOS) you can omit `sudo`.
    Definitely use `sudo` on Raspberry Pi.

4. Test the installation.

    First you may want to try the mock loom (since it does talk to your loom, and so avoids some complications):

        run_toika_server mock

    You should see the server start and you can connect to it with a web browser and try a few things out.
    Connect to the loom at `https://hostname.local/8000` where `hostname` is the host name you determined above
    (if the name already includes ".local", don't duplicate that).

    To control the real loom, specify the name of the USB port you found above:

        run_toika_server usb_port_name
