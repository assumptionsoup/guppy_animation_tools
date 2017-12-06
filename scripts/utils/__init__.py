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


# from https://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
class memoized(object):
    '''
    Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).
    '''
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args):
        if not isinstance(args, collections.Hashable):
            # uncacheable. a list, for instance.
            # better to not cache than blow up.
            return self.func(*args)
        if args in self.cache:
            return self.cache[args]
        else:
            value = self.func(*args)
            self.cache[args] = value
            return value

    def __repr__(self):
        '''Return the function's docstring.'''
        return self.func.__doc__

    def __get__(self, obj, objtype):
        '''Support instance methods.'''
        return functools.partial(self.__call__, obj)
