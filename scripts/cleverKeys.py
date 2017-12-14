'''cleverKeys is meant to improve setting keys intuitively in Maya.

If the mouse is over the graph editor, and a curve is selected, it keys
the attribute of the curve, otherwise, it keys the attributes selected
there. If the mouse is not over the graph editor, it keys the attributes
selected in the channel box.  If the channelBox is closed it will key
all the attributes on the selected node.  It attempts to use the "Insert
Key" function which makes keys match the curvature of the surrounding
keys whenever possible.  To use this module, call setKey()

*******************************************************************************
    License and Copyright
    Copyright 2012-2017 Jordan Hueckstaedt

    This program is free software: you can redistribute it and/or modify it
    under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or (at your
    option) any later version.

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

*******************************************************************************
'''

import collections

import maya.cmds as cmd
import maya.mel as mel
import pymel.core as pm
import maya.OpenMaya as om

import guppy_animation_tools as gat
from guppy_animation_tools import selectedAttributes


_log = gat.getLogger(__name__)


class KeyframeQueryFailed(Exception):
    pass


def toggleDebug():
    selectedAttributes.toggleDebug()


def setKey(insert=True, useSelectedCurves=True, usePartialCurveSelection=False):
    '''Sets clever keys.  Hohoho.

    If the mouse is over the graph editor, it keys the attributes
    selected there.  Otherwise it keys the attributes selected in the
    channel box. If the channelBox is closed it will key all the
    attributes on the selected node.  By default this uses the "Insert
    Key" behavior of Maya which makes keys match the curvature of the
    surrounding keys whenever possible.  Set insert parameter to false
    to disable this behavior.


    Parameters
    ----------
    insert : bool
        If true, uses the "insert key" behavior of Maya when creating keys.
        In this mode, key tangents will match any existing curves leaving
        them undisturbed.
    useSelectedCurves : bool
        If true, when an entire animation curve is selected in the graph
        editor (by clicking on the curve, not a key or tangent, or
        selecting every keyframe on the curve), then a key will only be
        inserted on the curves, other visible curves will be left alone.
    usePartialCurveSelection : bool
        This modifies the behavior of useSelectedCurves, and only
        affects behavior when that parameter is true as well. When true,
        this changes useSelectedCurves, so that selecting any part of a
        curve will limit keys to that curve (you do not need to select
        the entire curve).  Unselected curves will be left alone.
    '''

    # Get Attributes
    attributes = selectedAttributes.get(detectionType='cursor', useSelectedCurves=useSelectedCurves, usePartialCurveSelection=usePartialCurveSelection)
    currentFrame = cmd.currentTime(q=1)

    # Make extra sure attributes are unique (they should already be)
    attributes = list(set(attributes))

    if cmd.optionVar(ex='animBlendingOpt') and cmd.optionVar(q='animBlendingOpt') == 0:
        # PairBlend creation is disabled.  All incomming connections on
        # attributes will spit out warnings if we try to key them.
        removeConnectedAttributes(attributes)

    attrCount = 0
    for attr in attributes:
        # Test if we can use insert
        # canInsert returns 2 if something errored out in it.
        insertAttr = insert
        try:
            canInsert = canInsertKey(attr)
        except KeyframeQueryFailed as err:
            # Don't even try to key the attribute if we couldn't query it.
            _log.debug("KeyframeQueryFailed: %s", err)
        else:
            if not (insert and canInsert):
                insertAttr = False

            # Key it
            try:
                performSelect = selectNewKeyframe(attr)
                cmd.setKeyframe(attr, i=insertAttr)
                attrCount += 1

                # Select it if in between selected keys, or if adding
                # new keys and the last one was selected.
                if performSelect:
                    cmd.selectKey(attr, add=1, k=1, t=(currentFrame, currentFrame))

            except RuntimeError as err:
                print err
                om.MGlobal.displayError("Could not not set a key on %s." % attr)
    if attrCount:
        om.MGlobal.displayInfo('Set %d keys.' % attrCount)
    else:
        om.MGlobal.displayInfo('No keys were set.')


def selectNewKeyframe(attr):
    '''Determines if a new keyframe should be selected on the given attribute
    after being created on the current frame.  Returns True if the keyframes
    were selected.'''

    # Find out the frame number of each selected key
    keys = cmd.keyframe(attr, q=1, timeChange=1, sl=1)
    if keys:
        # Find out the previous/next keys (they will be equal if either
        # previous or next frame is missing)
        previousKey = cmd.findKeyframe(attr, which='previous')
        nextKey = cmd.findKeyframe(attr, which='next')

        # If the previous and next keys were selected, we need to select
        # the new key.
        if previousKey in keys and nextKey in keys:
            return True
    return False


