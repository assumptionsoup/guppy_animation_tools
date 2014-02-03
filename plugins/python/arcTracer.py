'''Arc Tracer is a script/plugin combo to visually display animation arcs.

This module is the plugin portion.  It is basically a read-only node, all the
information that is drawn here is gathered from the script.

This node has a compound attribute position which holdes the tx, ty,tz, and
frame that the traced object goes through.  It also stores the last frame that
attributes were set on it to determine which colors to use on the arc in the
lastFrame attribute.

When it is deleted it will delete any objects connected to the traceObj
attribute if follicle is set to 1.  It will also delete any expression
which updateOnPosition is connected to.

When it is renamed it will edit the expression connected to the attribute
updateOnPosition to reflect that name change.  The update is very greedy
and it's not recommended to connect updateOnPosition to any other
expression.

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
''''''
    Author:........Jordan Hueckstaedt
    Website:.......RubberGuppy.com
    Email:.........AssumptionSoup@gmail.com

****************************************************************************'''

__author__ = 'Jordan Hueckstaedt'
__copyright__ = 'Copyright 2012-2014'
__license__ = 'LGPL v3'
__version__ = '0.5'
__email__ = 'AssumptionSoup@gmail.com'
__status__ = 'Beta'

import sys
import maya.OpenMaya as om
import maya.OpenMayaMPx as omMPx
import maya.OpenMayaAnim as omAnim
import maya.OpenMayaRender as omRender
import maya.OpenMayaUI as omui
from math import tan, cos, acos, sin, sqrt, pi
from copy import copy

# Define constants
NODENAME = "arcTracer"

# ID not obtained from Autodesk.  Please let me know if it conflicts
# with a legitimate ID.
NODEID = om.MTypeId(0x87080)

GLFT = omRender.MHardwareRenderer.theRenderer().glFunctionTable()

BLUE = (0.2, 0.6, 1)
RED = (1, 0.1, 0.35)
GREEN = (0.1, 0.9, 0.3)
YELLOW = (1, 1, 0)
ORANGE = (1, .5, .25)


