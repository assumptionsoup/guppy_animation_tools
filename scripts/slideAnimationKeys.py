'''Slide Animation Keys is a tool that allows animators to quickly adjust keys.

*******************************************************************************
    License and Copyright
    Copyright 2011-2017 Jordan Hueckstaedt
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

****************************************************************************'''

__version__ = '2.0'
from functools import partial
import collections
import copy
import textwrap

import maya.cmds as cmd
import maya.OpenMaya as om
import pymel.core as pm

from guppy_animation_tools import selectedAttributes, getLogger


_log = getLogger(__name__)


# From python 3.5 docs, isclose()
def isFloatClose(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


class PersistentSettings(object):
    '''
    Global persistent settings store.

    Uses pm.env.optionVars under the hood which may lead to some quirkieness.
    '''
    modes = ('Blend', 'Average', 'Default', 'Shrink', 'Level', 'Linear')
    _attrBindings = {
        'mode': 'jh_sak_mode',
        'realtime': 'jh_sak_realtime',
        'resetOnApply': 'jh_sak_resetOnApply',
        'compoundPercentage': 'jh_sak_compoundPercentage',
        'manualReload': 'jh_sak_manualReload',
        'showSlider': 'jh_sak_showSlider',
        'showSliderField': 'jh_sak_showSliderField',
        'showQuickPick': 'jh_sak_showQuickPick',
        'quickPickNums': 'jh_sak_quickPickNums',
        'maxSlider': 'jh_sak_maxSlider',
        'absolute': 'jh_sak_absolute',
        'findCurrentKeys': 'jh_sak_findCurrentKeys',
    }
    _defaultValues = {
        'mode': modes[0],
        'realtime': True,
        'resetOnApply': False,
        'compoundPercentage': False,
        'manualReload': False,
        'showSlider': True,
        'showSliderField': True,
        'showQuickPick': True,
        'quickPickNums': (-100, -60, -30, 0, 30, 60, 100),
        'maxSlider': 100,
        'absolute': True,
        'findCurrentKeys': True,
    }

    def __init__(self):
        # Settings are stored between sessions in option vars.
        for attr, optionVar in self._attrBindings.iteritems():
            pm.env.optionVars.setdefault(optionVar, self._defaultValues[attr])

        # This shouldn't happen anymore, but I accidentally made this
        # one a single number once, and it NEEDS to be an array.  So
        # this forces it.
        if not isinstance(self.quickPickNums, collections.Iterable):
            self.quickPickNums = [self.quickPickNums]

    def factoryReset(self):
        # Reset all settings back to their default values.

        for attr, optionVar in self._attrBindings.iteritems():
            try:
                pm.env.optionVars.pop(optionVar)
            except KeyError:
                # This should never execute. PyMel doesn't seem to have
                # implemented pop() following python convention - it
                # returns 0 if the key does not exist (and one if it
                # does), rather than raising an exception.
                pass
        self.__init__()

    def __getattribute__(self, attr):
        # Get option var attributes
        try:
            optionVarName = object.__getattribute__(self, '_attrBindings')[attr]
        except KeyError:
            return object.__getattribute__(self, attr)
        else:
            return pm.env.optionVars[optionVarName]

    def __setattr__(self, attr, value):
        # Set option var attributes
        try:
            optionVarName = self._attrBindings[attr]
        except KeyError:
            super(PersistentSettings, self).__setattr__(attr, value)
        else:
            pm.env.optionVars[optionVarName] = value


settings = PersistentSettings()


class GlobalState(object):
    def __init__(self):
        self.keys = {}
        self.undoState = True
        self.sliding = False
        self.prevPercent = 0.0

        # Delete Me
        self.buildingSettings = False
        self.uiControl = {}
        self.segmentCollection = SegmentCollection()


state = GlobalState()


def ui():
    """Slides the middle keys between three or more keys to the values of the
    first and last key. Works on multiple attributes and objects at once."""

    global settings

    sliderFieldLabel = 'jh_sak_sliderFieldLabel'
    modeDrop = 'jh_sak_modeDropDown'
    manualReload = 'jh_sak_manualReloadButton'
    applyButton = 'jh_sak_applyButton'
    quickPickButton = ['jh_sak_quickPickButton%s' % x for x in range(len(settings.quickPickNums))]

    if cmd.window('slideAnimationKeysWin', exists=1):
        cmd.deleteUI('slideAnimationKeysWin')

    # cmd.windowPref('slideAnimationKeysWin', remove = 1)
    cmd.window('slideAnimationKeysWin', w=380, h=100, s=1, tb=1, menuBar=1, t='Slide Animation Keys - v%s' % __version__)

    cmd.menu(label='Options')
    cmd.menuItem(label='Settings', c=settingsWin)
    cmd.menu(label='Help', helpMenu=1)
    cmd.menuItem(label='Usage', c=usageWin)
    cmd.menuItem(label='About', c=aboutWin)

    cmd.formLayout('jh_sak_formLay', numberOfDivisions=100)

    lastMode = settings.mode

    cmd.optionMenu(
        modeDrop,
        label='',
        cc=setMode)

    for mode in settings.modes:
        cmd.menuItem(label=mode)

    # Set mode dropdown to previous mode.
    cmd.optionMenu(
        modeDrop,
        e=1,
        sl=settings.modes.index(lastMode) + 1)

    cmd.button(
        manualReload,
        label='Reload Keys',
        vis=settings.manualReload,
        c=lambda *args: loadKeys(1))

    cmd.text(
        sliderFieldLabel,
        vis=settings.showSliderField,
        label='Custom Strength')

    state.uiControl['sliderField'] = cmd.intField(
        'jh_sak_sliderField',
        minValue=-1 * settings.maxSlider,
        maxValue=settings.maxSlider,
        value=0,
        vis=settings.showSliderField,
        cc=setSlide)

    for x in range(len(quickPickButton)):
        cmd.button(
            quickPickButton[x],
            vis=settings.showQuickPick,
            c=partial(setSlide, settings.quickPickNums[x], qp=1),
            label='%s%%' % settings.quickPickNums[x])

    state.uiControl['slider'] = cmd.intSlider(
        'jh_sak_sliderSlider',
        minValue=-1 * settings.maxSlider,
        maxValue=settings.maxSlider,
        value=0,
        vis=settings.showSlider,
        dc=lambda *args: startSlide(int(args[0])),  # Certain versions of Maya apparently pass INTslider values as UNICODE.  WTF
        cc=endSlide)

    # Apply button is on if it's not realtime in absolute mode and if
    # either the slider or the strength field are also on.
    cmd.button(
        applyButton,
        vis=(1 - settings.realtime * settings.absolute) * (1 - (1 - settings.showSlider) * (1 - settings.showSliderField)),
        c = partial(setSlide, apply=1),
        label = "Apply")

    #
    # Format the layout

    layout = {'af': [], 'ap': [], 'ac': []}

    layout['af'].append((modeDrop, 'top', 5))
    layout['af'].append((modeDrop, 'left', 5))
    layout['ap'].append((modeDrop, 'right', 5, 25))

    reloadWidth = 65
    if not settings.showSliderField:
        reloadWidth = 100
    elif not settings.manualReload:
        reloadWidth = 50

    layout['af'].append((manualReload, 'top', 5))
    layout['ap'].append((manualReload, 'left', 5, 25))
    layout['ap'].append((manualReload, 'right', 5, reloadWidth))

    layout['af'].append((sliderFieldLabel, 'top', 8))
    layout['ap'].append((sliderFieldLabel, 'left', 5, reloadWidth))

    layout['af'].append((state.uiControl['sliderField'], 'top', 5))
    layout['ac'].append((state.uiControl['sliderField'], 'left', 5, sliderFieldLabel))
    layout['af'].append((state.uiControl['sliderField'], 'right', 5))

    # Position quick picks
    totalDivisor = len(quickPickButton)
    moveAmount = 100.0 / totalDivisor
    middleAmount = 0
    if totalDivisor % 2 and totalDivisor > 1:
        middleAmount = moveAmount / 3.0
        moveAmount = (100.0 - moveAmount - middleAmount) / (totalDivisor - 1)

    moveBy = 0
    for x in range(len(quickPickButton)):
        startBuffer = 1
        if x == 0:
            startBuffer = 5
        layout['ac'].append((quickPickButton[x], 'top', 5, modeDrop))
        layout['ap'].append((quickPickButton[x], 'left', startBuffer, (moveBy)))
        moveBy = moveBy + moveAmount
        if x == len(quickPickButton) / 2:
            moveBy = moveBy + middleAmount
        layout['ap'].append((quickPickButton[x], 'right', 1, moveBy))

    above = modeDrop
    if settings.showQuickPick:
        above = quickPickButton[0]

    layout['ac'].append((state.uiControl['slider'], 'top', 5, above))
    layout['af'].append((state.uiControl['slider'], 'left', 5))
    layout['af'].append((state.uiControl['slider'], 'right', 5))

    if settings.showSlider:
        above = state.uiControl['slider']

    layout['ac'].append((applyButton, 'top', 5, above))
    layout['af'].append((applyButton, 'left', 5))
    layout['af'].append((applyButton, 'right', 5))


    cmd.formLayout(
        'jh_sak_formLay',
        e=1,
        **layout)
    cmd.showWindow('slideAnimationKeysWin')


def usageWin(controlValue):
    print "I haven't written this yet!  Wait for the final release.  Good luck!"


def aboutWin(controlValue):
    if cmd.window('jh_sak_aboutWin', exists=1):
        cmd.deleteUI('jh_sak_aboutWin')
    cmd.window('jh_sak_aboutWin', wh=(415, 285), s = 1, tb = 1, t = 'Slide Animation Keys Settings')

    cmd.scrollLayout('jh_sak_aboutScrollLay')
    cmd.formLayout('jh_sak_aboutFormLay', numberOfDivisions=100)

    # Playing with some auto-formatting stuff
    def splitParagraphByLine(paragraph, splitAt=75):
        paragraph = ''.join(about.splitlines())  # Remove line breaks
        paragraph = list(paragraph)
        x = 1
        lastSplit = 0
        while x < len(paragraph):
            if (x - lastSplit) % splitAt == 0:
                nextSplit = next((y for y in xrange(x - 1, x - splitAt - 1, - 1) if paragraph[y] == ' '), None)
                if nextSplit is not None:
                    paragraph[nextSplit] += '\n'
                    lastSplit = nextSplit
                    x = nextSplit
                elif nextSplit is None:
                    nextSplit = next((y for y in xrange(x, len(paragraph)) if paragraph[y] == ' '), None)
                    if nextSplit is not None and nextSplit > lastSplit:
                        paragraph[nextSplit] += '\n'
                        lastSplit = nextSplit
                        x = nextSplit
                    else:
                        break
                else:
                    break
            x += 1
        return''.join(paragraph)

    about = textwrap.dedent('''
            Slide Anim Keys was written by Jordan Hueckstaedt.  It came as a request from animator
            Riannon Delanoy along the lines of "Make an awesome key tweaker thing for Maya that
            works.  Oh yeah, and make it so everyone will like it". I took inspiration from my
            favorite Android apps where nearly everything is customizable.  It lead to a
            monster of a settings page, but now I'm pretty confident that if not the best, it
            will be a pretty damn impressive "Key Tweaker Thing" for anyone that wants one.''')

    about = splitParagraphByLine(about)

    footnote = textwrap.dedent('''Version %s\n
                Copyright 2011 Jordan Hueckstaedt\n
                Slide Animation Keys is released under a GPLv3 license''' % __version__)

    # cmd.paneLayout('jh_sak_aboutPane', configuration = 'single')
    cmd.text('jh_sak_aboutTitle', label='About', al='center', fn='tinyBoldLabelFont')
    cmd.text('jh_sak_aboutAbout', label=about, al='center')
    cmd.text('jh_sak_aboutFootnote', label=footnote, al='center')

    # cmd.scrollField('jh_sak_aboutTitle', wordWrap = 1, text = 'About', editable = 0, fn = 'tinyBoldLabelFont')
    layout = {'af': [], 'ap': [], 'ac': []}

    layout['af'].append(('jh_sak_aboutTitle', 'top', 5))
    layout['af'].append(('jh_sak_aboutTitle', 'left', 10))
    layout['af'].append(('jh_sak_aboutTitle', 'right', 10))

    layout['ac'].append(('jh_sak_aboutAbout', 'top', 5, 'jh_sak_aboutTitle'))
    layout['af'].append(('jh_sak_aboutAbout', 'left', 10))
    layout['af'].append(('jh_sak_aboutAbout', 'right', 10))
    layout['ac'].append(('jh_sak_aboutAbout', 'bottom', 20, 'jh_sak_aboutFootnote'))

    layout['af'].append(('jh_sak_aboutFootnote', 'left', 10))
    layout['af'].append(('jh_sak_aboutFootnote', 'right', 10))
    layout['af'].append(('jh_sak_aboutFootnote', 'bottom', 5))


    cmd.formLayout(
        'jh_sak_aboutFormLay',
        e=1,
        **layout)
    cmd.showWindow('jh_sak_aboutWin')


def settingsWin(controlValue=None):

    global settings
    state.buildingSettings = True

    if cmd.window('jh_sak_settingsWin', exists=1):
        cmd.deleteUI('jh_sak_settingsWin')
    cmd.window('jh_sak_settingsWin', wh=(400, 340), s = 1, tb = 1, t = 'Slide Animation Keys Settings')

    cmd.formLayout('jh_sak_settingsFormLay', numberOfDivisions=100)

    modeLabel = 'jh_sak_settingsModeLabel'
    absolute = 'jh_sak_settingsAbsolute'
    relative = 'jh_sak_settingsRelative'
    realtime = 'jh_sak_settingsRealtime'
    resetOnApply = 'jh_sak_settingsResetOnApply'
    compoundPercentage = 'jh_sak_settingsCompoundPercentage'
    manualReload = 'jh_sak_settingsManualReload'
    findCurrentKeys = 'jh_sak_settingsFindCurrentKeys'
    maxSlider = 'jh_sak_settingsMaxSlider'
    maxSliderLabel = 'jh_sak_settingsMaxSliderLabel'
    showSlider = 'jh_sak_settingsShowSlider'
    showSliderField = 'jh_sak_settingsShowSliderField'
    showQuickPick = 'jh_sak_settingsShowQuickPick'
    numQuickPick = 'jh_sak_settingsNumQuickPick'
    numQuickPickLabel = 'jh_sak_settingsNumQuickPickLabel'
    quickPickNums = settings.quickPickNums
    quickPick = ['jh_sak_settingsQuickPick%s' % x for x in range(len(quickPickNums))]
    applySettings = 'jh_sak_settingsApplySettingsButton'


    cmd.text(
        modeLabel,
        label='Mode')

    cmd.radioCollection()
    cmd.radioButton(
        absolute,
        label='Absolute',
        ann='Keys will move to their absolute positions.',
        cc=partial(setSettings, toggle='absolute'),
        sl=settings.absolute)
    cmd.radioButton(
        relative,
        label='Relative',
        ann='Keys will move relative to their last position, so each click becomes an additive effect.  Realtime mode should be disabled with this mode since the slider will act in a exponential way.',
        cc=partial(setSettings, toggle='absolute'),
        sl=1 - settings.absolute)

    cmd.checkBox(
        realtime,
        label='Realtime Mode',
        en=settings.absolute,
        ann='All the buttons will change keys immediately.  With the slider this will mean you can see the keys move.',
        value=settings.realtime)

    cmd.checkBox(
        resetOnApply,
        label='Reset Default Value',
        ann='The initial position is reset after each apply.  The effect is like Compound Percentage, but the starting position will not be remembered.',
        cc=partial(setSettings, toggle='resetOnApply'),
        en=(1 - settings.compoundPercentage) * (1 - settings.absolute),
        value = settings.resetOnApply)

    cmd.checkBox(
        compoundPercentage,
        label='Compound Percentages in Relative Mode',
        ann="When this is active with Relative Mode on, each move will move the keys less and less.  This mode can not overshoot keys.  Values over 100 will not do anything.",
        cc=partial(setSettings, toggle='compoundPercentage'),
        en=(1 - settings.resetOnApply) * (1 - settings.absolute),
        value = settings.compoundPercentage)

    cmd.checkBox(
        manualReload,
        label='Manually Load Keys',
        ann='Script no longer auto-loads selected keys.  A button must be pushed instead.',
        value=settings.manualReload)

    cmd.checkBox(
        findCurrentKeys,
        label='Use Keys on Current Frame.',
        ann='Script will look for keys on the current frame in the graph editor as well as selected keys.  Selected keys will still take precedent.  This does not need the graph editor open to work, so watch out.',
        value=settings.findCurrentKeys)

    cmd.text(
        maxSliderLabel,
        label='Maximum Slider Value')

    cmd.intField(
        maxSlider,
        minValue=1,
        ann='The maximum value the the slider and the custom strength field can go to',
        value=settings.maxSlider)

    cmd.checkBox(
        showSlider,
        label='Show Slider',
        value=settings.showSlider)

    cmd.checkBox(
        showSliderField,
        label='Show Custom Strength',
        value=settings.showSliderField)

    cmd.checkBox(
        showQuickPick,
        label='Show Quick Pick Buttons',
        cc=partial(setSettings, toggle='quickPick'),
        value=settings.showQuickPick)

    cmd.text(
        numQuickPickLabel,
        label='Number of quick pick buttons')

    cmd.intField(
        numQuickPick,
        en=settings.showQuickPick,
        minValue=1,
        value=len(quickPickNums))

    for x in range(len(quickPickNums)):
        cmd.intField(
            quickPick[x],
            en=settings.showQuickPick,
            value=quickPickNums[x])

    cmd.button(
        applySettings,
        label='Apply Settings',
        c=setSettings,
        ann='')

    layout = {'af': [], 'ap': [], 'ac': []}


    layout['af'].append((modeLabel, 'top', 5))
    layout['ap'].append((modeLabel, 'left', 5, 20))
    layout['ap'].append((modeLabel, 'right', 5, 30))

    layout['af'].append((absolute, 'top', 5))
    layout['ac'].append((absolute, 'left', 10, modeLabel))
    layout['ap'].append((absolute, 'right', 5, 55))

    layout['af'].append((relative, 'top', 5))
    layout['ac'].append((relative, 'left', 5, absolute))
    layout['af'].append((relative, 'right', 5))

    layout['ac'].append((realtime, 'top', 5, absolute))
    layout['af'].append((realtime, 'left', 5))

    layout['ac'].append((resetOnApply, 'top', 5, realtime))
    layout['af'].append((resetOnApply, 'left', 5))

    layout['ac'].append((compoundPercentage, 'top', 5, resetOnApply))
    layout['af'].append((compoundPercentage, 'left', 5))

    layout['ac'].append((maxSliderLabel, 'top', 5, compoundPercentage))
    layout['af'].append((maxSliderLabel, 'left', 5))

    layout['ac'].append((maxSlider, 'top', 5, compoundPercentage))
    layout['ac'].append((maxSlider, 'left', 5, maxSliderLabel))

    layout['ac'].append((manualReload, 'top', 5, maxSlider))
    layout['af'].append((manualReload, 'left', 5))

    layout['ac'].append((findCurrentKeys, 'top', 5, manualReload))
    layout['af'].append((findCurrentKeys, 'left', 5))

    layout['ac'].append((showSlider, 'top', 5, findCurrentKeys))
    layout['af'].append((showSlider, 'left', 5))

    layout['ac'].append((showSliderField, 'top', 5, showSlider))
    layout['af'].append((showSliderField, 'left', 5))

    layout['ac'].append((showQuickPick, 'top', 5, showSliderField))
    layout['af'].append((showQuickPick, 'left', 5))

    layout['ac'].append((numQuickPickLabel, 'top', 5, showQuickPick))
    layout['af'].append((numQuickPickLabel, 'left', 5))

    layout['ac'].append((numQuickPick, 'top', 5, showQuickPick))
    layout['ac'].append((numQuickPick, 'left', 5, numQuickPickLabel))

    for x in range(len(quickPick)):
        layout['ac'].append((quickPick[x], 'top', 5, numQuickPick))
        layout['ap'].append((quickPick[x], 'left', 5, x * 100 / len(quickPick)))
        layout['ap'].append((quickPick[x], 'right', 5, (x + 1) * 100 / len(quickPick)))

    layout['ac'].append((applySettings, 'top', 5, quickPick[0]))
    layout['af'].append((applySettings, 'left', 5))
    layout['af'].append((applySettings, 'right', 5))

    cmd.formLayout(
        'jh_sak_settingsFormLay',
        e=1,
        **layout)
    cmd.showWindow('jh_sak_settingsWin')
    state.buildingSettings = False


def setSettings(controlValue, toggle=None):

    global settings
    if state.buildingSettings:
        # Avoid recursive loop.  Not sure why this function can get
        # called DURING a gui creation, but it does.
        return

    quickPick = ['jh_sak_settingsQuickPick%s' % x for x in range(len(settings.quickPickNums))]

    # Enable/disable quick pick GUI fields.
    if toggle == 'quickPick':
        showQuickPick = cmd.checkBox('jh_sak_settingsShowQuickPick', q=1, v=1)
        for x in range(len(quickPick)):
            cmd.intField(quickPick[x], edit=1, en=showQuickPick)
        cmd.intField('jh_sak_settingsNumQuickPick', edit=1, en=showQuickPick)
    elif toggle == 'absolute':
        absolute = cmd.radioButton('jh_sak_settingsAbsolute', q=1, sl=1)
        reset = cmd.checkBox('jh_sak_settingsResetOnApply', q=1, v=1)
        compound = cmd.checkBox('jh_sak_settingsCompoundPercentage', q=1, v=1)
        cmd.checkBox('jh_sak_settingsRealtime', edit=1, en=absolute)
        cmd.checkBox('jh_sak_settingsCompoundPercentage', edit=1, en=(1 - absolute) * (1 - reset))
        cmd.checkBox('jh_sak_settingsResetOnApply', edit=1, en=(1 - absolute) * (1 - compound))
    elif toggle == 'resetOnApply':
        reset = cmd.checkBox('jh_sak_settingsResetOnApply', q=1, v=1)
        cmd.checkBox('jh_sak_settingsCompoundPercentage', edit=1, en=1 - reset)
    elif toggle == 'compoundPercentage':
        compound = cmd.checkBox('jh_sak_settingsCompoundPercentage', q=1, v=1)
        cmd.checkBox('jh_sak_settingsResetOnApply', edit=1, en=1 - compound)
    else:
        # Find values from GUI
        absolute = cmd.radioButton('jh_sak_settingsAbsolute', q=1, sl=1)
        realtime = cmd.checkBox('jh_sak_settingsRealtime', q=1, v=1)
        resetOnApply = cmd.checkBox('jh_sak_settingsResetOnApply', q=1, v=1)
        compoundPercentage = cmd.checkBox('jh_sak_settingsCompoundPercentage', q=1, v=1)
        maxSlider = cmd.intField('jh_sak_settingsMaxSlider', q=1, v=1)
        manualReload = cmd.checkBox('jh_sak_settingsManualReload', q=1, v=1)
        findCurrentKeys = cmd.checkBox('jh_sak_settingsFindCurrentKeys', q=1, v=1)
        showSlider = cmd.checkBox('jh_sak_settingsShowSlider', q=1, v=1)
        showSliderField = cmd.checkBox('jh_sak_settingsShowSliderField', q=1, v=1)
        showQuickPick = cmd.checkBox('jh_sak_settingsShowQuickPick', q=1, v=1)
        numQuickPick = cmd.intField('jh_sak_settingsNumQuickPick', q=1, v=1)

        # Correct these so they don't go under the minimum value.  Maya
        # isn't so great at avoiding minimum values.
        if numQuickPick < 1:
            numQuickPick = 1
        if maxSlider < 1:
            maxSlider = 1

        # Update number of quick picks.
        quickPickNums = []
        for field in quickPick:
            if cmd.intField(field, ex=1):
                quickPickNums.append(cmd.intField(field, q=1, v=1))

        if numQuickPick != len(quickPickNums):
            for x in range(abs(len(quickPickNums) - numQuickPick)):
                # Add or remove item alternating between beginning and
                # end of list.  Apparently, insert can be used to append
                # as well.
                if numQuickPick < len(quickPickNums):
                    quickPickNums.pop(-1 * (x % 2))
                elif numQuickPick > len(quickPickNums):
                    quickPickNums.insert(len(quickPickNums) * (x % 2), 0)

        # Update settings object
        settings.absolute = absolute
        settings.realtime = realtime
        settings.resetOnApply = resetOnApply
        settings.compoundPercentage = compoundPercentage
        settings.maxSlider = maxSlider
        settings.manualReload = manualReload
        settings.findCurrentKeys = findCurrentKeys
        settings.showSlider = showSlider
        settings.showSliderField = showSliderField
        settings.showQuickPick = showQuickPick
        settings.quickPickNums = quickPickNums

        # Update GUI.
        settingsWin()
        ui()

#
# Gui Wrapper Functions


def updateSliderGui(value=None, fromField=None):
    if 'slider' in state.uiControl and 'sliderField' in state.uiControl:
        if value is None:
            if fromField == 'sliderField':
                if cmd.intField(state.uiControl['sliderField'], ex=1):
                    value = cmd.intField(state.uiControl['sliderField'], q=1, v=1)
            else:
                if cmd.intSlider(state.uiControl['slider'], ex=1):
                    value = cmd.intSlider(state.uiControl['slider'], q=1, v=1)

        if cmd.intSlider(state.uiControl['slider'], ex=1):
            cmd.intSlider(state.uiControl['slider'], e=1, v=value)
        if cmd.intField(state.uiControl['sliderField'], ex=1):
            cmd.intField(state.uiControl['sliderField'], e=1, v=value)
    return value


def startSlide(slideValue):
    global settings
    # Function called from slide GUI.  Helps efficiency by setting
    # sliding, so key checks during slide can be avoided.
    updateSliderGui(slideValue)

    if settings.realtime and settings.absolute:
        loadKeys()
        updateKeys(float(cmd.intSlider(state.uiControl['slider'], q=1, v=1)))
    state.sliding = True


def endSlide(slideValue):
    global settings
    state.sliding = False
    enableUndo()


def setSlide(value, apply=None, qp=None, update=1):
    if not value and apply:
        value = updateSliderGui(fromField='sliderField')
    elif value and update:
        updateSliderGui(value, fromField='sliderField')
    elif update:
        updateSliderGui(value)

    # Perform action on keys if the mode is realtime, if the apply
    # button has been pushed, or if a quick pick button was pushed
    if (settings.realtime and settings.absolute) or apply or qp:
        loadKeys()
        updateKeys(value)
        enableUndo(apply=1)


def hotkey(value=None, update=0):
    # This is a wrapper for setSlide, to make the call more intuitive.
    if value is None:
        # Test if value can be had from gui.
        value = updateSliderGui()

        if value is None:
            # There is no GUI.  Exit.
            om.MGlobal.displayError("I'm afraid I can't do that Dave.  Open the GUI first.")
            return
    setSlide(value, qp=1, update=update)


def setMode(mode):
    # Save mode
    global settings
    settings.mode = mode

    # Update stuff according to UI change.
    if settings.realtime and settings.absolute:
        updateKeys(float(cmd.intSlider(state.uiControl['slider'], q=1, v=1)))
        enableUndo()


def enableUndo(apply=None):
    """Undo is set up to ignore all the calls to updateKeys while sliding,
    making the function interactive, and still have the expected results
    on the undo queue."""

    global settings
    if settings.realtime or apply:
        if not state.undoState:
            try:
                cmd.undoInfo(cck=1)  # close chunk
            except TypeError:
                cmd.undoInfo(swf=1)  # turn undo back on
                cmd.undoInfo(q=1, un=0)  # needs this to work for some reason
            state.undoState = 1


def disableUndo():
    global settings
    if state.undoState:
        try:
            cmd.undoInfo(ock=1)  # Open chunk
        except TypeError:
            cmd.undoInfo(swf=0)  # turn undo off
        state.undoState = 0


class Key(object):
    '''
    Represents a single key in Maya.

    Lazy loads most attributes that require information from Maya.

    Usually instantiated via the Curve object.
    '''
    def __init__(self, curve, index, selected):
        self.curve = curve
        self.index = index
        self.selected = selected
        self._cache = {}

    @classmethod
    def fromCurve(cls, curve):
        keys = []
        selectedIndexes = set(pm.keyframe(curve.name, query=1, indexValue=1, selected=1) or [])
        for index in pm.keyframe(curve.name, query=1, indexValue=1):
            selected = index in selectedIndexes
            key = cls(curve, index, selected)
            keys.append(key)
        return keys

    @property
    def time(self):
        try:
            self._cache['time']
        except KeyError:
            self._cache['time'] = pm.keyframe(
                self.curve.name,
                query=True,
                index=(self.index, self.index),
                timeChange=True)[0]
        return self._cache['time']

    @property
    def value(self):
        try:
            self._cache['value']
        except KeyError:
            self._cache['value'] = pm.keyframe(
                self.curve.name, query=True, absolute=True, valueChange=True,
                index=(self.index, self.index))[0]
        return self._cache['value']

    @value.setter
    def value(self, value):
        # I'm still torn if this should be a property or an explicit
        # setter because we are setting state in Maya.
        self._cache['value'] = value
        pm.keyframe(self.curve.name, absolute=1, valueChange=value,
                    index=(self.index, self.index))

    def isFirst(self):
        '''
        Is this key the first key on a curve?
        '''
        return self.index == 0

    def isLast(self):
        '''
        Is this key the last key on a curve?
        '''

        # How to query maya for this info:
        # totalKeys = self.curve.node.keyTimeValue.numElements()
        # I'm going to trust the curve for now, it should be quicker.
        return len(self.curve.keys) - 1 == self.index

    def __eq__(self, other):
        if not isinstance(other, Key):
            return NotImplemented

        # Does not test that the DATA is the same, but that these
        # represent the same keys.
        return self.curve == other.curve and self.index == other.index

    def __str__(self):
        return '%s:%s' % (self.curve.name, self.index)

    def __repr__(self):
        return str(self)


class Curve(object):
    '''
    Represents an entire animation curve in Maya.

    Holds data about the curve node, and the attribute associated with
    that curve, and every key on the curve.

    Lazy loads most attributes that require information from Maya.

    Should be instantiated by the factory method `detectCurves` or
    `fromAttribute`.
    '''
    def __init__(self, name, keys=None):
        self.name = name

        # Keys are read-only.  The expectation is that SAK will refresh
        # objects rather than expect this object to sync state with Maya
        self.keys = tuple(keys) if keys else tuple()

    @property
    def node(self):
        # Lazily fetch the pymel curve node
        try:
            self._node
        except AttributeError:
            self._node = pm.PyNode(self.name)
        return self._node

    @property
    def attribute(self):
        # Lazily fetch the pymel attribute this curve is connected to
        try:
            self._attribute
        except AttributeError:
            attribute = selectedAttributes.getFirstConnection(
                self.name, attribute='output', outAttr=True, findAttribute=True)
            self._attribute = pm.PyNode(attribute)

        return self._attribute

    def selectedKeys(self):
        for key in self.keys:
            if key.selected:
                yield key

    @property
    def defaultValue(self):
        try:
            # Cache the results - we'll rely on the rest of SAK to
            # refresh curves often enough that cache-invalidation
            # shouldn't become an issue
            self._defaultValue
        except AttributeError:
            # Get the default value of this attribute / curve
            defaultValues = pm.attributeQuery(
                self.attribute.attrName(),
                node=self.attribute.node(),
                listDefault=True)

            # I don't think our animation curve node will every be connected
            # to a compound attribute, so it should be safe to return the
            # first value only.
            self._defaultValue = defaultValues[0]
        return self._defaultValue

    @classmethod
    def fromAttribute(cls, attribute):
        '''
        Returns a list of curves associated with an attribute.
        '''
        curveNames = pm.keyframe(attribute, query=1, name=1) or []
        curves = []
        for curveName in curveNames:
            curve = cls(curveName)
            curve.keys = Key.fromCurve(curve)
            curves.append(curve)
        return curves

    @classmethod
    def detectCurves(cls):
        curves = []
        # Find selected keyframes if graph editor is open.
        graphEditor = selectedAttributes.GraphEditorInfo.detect(restrictToVisible=True)
        if graphEditor.isValid():
            _log.debug("Searching for selected keys")
            # Find curves with selected keys
            for attr in pm.keyframe(query=1, name=1, selected=1) or []:
                curves.extend(cls.fromAttribute(attr))

        if not curves and settings.findCurrentKeys:
            # Nothing selected, set keys on current frame as selected
            _log.debug("No keys selected, grabbing from current frame")
            for attr in selectedAttributes.get(detectionType='panel'):
                curves.extend(cls.fromAttribute(attr))

            time = pm.currentTime(query=1)
            for x in reversed(range(len(curves))):
                keyIndices = pm.keyframe(curves[x].name, query=1, indexValue=1, time=(time, time))
                if keyIndices:
                    curves[x].keys[keyIndices[0]].selected = True
                else:
                    # Remove curves that have no keys on the current frame
                    curves.pop(x).name
        return curves

    def __eq__(self, other):
        if not isinstance(other, Curve):
            return NotImplemented
        return other.name == self.name


class SegmentKey(Key):
    '''
    A Key that is doubly linked with a CurveSegment and/or SegmentCollection.

    Contains extra attributes that transparently access segments /
    collections for calculations that involve more than a single key.
    '''
    def __init__(self, key, segment=None):
        super(SegmentKey, self).__init__(key.curve, key.index, key.selected)
        # Segment keys are doubly linked with their segement to allow
        # for lazy loading and caching of data generated over segments
        self.segment = segment
        self._cache = copy.copy(key._cache)

    @property
    def originalValue(self):
        try:
            self._cache['originalValue']
        except KeyError:
            self._cache['originalValue'] = self.value
        return self._cache['originalValue']

    @Key.value.setter
    def value(self, value):
        self.originalValue  # ensure original value is cached before changing.
        # super(SegmentKey, type(self)).value.fset(self, value)
        Key.value.fset(self, value)

    @property
    def levelValue(self):
        try:
            return self.segment.collection.levelValue
        except AttributeError:
            raise ValueError('Key/Segment is not linked to collection.  '
                             'Cannot find level value.')

    @property
    def linearValue(self):
        try:
            return self.segment.collection.getLinearValue(self)
        except AttributeError:
            raise ValueError('Key/Segment is not linked to collection.  '
                             'Cannot find linear value.')

    @property
    def shrinkValue(self):
        try:
            return self.segment.collection.getShrinkValue(self)
        except AttributeError:
            raise ValueError('Key/Segment is not linked to collection.  '
                             'Cannot find shrink value.')

    def __hash__(self):
        # Maya can't have spaces or dashes in the name, which helps us
        # guarantee that our index hash won't collide with a weirdly
        # named curve
        return hash('%s - %s' % (self.index, self.segment.curve.name))


class CurveSegment(object):
    '''
    A segment of an animation curve.

    A curve segment contains sequential keys in an animation curve. It
    may contain a partial collection of keys, or the entire curve.

    A CurveSegment is doubly linked with the collection that (may)
    contain it, and the SegmentKeys it contains.  This allows caching
    and calculation of various values across keys, segments, and
    collections.
    '''
    def __init__(self, curve, keys, collection=None):
        self.collection = collection
        self.curve = curve
        self.keys = tuple(SegmentKey(key, segment=self) for key in keys)
        self._cache = {}

        # Find neighboring keys
        lastKey = self.keys[-1]
        firstKey = self.keys[0]
        if lastKey.isLast():
            # lastKey is the last key in the curve
            self.neighborRight = lastKey
        else:
            self.neighborRight = curve.keys[lastKey.index + 1]

        if firstKey.isFirst():
            # firstKey is the first key in the curve
            self.neighborLeft = firstKey
        else:
            self.neighborLeft = curve.keys[firstKey.index - 1]

    @classmethod
    def fromCurve(cls, curve, collection=None):
        '''
        Returns a list of CurveSegment objects for every set of
        consecutive keys selected.
        '''
        lastIndex = None
        blenders = []
        keys = []

        for key in curve.selectedKeys():
            if lastIndex is not None:
                if lastIndex + 1 != key.index:
                    # Non-consecutive key, create CurveSegment and restart
                    # key finding process
                    blenders.append(cls(curve, keys, collection=collection))
                    keys = [key]
                    continue
            keys.append(key)
            lastIndex = key.index

        if keys:
            blenders.append(cls(curve, keys, collection=collection))
        return blenders

    def valueAtTime(self, time):
        try:
            timing = self._cache['timing']
        except KeyError:
            timing = self._cache['timing'] = {}

            # Fill out timing with existing keys first
            for key in self.keys:
                timing[key.time] = key.value

        try:
            return timing[time]
        except KeyError:
            # This time doesn't have a key, resort to querying Maya.

            # API method does not account for UI units (degrees vs radians,
            # millimeters vs centimeters, etc.)
            # mfn = self.curve.node.__apimfn__()
            # value = timing[time] = mfn.evaluate(pm.api.MTime(time))

            value = pm.keyframe(self.curve.name, query=True,
                                eval=True, absolute=True, t=(time, time))[0]
            return value


class SegmentCollection(object):
    '''
    A collection of curve segments.

    Collects and detects curve segments.  Can perform calculations and
    caching of various data that requires knowing about all segments.

    Doubly linked with all owned segments.
    '''
    def __init__(self, segments=None):
        self.segments = segments or []
        self._cache = {}

    def _cacheLevelAndLinear(self):
        try:
            self._cache['levelValue']
            self._cache['linearValues']
        except KeyError:
            self._cache['levelValue'] = 0.0
            self._cache['linearValues'] = {}
        else:
            # Already cached.
            return

        # Find Level Value and set the linear goals
        valueTotal = 0.0
        keyCount = 0
        for segment in self.segments:
            totalTime = float(segment.neighborRight.time - segment.neighborLeft.time)
            valueChange = segment.neighborRight.value - segment.neighborLeft.value
            for key in segment.keys:
                valueTotal += key.value
                keyCount += 1

                # Linear goal
                # Find the value that is the linear interpolation of the
                # start key to the end key at the current frame
                try:
                    t = (key.time - segment.neighborLeft.time) / totalTime
                except ZeroDivisionError:
                    t = 0.0
                self._cache['linearValues'][key] = t * valueChange + segment.neighborLeft.value

        try:
            self._cache['levelValue'] = valueTotal / keyCount
        except ZeroDivisionError:
            self._cache['levelValue'] = 0.0

    def _cacheShrink(self):
        try:
            self._cache['shrinkValues']
            shrinkCache = self._cache['shrinkTiming']
        except KeyError:
            self._cache['shrinkValues'] = {}
            shrinkCache = self._cache['shrinkTiming'] = {}
        else:
            # Already cached.
            return

        for segment in self.segments:
            for key in segment.keys:
                time = key.time
                try:
                    shrinkValue = shrinkCache[time]
                except KeyError:
                    total = sum(segment.valueAtTime(time) for segment in self.segments)
                    shrinkValue = shrinkCache[time] = total / float(len(self.segments))

                self._cache['shrinkValues'][key] = shrinkValue

    def hasSelectionChanged(self, otherCollection):
        if len(otherCollection.segments) != len(self.segments):
            # Different number of curves selected
            _log.debug('hasSelectionChanged: Segment number mismatch')
            return True

        def curveSegmentMap(collection):
            segmentMap = {}  # curve name : [segment, segment]
            for segment in collection.segments:
                segmentMap.setdefault(segment.curve.name, []).append(segment)

            # sort multiple segments by starting key.
            for segments in segmentMap.itervalues():
                segments.sort(key=lambda segment: segment.keys[0].index)
            return segmentMap

        otherSegmentMap = curveSegmentMap(otherCollection)
        thisSegmentMap = curveSegmentMap(self)

        if set(otherSegmentMap.iterkeys()) != set(thisSegmentMap.iterkeys()):
            # Different attributes / curves selected
            _log.debug('hasSelectionChanged: Curve name mismatch')
            return True

        for curveName in otherSegmentMap.iterkeys():
            otherSegments = otherSegmentMap[curveName]
            theseSegments = thisSegmentMap[curveName]
            if len(otherSegments) != len(theseSegments):
                _log.debug('hasSelectionChanged: Segments number mismatch')
                return True

            for x in xrange(len(otherSegments)):
                otherSegment = otherSegments[x]
                thisSegment = theseSegments[x]

                if [k.index for k in otherSegment.keys] != [k.index for k in thisSegment.keys]:
                    # Different keys selected
                    _log.debug('hasSelectionChanged: Key index mismatch')
                    return True
                for x in xrange(len(otherSegment.keys)):
                    if not isFloatClose(otherSegment.keys[x].value, thisSegment.keys[x].value):
                        # Key values do not align with cached state
                        _log.debug('hasSelectionChanged: key values mismatch')
                        return True
        _log.debug('hasSelectionChanged: No change.')
        return False

    @property
    def levelValue(self):
        self._cacheLevelAndLinear()
        return self._cache['levelValue']

    def getLinearValue(self, key):
        self._cacheLevelAndLinear()
        # I could have injected this value onto the key,
        # but I like this a little better, because it's more clear
        # where this value came from.
        try:
            return self._cache['linearValues'][key]
        except KeyError:
            raise KeyError('Key %r is not in this collection', key)

    def getShrinkValue(self, key):
        self._cacheShrink()
        try:
            return self._cache['shrinkValues'][key]
        except KeyError:
            # I like KeyError here.  It seems appropriate.
            raise KeyError('Key %r is not in this collection', key)

    @classmethod
    def detect(cls):
        '''
        Detect the currently selected keys/curve segments in Maya.

        Returns a SegmentCollection.  SegmentCollection may not have any
        segment associated with it, if the user's selection is empty.
        '''
        curves = Curve.detectCurves()
        collection = cls()

        for curve in curves:
            collection.segments.extend(
                CurveSegment.fromCurve(curve, collection=collection))
        return collection


def loadKeys(reload=False):
    '''
    Reload selected keys in global state.

    If reload=True, performs a force reload.  Otherwise, it will attempt
    to detect if a reload is needed.
    '''

    # If the user is in the middle of sliding the slider or if there is
    # a manual reload button and it has NOT been pushed then skip
    # everything.
    global settings
    if settings.manualReload and not reload or state.sliding:
        return

    # Get keys for each attribute.
    segmentCollection = SegmentCollection.detect()
    if not segmentCollection.segments:
        state.segmentCollection = segmentCollection
        # No keys selected, and none under the current frame. Clear keys
        # so we don't operate later on them when nothing is selected.
        om.MGlobal.displayError('You must select at least one key!')
        return

    # Test if keys have changed in some way (by value, because the user
    # changed something, or by a selection change).
    if (not reload and state.segmentCollection and
            not segmentCollection.hasSelectionChanged(state.segmentCollection)):
        return

    # Update state with new keys
    state.segmentCollection = segmentCollection

    # TODO: Get this gui code out of here.  This has bad smells.
    if reload and settings.absolute:
        updateSliderGui(0)


def updateKeys(percent):
    global settings
    # Disable undo so setting multiple attributes don't rack up in the
    # undo queue
    disableUndo()

    percent = percent / 100.0

    blendUpPercent = percent
    blendDownPercent = abs(percent)
    if percent < 0:
        blendUpPercent = 0
    else:
        blendDownPercent = 0


    mode = settings.mode.lower()

    for segment in state.segmentCollection.segments:

        neighborAvg = (segment.neighborLeft.value + segment.neighborRight.value) / 2.0
        keyVal = blendDownPercent * segment.neighborLeft.value + blendUpPercent * segment.neighborRight.value
        for key in segment.keys:

            keyValue = key.originalValue
            if not settings.absolute and not isFloatClose(percent, 0.0):
                # Use the previous value when relative resetOnApply is active,
                # EXCEPT when percent == 0.0 - in that case the user probably
                # wants to reset back to the original values, as a "relative"
                # percent of 0 would do nothing.
                keyValue = key.value

            if mode == 'blend':
                newValue = keyValue * (1 - abs(percent)) + keyVal
            elif mode == 'average':
                newValue = keyValue * (1 - percent) + neighborAvg * percent
            elif mode == 'default':
                newValue = keyValue * (1 - percent) + segment.curve.defaultValue * percent
            elif mode == 'shrink':
                newValue = keyValue * (1 - percent) + key.shrinkValue * percent
            elif mode == 'level':
                newValue = keyValue * (1 - percent) + state.segmentCollection.levelValue * percent
            elif mode == 'linear':
                newValue = keyValue * (1 - percent) + key.linearValue * percent
            key.value = newValue


if __name__ == '__main__':
    ui()
