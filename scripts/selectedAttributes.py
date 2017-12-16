'''Selected Attributes is a module for intelligently retrieving the selected
attributes in the channelbox and graph editor.

The primary method associated with this module is the "get" method.'''

'''****************************************************************************
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

*******************************************************************************

    Author:........Jordan Hueckstaedt
    Website:.......RubberGuppy.com
    Email:.........AssumptionSoup@gmail.com
'''

import maya.cmds as cmd
import maya.OpenMaya as om
import maya.mel as mel
import pymel.core as pm

import guppy_animation_tools as gat

# DEBUG methods
DEBUG = 0
_log = gat.getLogger(__name__)


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


class GraphEditorInfo(object):
    '''
    Encapsulates finding information about graph editors.
    '''
    # NOTE: Do not use pymel for UI objects. While in general PyMel is
    #       GREAT for nodes, the UI portion of it has needed some love
    #       for awhile now. UI objects don't appear to maintain state
    #       correctly, and behave really weird.  Some commands return UI
    #       objects while others still return strings.  It's a kind of a
    #       mess.

    def __init__(self, panelName):
        self.panelName = panelName

    @staticmethod
    def _getPanelUnderCursor():
        '''
        Returns the name of the panel under the cursor
        '''
        try:
            # May return None if no panel found
            panel = cmd.getPanel(underPointer=True)
        except TypeError:
            # Maya is ...special.  Yes, I've had this fail on this line
            # before. With a TypeError.  Maya told me underPointer
            # needed to be passed a bool. Well, I hate to tell you Maya,
            # but True is a bool.
            _log.debug("Old maid Maya has lost her cursor again.")
            panel = None
        return panel

    @staticmethod
    def _getPanelWithFocus():
        return cmd.getPanel(withFocus=True)

    @staticmethod
    def _isPanelVisible(panelName):
        '''
        Determines if the given panel is open. Minimized panels are
        considered closed.
        '''

        # Sanity Check:
        if not (panelName and cmd.scriptedPanel(panelName, query=True, exists=True)):
            return False


        # cmd.scriptedPanel does not provide a way to query what window
        # it uses.  cmd.lsUI(windows=1) appears to be broken in maya
        # 2018, only returning 'MayaWindow', even when more windows are
        # open. Which means it's no longer possible to search for
        # windows by name.  Therefore, the ONLY way to query a window
        # AFAIK is the most fragile - to simply hope it's at the top
        # level of the UI path (I suppose we might be able to trace it
        # using QT, but that comes with the small risk of segfaulting
        # instead of simply erroring).  So much for good coding
        # standards. #ThanksMaya!

        # Get full path to panel
        panelPath = cmd.scriptedPanel(panelName, query=True, control=True)
        if not panelPath:  # The docs say scriptedPanels may not have controls
            return False   # But I don't realistically think this will happen.

        # Use root path as window.
        window = panelPath.split('|')[0]
        if not window:
            return False

        # Return if the window is visible and not minimized.
        return (cmd.window(window, query=True, visible=True) and
                not cmd.window(window, query=True, iconify=True))

    @staticmethod
    def _isPanelGraphEditor(panelName):
        return (
            panelName and
            cmd.getPanel(typeOf=panelName) == 'scriptedPanel' and
            cmd.scriptedPanel(panelName, query=1, type=1) == 'graphEditor')

    @classmethod
    def detect(cls, restrictToCursor=False, restrictToFocus=False, restrictToVisible=False):
        scriptedPanels = cmd.getPanel(type='scriptedPanel') or []
        graphPanels = set(
            panel for panel in scriptedPanels
            if cmd.scriptedPanel(panel, query=True, type=True) == 'graphEditor')

        focusedPanel = cls._getPanelWithFocus()
        cursorPanel = cls._getPanelUnderCursor()

        if restrictToFocus:
            graphPanels = set([focusedPanel]) if focusedPanel in graphPanels else set()

        if restrictToCursor:
            graphPanels = set([cursorPanel]) if cursorPanel in graphPanels else set()

        if restrictToVisible:
            graphPanels = set(filter(cls._isPanelVisible, graphPanels))

        graphPanel = None
        if len(graphPanels) == 1:
            graphPanel = graphPanels.pop()
        elif len(graphPanels) > 1:
            # Restrictions have not narrowed down a possibility
            # Magical preference order kicks in here.
            if focusedPanel in graphPanels:
                graphPanel = focusedPanel
            elif cursorPanel in graphPanels:
                graphPanel = cursorPanel
            else:
                visiblePanels = filter(cls._isPanelVisible, graphPanels)
                if visiblePanels:
                    graphPanel = sorted(visiblePanels)[0]
                else:
                    graphPanel = sorted(graphPanels)[0]

        return cls(graphPanel)

    def isUnderCursor(self):
        '''
        Returns True if any graph editor is under the cursor.
        '''
        return self.isValid() and self._getPanelUnderCursor() == self.panelName

    def isFocused(self):
        return self.isValid() and self._getPanelWithFocus() == self.panelName

    def isVisible(self):
        '''
        Determines this graph editor is open. Minimized graph editors
        are considered closed.
        '''
        return self.isValid() and self._isPanelVisible(self.panelName)

    def isValid(self):
        return bool(self.panelName) and cmd.scriptedPanel(self.panelName, query=True, exists=True)


