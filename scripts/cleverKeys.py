'''cleverKeys is meant to improve setting keys intuitively in Maya.

If the mouse is over the graph editor, and a curve is selected, it keys the
attribute of the curve, otherwise, it keys the attributes selected there.  	If
the mouse is not over the graph editor, it keys the attributes selected in the
channel box.  If the channelBox is closed it will key all the attributes on the
selected node.  It attempts to use the "Insert Key" function which makes keys
match the curvature of the surrounding keys whenever possible.  To use this
module, call setKey()

*******************************************************************************
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

*******************************************************************************
''''''
	Author:........Jordan Hueckstaedt
	Website:.......RubberGuppy.com
	Email:.........AssumptionSoup@gmail.com
	Work Status:...Looking for work!  If you have a job where I can write tools
				   like this or rig characters, hit me up!

*******************************************************************************
'''

__author__ = 'Jordan Hueckstaedt'
__copyright__ = 'Copyright 2012'
__license__ = 'LGPL v3'
__version__ = '1.08'
__email__ = 'AssumptionSoup@gmail.com'
__status__ = 'Production'
__date__ = '6-24-2012'

import maya.cmds as cmd
import maya.mel as mel
import maya.OpenMaya as om
import collections
import selectedAttributes


def toggleDebug():
    selectedAttributes.toggleDebug()

# The real methods


def setKey(insert=True, useSelectedCurves=True):
    '''Sets clever keys.  Hohoho.

    If the mouse is over the graph editor, it keys the attributes selected there.  	Otherwise it keys the
    attributes selected in the channel box.  If the channelBox is closed it will key all the attributes
    on the selected node.  It attempts to use the "Insert Key" function which makes keys match the
    curvature of the surrounding keys whenever possible.  Set insert parameter to false to disable
    this behavior.'''

    # Get Attributes
    attributes = selectedAttributes.get(detectionType='cursor', useSelectedCurves=useSelectedCurves)
    selectedCurvesWereUsed = selectedAttributes.wereSelectedCurvesUsed(detectionType='cursor')
    currentFrame = cmd.currentTime(q=1)

    # Make extra sure attributes are unique (they should already be)
    attributes = list(set(attributes))

    if cmd.optionVar(ex='animBlendingOpt') and cmd.optionVar(q='animBlendingOpt') == 0:
        # PairBlend creation is disabled.  All incomming connections on attributes will spit out
        # warnings if we try to key them.
        removeConnectedAttributes(attributes)

    attrCount = 0
    for attr in attributes:
        # Test if we can use insert
        # canInsert returns 2 if something errored out in it.
        insertAttr = insert
        canInsert = canInsertKey(attr)
        if canInsert != 2:
            if not (insert and canInsert):
                insertAttr = False

            # Key it
            try:
                performSelect = selectNewKeyframe(attr)
                cmd.setKeyframe(attr, i=insertAttr)
                attrCount += 1

                # Select it if in between selected keys, or if adding new keys and the last one was selected.
                if performSelect:
                    cmd.selectKey(attr, add=1, k=1, t=(currentFrame, currentFrame))

            except Exception as err:
                print err
                om.MGlobal.displayError("Could not not set a key on %s." % attr)
    if attrCount:
        om.MGlobal.displayInfo('Set %d keys.' % attrCount)
    else:
        om.MGlobal.displayInfo('No keys were set.')


def selectNewKeyframe(attr):
    '''Determines if a new keyframe should be selected on the given attribute after being
    created on the current frame.  Returns True or False.'''

    # Find out the frame number of each selected key
    keys = cmd.keyframe(attr, q=1, timeChange=1, sl=1)
    if keys:
        # Find out the previous/next keys (they will be equal if either previous or next frame is missing)
        previousKey = cmd.findKeyframe(attr, which='previous')
        nextKey = cmd.findKeyframe(attr, which='next')

        # If the previous and next keys were selected, we need to select the new key.
        if previousKey in keys and nextKey in keys:
            return True
    return False


def canInsertKey(attr):
    '''Return if a given attribute can be keyframed with the insert keyframe command option.
    Returns the value 2 if something errored out inside.  Otherwise, it will return 0 or 1.'''
    # Insert keyframes are keyframes that match the curvature of the current keys around them.
    # They have a few limitations though...
    # You can't insert a keyframe if there are no keyframes to begin with
    try:
        if cmd.keyframe(attr, query=1, keyframeCount=1) == 0:
            return 0
    except:
        return 2

    # You don't want to insert a keyframe if the user changed something.
    # Thanks for keeping things consistent autodesk.  I always LOVE shit like this.
    # Keyframe always returns a list
    oldValue = cmd.keyframe(attr, query=1, eval=1)
    # GetAttr returns a single value if only one.  Otherwise, a list of tuples ex: [(0, 0, 0)]
    newValue = cmd.getAttr(attr)

    if not isinstance(newValue, collections.Iterable) and len(oldValue) == 1:
        # There's only one attribute.
        if round(oldValue[0], 6) != round(newValue, 6):
            return 0
    elif len(oldValue) == len(newValue[0]):
        # Attribute is an array, check each one.
        if any(round(oldValue[x], 6) != round(newValue[0][x], 6) for x in range(len(oldValue))):
            return 0
    else:
        # I don't know what this is.
        return 0
    return 1


