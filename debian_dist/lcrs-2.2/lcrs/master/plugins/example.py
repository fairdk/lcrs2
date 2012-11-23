#
# LCRS Copyright (C) 2009-2011
# - Rene Jensen
# - Michael Wojciechowski
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

from lcrs.master.plugins import BasePlugin #@UnresolvedImport

class ExamplePlugin(BasePlugin):
    
    plugin_id = "example"
    name = "Example plugin"
    description = "This is an example plugin"
    
    # This is a template for your configuration. Please ONLY use lower-case
    # keys do to the nature of the config file format.
    # To get an actual configuration user config_maser.ui_plugins
    config = {'example_key': ('This is an example', 'config value here')}
    
    def activate(self):
        print "I was activated!"
        self.mainwindow_instance.plugin_subscribe('on-add-computer', self.my_callback)
    
    def my_callback(self):
        print "I was called!!"
    
    def deactivate(self):
        pass
        