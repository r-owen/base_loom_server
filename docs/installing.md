# Installing

This page gives instructions for installing a loom server such as
such as [seguin_loom_server](https://pypi.org/project/seguin-loom-server/)
or [toika_loom_server](https://pypi.org/project/toika-loom-server/)
that is based on [base_loom_server](https://pypi.org/project/base-loom-server/).

See [Coding](coding.md) if you want to work on [base_loom_server](https://pypi.org/project/base-loom-server/) or use it to develop a new loom driver.

## Installing a Loom Server

1. Pick your Computer

    Decide which computer you will use to run the loom server.
    Any macOS, Windows, or linux computer will work, and a laptop is a fine choice,
    especially as you can run your web browser on the same machine that runs the server.

    The software uses minimal resources, so an old, slow computer is fine.
    A Raspberry Pi 5 works well; a model 4 will also work, but is not recommended, because it is slow when uploading patterns and takes a long time to boot up.
    A used Mac Mini is also a good choice, if you have a spare keyboard and monitor to get it set up.

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

    * Run this terminal command to see which USB ports are already in use, if any:

            ls /dev | grep -i "tty.*usb.*"

    * Connect your computer to the loom with a USB cable, turn on the loom, and wait a few seconds to let it connect.

    * Run the same command again. There should be one new entry, which is the name of the port connected to the loom.
      If not, wait a bit longer and try again.

    * The actual port name starts with "/dev/". So, for example, if the `ls /dev...` command shows "tty.usbserial-FT7UMAY8" then the port name is "/dev/tty.usbserial-FT7UMAY8"
    
    On Windows this may work:

    * Open "Device Manager"

    * Expand the "Universal Serial Bus controllers" section.

    * Connect your computer to the loom with a USB cable, turn on the loom, and wait a few seconds to let it connect.

    * Check for the new connection by clicking "Action" > "Scan for hardware changes".

5. If you plan to run the server computer "headless" (no monitor, keyboard, or pointer device), [create a WiFi hotspot](#creating-a-wifi-hotspot).

6. Install the loom server software.

    From here on I will assume you are installing [toika_loom_server](https://pypi.org/project/toika-loom-server/).
    For [seguin_loom_server](https://pypi.org/project/seguin-loom-server/) replace "toika" with "seguin".

    On Raspberry Pi, it is convenient to install with `sudo` to avoid having to hunt for the loom server executable in `~/.local/bin`:

        sudo python -m pip install toika_loom_server
    
    On other operating systems you can probably skip `sudo`, and Windows does not support `sudo`:

        python -m pip install toika_loom_server

    In either case, watch pip's output. Near the end it should tell you where it installed `run_toika_loom`.

7. Learn about the [command-line options](#command-line-options) available.

    Use the command line options that seem useful on the run commands below.

8. Find the installed loom server executable:

    * On macOS, Raspberry Pi (if you installed with `sudo`) and most unix you can probably run the executable directly:

            run_toika_loom <num_shafts> mock

        where <num_shafts> is the number of shafts you wish the mock loom to have.
        If that does not work, look at pip's output to see where it was installed.
    
    * On Raspberry Pi if you did not install with `sudo` then it is probably here (if not, look at pip's output):

            ~/.local/bin/run_toika_loom <num_shafts> mock

    * On Windows the executable will probably be buried in the Scripts subdirectory of your python installation.
        Again, pip's output should tell you where.

    If the path to the executable is long or hard to remember, consider adding the directory containing the executable
    to your "PATH", or in the case of macOS or unix, making an alias (a short word that will run the command).
    On macOS and unix you do this by editing a shell configuration file, which you can read about online.
    Here are [instructions for Windows 10](https://stackoverflow.com/q/44272416/1653413).

9. Test the loom server with the `mock` port:

    Once you have found and started the server with the mock port, as explained in the previous step, make sure you can connect to it.
    Point your web browser to `http://hostname.local:8000` where `hostname` is the host name you determined above
    (if the hostname ends with ".local", *don't* duplicate that).

    If you are running the web server on the same computer as the web browser (e.g. using a laptop)
    you can also use this simpler address: `http://localhost:8000`.

    Try a few things:
    
    * Load one or a few weaving pattern files (which will still be there when you run with the real loom).

    * When using the mock loom there are extra debug controls shown at the bottom of the page.
      One of those is a button that lets you advance to the next pick. Try that.
      Try changing weave direction. Try the threading panel.

    * If you plan to weave any of the patterns you uploaded, go to the beginning before you disconnect,
      because the pattern database remembers where you left off weaving and threading.

## Running a Loom Server

Once you know how to run the loom server, run it with the real USB port for your loom.
Be sure to include the [command line options](#command-line-options) you wish to use,
even though they are not shown here.

The loom must be turned on and connected to your server computer before you can
run the loom server (because the USB port will not exist, otherwise).

On macOS or unix:

    run_toika_loom <num_shafts> <usb_port_name>

or, if it is not on the PATH:

    <path-to-executable>/run_toika_loom <num_shafts> <usb_port_name>

On Windows:

    run_toika_loom.exe <num_shafts> <usb_port_name>

or, if it is not on the PATH:

    <path-to-executable>/run_toika_loom.exe <num_shafts> <usb_port_name>

<num_shafts> is the number of shafts your loom has. This is used in two ways:

* Pattern files that have too many shafts are rejected.
* The data format used by Toika ES dobby heads varies depending on the number of shafts.
    If you specify the wrong value, the loom will not work correctly.
    (Séguin looms do not have this issue).

## Command Line Options

The run_x_loom commands (e.g. run_toika_loom) accept various command line options.

To run more than one loom server on the same computer,
specify loom-specific values for each of the following options:

* `--db-path`: path of the pattern database

* `--port`: web server port

Other options of note (not complete; run with `-h` or `--help` to see the rest):

* `-v` or `--verbose`: show much more information in the log.
    This can be very useful for debugging problems.
    If you want to report a bug, please run this way and provide the output.

* `--nmcli-wifi`: enable a line in the Settings panel that controls WiFi.
    This setting should only be used all of the following are true:

    * The loom server is running "headless" (no monitor, pointer, or keyboard).
        Note: if the server has a monitor, etc., it is better to use the standard GUI-based tools to manage WiFi.
    * The loom server must have `nmcli`  (NetworkManager) installed,
        and must be allowed to run nmcli with sudo privileges.
        nmcli only runs on Linux-based operating systems (and is installed by default on most);
        it does not run on macOS or Windows.
    * The loom server should not have `dnsmasq`, because that interferes with running a WiFI hotspot.
        See [Creating a WiFi Hotspot](#creating-a-wifi-hotspot) for a command to uninstall `dnsmasq`.

    A default Raspberry Pi installation should have all of this, but you may have to uninstall `dnsmasq`.

* `--reset-db`: clear all save weaving patterns.
   Use this when you want to clear all patterns, or if you think the database might be corrupted.
   (You can also delete the database file manually, while the loom server software is not running, if you prefer).

* `-h` or `--help`: print help describing all command line options, then quit.

## Creating a WiFi Hotspot

Running a WiFi hotspot on your loom server is crucial if you do not have WiFi near your loom.
The server runs its own WiFI hotspot network, and you connect your device (tablet, phone, etc.) to that network to talk to the server and control the loom.

If you run your server "headless" (no monitor, keyboard, or pointing device),
then you should set up a hotspot as a fallback.
If the server cannot connect to your own WiFi when it starts up,
it will fall back to running the hotspot, and you can still weave.

These instructions are for Linux (e.g. Raspberry Pi).
If you plan to run macOS or Windows headless I'll leave it to you to find the instructions.

* Disable `dnsmask` with `sudo apt purge dnsmasq` because dnsmasq interferes with running a hotspot.
* Create a hotspot and configure it to auto-start,
    where `<hotspot-name>` and `<hotspot-password>` are the desired WiFi network name and password of the hotspot:

        sudo nmcli device wifi hotspot ifname wlan0 ssid <hotspot-name> password <hotspot-password>
        sudo nmcli connection modify <hotspot-name> connection.autoconnect yes connection.autoconnect-priority 100

* If you want the loom server to connect to your own WiFI, set it up as follows,
    where `<wifi-name>` and `<wifi-password>` are the name and password of of your WiFI network:

        sudo nmcli device wifi connect <wifi-name> password <wifi-password>
        sudo nmcli connection modify <wifi-name> connection.autoconnect yes connection.autoconnect-priority 50

    Note: a connection with lower numeric priority is tried first.

* Bring up the preferred connection:

        sudo nmcli device up <wifi-or-hotspot-name>

## Upgrading Software

Use pip to upgrade your software. Include a prefix of "sudo" if you performed the original install using sudo. Thus one of:

        sudo python -m pip install --upgrade dtx_to_wif base_loom_server toika_loom_server
    
or

        python -m pip install --upgrade dtx_to_wif base_loom_server toika_loom_server

On Toika's built-in web server you will almost certainly have to include the scary-looking `--break-system-packages` argument. Don't worry; it is safe in this context.
Note that Toika does not install using sudo:

        python -m pip install --upgrade dtx_to_wif base_loom_server toika_loom_server --break-system-packages

See pip's documentation for more information, including how to specify specific versions of packages.