def clearAttributes(graphEditor=None, channelBox=None):
    '''Clears any attributes selected in the graphEditor and/or channelBox.

    If nothing is passed it will clear the graphEditor if it is under the cursor,
    otherwise it will clear the channelBox.
    If graphEditor and/or channelBox is specified it will clear those no matter
    where the cursor is.'''
    if graphEditor is None and channelBox is None:
        graphEditorActive, panel = selectedAttributes.isGraphEditorActive()
        if graphEditorActive:
            clearGraphEditor(panel)
        else:
            clearChannelBox()
    else:
        if graphEditor:
            clearGraphEditor('graphEditor1')
        if channelBox:
            clearChannelBox()


def clearChannelBox():
    '''Deselects the channelBox attributes by reselecting objects.'''
    selected = cmd.ls(sl=1)
    if selected:
        cmd.select(selected)


def clearGraphEditor(panel):
    '''Deselects the attributes of the specified graphEditor panel by clearing the selectionConnection.'''

    selectionConnection = selectedAttributes.getSelectionConnection(panel)
    cmd.selectionConnection(selectionConnection, e=1, clr=1)


def syncGraphEditor():
    '''Syncs the attributes selected in the channelBox to those in the graphEditor.
    I don't know of any way to select channelBox attributes, so I have not been able
    to implement the equivalent syncChannelBox.'''

    # Get channelbox attributes
    attributes = selectedAttributes.getChannelBox(expandObjects=False)

    # Clear graph editor attributes
    selectionConnection = selectedAttributes.getSelectionConnection()
    cmd.selectionConnection(selectionConnection, e=1, clr=1)

    # Select channelbox attributes in graph editor
    for attr in attributes:
        cmd.selectionConnection(selectionConnection, edit=True, select=attr)


def selectSimilarAttributes(detectCursor=True):
    '''Selects the same attributes already selected on every node in the Graph Editor.

    When detectCursor is true, if your cursor is not over the Graph Editor, the Channel
    Box attributes are synced to the Graph Editor using the method syncGraphEditor().
    '''

    # Where is the cursor?
    useGraphEditor, panel = selectedAttributes.isGraphEditorActive()

    # Select similar attributes.
    if useGraphEditor or not detectCursor:
        # Get selected nodes and attributes
        attributes = selectedAttributes.getGraphEditor(panel, expandObjects=False)
        nodes = cmd.ls(sl=1, l=1)

        # Clear graph editor attributes
        selectionConnection = selectedAttributes.getSelectionConnection(panel)
        cmd.selectionConnection(selectionConnection, e=1, clr=1)

        # Process attributes
        # Get the attribute part of node.attribute and separate out selected objects.
        objs = []
        for x in reversed(range(len(attributes))):
            if '.' in attributes[x]:
                # This works for compound attributes too.  Trust me.
                null, attributes[x] = selectedAttributes.splitAttr(attributes[x])
            else:
                objs.append(attributes.pop(x))
        attributes = list(set(attributes))

        # Select the attributes on every node selected
        for attr in attributes:
            for node in nodes:
                try:
                    cmd.selectionConnection(selectionConnection, edit=True, select='%s.%s' % (node, attr))
                except:
                    # That attribute probably didn't exist on that node.
                    pass

        # reselect objects
        for obj in objs:
            cmd.selectionConnection(selectionConnection, edit=True, select=obj)

    else:
        syncGraphEditor()


def removeConnectedAttributes(attributes):
    '''Remove any attribute from given list that is connected to an object that is not an anim curve
    or a pairBLend'''
    for attr in attributes[:]:
        connection = getFirstConnection(attr, inAttr=1)
        if connection and not mel.eval('isAnimCurve("%s")' % connection):
            nodeType = cmd.ls(connection, st=1)
            if not nodeType or (nodeType and len(nodeType) > 1 and nodeType[1] != 'pairBlend'):
                attributes.remove(attr)


def isAttributeConnected(attr):
    '''Test if attribute is connected to an object that is not an anim curve or a pairBlend'''
    connection = getFirstConnection(attr, inAttr=1)
    if connection and not mel.eval('isAnimCurve("%s")' % connection):
        nodeType = cmd.ls(connection, st=1)
        if not nodeType or (nodeType and len(nodeType) > 1 and nodeType[1] != 'pairBlend'):
            return True
    return False


def getFirstConnection(node, attribute=None, inAttr=1, outAttr=None, findAttribute=0):
    '''An quick way to get a single object from an incomming or outgoing connection.'''
    # Translated from my mel script jh_fl_fishingLine.mel
    if attribute is None:
        node, attribute = selectedAttributes.splitAttr(node)
        if not attribute:
            om.MGlobal.displayInfo('Node %s has no attribute passed.  An attribute is needed to find a connection!' % node)

    if outAttr == None:
        outAttr = not inAttr
    else:
        inAttr = not outAttr

    try:
        nodes = cmd.listConnections('%s.%s' % (node, attribute), d=outAttr, s=inAttr, scn=1, p=findAttribute)
        if nodes:
            return nodes[0]
    except:
        om.MGlobal.displayWarning('%s has no attribute %s' % (node, attribute))

'''
if __name__ == '__main__':
	import cleverKeys
	reload(cleverKeys)
'''