@printCalled
def get(detectionType='cursor', useSelectedCurves=True, animatableOnly=True, usePartialCurveSelection=True):
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
    if detectionType == 'cursor':
        graphEditor = GraphEditorInfo.detect(restrictToCursor=True)
    elif detectionType == 'panel':
        graphEditor = GraphEditorInfo.detect(restrictToVisible=True)
    else:
        raise ValueError('%s is not a valid detection type.  Use "cursor" or "panel"' % detectionType)

    # Get selected attributes from the channelBox or graphEditor depending on where the cursor is.
    if graphEditor.isValid():
        # Pass list by reference
        attributes = getGraphEditor(graphEditor,
            useSelectedCurves=useSelectedCurves,
            animatableOnly=animatableOnly,
            usePartialCurveSelection=usePartialCurveSelection)
    else:
        attributes = getChannelBox(animatableOnly=animatableOnly)

    return attributes


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
def filterSelectedToAttributes(selected, expandObjects, animatableOnly):
    '''
    The real brains of the operation.  Filters the given objects/attributes
    into obj.attribute pairs, keeping things homogenized with long attribute
    names.  Sorts attributes further depending on the expandObjects and
    animatableOnly parameters.

    If expandObjects is false, entire objects are returned instead of all the
    attributes on that object.

    if animatableOnly is true, only keyable attributes are returned from the
    ones given.'''

    # Separate the attributes from the objects, the men from the boys.
    attributes = []
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
                attributes.extend(getAnimatableAttributes(obj))

                # Add non-keyable attributes if needed.  Disable this chunk if getNonAnimatableAttributes fails again
                if not animatableOnly:
                    attributes.extend(a for a in getNonAnimatableAttributes(obj)
                                      if a not in attrs)

        attributes.extend(attrs)
    return attributes


@printCalled
def getGraphEditor(graphInfo, expandObjects=True, useSelectedCurves=True, animatableOnly=True, usePartialCurveSelection=True):
    '''
    Get attributes selected in the graph editor.

    If expandObjects is true, attributes are saved in the format
    object.attribute and a lack of selection or an entire object selected will
    expand to that object's keyable nodes.

    Otherwise, the list will be a mix of object.attribute and object.  Objects
    will not have their attributes expanded.
    '''

    selection = []

    # Check for curves first, we may use those exclusively
    if useSelectedCurves:
        selection = getSelectedCurves(usePartialCurveSelection=usePartialCurveSelection)

        if selection:
            return selection

    # Get the graph outliner ui name.
    outliner = getEditorFromPanel(graphInfo.panelName, cmd.outlinerEditor)

    if outliner is not None:
        # Find attributes selected in the graph editor's outliner
        sc = cmd.outlinerEditor(outliner, q=1, selectionConnection=1)
        selection = cmd.selectionConnection(sc, q=1, object=1)

        # If nothing is selected, find objects present in outliner.
        if not selection:
            sc = cmd.outlinerEditor(outliner, q=1, mainListConnection=1)
            selection = cmd.selectionConnection(sc, q=1, object=1)

        if not selection:
            selection = []

    attributes = []
    if selection:
        # This is rare, but eliminate underworld paths.
        removeUnderworldFromPath(selection)
        attributes = filterSelectedToAttributes(selection, expandObjects, animatableOnly)

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

    channelBoxVisible = isChannelBoxVisible()
    selected = False
    if channelBoxVisible:
        # Find what's selected (if anything) in the channelBox
        channelAttributes = ['sma', 'ssa', 'sha', 'soa']
        channelObjects = ['mol', 'sol', 'hol', 'ool']

        foundObjs = []
        channelBox = pm.melGlobals['gChannelBoxName']
        for objArea, attrArea in zip(channelObjects, channelAttributes):
            foundAttrs = cmd.channelBox(channelBox, query=1, **{attrArea: True}) or []
            foundObjs = cmd.channelBox(channelBox, query=1, **{objArea: True}) or []

            # Something was selected
            if foundObjs and foundAttrs:
                for obj in foundObjs:
                    # Find keyable attributes to filter.
                    if animatableOnly:
                        keyableAttrs = getAnimatableAttributes(obj)

                    for attr in foundAttrs:
                        # Make sure the attribute isn't something
                        # incredibly weird that will fail later.
                        try:
                            attr = homogonizeName('%s.%s' % (obj, attr))
                        except RuntimeError:
                            continue

                        # Filter only keyable objects if necessary.
                        selected = True
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
        attributes.extend(filterSelectedToAttributes(objects, expandObjects, animatableOnly))

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

    if outAttr is None:
        outAttr = not inAttr
    else:
        inAttr = not outAttr

    try:
        nodes = cmd.listConnections('%s.%s' % (node, attribute), d=outAttr, s=inAttr, scn=1, p=findAttribute)
        if nodes:
            return nodes[0]
    except RuntimeError:
        raise AttributeError('%s has no attribute %s' % (node, attribute))


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
def selectionConnectionFromPanel(panel):
    '''A more robust way of determining the selection connection of a graph
    editor given its panel Returns None if nothing is found.'''

    outliner = getEditorFromPanel(panel, cmd.outlinerEditor)

    if outliner is not None:
        return cmd.outlinerEditor(outliner, q=1, selectionConnection=1)
    return None


