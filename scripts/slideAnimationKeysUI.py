'''
Slide Animation Keys is a tool that allows animators to quickly adjust keys.

... and this is the UI for that!

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

'''

from functools import partial

from guppy_animation_tools import getLogger, internal, slideAnimationKeys
from guppy_animation_tools.internal.qt import QtCore, QtGui, QtWidgets

_controller = slideAnimationKeys.controller


_log = getLogger(__name__)


class IntegerValidator(QtGui.QValidator):
    '''
    Validates lineEdit's for integer values
    '''
    def validate(self, inputString, pos):
        if inputString.startswith('-'):
            inputString = inputString[1:]
            if not inputString:
                return QtGui.QValidator.Intermediate

        for char in inputString:
            if not char.isdigit():
                return QtGui.QValidator.Invalid
        return QtGui.QValidator.Acceptable


class CheckBoxFrame(QtWidgets.QFrame):
    '''
    A QFrame with an inline checkbox at the top.

    Usage:
    Pretty straight forward.
    Access the checkbox part via CheckBoxFrame.checkbox
    CheckBoxFrame itself is the frame.  Add widgets as you normally would.
    '''
    _stylesheet = '''
        CheckBoxFrame {{
            padding: 10px 5px 8px 5px;
            margin: 8px 0px 8px 0px;
            border-style: solid;
            border-width: 2px;
            border-radius: 8px;
            border-color: {borderColor}
        }}'''

    def __init__(self, parent=None):
        super(CheckBoxFrame, self).__init__(parent=parent)
        self._buildLayout()
        self.setBorderColor("#8c8c8c")

    def _buildLayout(self):
        self.setContentsMargins(0, 0, 0, 0)

        self._widgetHolder = QtWidgets.QFrame(parent=self)
        self._widgetHolder.setLayout(QtWidgets.QHBoxLayout())
        self._widgetHolder.layout().setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self._widgetHolder.setObjectName("_widgetHolder")
        self._widgetHolder.setContentsMargins(4, 10, 4, 4)
        self._widgetHolder.layout().setContentsMargins(0, 0, 0, 0)

        self.checkbox = QtWidgets.QCheckBox(parent=self)

        self._widgetHolder.layout().addWidget(self.checkbox)
        self._widgetHolder.move(15, -8)

        self._widgetHolder.setBackgroundRole(QtGui.QPalette.Window)
        self._widgetHolder.setAutoFillBackground(True)

    def setBorderColor(self, color):
        self.setStyleSheet(self._stylesheet.format(borderColor=color))

    def resizeEvent(self, event):
        super(CheckBoxFrame, self).resizeEvent(event)

        eventSize = event.size()
        sizeHint = self._widgetHolder.sizeHint()
        self._widgetHolder.setFixedWidth(
            min(eventSize.width(), sizeHint.width()))
        self._widgetHolder.setFixedHeight(
            min(eventSize.height(), sizeHint.height()))


class ToggleFrame(CheckBoxFrame):
    '''
    A CheckBoxFrame that can be toggled on / off (enabled / disabled)
    '''
    enabledColor = '#8c8c8c'
    disabledColor = '#515151'

    def __init__(self, parent=None):
        super(ToggleFrame, self).__init__(parent=parent)
        self._enabled = True
        self._states = {}
        self.checkbox.stateChanged.connect(self.setEnabled)
        self.checkbox.setChecked(True)

    def setEnabled(self, state):
        if self.layout():
            for x in xrange(self.layout().count()):
                widget = self.layout().itemAt(x).widget()
                newState = state
                if state:
                    newState = self._states.get(widget, True)
                else:
                    self._states[widget] = widget.isEnabled()
                widget.setEnabled(newState)

        if state:
            self.setBorderColor(self.enabledColor)
        else:
            self.setBorderColor(self.disabledColor)
        self._enabled = state

        # True up checkbox state in case this function was called
        # directly, and not through a signal.
        with internal.ui.SignalBlocker(self.checkbox):
            self.checkbox.setChecked(state)

    def isEnabled(self):
        return self._enabled


