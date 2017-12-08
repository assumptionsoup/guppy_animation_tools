'''
*******************************************************************************
    License and Copyright
    Copyright 2012-2014 Jordan Hueckstaedt
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

*******************************************************************************
'''
import collections
import functools

import pymel.core as pm

import guppy_animation_tools.utils.ui
import guppy_animation_tools.utils.observer


__all__ = ['ui', 'decorator', 'observer']



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
    from guppy_animation_tools.utils.qt import QtWidgets
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


##  Context Managers ##
class UndoChunk(object):
    '''
    Context manager to group all following commands into a single undo
    "chunk".
    '''
    def __init__(self):
        self.isOpen = False

    def __enter__(self):
        try:
            pm.undoInfo(openChunk=1)
        except TypeError:
            # Legacy support for before undo chunking existed
            pm.undoInfo(stateWithoutFlush=0)  # turn undo off
        return self

    def __exit__(self, type, value, tb):
        try:
            pm.undoInfo(closeChunk=1)
        except TypeError:
            # Legacy support for before undo chunking existed
            # Turn undo back on
            pm.undoInfo(stateWithoutFlush=1)
            # This is needed for things to work for some reason
            pm.undoInfo(query=1, undoName=0)


class MaintainSelection(object):
    '''
    Context manager that maintains / restores selection once the context
    exits.
    '''
    def __enter__(self):
        self.selection = pm.ls(selection=1)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Avoid node.exists() due to bug in pymel fixed AFTER 1.0.10rc2
        # https://github.com/LumaPictures/pymel/commit/5c141874ade4fee5fb892507d47f2ed5dbddeb33
        selection = [node for node in self.selection if pm.objExists(node)]
        pm.select(selection)
