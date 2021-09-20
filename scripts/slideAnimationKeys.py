'''
Slide Animation Keys is a tool that allows animators to quickly adjust keys.

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


'''

__version__ = '2.0'

from itertools import izip
import collections
import copy

import pymel.core as pm

from guppy_animation_tools import selectedAttributes, getLogger, internal


_log = getLogger(__name__)

# From python 3.5 docs, isclose()
def isFloatClose(a, b, rel_tol=1e-09, abs_tol=0.0):
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def lerp(a, b, alpha):
    return (b - a) * alpha + a

def easeInCubic(alpha):
    return alpha ** 3

def easeOutCubic(alpha):
    return 1 - (1.0 - alpha) ** 3

def easeInOutCubic(alpha):
    if alpha < 0.5:
        return 4.0 * alpha ** 3
    else:
        return 1.0 - (-2.0 * alpha + 2.0) ** 3 / 2.0

class PersistentSettings(object):
    '''
    Global persistent settings store.

    Uses pm.env.optionVars under the hood which may lead to some quirkieness.
    '''
    modes = ('blend', 'shift', 'average', 'default', 'shrink', 'level', 'linear', 'ease', 'ease in/out')
    _attrBindings = {
        'mode': 'jh_sak_mode',
        'showSlider': 'jh_sak_showSlider',
        'showQuickPick': 'jh_sak_showQuickPick',
        'quickPickNums': 'jh_sak_quickPickNums',
        'sliderMax': 'jh_sak_maxSlider',
        'sliderMin': 'jh_sak_minSlider',
        'absoluteQuickPicks': 'jh_sak_absolute',
        'findCurrentKeys': 'jh_sak_findCurrentKeys',
        'uiGeometry': 'jh_sak_uiGeometry',
    }
    _defaultValues = {
        'mode': modes[0],
        'showSlider': True,
        'showQuickPick': True,
        'quickPickNums': (-100, -50, -20, 0, 20, 50, 100),
        'sliderMax': 100,
        'sliderMin': -100,
        'absoluteQuickPicks': False,
        'findCurrentKeys': True,
        'uiGeometry': [],
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
            value = pm.env.optionVars[optionVarName]
            if attr == 'modes':
                # Fix legacy capitalization
                value = [mode.lower() for mode in value]
            return value

    def __setattr__(self, attr, value):
        # Set option var attributes
        try:
            optionVarName = self._attrBindings[attr]
        except KeyError:
            super(PersistentSettings, self).__setattr__(attr, value)
        else:
            pm.env.optionVars[optionVarName] = value


# Global state
_settings = PersistentSettings()


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
    def detectCurves(cls, forceSelectedKeys=False):
        curves = []
        # Find selected keyframes if graph editor is open.
        graphEditor = selectedAttributes.GraphEditorInfo.detect(restrictToVisible=True)
        if graphEditor.isValid() or forceSelectedKeys:
            _log.debug("Searching for selected keys")
            # Find curves with selected keys
            for attr in pm.keyframe(query=1, name=1, selected=1) or []:
                curves.extend(cls.fromAttribute(attr))

        if not curves and _settings.findCurrentKeys:
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

    @property
    def defaultValue(self):
        try:
            return self.segment.curve.defaultValue
        except AttributeError:
            raise ValueError('Key/Segment is not linked to collection.  '
                             'Cannot find shrink value.')

    @property
    def easeInValue(self):
        try:
            return self.segment.collection.getEaseInValue(self)
        except AttributeError:
            raise ValueError('Key/Segment is not linked to collection.  '
                             'Cannot find ease in value.')

    @property
    def easeOutValue(self):
        try:
            return self.segment.collection.getEaseOutValue(self)
        except AttributeError:
            raise ValueError('Key/Segment is not linked to collection.  '
                             'Cannot find ease out value.')

    @property
    def easeInOutValue(self):
        try:
            return self.segment.collection.getEaseInOutValue(self)
        except AttributeError:
            raise ValueError('Key/Segment is not linked to collection.  '
                             'Cannot find ease in/out value.')

    def __hash__(self):
        # Maya can't have spaces or dashes in the name, which helps us
        # guarantee that our index hash won't collide with a weirdly
        # named curve
        return hash('%s - %s' % (self.index, self.segment.curve.name))

    def isEquivalent(self, other):
        if not isinstance(other, SegmentKey):
            raise NotImplementedError

        if self.curve.name != other.curve.name:
            _log.debug('Keys curve mismatch %s %s', self, other)
            return False
        if self.index != other.index:
            _log.debug('Keys index mismatch %s %s', self, other)
            return False
        if not isFloatClose(self.value, other.value):
            _log.debug('Keys value mismatch %s %s', self, other)
            return False
        if self.time != other.time:
            _log.debug('Keys time mismatch %s %s', self, other)
            return False
        return True


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
            self.neighborRight = SegmentKey(curve.keys[lastKey.index + 1])

        if firstKey.isFirst():
            # firstKey is the first key in the curve
            self.neighborLeft = firstKey
        else:
            self.neighborLeft = SegmentKey(curve.keys[firstKey.index - 1])

    @property
    def totalTimeInclusive(self):
        '''
        Return total time including immediate neighbors
        '''
        try:
            totalTime = self._cache['totalTime']
        except KeyError:
            totalTime = self._cache['totalTime'] = float(self.neighborRight.time - self.neighborLeft.time)
        return totalTime

    def getTimeAsPercentInclusive(self, key):
        '''
        Return 0-1 value representing the key's palcement along curve segment in time.
        '''
        currentTime = key.time - self.neighborLeft.time
        return currentTime / self.totalTimeInclusive

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

    def isEquivalent(self, other):
        # Different from __eq__ - we only test that the key indexes and
        # current values match - not the original context
        if not isinstance(other, CurveSegment):
            raise NotImplementedError

        if self.curve.name != other.curve.name:
            return False

        if len(self.keys) != len(other.keys):
            _log.debug('Segment num keys mismatch')
            return False

        if (not self.neighborLeft.isEquivalent(other.neighborLeft) or
                not self.neighborRight.isEquivalent(other.neighborRight)):
            _log.debug('Segment key equivalence mismatch')
            return False

        for thisKey, otherKey in izip(self.keys, other.keys):
            if not thisKey.isEquivalent(otherKey):
                _log.debug('Segment key equivalence mismatch')
                return False
        return True


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

    def _findEase(self, easeFunc):
        easeGoals = {}

        for segment in self.segments:
            for key in segment.keys:
                # Should we be normalizing time across all curves?
                # Or let each curve ease on its own timeline?
                percentTime = segment.getTimeAsPercentInclusive(key)
                easeGoals[key] = lerp(
                    segment.neighborLeft.value,
                    segment.neighborRight.value,
                    easeFunc(percentTime))
        return easeGoals

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

    def hasSelectionChanged(self, other):
        if len(other.segments) != len(self.segments):
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

        otherSegmentMap = curveSegmentMap(other)
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

            for thisSegment, otherSegment in izip(theseSegments, otherSegments):
                if not thisSegment.isEquivalent(otherSegment):
                    _log.debug('hasSelectionChanged: segment equivalence mismatch')
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

    def getEaseInValue(self, key):
        try:
            self._cache['easeIn']
        except KeyError:
            self._cache['easeIn'] = self._findEase(easeInCubic)

        try:
            return self._cache['easeIn'][key]
        except KeyError:
            raise KeyError('Key %r is not in this collection', key)

    def getEaseOutValue(self, key):
        try:
            self._cache['easeOut']
        except KeyError:
            self._cache['easeOut'] = self._findEase(easeOutCubic)

        try:
            return self._cache['easeOut'][key]
        except KeyError:
            raise KeyError('Key %r is not in this collection', key)

    def getEaseInOutValue(self, key):
        try:
            self._cache['easeInOut']
        except KeyError:
            self._cache['easeInOut'] = self._findEase(easeInOutCubic)

        try:
            return self._cache['easeInOut'][key]
        except KeyError:
            raise KeyError('Key %r is not in this collection', key)

    @classmethod
    def detect(cls, forceSelectedKeys=False):
        '''
        Detect the currently selected keys/curve segments in Maya.

        Returns a SegmentCollection.  SegmentCollection may not have any
        segment associated with it, if the user's selection is empty.
        '''
        curves = Curve.detectCurves(forceSelectedKeys=forceSelectedKeys)
        collection = cls()

        for curve in curves:
            collection.segments.extend(
                CurveSegment.fromCurve(curve, collection=collection))
        return collection


class SlideKeysController(object):
    '''
    Stateful controller that provides an interface between the UI / hotkeys
    and Maya.

    Is also a model in the sense that it stores the sliding state, but
    if you look at it as Maya being the model, then this could be
    a controller...
    '''
    def __init__(self):
        self._absolutePercent = 0.0  # 0-100, not 0-1
        self._isSliding = False
        self._segmentCollection = SegmentCollection()
        self._undoChunk = internal.UndoChunk()
        self._relativeValueCache = {}
        self.settings = _settings
        self._mode = self.settings.mode.lower()
        self.dispatcher = internal.observer.Dispatcher()


    @property
    def percent(self):
        return self._absolutePercent

    def detectKeys(self, force=False):
        '''
        Reload selected keys from Maya.  Returns True if keys were
        changed False if they were kept the same.

        Detects if a reload is needed if force keyword is not True.
        '''

        # Skip detection while sliding keys (unless forced to)
        if self._isSliding and not force:
            return

        # Get keys for each attribute.
        segmentCollection = SegmentCollection.detect()
        if not segmentCollection.segments:
            # No keys selected, warn the user, but still change
            # key state (to no keys)
            _log.warn('You must select at least one key!')

        # Test if keys have changed in some way (by value, because the user
        # changed something, or by a selection change).
        elif (not force and self._segmentCollection and
                not segmentCollection.hasSelectionChanged(self._segmentCollection)):
            return False

        _log.debug('Refreshing Keys')
        # Update state with new keys
        self._segmentCollection = segmentCollection
        self._relativeValueCache = {}
        self.dispatcher.send(self, 'KeysReloaded')
        return True

    def setMode(self, mode):
        mode = mode.lower()

        # controller is up to date
        if mode == self._mode:
            return

        self.settings.mode = mode
        self._mode = mode
        self._absolutePercent = 0

        # quick picks in relative mode, aka calling
        # setSlide(absolute=False), "compound"  changes with each call.
        # Once this happens, we cache those relative values so that the
        # slider can start blending from those instead of the original
        # key values.
        #
        # Consider switching modes as the mechanism that the slider can
        # "compound" changes. The next mode will pick up sliding where
        # this mode left off.
        #
        # I was originally only going to do this if _relativeValueCache
        # had any keys set, aka. have we ever used a relative blend,
        # then force detect keys if we hadn't - but that creates
        # inconsistent behavior where SOMETIMES you can reset back to
        # your original values (when relative values had been used) and
        # SOMETIMES you couldn't (when we tossed them due to a force re-
        # detect). Therefore, I'm letting ALL mode switches cache values
        # Making everything consistent - even if it makes "absolute"
        # mode slightly less... absolute.
        for segment in self._segmentCollection.segments:
            for key in segment.keys:
                self._relativeValueCache[key] = key.value

        self.dispatcher.send(self, 'ModeChanged')

    def beginSlide(self, percent=None):
        '''
        Begin sliding keys.

        Must be called before slide() or endSlide(). endSlide() must be
        called after sliding is finished, or Maya will be left in an
        invalid state (THIS IS REALLY BAD).
        '''
        if self._isSliding:
            raise RuntimeError(
                "Cannot call beginSlide twice. "
                "Call endSlide() when sliding has finished.")

        self._undoChunk.__enter__()
        self.detectKeys()
        self._isSliding = True
        self.dispatcher.send(self, 'BeginSlide')
        if percent is not None:
            self._apply(percent, absolute=True)

    def slide(self, percent):
        '''
        Sliding keys to the given percent.

        beginSlide must be called before this, and endSlide must be
        called when finished sliding, or Maya will be left in an invalid
        state (THIS IS REALLY BAD).
        '''
        self._apply(percent, absolute=True)

    def endSlide(self):
        '''
        End sliding keys.

        Must be called when finished sliding keys, or Maya will be left
        in an invalid state (THIS IS REALLY BAD).
        '''
        if self._isSliding:
            self._undoChunk.__exit__(None, None, None)
        self._isSliding = False
        self.dispatcher.send(self, 'EndSlide')

    def setSlide(self, percent, absolute=True):
        '''
        Slide keys to the given value.

        One-shot function to immediately slide keys without calling
        begin/slide/end
        '''
        self.beginSlide()
        self._apply(percent, absolute=absolute)
        self.endSlide()
        self.dispatcher.send(self, 'SetSlide')

    def resetSlide(self):
        '''
        Reset all keys back to their original position.
        '''
        # Reset relative values, restore original values.
        self._relativeValueCache = {}
        self.setSlide(0.0)
        self.dispatcher.send(self, 'ResetSlide')

    def _apply(self, percent, absolute=True, reset=False):
        '''
        Apply the given slide percent to all selected keys in Maya
        '''
        if not self._isSliding:
            raise RuntimeError(
                "Cannot apply slide percentage when sliding has "
                "not been activated.  Call beginSlide() first.")

        percent = percent / 100.0

        def getKeyValue(key):
            if not absolute:
                return key.value
            else:
                # If relative values have been used, we should use
                # those as our starting value - preventing an
                # absolute value move from jumping around (because
                # relative mode works off the current value, it can
                # move keys in ways that absolute sliding can't)
                return self._relativeValueCache.get(key, key.originalValue)


        for segment in self._segmentCollection.segments:
            # Segment level calculations
            if self._mode == 'average':
                averageGoal = (segment.neighborLeft.value + segment.neighborRight.value) / 2.0
            if self._mode == 'shift':
                # Find the difference between the end keys and their neighbors
                # Use that to shift all keys by that amount.
                if percent < 0:
                    shiftGoal = segment.neighborLeft.value - getKeyValue(segment.keys[0])
                else:
                    shiftGoal = segment.neighborRight.value - getKeyValue(segment.keys[-1])

            for key in segment.keys:
                # Find the goal we will lerp to
                if self._mode == 'blend':
                    if percent < 0:
                        goalValue = segment.neighborLeft.value
                    else:
                        goalValue = segment.neighborRight.value
                elif self._mode == 'shift':
                    goalValue = getKeyValue(key) + shiftGoal
                elif self._mode == 'average':
                    goalValue = averageGoal
                elif self._mode == 'default':
                    goalValue = key.defaultValue
                elif self._mode == 'shrink':
                    goalValue = key.shrinkValue
                elif self._mode == 'level':
                    goalValue = key.levelValue
                elif self._mode == 'linear':
                    goalValue = key.linearValue
                elif self._mode == 'ease':
                    if percent < 0:
                        goalValue = key.easeOutValue
                    else:
                        goalValue = key.easeInValue
                elif self._mode == 'ease in/out':
                    goalValue = key.easeInOutValue


                keyValue = getKeyValue(key)
                # Lerp to goal.
                if self._mode in ('blend', 'shift', 'ease'):  # Non-negative lerps
                    newValue = keyValue * (1 - abs(percent)) + goalValue * abs(percent)
                else:
                    newValue = keyValue * (1 - percent) + goalValue * percent

                key.value = newValue  # Set key value in Maya.
                if not absolute:
                    self._relativeValueCache[key] = newValue

        self._absolutePercent = percent * 100 if absolute else 0.0
        self.dispatcher.send(self, 'PercentChanged')


controller = SlideKeysController()


def hotkey(value, absolute=None):
    '''

    '''
    # Update keyword parameter kept for backwards compatibility.
    global controller
    # Pick up the persistent setting unless passed an explicit one.
    if absolute is None:
        absolute = controller.settings.absoluteQuickPicks
    controller.setSlide(value, absolute=absolute)


def setMode(mode):
    '''
    Set the mode of the following operations.
    '''
    global controller
    mode = mode.lower()
    if mode.lower() not in controller.settings.modes:
        raise ValueError(
            "Mode must be one of: %s" % repr(controller.settings.modes))
    controller.setMode(mode)


# This function is in this module for backwards compatibility
def ui():
    '''
    Launches the UI for slide animation keys
    '''
    from guppy_animation_tools.slideAnimationKeysUI import ui
    ui()
