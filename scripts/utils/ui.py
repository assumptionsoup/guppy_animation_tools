'''
*******************************************************************************
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
'''

import pymel.core as pm


try:
    import shiboken
except ImportError:
    import shiboken2 as shiboken

import maya.OpenMayaUI as omUI

import guppy_animation_tools as gat
from guppy_animation_tools.utils.qt import QtCore, QtGui, QtWidgets
from guppy_animation_tools.utils.decorator import memoized


_log = gat.getLogger(__name__)
_globalQtObjects = {}


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

# Cache results, as we really don't want multiple class objects
# floating around
@memoized
def RightClickWidgetFactory(widgetType):
    '''
    Creates a widget class that emits a rightClicked signal.

    Why does this exist?
        PySide and PySide2 objects do not call super().  This breaks
        multiple inheritance.
    '''
    # Create the class - I could have used type(), but that's
    # a little harder to read.  This seems simpler.
    class RightClickWidget(widgetType):
        '''
        A widget that emits a `rightClicked` signal.
        '''
        rightClicked = QtCore.Signal()

        def mousePressEvent(self, event):
            if event.button() == QtCore.Qt.RightButton:
                event.accept()
                self.rightClicked.emit()
            else:
                event.ignore()
                super(RightClickWidget, self).mousePressEvent(event)

    # Name the class after the widget it inherits from.
    widgetName = widgetType.__name__
    if widgetName.startswith('Q'):
        widgetName = widgetName[1:]
    widgetName = 'RightClick' + widgetName
    RightClickWidget.__name__ = widgetName

    return RightClickWidget


@memoized
def BubblingMenuFactory(widgetType):
    '''
    Creates a widget class that opens a menu when right clicked.

    This menu can bubble up to parent instances of this class, allowing
    a QT chain of widgets to build up a menu like this:

    Menu
    ------------
    Menu item from most specific widget
    ------------
    Menu item from parent widget
    ------------
    Menu item from top widget


    Why does this exist?
        PySide and PySide2 objects do not call super().  This breaks
        multiple inheritance.  This class allows multiple inheritance
        along a single axis (varying the Qt widget type).
    '''
    class BubblingMenu(RightClickWidgetFactory(widgetType)):
        def __init__(self, *args, **kwargs):
            super(BubblingMenu, self).__init__(*args, **kwargs)
            self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
            self.rightClicked.connect(self.rightClickMenu)

        def rightClickMenu(self, menu=None, bubble=True):
            _log.debug("Bubbling right click menu, bubble=%s", bubble)
            widget = self
            bubbled = False
            if bubble:
                while widget.parent():
                    try:
                        widget.parent().rightClickMenu
                    except AttributeError:
                        _log.debug("Bubbling failed on widget %s",
                                   type(widget.parent()))
                        widget = widget.parent()
                    else:
                        _log.debug("Bubbling right click to %s",
                                   type(widget.parent()))
                        action = widget.parent().rightClickMenu(menu=menu)
                        bubbled = True
                        break

            if not bubbled or not bubble:
                action = menu.exec_(QtGui.QCursor.pos())
            return action
    widgetName = widgetType.__name__
    if widgetName.startswith('Q'):
        widgetName = widgetName[1:]
    widgetName = 'RightClickMenu' + widgetName
    BubblingMenu.__name__ = widgetName

    return BubblingMenu


class PersistentWidget(QtWidgets.QWidget):
    '''
    A widget that remembers its position and size between sessions.
    '''
    def __init__(self, *args, **kwargs):
        super(PersistentWidget, self).__init__(*args, **kwargs)

        self._geometryIdentifier = 'gat_ui_rect_%s' % str(type(self).__name__)
        QtCore.QCoreApplication.instance().aboutToQuit.connect(
            self._saveGeometry)

    def _saveGeometry(self):
        rect = self.geometry()
        rect = [rect.x(), rect.y(), rect.width(), rect.height()]
        _log.debug("Saving %s geometry as %s", self, rect)

        # A bit hack to save this as an option var, but it's
        # far easier than writing to a config file somewhere.
        pm.env.optionVars[self._geometryIdentifier] = rect

    def _restoreGeometry(self):
        rectData = pm.env.optionVars.get(self._geometryIdentifier, None)
        if rectData:
            _log.debug("Restoring %s geometry to %s", self, rectData)
            self.setGeometry(QtCore.QRect(*rectData))
        else:
            # Center widget on to the maya window instead of opening it
            # at [0, 0] like the stupid default.
            self.adjustSize()
            windowCenter = getMayaWindow().geometry().center()
            thisRect = self.geometry()
            x = windowCenter.x() - thisRect.width() / 2
            y = windowCenter.y() - thisRect.height() / 2
            self.move(x, y)
            _log.debug("Moving %s to center screen at %s %s", self, x, y)

    def closeEvent(self, event):
        self._saveGeometry()
        super(PersistentWidget, self).closeEvent(event)

    def showEvent(self, event):
        # super(PersistentWidget, self).showEvent(event)
        self._restoreGeometry()



class SignalBlocker(object):
    '''
    Context manager to block signals of the given QObject.
    '''

    def __init__(self, widget):
        self.widget = widget
        self.state = False

    def __enter__(self):
        self.state = self.widget.blockSignals(True)

    def __exit__(self, exc_type, exc_value, traceback):
        self.widget.blockSignals(self.state)


def showWidget(key, widgetType, refresh=False):
    global _globalQtObjects
    if refresh:
        # Close and remove widget, so we can test a new one.
        try:
            widget = _globalQtObjects.pop(key)
        except (KeyError, RuntimeError):
            pass
        else:
            # Widget might get deleted on close, watch out!
            if shiboken.isValid(widget):
                widget.close()
            if shiboken.isValid(widget):
                widget.deleteLater()

    # Prevent GC
    widget = _globalQtObjects.get(key)
    if widget is None or not shiboken.isValid(widget):
        widget = _globalQtObjects[key] = widgetType()
    widget.show()
    widget.raise_()
