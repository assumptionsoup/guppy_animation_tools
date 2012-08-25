'''pointOnMesh is a helper module for Arc Tracer.  If I cleaned it up, it 
could probably become a pretty useful wrapper for Open Maya ray intersections.

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
__version__ = '0.1'
__email__ = 'AssumptionSoup@gmail.com'
__status__ = 'Beta'
__date__ = '8-24-2012'

import maya.cmds as cmd
import maya.mel as mel
import maya.OpenMaya as om
import maya.OpenMayaUI as omui
from operator import attrgetter

class SurfaceIntersectData(object):
	#A container for holding surface intersection data
	def __init__(self, name, surfaceType, distance, point, u, v, closestVertex, follicle = None):
		self.name = name
		self.type = surfaceType
		self.distance = distance
		self.point = point
		self.u = u
		self.v = v
		self.closestVertex = closestVertex
		self.follicle = follicle
	
	def __repr__(self):
		return repr((self.name, self.distance, self.point, self.u, self.v, self.closestVertex, self.follicle))

def getPoint(clickPosition, createFollicle = 1):
	currentSel = cmd.ls(sl = 1)
	
	#Get ray information.
	shapes, clickPoint, clickDirection = castRay(clickPosition)
	
	#Find intersect points
	surfaceData = []
	for mesh in shapes:
		resultData = rayIntersect(mesh, clickPoint, clickDirection)
		if resultData:
			surfaceData.append(resultData)
	
	#If we got a point
	if surfaceData:
		#Sort points by distance.
		surfaceData.sort(key=attrgetter('distance'))
		surfaceData = surfaceData[0]
		if createFollicle:
			surfaceData.follicle = createFollicleAtPoint(surfaceData)
		
		#Set tool to move tool.
		cmd.setToolTo('moveSuperContext')
	else:
		surfaceData = None
		om.MGlobal.displayError('Sorry, I think you need to click on something for this whole process to work.  You click.  Me trace.')
	
	#Reselect old stuff
	if currentSel:
		cmd.select(currentSel)
	else:
		cmd.select(cl = 1)
	
	return surfaceData

def vectorToList(vector):
	#Actually takes vectors or points
	axes = ['x', 'y', 'z']
	if hasattr(vector, 'w'):
		axes.append('w')
	result = []
	for axis in axes:
		result.append(getattr(vector, axis))
	return result
	
def getDagPath(objectName):
	#Get DagPath from object name.
	# put object name into the MObject
	tempList = om.MSelectionList()
	tempList.add(objectName)

	# get the dagpath of the object
	dagpath = om.MDagPath()
	tempList.getDagPath(0, dagpath)
	return dagpath

def castRay(clickPosition, wireframeMode = False):
	#Get world space point and direction vector of pointer
	clickPoint = om.MPoint()
	clickDirection = om.MVector()
	
	activeView = omui.M3dView.active3dView()
	activeView.viewToWorld(int(clickPosition[0]), int(clickPosition[1]), clickPoint, clickDirection)
	
	#Convert to lists, and make clickDirection relative to the clickPoint.
	clickPoint = vectorToList(clickPoint)
	clickDirection = vectorToList(clickDirection)
	clickDirection = [clickDirection[x] + clickPoint[x] for x in xrange(len(clickDirection))]
	
	if wireframeMode:
		#Find All Visible Meshes.  It works in wireframe mode, which I've had the more efficient method fail at before.
		shapes = cmd.ls(g = 1, v = 1)
	else:
		#Grab only mesh under pointer
		shapes = []
		om.MGlobal.selectFromScreen(int(clickPosition[0]), int(clickPosition[1]), om.MGlobal.kReplaceList , om.MGlobal.kSurfaceSelectMethod )
		objFromClick = cmd.ls(sl = 1)
		
		for obj in objFromClick:
			shapes.extend(cmd.listRelatives(obj, s = 1))

	return shapes, clickPoint, clickDirection
	
def rayIntersect( mesh, point, direction):
	#Calculate ray direction vector
	raySource = om.MFloatPoint(point[0], point[1], point[2], 1.0)
	rayDir = om.MFloatVector(direction[0], direction[1], direction[2])
	rayDir = rayDir - om.MFloatVector(raySource)
	
	#Determine surface type since each intersection is dependant on type.
	surfaceType = cmd.ls(mesh, st = 1)[-1]
	
	#Why are the nurbs and polygon intersect functions so different?  One uses MPoint the other MFloatPoint.  
	#There is a REASON that python is a DUCK TYPED language autodesk.
	surfaceData = None
	if surfaceType == 'nurbsSurface':
		surfaceData = getNurbsSurfaceData(mesh, raySource, rayDir, surfaceType)
	elif surfaceType == 'mesh':
		surfaceData = getPolygonSurfaceData(mesh, raySource, rayDir, surfaceType)
	
	return surfaceData
	
def getNurbsSurfaceData(mesh, raySource, rayDir, surfaceType):
	#Find nurbs intersection.  om.kMFnNurbsEpsilon was the secret sauce for this sucker to work
	worldSpace = om.MSpace.kWorld
	raySource = om.MPoint(raySource)
	rayDir = om.MVector(rayDir)
	
	uUtil = om.MScriptUtil()
	u = uUtil.asDoublePtr()
	vUtil = om.MScriptUtil()
	v = vUtil.asDoublePtr()
	
	exactHitUtil = om.MScriptUtil()
	exactHit = exactHitUtil.asBoolPtr()
	resultPoint = om.MPoint()
	
	distanceUtil = om.MScriptUtil()
	distance = distanceUtil.asDoublePtr()
	
	fnSurface = om.MFnNurbsSurface(getDagPath(mesh))
	fnSurface.intersect	(	raySource,
							rayDir,
							u, #U position - Double
							v, #V position - Couble
							resultPoint,
							om.kMFnNurbsEpsilon,	#tolerance - Double
							worldSpace,
							True, #calculate distance
							distance,
							False, #calculateExactHit (Did it actually hit, or was it within the tolerance)
							None) #wasExactHit
	distance = om.MScriptUtil.getDouble( distance )
	#Get UV values
	u = om.MScriptUtil.getDouble( u )
	v = om.MScriptUtil.getDouble( v )
	
	#Normalize UV Values
	maxU = cmd.getAttr( mesh + '.maxValueU' )
	maxV = cmd.getAttr( mesh + '.maxValueV' )
	minU = cmd.getAttr(mesh + '.minValueU' )
	minV = cmd.getAttr(mesh + '.minValueV' )
	u = (u - minU) / (maxU - minU)
	v = (v - minV) / (maxV - minV)
	
	if distance > 0.0:
		return SurfaceIntersectData(mesh, surfaceType, distance, vectorToList(resultPoint), u, v, None)
	else:
		return None
	
def getPolygonSurfaceData(mesh, raySource, rayDir, surfaceType):
	#Find polygon intersection.
	worldSpace = om.MSpace.kWorld
	resultPoint = om.MFloatPoint()
	#hitRayParam = om.MScriptUtil().asFloatPtr()	#Don't ever do this.
	hitRayParamUtil = om.MScriptUtil()
	hitRayParam = hitRayParamUtil.asFloatPtr()
	
	fnMesh = om.MFnMesh(getDagPath(mesh))
	fnMesh.closestIntersection(	raySource, 
								rayDir, 
								None, #faceIds 
								None, #triIds
								False, #idsSorted 
								worldSpace, 
								999999, #maxParam, 
								False, #testBothDirections,
								None, #accelParams
								resultPoint, 
								hitRayParam, 
								None, #hitFace
								None, #hitTris
								None, #hitBarys1
								None, #hitBarys2 
								0.0001) #tolerance om.kMFnMeshPointTolerance
	distance = om.MScriptUtil.getFloat( hitRayParam )
	
	#Now get the UV data
	#Google is your friend.  I don't know how people figured this poop out.
	#This monstrosity creates the float2
	pArray = [0,0]
	x1 = om.MScriptUtil()
	x1.createFromList( pArray, 2 )
	uvPoint = x1.asFloat2Ptr()
	
	#Try to get UV point.  I've seen this fail.  Due to lack of uv's.  Don't ask.
	try:
		fnMesh.getUVAtPoint	(	om.MPoint(resultPoint),
								uvPoint, #float2 & 	uvPoint,
								worldSpace,
								None, #const MString * 	uvSet = NULL,
								None) #int * 	closestPolygon = NULL	 
		#And this accesses it.  A 2 dimentional array to get a 1 dimensional array.  Makes...sense...right?
		#....nnnnoooooooooooo
		u = om.MScriptUtil.getFloat2ArrayItem( uvPoint, 0, 0 )
		v = om.MScriptUtil.getFloat2ArrayItem( uvPoint, 0, 1 )
	except:
		u = None
		v = None
	
	#With the closest vert, you could make a vertex constraint thing, without needed a UV.
	closestPolygonUtil = om.MScriptUtil()
	closestPolygon = closestPolygonUtil.asIntPtr()
	fnMesh.getClosestPoint(	om.MPoint(resultPoint),
							om.MPoint(), #theClosestPoint point storage
							worldSpace,
							closestPolygon) #int * 	closestPolygon = NULL
	closestVertex = getClosestPointFromPolygon(om.MPoint(resultPoint), fnMesh, closestPolygon)
	
	if distance > 0.0:
		return SurfaceIntersectData(mesh, surfaceType, distance, vectorToList(resultPoint), u, v, closestVertex)
	else:
		return None
	
def getClosestPointFromPolygon(point, fnMesh, polygonId):
	#Get verticies of polygon
	worldSpace = om.MSpace.kWorld
	vertexList = om.MIntArray()
	fnMesh.getPolygonVertices( om.MScriptUtil.getInt(polygonId), vertexList)
	
	#Find closest vertex to point.
	distance = None
	closestVertex = None
	for vertex in vertexList:
		vertexPoint = om.MPoint()
		fnMesh.getPoint(vertex, vertexPoint, worldSpace)
		newDistance = point.distanceTo(vertexPoint)
		if not distance:
			distance = newDistance
			closestVertex = vertex
		elif newDistance < distance:
			distance = newDistance
			closestVertex = vertex
	return closestVertex

def createFollicle(surfaceData, name = 'follicleOnSurface'):
	#Create follicle at point on mesh.
	#Just for fun, lets break convention on this command and have the type come first instead of the name
	follicle = cmd.createNode('transform', n = name)
	follicleShape = cmd.createNode('follicle', n = '%sShape#' % name, p = follicle)
	
	#Set follicle uv
	cmd.setAttr('%s.parameterU' % follicleShape, surfaceData.u)
	cmd.setAttr('%s.parameterV' % follicleShape, surfaceData.v)
	
	#Connect follicle up
	if surfaceData.type == 'mesh':
		cmd.connectAttr('%s.outMesh' % surfaceData.name, '%s.inputMesh' % follicleShape, f = 1)
	else:
		cmd.connectAttr('%s.local' % surfaceData.name, '%s.inputSurface' % follicleShape, f = 1)
	cmd.connectAttr('%s.worldMatrix[0]' % surfaceData.name, '%s.inputWorldMatrix' % follicleShape, f = 1)
	cmd.connectAttr('%s.outRotate' % follicleShape, '%s.rotate' % follicle, f = 1)
	cmd.connectAttr('%s.outTranslate' % follicleShape, '%s.translate' % follicle, f = 1)
	cmd.setAttr('%s.v' % follicle, 0)
	cmd.select(follicle)
	return follicle

	
if __name__ == '__main__':
	reload(PointOnMesh)
	pass
