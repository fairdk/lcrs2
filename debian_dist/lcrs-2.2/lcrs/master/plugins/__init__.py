#
# LCRS Copyright (C) 2009-2012
# - Benjamin Bach
#
# LCRS is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# LCRS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with LCRS.  If not, see <http://www.gnu.org/licenses/>.

class CallbackFailed(Exception):
    pass

class BasePlugin():
    
    plugin_id = "unique_id"
    name = "My Plugin"
    description = "This is a plugin"
    config = {}
    
    def __init__(self, mainwindow_instance, config_master):
        # an instance of the main window
        self.mainwindow_instance = mainwindow_instance
        # an instance of config_master
        self.config_master = config_master
    
    def get_config(self, key):
        return self.config_master.ui_plugins[self.__class__][key]

    def activate(self):
        pass
    
    def deactivate(self):
        pass
