'''
Move My Objects provides a way to quickly save and restore objects' world
space position.

The UI of Move My Objects allows an animator to save the position of multiple
nodes and later apply those positions to the same nodes, or new ones.

*******************************************************************************
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

''''''*************************************************************************

    Author:........Jordan Hueckstaedt
    Website:.......RubberGuppy.com
    Email:.........AssumptionSoup@gmail.com

****************************************************************************'''

from functools import partial

import pymel.core as pm
import guppy_animation_tools as gat
from guppy_animation_tools import utils
from guppy_animation_tools.utils.qt import QtCore, QtGui, QtWidgets

try:
    import shiboken
except ImportError:
    import shiboken2 as shiboken

try:
    _globalQtObjects
except NameError:
    _globalQtObjects = {}

_log = gat.getLogger(__name__)


def duplicateGroup(obj, name):
    # Duplicate object transform
    dupObj = pm.duplicate(obj, po=1, rr=1, n=name)[0]

    # unlock default channels
    attrs = 't r s tx ty tz rx ry rz sx sy sz v'.split()
    for attr in attrs:
        dupObj.setAttr(attr, lock=0, keyable=1)
    return dupObj


def getNodePositions(nodes):
    '''
    Returns a list of world matrices of the given nodes.


    Returned matrices are always scaled to (1, 1, 1). Return type is
    [pm.dt.Matrix, ..]
    '''

    # It would be really REALLY easy to query world matrices directly
    # from Maya, but we'll be EXTRA careful, and do a bunch of extra
    # work to use parent constraints first, because in my experience
    # this works more reliably in rare edge cases.
    positions = []

    # Stop undo, so this doesn't get annoying for artist
    with utils.UndoChunk(), utils.MaintainSelection():

        # Create tempgroup and parent constrain it to object to get position
        # Maya likes this approach better
        tempGroup = pm.group(n='mmo_savePos_tmpGrp', em=1)

        # If passed a string instead of a list
        if isinstance(nodes, basestring):
            nodes = [nodes]

        # Get position with parent constraints
        for node in nodes:
            if not isinstance(node, pm.PyNode):
                node = pm.PyNode(node)
            tempConst = pm.parentConstraint(node, tempGroup)
            pm.refresh()
            positions.append(tempGroup.getMatrix(worldSpace=1))
            pm.delete(tempConst)

        # Delete temp group
        pm.delete(tempGroup)

    return positions


def applyNodePositions(matrices, nodes):
    '''
    Applies the the given matrices to the given nodes in world space.

    Has some smarts for applying differing number of matrices to nodes.
    Ex:
        1 matrix, many nodes: All nodes are set to this matrix
        3 matrices, 2 nodes: First two matrices are applied.
        2 matrices, 3 nodes: IndexError is raised due to ambiguous case.
        3 matrices, 3 nodes: All three positions are applied.
    '''

    # Stop undo, so this doesn't get annoying for artist
    with utils.UndoChunk(), utils.MaintainSelection():

        # create temporary group outside of loop
        positionGroup = pm.group(n='mmo_applyPos_tmpGrp', em=1)

        # If passed a string instead of a list
        if isinstance(nodes, basestring):
            nodes = [nodes]

        # Make number of matrices match nodes
        if len(matrices) != len(nodes):

            # Much like GoodParenting, we allow 1 position to be applied to
            # multiple nodes. We also allow a partial application of matrices,
            # when there are more matrices passed than nodes.
            # The only case we can't handle, is when there are otherwise less
            # matrices than nodes.  It's ambiguous what to do if 2 matrices
            # were to be applied to 3 nodes.
            if len(matrices) == 1:
                matrices = matrices * len(nodes) # Copy list
            elif len(nodes) > len(matrices):
                raise IndexError('More nodes (%d) than saved matrices (%d)!' %
                    (len(nodes), len(matrices)))

        for matrix, node in zip(matrices, nodes):
            if not isinstance(node, pm.PyNode):
                node = pm.PyNode(node)
            # Don't constraint directly to selected, since it could be
            # something special or have stuff locked.  Create a duplicate of
            # selected group, and constrain that
            positionGroup.setMatrix(matrix, worldSpace=True)
            dummyGroup = duplicateGroup(node, 'mmo_applyPosDummy_tmpGrp')
            tempConst = pm.parentConstraint(positionGroup, dummyGroup)
            pm.refresh()

            # Copy attributes from the dummy group onto the real one.
            for attr in 'tx ty tz rx ry rz sx sy sz'.split():
                value = dummyGroup.getAttr(attr)
                try:
                    node.setAttr(attr, value)
                except RuntimeError:
                    _log.warning('Could not set value for %s.%s, skipping...',
                        node, attr)

            pm.delete(tempConst)
            pm.delete(dummyGroup)
        pm.delete(positionGroup)