class StackedWidgets(QtCore.QObject):
    '''
    A stacked widget class that acts on another layout, rather than
    creating its own.
    '''
    # Should mostly be a drop-in replacement except for the init arg,
    # but it is far from a complete implementation.

    def __init__(self, parentLayout):
        self.layout = parentLayout
        self._index = 0
        self._widgets = []

    def addWidget(self, widget):
        self.layout.addWidget(widget)
        if self._index != len(self._widgets):
            widget.hide()
        self._widgets.append(widget)

    def removeWidget(self, widget):
        self.layout.removeWidget(widget)
        index = self._widgets.index(widget)
        self._widgets.remove(widget)
        if index == self._index:
            try:
                self.setCurrentIndex(max(0, self._index - 1))
            except IndexError:
                pass

    def setCurrentIndex(self, index):
        for widget in self._widgets:
            widget.hide()
        self._widgets[index].show()

        # This is icky, but I was experiencing a bug in QT, where
        # widgets shown after being hidden were the wrong size (the
        # layout didn't seem to update). This is the only way I've been
        # able to force a layout update (repaint, updateGeometry,
        # update, adjustSize, and toggling enabled didn't help)
        geo = self._widgets[index].geometry()
        self._widgets[index].setGeometry(QtCore.QRect(0, 0, 0, 0))
        self._widgets[index].setGeometry(geo)

        self._index = index

    def currentIndex(self):
        return self._index


class QuickPickButton(internal.ui.BubblingMenuFactory(QtWidgets.QPushButton)):
    '''
    A single quick pick button widget.
    '''
    def __init__(self, parent=None):
        super(QuickPickButton, self).__init__(parent=parent)
        self._value = 0

    def setValue(self, value):
        self._value = value
        text = str(value)
        self.setText(text)
        if value == 0:
            self.setToolTip("Reset to original values")
        else:
            self.setToolTip("Right click for more options")

        # Set the minimum width to a fixed size, unless the text
        # can't fit - then make the width accommodate the text.
        fixedWidth = 25
        fm = self.fontMetrics()
        if value == 0:
            # 0 is usually like a reset button, so I like making it a
            # bit larger
            fixedWidth = 45
        # Don't know why I need 10 extra pixels for this to look right.
        self.setMinimumWidth(max(fixedWidth, fm.width(text) + 10))

    def value(self):
        return self._value

    def rightClickMenu(self, menu=None):
        if menu is None:
            menu = QtWidgets.QMenu()

        # Ehhh, don't do this, have an "Enter edit mode", instead.
        # Buttons become text fields,
        copyAction = menu.addAction("Copy action to clipboard")

        action = super(QuickPickButton, self).rightClickMenu(menu=menu)

        if action == copyAction:
            internal.copyFunctionToClipboard(
                slideAnimationKeys.__name__, 'hotkey(%d)' % self.value())
            _log.info("Copied action to clipboard! Paste it into the python "
                      "script editor or python hotkey.")

        return action


class QuickPickEdit(internal.ui.BubblingMenuFactory(QtWidgets.QLineEdit)):
    '''
    The edit field for quick picks when in configuration mode.
    '''
    deletePick = QtCore.Signal()
    insertPick = QtCore.Signal(str)  # insert direction: "right" or "left"

    def __init__(self, parent=None):
        super(QuickPickEdit, self).__init__(parent=parent)
        self._buildLayout()
        self.setContextMenuPolicy(QtCore.Qt.NoContextMenu)

    def setValue(self, value):
        self.setText(str(value))

    def value(self):
        return int(self.text())

    def _buildLayout(self):
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self.setMinimumWidth(15)
        self.setFixedHeight(25)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setValidator(IntegerValidator())
        self.setToolTip('Right click for more options')
        self.setText("0")

    def rightClickMenu(self, menu=None):
        if menu is None:
            menu = QtWidgets.QMenu()

        insertButton = menu.addAction("Insert Button")
        deleteButton = menu.addAction("Delete Button")
        cursorPos = QtGui.QCursor.pos()
        action = super(QuickPickEdit, self).rightClickMenu(menu=menu, bubble=True)
        if action == deleteButton:
            self.deletePick.emit()
        elif action == insertButton:
            # Find roughly where the right click came from, and use that
            # to determine the insertion direction
            pos = self.mapFromGlobal(cursorPos).x()
            if (float(pos) / self.width()) > 0.5:
                self.insertPick.emit('right')
            else:
                self.insertPick.emit('left')

        return action