def canInsertKey(attr):
    '''
    Returns True if a given attribute can be keyframed with the insert keyframe
    command option.

    Raises KeyframeQueryFailed
    '''
    # Insert keys match the curvature of the existing curve.
    # They have a few limitations though...
    try:
        # You can't insert a keyframe if there are no keyframes to begin with
        if cmd.keyframe(attr, query=1, keyframeCount=1) == 0:
            return False
    except RuntimeError as err:
        raise KeyframeQueryFailed(err)

    # You don't want to insert a keyframe if the user changed something.
    # Keyframe always returns a list
    oldValue = cmd.keyframe(attr, query=1, eval=1)
    # GetAttr returns a single value if only one.  Otherwise, a list of
    # tuples ex: [(0, 0, 0)]
    newValue = cmd.getAttr(attr)

    if not isinstance(newValue, collections.Iterable) and len(oldValue) == 1:
        # There's only one attribute.
        if round(oldValue[0], 6) != round(newValue, 6):
            return False
    elif len(oldValue) == len(newValue[0]):
        # Attribute is an array, check each one.
        if any(round(oldValue[x], 6) != round(newValue[0][x], 6) for x in range(len(oldValue))):
            return False
    else:
        # I don't know what this is.
        return False
    return True


def clearAttributes(graphEditor=False, channelBox=False):
    '''Clears any attributes selected in the graphEditor and/or channelBox.

    If nothing is passed it will clear the graphEditor if it is under the
    cursor, otherwise it will clear the channelBox. If graphEditor and/or
    channelBox is specified it will clear those no matter where the cursor
    is.'''
    if not graphEditor and not channelBox:
        graphInfo = selectedAttributes.GraphEditorInfo.detect(restrictToCursor=True)

        if graphInfo.isValid():
            clearGraphEditor(graphInfo.panelName)
        else:
            clearChannelBox()
    else:
        if graphEditor:
            graphInfo = selectedAttributes.GraphEditorInfo.detect()
            if graphInfo.isValid():
                clearGraphEditor(graphInfo.panelName)
        if channelBox:
            clearChannelBox()


def clearChannelBox():
    '''Deselects the channelBox attributes.'''

    try:
        # I hear that the select flag was added in Maya 2016 Extension 2
        pm.channelBox(
            pm.melGlobals['gChannelBoxName'], select=None, edit=True)
    except TypeError:

        # ## Legacy Approach.
        # Since Maya does not provide direct access to channel box
        # selection, we need to trick Maya into de-selecting channel box
        # attributes by reselecting the current object selection.
        selected = cmd.ls(sl=1)
        if selected:
            cmd.select(clear=1)
            # We must defer the re-selection, or Maya won't refresh the gui.
            # The refresh() command won't work because that only refreshes
            # the viewport (as far as I know).  The "channelBox -update"
            # command does nothing.
            cmd.evalDeferred(lambda: cmd.select(selected))


def clearGraphEditor(panel):
    '''Deselects the attributes of the specified graphEditor panel by clearing
    the selectionConnection.'''

    selectionConnection = selectedAttributes.selectionConnectionFromPanel(panel)

    # Clear current selection, including filtered attributes
    cmd.selectionConnection(selectionConnection, e=1, clr=1)

    # Reselect just the nodes. Restoring the graph editor to the state
    # it would be in if you had just selected these.
    for node in cmd.ls(selection=True):
        cmd.selectionConnection(selectionConnection, edit=True, select=node)


def syncGraphEditor(graphInfo=None):
    '''
    Syncs the attributes selected in the channelBox to those in the
    graphEditor.
    '''
    graphInfo = graphInfo or selectedAttributes.GraphEditorInfo.detect()
    if not graphInfo.isValid():
        return

    # Get channelbox attributes
    attributes = selectedAttributes.getChannelBox(expandObjects=False)

    # Clear graph editor attributes
    selectionConnection = selectedAttributes.selectionConnectionFromPanel(
        graphInfo.panelName)
    cmd.selectionConnection(selectionConnection, e=1, clr=1)

    # Select channelbox attributes in graph editor
    for attr in attributes:
        cmd.selectionConnection(selectionConnection, edit=True, select=attr)