@printCalled
def getSelectedCurves(usePartialCurveSelection=True):
    '''
    Returns a list of all curves that are completely selected.

    usePartialCurveSelection: Curves are returned if any part of a curve
    is selected (tangent, key, or whole curve)
    '''
    selection = []

    # First see if there are any curves selected
    curves = cmd.keyframe(q=1, name=1, sl=1) or []

    def isEntireCurveSelected(curve):
        # Find out if the entire curve is selected, based on keyframe count.
        totalKeyframes = cmd.keyframe(curve, q=1, keyframeCount=1)
        selectedKeyframes = cmd.keyframe(curve, q=1, keyframeCount=1, sl=1)
        return totalKeyframes == selectedKeyframes

    for curve in curves:
        if usePartialCurveSelection or isEntireCurveSelected(curve):
            try:
                # Trace the output of  the curve to find the attribute.
                attr = getFirstConnection(curve, 'output', outAttr=1, findAttribute=1)
                selection.append(attr)
            except AttributeError:
                pass
        else:
            # Short circuit the whole loop.  If there's ever any
            # selection that is NOT an entire curve, then NOTHING is
            # returned.  Without this, other functions may operate
            # only on curves, but ignore other selected keys, which
            # is not desirable when usePartialCurveSelection is false.
            return []
    return selection


@printCalled
def wereSelectedCurvesUsed(detectionType='cursor', useSelectedCurves=True, usePartialCurveSelection=True):
    '''Returns true if selected curves took precedence while obtaining
    attributes'''

    if useSelectedCurves:
        if detectionType == 'cursor':
            graphEditor = GraphEditorInfo.detect(restrictToCursor=True)
        elif detectionType == 'panel':
            graphEditor = GraphEditorInfo.detect(restrictToVisible=True)
        else:
            raise ValueError('%s is not a valid detection type.  Use "cursor" or "panel"' % detectionType)

        if graphEditor.isValid():
            if getSelectedCurves(usePartialCurveSelection=usePartialCurveSelection):
                return True
    return False


@printCalled
def isChannelBoxVisible():
    '''
    Returns if the channelBox is visible to the user (the user does not have
    another control docked in front of it).
    '''
    channelBox = pm.melGlobals['gChannelBoxName']
    # Test if QT version exists:
    if not mel.eval('catchQuiet(`isChannelBoxRaised`)'):
        # Undocumented mel proc in setChannelBoxVisible.mel included in 2011+
        # Roughly traces channelBox by name until its dockControl is found, and queries that.
        return mel.eval('isChannelBoxRaised()')
    else:
        # This command has the same functionality as isChannelBoxRaised, UNTIL QT was introduced.
        return not cmd.channelBox(channelBox, q=1, io=1)


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