class MoveMyObjects(object):
    '''
    Primary interface for move my objects.

    Has the ability to save node positions, and to apply them later to
    selected nodes.  Provides extra callback features to provide a layer
    of abstraction between Maya and the UI for moveMyObjects.
    '''

    def __init__(self):
        self.positions = []
        # Monitor number of selected objects and provide callbacks for
        # MoveMyObjectsWidget, to help keep Maya interaction logic outside
        # of the UI class
        self.numSelected = 0
        self._callbacks = {}
        self._cbid = None

    def addCallback(self, cbName, cb):
        '''
        Add a callback function for a number of actions.

        Valid actions are:
            savePosition - updated when positions are saved
            applyPosition - updated when positions are applied
            selectionChanged - updated whenever a node selection changes

        All callbacks are parameterless.  Ex:

        >>> def shout():
        ...     print 'Positions Saved!!'
        ...
        ... import pymel.core as pm
        ... pm.group()
        ... mmo = MoveMyObjects()
        ... mmo.addCallback('savePosition', shout)
        ... mmo.savePositions()
        Positions Saved!!
        '''
        validFunctions = ('savePosition', 'applyPosition', 'selectionChanged')
        if cbName not in validFunctions:
            raise ValueError(
                "Invalid callback registration, function must be in:\n %s",
                validFunctions)
        callbacks = self._callbacks.setdefault(cbName, [])
        _log.debug("Adding callback %s to callback list %s", cbName, callbacks)
        callbacks.append(cb)

        if cbName == 'selectionChanged':
            self._monitorSelection()

    def removeCallback(self, cbName, cb):
        '''
        Removes a registered callback.

        Raises a ValueError if given callback is no longer registered.
        '''
        callbacks = self._callbacks.get(cbName, [])
        _log.debug("Removing callback %s from callback list: %s", cb, callbacks)
        try:
            callbacks.remove(cb)
        except ValueError:
            raise ValueError("Callback is not registered")
        if cbName == 'selectionChanged' and len(callbacks) == 0:
            self._stopMonitoringSelection()

    def _callCallbacks(self, cbName):
        for cb in self._callbacks.get(cbName, []):
            _log.debug("Calling callback, %s for %s channel", cb, cbName)
            cb()

    def _updateSelection(self):
        self.numSelected = len(pm.selected())
        self._callCallbacks('selectionChanged')

    def _monitorSelection(self):
        if self._cbid is not None:
            return

            _log.debug("Monitoring Maya's selection")
        self._cbid = pm.api.MModelMessage.addCallback(
            pm.api.MModelMessage.kActiveListModified,
            lambda *arg: self._updateSelection())
        # Set initial state
        self._updateSelection()

    def _stopMonitoringSelection(self):
        if self._cbid:
            _log.debug("No longer monitoring Maya's selection")
            pm.api.MMessage.removeCallback(self._cbid)
            self._cbid = None

    def savePositions(self):
        # Save the position of the selected objects
        sel = pm.ls(sl=1)
        if sel:
            self.positions = getNodePositions(sel)
            # I like letting the user know something happened
            _log.info('Position saved')
            self._callCallbacks('savePosition')
        else:
            _log.warning('You have to select something first!')

    def applyPositions(self, *args):
        sel = pm.ls(sl=1)

        if self.positions:
            _log.debug("Applying positions: %r", self.positions)
            if sel:
                applyNodePositions(self.positions, sel)
                _log.info('Position applied')
                self._callCallbacks('applyPosition')
            else:
                _log.warning('You have to select something first!')
        else:
            _log.warning('You have to save a position first!')

    def savePosition(self):
        # Function signature has changed to reflect its new ability to
        # operate on multiple nodes
        _log.warning("savePosition is deprecated, please switch to calls to savePositions")
        self.savePositions()

    def applyPosition(self):
        # Function signature has changed to reflect its new ability to
        # operate on multiple nodes
        _log.warning("applyPosition is deprecated, please switch to calls to applyPositions")
        self.applyPositions()


def copyFunctionToClipboard(moduleName, functionName):
    '''
    Returns the full text required to import the given fully qualified module
    and run the given function.  Useful to aid users in scripting / setting
    hotkeys for actions they perform frequently.

    Ex:
        >>> copyFunctionToClipboard('guppy_animation_tools.moveMyObjects', 'savePosition()')
        from guppy_animation_tools import moveMyObjects
        moveMyObjects.savePosition()
    '''
    clipboard = QtWidgets.QApplication.clipboard()
    modules = moduleName.rsplit('.', 1)

    if len(modules) == 1:
        importText = 'import %s' % moduleName
        module = moduleName
    else:
        importText = 'from {0} import {1}'.format(*modules)
        module = modules[-1]

    clipboard.setText((
        '{importText}\n'
        '{module}.{function}').format(
        importText=importText, module=module, function=functionName))


# Create global state/controller object so that positions are remembered
# between calls. This seems like weird design, but remember, many
# animators like saving commands to hotkeys, the simpler the final call
# to a function, the better it is for them.
try:
    _globalController
