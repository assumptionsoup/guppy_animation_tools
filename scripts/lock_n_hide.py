''' Allows the user to lock and/or hide attributes on referenced nodes using
the custom lock_n_hide command (a separate python module).


-------------------------------------------------------------------------------
Usage:

WARNING: The lock_n_hide command is NOT meant to be called by users.  It has
the python private _ underscore for that reason.  Unless you are a developer,
it is not safe to call this.

The user is meant to interact with the following methods:
resetAll
reset
lock
lockHide

Advanced users may also use:
startScriptJob
stopScriptJob
emergencyReset
emergencyResetAll

The GUI is opened from the ui() method.

All other methods are meant for internal/developer use only.

-------------------------------------------------------------------------------
Details:

The lock_n_hide command allows a user to change the locked and hidden
state of an attribute in a referenced file.  However, Maya does not save/load
those changes.  This is why it is unsafe for users to call directly.  It is
very easy to lose data directly calling this command.  In addition, unlocking
locked attributes on a referenced rig could cause havoc to a pipeline.  That
is why this script exists.  While this script could have been incorporated
into the command, it was easiest to separate the two.  (Using OpenMaya is
annoying).

-------------------------------------------------------------------------------
Further Details:
The primary method of this module is lockHideAttribute.

A PICKLED_ATTRIBUTE is stored on every node with a modified attribute state.
This attribute stores an AttributeStates object, which is basically a
dictionary of AttributeState objects.  These store the current state of the
attribute,  which states were set, and what the initial state of the attribute
was.  On  import, this module calls startScriptJob creates a scriptJob that
monitors scene loads.  When a scene is loaded, it calls
restoreAllAttributeStates.  That method finds all objects with a
PICKLED_ATTRIBUTE, saves over the current state of all
saved attributes as the initial state (validateStates parameter), and finally
re-applies all valid states.

The method lockHideAttribute()'s duty is to run the lock_n_hide command
for the given attribute as well as run saveAttributeState.

The method saveAttributeState()'s duty is to save the current state to the
PICKLED_ATTRIBUTE.  It is responsible for creating PICKLED_ATTRIBUTE, keeping
the data saved in it up to date and relevant, as well as deleting the
PICKLED_ATTRIBUTE if it is no longer needed.  saveAttributeState must be called
before the lockHideAttribute command is called in order to properly save
the initial state of an attribute.

-------------------------------------------------------------------------------
    License and Copyright
    Copyright 2012-2017 Jordan Hueckstaedt
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

-------------------------------------------------------------------------------
'''

# Meta.
__version__ = '0.45'


import maya.OpenMaya as om
import maya.cmds as cmd
import maya.mel as mel
from textwrap import dedent

from guppy_animation_tools import getLogger, internal, selectedAttributes
import guppy_animation_tools.pickleAttr as pickle
from guppy_animation_tools.internal.qt import QtCore, QtGui, QtWidgets


# Constants
PICKLED_ATTRIBUTE = 'lockHideReferenceDict'
_log = getLogger(__name__)


def loadPlugin():
    ''' Tries to load the lockHidAttribute Command plugin.  Returns True if
    successfull. '''
    if not cmd.pluginInfo('lock_n_hide', query=1, l=1):
        try:
            cmd.loadPlugin('lock_n_hide.py')
        except RuntimeError:
            om.MGlobal.displayError("lock_n_hide plugin not found.  Please install it for lock_n_hide to function correctly.")
            return False
    return True


