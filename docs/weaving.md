# Weaving

How to weave fabric.

This page assumes you have done all the [basics](index.md):

* Connected your web browser to the loom server
* Uploaded at least one pattern, and selected a pattern from the pattern menu
* Selected the Weaving mode.

## Pattern Display

The pattern is displayed as a picture that shows woven fabric below and potential future fabric above.
(This is the opposite of the usual US drawdown).
Note that the display is a bit naive, in that it shows all threads as the same thickness
and does not display multi-layer patterns (such as doubleweave) correctly.

There are two rectangles to the right of the pattern display:

* The short upper rectangle shows the color of the current pick (blank if pick 0),
    or, if you have specified a pick to jump to, then it is the color of that pick.

* The square button below that shows the weave direction: whether you are weaving (green down arrow) or unweaving (red up arrow).
    The arrow points in the direction cloth is moving through the loom.

    How you change direction depends on the loom:

    * Séguin looms allow you to change direction by pressing the square
      weave direction button and by pressing the UNW button on the dobby unit.
      Both work. Use whichever you prefer.

    * Toika looms can be operated in one of two ways, specified by
      a command-line argument when you start the loom server:

        * Software controls the weave direction. The square button showing weave
          direction can be pressed to change the direction. The physical button
          on the dobby head is ignored. This is the default.

        * The loom controls the weave direction. You have to press the physical button
          on the dobby head to change directions. The square button showing weave direction
          is only a display (you can't click it). You run in this mode by starting the loom server with argument `--weave-direction loom`,
    
    * For other looms, see the loom-specific documentation with the software package.

## Repeating

The software will automatically repeat patterns if you weave or unweave beyond the end.
However, you must advance twice when you reach an end, before the next set of shafts is raised.
The first advance will lower all shafts, as a signal that you have finished weaving or unweaving one pattern repeat.
The next advance will show the desired shed.

## Jumping

You can jump to a different pick and/or repeat number.
This is a two-step process: first you request the jump, then you advance to it by pressing the loom's pedal.
(Two steps are necessary because most looms will not accept an unsolicited command to raise shafts.)
In detail:

* Enter the desired pick and/or repeat numbers in the boxes on the "Jump to pick" line.
    The box(es) will turn pink and the Jump button will be enabled.

* Press the "return" keyboard key or click the "Jump" button on the web page
    to send the requested jump to the server.
    You will see several changes:

    * The jump input boxes will have a white background and the jump button will be disabled.

    * The pattern display will show the new pick in the center row, with a dotted box around it.
    (But if you are only changing the repeat number, the box will be solid.)

* Advance to the next pick by pressing the loom's pedal.
    Until you advance to the next pick, you can request a different jump
    (in case you got it wrong the first time) or cancel the jump in several ways:

    * Press the "Reset" button to the right of "Jump".

    * Reload the page.

    * Select a new pattern.
