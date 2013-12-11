''' Uses the python API to circumvent the default maya behavior and lock and/or
hide attributes on referenced and non-referenced nodes.

Changes made to referenced nodes will not be saved with the scene.  For this
reason and because this could potentially lead to lost work, THIS COMMAND
SHOULD NOT BE CALLED DIRECTLY unless you are a developer.  THE LOCK_N_HIDE
SCRIPT DISTRIBUTED WITH THIS COMMAND SHOULD BE USED INSTEAD.

There are a number of obfuscations built into this command to help prevent
non-developer use.  You proceed at your own risk if you disable them or
circumvent them.  I believe in python's "treat everyone as a responsible adult"
policy.  I regret the need to put these obfuscations in, but felt it would be
better to be on the safe side, since this may be used in a production where
accidental misuse could cause lost work, time, and money.

-------------------------------------------------------------------------------
	License and Copyright
	Copyright 2012 Jordan Hueckstaedt
	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU Lesser General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU Lesser General Public License for more details.

	You should have received a copy of the GNU Lesser General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

-------------------------------------------------------------------------------
''''''
	Author:........Jordan Hueckstaedt
	Website:.......RubberGuppy.com
	Email:.........AssumptionSoup@gmail.com
	Work Status:...Looking for work!  If you have a job where I can write stuff
					like this or rig characters, hit me up!

-------------------------------------------------------------------------------
'''

__author__ = 'Jordan Hueckstaedt'
__copyright__ = 'Copyright 2012'
__license__ = 'LGPL v3'
__version__ = '0.1'
__email__ = 'AssumptionSoup@gmail.com'
__status__ = 'Alpha'

import maya.OpenMaya as om
import maya.OpenMayaMPx as omMPx

COMMAND_NAME = '_lock_n_hide'
I_KNOW_FLAG = '-I_know_what_Im_doing_and_wont_complain_if_I_fuck_shit_up'


class UndoData(object):
    # Class to store basic undo data.

    def __init__(self, plug, setKeyable, setLocked):
        self.plug = plug
        if setKeyable != -1:
            self.setKeyable = True
        else:
            self.setKeyable = False

        if setLocked != -1:
            self.setLocked = True
        else:
            self.setLocked = False

        # These will be set manually later
        self.keyState = None
        self.lockState = None


class LockHideAttribute(omMPx.MPxCommand):
    plugs = []
    undoData = []
    lock = -1
    hide = -1

    def __init__(self):
        omMPx.MPxCommand.__init__(self)

    @staticmethod
    def commandCreator():
        return omMPx.asMPxPtr(LockHideAttribute())

    @staticmethod
    def synatxCreator():
        syntax = om.MSyntax()

        syntax.addFlag('-a', '-attribute', om.MSyntax.kString)
        syntax.addFlag('-l', '-lock', om.MSyntax.kUnsigned)
        syntax.addFlag('-h', '-hide', om.MSyntax.kUnsigned)

        # Saftey procaution so users don't try anything stupid.  Read the full
        # documentation to the lock_n_hide script before proceeding.
        syntax.addFlag('', I_KNOW_FLAG, om.MSyntax.kNoArg)

        # Take an object on the end.  Needs at least one.
        syntax.setObjectType(om.MSyntax.kSelectionList, 1)

        # Place the selection into the command so the user doesn't have to
        # explicitly specify the objects
        syntax.useSelectionAsDefault(True)

        # No query or edits.
        syntax.enableEdit(False)
        syntax.enableQuery(False)

        return syntax

    def doIt(self, argList):
        # Read all the arg variables

        try:
            argData = om.MArgDatabase(self.syntax(), argList)
        except:
            return om.MStatus.kFailure

        # Saftey procaution so users don't try anything stupid.  Read the full
        # documentation to the lock_n_hide script before proceeding.
        if not argData.isFlagSet(I_KNOW_FLAG):
            raise KeyError('This command is not meant to be called directly.')

        if argData.isFlagSet('-attribute'):
            attribute = argData.flagArgumentString('-attribute', 0)
        else:
            raise KeyError('An attribute must be specified with the -attribute flag.')

        if argData.isFlagSet('-lock'):
            self.lock = argData.flagArgumentInt('-lock', 0)

        if argData.isFlagSet('-hide'):
            self.hide = argData.flagArgumentInt('-hide', 0)

        # Initialize selection from stored argData
        selection = om.MSelectionList()
        argData.getObjects(selection)

        # Reset saved plugs
        self.plugs = []

        # Find plugs
        for x in range(selection.length()):
            # Get depend node from selectionList
            depend = om.MObject()
            selection.getDependNode(x, depend)
            depend = om.MFnDependencyNode(depend)

            # Find plug.  Probably needs some wrapper around findPlug if it fails.
            try:
                plug = depend.findPlug(attribute, 0)
            except:
                raise AttributeError('%s is not an attribute on %s' % (attribute, depend.name()))
            self.plugs.append(plug)

        return self.redoIt()

    def redoIt(self):
        # Main functionality

        # Make 'em hidden.  Make 'em safe.
        self.undoData.append([])
        for plug in self.plugs:
            self.undoData[-1].append(UndoData(plug, self.hide, self.lock))
            # Hide 'em
            if self.hide != -1:
                self.undoData[-1][-1].keyState = plug.isKeyable()
                plug.setKeyable(not self.hide)

            # Lock 'em
            if self.lock != -1:
                self.undoData[-1][-1].lockState = plug.isLocked()
                plug.setLocked(self.lock)

    def undoIt(self):
        # Restore initial state
        for data in self.undoData.pop():
            if data.setKeyable:
                data.plug.setKeyable(data.keyState)
            if data.setLocked:
                data.plug.setLocked(data.lockState)

    def isUndoable(self):
        return True


def initializePlugin(mobject):
    mplugin = omMPx.MFnPlugin(mobject)  # , 'Jordan Hueckstaedt', '0.1', 'Any')


    try:
        mplugin.registerCommand(COMMAND_NAME, LockHideAttribute.commandCreator, LockHideAttribute.synatxCreator)
    except Exception as err:
        sys.stderr.write("%s\nError loading command %s\n" % (err, COMMAND_NAME))
        raise


def uninitializePlugin(mobject):
    mplugin = omMPx.MFnPlugin(mobject)

    try:
        mplugin.deregisterCommand(COMMAND_NAME)
    except:
        sys.stderr.write("Error removing command %s\n" % COMMAND_NAME)
        raise