class QuickPicksWidget(internal.ui.BubblingMenuFactory(QtWidgets.QWidget)):
    '''
    Widget for all quick pick buttons.

    Also manages changing / applying settings when toggleConfigureMode()
    is called.
    '''
    buttonClicked = QtCore.Signal(int)

    def __init__(self, parent=None):
        super(QuickPicksWidget, self).__init__(parent=parent)
        self._configuringUI = False
        self.pickButtons = []
        self.pickFields = []
        self._pickValues = [int(v) for v in _controller.settings.quickPickNums]
        self._buildLayout()
        self._connectSignals()

    def _buildLayout(self):
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.buttonsWidget = QtWidgets.QWidget(parent=self)
        self.buttonsWidget.setLayout(QtWidgets.QHBoxLayout())
        self.buttonsWidget.layout().setContentsMargins(0, 0, 0, 0)
        self.buttonsWidget.layout().setSpacing(2)

        self.configuringWidgets = ToggleFrame(parent=self)
        self.configuringWidgets.setLayout(QtWidgets.QVBoxLayout())
        self.configuringWidgets.layout().setContentsMargins(0, 0, 0, 0)
        self.configuringWidgets.layout().setSpacing(2)

        self.nudgeButton = QtWidgets.QRadioButton("Nudge")
        self.absoluteButton = QtWidgets.QRadioButton("Absolute")

        self.modeContainer = QtWidgets.QWidget(parent=self)
        self.modeContainer.setLayout(QtWidgets.QHBoxLayout())
        self.modeContainer.layout().setContentsMargins(0, 0, 0, 0)
        self.modeContainer.layout().setSpacing(2)
        self.modeContainer.layout().addWidget(self.nudgeButton)
        self.modeContainer.layout().addWidget(self.absoluteButton)
        self.modeContainer.layout().setAlignment(QtCore.Qt.AlignCenter)

        self.fieldsWidget = QtWidgets.QWidget(parent=self)
        self.fieldsWidget.setLayout(QtWidgets.QHBoxLayout())
        self.fieldsWidget.layout().setContentsMargins(0, 0, 0, 0)
        self.fieldsWidget.layout().setSpacing(2)

        self.configuringWidgets.checkbox.setText("Show Quick Picks")
        self.configuringWidgets.layout().addWidget(self.modeContainer)
        self.configuringWidgets.layout().addWidget(self.fieldsWidget)

        for x in xrange(len(_controller.settings.quickPickNums)):
            self.createButton()
        self.updateButtons()
        self.updateCheckboxes()

        self.stack = StackedWidgets(self.layout())
        self.stack.addWidget(self.buttonsWidget)
        self.stack.addWidget(self.configuringWidgets)

        if not _controller.settings.showQuickPick:
            self.hide()

    def _connectSignals(self):
        pass

    def toggleConfigureMode(self, acceptChanges=True):
        self._configuringUI = not self._configuringUI
        self.show()
        if not self._configuringUI and acceptChanges:
            _controller.settings.absoluteQuickPicks = self.absoluteButton.isChecked()
            # From editLines to buttons / settings
            for x, field in enumerate(self.pickFields):
                self._pickValues[x] = field.value()
            _controller.settings.quickPickNums = self._pickValues
            _controller.settings.showQuickPick = self.configuringWidgets.checkbox.isChecked()
            if not _controller.settings.showQuickPick:
                # Hide the whole widget, not just the stackedWidget, so
                # we don't leave extra spacing around in our parent
                # layout.
                self.hide()
                self.adjustSize()  # Shrink, please
        else:
            self._pickValues = [int(v) for v in _controller.settings.quickPickNums]
        self.updateButtons()
        self.updateCheckboxes()

        self.stack.setCurrentIndex(int(self._configuringUI))

        # Setting the stack index will FORCE show its children.
        # So this state change needs to come after.
        if not self._configuringUI and not _controller.settings.showQuickPick:
            # Hide the whole widget, not just the stackedWidget, so
            # we don't leave extra spacing around in our parent
            # layout.
            self.hide()

    def deleteButton(self, index):
        self._pickValues.pop(index)
        self._deleteButtonWidget(index)

    def _deleteButtonWidget(self, index):
        field = self.pickFields.pop(index)
        button = self.pickButtons.pop(index)

        self.buttonsWidget.layout().removeWidget(button)
        self.fieldsWidget.layout().removeWidget(field)
        button.deleteLater()
        field.deleteLater()

    def createButton(self, value=0):
        button = QuickPickButton(parent=self)
        self.buttonsWidget.layout().addWidget(button)

        field = QuickPickEdit(parent=self)
        self.fieldsWidget.layout().addWidget(field)

        button.setValue(value)
        field.setValue(value)

        self.pickButtons.append(button)
        self.pickFields.append(field)

        button.clicked.connect(
            lambda: self.buttonClicked.emit(button.value()))
        field.deletePick.connect(
            lambda: self.deleteButton(self.pickButtons.index(button)))

        def insertButton(direction):
            index = self.pickButtons.index(button)
            if direction.lower() == 'right':
                index += 1
            self.insertButton(index)
        field.insertPick.connect(insertButton)

    def updateButtons(self):
        # Clear buttons
        for x in reversed(xrange(len(self.pickButtons))):
            self._deleteButtonWidget(x)

        # Rebuild
        for value in self._pickValues:
            self.createButton(value)

    def updateCheckboxes(self):
        self.absoluteButton.setChecked(_controller.settings.absoluteQuickPicks)
        self.nudgeButton.setChecked(not _controller.settings.absoluteQuickPicks)
        self.configuringWidgets.checkbox.setChecked(_controller.settings.showQuickPick)

    def insertButton(self, index, value=0):
        if not self._configuringUI:
            # Can't delete buttons when not configuring.
            return
        self._pickValues.insert(index, value)

        self.updateButtons()

    def rightClickMenu(self, menu=None):
        if menu is None:
            menu = QtWidgets.QMenu()

        # Don't allow the user to delete buttons, if there is only one
        # left - I don't want a situation where they can't figure out
        # where to click to create more.  This implementation is a big
        # fragile...
        if len(self._pickValues) <= 1:
            for action in menu.actions():
                if action.text().lower() == 'delete button':
                    menu.removeAction(action)

        action = super(QuickPicksWidget, self).rightClickMenu(menu=menu)

        return action


