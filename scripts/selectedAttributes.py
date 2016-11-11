'''Selected Attributes is a module for intelligently retrieving the selected
attributes in the channelbox and graph editor.

The primary method associated with this module is the "get" method.'''

'''****************************************************************************
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

    Author:........Jordan Hueckstaedt
    Website:.......RubberGuppy.com
    Email:.........AssumptionSoup@gmail.com
'''

__author__ = 'Jordan Hueckstaedt'
__copyright__ = 'Copyright 2012 Jordan Hueckstaedt'
__license__ = 'LGPL v3'
__version__ = '0.14'
__email__ = 'AssumptionSoup@gmail.com'
__status__ = 'Production'

import maya.cmds as cmd
import maya.OpenMaya as om
import maya.mel as mel

# DEBUG methods
DEBUG = 0


def toggleDebug():
    global DEBUG
    DEBUG = not DEBUG

__report_indent = [0]


def printCalled(fn):
    """Decorator to print information about a function
    call for use while debugging.
    Prints function name, arguments, and call number
    when the function is called. Prints this information
    again along with the return value when the function
    returns.
    """

    def wrap(*params, **kwargs):
        if DEBUG:
            wrap.callcount = wrap.callcount + 1

            indent = ' ' * __report_indent[0]
            fc = "%s(%s)" % (fn.__name__, ', '.join(
                [a.__repr__() for a in params] +
                ["%s = %s" % (a, repr(b)) for a, b in kwargs.items()]
            ))

            print "%s%s called" % (indent, fc)
            __report_indent[0] += 1
            ret = fn(*params, **kwargs)
            __report_indent[0] -= 1
            print "%s%s returned %s" % (indent, fc, repr(ret))
        else:
            ret = fn(*params, **kwargs)
        return ret
    wrap.callcount = 0
    return wrap

# The real methods


@printCalled
def get(detectionType='cursor', useSelectedCurves=True, animatableOnly=True):
    '''Get selected attributes using the given detection type.

    A detectionType of 'cursor' will find selected attributes in the graph
    editor if the user has their cursor over that panel.  Otherwise, any
    attributes selected in the channelbox will be used.  If the channelbox is
    closed, attributes on the selected nodes will be returned.

    A detectionType of 'panel' will find selected attributes in the graph
    editor if it is open. If it is closed or minimized, it will return
    attributes selected in the channelbox.  If the channelbox is closed, it
    will grab attributes on the selected nodes.
    '''

    # Determine which attributes to grab.
    useGraph, panel = useGraphAttributes(detectionType=detectionType)

    # Get selected attributes from the channelBox or graphEditor depending on where the cursor is.
    if useGraph:
        # Pass list by reference
        attributes = getGraphEditor(panel, useSelectedCurves=useSelectedCurves, animatableOnly=animatableOnly)
    else:
        attributes = getChannelBox(animatableOnly=animatableOnly)

    return attributes


@printCalled
def useGraphAttributes(detectionType='cursor'):
    '''Determines whether to use the graph editor or not based on the detection
    type'''

    if detectionType.lower() == 'cursor':
        # Find out if the graph editor is under cursor, and the
        # graphPanel if it is
        useGraphAttributes, panel = isGraphEditorActive()
    elif detectionType.lower() == 'panel':
        # Use the graph editor if it is open.
        panel = findGraphEditorPanel()
        useGraphAttributes = isGraphEditorVisible(panel) if panel else False
    else:
        raise Exception('%s is not a valid detection type.  Use "cursor" or "panel"' % detectionType)

    return useGraphAttributes, panel


def splitAttr(fullPath):
    '''Split object.attr.attr into (object, attr.attr)'''
    attrs = fullPath.split('.')
    return attrs.pop(0), '.'.join(attrs)


