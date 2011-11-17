import gtk, gobject
#
# LCRS Copyright (C) 2009-2011
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

class SplashWindow:
    def __init__(self, callback):
        self.callback = callback
        self.uiApp = gtk.Builder()
        self.uiApp.add_from_file('ui/glade/splash.glade')
        self.uiApp.connect_signals (self)
        
        self.window = self.uiApp.get_object ('windowSplash')
        
        self.get_widget("imageSplash").connect("button-press-event", self.quit)
        self.get_widget("imageSplash").connect("button-release-event", self.quit)
        self.window.show()
        
        gobject.timeout_add_seconds(2, self.quit)
        
    def get_widget(self, key):
        """Use this object as a dictionary of widgets"""
        return self.uiApp.get_object(key)
        
    def quit(self, *args):
        self.callback()
        self.window.destroy()
