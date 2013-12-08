'''Arc Tracer is a script/plugin combo to visually display animation arcs.

This module is the script portion.  This script is the brains of the operation.
The plugin merely displays information gathered here.

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

****************************************************************************'''

__author__ = 'Jordan Hueckstaedt'
__copyright__ = 'Copyright 2012'
__license__ = 'LGPL v3'
__version__ = '0.5'
__email__ = 'AssumptionSoup@gmail.com'
__status__ = 'Beta'
__date__ = '8-24-2012'

import maya.cmds as cmd
import maya.mel as mel
import maya.OpenMayaUI as omui
import maya.OpenMaya as om
import textwrap
import inspect
import collections
from math import cos, sqrt
from operator import attrgetter
from functools import partial

# pointOnMesh should be bundled with arcTracer, but it's only
# Really needed for tracing a point on the mesh (atPoint() and getPoint())
# So we'll just warn the user in those functions if pointOnMesh
# wasn't installed.  The whole class was also a bit of a failure,
# since it runs so slowly.
try:
    import pointOnMesh
except:
    pointOnMesh = None
CONTEXTNAME = 'arcTracerCtx'

'''
import time
average = []
def print_timing(func):
	def wrapper(*arg):
		t1 = time.clock()
		res = func(*arg)
		t2 = time.clock()
		#global average
		#average.append((t2-t1)*1000.0)
		print '%s took %0.3f ms' % (func.func_name, (t2-t1)*1000.0)
		return res
	return wrapper
'''
# use decorator: @print_timing before a function to attach print_timing to it
# Add this somewhere after the function executed to print out the average time it took to execute that function.
# global average
# print 'Average getpoint took', round(sum(average) / float(len(average)), 4)


def pluginLoaded():
    if not cmd.pluginInfo('arcTracer', query=1, l=1):
        try:
            cmd.loadPlugin('arcTracer.py')
        except:
            om.MGlobal.displayError("Arc Tracer plugin not found.  Make sure it is installed or loaded before running this command")
            return False
    return True


def create(traceObj=None, settings=None, follicle=False):
    '''Creates an arc tracer on the given/selected object with the given settings.
    Use the getShortcut() function to obtain create an arc tracer with settings other
    than the default.'''
    # Test for plugin.
    if not pluginLoaded():
        return

    # Get selected object if one isn't given
    if not traceObj:
        selected = cmd.ls(sl=1)
        if selected:
            traceObj = selected[0]

    # Test for object
    if not traceObj:
        om.MGlobal.displayError('You must select an object to trace')
        return
    elif not cmd.objExists(traceObj):
        om.MGlobal.displayError('%s does not exist.' % traceObj)
        return

    # Create the node
    arcTracer = cmd.createNode('arcTracer')

    # Set module name
    mName = "__import__('sys').modules['%s']." % __name__

    # Add needed attributes
    cmd.setAttr('%s.moduleName' % arcTracer, mName, type='string')

    # Connect things up
    cmd.connectAttr('%s.%s' % (traceObj, 'message'), '%s.%s' % (arcTracer, 'traceObj'), f=1)

    # Flag if trace object is a follicle, so the arcTracer node can delete it later.
    if follicle:
        cmd.setAttr('%s.follicle' % arcTracer, 1)

    # Hide locator stuff no one wants to look at.
    axes = ('X', 'Y', 'Z')
    for attribute in ('localPosition', 'localScale'):
        for axis in axes:
            cmd.setAttr('%s.%s%s' % (arcTracer, attribute, axis), cb=0)


    # Apply settings if they were given
    if settings:
        for attr, value in settings.iteritems():
            if isinstance(settings[attr], collections.Iterable):
                cmd.setAttr('%s.%s' % (arcTracer, attr), *settings[attr])
            else:
                cmd.setAttr('%s.%s' % (arcTracer, attr), settings[attr])

    # Initialize the values.
    update(arcTracer, forceUpdate=True)

    # Setup on-frame change expression.
    # Update on frame change.
    # Adds expression option to limit updates based on playback status (hitting the play key)
    onlyUpdateOnPlayback = 0
    onlyUpdateOnFrameChange = 0
    updateOnPlayback = ''
    if onlyUpdateOnPlayback:
        updateOnPlayback = '`play -q -st` == 1 && '  # Note that it will not update on playblasts if this is enabled.
    elif onlyUpdateOnFrameChange:
        updateOnPlayback = '`play -q -st` == 0 && '

    expressionName = 'arcTracerExpression1'
    expressionCommand = textwrap.dedent(
        '''
						//Do not remove the following line or the arcTracer will no longer delete this expression when it is deleted.
						//Any other expression that makes a connection from updateOnPlayback will also be deleted
						//when the arcTracer is deleted.
						$update = {0}.updateOnPlayback;
						if ($update && {1} {0}.lastFrame != frame && !{0}.useRefreshMode)
							python("{2}update('{0}')");
						'''.format(arcTracer, updateOnPlayback, mName))
    expressionName = cmd.expression(n=expressionName, o=arcTracer, s=expressionCommand)


