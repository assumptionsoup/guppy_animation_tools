''' Allows python data to be pickled to an attribute on a node and read back
later.

*******************************************************************************
    License and Copyright
    Copyright 2010 Eric Pavey
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

    Author: Eric Pavey
    Modified by: Jordan Hueckstaedt
    Originally Posted on: http://http://www.akeric.com/blog/?p=1049
    Re-licensed to LGPL with permission.  Original snippet is under the Apache
    License v2.0

*******************************************************************************
'''
__license__ = 'LGPL v3'
__version__ = '0.3'

import cPickle
import maya.cmds as cmd
import maya.mel as mel
from selectedAttributes import splitAttr


def lockUnlockAttr(obj, attr, lockState, useLockHide):
    try:
        cmd.setAttr('%s.%s' % (obj, attr), edit=True, lock=lockState)
    except RuntimeError as err:
        if useLockHide:
            cmd._lock_n_hide(obj, attribute=attr, lock=lockState, I_know_what_Im_doing_and_wont_complain_if_I_fuck_shit_up=1)
        else:
            raise err


def toAttr(objAttr, data, useLockHide=False):
    '''
    Write (pickle) Python data to the given Maya obj.attr.  This data can
    later be read back (unpickled) via attrToPy().

    Arguments:
    objAttr : string : a valid object.attribute name in the scene.  If the
            object exists, but the attribute doesn't, the attribute will be added.
            The if the attribute already exists, it must be of type 'string', so
            the Python data can be written to it.
    data : some Python data :  Data that will be pickled to the attribute
    '''

    obj, attr = splitAttr(objAttr)
    # Add the attr if it doesn't exist:
    # if not cmd.objExists(objAttr): # Gives false positives on shape nodes, the same as getAttr
    if not mel.eval('attributeExists %s %s' % (attr, obj)):
        cmd.addAttr(obj, longName=attr, dataType='string')


    # Make sure it is the correct type before modifing:
    if cmd.getAttr(objAttr, type=True) != 'string':
        raise Exception("Object '%s' already has an attribute called '%s', but it isn't type 'string'" % (obj, attr))

    # Pickle the data and return the corresponding string value:
    stringData = cPickle.dumps(data)

    # Make sure attr is unlocked before edit:
    lockUnlockAttr(obj, attr, 0, useLockHide)

    # Set attr to string value:
    cmd.setAttr(objAttr, stringData, type='string')

    # And lock it for safety:
    lockUnlockAttr(obj, attr, 1, useLockHide)


def toPython(objAttr, lockAttr=False, useLockHide=False):
    '''
    Take previously stored (pickled) data on a Maya attribute (put there via
    pyToAttr() ) and read it back (unpickle) to valid Python values.

    Arguments:
    objAttr : string : A valid object.attribute name in the scene.  And of course,
            it must have already had valid Python data pickled to it.

    Return : some Python data :  The reconstituted, unpickled Python data.
    '''
    # Get the string representation of the pickled data.  Maya attrs return
    # unicode vals, and cPickle wants string, so we convert:
    stringAttrData = str(cmd.getAttr(objAttr))

    # Un-pickle the string data:
    loadedData = cPickle.loads(stringAttrData)

    if lockAttr:
        obj, attr = splitAttr(objAttr)
        lockUnlockAttr(obj, attr, 1, useLockHide)

    # And lock it for safety, even on read, because it will reset itself
    # during file opens.
    return loadedData
