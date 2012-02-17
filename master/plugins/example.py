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

from plugins import BasePlugin

class ExamplePlugin(BasePlugin):
    
    name = "Example plugin"
    description = "This is an example plugin"
    
    def __init__(self, mainwindow_instance):
        self.mainwindow_instance = mainwindow_instance
    
    def activate(self):
        print "I was activated!"
        self.mainwindow_instance.plugin_subscribe('on-add-computer', self.my_callback)
    
    def my_callback(self):
        print "I was called!!"
    
    def deactivate(self):
        pass
        