def getShortcut(arcTracer=None):
    '''Prints out the command needed to generate an arc tracer
    with the same settings as the selected or passed arc tracer object'''

    if not arcTracer:
        selected = cmd.ls(sl=1)
        if selected:
            arcTracer = selected[0]

    # Test for object
    if not arcTracer:
        om.MGlobal.displayError('You must select an arc tracer to set get a shortcut for one.')
        return
    elif not cmd.objExists(arcTracer):
        om.MGlobal.displayError('%s does not exist.' % arcTracer)
        return

    # Make sure an arc tracer is selected
    shapes = cmd.listRelatives(arcTracer, s=1)
    if shapes:
        for shape in shapes:
            type = cmd.ls(shape, st=1)[-1]
            if 'arcTracer' == type:
                arcTracer = shape

    type = cmd.ls(arcTracer, st=1)[-1]
    if 'arcTracer' != type:
        om.MGlobal.displayError('%s is not an arc tracer.' % arcTracer)
        return

    # Set module name.  Not nearly as specific as the one used in install(), but I think
    # the user can be smart enough to figure it out and change the output if it's wrong.
    # The one in install() would work here too, but I think it would confuse people with
    # it's extreme verbosity when it may not be needed.
    mName = ''
    if __name__ != '__main__':
        mName = '%s.' % __name__

    # Get attributes that are not the default value.
    settings = {}
    attributes = '''pastFrames futureFrames minSubframes maxSubframes showArc overlayArc
	showFrameNumbers showFrameMarkers frameMarkersScaleToCamera frameMarkerSize
	updateOnPlayback useRefreshMode pastColor currentColor futureColor'''.split()
    for attr in attributes:
        # Gotta love how Autodesk makes us jump through hoops here for no reason.
        value = cmd.getAttr('%s.%s' % (arcTracer, attr))
        default = tuple(cmd.attributeQuery(attr, n=arcTracer, listDefault=1))
        if isinstance(value, collections.Iterable):
            value = value[0]
        else:
            default = default[0]
        if value != default:
            settings[attr] = value

    # Format settings into a string
    # settings = ', '.join('%s = %s' % (k,v) for k, v in settings.iteritems())
    om.MGlobal.displayInfo('%screate(settings = %s)' % (mName, settings))


def debug():
    width = 25
    arcTracers = cmd.ls(type='arcTracer')
    for arcTracer in arcTracers:
        print 'On %s' % arcTracer
        attributes = '''pastFrames futureFrames minSubframes maxSubframes showArc overlayArc
		showFrameNumbers showFrameMarkers frameMarkersScaleToCamera frameMarkerSize
		updateOnPlayback traceVertex follicle lastFrame'''.split()
        for attr in attributes:
            value = cmd.getAttr('%s.%s' % (arcTracer, attr))
            print '{0}: {1:>{2}}'.format(attr, value, len(attr) - width)
        print 'moduleName:     %s' % cmd.getAttr('%s.moduleName' % arcTracer)
        print 'positions:      %s' % [cmd.getAttr('%s.%s' % (arcTracer, attr)) for attr in cmd.listAttr('%s.position' % arcTracer, multi=1)]
        print 'tracing object: %s' % getFirstConnection('%s.traceObj' % arcTracer, inAttr=1)
        print ''


