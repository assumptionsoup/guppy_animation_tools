'''Guppy Animation Tools is a collection of tools to help animators

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
'''
import os
import sys

import pymel.internal.plogging as plogging

# Include the scripts folder in this package.  Which allows for:
# import guppy_animation_tools.cleverKeys

# As well as the less intuitive:
# import guppy_animation_tools.scripts.cleverKeys

# This allows us to use guppy_animation_tools as both a complete
# development package (including plugin, scripts, and icons), and allow
# non-technical users to drop the package into an existing folder on the
# PYTHONPATH (e.g. the maya scripts dir)

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
    'renameIt']
_logRegister = {}
_logLevels = {}
_debugOn = False


def getLogger(name):
    if 'guppy_animation_tools' in name:
        name = name.replace('guppy_animation_tools', 'gat', 1)
    if name not in _logRegister:
        log = plogging.getLogger(name)
        log.setLevel(log.INFO)
        _logRegister[name] = log

    return _logRegister[name]


def setLoggerLevels(level, namespaces=None):
    if namespaces is None:
        namespaces = _logRegister.keys()

    if _logLevels:
        namespaces = [n for n in _logLevels.iterkeys() if n not in namespaces]

    for name in namespaces:
        _logLevels[name] = _logRegister[name].level
        _logRegister[name].setLevel(level)


def restoreLoggerLevels():
    global _logLevels
    for name, level in _logLevels.iteritems():
        _logRegister[name].setLevel(level)
    _logLevels = {}


def toggleDebug():
    global _debugOn
    if _debugOn:
        restoreLoggerLevels()
    else:
        setLoggerLevels(plogging.DEBUG)
    _debugOn = not _debugOn


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


# Add necessary folders to the PYTHONPATH
_pluginPath = os.path.join(REPO_DIR, 'plugins')
_addPluginPath(os.path.join(_pluginPath, 'python'))
_addScriptPath(os.path.join(REPO_DIR, 'AETemplates'))
_addIconPath(os.path.join(REPO_DIR, 'icons'))

# Add logger TODO: investigate if pymel has controls for manipluating
# all loggers created through it.  If not, we should keep track of all
# of GAT's loggers so we can toggle verbosity for the entire package if
# needed.
logger = getLogger('guppy_animation_tools')
