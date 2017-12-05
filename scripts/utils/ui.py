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

import pymel.core as pm
from qt import QtCore, QtGui, QtWidgets

try:
    import shiboken
except ImportError:
    import shiboken2 as shiboken

import maya.OpenMayaUI as omUI



def toQtWindow(windowName):
    ptr = omUI.MQtUtil.findWindow(windowName)
    if ptr is not None:
        return shiboken.wrapInstance(long(ptr), QtWidgets.QWidget)


def getMayaWindow():
    '''
    Get the main Maya window as a QtGui.QMainWindow instance
    '''
    return toQtWindow(pm.melGlobals['$gMainWindow'])


## Common Widgets ##
class RightClickButton(QtWidgets.QPushButton):
    rightClicked = QtCore.Signal()

    def mousePressEvent(self, event):
        super(RightClickButton, self).mousePressEvent(event)
        if event.button() == QtCore.Qt.RightButton:
            self.rightClicked.emit()