def getPoint(settings):
    '''The real content of atPoint, this should only be called from the context
    created in atPoint.'''
    # Test for plugin.
    if not pluginLoaded():
        return

    # Get screen position of pointer
    clickPosition = cmd.draggerContext(CONTEXTNAME, q=1, dragPoint=1)
    surfaceData = pointOnMesh.getPoint(clickPosition, createFollicle=0)

    # Limit maxSubframes on creation if they're not already set, because follicles are SLOW
    if not 'maxSubframes' in settings:
        if 'minSubframes' in settings:
            settings['maxSubframes'] = settings['minSubframes']
        else:
            settings['maxSubframes'] = 0

    if surfaceData:
        if surfaceData.u == None or surfaceData.v == None:
            if surfaceData.type == 'mesh':
                om.MGlobal.displayWarning('Falling back to nearest point mode.  Tell Jordan if this worked or not!')
                settings['traceVertex'] = surfaceData.closestVertex
                create(surfaceData.name, settings)
            else:
                om.MGlobal.displayError('Could not create arc on specified mesh.  Could not find UV data')
        elif surfaceData.type == 'nurbsSurface' or surfaceData.type == 'mesh':
            follicle = pointOnMesh.createFollicle(surfaceData, 'arcTracerFollicle')
            if follicle:
                create(follicle, settings, follicle=True)
        else:
            om.MGlobal.displayError('Could not create arc on a %s' % surfaceData.type)


def atPoint(settings=None):
    '''I WOULD NOT RECOMMEND USING THIS.  IT IS SLOW.
    Creates a context in which the user can click on an object in the scene and
    a point will be traced on that mesh, using either a follicle or the nearest
    point on the mesh.  This function takes the same settings dictionary that
    getShortcut creates.'''

    # Test for plugin.
    if not pluginLoaded():
        return

    if not settings:
        settings = {}

    if pointOnMesh:
        if cmd.draggerContext(CONTEXTNAME, q=1, ex=1):
            cmd.deleteUI(CONTEXTNAME)

        # I have found no way to test if an icon exists, other than to just attempt to create
        # something with that icon.
        kwargs = {'releaseCommand': partial(getPoint, settings=settings), 'cursor': 'crossHair', 'image1': 'arcTracerOnMesh.png'}
        try:
            cmd.draggerContext(CONTEXTNAME, **kwargs)
        except RuntimeError:
            kwargs['image1'] = None
            cmd.draggerContext(CONTEXTNAME, **kwargs)
        cmd.setToolTo(CONTEXTNAME)
    else:
        om.MGlobal.displayWarning("Could not find module pointOnMesh.  You must install pointOnMesh to use this functionality.")


