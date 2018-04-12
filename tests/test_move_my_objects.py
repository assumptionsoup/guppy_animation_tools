import pytest
import pymel.core as pm
import guppy_animation_tools.moveMyObjects as mmo


@pytest.fixture(autouse=True)
def newfile():
    pm.newFile(f=1)


def test_duplicate():
    cube, shape = pm.polyCube()
    cube.t.set((1, 2, 3))
    cube.r.set((20, 30, 40))
    cube.rx.lock()
    cube.rx.setKeyable(False)

    group = mmo.duplicateGroup(cube, 'my_cube')
    assert (group.nodeName() == 'my_cube')
    assert (list(group.t.get()) == pytest.approx([1.0, 2.0, 3.0]))
    assert (list(group.r.get()) == pytest.approx([20.0, 30.0, 40.0]))
    for attr in 't r s tx ty tz rx ry rz sx sy sz v'.split():
        assert (not group.attr(attr).isLocked())
        assert (group.attr(attr).isKeyable())


def flattenMat(mat):
    return [num for row in mat.tolist() for num in row]


def test_applyOneMatrix():
    cube, shape = pm.polyCube()

    # Pass through identity matrix
    mat = pm.dt.Matrix()
    mmo.applyNodePositions([mat], [cube])
    cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
    assert(cubeMat == pytest.approx(flattenMat(mat)))

    # Reset to identity
    cube.t.set((1, 2, 3))
    mmo.applyNodePositions([mat], [cube])
    cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
    assert(cubeMat == pytest.approx(flattenMat(mat)))

    # Arbitrary matrix.
    mat = pm.dt.Matrix([
        [0.664463024389, 0.664463024389, -0.342020143326, 0.0],
        [-0.386220403522, 0.697130037317, 0.604022773555, 0.0],
        [0.639783314196, -0.269255641148, 0.719846310393, 0.0],
        [15.5773616478, 17.4065855678, 15.7988353267, 1.0]])

    mmo.applyNodePositions([mat], [cube])
    cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
    assert(cubeMat == pytest.approx(flattenMat(mat)))


def test_applyLocked():
    cube, shape = pm.polyCube()
    cube.tx.lock()


    applyMat = pm.dt.Matrix()
    resultMat = pm.dt.Matrix()
    applyMat[3] = (5, 5, 5, 1)
    # Tests partial application of position
    resultMat[3] = (0, 5, 5, 1)
    mmo.applyNodePositions([applyMat], [cube])

    cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
    assert(cubeMat == pytest.approx(flattenMat(resultMat)))


def test_applyScaledMatrix():
    # applyNodePositions should NOT apply scale.
    cube, shape = pm.polyCube()
    mat = pm.dt.Matrix([
        [0.5, 0.5, -0.707106781187, 0.0],
        [-0.292893218813, 1.70710678119, 1.0, 0.0],
        [1.70710678119, -0.292893218813, 1.0, 0.0],
        [1.0, 2.0, 3.0, 1.0]])

    # Same matrix, but unscaled
    unscaled = pm.dt.Matrix([
        [0.5, 0.5, -0.707106781187, 0.0],
        [-0.146446609407, 0.853553390593, 0.5, 0.0],
        [0.853553390593, -0.146446609407, 0.5, 0.0],
        [1.0, 2.0, 3.0, 1.0]])
    mmo.applyNodePositions([mat], [cube])
    cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
    assert(cubeMat == pytest.approx(flattenMat(unscaled)))


def getMultiMatrixObjects():
    cubes = [pm.polyCube()[0] for x in xrange(4)]

    # Just some translation matrices, other tests can check rotation
    # This test should check that we touch the correct objects, and
    # fail otherwise.
    mats = []
    for x in xrange(4):
        mat = pm.dt.Matrix()
        mat[3] = (x, x + 1, x + 2, 1)
        mats.append(mat)
    return cubes, mats


def test_applyOneToMany():
    cubes, mats = getMultiMatrixObjects()
    mmo.applyNodePositions([mats[0]], cubes)

    for cube in cubes:
        cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
        assert(cubeMat == pytest.approx(flattenMat(mats[0])))


def test_applyOneToMany2():
    cubes, mats = getMultiMatrixObjects()
    mmo.applyNodePositions([mats[0]], cubes[2:])

    for cube in cubes[2:]:
        cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
        assert(cubeMat == pytest.approx(flattenMat(mats[0])))
    for cube in cubes[:2]:
        cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
        assert(cubeMat == pytest.approx(flattenMat(pm.dt.Matrix())))


def test_applyManyToMore():
    cubes, mats = getMultiMatrixObjects()
    # Failure case.
    with pytest.raises(IndexError):
        mmo.applyNodePositions(mats[2:], cubes)
    # Check that nothing was changed.
    for cube in cubes:
        cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
        assert(cubeMat == pytest.approx(flattenMat(pm.dt.Matrix())))


def test_applyManyToLess():
    cubes, mats = getMultiMatrixObjects()
    mmo.applyNodePositions(mats[:3], cubes[:2])

    # Only two cubes changed. Remaining matrices tossed.
    for x in xrange(2):
        cubeMat = flattenMat(cubes[x].getMatrix(worldSpace=True))
        assert(cubeMat == pytest.approx(flattenMat(mats[x])))
    for cube in cubes[2:]:
        cubeMat = flattenMat(cube.getMatrix(worldSpace=True))
        assert(cubeMat == pytest.approx(flattenMat(pm.dt.Matrix())))


def test_applyManyToSame():
    cubes, mats = getMultiMatrixObjects()
    mmo.applyNodePositions(mats, cubes)

    for x in xrange(len(cubes)):
        cubeMat = flattenMat(cubes[x].getMatrix(worldSpace=True))
        assert(cubeMat == pytest.approx(flattenMat(mats[x])))


def test_getPositions1():
    cube, shape = pm.polyCube()
    # Basic identity test
    mat = pm.dt.Matrix()
    foundMats = mmo.getNodePositions([cube])
    assert(flattenMat(foundMats[0]) == pytest.approx(flattenMat(mat)))


def test_getPositions2():
    # Basic world position test
    cube1 = pm.polyCube()[0]
    cube2 = pm.polyCube()[0]
    cube1.setParent(cube2)
    cube2.t.set(1, 3, 4)
    cube1.t.set(1, 2, 3)

    mat = pm.dt.Matrix()
    mat[3] = [2, 5, 7, 1]
    foundMats = mmo.getNodePositions([cube1])
    assert(flattenMat(foundMats[0]) == pytest.approx(flattenMat(mat)))

    # TODO: Harder edge cases, maybe something with an IK system
    #       those always screw Maya up...


def test_mainClass():
    mm = mmo.MoveMyObjects()

    cube1 = pm.polyCube()[0]
    cube2 = pm.polyCube()[0]
    cube2.t.set(1, 2, 3)
    pm.select([cube1, cube2])
    mm.savePositions()
    cube2.t.set(0, 0, 0)
    mm.applyPositions()

    # Test state
    assert(list(cube2.t.get()) == [1, 2, 3])
    assert(len(mm.positions) == 2)