def syncChannelBox(graphInfo=None, perfectSync=False):
    '''
    Syncs the attributes selected in the graphEditor to those in the
    channelBox.

    Attributes selected in the graphEditor will be modified
    to so that every node has the same attributes selected - this
    "trues" up the channelbox selection with the graph editor.
    '''

    graphInfo = graphInfo or selectedAttributes.GraphEditorInfo.detect()
    if not graphInfo.isValid():
        return

    # Get selected nodes and attributes
    selected = selectedAttributes.getGraphEditor(graphInfo, expandObjects=False)
    nodes = cmd.ls(sl=1, l=1)

    # Process attributes
    # Get the attribute part of node.attribute and separate out
    # selected objects.
    objs = []
    attributes = set()
    for nodeOrAttr in selected:
        if '.' in nodeOrAttr:
            # This works for compound attributes too.  Trust me.
            attributes.add(selectedAttributes.splitAttr(nodeOrAttr)[1])
        else:
            objs.append(nodeOrAttr)
    attributes = list(attributes)

    objAttrs = ["%s.%s" % (node, attr) for attr in attributes for node in nodes]
    try:
        # I hear that the select flag was added in Maya 2016 Extension 2
        pm.channelBox(
            pm.melGlobals['gChannelBoxName'], select=objAttrs, edit=True)
    except TypeError:
        # Legacy behavior before channelBox -select flag was created
        # Does not actually sync with channel box, because that was impossible.
        # instead it just selected the same attributes on all graph nodes.
        if perfectSync:
            # Clear graph editor attributes
            selectionConnection = selectedAttributes.selectionConnectionFromPanel(
                graphInfo.panelName)
            cmd.selectionConnection(selectionConnection, edit=True, clr=True)

            # Select the attributes on every node selected
            for attr in attributes:
                for node in nodes:

                    try:
                        cmd.selectionConnection(selectionConnection, edit=True,
                                                select='%s.%s' % (node, attr))
                    except RuntimeError:
                        # That attribute probably didn't exist on that node.
                        pass

            # reselect objects
            for obj in objs:
                cmd.selectionConnection(selectionConnection, edit=True, select=obj)
    else:
        if perfectSync:
            syncGraphEditor(graphInfo=graphInfo)


def selectSimilarAttributes(detectCursor=True, perfectSync=False):
    '''
    Selects the same attributes already selected on every node in the Graph
    Editor.

    When detectCursor is True, if your cursor is over the Graph
    Editor, the Graph Editor selection is synced to the ChannelBox, otherwise
    the ChannelBox is synced to the Graph Editor.
    When detectCursor is False, your channel box is always synced to the Graph
    Editor.

    When perfectSync is True and the graph editor is syncing to the channel box,
    the graph editor selection will change as well so that it is a valid
    channel box selection (every attribute is selected on every node).
    '''

    # Where is the cursor?
    graphInfo = selectedAttributes.GraphEditorInfo.detect(restrictToCursor=detectCursor)

    # Select similar attributes.
    if graphInfo.isValid():
        # Sync graph editor selection to channel box.
        syncChannelBox(graphInfo=graphInfo, perfectSync=perfectSync)
    else:
        syncGraphEditor()


def removeConnectedAttributes(attributes):
    '''Remove any attribute from given list that is connected to an object that
    is not an anim curve or a pairBLend'''
    for attr in attributes[:]:
        connection = getFirstConnection(attr, inAttr=1)
        if connection and not mel.eval('isAnimCurve("%s")' % connection):
            nodeType = cmd.ls(connection, st=1)
            if not nodeType or (nodeType and len(nodeType) > 1 and nodeType[1] != 'pairBlend'):
                attributes.remove(attr)


def isAttributeConnected(attr):
    '''Test if attribute is connected to an object that is not an anim curve or
    a pairBlend'''
    connection = getFirstConnection(attr, inAttr=1)
    if connection and not mel.eval('isAnimCurve("%s")' % connection):
        nodeType = cmd.ls(connection, st=1)
        if not nodeType or (nodeType and len(nodeType) > 1 and nodeType[1] != 'pairBlend'):
            return True
    return False


def getFirstConnection(node, attribute=None, inAttr=1, outAttr=None, findAttribute=0):
    '''An quick way to get a single object from an incoming or outgoing
    connection.'''
    if attribute is None:
        node, attribute = selectedAttributes.splitAttr(node)
        if not attribute:
            om.MGlobal.displayInfo('Node %s has no attribute passed.  An attribute is needed to find a connection!' % node)

    if outAttr is None:
        outAttr = not inAttr
    else:
        inAttr = not outAttr

    try:
        nodes = cmd.listConnections('%s.%s' % (node, attribute), d=outAttr, s=inAttr, scn=1, p=findAttribute)
        if nodes:
            return nodes[0]
    except RuntimeError:
        om.MGlobal.displayWarning('%s has no attribute %s' % (node, attribute))