def update(arcTracer, forceUpdate=False):
    '''Populates an arcTracer with updated spacial information.'''
    # Get object to trace
    traceObj = getFirstConnection('%s.traceObj' % arcTracer, inAttr=1)

    if not traceObj:
        om.MGlobal.displayError('Trace object for arc tracer %s disappeared!' % arcTracer)
        return

    # Get selection so it can be restored later
    selection = cmd.ls(sl=1)

    # Hide everything but the trace obj in refresh mode
    if cmd.getAttr('%s.useRefreshMode' % arcTracer):
        cmd.select(traceObj)
        panels = cmd.getPanel(typ='modelPanel')
        panelsIsolated = []
        for panel in panels:
            if not cmd.isolateSelect(panel, q=1, state=1):
                cmd.isolateSelect(panel, state=1)
                panelsIsolated.append(panel)

    pastFrames = cmd.getAttr('%s.pastFrames' % arcTracer)
    futureFrames = cmd.getAttr('%s.futureFrames' % arcTracer)

    # Disable cycle check since the update-frame expression causes a cycle (apparently)
    try:
        # Only recent versions of maya can query the cycle check.
        cycleCheck = cmd.cycleCheck(q=1, e=1)
    except:
        cycleCheck = 1
    cmd.cycleCheck(e=0)

    currentFrame = cmd.currentTime(q=1)
    lastFrame = cmd.getAttr('%s.lastFrame' % arcTracer)
    timeShift = abs(lastFrame - currentFrame)
    if timeShift != 0 or forceUpdate:
        frameRange, direction = findFrameRange(pastFrames, futureFrames, currentFrame, lastFrame, timeShift, forceUpdate)
        arcPositions = getSavedArcPositions(arcTracer, timeShift, forceUpdate)

        # Get updated positions
        getUpdatedArcPositions(arcTracer, traceObj, frameRange, currentFrame, direction, arcPositions)

        # Set all positions
        setArcPositions(arcTracer, arcPositions, pastFrames, futureFrames, currentFrame)

        cmd.setAttr('%s.lastFrame' % arcTracer, currentFrame)

    cmd.cycleCheck(e=cycleCheck)

    # Restore isolation
    if cmd.getAttr('%s.useRefreshMode' % arcTracer):
        for panel in panelsIsolated:
            cmd.isolateSelect(panel, state=0)

        # Restore previous selection
        cmd.select(selection)


def findFrameRange(pastFrames, futureFrames, currentFrame, lastFrame, timeShift, forceUpdate):
    # Finds the frame ranges that need to be queried, so that cached data can be skipped over.
    pastRange = currentFrame - pastFrames
    futureRange = currentFrame + futureFrames + 1
    frameRange = [pastRange, futureRange]
    direction = None

    if timeShift and not forceUpdate:
        if lastFrame > currentFrame:
            # moved backwards in the timeline.
            if timeShift <= (pastFrames + futureFrames + 1):
                # Some frames are still cached
                frameRange[1] = pastRange + timeShift
                direction = 'back'
        else:
            # Moved forwards in timeline
            if timeShift <= (pastFrames + futureFrames):
                # Some frames are still cached
                frameRange[0] = futureRange - timeShift
                # frameRange[1] = pastRange
                direction = 'forward'

    frameRange = [int(frameRange[0]), int(frameRange[1])]  # Avoid deprecationWarning.
    return frameRange, direction


class ArcPosition(object):

    def __init__(self, position, time=None):
        self.position = list(position)
        if not time and len(self.position) == 4:
            self.time = self.position.pop(-1)
        else:
            self.time = time

    def allData(self):
        data = self.position[:]
        data.append(self.time)
        return data


def getSavedArcPositions(arcTracer, timeShift, forceUpdate):
    arcPositions = []
    if timeShift != 0 and not forceUpdate:
        for x in range(cmd.getAttr('%s.position' % arcTracer, size=1)):
            pos = cmd.getAttr('%s.position[%s]' % (arcTracer, x))
            if pos and pos[0]:
                arcPositions.append(ArcPosition(pos[0]))
        # arcPositions = sorted(arcPositions, key=attrgetter('time'))
    return arcPositions