class AttributeState(object):

    ''' Store data on attribute state and perform basic operations about that
    data. Will not store attribute or node it is attached to, because that
    information may change due to referencing renaminng, etc.'''

    def __init__(self, attribute, lock, hide):
        self.initialLockState = cmd.getAttr(attribute, lock=1)
        self.initialHideState = not cmd.getAttr(attribute, keyable=1)
        self.lock = lock
        self.hide = hide
        self.version = __version__

    def lockIsActive(self):
        # Was the lock ever set, or back to it's original state?
        return self.lock != -1 and self.lock != self.initialLockState

    def hideIsActive(self):
        # Was the attribute ever hidden, or is it back to its original state?
        return self.hide != -1 and self.hide != self.initialHideState

    def isActive(self):
        # Is the attribute currently back to its original state?
        return self.hideIsActive() or self.lockIsActive()

    def copyState(self, otherState):
        # Copy new state, but keep original initial states stored.
        self.lock = otherState.lock
        self.hide = otherState.hide

    def validLockState(self, attribute):
        return self.initialLockState == cmd.getAttr(attribute, lock=1)

    def validHideState(self, attribute):
        return self.initialHideState != cmd.getAttr(attribute, keyable=1)

    def validState(self, attribute):
        return self.validLockState(attribute) and self.validHideState(attribute)

    def validateState(self, attribute):
        if not self.validState(attribute):
            pass

        if not self.validLockState(attribute):
            self.initialLockState = cmd.getAttr(attribute, lock=1)
            if self.initialLockState == 1 and self.lock == 0:
                self.lock = 1

        if not self.validHideState(attribute):
            self.initialHideState = not cmd.getAttr(attribute, keyable=1)
            if self.initialHideState == 1 and self.hide == 0:
                self.hide = 0


class AttributeStates(object):

    '''A dictionary-like class which stores the states of multiple attributes.
    Keys to this class should be attribute names, and objects stored must be
    AttributeState objects.

    The primary purpose of this class is to copy new states to existing keys
    without overriding their initial states.'''

    def __init__(self):
        self.states = {}
        self.version = __version__

    def __getitem__(self, key):
        ''' Get the item if it exists '''
        if key in self.states.keys():
            return self.states[key]
        else:
            raise KeyError(key)

    def __setitem__(self, key, otherState):
        '''Set the item if it is an AttributeState.  Will not overwrite
        initial states.'''
        if not isinstance(otherState, AttributeState):
            raise TypeError('AttributeStates can only be set to objects of \
                type AttributeState.  Got %s instead' % type(otherState))

        if key in self.states.keys():
            self.states[key].copyState(otherState)
        else:
            self.states[key] = otherState

    def keys(self):
        return self.states.keys()

    def pop(self, item=-1):
        return self.states.pop(item)

    def removeInactive(self):
        for attribute in self.states.keys():
            if not self.states[attribute].isActive():
                self.states.pop(attribute)


def hasAttributeState(node):
    # Returns if a given node has a PICKLED_ATTRIBUTE
    try:
        # See if attribute exists
        return mel.eval('attributeExists %s %s' % (PICKLED_ATTRIBUTE, node))
        # getAttr is inexact and will return true if attribute is
        # actually on shapeNode instead.
        # cmd.getAttr('%s.%s' % (node, PICKLED_ATTRIBUTE))
    except RuntimeError:
        return False


def getAttributeStates(node):
    ''' If the given node has a PICKLED_ATTRIBUTE, return a de-pickled
    AttributeStates object from PICKLED_ATTRIBUTE.  Otherwise, return a new
    AttributeStates object.'''

    if hasAttributeState(node):
        # Retrieve states
        try:
            return pickle.toPython('%s.%s' % (node, PICKLED_ATTRIBUTE), lockAttr=1, useLockHide=1)
        except Exception:
            pass
    return AttributeStates()


def callLockHideCommand(node, attribute, lock=-1, hide=-1):
    '''A simple wrapper for the lock_n_hide command.

    Want to call this on your own?  READ THE ENTIRE DOCUMENTATION.

    This method is useful because lock_n_hide has some obfuscation to help
    prevent users from accidentally calling it (or developers who haven't read
    the documentation)'''

    kwargs = {'attribute': attribute, 'I_know_what_Im_doing_and_wont_complain_if_I_fuck_shit_up': 1}
    if lock != -1:
        kwargs['lock'] = lock
    if hide != -1:
        kwargs['hide'] = hide
    cmd._lock_n_hide(node, **kwargs)


def deletePickledAttribute(node):
    ''' Tries to delete a PICKLED_ATTRIBUTE on the given node.  Returns true if
    it succeeds.'''
    try:
        callLockHideCommand(node, PICKLED_ATTRIBUTE, lock=0)
        cmd.deleteAttr(node, attribute=PICKLED_ATTRIBUTE)
        return True
    except Exception as err:
        return False


