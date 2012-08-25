Guppy Animation Tools is a loose collection of scripts to help animators in Maya.

### _License_ ###
***
All scripts contained in Guppy Animation tools script are licensed under the 
GNU Lesser General Public License version 3.0.  The full license is contained 
in the License directory of this project.

# Index #
***
**[About](#about)**

- [General](#general)
- [Arc Tracer](#arc-tracer)
- [Clever Keys](#clever-keys)
- [Lock 'n Hide](#lock-n-hide)
- [Move My Objects](#move-my-objects)
- [Slide Animation Keys](#slide-animation-keys)
- [Zero Selection](#zero-selection)

**[To Install](#to-install)**

- [Move Files](#move-files)
- [Setup usersetup.mel](#setup-usersetup.mel)

**[Usage](#usage)**

- [Arc Tracer](#arc-Tracer-Usage)
- [Clever Keys](#clever-keys-usage)
- [Lock 'n Hide](#lock-n-hide-usage)
- [Move My Objects](#move-my-objects-usage)
- [Slide Animation Keys](#slide-animation-keys-usage)
- [Zero Selection](#zero-selection-usage)

---

# About #
***
### General ###
This is the live code repository to Guppy Animation Tools. Scripts in this 
repository will be updated as I write them.  They will contain the newest 
features, the newest bug fixes, and the newest bugs.
 
Gupy Animation Tools is just a loose collection of scripts I've written to help animators.  It is not intended to be a cohesive suite of scripts, but rather 
various odds and ends I've written at animators' requests.

### Arc Tracer ###
Arc Tracer is a script/plugin combo that can visually display the arc of an 
animated object or point on a mesh.  It aims to have a few extra features 
not found in most other arc tracers, such as a display on top feature and 
displaying sub-frame arc information.

### Clever Keys ###
Clever Keys is a script that allows animators to quickly key selected 
attributes in both the graph editor and the channel box.  It determines 
which attributes to key based on the mouse position and tries to always 
insert a key.

### Lock 'n Hide ###
Lock 'n Hide is a script/plugin combo that allows animators to lock and or hide
attributes on referenced nodes.  Animators can restore the original state of
changed attributes at any time.  Attributes not modified by Lock 'n Hide that 
are hidden or locked on referenced nodes can not be unlocked or unhidden.  This
is to protect asset integrity.

### Move My Objects ###
Move My Objects is a simple script to save and restore the world position of 
a single object.

### Slide Animation Keys ###
Slide Animation Keys is a script that allows an animator to quickly adjust 
multiple keys.  It has a simple interface that is extremely customizable, 
and multiple modes to determine how to move the keys.

### Zero Selection ###
Zero Selection is a small script that quickly lets the user return the selected 
attributes to their default values.

# To Install #
***
### Move Files ###
_If you've installed scripts and plugins for Maya before, you probably already 
know where to put these files._

**Advanced User Note:** _On my local machine I hardlink these files to the 
correct directory so I can use the latest version in Maya while keeping 
everything version controlled in git._

1. Files in the Scripts directory and in the Plugins/AETemplates directory 
need to be placed in a Maya scripts directory. In windows this should be 
My Documents/Maya/scripts.
<br><br>
If you're having trouble finding a directory you can write to, you can try 
running the following lines in the python script editor in Maya.  It should 
print out directories you can use.
```
import maya.mel as mel
print '\n'.join(mel.eval('getenv("MAYA_SCRIPT_PATH")').split(';'))
```

2. Files in the Plugins/Python directory need to be placed in a Maya plug-ins 
directory.  In windows, should be My Documents/Maya/plug-ins.  You may have to 
create this folder if it doesn't exist.
<br><br>
If you're having trouble finding a directory you can write to, you can try 
running the following lines in the python script editor in Maya.  It should 
print out directories you can use.
```
import maya.mel as mel
print '\n'.join(mel.eval('getenv("MAYA_PLUG_IN_PATH")').split(';'))
```

3. Icons in the Plugins/Icon directory can be placed in a Maya icons
directory. In windows this should be My Documents/Maya/prefs/icons. You 
may have to create this folder if it doesn't exist.
<br><br>
If you're having trouble finding a directory you can write to, you can try 
running the following lines in the python script editor in Maya.  It should 
print out directories you can use.
```
import maya.mel as mel
print '\n'.join(mel.eval('getenv("XBMLANGPATH")').split(';'))
```

### Setup usersetup.mel ###
usersetup.mel is a mel file that should be in your Maya scripts directory. 
You may have to create this file if it does not exist.  Anything in this 
file is run when Maya starts up.

**Advanced User Note:** _I prefer using usersetup.mel over usersetup.py because
usersetup.py is run much sooner than usersetup.mel, often before Maya's ui is 
fully loaded._


Add the following lines to your usersetup.mel:
```
python("import arcTracer");
python("import cleverKeys");
python("import lock_n_hide");
python("import moveMyObjects");
python("import slideAnimationKeys");
python("import zeroSelection");
```

# USAGE #
***
*Please note that while Guppy Animation Tools is primarily written in python,
all of the commands in this section are MEL.  So be sure to make mel hotkeys/shelf 
buttons!*

**Advanced User Note:** _This is because older versions of Maya did not have python
hotkeys._

Some of these scripts, like clever keys, are meant to be run as hotkeys. If you don't know how to set a hotkey in Maya, [the documentation is an excellent place to 
learn.](http://download.autodesk.com/global/docs/maya2012/en_us/index.html?url=files/PC_Assign_a_MEL_script_to_a_hotkey.htm,topicNumber=d28e54174)


### Arc Tracer Usage ###
---
To create an arc tracer, run:

    python("arcTracer.create()");

If you want an arc tracer to always be run with the same settings, 
first create an arc tracer with the settings you like, then run:

    python("arcTracer.getShortcut()");

This will print out the command needed to create an arc tracer with 
those settings.  You can make that your default hotkey/shelf button.

This command will let you trace mesh.  Just run it and click the point 
on the mesh you want to trace.  A word of warning: this was an experiment 
that has mostly been abandoned due to being **extremely slow**.  If you 
want to use this with the getShortcut command, just replace arcTracer.create 
with arcTracer.atPoint from the output.

    python("arcTracer.atPoint()");

---
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
full scene DG evaluation (which is slow). However, these methods can fail to work correctly in certain circumstances (usually involving IK's or expressions). 
Enabling this mode will make the Update button move the current frame and refresh 
the entire scene for every frame needed.  This will result in the most acurrate 
positional data from Maya.
- _Update:_ Updates the Arc Tracer.


### Clever Keys Usage ###
---

**General**
Clever keys tries to provide a simple and intuitive way to key the selected 
attributes. Exactly what is keyed and when is described below.

If the mouse is over the graph editor, and a curve is selected, it will key 
just that curve, otherwise, it will key all the attributes selected there. If 
no attributes are selected in the graph editor, it will key all the attributes 
in the graph editor. If the mouse is not over the graph editor, it will key the 
attributes selected in the channel box.  If the channelBox is closed it will key all the attributes on the selected node.  It attempts to use the "Insert Key" function which makes keys match the curvature of the surrounding keys whenever possible.

**Commands**

---

This is the main command, setting a key.  I suggest setting this to your 
default setKey hotkey, "s".  It might also be a good idea to set Maya's 
original hotkey to something like Shift + "s".  I've tried to make this 
script as bug free and stable as possible.  But if something does go wrong 
at some point and you do need to set a normal key again, it's nice to 
have the fallback already set up.

    python("cleverKeys.setKey()");

---
_Everything from here on is just icing on the cake.  If you just want 
to use the default Clever Keys, you don't need to read any further._

If you don't want clever keys to try to insert keys, you can use this 
command instead:

    python("cleverKeys.setKey(insert = False)");

When working in the graph editor, if an animation curve is selected 
Clever Keys will only key the selected curve(s) and not any other 
attributes.  To disable this, you can use the option:

    python("cleverKeys.setKey(useSelectedCurves = False)");

In Maya 2011 and later it is very easy to clear a channel selection.  
You just have to click away from the channel.  Before 2010 things were 
a little trickier.  To help with this, I've added the clear command, 
which will clear your selection.

    python("cleverKeys.clearAttributes()");

That command works the same way that Clever Keys does.  It clears 
whatever is under your mouse.  If you want to just clear a specific 
window, you can use either of these:

    python("cleverKeys.clearAttributes(graphEditor = True)");
    python("cleverKeys.clearAttributes(channelBox = True)");

Or to clear them both:

    python("cleverKeys.clearAttributes(graphEditor = True, channelBox = True)");

Select similar attributes.  If your mouse is over the graph editor, this 
will take any attribute you have selected and select that attribute on all 
of the nodes in your graph editor.  If your mouse is not over the graph
editor, this will sync the channels you have selected in the channel box
to the ones in the graph editor.

    python("cleverKeys.selectSimilarAttributes()");

To explicitly select similar attributes in the Graph Editor without 
detecting where your mouse is, use:

    python("cleverKeys.selectSimilarAttributes(detectCursor = False)");

To explicitly sync the Channel Box to the Graph editor, use the following
command. Unfortunately, as far as I know, Maya doesn't offer me enough 
control to write a command that syncs the channel selection the other way.

    python("cleverKeys.syncGraphEditor()");

### Lock 'n Hide Usage ###
---
Lock 'n Hide can be used with or without a GUI.  To open the gui, use the 
command:

    python("lock_n_hide.ui()");

---
_The following commands can be used if you don't wish to have a GUI.  You 
do not need them if you plan to use the GUI._

To lock the selected attributes:

    python("lock_n_hide.lock()");

To lock and hide the selected attributes:

    python("lock_n_hide.lockHide()");

To reset the selected attributes:

    python("lock_n_hide.reset()");

To reset all the attributes in the scene:

    python("lock_n_hide.resetAll()");

### Move My Objects Usage ###
---
Move My Objects can be used with or without a GUI.  To open the gui, use the 
command:

    python("moveMyObjects.ui()");

---
_The following commands can be used if you don't wish to have a GUI.  You 
do not need them if you plan to use the GUI._

To save an object's position without the GUI use:

    python("moveMyObjects.savePosition()");

To apply a position to an object without the GUI use:

    python("moveMyObjects.applyPosition()");


### Slide Animation Keys Usage ###
---

**General**

Slide Animation Keys uses a special subset of the selectedAttributes.py 
module to help get relevant selected attributes. If your graph editor is 
open it will work on the selected keys. If no keys are selected or the 
graph editor is closed, it will work on the keys on the selected object 
on the current frame. This last behavior can be disabled in the settings 
by unchecking "Use Keys on Current Frame" and pressing apply.

**Commands**

---
Slide Animation Keys is primarily meant to be used through the GUI. You 
can open the gui by running:

    python("slideAnimationKeys.ui()");

A single command is provided to set the value of the slider using the last 
mode previously used.  Slide Animation Keys should save the last mode used 
between Maya sections, so if you want to only use a single mode, you will 
only have to set it through the GUI once.

   python("slideAnimationKeys.hotkey( value = 30 )");

In this command you can replace 30 with any number you like.  Additionally, 
you can set an optional update parameter to False if you don't want this 
command to affect the GUI.  This is only relevant if you are using this 
command in conjunction with the GUI.

   python("slideAnimationKeys.hotkey( value = 30, update = False )");

By default, update is True.

---
**Blend Modes**

_A brief description of the blending modes in Slide Animation Keys._

- _Blend:_ Blend key values between the previous and next keys.
- _Average:_ Move key values towards the average of the previous and next keys.
- _Default:_ Move key values towards their defaults (zero for most attributes, 
one for scale).
- _Shrink:_ Move keys on each frame towards their vertical center.
- _Level:_ Move all keys towards their vertical center.

---
**Settings**

_A brief description of the settings in Slide Animation Keys._

- _Absolute Mode:_ Keys will move to an absolute percentage.
- _Relative Mode:_ Keys will move by a percentage relative to their last position.
- _Realtime Mode:_ Moving the slider will update the keys in real time.  Only 
avaliable in Absolute Mode.
- _Reset Default Value:_ The saved position is reset each time a value is applied. 
The effect is similar to Compound Percentages. This mode can overshoot keys, but 
it can not reset the keys back to their original positions.
- _Compound Percentages:_ Each key will move less each time a button is pressed. 
This cannot overshoot keys, but keys can still be reset to their original positions 
by applying 0.
- _Visibilities:_ Everything but the blend mode can be hidden through the 
settings.

### Zero Selection Usage ###
---
Zero Selection uses the selectedAttributes.py module and will therefore work on 
selected attributes in the same way as Clever Keys.  Zero Selection is meant to 
be run without a GUI and has a single command:

    python("zeroSelection.zeroSelection()");