def getUpdatedArcPositions(arcTracer, traceObj, frameRange, currentFrame, direction, arcPositions):
    # Get position and mesh data before the loop to optimize things.
    refreshMode = cmd.getAttr('%s.useRefreshMode' % arcTracer)
    traceVertex = cmd.getAttr('%s.traceVertex' % arcTracer)
    mesh = None
    matrixMismatch = False
    if traceVertex > -1:
        # If we're tracing verticies, traceObj will actually be connected to a shape.  Get that shape now.
        shape = getFirstConnection('%s.traceObj' % arcTracer, inAttr=1, findAttribute=1).split('.')[0]

        if refreshMode:
            # Refresh Mode needs a dagPath
            mesh = getDagPath(shape)
        else:
            # Non-refresh mode needs a plug
            mesh = getMeshPlug(shape)
    pivot = cmd.xform(traceObj, q=1, piv=1)

    # Find positions at whole frames.
    updatedPositions = []
    for frame in xrange(*frameRange):
        pos = getPosition(traceObj, frame, traceVertex, pivot=pivot, refreshMode=refreshMode, mesh=mesh)
        if pos:
            updatedPositions.append(ArcPosition(pos))

    # Add whole frame positions to arcPositions.
    if arcPositions:
        lastArcPosition = arcPositions[-1]
    arcPositions.extend(updatedPositions)

    # Find subframe limitations
    minSubframes = cmd.getAttr('%s.minSubframes' % arcTracer)
    maxSubframes = cmd.getAttr('%s.maxSubframes' % arcTracer)

    # Get out of here if the user doesn't want any subframes
    if not maxSubframes:
        if refreshMode:
            cmd.currentTime(currentFrame, u=1)

        return

    # Find last cached keyframed position if it exists
    if direction:
        if direction == 'forward':
            updatedPositions.insert(0, lastArcPosition)
        else:
            updatedPositions.append(arcPositions[0])

    # Initialize variables for loop
    subframePositions = []
    resolution = getResolution(traceObj)
    activeView = omui.M3dView.active3dView()

    # Unfortunately I can't seem to consolidate this to a function without crashing maya.
    # And each MScriptUtil instance must be unique for the pointer to work correctly.  Thanks autodesk!
    xPos1Util = om.MScriptUtil()
    xPos1 = xPos1Util.asShortPtr()
    yPos1Util = om.MScriptUtil()
    yPos1 = yPos1Util.asShortPtr()
    xPos2Util = om.MScriptUtil()
    xPos2 = xPos2Util.asShortPtr()
    yPos2Util = om.MScriptUtil()
    yPos2 = yPos2Util.asShortPtr()

    # Set iterations outside the loop to enhance effeciency if minSubframes == maxSubframes.
    iterations = maxSubframes
    for x in xrange(1, len(updatedPositions)):
        # Attempt to get the screen-space resolution to determine subframe iterations first as it's more accurate
        # If the position is off-screen, switch to the distance based resolution.

        if not minSubframes == maxSubframes:
            arc1 = om.MPoint(*updatedPositions[x].position)
            arc2 = om.MPoint(*updatedPositions[x - 1].position)
            inView1 = activeView.worldToView(arc1, xPos1, yPos1)
            inView2 = activeView.worldToView(arc2, xPos2, yPos2)

            if inView1 and inView2:
                arcPoint1 = [om.MScriptUtil.getShort(xPos1), om.MScriptUtil.getShort(yPos1)]
                arcPoint2 = [om.MScriptUtil.getShort(xPos2), om.MScriptUtil.getShort(yPos2)]
                distance = distanceBetween(arcPoint1, arcPoint2)
                iterations = int(distance / 12)

            else:
                # Find distance traveled in one frame
                distance = distanceBetween(updatedPositions[x].position, updatedPositions[x - 1].position)

                # Find iterations needed and the time increment for that iteration.
                iterations = int(distance / resolution)
            iterations = max(minSubframes, min(maxSubframes, iterations))

        frame1 = updatedPositions[x - 1].time
        increment = 1.0 / (iterations + 1)

        # Set positions
        for i in xrange(iterations):
            pos = getPosition(traceObj, increment * (i + 1) + frame1, traceVertex, pivot=pivot, refreshMode=refreshMode, mesh=mesh)
            if pos:
                subframePositions.append(ArcPosition(pos))

    # Add subframe positions to arcPositions
    arcPositions.extend(subframePositions)

    if refreshMode:
        cmd.currentTime(currentFrame, u=1)


def setArcPositions(arcTracer, arcPositions, pastFrames, futureFrames, currentFrame):
    futureFrames = futureFrames + currentFrame
    pastFrames = currentFrame - pastFrames

    # Sort positions
    arcPositions = sorted(arcPositions, key=attrgetter('time'))

    # Set positions based on time.
    frameCount = 0
    for position in arcPositions:
        if pastFrames <= position.time <= futureFrames:
            cmd.setAttr('%s.position[%s]' % (arcTracer, frameCount), *position.allData())
            frameCount += 1

    # Cleanup extra attributes created due to variable sub-frame iterations.
    numAttrs = cmd.getAttr('%s.position' % arcTracer, size=1)
    if numAttrs - frameCount > 0:
        for x in range(frameCount, numAttrs):
            cmd.removeMultiInstance('%s.position[%s]' % (arcTracer, x))