class ArcNode(omMPx.MPxLocatorNode):
    # This scripted node creates a locator which traces an object's
    # position in time.

    # Node attributes
    pastFrames = om.MObject()
    futureFrames = om.MObject()
    minSubframes = om.MObject()
    maxSubframes = om.MObject()

    showArc = om.MObject()
    overlayArc = om.MObject()
    showFrameMarkers = om.MObject()
    showFrameNumbers = om.MObject()
    frameMarkerSize = om.MObject()
    frameMarkersScaleToCamera = om.MObject()
    updateOnPlayback = om.MObject()
    refreshMode = om.MObject()

    position = om.MObject()
    translateX = om.MObject()
    translateY = om.MObject()
    translateZ = om.MObject()
    frame = om.MObject()

    fColor = om.MObject()
    cColor = om.MObject()
    pColor = om.MObject()

    traceObj = om.MObject()
    lastFrame = om.MObject()
    moduleName = om.MObject()
    traceVertex = om.MObject()
    follicle = om.MObject()

    def __init__(self):
        omMPx.MPxLocatorNode.__init__(self)

    def excludeAsLocator(self):
        # Don't hide arcTracers with locators, even though it inherits
        # from the locator node
        return False

    def isTransparent(self):
        # I think something was supposed to be a bit transparent...?
        # maybe?
        return True

    def drawLast(self):
        # Important for overlay function.
        return True

    def printMatrixPointer(self, matrix):
        # Helper function for printing out matrix pointer objects while
        # debugging
        su = om.MScriptUtil()
        for x in range(4):
            for y in range(4):
                print "%s " % round(su.getFloatArrayItem(matrix, x * 4 + y), 5),
            print ""

    def printMatrix(self, matrix):
        # Helper function for printing out matricies while debugging
        for x in range(4):
            for y in range(4):
                print "%s " % matrix(x, y),
            print ""

    def matrixRowVector(self, matrix, row):
        # Returns given matrix row as an om.MVector
        return om.MVector(matrix(row, 0), matrix(row, 1), matrix(row, 2))

    def billboard(self, camMatrix, curPos):
        '''Sets up the gl matrix such that an object created at curPos will
        face camMatrix. curPos should be a list.'''

        # Get initial MVectors
        camPos = self.matrixRowVector(camMatrix, 3)
        curPos = om.MVector(*curPos)

        aimProj = om.MVector(camPos.x - curPos.x, 0, camPos.z - curPos.z)
        aimProj.normalize()

        look = om.MVector(0, 0, 1)
        look.normalize()
        up = look ^ aimProj
        angle = look * aimProj
        if angle < 1 and angle > -1:
            GLFT.glRotatef(acos(angle) * 180 / pi, up.x, up.y, up.z)

        aim = camPos - curPos
        aim.normalize()
        up = om.MVector(0, 0, 0)

        angle = aimProj * aim
        if angle < 1 and angle > -1:
            if aim[1] < 0:
                GLFT.glRotatef(acos(angle) * 180 / pi, 1, 0, 0)
            else:
                GLFT.glRotatef(acos(angle) * 180 / pi, -1, 0, 0)

    def setColor(self, color, intensity=1):
        # A wrapper to unpack (*color, intensity) into glColor4f
        if color and len(color) >= 3:
            GLFT.glColor4f(color[0], color[1], color[2], intensity)

    def getPositions(self, compound, children):
        plug = om.MPlug(self.thisMObject(), compound)
        positions = []
        indexes = om.MIntArray()
        try:
            plug.getExistingArrayAttributeIndices(indexes)
        except:
            print "Failed to get position indexes"

        for e in indexes:
            try:
                xyz = []
                for child in children:
                    plugElement = plug.elementByLogicalIndex(e)
                    xyz.append(plugElement.child(child).asDouble())
                positions.append(xyz)
            except:
                print "Falied to get outputValue on index", index
        return positions


    def draw(self, view, path, style, status):
        # Retrieve data.
        positions = self.getPositions(self.position, [self.translateX, self.translateY, self.translateZ, self.frame])
        frames = [pos.pop(-1) for pos in positions]

        try:
            showArc = om.MPlug(self.thisMObject(), self.showArc).asBool()
        except:
            print "Failed to get showArc"

        try:
            overlayArc = om.MPlug(self.thisMObject(), self.overlayArc).asBool()
        except:
            print "Failed to get overlayArc"

        try:
            currentFrame = om.MPlug(self.thisMObject(), self.lastFrame).asDouble()
        except:
            print "Failed to get lastFrame"

        try:
            showFrameMarkers = om.MPlug(self.thisMObject(), self.showFrameMarkers).asBool()
        except:
            print "Falied to get showFrameMarkers value"

        try:
            showFrameNumbers = om.MPlug(self.thisMObject(), self.showFrameNumbers).asBool()
        except:
            print "Falied to get showFrameMarkers value"

        try:
            scaleToCamera = om.MPlug(self.thisMObject(), self.frameMarkersScaleToCamera).asBool()
        except:
            print "Failed to get frameMarkersScaleToCamera value"

        try:
            frameMarkerSize = om.MPlug(self.thisMObject(), self.frameMarkerSize).asDouble()
        except:
            print "Failed to get frameMarkerSize value"


        camera = om.MDagPath()
        view.getCamera(camera)
        camMatrix = camera.inclusiveMatrix()
        cameraObj = camera.node()
        cameraDg = om.MFnDependencyNode(cameraObj)

        # Determine if camera is orthographic and its width if it is
        # this is needed because orthographic cameras do not actually
        # zoom by moving in space.
        cameraWidth = None
        if scaleToCamera:
            try:
                hasOrtho = cameraDg.hasAttribute('orthographic') and cameraDg.hasAttribute('orthographicWidth')
            except:
                print "Could not determine camera's orthographic state"

            if hasOrtho:
                try:
                    isOrthographic = om.MPlug(cameraObj, cameraDg.attribute('orthographic')).asBool()
                except:
                    print "Could not access camera's orthographic attribute"
                if isOrthographic:
                    try:
                        cameraWidth = om.MPlug(cameraObj, cameraDg.attribute('orthographicWidth')).asDouble()
                    except:
                        print "Could not access camera's orthographic width"


        # Begin drawing
        view.beginGL()
        blendSet = GLFT.glIsEnabled(omRender.MGL_BLEND)
        GLFT.glEnable(omRender.MGL_BLEND)
        if overlayArc:
            # Save initial depth func settings so we can restore them
            # later.
            initialDepthFuncMS = om.MScriptUtil()
            initialDepthFunc = initialDepthFuncMS.asIntPtr()
            GLFT.glGetIntegerv(omRender.MGL_DEPTH_FUNC, initialDepthFunc)

            # Always draw on top..and keep depth information (not sure
            # what that means)
            GLFT.glDepthFunc(omRender.MGL_ALWAYS)

            # Originally did this, but it fails with image planes.
            # GLFT.glDisable(omRender.MGL_DEPTH_TEST)
        GLFT.glPushMatrix()

        fColor = self.getColor(self.fColor)
        pColor = self.getColor(self.pColor)
        cColor = self.getColor(self.cColor)
        if showArc and len(positions) > 2:
            self.drawCurve(positions, frames, currentFrame, pColor, fColor)
        if showFrameMarkers or showFrameNumbers:
            self.drawFrameMarkers(view, scaleToCamera, cameraWidth, camMatrix, positions, frames, currentFrame, pColor, cColor, fColor, showFrameMarkers, showFrameNumbers, frameMarkerSize)

        if overlayArc:
            # Restore original depth testing.
            GLFT.glDepthFunc(om.MScriptUtil.getInt(initialDepthFunc))

        if not blendSet:
            GLFT.glDisable(omRender.MGL_BLEND)
        GLFT.glPopMatrix()
        view.endGL()

    def drawFrameMarkers(self, view, scaleToCamera, cameraWidth, camMatrix, positions, frames, currentFrame, pColor, cColor, fColor, showFrameMarkers, showFrameNumbers, frameMarkerSize):
        GLFT.glLineWidth(2.0)
        markerColor = pColor
        frameColor = YELLOW

        for x, pos in enumerate(positions):
            if not frames[x] % 1:
                # Set current color, if frame is current frame.
                if frames[x] == currentFrame:
                    markerColor = cColor
                    frameColor = ORANGE

                # Set future colors
                if frames[x] > currentFrame:
                    markerColor = fColor
                    frameColor = YELLOW

                # Create markers/numbers
                if showFrameMarkers:
                    self.drawFrameMarker(scaleToCamera, cameraWidth, camMatrix, pos, markerColor, frameMarkerSize)
                if showFrameNumbers:
                    self.setColor(frameColor, 0.8)
                    view.drawText(int(frames[x]), om.MPoint(*pos), omui.M3dView.kCenter)

        GLFT.glLineWidth(1.0)

    def drawFrameMarker(self, scaleToCamera, cameraWidth, camMatrix, pos, color, size):
        GLFT.glPushMatrix()

        # Move into position
        GLFT.glTranslatef(*pos)

        # rotates matrix to aim at camera
        self.billboard(camMatrix, pos)

        # Orthographic vs perspective camera distance.
        if scaleToCamera:
            if cameraWidth:
                cameraDistance = cameraWidth
            else:
                cameraDistance = om.MPoint(self.matrixRowVector(camMatrix, 3)).distanceTo(om.MPoint(*pos))
        else:
            cameraDistance = 20.0

        # Create wonderful circles!
        # print cameraDistance
        self.setColor(color, 0.3)
        self.drawCircle(omRender.MGL_POLYGON, 0, 0, 0, .005 * cameraDistance * size, 20)
        self.setColor(color, 0.8)
        self.drawCircle(omRender.MGL_LINE_LOOP, 0, 0, .01, .005 * cameraDistance * size, 20)

        GLFT.glPopMatrix()

    def drawCircle(self, type, cx, cy, cz, r, num_segments):
        '''A fast draw circle method that only computes cosine and sine once
        Taken from: http://slabode.exofire.net/circle_draw.shtml
        '''
        theta = 2 * pi / num_segments
        c = cos(theta)  # calculate the tangential factor
        s = sin(theta)  # calculate the radial factor

        x = r  # we start at angle = 0
        y = 0

        GLFT.glBegin(type)
        for i in xrange(num_segments):
            GLFT.glVertex3f(x + cx, y + cy, cz)  # output vertex
            t = x
            x = c * x - s * y
            y = s * t + c * y
        GLFT.glEnd()

    def drawCircleNormal(self, type, segments):
        '''Draws a circle using a basic algorithm.  Use drawCircle instead,
        it's faster'''
        GLFT.glBegin(type)
        for i in xrange(segments):
            angle = i * 2 * pi / segments
            GLFT.glVertex2f(cos(angle), sin(angle))
        GLFT.glEnd()

    def getColor(self, color):
        '''Retrieves the given color MObject from a color plug and returns the
        float values as a list'''
        colorPlug = om.MPlug(self.thisMObject(), color)
        color = []
        for c in xrange(colorPlug.numChildren()):
            try:
                color.append(colorPlug.child(c).asFloat())
            except:
                print "Could not get color plug, ", colorPlug.name()
        return color

    def drawCurve(self, positions, frames, currentFrame, pColor, fColor):
        '''Draws a line with points on the pre-sorted given positions The line
        starts in pColor and when frames are greater than current frame it
        switches to fColor'''

        GLFT.glLineWidth(3.0)
        GLFT.glBegin(omRender.MGL_LINES)

        self.setColor(pColor)

        for x in xrange(1, len(positions)):
            if frames[x] > currentFrame:
                self.setColor(fColor)
            GLFT.glVertex3f(*positions[x - 1])
            GLFT.glVertex3f(*positions[x])

        GLFT.glEnd()
        GLFT.glLineWidth(1.0)

    def postConstructor(self):
        # Set node so it is named properly.  Aka  ArcNode|ArcNodeShape1
        dpNode = om.MFnDependencyNode(self.thisMObject())
        dpNode.setName('arcTracerShape#')

        # Add delete callback that will delete any associated
        # expressions with the arc tracer
        try:
            self.aboutToDeleteID = om.MNodeMessage.addNodeAboutToDeleteCallback(self.thisMObject(), self.aboutToDelete, None)
        except:
            print "Could not create aboutToDelete callback"

        try:
            self.nameChangedID = om.MNodeMessage.addNameChangedCallback(self.thisMObject(), self.nameChanged, None)
        except:
            print "Could not create nameChanged callback"

    def nameChanged(self, node, previousName, clientData):
        # Find any connected expressions and update node name in it. I'm
        # sure this needs more try's somewhere.  Not really sure where.
        # For that matter, I'm not really sure what good putting the
        # try's in at all is. Most of the time when something goes
        # wrong, maya just crashes anyway.

        # Find expressions.
        dpNode = om.MFnDependencyNode(self.thisMObject())
        plug = om.MPlug(self.thisMObject(), self.updateOnPlayback)
        plugs = om.MPlugArray()
        plug.connectedTo(plugs, 0, 1)

        for p in xrange(plugs.length()):
            # update expressions.
            node = plugs[p].node()

            # I figured this if statement out by myself from the
            # documenation alone.  Didn't even need an example. I feel
            # special.  It's probably not doing what I think it's doing.
            if node.hasFn(om.MFn.kExpression):
                expNode = om.MFnExpression(node)
                expContent = expNode.expression()
                expContent = expContent.replace("'%s'" % previousName, "'%s'" % dpNode.name())
                try:
                    expNode.setExpression(expContent)
                except Exception as e:
                    print "Could not set new expression"
                    print expContent
                    print e

    def deleteConnected(self, fromPlug, nodeType, dgModifier, inAttr=1, outAttr=None):
        '''Delete node connected to fromPlug of nodeType.  If nodeType is None,
        it will be deleted regardless of type.'''

        if outAttr == None:
            outAttr = not inAttr
        else:
            inAttr = not outAttr

        plug = om.MPlug(self.thisMObject(), fromPlug)
        plugs = om.MPlugArray()
        plug.connectedTo(plugs, inAttr, outAttr)

        for p in xrange(plugs.length()):
            node = plugs[p].node()
            if not nodeType or node.hasFn(nodeType):
                dgModifier.deleteNode(node)

    def aboutToDelete(self, node, dgModifier, clientData):
        # Clean up other objects that may be attached to the arcTracer
        # Remove any associated expressions.
        self.deleteConnected(self.updateOnPlayback, om.MFn.kExpression, dgModifier, outAttr=1)

        # Delete any follicles the arcTracer may be following
        if om.MPlug(self.thisMObject(), self.follicle).asBool():
            self.deleteConnected(self.traceObj, None, dgModifier, inAttr=1)

        try:
            dgModifier.doIt()
        except:
            print "Failed to do it."

        # I assume these removeCallback functions are needed to clean
        # things up However, if I call them, the callbacks don't get
        # reinstated on redos So I'm leaving them out and hoping maya is
        # smart enough to clean up its own garbage.  I have my doubts
        # though...
        '''
        try:
            om.MMessage.removeCallback(self.aboutToDeleteID)
        except:
            print "Failed to remove aboutToDelete callback"

        try:
            om.MMessage.removeCallback(self.nameChangedID)
        except:
            print "Failed to remove nameChanged callback"
        '''


