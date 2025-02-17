# Threading

The threading mode helps you correctly thread warp strings through the heddles.
Every time you press the pedal, the loom will raise the next group of shafts
and a display will show you which threads belong on which shaft.

This page assumes you have done all the [basics](index.md):

* Connected your web browser to the loom server
* Uploaded at least one pattern, and selected a pattern from the pattern menu
* Selected the Threading mode.

## Threading Display

Threading is displayed as a picture that shows a group of threads (vertical colored bars) and the shaft they go through (numbers that interrupt the colored bars).
It also shows the one or a few warp thread numbers along the top.

Warp end numbering goes up from 1 at the right (the typical US scheme when warping back to front).
Warp end 0 is special: it has no threads and is what a pattern starts with and is also an intermediate step when repeating a threading sequence.

There is one square button right of the pattern display which shows the direction.
A left-facing arrow indicates that you are threading right to left.

You can press the button to change the threading direction.

**Warning** the dobby's direction control is always ignored while threading.

## Repeating

The software will automatically repeat threading if you thread beyond the end.
However, you must advance twice when you reach an end, before the next set of shafts is raised.
The first advance will lower all shafts (going to warp end 0), as a signal that you have finished threading one pattern repeat.
The next advance will raise the desired shafts.

## Group Size

The "Group size" menu selects how many warp ends are in a group
(all shafts for a group are raised at once).

You can change the group size whenever you like (the change takes effect for the next thread group).
This can be convenient if threading a unit weave that also has sone non-unit-sized borders or other odd columns.

## Jumping

You can jump to a different warp end and/or repeat number.
The end number you specify will be the smaller warp end number,
e.g. if group size is 4 and you jump to 21, the displayed group will be ends 21, 22, 23, 24, and 25.

Jumping is a two-step process: first you request the jump, then you advance to it by pressing the loom's pedal.
(Two steps are necessary because most looms will not accept an unsolicited command to raise shafts.)
In detail:

* Enter the desired warp end and/or repeat numbers in the boxes on the "Jump to end" line.
    The box(es) will turn pink and the Jump button will be enabled.

* Press the "return" keyboard key or click the "Jump" button on the web page
    to send the requested jump to the server.
    You will see several changes:

    * The jump input boxes will have a white background and the jump button will be disabled.

    * The pattern display will show the new thread group, with a dotted box around it.
    (But if you are only changing the repeat number, the box will be solid.)

* Advance to the next group by pressing the loom's pedal.
    Until you advance to the next group, you can request a different jump
    (in case you got it wrong the first time) or cancel the jump in several ways:

    * Press the "Reset" button to the right of "Jump".

    * Reload the page.

    * Select a new pattern.