def getResolution(traceObj):
    # Get view for later
    activeView = omui.M3dView.active3dView()

    # Get camera position and the traced object position as MPoints
    cameraDag = om.MDagPath()
    activeView.getCamera(cameraDag)
    cameraPoint = matrixRowPoint(cameraDag.inclusiveMatrix(), 3)
    traceDag = getDagPath(traceObj)
    tracePoint = matrixRowPoint(traceDag.inclusiveMatrix(), 3)

    # Get the distance from the camera to the trace point on screen
    distance = cameraPoint.distanceTo(tracePoint)

    nearPoint = om.MPoint()  # Won't actually use this.
    farPoint = om.MPoint()

    # Get points on near and far clipping planes in upper left corner of the screen.
    activeView.viewToWorld(0, 0, nearPoint, farPoint)

    # Get the angle between the camera, the trace object and the far clipping plane with the camera as the vertex.
    hyp = om.MVector(farPoint - cameraPoint)
    adj = om.MVector(tracePoint - cameraPoint)
    theta = hyp.angle(adj)

    # Use the distance from the camera and the vector projection equation (solved for the reversed vector)
    # to find a distance which makes the angle between the new point, the trace object and the camera
    # 90 degrees where the trace object is the vertex.
    hyp = adj.length() / cos(theta)
    leftPoint = cameraPoint + ((farPoint - cameraPoint) * (hyp / cameraPoint.distanceTo(farPoint)))
    # cmd.spaceLocator(n = 'leftPoint', p = (leftPoint[0], leftPoint[1], leftPoint[2]))

    # Do the same to the lower right corner
    activeView.viewToWorld(activeView.portWidth(), activeView.portHeight(), nearPoint, farPoint)
    hyp = om.MVector(farPoint - cameraPoint)
    theta = hyp.angle(adj)
    hyp = adj.length() / cos(theta)

    rightPoint = cameraPoint + ((farPoint - cameraPoint) * (hyp / cameraPoint.distanceTo(farPoint)))
    # cmd.spaceLocator(n = 'rightPoint', p = (rightPoint[0], rightPoint[1], rightPoint[2]))

    # Calculate the scale as the distance between the left and right points.
    scale = leftPoint.distanceTo(rightPoint)

    res = scale / 100.0
    return res


def vectorToList(vector):
    # Actually takes vectors or points
    axes = ['x', 'y', 'z']
    if hasattr(vector, 'w'):
        axes.append('w')
    result = []
    for axis in axes:
        result.append(getattr(vector, axis))
    return result


def matrixRowPoint(matrix, row):
    # Returns matrix row as vector
    return om.MPoint(matrix(row, 0), matrix(row, 1), matrix(row, 2))


def distanceBetween(point1, point2):
    if len(point1) == 3:
        return sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2)
    else:
        return sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2)