def saveAttributeState(node, attribute, lock, hide):
    ''' Save an AttributeStates object to the given node on a PICKLED_ATTRIBUTE
    attribute.  Deletes that attribute if the AttributeStates object is not
    storing any changed states.'''
    attributeStates = getAttributeStates(node)
    attributeStates[attribute] = AttributeState('%s.%s' % (node, attribute), lock, hide)

    # Prune attribute from dict if it's being unset
    attributeStates.removeInactive()

    if not attributeStates.keys():
        # Remove attribute and exit function if it is no longer storing any states
        deletePickledAttribute(node)

    else:
        # Otherwise, store its state.
        pickle.toAttr('%s.%s' % (node, PICKLED_ATTRIBUTE), attributeStates, useLockHide=True)


def lockHideAttribute(fullAttribute, lock=-1, hide=-1, override=False):
    ''' Can lock, hide or unlock and unhide referenced attributes using the
    custom lockHideAttribute command.  Assumes that all attributes are on
    a referenced object.

    Has a saftey feature in place to not unlock or unhide any previously locked
    or hidden attribute.  The override parameter will override this, however
    the restoreAllAttributeStates method will erase any state saved this way on
    file-load.  Therefore THE OVERRIDE METHOD IS ONLY AVALIABLE TO DEVELOPERS.

    Pass lock or hide 1 or 0 to set an attribute as locked or hidden.  Pass -1
    to not affect the current state.

    resetAttributeState and resetNodeState should be used to restore prior
    states.

    Attributes set back to their original values will be cleaned automatically.
    '''
    node, attribute = selectedAttributes.splitAttr(fullAttribute)

    # Saftey check to stop unhiding or unlocking locked referenced attributes
    # to help maintain asset integrity.
    if not override:
        attributeStates = getAttributeStates(node)
        if attribute in attributeStates.keys():
            if lock == 0 and attributeStates[attribute].initialLockState == 1:
                om.MGlobal.displayWarning((
                    "Lock 'n Hide: Skipping %s because it was initially "
                    "locked.  Use the override flag if you still want to "
                    "unlock this attribute.") % fullAttribute)
                return
            if hide == 0 and attributeStates[attribute].initialHideState == 1:
                om.MGlobal.displayWarning((
                    "Lock 'n Hide: Skipping %s because it was initially "
                    "hidden.  Use the override flag if you still want to "
                    "unhide this attribute.") % fullAttribute)
                return

    # Apply command
    saveAttributeState(node, attribute, lock, hide)
    callLockHideCommand(node, attribute, lock, hide)


def restoreAllAttributeStates(validateStates=True):
    ''' Restores all saved attribute states on all nodes with a
    PICKLED_ATTRIBUTE.

    When validateStates is true, this function will store the current state of
    every saved attribute as it's initial state.  Therefore it is VERY
    IMPORTANT that this function IS NOT RUN TWICE in a row with validateStates
    as true.  If it is, the modified states will be set as the initial states,
    invalidating the internal state machine which does not have any sort of
    check against this thing.  That is to say, running this method twice may
    seriously fuck up your work.

    It is important to run this command once (and only once) after a new scene
    load because referenced animation files will not save new locked or hidden
    states set from the custom lockHideAttribute command.'''
    for node in cmd.ls():
        attributeStates = getAttributeStates(node)
        if attributeStates.keys():
            # Force state validation
            if validateStates:
                for attribute in attributeStates.keys():
                    attributeStates[attribute].validateState('%s.%s' % (node, attribute))

            # Prune attribute from dict if it's being unset
            attributeStates.removeInactive()

            if not attributeStates.keys():
                # Remove attribute and exit function if it is no longer storing any states
                result = deletePickledAttribute(node)
            else:
                # Otherwise, store its state.
                pickle.toAttr('%s.%s' % (node, PICKLED_ATTRIBUTE), attributeStates, useLockHide=True)

                # Apply states
                for attribute in attributeStates.keys():
                    callLockHideCommand(node, attribute, attributeStates[attribute].lock, attributeStates[attribute].hide)


