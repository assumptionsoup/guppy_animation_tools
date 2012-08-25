'''Move My Objects provides a way to quickly save and restore objects' world
space position.

The UI of Move My Objects only allows an animator to save and move a single
object at a time (due to lack of time to write a proper interface for more).
However, using savePositions and applyPositions directly can save and restore
multiple objects.
	
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

''''''*************************************************************************

	Author:........Jordan Hueckstaedt
	Website:.......RubberGuppy.com
	Email:.........AssumptionSoup@gmail.com
	Work Status:...Looking for work!  If you have a job where I can write tools
				   like this or rig characters, hit me up!

****************************************************************************'''

import maya.cmds as cmd
import maya.OpenMaya as om

#		from moveMyObjects import MoveMyObjects
#		mmo = MoveMyObjects()
#		mmo.ui()


def enableUndo():
	try:
		cmd.undoInfo(cck = 1)			#close chunk
	except:
		cmd.undoInfo(swf = 1)			#turn undo back on
		cmd.undoInfo(q = 1, un = 0)		#needs this to work for some reason

def disableUndo():
	try:
		cmd.undoInfo(ock = 1)		#Open chunk
	except:
		cmd.undoInfo(swf = 0)		#turn undo off

def duplicateGroup(obj, name):
	# Duplicate object transform
	dupObj = cmd.duplicate(obj, po = 1, rr = 1, n = name)[0]
	
	#unlock default channels
	attrs = 't r s tx ty tz rx ry rz sx sy sz v'.split()
	for attr in attrs:
		cmd.setAttr('%s.%s' % (dupObj, attr), lock = 0, keyable = 1)
	return dupObj

def savePositions(objects):
	positions = []
	sel = cmd.ls(sl = 1)
	
	# Stop undo, so this doesn't get annoying for artist
	disableUndo()
	
	# Create tempgroup and parent constrain it to object to get position
	# Maya likes this approach better
	tempGroup = cmd.group(n = 'jh_savePos_tmpGrp', em = 1)
	
	# If passed a string instead of a list
	if isinstance( objects, basestring ):
		objects = [objects]
	
	# Get position with parent constraints
	for obj in objects:
		tempConst = cmd.parentConstraint(obj, tempGroup)
		cmd.refresh()
		positions.append( cmd.xform(tempGroup, q = 1, ws = 1, matrix = 1) )
		cmd.delete(tempConst)
	
	# Delete temp group
	cmd.delete(tempGroup)
	
	# Restore selection and undo
	cmd.select(sel)
	enableUndo()

	return positions

def applyPositions(positions, objects):
	sel = cmd.ls(sl = 1)
	
	# Stop undo, so this doesn't get annoying for artist
	disableUndo()
	
	#create tempgroup outside of loop
	tempGroup = cmd.group(n = 'jh_applyPos_tmpGrp', em = 1)

	# If passed a string instead of a list
	if isinstance( objects, basestring ):
		objects = [objects]
	
	# Make number of positions match objects
	if len(positions) != len(objects):
		if len(positions) == 1:
			positions *= len(objects)
		else:
			raise IndexError, 'Number of positions(%d) to objects(%d) were not compatible' % (len(positions), len(objects))
	
	for x in range(len(positions)):	
		#Don't constraint directly to selected, since it could be something special
		#or have stuff locked.  Create a duplicate of selected group, and constrain 
		#that
		cmd.xform(tempGroup, ws = 1, matrix = positions[x])
		dummyGroup = duplicateGroup(objects[x], 'jh_applyPosDummy_tmpGrp')
		tempConst = cmd.parentConstraint(tempGroup, dummyGroup)
		cmd.refresh()
		
		#Copy attributes from the dummy group onto the real one.
		attrs = ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz')
		for attr in attrs:
			value = cmd.getAttr('%s.%s' % (dummyGroup, attr))
			try:
				cmd.setAttr('%s.%s' % (objects[x], attr), value)
			except:
				om.MGlobal.displayWarning('Could not set value for %s.%s, skipping...' % (objects[x], attr))
		
		cmd.delete(tempConst)
		cmd.delete(dummyGroup)
	cmd.delete(tempGroup)
	cmd.select(sel)
		
	#reenable undo
	enableUndo()
			
class MoveMyObjects(object):
	def __init__(self):
		self.positions = []

	def ui(self):
		if cmd.window('jh_savePositionWin', exists = 1):
			cmd.deleteUI('jh_savePositionWin')
		window = cmd.window('jh_savePositionWin', w = 200, h = 40, s = 1, tb = 1, menuBar = 1, t = 'Save Position')
		cmd.formLayout('jh_savePos_formLay', numberOfDivisions = 100)

		cmd.button('jh_savePos_savePos', c = self.savePosition, label = 'Save Position')
		cmd.button('jh_savePos_applyPos', c = self.applyPosition, label = 'Apply Position')
		
		
		layout = {'af' : [], 'ap' : [], 'ac' : []}
		layout['af'].append(('jh_savePos_savePos', 'top',	 	5))
		layout['af'].append(('jh_savePos_savePos', 'left',	 	5))
		layout['ap'].append(('jh_savePos_savePos', 'right',	 	5,	50))
		
		layout['af'].append(('jh_savePos_applyPos', 'top',	 	5))
		layout['ap'].append(('jh_savePos_applyPos', 'left',	 	5,	50))
		layout['af'].append(('jh_savePos_applyPos', 'right',	5))
		cmd.formLayout(
			'jh_savePos_formLay',
			e = 1,
			**layout )
		cmd.showWindow(window)
	
	def savePosition(self, *args):
		# Save the position of the first thing selected
		sel = cmd.ls(sl = 1)
		if sel:
			self.positions = savePositions(sel[0])
			om.MGlobal.displayInfo('Position saved')
		else:
			om.MGlobal.displayWarning('You have to select something first!')
		
	def applyPosition(self, *args):
		sel = cmd.ls(sl = 1)
		
		if self.positions:
			print 'Got Position: ', self.positions
			if sel:
				applyPositions(self.positions, sel)
			else:
				om.MGlobal.displayWarning('You have to select something first!')
		else:
			om.MGlobal.displayWarning('You have to save a position first!')

	def saveAnimation(self, *args):
		nodes = cmd.ls(sl = 1)
		if nodes:
			#Get keyframe attrs from selected (Basically turns . to _ and expands single objects to object attributes)
			attrs = []
			for node in nodes:
				#Channels can sometimes be None for some reason... So check that.
				att = cmd.keyframe(node, q = 1, n = 1)
				if att:
					attrs.extend(att)
			print attrs
			
			#Find keyframes on current time.  If there are, add them to keys
			time = cmd.currentTime(q = 1)
			for attr in attrs:
				ky = cmd.keyframe(attr, q = 1, iv = 1, t = (time,time))
				if ky:
					keys[attr] = ky
					allKeys[attr] = cmd.keyframe(attr, q = 1, iv = 1)
			attrs = keys.keys()
			selectedKeys = False

mmo = None
def ui():
	# Wrapper to simplify usage for basic users for MoveMyObjects().ui
	global mmo
	if not mmo:
		mmo = MoveMyObjects()
	mmo.ui()

def savePosition():
	# Wrapper to simplify usage for basic users for MoveMyObjects().savePosition
	global mmo
	if not mmo:
		mmo = MoveMyObjects()
	mmo.savePosition()

def applyPosition():
	# Wrapper to simplify usage for basic users for MoveMyObjects().applyPosition
	global mmo
	if not mmo:
		mmo = MoveMyObjects()
	mmo.applyPosition()

if __name__ == '__main__':
	ui()