# Loom Server

A loom server is a package based on [base_loom_server](https://pypi.org/project/base-loom-server/) that allows you to control a dobby loom from a web browser (e.g. on a phone or tablet). Two examples are [seguin_loom_server](https://pypi.org/project/seguin-loom-server/)
and [toika_loom_server](https://pypi.org/project/toika-loom-server/).

A loom server supports two modes:

* Weaving: the usual mode.
* Threading: raise shafts for sequential groups of warp threads.

In both cases the first steps are:

* Connect to the loom server
* Select the desired mode
* Upload one or more pattern files

## Connect to the Loom Server

Connect to the loom server using any modern web browser (e.g. on a phone, tablet, or laptop).
The address will be "http://*hostname*.local:8000" where *hostname* is the host name of the loom server computer

## Select the Mode

The server has two modes, which are listed at the top: [Weaving](weaving.md) and [Threading](threading.md).
Click on the word to select that mode.
The bold word shows the current mode.

## Upload and Select Pattern Files

Before you can weave or thread, you must upload one or more pattern files to the loom server.
The server accepts both WIF (.wif) and Fiberworks (.dtx) files.

There are two ways to upload files:

* Push the "Upload" button.
* Drag and drop the files onto the web page (making sure the web page is gray before dropping them).

Once you have uploaded patterns, you can select one using the menu labeled "Pattern", just to the left of the "Upload" menu.

The loom server remembers the 25 most recent patterns that you have uploaded,
and this information is saved on disk, so should not be lost in a power failure.

The saved information includes the most recent pick (weaving) and the most recent warp thread group (threading).
This allows you to switch between different patterns while weaving something.
However, if you upload a new pattern with the same file name as a saved pattern,
the new pattern overwrites the old and the pick and warp thread group information is reset.
So please be careful.

To clear out the pattern menu (which may become cluttered over time),
select "Clear Recents", the last item in the pattern menu.
This clears out information for all patterns except the current pattern.

You can also restart the loom server with the **--reset-db** command-line argument.
This can be useful if upgrading to a new version of the loom software that has an incompatible database format.

## Multiple Connections

The server only allows one web browser to connect, and the most recent connection wins.
This prevents a mystery connection from hogging the loom.
If the connection is dropped on the device you want to use for weaving,
simply reload the page to regain the connection.

## Reset the Loom Connection

Every time you connected to the web server or reload the page, the server refreshes
its connection to the loom (by disconnecting and immediately reconnecting).
So if the server is reporting a problem with its connection to the loom,
and it is not due to the loom losing power, or a disconnected or bad USB cable,
you might try reloading the page.

If the loom seems confused, try turning off the loom, waiting a few seconds, then turning it on again.
Then reload the web page, to force the web server to make a new connection to the loom.

## Base Loom Server

This documentation is for base_loom_server, a base package that can be used to write loom servers for specific looms. base_loom_server does most of the work, so this documentation tells you how to weave
with any loom server based on this package.