def resetAttributeState(attribute, lock=True, hide=True):
    ''' Resets the lock/hidden state on the given attribute. Cleanup is handled
    in saveAttributeState.'''

    node, attribute = selectedAttributes.splitAttr(attribute)
    attributeStates = getAttributeStates(node)

    if attribute in attributeStates.keys():
        kwargs = {'lock': -1, 'hide': -1}
        if lock:
            kwargs['lock'] = attributeStates[attribute].initialLockState
        if hide:
            kwargs['hide'] = attributeStates[attribute].initialHideState
        lockHideAttribute('%s.%s' % (node, attribute), **kwargs)


def resetNodeState(node, lock=True, hide=True):
    ''' Resets the lock/hidden state for all attributes on the given node.
    Cleanup is handled in saveAttributeState.'''
    attributeStates = getAttributeStates(node)

    for attribute in attributeStates.keys():
        kwargs = {'lock': -1, 'hide': -1}
        if lock:
            kwargs['lock'] = attributeStates[attribute].initialLockState
        if hide:
            kwargs['hide'] = attributeStates[attribute].initialHideState
        lockHideAttribute('%s.%s' % (node, attribute), **kwargs)


def lockHideSelected(lock=True, hide=True):
    ''' Locks and/or hides the attributes selected in the channelBox. '''
    if not lock:
        lock = -1
    if not hide:
        hide = -1

    selAttrs = selectedAttributes.getChannelBox(animatableOnly=0)
    for attr in selAttrs:
        lockHideAttribute(attr, lock=lock, hide=hide)


def getScriptJob():
    '''Gets the running scriptJob number from the global mel variable
    $gLock_N_HideScriptJob Initializes variable to -1 if it doesn't exist'''
    # It's best to use a mel global variable instead of a python one
    # tied to this module instance since python can create multiple
    # instances.
    if mel.eval('catchQuiet(eval("$gLock_N_HideScriptJob = $gLock_N_HideScriptJob"))'):
        return mel.eval('int $gLock_N_HideScriptJob = -1')
    else:
        return mel.eval('$gLock_N_HideScriptJob = $gLock_N_HideScriptJob')


def setScriptJob(number):
    # Set given integer to the global mel variable $gLock_N_HideScriptJob
    mel.eval('$gLock_N_HideScriptJob = %d' % number)

'''############################################################################
                                User Functions
############################################################################'''


def emergencyReset(nodes=None):
    ''' Does an emergency reset of the given nodes.  If no nodes are given, the
    current selection is used.  An emergency reset first checks for a
    PICKLED_ATTRIBUTE, and then tries to delete it without first restoring
    attribute states.  The scene must then be saved and reloaded to achieve the
    correct state.

    This is intended to be an emergency measure only for when the regular reset
    method does not work. '''

    warnings = 0
    if nodes is None:
        nodes = cmd.ls(sl=1)
    for node in nodes:
        if hasAttributeState(node):
            if not deletePickledAttribute(node):
                om.MGlobal.displayWarning("Lock 'n Hide: %s could not be reset.")
                warnings += 1
    if not warnings:
        om.MGlobal.displayInfo("Lock 'n Hide: Emergency reset completed without errors.  Please save and restart your scene to finish the operation.")
    else:
        om.MGlobal.displayWarning("Lock 'n Hide: Emergency reset completed with %d warnings.  Please save and restart your scene if you wish to finish the operation." % warnings)


def emergencyResetAll():
    ''' Does an emergency reset of all nodes in the scene.  See emergencyReset
    for more details '''

    emergencyReset(cmd.ls())


def resetAll(lock=True, hide=True):
    ''' Removes and restores the original attribute state of given type for
    all nodes in the scene. '''
    errorsOccurred = 0
    for obj in cmd.ls():
        try:
            resetNodeState(obj, lock, hide)
        except RuntimeError as e:
            errorsOccurred += 1
            print e
    if errorsOccurred:
        raise RuntimeError('%d errors occurred while running resetAll.  \
Some nodes may not have been correctly reset. See above for details.' % errorsOccurred)


