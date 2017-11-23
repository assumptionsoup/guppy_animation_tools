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

import pymel.core as pm
import guppy_animation_tools.utils.ui


__all__ = ['ui']

######### Uncategorized Functions ############
#########                         ############

class UndoChunk(object):
    '''
    Context manager to group all following commands into a single undo
    "chunk".
    '''
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
    def __init__(self):
        self.selection = []

    def __enter__(self):
        self.selection = pm.ls(selection=1)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Avoid node.exists() due to bug in pymel fixed AFTER 1.0.10rc2
        # https://github.com/LumaPictures/pymel/commit/5c141874ade4fee5fb892507d47f2ed5dbddeb33
        selection = [node for node in self.selection if pm.objExists(node)]
        pm.select(selection)