def nodeCreator():
    return omMPx.asMPxPtr(ArcNode())


def nodeInitializer():
    cAttr = om.MFnCompoundAttribute()
    numAttr = om.MFnNumericAttribute()
    uAttr = om.MFnUnitAttribute()

    ArcNode.pastFrames = numAttr.create('pastFrames', 'pastFrames', om.MFnNumericData.kInt, 4)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setMin(0)
    numAttr.setChannelBox(1)

    ArcNode.futureFrames = numAttr.create('futureFrames', 'futureFrames', om.MFnNumericData.kInt, 4)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setMin(0)
    numAttr.setChannelBox(1)

    ArcNode.minSubframes = numAttr.create('minSubframes', 'minSubframes', om.MFnNumericData.kInt, 0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setMin(0)
    numAttr.setChannelBox(1)

    ArcNode.maxSubframes = numAttr.create('maxSubframes', 'maxSubframes', om.MFnNumericData.kInt, 0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setMin(0)
    numAttr.setChannelBox(1)

    ArcNode.showArc = numAttr.create('showArc', 'showArc', om.MFnNumericData.kBoolean, 1.0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setChannelBox(1)

    ArcNode.overlayArc = numAttr.create('overlayArc', 'overlayArc', om.MFnNumericData.kBoolean, 1.0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setChannelBox(1)

    ArcNode.showFrameNumbers = numAttr.create('showFrameNumbers', 'sfn', om.MFnNumericData.kBoolean, 0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setKeyable(1)

    ArcNode.showFrameMarkers = numAttr.create('showFrameMarkers', 'sfm', om.MFnNumericData.kBoolean, 1)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setKeyable(1)

    ArcNode.frameMarkersScaleToCamera = numAttr.create('frameMarkersScaleToCamera', 'fmc', om.MFnNumericData.kBoolean, 1)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setKeyable(1)

    ArcNode.frameMarkerSize = numAttr.create('frameMarkerSize', 'fms', om.MFnNumericData.kDouble, 1.0)
    numAttr.setMin(0.001)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setKeyable(1)

    ArcNode.updateOnPlayback = numAttr.create('updateOnPlayback', 'uop', om.MFnNumericData.kBoolean, 1)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setChannelBox(1)

    ArcNode.refreshMode = numAttr.create('useRefreshMode', 'ufm', om.MFnNumericData.kBoolean, 0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setChannelBox(1)

    ArcNode.fColor = numAttr.createColor('futureColor', 'fcl')
    numAttr.setDefault(*BLUE)
    numAttr.setHidden(1)  # Colors cobble up the channel editor.  They'll be added back in the attribute editor with the aetemplate.
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setKeyable(1)
    numAttr.setUsedAsColor(1)

    ArcNode.pColor = numAttr.createColor('pastColor', 'pcl')
    numAttr.setDefault(*RED)
    numAttr.setHidden(1)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setKeyable(1)
    numAttr.setUsedAsColor(1)

    ArcNode.cColor = numAttr.createColor('currentColor', 'ccl')
    numAttr.setDefault(*GREEN)
    numAttr.setHidden(1)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setKeyable(1)
    numAttr.setUsedAsColor(1)

    ArcNode.translateX = numAttr.create('tanslateX', 'tx', om.MFnNumericData.kDouble, 0.0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)

    ArcNode.translateY = numAttr.create('translateY', 'ty', om.MFnNumericData.kDouble, 0.0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)

    ArcNode.translateZ = numAttr.create('translateZ', 'tz', om.MFnNumericData.kDouble, 0.0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)

    ArcNode.frame = numAttr.create('frame', 'fr', om.MFnNumericData.kDouble, 0.0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)

    ArcNode.position = cAttr.create("position", "pos")
    # cAttr.setHidden(1)
    cAttr.setArray(1)
    cAttr.setUsesArrayDataBuilder(1)
    cAttr.addChild(ArcNode.translateX)
    cAttr.addChild(ArcNode.translateY)
    cAttr.addChild(ArcNode.translateZ)
    cAttr.addChild(ArcNode.frame)

    # These are not meant to be touched by the user.
    messAttr = om.MFnMessageAttribute()
    ArcNode.traceObj = messAttr.create('traceObj', 'traceObj')

    ArcNode.lastFrame = numAttr.create('lastFrame', 'lastFrame', om.MFnNumericData.kDouble, 0.0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)
    numAttr.setHidden(1)

    tAttr = om.MFnTypedAttribute()
    defaultString = om.MFnStringData().create('')
    ArcNode.moduleName = tAttr.create("moduleName", "moduleName", om.MFnData.kString, defaultString)
    tAttr.setStorable(1)
    tAttr.setKeyable(0)

    ArcNode.traceVertex = numAttr.create('traceVertex', 'traceVertex', om.MFnNumericData.kInt, -1)
    numAttr.setStorable(1)
    numAttr.setWritable(1)

    ArcNode.follicle = numAttr.create('follicle', 'follicle', om.MFnNumericData.kBoolean, 0)
    numAttr.setStorable(1)
    numAttr.setWritable(1)

    addAttr(ArcNode.pastFrames, 'pastFrames')
    addAttr(ArcNode.futureFrames, 'futureFrames')
    addAttr(ArcNode.minSubframes, 'minSubframes')
    addAttr(ArcNode.maxSubframes, 'maxSubframes')
    addAttr(ArcNode.showArc, 'showArc')
    addAttr(ArcNode.overlayArc, 'overlayArc')
    addAttr(ArcNode.showFrameMarkers, 'showFrameMarkers')
    addAttr(ArcNode.showFrameNumbers, 'showFrameNumbers')
    addAttr(ArcNode.frameMarkerSize, 'frameMarkerSize')
    addAttr(ArcNode.frameMarkersScaleToCamera, 'frameMarkersScaleToCamera')
    addAttr(ArcNode.updateOnPlayback, 'updateOnPlayback')
    addAttr(ArcNode.refreshMode, 'refreshMode')
    addAttr(ArcNode.pColor, 'pColor')
    addAttr(ArcNode.cColor, 'cColor')
    addAttr(ArcNode.fColor, 'fColor')
    addAttr(ArcNode.position, 'position')
    addAttr(ArcNode.traceObj, 'traceObj')
    addAttr(ArcNode.lastFrame, 'lastFrame')
    addAttr(ArcNode.moduleName, 'moduleName')
    addAttr(ArcNode.traceVertex, 'traceVertex')
    addAttr(ArcNode.follicle, 'follicle')

    return om.MStatus.kSuccess


def addAttr(attr, name):
    try:
        ArcNode.addAttribute(attr)
    except:
        sys.stderr.write("Failed to add %s attribute %s." % (attr.apiTypeStr(), name))
        raise


def initializePlugin(obj):
    plugin = omMPx.MFnPlugin(obj)
    try:
        plugin.registerNode(NODENAME, NODEID, nodeCreator, nodeInitializer, omMPx.MPxNode.kLocatorNode)
    except:
        sys.stderr.write("Failed to register node: %s" % NODENAME)


def uninitializePlugin(obj):
    plugin = omMPx.MFnPlugin(obj)
    try:
        plugin.deregisterNode(NODEID)
    except Exception as err:
        sys.stderr.write("Failed to deregister node: %s\n%s" % (NODENAME, err))