def homogonizeName(fullPath):
    '''Takes in any full attribute path and returns the relative object path
    with full attribute names'''
    # Split attributes
    attrs = fullPath.split('.')

    # Get relative path to object while removing obj from attrs
    obj = cmd.ls(attrs.pop(0), o=1)[0]

    # Get full name of each attribute and add it back to obj.
    for attr in attrs:
        fullAttr = '%s.%s' % (obj, attr)
        longName = cmd.attributeName(fullAttr, l=1)
        if ' ' in longName:
            # Maya has seen fit to sometimes give nice names instead of
            # long names. Here, we'll hope to god that the nice name
            # correlates exactly with the long name. and camel case it.
            # Yaaaay Autodesk.
            longName = [name.capitalize() for name in longName.split()]
            longName[0] = longName[0].lower()
            longName = ''.join(longName)
        obj = '%s.%s' % (obj, longName)

    return obj


@printCalled
def getAnimatableAttributes(obj):
    '''Returns keyable attributes on an object.  Always returns a list'''

    attrs = cmd.listAnimatable(obj)
    if attrs:
        # Remove shapes from attributes.  List animatable includes them
        # by default.
        # attrs = [attr for attr in attrs if not cmd.ls(attr.split('.')[0], s = 1)]

        # Homogenize names.  (listAnimatable returns FULL paths).
        # ListAnimatable might return a shape instead of the original
        # given object, so cmd.ls(attr, o = 1)[0] is needed to determine
        # the relative path.
        attrs = [homogonizeName(attr) for attr in attrs]
    else:
        attrs = []
    removeUnderworldFromPath(attrs)
    return attrs


@printCalled
def getNonAnimatableAttributes(obj):
    '''Returns non-keyable attributes on an object.  Always returns a list.

    If this fails to work again, I recommend disabling it in
    filterSelectedToAttributes'''
    attrs = []

    # Get scalar keyable attributes.  I believe only scalar attributes appear in the channel box
    # Though I have been known to be mistaken about these things before.
    allKeyable = cmd.listAttr(obj, k=1, s=1)
    if allKeyable:
        for attr in allKeyable:
            try:
                # Get non-multi attributes
                if cmd.getAttr('%s.%s' % (obj, attr), size=1) == 1:
                    attrs.append(attr)
            except ValueError:
                # Most likely failed because of a multi attribute not yet set
                # For some reason listAttr includes these.  And listAttr -multi does not
                # so I can't filter them out.  Yaaaaaaaay Autodesk.
                pass

    # Grab non-keyable attributes in channel box.
    nonKeyable = cmd.listAttr(obj, cb=1)
    if nonKeyable:
        attrs.extend(nonKeyable)

    # Homogonize names.
    attrs = [homogonizeName('%s.%s' % (obj, attr)) for attr in attrs]
    removeUnderworldFromPath(attrs)
    return attrs


@printCalled
def filterSelectedToAttributes(selected, attributes, expandObjects, animatableOnly):
    '''The real brains of the operation.  Filters the given objects/attributes
    into obj.attribute pairs, keeping things homogenized with long attribute
    names.  Sorts attributes further depending on the expandObjects and
    animatableOnly parameters.

    If expandObjects is false, entire objects are returned instead of all the
    attributes on that object.

    if animatableOnly is true, only keyable attributes are returned from the
    ones given.'''

    # Seperate the attributes from the objects, the men from the boys.
    objects = []
    for obj in selected:
        if '.' in obj or not expandObjects:
            attributes.append(obj)
        else:
            objects.append(obj)

    if expandObjects:
        # Add objects to attribute list while avoid keying objects if the attribute is already selected
        attrs = []
        for obj in objects:
            # Skip object if it's already in attributes
            if not any(1 for att in attributes if '%s.' % obj in att):
                # Combine attributes with the object names to be: object.attribute
                # If there are no animatable attrs, could be None.
                attrs += getAnimatableAttributes(obj)  # Did you know you can extend() lists like this?  For some reason, I never knew.

                # Add non-keyable attributes if needed.  Disable this chunk if getNonAnimatableAttributes fails again
                if not animatableOnly:
                    nonAnimatable = [a for a in getNonAnimatableAttributes(obj) if a not in attrs]
                    attrs += nonAnimatable

        # Woops!  Used to have this in the loop.  That's a big logic no-no.
        # Don't want to modify something your checking against unless you're very very careful.  Which I wasn't.
        attributes += attrs