class SliderWidget(internal.ui.BubblingMenuFactory(QtWidgets.QFrame)):
    '''
    The slider widget for sliding keys.

    Also manages changing / applying settings when toggleConfigureMode()
    is called.
    '''
    valueChanged = QtCore.Signal(int)
    sliderMoved = QtCore.Signal(int)
    sliderPressed = QtCore.Signal(int)
    sliderReleased = QtCore.Signal()

    def __init__(self, parent=None):
        super(SliderWidget, self).__init__(parent=parent)
        self._sliding = False
        self._buildLayout()
        self._connectSignals()

    def _buildLayout(self):
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self._configuringUI = False

        self.slider = QtWidgets.QSlider()
        self.slider.setRange(-100, 100)
        self.slider.setTickInterval(1)
        self.slider.setOrientation(QtCore.Qt.Horizontal)

        self.editSlider = QtWidgets.QSlider()
        self.editSlider.setRange(-100, 100)
        self.editSlider.setTickInterval(1)
        self.editSlider.setOrientation(QtCore.Qt.Horizontal)

        self.editMin = QtWidgets.QLineEdit()
        self.editMin.setValidator(IntegerValidator())
        self.editMin.setText(str(_controller.settings.sliderMin))
        self.editMin.setFixedWidth(35)  # Just hardcode something reasonable
        self.editMin.setToolTip('Minimum slider value')

        self.editMax = QtWidgets.QLineEdit()
        self.editMax.setValidator(IntegerValidator())
        self.editMax.setText(str(_controller.settings.sliderMax))
        self.editMax.setFixedWidth(35)  # Just hardcode something reasonable
        self.editMax.setToolTip('Maximum slider value')

        self.editFrame = ToggleFrame(parent=self)
        self.editFrame.setLayout(QtWidgets.QHBoxLayout())
        self.editFrame.layout().setContentsMargins(0, 0, 0, 0)
        self.editFrame.layout().setSpacing(2)
        self.editFrame.checkbox.setText("Show Slider")
        self.editFrame.checkbox.setChecked(_controller.settings.showSlider)
        self.editFrame.layout().addWidget(self.editMin)
        self.editFrame.layout().addWidget(self.editSlider)
        self.editFrame.layout().addWidget(self.editMax)

        self.stack = StackedWidgets(self.layout())
        self.stack.addWidget(self.slider)
        self.stack.addWidget(self.editFrame)

        self.layout().addWidget(self.slider)
        self.layout().addWidget(self.editFrame)

        if not _controller.settings.showSlider:
            self.hide()

    def _connectSignals(self):

        self.slider.sliderPressed.connect(self._onPress)
        self.slider.sliderMoved.connect(self._onMove)
        self.slider.sliderReleased.connect(self._onRelease)

    def _onPress(self):
        self._sliding = True
        self.sliderPressed.emit(self.value())
        self.valueChanged.emit(self.valueChanged.emit(self.value()))

    def _onMove(self, value):
        self.sliderMoved.emit(value)
        self.valueChanged.emit(value)

    def _onRelease(self):
        self._sliding = False
        self.sliderReleased.emit()

    def isSliding(self):
        return self._sliding

    def setValue(self, value):
        self.slider.setValue(value)

    def value(self):
        return self.slider.value()

    def toggleConfigureMode(self, acceptChanges=True):
        self._configuringUI = not self._configuringUI
        self.show()
        if self._configuringUI:
            self.editSlider.setValue(self.slider.value())
        elif acceptChanges:
            _controller.settings.showSlider = self.editFrame.checkbox.isChecked()
            if not _controller.settings.showSlider:
                self.hide()
                self.adjustSize()  # Shrink, please
            _controller.settings.sliderMax = int(self.editMax.text())
            _controller.settings.sliderMin = int(self.editMin.text())
        self.editFrame.checkbox.setChecked(_controller.settings.showSlider)
        self.editMax.setText(str(_controller.settings.sliderMax))
        self.editMin.setText(str(_controller.settings.sliderMin))
        self.slider.setRange(_controller.settings.sliderMin, _controller.settings.sliderMax)

        self.stack.setCurrentIndex(int(self._configuringUI))