def getPosition(obj, frame, traceVertex, pivot=None, refreshMode=0, mesh=None, applyPivot=True):
    # Finds the world position of a object at a given time
    # If apply pivot is true, it finds the world position of the pivot. (Important for controllers)
    # If traceVertex is not -1, find the position of that vertex.

    # Get time
    if refreshMode or traceVertex > -1 and mesh:
        # get MTime at given frame
        time = om.MTime()
        time.setValue(frame)

    # Move Maya to time
    if refreshMode:
        om.MGlobal.viewFrame(time)

    # Special method to trace point directly on mesh using API.
    # This method does not require UV's to be present.
    if traceVertex > -1 and mesh:
        point = getPointAtTime(refreshMode, mesh, traceVertex, time)
        return (point[0], point[1], point[2], frame)

    # It seems like some sort of further calculation beyond worldMatrix + pivot
    # is occuring to derive the worldspace of an object.  The xform command
    # preforms this unknown operation correctly, but can't be queried based on
    # time.  Hence, the following, where xform will be used if refresh mode is
    # activated.
    if refreshMode:
        if applyPivot:
            worldMatrix = cmd.xform(obj, q=1, ws=1, piv=1)[:3]
            return worldMatrix + [frame]
        else:
            worldMatrix = cmd.xform(obj, q=1, ws=1, t=1)
    else:
        worldMatrix = cmd.getAttr('%s.worldMatrix' % obj, t=frame)

    pivotIsZero = False
    if worldMatrix and len(worldMatrix) == 16:
        # If there is a pivot, add it to the world matrix
        if applyPivot:
            if not pivot:
                pivot = cmd.xform(obj, q=1, piv=1)
            if pivot:
                # If pivot is not at 0, 0, 0
                if any(round(axis, 10) for axis in pivot):
                    # Add pivot to worldspace matrix using provided API methods.
                    matrix = om.MMatrix()
                    om.MScriptUtil.createMatrixFromList(worldMatrix, matrix)
                    matrix = om.MTransformationMatrix(matrix)
                    matrix.addTranslation(om.MVector(*pivot[:3]), om.MSpace.kObject)
                    tran = matrix.getTranslation(om.MSpace.kWorld)
                    return (tran[0], tran[1], tran[2], frame)
                else:
                    pivotIsZero = True
            else:
                applyPivot = False
        if not applyPivot or pivotIsZero:
            return worldMatrix[-4:-1] + [frame]


def getDagPath(objectName):
    # Get DagPath from object name.
    # put object name into the MObject
    tempList = om.MSelectionList()
    tempList.add(objectName)

    # get the dagpath of the object
    dagpath = om.MDagPath()
    tempList.getDagPath(0, dagpath)
    return dagpath


def getMeshPlug(meshName):
    dagPath = getDagPath(meshName)

    # Find mesh plug
    fnDependNode = om.MFnDependencyNode(dagPath.node())
    return fnDependNode.findPlug('outMesh', False)  # might need MString instead of regular one.


def getPointAtTime(refreshMode, mesh, vertexId, time):
    if refreshMode:
        # If refreshMode is on, mesh should be a dagPath
        # You MUST reinitialize the function set after changing time!
        fnMesh = om.MFnMesh()
        fnMesh.setObject(mesh)
    else:
        # If refreshMode is off, mesh should be a mplug
        # Get its value at the specified Time.
        meshData = mesh.asMObject(om.MDGContext(time))

        # Use its MFnMesh function set
        fnMesh = om.MFnMesh(meshData)

    # Get vertices at this time
    position = om.MPoint()
    fnMesh.getPoint(vertexId, position, om.MSpace.kWorld)
    # cmd.spaceLocator(n = 'locl%s' % frame, p = (position[0], position[1], position[2]))
    return (position[0], position[1], position[2])


def getFirstConnection(node, attribute=None, inAttr=1, outAttr=None, findAttribute=0):
    # An quick way to get a single object from an incomming or outgoing connection.
    # Translated from my mel script jh_fl_fishingLine.mel
    if not attribute:
        attribute = node.split('.')
        if len(attribute) == 2:
            node, attribute = attribute
        else:
            om.MGlobal.displayInfo('Node %s has no attribute passed.  An attribute is needed to find a connection!' % node)
    else:
        attribute = attribute.split('.')[-1]
    if outAttr == None:
        outAttr = not inAttr
    else:
        inAttr = not outAttr

    if cmd.objExists(node) and mel.eval('attributeExists("%s", "%s")' % (attribute, node)):
        nodes = cmd.listConnections('%s.%s' % (node, attribute), d=outAttr, s=inAttr, scn=1, p=findAttribute)
        if nodes:
            return nodes[0]

    else:
        om.MGlobal.displayWarning('%s has no attribute %s' % (node, attribute))

# arcTracker.create('locator1')
if __name__ == '__main__':
    reload(arcTracer)
    # arcTracer.atPoint()
    pass
