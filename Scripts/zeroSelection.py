'''Zero Selection lets the user easily and quickly return the selected channels
to their default values.

The primary method associated with this module is zeroSelection()

*******************************************************************************
	License and Copyright
	Copyright 2012 Jordan Hueckstaedt
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
	Work Status:...Looking for work!  If you have a job where I can write tools
				   like this or rig characters, hit me up!

*******************************************************************************
   Change Log:
    1-31-2012 - v0.02 - Updated to use selectedAttributes module.

	Note: After the first commit to git, this history will be erased.  I'll be
	using git as a way of keeping track of future changes.
****************************************************************************'''

__author__ = 'Jordan Hueckstaedt'
__copyright__ = 'Copyright 2012'
__license__ = 'GPL v3'
__version__ = '0.02'
__email__ = 'AssumptionSoup@gmail.com'
__status__ = 'Production'
__date__ = '2-25-2012'

import maya.cmds as cmd
import maya.OpenMaya as om
import selectedAttributes
import collections


def zeroSelection():
    # Easily and quickly return the selected channels to their default values.

    # Get Attributes
    attributes = selectedAttributes.get(detectionType='cursor', animatableOnly=False)

    # Make extra sure attributes are unique (they should already be)
    attributes = list(set(attributes))

    for attr in attributes:
        try:
            # Get default values
            default = cmd.attributeQuery(attr.split('.')[-1], node=attr.split('.')[0], listDefault=1)
            if isinstance(default, collections.Iterable) and len(default):
                try:
                    cmd.setAttr(attr, default[0])
                except:
                    # Maybe a compound?
                    om.MGlobal.displayError("Sorry, but I couldn't reset the attribute: %s" % attr)
            else:
                # Probably a string or something weird.  Actually, I'm curious.  So I want to know what would fail..
                om.MGlobal.displayError("Sorry, but I don't know how to deal with the attribute: %s" % attr)
        except:
            # Print out exception so I can debug any further problems if they appear...
            om.MGlobal.displayError("Sorry, what is this? %s" % attr)
