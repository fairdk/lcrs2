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

import gtk

class GetID():
    
    def __init__(self, computer, grouppage):
        self.computer = computer
        self.grouppage = grouppage
        
        glade = gtk.Builder()
        glade.add_objects_from_file('ui/glade/get_id.glade', ['getid'])
        self.glade = glade
        
        self.glade.get_object('buttonOK').connect('button-press-event', self.on_ok)
        self.glade.get_object('entryID').connect('activate', self.on_ok)
        self.glade.get_object('buttonCancel').connect('button-press-event', self.on_cancel)
        
        self.mainContainer = glade.get_object('getid')
        
        self.glade.connect_signals(self)
    
    def on_delete_event(self, *args):
        pass

    def get_widget(self):
        return self.mainContainer

    def focus_id_entry(self):
        self.glade.get_object('entryID').grab_focus()

    def on_cancel(self, *args):
        self.grouppage.cancel_get_id(self.computer)
    
    def on_ok(self, *args):
        self.glade.get_object('buttonOK').set_sensitive(False)
        self.glade.get_object('buttonCancel').set_sensitive(False)
        id_input = self.glade.get_object('entryID').get_text()
        self.grouppage.set_id(self.computer, id_input)
    