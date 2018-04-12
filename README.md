Guppy Animation Tools is a collection of tools to help with animation
production in Maya.

Guppy Animation tools and all associated files are licensed under the
GNU Lesser General Public License version 3.0 unless otherwise stated.


- [Install](#install)

- [Arc Tracer](#arc-tracer)
- [Clever Keys](#clever-keys)
- [Lock 'n Hide](#lock-n-hide)
- [Move My Objects](#move-my-objects)
- [Rename It](#rename-it)
- [Slide Animation Keys](#slide-animation-keys)
- [Zero Selection](#zero-selection)


## Install ##

#### Download ####
Regular Users: [Download Guppy Animation Tools as a zip file here.](https://github.com/assumptionsoup/guppy_animation_tools/archive/master.zip)<br>
Developers: Feel free to clone/fork the repo.  Add the repo to your PYTHONPATH,
it should be named "guppy_animation_tools".  Import the specific tool you
need.  Skip ahead to the [usage section](#usage).

#### Move Files ####

1. If you downloaded the zip archive, extract it.
2. Rename the top folder "guppy_animation_tools" without the quotes.  Make sure
that this is the TOP folder.  Some zip extraction tools will add an extra
folder!

3. Move the guppy_animation_tools folder to Maya's "scripts" directory. In
windows this should be "My Documents/Maya/scripts".  In linux this should be
"~/maya/scripts".


If you're having trouble finding a directory you can write to, you can try
running the following lines in the python script editor in Maya.  It should
print out all the directories you can use.
```
import maya.mel as mel
print '\n'.join(mel.eval('getenv("PYTHONPATH")').split(';'))
```

#### Setup ####

The userSetup.py file is a python script that Maya executes on startup.
It should be in Maya's "scripts" directory - the same directory you put
the guppy_animation_tools folder in.  You may have to create this file
if it does not exist.


Add the following lines to your userSetup.py:
```
import maya.cmds as cmds
cmds.evalDeferred("from guppy_animation_tools import *")
```

## USAGE ##

All of the commands given below are python. Some of these tools, are
meant to be run as hotkeys. If you don't know how to set a hotkey in
Maya, [the documentation is an excellent place to
learn.](https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2016/ENU/Maya/files/GUID-92F8EBD9-A658-4A1E-9D85-571B5B809F52-htm.html)


#### Arc Tracer ####

Arc Tracer is a tool that can visually display the arc of an animated
object or point on a mesh.  It aims to have a few extra features not
found in most other arc tracers, such as a display-over-mesh feature and
displaying sub-frame arc information.

![Arc Tracer Overview Image](../doc_assets/arc_overview.gif )

**IMPORTANT** Arc Tracer has not yet been updated to use viewport 2.0
As a stop-gap measure, in order to see anything in Maya 2017 update 3 or
later, you must set the `MAYA_ENABLE_VP2_PLUGIN_LOCATOR_LEGACY_DRAW`
before launching maya.  In bash terminals this is done by running
this command before launching:

    export MAYA_ENABLE_VP2_PLUGIN_LOCATOR_LEGACY_DRAW=1

To create an arc tracer, select a node you want to trace, then run the
python command:

    arcTracer.create()

If you want an arc tracer to always be run with the same settings,
first create an arc tracer with the settings you like, then run:

    arcTracer.getShortcut()

This will print out the command needed to create an arc tracer with
those settings.  You can make that your default hotkey/shelf button.

This command will let you trace mesh.  Run this python command and click
the point on the mesh you want to trace.  A word of warning: this was an
experiment that has mostly been abandoned due to being **extremely
slow**.  If you want to use this with the getShortcut command, just
replace arcTracer.create with arcTracer.atPoint from the output.

    arcTracer.atPoint()


**Settings**

_A brief description of the settings on the Arc Tracer node._

- _Past Frames:_ How many frames to trace before the current one.
- _Future Frames:_ How many frames to trace after the current one.
- _Min Subframes:_ The minimum number of subframes to calculate.  Arc Tracer
tries to guess at a good number of subframes to calculate between the minimum
and maximum based on the camera distance.  If Min and Max subframes are at the
same number, this will force Arc Tracer to calculate exactly that many subframes.
- _Max Subframes:_ The maximum number of subframes to calculate.
- _Show Arc:_ Shows the arc curve.
- _Overlay Arc:_ Shows the arc curve on top of every object in the scene.
- _Show Frame Numbers:_ Shows the frame numbers (duh) on the arc.
- _Show Frame Markers:_ Shows dots on each frame.
- _Frame Markers Scale To Camera:_ The size of the markers will stay the same on
the screen no matter how much you zoom in or out.
- _Frame Marker Size:_ The size of the frame markers.  There is no control for the
size of frame numbers.
- _Update On Playback:_ New frame information will be gathered when the current
frame is changed.
- _Use Refresh Mode:_ Only use this if Arc Tracer doesn't seem to be tracing the
object correctly. By default Arc Tracer tries to use methods in Maya that avoid a
full scene DG evaluation (which is slow). However, these methods can fail to
work correctly in certain circumstances (usually involving IK's or expressions).
<br><br>Enabling this mode will make the Update button move the current frame and refresh
the entire scene for every frame needed.  This will result in the most accurate
positional data from Maya.
- _Update:_ Updates the Arc Tracer.


#### Clever Keys ####

Clever Keys provides a simple way to key selected attributes. It
determines which attributes to key based on the mouse position and tries
to always insert a key.

But what exactly what is keyed and when? Roughly, if your cursor is over
the graph editor, things selected in the graph editor will be keyed,
otherwise attributes selected in the channel box will be keyed. What
specifically happens can be tweaked in the various options listed below.

![Clever Keys Overview Image](../doc_assets/cleverkeys_overview.gif)


This is the main command, setting a key.  I suggest setting this to your
default setKey hotkey, "s".  It might also be a good idea to set Maya's
original hotkey to something like Shift + "s".  I've tried to make this
script as bug free and stable as possible.  But if something does go wrong
at some point and you do need to set a normal key again, it's nice to
have the fallback already set up.

    cleverKeys.setKey()


_Everything from here on is just icing on the cake.  If you just want
to use the default Clever Keys, you don't need to read any further._

If you don't want clever keys to try to insert keys, you can use this
command instead:

    cleverKeys.setKey(insert=False)

When working in the graph editor, if any part of an animation curve is
selected Clever Keys will only key the selected curve(s) and not any
other attributes.  To disable this, you can use the option:

    cleverKeys.setKey(usePartialCurveSelection=False)

Even with this option set, if an entire curve is selected (not just part
of it) Clever Keys will only key the selected curve(s) and not any other
attributes.  To disable curve filtering entirely, you can use the option:

    cleverKeys.setKey(useSelectedCurves=False)

Clever keys can help you clear your selected attributes.

    cleverKeys.clearAttributes()

This command works the same way that Clever Keys does.  It clears
whatever is under your mouse.  If you want to just clear a specific
window, you can use either of these:

    cleverKeys.clearAttributes(graphEditor=True)
    cleverKeys.clearAttributes(channelBox=True)

Or to clear them both:

    cleverKeys.clearAttributes(graphEditor=True, channelBox=True)

CleverKeys can help you sync your selection between the graph editor and
the channel box.

    cleverKeys.selectSimilarAttributes()

If your mouse is over the graph editor, this will sync the attributes
selected in the Graph Editor to the Channel Box.  If your mouse is not
over the graph editor, this will sync the channels selected in the
channel box to the ones in the graph editor.

To explicitly select similar attributes in the Graph Editor without
detecting where your mouse is, use:

    cleverKeys.selectSimilarAttributes(detectCursor=False)

To explicitly sync the Channel Box to the Graph editor, use the following
command.

    cleverKeys.syncGraphEditor()

To sync the Graph Editor to the Channel box, use this python command:

    cleverKeys.syncChannelBox()

#### Lock 'n Hide ####

Lock 'n Hide is a tool that allows you to lock and or hide attributes on
referenced nodes.  You can restore the original state at any time.

Lock 'n Hide can be opened with the python command:

    lock_n_hide.ui()

If you want to use an action without using the GUI, right click on the
action to copy it to the keyboard. You can then make a hotkey or shelf
button by pasting this in the appropriate area. You do not have to have
the UI open in order to use these hotkeys.

Attributes not modified by Lock 'n Hide that are hidden or locked on
referenced nodes can not be unlocked or unhidden.  This is to protect
asset integrity.


#### Move My Objects ####

Move My Objects is a simple tool to save and restore the world position
of nodes.

![SAK Overview Image](../doc_assets/mmo_overview.gif)

Move My Objects can be opened with the python command:

    moveMyObjects.ui()

If you want to use an action without using the GUI, right click on the
action to copy it to the keyboard. You can then make a hotkey or shelf
button by pasting this in the appropriate area. You do not have to have
the UI open in order to use these hotkeys.


#### Rename It ####

Rename It is a simple, but powerful renaming tool. It is opened with
the following python command:

    renameIt.ui()

RenameIt can do simple renaming. It understands ending numbers and how
to pad node names.

![Rename It Padding Image](../doc_assets/renamit_padding.gif)

RenameIt can also search and replace text.

![Rename It Simple Rename Image](../doc_assets/renameit_simple_rename.gif)

For the advanced user, RenameIt can also do complex regex search and
replace. The up/down arrow keys can be used to bring up previous entries.

![Rename It Regex Rename Image](../doc_assets/renameit_regex_rename.gif)


#### Slide Animation Keys ####

Slide Animation Keys helps you quickly adjust the values of multiple
keys.
![SAK Overview Image](../doc_assets/sak_overview.gif)

Slide Animation Keys uses a lot of the same selection logic that Clever
Keys uses. If your graph editor is open it will work on the selected
keys. If no keys are selected or the graph editor is closed, it will
work on the keys on the selected object on the current frame.

Slide Animation Keys is opened with the python command:

    slideAnimationKeys.ui()

Right click to adjust settings. If you want to use an action without
using the GUI, right click on the action to copy it to the keyboard.
You can then make a hotkey or shelf button by pasting this in
the appropriate area. You do not have to have the UI open in order
to use these hotkeys.

![SAK Configure UI Image](../doc_assets/sak_configure.gif)

***
**Blend Modes**

![SAK Blend Image](../doc_assets/sak_blend.gif)

_Blend mode_ moves all keys towards the previous and next keys.

![SAK Shift Image](../doc_assets/sak_shift.gif)

_Shift mode_ shifts the keys as a block towards the previous and next keys.

![SAK Average Image](../doc_assets/sak_average.gif)

_Average mode_ moves keys toward the average of the previous and next key per attribute.

![SAK Level Image](../doc_assets/sak_level.gif)

_Level mode_ moves all keys toward a single average value.

![SAK Shrink Image](../doc_assets/sak_shrink.gif)

_Shrink mode_ shrinks each key towards each other on every frame.

![SAK Linear Image](../doc_assets/sak_linear.gif)

_Linear mode_ makes a line between the previous key and the next key per attribute.

![SAK Default Image](../doc_assets/sak_default.gif)

_Default mode_ moves all keys toward their defaults (zero for most attributes).

#### Zero Selection ####

Zero Selection returns the selected attributes to their default values.

Zero Selection uses the same logic as Clever Keys when choosing what
attribute to zero out.  Zero Selection is run with the python command:

    zeroSelection.zeroSelection()



