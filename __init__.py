# Importing the scripts folder gives us a nice top-level namespace of
# python scripts we care about.  For instance:

# import guppy_animation_tools as gat
# gat.cleverKeys

# Unfortunately, it also brings in scripts that require plugins, like
# lock_n_hide. The first thing that script tries to do is access the
# plugin, and spit out an error message if it can't find it.

# This doesn't sound so bad, except that I now building guppy animation
# tools to be primarily run via an installer, which goes like this:
# import guppy_animation_tools as gat  # scripts are imported
#                                      # lock_n_hide prints an error message
# gat.install()  # Plugins are now installed on the path.

# To work around this for now, I'm letting this package run the
# installer, but I'm not sure I like this method because it means these
# plugins will be loaded automatically without a good way for the end-
# user (even a reasonably python savvy one), to change this behavior.

# Perhaps my installer could look at environment variables which control
# plugin loading...
import guppy_animation_tools.guppyInstaller
guppy_animation_tools.guppyInstaller.install()
from guppy_animation_tools.scripts import *
