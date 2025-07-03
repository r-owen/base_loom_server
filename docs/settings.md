# Settings

This panel offers a few settings that you can change which apply to all weaving patterns.
Settings are automatically saved, and should survive rebooting the loom server.

These include:

* **Language**: which language to use.
  A language is listed as "preliminary" (in that language) if the translation is not well vetted.
  As of June, 2025 there are only two translations, both preliminary.
  If you can help correct or add any translations, it would be much appreciated.
  Read [Translations](translations.md) for more information.

  Note that changing languages reloads the page, but this should be fast and harmless.

* **Loom name**: the name of the loom, as it appears in the display.
  Feel free to use any name you like; it is purely for display purposes.
  If you have more than one computer-controlled loom, I suggest you name each differently.

* **Direction control**: specify how to change direction (weaving or unweaving, threading or unthreading).
  See [Weave Direction](weaving.md#weave-direction) for more information.
  This setting is not shown for Séguin looms and others that support changing direction from both software and a button on the loom.

* **Warp end 1**: specify whether to display warp end 1 on the right or left
  in the [Weaving](weaving.md) and [Threading](threading.md) pattern displays.
  However, this is as seen *from the front of the loom*.
  If you specify threading front-to-back, the threading pattern is displayed as seen from the back of the loom,
  so end 1 will be on the opposite side than what you specify here.

* **Threading**: specify whether you prefer to thread right-to-left or left-to-right, and front-to-back or back-to-front.
  Specifying front-to-back simply changes the Threading pattern display to appear as if you are sitting behind the castle:
  shaft 1 is displayed at the top and warp end 1 is displayed on the opposite side of that specified in "Warp end 1`".

* **Default threading group size**: specify the threading group size for newly uploaded patterns.
  This setting has no effect on any pattern files that are already loaded;
  use the "Group size" control in the [Threading](threading.md) panel to change those.