except NameError:
    _globalController = MoveMyObjects()


class RightClickButton(QtWidgets.QPushButton):
    rightClicked = QtCore.Signal()

    def mousePressEvent(self, event):
        super(RightClickButton, self).mousePressEvent(event)
        if event.button() == QtCore.Qt.RightButton:
            self.rightClicked.emit()


class MoveMyObjectsWidget(QtWidgets.QWidget):
    controller = _globalController

    def __init__(self, parent=None):
        super(MoveMyObjectsWidget, self).__init__(parent=parent)
        self._buildLayout()
        self._connectSlots()

        # Set delete on close, so that destroyed() is called and our
        # callbacks are cleaned up.  I would have preferred to use
        # weakref to maintain our callbacks to avoid all these
        # shenanigans, but weakref's don't seem to be working for my
        # QWidget - they get dereferenced immediately after the function
        # returns.
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)
        self.update()

    def update(self):
        # Update ui to reflect controller state
        numPositions = len(self.controller.positions)
        numSelected = self.controller.numSelected

        self.applyPositionsButton.setEnabled(numPositions > 0 and
            (numSelected <= numPositions or numPositions == 1) and
            numSelected > 0)
        self.savePositionsButton.setEnabled(numSelected > 0)

        applyText = ''
        saveText = ''
        if numPositions > 1:
            if numPositions == numSelected:
                applyText = "Apply %d Positions" % numPositions
            elif numPositions < numSelected:
                # Try to clarify ambiguous case to user.
                applyText = "Apply %d positions to %d nodes" % (numPositions, numSelected)
            else:
                applyText = "Apply %d of %d Positions" % (numSelected, numPositions)
        else:
            # One position case
            if numSelected > 1:
                applyText = "Apply position to %d nodes" % numSelected
            else:
                applyText = "Apply Position"

        if numSelected > 1 or numSelected == 0:
            saveText = "Save %d Positions" % numSelected
        else:
            saveText = "Save Position"

        self.applyPositionsButton.setText(applyText)
        self.savePositionsButton.setText(saveText)

    def _buildLayout(self):
        self.setWindowTitle("Move My Objects")
        self.savePositionsButton = RightClickButton("Save Positions")
        self.applyPositionsButton = RightClickButton("Apply Positions")
        self.setLayout(QtWidgets.QHBoxLayout())
        self.setMinimumWidth(150)
        self.layout().addWidget(self.savePositionsButton)
        self.layout().addWidget(self.applyPositionsButton)

        self.adjustSize()
        self.resize(300, self.height())
        self.move(QtWidgets.QApplication.desktop().screen().rect().center()
            - self.rect().center())

    def _connectSlots(self):
        self.savePositionsButton.clicked.connect(self.controller.savePositions)
        self.applyPositionsButton.clicked.connect(self.controller.applyPositions)
        self.applyPositionsButton.rightClicked.connect(
            partial(self.buttonMenu, 'applyPosition()'))
        self.savePositionsButton.rightClicked.connect(
            partial(self.buttonMenu, 'savePosition()'))

        self.controller.addCallback('savePosition', self.update)
        self.controller.addCallback('selectionChanged', self.update)

        def cleanup():
            self.controller.removeCallback('savePosition', self.update)
            self.controller.removeCallback('selectionChanged', self.update)

        self.destroyed.connect(cleanup)

    def buttonMenu(self, functionName):
        menu = QtWidgets.QMenu()
        copyAction = menu.addAction("Copy action to clipboard")
        clickedAction = menu.exec_(QtGui.QCursor.pos())
        if clickedAction == copyAction:
            copyFunctionToClipboard(__name__, functionName)
            _log.info("Copied action to clipboard! Paste it into the python "
                "script editor or python hotkey.")


def ui(refresh=False):
    '''Ui launcher'''
    global _globalQtObjects
    if refresh:
        # Close and remove widget, so we can test a new one.
        try:
            mmw = _globalQtObjects.pop('move_objects_widget')
        except KeyError, RuntimeError:
            pass
        else:
            # Our widget gets deleted on close, watch out!
            if shiboken.isValid(mmw):
                mmw.close()

    # Prevent GC
    mmw = _globalQtObjects.get('move_objects_widget')
    if mmw is None or not shiboken.isValid(mmw):
        mmw = _globalQtObjects['move_objects_widget'] = MoveMyObjectsWidget()
    mmw.show()
    mmw.raise_()


def savePositions():
    '''Wrapper to simplify usage for basic users for
    MoveMyObjects().savePosition'''
    _globalController.savePositions()


def applyPositions():
    '''Wrapper to simplify usage for basic users for
    MoveMyObjects().applyPosition'''
    _globalController.applyPositions()

# Legacy, I won't deprecate these since they are so prevalent in hotkeys.
savePosition = savePositions
applyPosition = applyPositions

if __name__ == '__main__':
    ui(refresh=True)
