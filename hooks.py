#  Copyright (c) 2016 Phil Birkelbach
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

try:
    from PyQt5.QtCore import *
except:
    from PyQt4.QtCore import *

import logging
import importlib


imodules = list()

# Read through the configuration and load the hook modules
def initialize(config):
    global imodules
    log = logging.getLogger(__name__)

    if config == None: return # None Configured
    # Load the Hook Modules
    for each in config:
        module = config[each]["module"]
        try:
            name = each
            m = importlib.import_module(module)
            if 'config' in config[each]:
                m.start(config[each]['config'])
                imodules.append(m)
            #load_screen(each[7:], module, config)
        except Exception as e:
            logging.critical("Unable to load module - " + module + ": " + str(e))
            raise

def stop():
    global  imodules
    for m in imodules:
        m.stop()
