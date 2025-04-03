# Loom Server

A loom server is a package based on [base_loom_server](https://pypi.org/project/base-loom-server/) that allows you to control a dobby loom from a web browser (e.g. on a phone or tablet). Two examples are [seguin_loom_server](https://pypi.org/project/seguin-loom-server/)
and [toika_loom_server](https://pypi.org/project/toika-loom-server/).

This document explains how to use any of these loom servers (though there may be a few loom-specific differences that are described in that package's documentation).

The first step is to [install](installing.md) the software. Once you have done that, read on:

## Connect to the Loom Server

Connect to the loom server using any modern web browser (e.g. on a phone, tablet, or laptop).
The address will be `http://*hostname*.local:8000` where *hostname* is the host name
of the loom server computer, as determined in [Installing](installing.md).

## Select the Mode

The server has two modes, which are listed at the top of the web page: Weaving and Threading:

* [Weaving](weaving.md) is used to weave fabric; this is by far the most common mode.

* [Threading](threading.md) will help you thread the loom, by lifting shafts for groups of threads.

Click on the word to select that mode.
The bold word shows the current mode.

The links above give detailed instructions for using each mode.
But before you dive into that, read the next section about pattern files:

## Upload and Select Pattern Files

Before you can weave or thread, you must upload one or more pattern files to the loom server.
The server accepts WIF (.wif), Fiberworks (.dtx), and WeavePoint (.wpo) files.

There are two ways to upload files:

* Push the "Upload" button.
* Drag and drop the files onto the web page (making sure the web page is gray before dropping them).

Once you have uploaded patterns, you can select one using the menu labeled "Pattern" (next to the "Upload" button).

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