class ModeWidget(internal.ui.BubblingMenuFactory(QtWidgets.QWidget)):
    '''
    The mode selector widget.
    '''
    modeChanged = QtCore.Signal(str)

    def __init__(self, parent=None):
        super(ModeWidget, self).__init__(parent=parent)
        self._configuringUI = False
        self._buildLayout()
        self.refresh()
        self._connectSignals()

    def _buildLayout(self):
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.modeWidget = QtWidgets.QComboBox()
        self.modeWidget.addItems(
            [mode.capitalize() for mode in _controller.settings.modes])
        self.layout().addWidget(self.modeWidget)

    def _connectSignals(self):
        self.modeWidget.currentIndexChanged.connect(self._onIndexChange)

    def _onIndexChange(self, index):
        self.modeChanged.emit(self.getMode())

    def getMode(self):
        return _controller.settings.modes[self.modeWidget.currentIndex()]

    def toggleConfigureMode(self, acceptChanges=True):
        self._configuringUI = not self._configuringUI
        self.modeWidget.setEnabled(not self._configuringUI)

    def refresh(self):
        '''
        Refresh widget from settings
        '''
        # This does not trigger _onIndexChange
        # If it did, we would have a recursive loop due to
        # the way the controller / view is wired.
        self.modeWidget.setCurrentIndex(
            _controller.settings.modes.index(_controller.settings.mode.lower()))

    def rightClickMenu(self, menu=None):
        if menu is None:
            menu = QtWidgets.QMenu()

        copyAction = menu.addAction("Copy action to clipboard")
        action = super(ModeWidget, self).rightClickMenu(menu=menu)

        if action == copyAction:
            internal.copyFunctionToClipboard(
                slideAnimationKeys.__name__, 'setMode(%r)' % self.getMode())
            _log.info("Copied action to clipboard! Paste it into the python "
                      "script editor or python hotkey.")

        return action


