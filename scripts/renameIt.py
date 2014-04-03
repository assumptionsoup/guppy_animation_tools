'''
A super simplistic dialog for renaming the selected nodes in Maya
'''
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
    Author:........Jordan Hueckstaedt
    Website:.......RubberGuppy.com
    Email:.........AssumptionSoup@gmail.com
'''

import re

import pymel.core as pm
from PySide import QtCore, QtGui
import guppy_animation_tools.utils as utils


try:
    _globalQtObjects
    _history
except NameError:
    _globalQtObjects = []
    _history = {'search': [], 'replace': []}

# TODO:
#      - Add option to enable/disable smart-padding
#      - Add option to set padding character (currently "0")
#      - Add tooltip hints
#      - Consider adding preview window of regex matches


class InvalidNameError(ValueError):
    pass


def safeRename(objs, newNames):
    '''
    Safely renames the given PyNodes to the given names.

    First validates the names, then renames each node to a name that
    will not conflict with any new name.  If an error is encountered,
    the original name is restored.
    '''

    # Validate names
    for obj, name in zip(objs, newNames):
        if not pm.mel.isValidObjectName(name):
            raise InvalidNameError(
                'Cannot rename "%s" to "%s"' % (obj.nodeName(), name))

    with utils.UndoChunk():
        # Rename objects to something that I hope doesn't already exist,
        # so that we don't run into issues trying to rename an object in
        # our list to the name of an object that hasn't yet been
        # renamed.

        oldNames = []
        for obj in objs:
            oldNames.append(obj.nodeName())
            obj.rename('_' * 80)

        # Rename things for real
        for x, obj in enumerate(objs):
            try:
                obj.rename(newNames[x])
            except RuntimeError:
                # Restore original name in case of errors
                obj.rename(oldNames[x])
                raise


def renameObjects(objs, searchText, replaceText):
    '''
    Rename the given PyNode's.

    There are two fundamental behaviors to this rename: regex
    substitution, and padded rename.

    Regex Substitution:
        Occurs when searchText has been specified and is not equal to
        ".*"  It performs a regular python regex substitution on all
        nodes.
    Padded Rename:
        Occurs when searchText is empty or equal to ".*"  It names all
        the given objects to the `replaceText` string.  Unlike a regular
        rename operation in Maya it will calculate the needed padding to
        properly pad all numbers.  If the `replaceText` ends in a
        number, that number will be the first number used for the
        sequence.  If that number is padded, that padding will be used
        instead of the automatically calculated padding.

    Examples
    --------
    >>> renameObjects(['null1', 'null2', 'null3'], '', 'node')
    # Result: ['node1', 'node2', 'node3']

    >>> renameObjects(['null1', 'null2', ..., 'null10'], '', 'node')
    # Result: ['node01', 'node02', 'node03']

    >>> renameObjects(['null1', 'null2', 'null3'], '.*', 'node0003')
    # Result: ['node0003', 'node0004', 'node0005']

    >>> renameObjects(['null1', 'null2', 'null3'], '(n)', '_\1_')
    # Result: ['_n_ull1', '_n_ull2', '_n_ull3']
    '''
    if not objs:
        return

    if not searchText:
        searchText = '.*'

    if searchText == '.*':
        _renameWithPadding(objs, replaceText)
    else:
        _substituteRename(objs, searchText, replaceText)


def _substituteRename(objs, searchText, replaceText):
    '''
    Perform a python regex substitution on the nodeName for all given
    PyNode's.
    '''
    # Find the results
    newNames = []
    reComp = re.compile(searchText)
    for obj in objs:
        name = reComp.sub(replaceText, obj.nodeName())
        newNames.append(name)

    # Rename 'em
    safeRename(objs, newNames)


def _renameWithPadding(objs, name):
    '''
    Renames all the given PyNodes to `name`.

    Unlike a regular rename operation in Maya it will calculate the
    needed padding to properly pad all the selected names (e.g. node01,
    node02 ... node10).  If the `name` ends in a number, that number
    will be the first number used for the sequence. If that number is
    padded, that padding will be used instead of the automatically
    calculated padding.


    Examples
    --------
    >>> _renameWithPadding(['null1', 'null2', 'null3'], 'node')
    # Result: ['node1', 'node2', 'node3']

    >>> _renameWithPadding(['null1', 'null2', ..., 'null10'], 'node')
    # Result: ['node01', 'node02', 'node03']

    >>> _renameWithPadding(['null1', 'null2', 'null3'], 'node0003')
    # Result: ['node0003', 'node0004', 'node0005']

    '''

    # Find the padding
    startNum = None
    padding = 0

    digitSearch = re.search(r'(\d+)$', name)
    if digitSearch is not None:
        digit = digitSearch.group()
        padding = len(digit)
        startNum = int(digit)
        name = name[:-padding]
    else:
        padding = len(str(len(objs)))

    # Find the names
    newNames = []
    for x, obj in enumerate(objs):
        if startNum is None:
            if len(objs) == 1:
                suffix = ''
            else:
                suffix = padNumber(x + 1, padding)
        else:
            suffix = padNumber(startNum + x, padding)
        newNames.append(name + suffix)

    # Rename 'em
    safeRename(objs, newNames)


def padNumber(number, padding):
    '''
    Returns a string of an integer padded by the given number of digits.

    Examples
    --------
    >>> padNumber(5, 4)
    '0005'
    '''
    return '%%0%dd' % padding % number


class RenameDialog(QtGui.QDialog):
    '''
    A super simplistic dialog for renaming the selected nodes in Maya
    '''

    # Use slightly larger-than-default text and monospace, since
    # it's hip.
    #
    # There seems to be SEVERAL bugs with maya's stylesheets here.
    # Setting this at all causes the fields to be a darker gray,
    # which I _prefer_.  I would like to set this explicitly via:
    #     background-color: rgb(40, 40, 40);
    # However, doing that removes the border to the fields AND
    # changes their padding.  So I'm leaving it be for now.
    thisStylesheet = '''
        *
        {
            font-size: 6pt;
        }

        QLineEdit
        {
            font-family: "Monospace";
        }
    '''

    def __init__(self, parent=None, closeOnRename=True, closeOnFocusLoss=True):
        super(RenameDialog, self).__init__(parent=parent,
                                           f=QtCore.Qt.FramelessWindowHint)
        self.closeOnRename = closeOnRename
        self.closeOnFocusLoss = closeOnFocusLoss
        self.setStyleSheet(self.thisStylesheet)

        # Build layout
        self.searchText = QtGui.QLabel(self)
        self.searchText.setText('Search')
        self.searchField = QtGui.QLineEdit(self)
        self.searchField.returnPressed.connect(self.renameSelection)
        self.replaceText = QtGui.QLabel(self)
        self.replaceText.setText('Replace')
        self.replaceField = QtGui.QLineEdit(self)
        self.replaceField.returnPressed.connect(self.renameSelection)
        self.populateReplaceField()

        self.setLayout(QtGui.QHBoxLayout())
        self.setMinimumWidth(250)
        self.textColumn = QtGui.QWidget(self)
        self.fieldColumn = QtGui.QWidget(self)
        self.layout().addWidget(self.textColumn)
        self.layout().addWidget(self.fieldColumn)
        fieldLayout = QtGui.QVBoxLayout()
        textLayout = QtGui.QVBoxLayout()
        self.textColumn.setLayout(textLayout)
        self.fieldColumn.setLayout(fieldLayout)
        textLayout.setContentsMargins(0, 0, 0, 0)
        fieldLayout.setContentsMargins(0, 0, 0, 0)

        textLayout.addWidget(self.searchText)
        textLayout.addWidget(self.replaceText)
        fieldLayout.addWidget(self.searchField)
        fieldLayout.addWidget(self.replaceField)

        # Monkey patch fields to detect focus events
        def checkFocusEvents(field):
            origFocusOut = field.focusOutEvent

            def wrappedFocusOutEvent(event):
                focused = self.anyFocus()
                if not focused and self.closeOnFocusLoss:
                    self.close()
                return origFocusOut(event)
            field.focusOutEvent = wrappedFocusOutEvent

        checkFocusEvents(self.searchField)
        checkFocusEvents(self.replaceField)

        # Set background transparent.  Only items drawn in paintEvent
        # will be visible.  This is necessary for rounded corners.
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Base, QtCore.Qt.transparent)
        self.setPalette(palette)
        self.replaceField.setFocus()

        # Add hotkeys to detect up and down arrows
        QtGui.QShortcut(QtGui.QKeySequence("Up"), self, self.previousEntry)
        QtGui.QShortcut(QtGui.QKeySequence("Down"), self, self.nextEntry)

        self.historyIndexes = {'search': len(_history['search']) - 1,
                               'replace': len(_history['replace']) - 1}
        self.historyFields = {'search': self.searchField,
                              'replace': self.replaceField}
        self._addHistory()

    def _addHistory(self):
        '''
        Add the current field text to the history if applicable.
        '''
        global _history

        def addToHistory(entries, index, text):
            # Add a new entry if we are at the end of the entries list,
            # and the last entry is not the same.
            if index == len(entries) - 1:
                if not (entries and entries[-1] == text):
                    index = len(entries)
                    entries.append(text)
            else:
                # Otherwise insert a new entry.
                index += 1
                entries.insert(index, text)
            return index

        for field, entries in _history.iteritems():
            self.historyIndexes[field] = addToHistory(
                entries,
                self.historyIndexes[field],
                self.historyFields[field].text())

    def previousEntry(self):
        '''
        Set the text field with focus to the previous history entry.
        '''
        global _history

        def getPreviousIndex(currentIndex):
            if currentIndex - 1 < 0:
                index = 0
            else:
                index = currentIndex - 1
            return index

        focusedWidget = QtGui.qApp.focusWidget()
        for field, entries in _history.iteritems():
            if focusedWidget is self.historyFields[field]:
                i = getPreviousIndex(self.historyIndexes[field])
                self.historyIndexes[field] = i
                self.historyFields[field].setText(entries[i])

    def nextEntry(self):
        '''
        Set the text field with focus to the next history entry.
        '''
        global _history

        def getNextIndex(currentIndex, entries):
            if currentIndex == len(entries) - 1:
                index = currentIndex
            else:
                index = currentIndex + 1
            return index

        focusedWidget = QtGui.qApp.focusWidget()
        for field, entries in _history.iteritems():
            if focusedWidget is self.historyFields[field]:
                i = getNextIndex(self.historyIndexes[field], entries)
                self.historyIndexes[field] = i
                self.historyFields[field].setText(entries[i])

    def paintEvent(self, event):
        # Add curved corners and a border to this dialog.
        lineWidth = 2
        fillColor = QtGui.QColor(65, 65, 65, 255)
        lineColor = QtCore.Qt.gray

        # Prep the painter
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QBrush(lineColor), lineWidth))
        painter.setBrush(QtGui.QBrush(fillColor))

        # Adjust the rounded corners rect to account for the lineWidth
        roundRect = self.rect().adjusted(
            lineWidth, lineWidth, -lineWidth, -lineWidth)
        painter.drawRoundedRect(roundRect, 15, 15)

    def anyFocus(self):
        '''
        Returns True if this dialog or any of it's children have focus.
        '''

        hasFocus = False
        focusedWidget = QtGui.qApp.focusWidget()
        if focusedWidget is not None:
            if self is focusedWidget.window():
                hasFocus = True
        return hasFocus

    def populateReplaceField(self):
        '''
        Populate the replaceField with the node name of the first
        selected object.
        '''
        self.replaceField.setFocus()
        objs = self.getSelection()
        if objs:
            self.replaceField.setText(objs[0].nodeName())
            self.replaceField.selectAll()

    def renameSelection(self):
        '''
        Renames the selected objects with the replaceField string
        '''
        self._addHistory()
        objs = self.getSelection()
        if not objs:
            # TODO: Pop up a dialog with this
            print 'You must select one or more objects to rename.'
        else:
            searchText = self.searchField.text()
            replaceText = self.replaceField.text()
            renameObjects(objs, searchText, replaceText)

        if self.closeOnRename:
            self.close()

    def getSelection(self):
        '''
        Returns a list of selected PyNode objects to rename.
        '''
        return pm.selected()


def ui():
    global _globalQtObjects
    if pm.selected():
        renameDialog = RenameDialog(utils.ui.getMayaWindow())
        for obj in reversed(_globalQtObjects):
            _globalQtObjects.remove(obj)
            obj.close()

        renameDialog.show()
        renameDialog.raise_()
        _globalQtObjects.append(renameDialog)
    else:
        # It would be total overkill, but I'd love to implement my own
        # version of this, so it showed up in the same place the rename
        # window would have shown up.
        pm.inViewMessage(message='Nothing Selected', pos='topCenter',
                         backColor=0x00111111, fade=1, fadeInTime=200,
                         fadeStayTime=450, fadeOutTime=200, fontSize=11)

if __name__ == '__main__':
    ui()