def reset():
    ''' Removes and restores the original attribute state of the selected
    channelbox attributes.  If no attributes are selected, it operates on the
    entire object '''
    selAttrs = selectedAttributes.getChannelBox(animatableOnly=0)
    for attr in selAttrs:
        resetAttributeState(attr, 1, 1)

    selAttrs = selectedAttributes.getChannelBox(selectedOnly=1)
    if not selAttrs:
        for object in cmd.ls(sl=1):
            if object not in selAttrs:
                resetNodeState(object, 1, 1)


def lock():
    ''' Convenience function for animators to set to a hotkey. '''
    lockHideSelected(lock=1, hide=0)


def lockHide():
    ''' Convenience function for animators to set to a hotkey. '''
    lockHideSelected(lock=1, hide=1)


def startScriptJob():
    ''' Starts a PostSceneRead scriptJob for the restoreAllAttributeStates
    method. Tries to stop a previously saved scriptJob before starting a new
    one.

    It is VERY important that restoreAllAttributeStates is only run once during
    scene load (and therefore very important that there only be one scriptJob
    calling it.'''

    stopScriptJob()
    scriptJob = cmd.scriptJob(e=["PostSceneRead", restoreAllAttributeStates])
    setScriptJob(scriptJob)


def stopScriptJob():
    ''' Stops a saved scriptJob if one exists.

    Returns True if it existed and was stopped, returns False otherwise.'''
    scriptJob = getScriptJob()
    if cmd.scriptJob(ex=scriptJob):
        cmd.scriptJob(kill=scriptJob)
        return True
    return False

'''############################################################################
                                UI
############################################################################'''


class CopyActionButton(internal.ui.BubblingMenuFactory(QtWidgets.QPushButton)):
    def __init__(self, actionText, buttonText, parent=None):
        self._actionText = actionText
        super(CopyActionButton, self).__init__(buttonText, parent=parent)

    def rightClickMenu(self, menu=None):
        if menu is None:
            menu = QtWidgets.QMenu()
        copyAction = menu.addAction("Copy action to clipboard")
        action = super(CopyActionButton, self).rightClickMenu(menu=menu)
        if action == copyAction:
            internal.copyFunctionToClipboard(
                __name__, self._actionText)
            _log.info("Copied action to clipboard! Paste it into the python "
                      "script editor or python hotkey.")
        return action


class LockNHideWidget(internal.ui.BubblingMenuFactory(internal.ui.PersistentWidget)):
    def __init__(self, parent=None):
        super(LockNHideWidget, self).__init__(parent=parent)
        self._buildLayout()
        self._connectSignals()

    def _buildLayout(self):
        self.setWindowTitle("Lock 'n Hide")
        self.setLayout(QtWidgets.QVBoxLayout())
        self.row1Layout = QtWidgets.QHBoxLayout()
        self.row2Layout = QtWidgets.QHBoxLayout()
        self.layout().addLayout(self.row1Layout)
        self.layout().addLayout(self.row2Layout)

        self.lockButton = CopyActionButton(
            "lockHideSelected(lock=True, hide=False)", "Lock")
        self.lockHideButton = CopyActionButton(
            "lockHideSelected(lock=True, hide=True)", "Lock 'n Hide")
        self.resetButton = CopyActionButton(
            "reset()", "Reset Selected")

        self.row1Layout.addWidget(self.lockButton)
        self.row1Layout.addWidget(self.lockHideButton)
        self.row2Layout.addWidget(self.resetButton)

    def _connectSignals(self):
        self.lockButton.clicked.connect(lambda: lockHideSelected(lock=True, hide=False))
        self.lockHideButton.clicked.connect(lambda: lockHideSelected(lock=True, hide=True))
        self.resetButton.clicked.connect(reset)

    def rightClickMenu(self, menu=None):
        if menu is None:
            menu = QtWidgets.QMenu()
        else:
            menu.addSeparator()

        resetAction = menu.addAction("Reset All Channels")
        action = super(LockNHideWidget, self).rightClickMenu(menu=menu)
        if action == resetAction:
            resetAll()
        return action


def ui(refresh=False):
    '''Ui launcher'''
    internal.ui.showWidget('lock_n_hide_widget', LockNHideWidget, refresh=refresh)


# Loads plugin and creates scriptjob on import
if __name__ != '__main__':
    loadPlugin()
    startScriptJob()
else:
    ui(refresh=True)