class SlideAnimationKeysWidget(internal.ui.BubblingMenuFactory(internal.ui.PersistentWidget)):
    '''
    The main widget / window for slide animation keys
    '''
    def __init__(self, parent=None):
        super(SlideAnimationKeysWidget, self).__init__(parent=parent)
        self._configuringUI = False
        self._buildLayout()
        self._connectSignals()
        self._onControllerUpdate()

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        QtWidgets.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)

    def _buildLayout(self):
        self.setWindowTitle("Slide Animation Keys")
        self.sliderWidget = SliderWidget()

        self.confirmContainer = QtWidgets.QWidget()
        self.confirmContainer.setLayout(QtWidgets.QHBoxLayout())
        self.confirmContainer.layout().setContentsMargins(0, 0, 0, 0)
        self.confirmContainer.layout().setSpacing(4)

        self.applyButton = QtWidgets.QPushButton("Apply")
        self.cancelButton = QtWidgets.QPushButton("Cancel")

        self.modeWidget = ModeWidget(parent=self)
        self.sliderValueLabel = QtWidgets.QLabel("")
        self.sliderValueLabel.setAlignment(QtCore.Qt.AlignRight)
        self.quickPicksWidget = QuickPicksWidget(parent=self)

        self.topLayout = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.LeftToRight)
        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setSpacing(6)
        self.layout().addLayout(self.topLayout)

        self.topLayout.addWidget(self.modeWidget)
        self.topLayout.addWidget(self.sliderValueLabel)
        self.topLayout.insertStretch(1, 1)

        # Maya has apply / cancel buttons in this order.
        self.confirmContainer.layout().addWidget(self.applyButton)
        self.confirmContainer.layout().addWidget(self.cancelButton)
        self.confirmContainer.hide()

        self.layout().addWidget(self.quickPicksWidget)
        self.layout().addWidget(self.sliderWidget)
        self.layout().addWidget(self.confirmContainer)

        if not _controller.settings.showSlider:
            self.sliderValueLabel.hide()

    def _connectSignals(self):
        def updateValueLabel(value):
            self.sliderValueLabel.setText(str(value))

        def closeConfigureMode(acceptChanges):
            if self._configuringUI:
                self.toggleConfigureMode(acceptChanges=acceptChanges)

        self.sliderWidget.valueChanged.connect(updateValueLabel)
        self.applyButton.released.connect(partial(closeConfigureMode, True))
        self.cancelButton.released.connect(partial(closeConfigureMode, False))

        self.modeWidget.modeChanged.connect(_controller.setMode)

        self.sliderWidget.sliderPressed.connect(self._onSliderPress)
        self.sliderWidget.sliderMoved.connect(self._onSliderMove)
        self.sliderWidget.sliderReleased.connect(self._onSliderRelease)
        self.quickPicksWidget.buttonClicked.connect(self._onQuickPick)

        def cleanup():
            try:
                _log.debug("Removing UI observer from controller dispatcher")
                _controller.dispatcher.removeObserver(self)
            except ValueError:
                # This should only happen if cleanup is called twice, or
                # the controller object gets recreated... which I
                # sometimes do when developing this module.
                _log.debug("Failed to remove UI observer from controller dispatcher")

        _controller.dispatcher.addObserver(self)
        self.destroyed.connect(cleanup)
        # QtCore.QCoreApplication.instance().aboutToQuit.connect(self._onClose)

    def receiveMessage(self, message):
        # Update UI with controller changes.
        # Allows for hotkeys triggers to update the UI
        if message.id == 'PercentChanged':
            if not self.sliderWidget.isSliding():
                self._onControllerUpdate()
        if message.id == 'EndSlide':
            self._onControllerUpdate()
        if message.id == 'ModeChanged':
            self._onControllerUpdate()

    def _onControllerUpdate(self):
        # Update from controller/settings
        _log.debug("Refreshing ui from controller change")
        self.modeWidget.refresh()
        self.sliderWidget.setValue(_controller.percent)
        self.sliderValueLabel.setText(str(_controller.percent))

    def _onQuickPick(self, value):
        if slideAnimationKeys.isFloatClose(value, 0.0):
            _controller.resetSlide()
        else:
            _controller.setSlide(
                value, absolute=_controller.settings.absoluteQuickPicks)

    def _onSliderPress(self, value):
        _controller.beginSlide(value)

    def _onSliderMove(self, value):
        _controller.slide(value)

    def _onSliderRelease(self):
        _controller.endSlide()

    def toggleConfigureMode(self, acceptChanges=True):
        self._configuringUI = not self._configuringUI
        if self._configuringUI:
            self.confirmContainer.show()
        else:
            self.confirmContainer.hide()
        self.quickPicksWidget.toggleConfigureMode(acceptChanges=acceptChanges)
        self.sliderWidget.toggleConfigureMode(acceptChanges=acceptChanges)
        self.modeWidget.toggleConfigureMode(acceptChanges=acceptChanges)

        self.sliderValueLabel.setEnabled(not self._configuringUI)
        if not _controller.settings.showSlider:
            self.sliderValueLabel.hide()
        else:
            self.sliderValueLabel.show()
        self.adjustSize()

    def restoreAllSettings(self):
        if self._configuringUI:
            _controller.settings.factoryReset()
            self.toggleConfigureMode(acceptChanges=False)

    def rightClickMenu(self, menu=None):
        if menu is None:
            menu = QtWidgets.QMenu()
        menu.addSeparator()

        if not self._configuringUI:
            configureAction = menu.addAction("Configure UI")
            restoreSettingsAction = object()
        else:
            configureAction = object()
            restoreSettingsAction = menu.addAction("Restore Everything to Default")

        action = super(SlideAnimationKeysWidget, self).rightClickMenu(menu=menu)
        if action == configureAction:
            self.toggleConfigureMode()
        elif action == restoreSettingsAction:
            answer = QtWidgets.QMessageBox.question(
                self, "Are you sure?", "This will reset all settings back to "
                "their defaults. This action cannot be undone.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)

            if answer == QtWidgets.QMessageBox.Yes:
                self.restoreAllSettings()

        return action


def ui(refresh=False):
    '''
    Launch the UI for slide animation keys.
    '''
    internal.ui.showWidget('slide_animation_keys_widget',
                        SlideAnimationKeysWidget,
                        refresh=refresh)


if __name__ == '__main__':
    ui(refresh=True)
