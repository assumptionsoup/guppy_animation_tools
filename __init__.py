# Include the scripts folder in this package.  Which allows for:
# import guppy_animation_tools.cleverKeys

# As well as the less intuitive:
# import guppy_animation_tools.scripts.cleverKeys

# This allows us to use guppy_animation_tools as both a complete
# development package (including plugin, scripts, and icons), and allow
# non-technical users to drop the package into an existing folder on the
# PYTHONPATH (e.g. the maya scripts dir)
import os
import sys


REPO_DIR = os.path.dirname(os.path.realpath(__file__))
_SCRIPTS_DIR = os.path.join(REPO_DIR, 'scripts')
__path__.append(_SCRIPTS_DIR)
__all__ = [
    'arcTracer',
    'cleverKeys',
    'lock_n_hide',
    'moveMyObjects',
    'pickleAttr',
    'pointOnMesh',
    'selectedAttributes',
    'slideAnimationKeys',
    'zeroSelection',
    'guppyInstaller']


def _addToPath(env, newLocation):
    '''
    Add path to os.environ[env]
    '''
    if not newLocation.endswith(os.path.sep):
        newLocation += os.path.sep

    if newLocation not in os.environ[env].split(os.pathsep):
        if os.environ[env]:
            os.environ[env] += os.pathsep
        os.environ[env] += newLocation


def _addPluginPath(pluginLocation):
    '''
    Add plugin path to Maya.
    '''
    _addToPath('MAYA_PLUG_IN_PATH', pluginLocation)


def _addScriptPath(scriptLocation):
    '''
    Add mel script path to Maya.
    '''
    _addToPath('MAYA_SCRIPT_PATH', scriptLocation)


def _addPythonPath(scriptLocation):
    '''
    Add python script path to Maya.
    '''
    # Adding to python path just adds the parent dir for some reason
    # (Guppy-Animation-Tools).
    # _addToPath('PYTHONPATH', scriptLocation)
    if scriptLocation not in sys.path:
        sys.path.append(scriptLocation)


def _addIconPath(iconLocation):
    '''
    Add icon path to Maya.
    '''
    _addToPath('XBMLANGPATH', iconLocation)

logger = getLogger('guppy_animation_tools')

# Add necessary folders to the PYTHONPATH
pluginPath = os.path.join(REPO_DIR, 'plugins')
_addPluginPath(os.path.join(pluginPath, 'python'))
_addScriptPath(os.path.join(REPO_DIR, 'AETemplates'))
_addIconPath(os.path.join(REPO_DIR, 'icons'))