@printCalled
def getGraphEditor(panel='graphEditor1', expandObjects=True, useSelectedCurves=True, animatableOnly=True):
    '''Get attributes selected in the graph editor.

    If expandObjects is true, attributes are saved in the format
    object.attribute and a lack of selection or an entire object selected will
    expand to that object's keyable nodes.

    Otherwise, the list will be a mix of object.attribute and object.  Objects
    will not have their attributes expanded.
    '''
    attributes = []

    # Get selected
    selected = getGraphSelection(panel, useSelectedCurves=useSelectedCurves)

    if selected:
        # This is rare, but eliminate underworld paths.
        removeUnderworldFromPath(selected)

        filterSelectedToAttributes(selected, attributes, expandObjects, animatableOnly)
    return attributes


@printCalled
def getChannelBox(expandObjects=True, animatableOnly=True, selectedOnly=False):
    '''Gets attributes selected in the channelBox.

    Will only find attributes that are selected in the channelBox if the
    channelbox is visible.  If expandObjects is true attributes are saved in
    the format object.attribute.  Otherwise whole objects may be returned if no
    attributes are selected. Selected only will only return attributes if they
    are selected on a visible channelbox.
    '''

    # This comment is currently not relevant, but may be if
    # getNonAnimatableAttributes is disabled again
    #
    # When animatableOnly is false locked and unkeyable attributes that
    # are selected will be returned.  Keep in mind that unselected but
    # visible locked and unkeyable attributes will not be returned, as I
    # have found no consistent way to determine these attributes.

    attributes = []

    # get objects selected
    objects = cmd.ls(sl=1)

    # This is rare, but eliminate underworld paths.
    removeUnderworldFromPath(objects)
    channelBox = mel.eval('$gChannelBoxName=$gChannelBoxName')  # Annoying method of getting mainChannelBox name.
    channelBoxVisible = isChannelBoxVisible(channelBox)

    selected = 0
    if channelBoxVisible:
        # Find what's selected (if anything) in the channelBox
        channelAttributes = ['sma', 'ssa', 'sha', 'soa']
        channelObjects = ['mol', 'sol', 'hol', 'ool']
        channelAreas = zip(channelObjects, channelAttributes)

        foundObjs = []
        for objArea, attrArea in channelAreas:
            attrs = {attrArea: 1}
            objs = {objArea: 1}
            attrs = cmd.channelBox(channelBox, q=1, **attrs)
            objs = cmd.channelBox(channelBox, q=1, **objs)

            if objs:
                foundObjs.extend(objs)
            # Something was selected
            if objs and attrs:
                for obj in objs:
                    # Find keyable attributes to filter.
                    if animatableOnly:
                        keyableAttrs = getAnimatableAttributes(obj)

                    for attr in attrs:
                        # Make sure the attribute isn't something incredibly weird that will fail later.
                        try:
                            attr = homogonizeName('%s.%s' % (obj, attr))
                        except RuntimeError:
                            continue

                        # Filter only keyable objects if necessary.
                        selected = 1
                        if animatableOnly and keyableAttrs:
                            if attr in keyableAttrs:
                                attributes.append(attr)
                        else:
                            attributes.append(attr)
        if not selectedOnly and not animatableOnly and not selected:
            # Mostly for shapes, since shapes do not show up in
            # cmd.ls(), non-animatable attributes on shapes will not be
            # added, unless we let filterSelectedToAttributes know that
            # shapes are there.
            objects.extend(foundObjs)

    # There is at least one object selected, but no attributes
    if not selectedOnly and (not channelBoxVisible or (not selected and objects)):
        filterSelectedToAttributes(objects, attributes, expandObjects, animatableOnly)

    return attributes


