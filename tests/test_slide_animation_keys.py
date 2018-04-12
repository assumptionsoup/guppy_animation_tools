import pytest
import pymel.core as pm
import guppy_animation_tools.slideAnimationKeys as sak


@pytest.fixture(autouse=True)
def newfile():
    pm.newFile(f=1)
