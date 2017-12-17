import pytest
import pymel.core as pm
import guppy_animation_tools.slideAnimationKeys as sak


@pytest.fixture(autouse=True)
def newfile():
    pm.newFile(f=1)


def setupCube():
    cube = pm.polyCube()[0]
    pm.setKeyframe()
    for x in xrange(5):
        pm.currentTime(x)
        cube.tx.set(x)
        cube.ty.set(x)
        pm.setKeyframe()

    pm.selectKey(clear=True)
    pm.selectKey(cube.tx.connections()[0], add=1, k=1, t="1:3")
    pm.selectKey(cube.ty.connections()[0], add=1, k=1, t="1:3")
    return cube


def test_selection_no_immediate_change():
    setupCube()
    collection = sak.SegmentCollection.detect()

    # Immediate query has not changed selection
    assert not collection.hasSelectionChanged(sak.SegmentCollection.detect())


def test_selection_cache_change():
    cube = setupCube()
    collection = sak.SegmentCollection.detect()

    pm.setKeyframe(cube.ty, value=10, time=3)
    pm.setKeyframe(cube.ty, value=10, time=4)

    # Still no change as we never cached the original values
    assert not collection.hasSelectionChanged(sak.SegmentCollection.detect())

    # Not even a double query changes anything as these values were not
    # cached before the initial query. BUT they have been cached now.
    assert not collection.hasSelectionChanged(sak.SegmentCollection.detect())

    # Change each key one at a time and test that the change was detected.
    # Current values
    values = [0, 1, 2, 10, 10]
    for time, value in enumerate(values):
        # Selected value changed
        pm.setKeyframe(cube.ty, value=-1, time=time)
        assert collection.hasSelectionChanged(
            sak.SegmentCollection.detect())

        # reset back value back
        pm.setKeyframe(cube.ty, value=value, time=time)

        # Back to unchanged?
        assert not collection.hasSelectionChanged(
            sak.SegmentCollection.detect())


def test_selection_change_clear():
    setupCube()
    collection = sak.SegmentCollection.detect(forceSelectedKeys=True)

    pm.selectKey(clear=True)
    assert collection.hasSelectionChanged(
        sak.SegmentCollection.detect(forceSelectedKeys=True))


def test_selection_change_deselect():
    cube = setupCube()
    collection = sak.SegmentCollection.detect(forceSelectedKeys=True)

    pm.selectKey(cube.tx.connections()[0], rm=1, k=1, t="3")
    assert collection.hasSelectionChanged(
        sak.SegmentCollection.detect(forceSelectedKeys=True))


def test_selection_change_more():
    cube = setupCube()
    # Force graph will force sgment collection to consider selected keys
    # instead of keys on the current frame.
    collection = sak.SegmentCollection.detect(forceSelectedKeys=True)

    # Selected keys
    for x in xrange(1, 4):
        # deselect
        pm.selectKey(cube.tx.connections()[0], rm=1, k=1, t=x)
        assert collection.hasSelectionChanged(
            sak.SegmentCollection.detect(forceSelectedKeys=True))

        # reset
        pm.selectKey(cube.tx.connections()[0], add=1, k=1, t=x)
        assert not collection.hasSelectionChanged(
            sak.SegmentCollection.detect(forceSelectedKeys=True))

    for x in [0, 4]:
        # select
        pm.selectKey(cube.tx.connections()[0], add=1, k=1, t=x)
        assert collection.hasSelectionChanged(
            sak.SegmentCollection.detect(forceSelectedKeys=True))

        # reset
        pm.selectKey(cube.tx.connections()[0], rm=1, k=1, t=x)
        assert not collection.hasSelectionChanged(
            sak.SegmentCollection.detect(forceSelectedKeys=True))
