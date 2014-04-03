'''Slide Animation Keys is a tool that allows animators to quickly adjust keys.

It is also badly in need of a rewrite.

*******************************************************************************
    License and Copyright
    Copyright 2011-2014 Jordan Hueckstaedt
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

__author__ = 'Jordan Hueckstaedt'
__copyright__ = 'Copyright 2011-2014'
__license__ = 'LGPL v3'
__version__ = '1.96'
__email__ = 'AssumptionSoup@gmail.com'
__status__ = 'Beta'

import maya.cmds as cmd
import maya.OpenMaya as om
from functools import partial
import textwrap
import collections
import selectedAttributes


def setDefaultOptionVar(name, value):
    if not cmd.optionVar(exists=name):
        if isinstance(value, basestring):
            print name, 'is string'
            cmd.optionVar(sv=(name, value))
        elif isinstance(value, collections.Iterable):
            if len(value) > 0:
                if any(isinstance(v, basestring) for v in value):
                    cmd.optionVar(sv=(name, value[0]))
                    for i in range(1, len(value)):
                        cmd.optionVar(sva=(name, value[i]))
                else:
                    cmd.optionVar(fv=(name, value[0]))
                    for i in range(1, len(value)):
                        cmd.optionVar(fva=(name, value[i]))
        else:
            cmd.optionVar(fv=(name, value))


class SAKSettings(object):

    def __init__(self):
        self.modes = ['Blend', 'Average', 'Default', 'Shrink', 'Level', 'Linear']
        self.keys = {}
        self.undoState = 1
        self.shrinkWarning = False
        self.buildingSettings = 0
        self.sliding = 0
        self.lastPercent = 0
        self.mode = 'Blend'
        self.uiControl = {}

        # Get GUI Settings from option vars - set them if they don't exist
        setDefaultOptionVar('jh_sak_mode', self.modes[0])
        setDefaultOptionVar('jh_sak_realtime', 1)
        setDefaultOptionVar('jh_sak_resetOnApply', 0)
        setDefaultOptionVar('jh_sak_compoundPercentage', 0)
        setDefaultOptionVar('jh_sak_manualReload', 0)
        setDefaultOptionVar('jh_sak_absolute', 1)
        setDefaultOptionVar('jh_sak_findCurrentKeys', 1)
        setDefaultOptionVar('jh_sak_maxSlider', 100)
        setDefaultOptionVar('jh_sak_showSlider', 1)
        setDefaultOptionVar('jh_sak_showSliderField', 1)
        setDefaultOptionVar('jh_sak_showQuickPick', 1)
        setDefaultOptionVar('jh_sak_quickPickNums', [-100, -60, -30, 0, 30, 60, 100])

        # Load global settings from option vars.
        self.mode = cmd.optionVar(q='jh_sak_mode')
        self.realtime = cmd.optionVar(q='jh_sak_realtime')
        self.resetOnApply = cmd.optionVar(q='jh_sak_resetOnApply')
        self.compoundPercentage = cmd.optionVar(q='jh_sak_compoundPercentage')
        self.manualReload = cmd.optionVar(q='jh_sak_manualReload')
        self.showSlider = cmd.optionVar(q='jh_sak_showSlider')
        self.showSliderField = cmd.optionVar(q='jh_sak_showSliderField')
        self.showQuickPick = cmd.optionVar(q='jh_sak_showQuickPick')
        self.quickPickNums = cmd.optionVar(q='jh_sak_quickPickNums')
        self.maxSlider = cmd.optionVar(q='jh_sak_maxSlider')
        self.absolute = cmd.optionVar(q='jh_sak_absolute')
        self.findCurrentKeys = cmd.optionVar(q='jh_sak_findCurrentKeys')

        # This shouldn't happen anymore, but I accidentally made this
        # one a single number once, and it NEEDS to be an array.  So
        # this forces it.
        if not isinstance(self.quickPickNums, collections.Iterable):
            self.quickPickNums = [self.quickPickNums]
settings = SAKSettings()


def ui():
    """Slides the middle keys between three or more keys to the values of the
    first and last key. Works on multiple attributes and objects at once."""

    global settings

    sliderFieldLabel = 'jh_sak_sliderFieldLabel'
    modeDrop = 'jh_sak_modeDropDown'
    manualReload = 'jh_sak_manualReloadButton'
    maxLabel = 'jh_sak_maxLabel'
    maxField = 'jh_sak_maxField'
    applyButton = 'jh_sak_applyButton'
    quickPickButton = ['jh_sak_quickPickButton%s' % x for x in range(len(settings.quickPickNums))]
    quickPickInvert = 'jh_sak_quickPickInvert'

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

    lastMode = cmd.optionVar(q='jh_sak_mode')

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

    settings.uiControl['sliderField'] = cmd.intField(
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

    settings.uiControl['slider'] = cmd.intSlider(
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

    layout['af'].append((settings.uiControl['sliderField'], 'top', 5))
    layout['ac'].append((settings.uiControl['sliderField'], 'left', 5, sliderFieldLabel))
    layout['af'].append((settings.uiControl['sliderField'], 'right', 5))

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

    layout['ac'].append((settings.uiControl['slider'], 'top', 5, above))
    layout['af'].append((settings.uiControl['slider'], 'left', 5))
    layout['af'].append((settings.uiControl['slider'], 'right', 5))

    if settings.showSlider:
        above = settings.uiControl['slider']

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
    settings.buildingSettings = 1

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
    settings.buildingSettings = 0


def setSettings(controlValue, toggle=None):

    global settings
    if settings.buildingSettings:
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

        # Update Option Vars
        cmd.optionVar(fv=('jh_sak_absolute', absolute))
        cmd.optionVar(fv=('jh_sak_realtime', realtime))
        cmd.optionVar(fv=('jh_sak_resetOnApply', resetOnApply))
        cmd.optionVar(fv=('jh_sak_compoundPercentage', compoundPercentage))
        cmd.optionVar(fv=('jh_sak_maxSlider', maxSlider))
        cmd.optionVar(fv=('jh_sak_manualReload', manualReload))
        cmd.optionVar(fv=('jh_sak_findCurrentKeys', findCurrentKeys))
        cmd.optionVar(fv=('jh_sak_showSlider', showSlider))
        cmd.optionVar(fv=('jh_sak_showSliderField', showSliderField))
        cmd.optionVar(fv=('jh_sak_showQuickPick', showQuickPick))


        for x in range(len(quickPickNums)):
            if x == 0:
                cmd.optionVar(fv=('jh_sak_quickPickNums', quickPickNums[x]))
            else:
                cmd.optionVar(fva=('jh_sak_quickPickNums', quickPickNums[x]))

        # Update global vars
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
    if 'slider' in settings.uiControl and 'sliderField' in settings.uiControl:
        if value == None:
            if fromField == 'sliderField':
                if cmd.intField(settings.uiControl['sliderField'], ex=1):
                    value = cmd.intField(settings.uiControl['sliderField'], q=1, v=1)
            else:
                if cmd.intSlider(settings.uiControl['slider'], ex=1):
                    value = cmd.intSlider(settings.uiControl['slider'], q=1, v=1)

        if cmd.intSlider(settings.uiControl['slider'], ex=1):
            cmd.intSlider(settings.uiControl['slider'], e=1, v=value)
        if cmd.intField(settings.uiControl['sliderField'], ex=1):
            cmd.intField(settings.uiControl['sliderField'], e=1, v=value)
    return value


def startSlide(slideValue):
    global settings
    # Function called from slide GUI.  Helps efficiency by setting
    # sliding, so key checks during slide can be avoided.
    updateSliderGui(slideValue)

    if settings.realtime and settings.absolute:
        loadKeys()
        updateKeys()
    settings.sliding = 1


def endSlide(slideValue):
    global settings
    settings.sliding = 0
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
    if value == None:
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
    cmd.optionVar(sv=('jh_sak_mode', mode))

    # Update stuff according to UI change.
    if settings.realtime and settings.absolute:
        updateKeys()
        enableUndo()

    # Reset shrink mode not working warning every time we change mode.
    # It could be hours between the user changing modes.  They may have
    # forgotten the selection doesn't work. Okay, that may be an
    # unrealistic situation. Still, they might miss it or something.
    settings.shrinkWarning = False


def enableUndo(apply=None):
    """Undo is set up to ignore all the calls to updateKeys while sliding,
    making the function interactive, and still have the expected results
    on the undo queue.  Though this doesn't seem to work quite right yet,
    so beware!"""

    global settings
    if settings.realtime or apply:
        if not settings.undoState:
            try:
                cmd.undoInfo(cck=1)  # close chunk
            except TypeError:
                cmd.undoInfo(swf=1)  # turn undo back on
                cmd.undoInfo(q=1, un=0)  # needs this to work for some reason
            settings.undoState = 1


def disableUndo():
    global settings
    if settings.undoState:
        try:
            cmd.undoInfo(ock=1)  # Open chunk
        except TypeError:
            cmd.undoInfo(swf=0)  # turn undo off
        settings.undoState = 0


def isConsecutive(nList):
    return not [1 for x in range(1, len(nList)) if nList[x] - nList[x - 1] != 1]


def loadKeys(reload=0):
    # This function loads the currently selected keys.  It can be called
    # explicitly with reload = 1 or implicitly from other functions.  It
    # also tests if these new keys are the same as the old ones and
    # compares their values against the old ones.  If they have changed
    # it updates the keys, making things seamless and automatic for the
    # user.  This is so the user doesn't manually have to press a
    # "Reload Keys" button.

    # If the user is in the middle of sliding the slider or if there is
    # a manual reload button and it has NOT been pushed then skip
    # everything.
    global settings
    if settings.manualReload and not reload or settings.sliding:
        return

    newKeys = {}
    consecutive = True

    # Get keys for each attribute.
    keys = {}
    allKeys = {}
    selectedKeys = True
    attrs = []

    # Find selected keyframes if graph editor is open.
    if selectedAttributes.isGraphEditorVisible():
        attrs = cmd.keyframe(q=1, n=1, sl=1)

    # If none are selected, get any keys on the current frame that are
    # selected in the graph editor.  If the graph editor isn't open, get
    # what is selected in the channel box
    if attrs:
        for attr in attrs:
            keys[attr] = cmd.keyframe(attr, q=1, iv=1, sl=1)
            allKeys[attr] = cmd.keyframe(attr, q=1, iv=1)
    elif settings.findCurrentKeys:
        # Get selected
        attributes = selectedAttributes.get(detectionType='panel')
        # Get keyframe attrs from selected (Basically turns . to _ and
        # expands single objects to object attributes)
        attrs = []
        for att in attributes:
            att = cmd.keyframe(att, q=1, n=1)
            # Attributes can sometimes be None for some reason... So
            # check that.
            if att:
                attrs.extend(att)
        attrs = list(set(attrs))

        if attrs:
            # Find keyframes on current time.  If there are, add them to
            # keys
            time = cmd.currentTime(q=1)
            for attr in attrs:
                ky = cmd.keyframe(attr, q=1, iv=1, t=(time, time))
                if ky:
                    keys[attr] = ky
                    allKeys[attr] = cmd.keyframe(attr, q=1, iv=1)
            attrs = keys.keys()
            selectedKeys = False

    if not attrs:
        # No keys selected, and none under the current frame. Clear keys
        # so we don't operate later on them when nothing is selected.
        settings.keys = {}

    if attrs:
        changed = 0
        gKeys = settings.keys
        for attr in attrs:
            if keys[attr]:
                keys[attr].sort()
                allKeys[attr].sort()
                if not isConsecutive(keys[attr]):
                    consecutive = False
                # elif keys[attr][0] > allKeys[attr][0] or keys[attr][-1] < allKeys[attr][-1]:
                else:
                    first = 1
                    last = 1
                    if keys[attr][0] == allKeys[attr][0]:
                        first = 0
                    if keys[attr][-1] == allKeys[attr][-1]:
                        last = 0
                    keys[attr].insert(0, keys[attr][0] - first)
                    keys[attr].append(keys[attr][-1] + last)

                    newKeys[attr] = []

                    # Get default value
                    realNode = cmd.listConnections('%s.output' % attr, d=1, s=0, scn=1, p=1)[0].split('.')
                    default = cmd.attributeQuery(realNode[1], node=realNode[0], listDefault=1)[0]

                    # Test if keys are the same.  The test is in this
                    # section for efficiency.  Sorry it's less readable.
                    keyExisted = attr in gKeys.keys()
                    if not keyExisted or len(keys[attr]) != len(gKeys[attr]):
                        changed = 1

                    for x, key in enumerate(keys[attr]):
                        newKeys[attr].append({})
                        newKeys[attr][x]['key'] = key
                        newKeys[attr][x]['value'] = cmd.keyframe(attr, index=(key, key), q = 1, valueChange = 1)[0]
                        newKeys[attr][x]['time'] = cmd.keyframe(attr, index=(key, key), q = 1, timeChange = 1)[0]
                        newKeys[attr][x]['default'] = default
                        newKeys[attr][x]['endKey'] = (x == 0 and len(keys[attr]) > 1 and keys[attr][x + 1] == key) or (x == len(keys[attr]) - 1 and keys[attr][x - 1] == key)
                        newKeys[attr][x]['lastValue'] = newKeys[attr][x]['value']

                        if not changed and not reload:
                            # If keys are not on the same frame they have changed
                            if gKeys[attr][x]['key'] != key:
                                changed = 1
                            # If key is a start or end key and matches
                            # the next or previous key, it is a
                            # duplicate made on purpose.  lastValue will
                            # be changed on the real key in the middle.
                            # So the value check needs to be avoided for
                            # these duplicates.  These duplicates are
                            # made so that start and end keys can still
                            # be manipulated.
                            if not newKeys[attr][x]['endKey']:
                                # If keys do not have the same value, they have changed.
                                if round(gKeys[attr][x]['lastValue'], 5) != round(newKeys[attr][x]['value'], 5):
                                    changed = 1


    # Test if keys have changed.  If they have, reload them and set their defaults.
    if newKeys and not reload:
        if gKeys and not changed:
            if sorted(gKeys.keys()) != sorted(newKeys.keys()):
                changed = 1
            if not changed:
                # Don't do anything else, these are the same keys and
                # the user hasn't touched them.
                return

    # Keys will get reloaded beyond this point!
    settings.shrinkWarning = False

    # Find additional information needed for Shrink and Level function
    if newKeys:

        # Find Level Value and set the linear goals
        level = 0
        count = 0
        for attr in newKeys:
            startKey = newKeys[attr][0]
            endKey = newKeys[attr][-1]
            for key in range(1, len(newKeys[attr]) - 1):
                # Sum levels
                level += newKeys[attr][key]['value']
                count += 1

                # Linear goal
                # Find the value that is the linear interpolation of the
                # start key to the end key at the current frame
                totalTime = float(endKey['time'] - startKey['time'])
                try:
                    t = (newKeys[attr][key]['time'] - startKey['time']) / totalTime
                except ZeroDivisionError:
                    t = 0.0
                goal = (t * (endKey['value'] - startKey['value'])) + startKey['value']
                newKeys[attr][key]['linear'] = goal

        if count > 0:
            level /= count

        # Find out how many keys per attribute for shrink, and add level
        # to each key (it's the same value, but it doesn't make sense to
        # put it on a lower level)
        keys = []
        for attr in newKeys.keys():
            keys.append(len(newKeys[attr]))
            for key in newKeys[attr]:
                key['level'] = level

        center = []
        if len(set(keys)) == 1:
            count = []
            for attr in newKeys.keys():
                for x in range(len(newKeys[attr]) - 2):
                    if len(center) <= x:
                        center.append(0)
                        count.append(0)
                    center[x] += newKeys[attr][x + 1]['value']
                    count[x] += 1
            for x in range(len(center)):
                center[x] /= count[x]

        # Add shrink to newKeys
        for attr in newKeys.keys():
            for x in range(len(newKeys[attr]) - 2):
                if center:
                    newKeys[attr][x + 1]['shrink'] = center[x]
                else:
                    newKeys[attr][x + 1]['shrink'] = None

        # Let user know that shrink won't work.
        if not center:
            om.MGlobal.displayInfo('Shrink will not work for this selection.  Select the same number of keys for every attribute for shrink to work.')

        settings.keys = newKeys

        # Reset the GUI if appropriate.
        if reload and settings.absolute:
            updateSliderGui(0)

    # Update GUI or print warnings/errors
    if settings.keys:
        if not selectedKeys:
            om.MGlobal.displayInfo('Grabbed keys from current frame.')
    if not consecutive:
        om.MGlobal.displayWarning('All selected keys must be consecutive.')
    elif not settings.keys:
        om.MGlobal.displayError('You must select at least one key!')


def updateKeys(percent=None):
    global settings
    # Disable undo so setting multiple attributes don't rack up in the
    # undo queue
    disableUndo()

    if percent == None:
        percent = float(cmd.intSlider(settings.uiControl['slider'], q=1, v=1))

    if not settings.absolute and not settings.resetOnApply:
        if percent == 0.0:  # Zero is meant to be a reset of sorts.  On relative mode I don't know why someone would want to move keys by 0,
            settings.lastPercent = 0.0  # so if they try to do this, they're probably attempting to reset things.
        if settings.compoundPercentage:
            # Creates a bell curve between -100 and 100.  The top of the
            # bell curve is probably more of a point, with -100 and 100
            # being asymptotes. It's been awhile since I've done stuff
            # like this.  Quite frustrating.  I'm sure there's a better
            # way to do it.

            if settings.lastPercent == 0.0:
                # Avoid divide by zero messages.
                settings.lastPercent = 100.0

            negative = 0
            if percent < 0:
                negative = 1

            # Avoid divide by zero..
            if percent >= 100:
                percent = 99
            elif percent <= -100:
                percent = -99

            calc = 0
            if negative and 0 < settings.lastPercent < 100 or (not negative and -100 < settings.lastPercent < 0):
                # Inverse function to more and more quickly reverse percentages
                calc = 1
                if abs(percent) == 99:
                    newPercent = 100.0
                else:
                    newPercent = -1 * (settings.lastPercent / (abs(percent) / 100 - 1))

                # If the inverse function overshoots 100%, switch to regular function.
                if abs(newPercent) > 100:
                    calc = 0
            if not calc:
                newPercent = abs(settings.lastPercent) * (1 - abs(percent / 100.0))
                if negative:
                    newPercent = newPercent * - 1

            settings.lastPercent = newPercent
            percent = 1 - abs(newPercent) / 100

            if newPercent < 0:
                percent = percent * -1

        else:
            percent = settings.lastPercent + percent
            settings.lastPercent = percent
            percent = percent / 100.0
    else:
        percent = percent / 100.0

    blendUpPercent = percent
    blendDownPercent = percent
    if percent < 0:
        blendUpPercent = 0
        blendDownPercent *= -1
    else:
        blendDownPercent = 0


    mode = settings.mode
    # Force mode to average if percent is zero and reset on apply is set
    # and it is relative. This forces the key to the middle of the
    # surrounding keys when zero is pressed - like a reset button. Which
    # zero is always supposed to mean.  In my mind.  And tool :D I might
    # take this out if it just doesn't feel consistent enough.
    fakeReset = percent == 0.0 and settings.resetOnApply and not settings.absolute and mode == 'Blend'
    if fakeReset:
        mode = 'Average'

    canShrink = True
    for attr in settings.keys.keys():
        keyVal = blendDownPercent * settings.keys[attr][0]['value'] + blendUpPercent * settings.keys[attr][-1]['value']

        startKey = settings.keys[attr][0]
        endKey = settings.keys[attr][-1]
        for key in range(1, len(settings.keys[attr]) - 1):
            # Skip fake resets on end keys - they won't behave as the user expects (Halving the end key values instead of zeroing them)
            if fakeReset and ((key == 1 and settings.keys[attr][key - 1]['endKey']) or (key == len(settings.keys[attr]) - 2) and settings.keys[attr][key + 1]['endKey']):
                percent = 0
            elif fakeReset:
                percent = 1

            midKey = settings.keys[attr][key]
            if mode == 'Blend':
                keyValFin = midKey['value'] * (1 - abs(percent)) + keyVal
            elif mode == 'Average':
                keyValFin = midKey['value'] * (1 - percent) + ((startKey['value'] + endKey['value']) / 2) * percent
            elif mode == 'Default':
                keyValFin = midKey['value'] * (1 - percent) + midKey['default'] * percent
            elif mode == 'Shrink':
                if midKey['shrink']:
                    keyValFin = midKey['value'] * (1 - percent) + midKey['shrink'] * percent
                else:
                    canShrink = False
                    break
            elif mode == 'Level':
                keyValFin = midKey['value'] * (1 - percent) + midKey['level'] * percent
            elif mode == 'Linear':
                keyValFin = midKey['value'] * (1 - percent) + midKey['linear'] * percent

            cmd.keyframe(attr, a=1, valueChange=keyValFin, index=(midKey['key'], midKey['key']))
            settings.keys[attr][key]['lastValue'] = keyValFin
            if settings.resetOnApply and not settings.absolute:
                settings.keys[attr][key]['value'] = keyValFin
        if not canShrink:
            break

    # Raise warning ONCE if shrink won't work for selection
    if not canShrink and not settings.shrinkWarning:
        om.MGlobal.displayWarning('Shrink will not work for this selection.  Select the same number of keys for every attribute for shrink to work.')
        settings.shrinkWarning = True

if __name__ == '__main__':
    sak = SlideAnimationKeys()
    sak.ui()