@printCalled
def getFirstConnection(node, attribute=None, inAttr=1, outAttr=None, findAttribute=0):
    '''An quick way to get a single object from an incomming or outgoing
    connection.'''
    # Translated from my mel script jh_fl_fishingLine.mel
    if attribute is None:
        node, attribute = splitAttr(node)
        if not attribute:
            raise Exception('Node %s has no attribute passed.  An attribute is needed to find a connection!' % node)

    if outAttr == None:
        outAttr = not inAttr
    else:
        inAttr = not outAttr

    try:
        nodes = cmd.listConnections('%s.%s' % (node, attribute), d=outAttr, s=inAttr, scn=1, p=findAttribute)
        if nodes:
            return nodes[0]
    except Exception:
        raise Exception('%s has no attribute %s' % (node, attribute))


@printCalled
def getEditorFromPanel(panel, editorCommand):
    '''Finds the editor associated with the given panel.  editorCommand must be
    the editor's function e.g. maya.cmds.nodeEditor'''
    editors = cmd.lsUI(editors=1)

    for editor in editors:
        if editorCommand(editor, ex=1):
            if editorCommand(editor, q=1, pnl=1) == panel:
                return editor


@printCalled
def getSelectionConnection(panel='graphEditor1'):
    '''A more robust way of determining the selection connection of a graph
    editor given its panel Returns None if nothing is found.'''

    outliner = getEditorFromPanel(panel, cmd.outlinerEditor)

    if outliner is not None:
        return cmd.outlinerEditor(outliner, q=1, selectionConnection=1)
    return None


@printCalled
def getSelectedCurves():
    '''Returns a list of all curves that are completely selected.'''
    selection = []

    # First see if there are any curves selected
    curves = cmd.keyframe(q=1, name=1, sl=1)
    if curves:
        for curve in curves:
            # Find out if the entire curve is selected, based on keyframe count.
            totalKeyframes = cmd.keyframe(curve, q=1, keyframeCount=1)
            selectedKeyframes = cmd.keyframe(curve, q=1, keyframeCount=1, sl=1)
            if totalKeyframes == selectedKeyframes:
                try:
                    # Trace the output of  the curve to find the attribute.
                    attr = getFirstConnection(curve, 'output', outAttr=1, findAttribute=1)
                    selection.append(attr)
                except RuntimeError:
                    pass
            else:
                # Short circut the whole loop.  If there's ever any
                # selection that is NOT an entire curve, then NOTHING is
                # returned Without this, other functions may operate
                # only on curves, but ignore other selected keys, which
                # is not desirable.
                return []
    return selection


@printCalled
def wereSelectedCurvesUsed(detectionType='cursor', useSelectedCurves=True):
    '''Returns true if selected curves took precedence while obtaining
    attributes'''

    if useSelectedCurves:
        useGraph, panel = useGraphAttributes(detectionType=detectionType)
        if useGraph:
            if getSelectedCurves():
                return True
    return False


@printCalled
def getGraphSelection(panel='graphEditor1', useSelectedCurves=True):
    '''A robust method of finding the selected objects/attributes in the graph
    editor. If nothing is selected, all objects in the graph outliner will be
    returned.  If a one or more curves are selected, those curves take
    precedence over any other selection.

    Always returns a list.'''

    # First see if there are any curves selected
    if useSelectedCurves:
        selection = getSelectedCurves()

        if selection:
            return selection

    else:
        selection = []

    # Get the graph outliner ui name.
    outliner = getEditorFromPanel(panel, cmd.outlinerEditor)

    if outliner is not None:
        # Find selected attributes
        sc = cmd.outlinerEditor(outliner, q=1, selectionConnection=1)
        selection = cmd.selectionConnection(sc, q=1, object=1)

        # If nothing is selected, find objects present in outliner.
        if not selection:
            sc = cmd.outlinerEditor(outliner, q=1, mainListConnection=1)
            selection = cmd.selectionConnection(sc, q=1, object=1)

        if not selection:
            selection = []

    return selection


@printCalled
def isChannelBoxVisible(channelBox):
    '''Returns if the channelBox is visible to the user (the user does not have
    another control docked in front of it).'''
    chVisible = 0

    # Test if QT version exists:
    if not mel.eval('catchQuiet(`isChannelBoxRaised`)'):
        # Undocumented mel proc in setChannelBoxVisible.mel included in 2011+
        # Roughly traces channelBox by name until its dockControl is found, and queries that.
        return mel.eval('isChannelBoxRaised()')
    else:
        # This command has the same functionality as isChannelBoxRaised, UNTIL QT was introduced.
        return not cmd.channelBox(channelBox, q=1, io=1)


@printCalled
def isGraphEditorActive():
    '''Returns a tuple of (graphEditorState, graphEditorPanel).
    GraphEditorState is true if the cursor is over the graph editor, and false
    if it is not, or if the cursor can not be queried.  The graphEditorPanel
    will default to 'graphEditor1' if no graph editor is found under the
    mouse.'''

    # Find out if the graph editor is under cursor
    graphEditorActive = False
    panel = ''
    try:
        panel = cmd.getPanel(underPointer=True)
    except TypeError:
        # Maya is being bitchy again.  Default to channelBox and warn
        # the user that Maya is a bitch. Yes, I've had this fail here
        # before.  Maya told me underPointer needed to be passed a bool.
        # Well, I hate to tell you Maya, but True is a bool.
        om.MGlobal.displayWarning("Defaulting to channelBox because Maya doesn't know where your cursor is.")

    if panel and cmd.getPanel(typeOf=panel) == 'scriptedPanel':
        # I assume that testing for the type will be more accurate than matching the panel strings
        if cmd.scriptedPanel(panel, q=1, type=1) == 'graphEditor':
            graphEditorActive = True

    # A graph editor panel should always be passed, even if we couldn't find a specific one.
    if not graphEditorActive:
        panel = 'graphEditor1'
    return graphEditorActive, panel


@printCalled
def findGraphEditorPanel():
    """
    Find the first graph editor panel, if one exists.
    Returns None if no panel exists
    """
    graphPanels = [panel for panel in (cmd.getPanel(type='scriptedPanel') or []) 
                   if cmd.scriptedPanel(panel, q=1, type=1) == 'graphEditor']
    if graphPanels:
        # Sort graph panels just to help keep things deterministic if more than one is open.
        return sorted(graphPanels)[0]
    else:
        return None


@printCalled
def isGraphEditorVisible(panel):
    '''Determines if the provided graph editor panel is open by finding the
    associated window. Minimized graph editors are considered closed.'''

    # If the panel was passed in, there's a chance it was the wrong type.
    if cmd.getPanel(typeOf=panel) == 'scriptedPanel' and cmd.scriptedPanel(panel, q=1, type=1) == 'graphEditor':
        allWindows = cmd.lsUI(windows=1)
        panelPath = cmd.scriptedPanel(panel, q=1, ctl=1)

        if panelPath and allWindows:
            # I can't find any easy api access to the window like panel.getWindow()
            # So we have to do things the hard way and string match window paths
            # to the controller paths.
            matchingWindows = [window for window in allWindows if panelPath.startswith(window)]
            if matchingWindows:
                # Take the longest path, just in case there's more than one match.
                # I don't think there can be, but just in case maya can make nested
                # windows, lets do this to be safe.
                window = sorted(matchingWindows)[-1]

            if cmd.window(window, q=1, vis=1) and not cmd.window(window, q=1, i=1):
                # If the panel is visible and not minimized.
                return True
    return False


@printCalled
def removeUnderworldFromPath(attributes):
    '''This is rare, but more than one underworld -> marker in the path will
    break a lot of things in Maya. This removes all -> from path if there is
    more than one. Maya assumes underworld objects can't be parented.  Except
    Maya will parent them itself under certain circumstances... Like I said,
    really rare. Modifies attributes by reference.'''
    for x in range(len(attributes)):
        if attributes[x].count('->') >= 2:
            attributes[x] = attributes[x].split('->')[-1]
