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

import gtk, gobject

import computer

COLUMN_LENGTH = 2
(COLUMN_NAME, COLUMN_VALUE) = range(COLUMN_LENGTH)

WIPE_METHODS = computer.WIPE_METHODS.keys()

class ComputerPanel():
    """
    The panel at the bottom of a GroupPage 
    showing details and actions for a computer
    """
    
    def __init__(self, computer, grouppage):
        
        self.computer = computer
        self.grouppage = grouppage
        
        glade = gtk.Builder()
        glade.add_objects_from_file('ui/glade/mainwindow.glade', ['computerPanel'])
        self.glade = glade
        self.glade.connect_signals(self)

        self.mainContainer = glade.get_object('computerPanel')
        
        self.glade.get_object('buttonComputerGetID').connect('clicked', self.grouppage.on_get_id, self.computer)
        self.glade.get_object('buttonComputerStart').connect('clicked', self.on_clicked_start)
        self.glade.get_object('checkbuttonWipe').connect('toggled', self.on_toggle_wipe)
        self.glade.get_object('checkbuttonScan').connect('toggled', self.on_toggle_scan)
        self.glade.get_object('buttonComputerRegister').connect('clicked', self.on_register)
        self.glade.get_object('buttonComputerRemove').connect('clicked', self.on_delete)
        self.glade.get_object('buttonComputerReload').connect('clicked', self.on_reload)
        
        self.set_headline()
        
        self.treeview = glade.get_object('treeviewComputer')
        
        # hardware type column
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Category", cell, text=COLUMN_NAME)
        self.treeview.append_column(col)

        # hardware value column
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Description", cell, text=COLUMN_VALUE)
        self.treeview.append_column(col)
        
        self.liststore = gtk.ListStore(gobject.TYPE_STRING,  # HW name
                                       gobject.TYPE_STRING,  # HW Description
                                      )
        self.treeview.set_model(self.liststore)
        self.treeview.set_reorderable(False)
        
        self.set_hardware()
        
        wipe_method = self.glade.get_object("comboboxMethod")
        wipe_method_liststore = gtk.ListStore(gobject.TYPE_STRING)
        wipe_method.set_model(wipe_method_liststore)
        cell = gtk.CellRendererText()
        wipe_method.pack_start(cell, True)
        wipe_method.add_attribute(cell, 'text', 0)
        for method in WIPE_METHODS:
            wipe_method.append_text(method)
        wipe_method.set_active(0)

    def on_delete_event(self, *args):
        pass

    def get_widget(self):
        return self.mainContainer

    def set_headline(self):
        if self.computer.id:
            headline = "Details: %s" % str(self.computer.id)
        else:
            headline = "Details: No ID"
        self.glade.get_object('labelComputerPanel').set_text(headline)

    def set_hardware(self):
        hw = self.computer.hw_info
        
        hw["MAC address"] = self.computer.macAddress
        
        self.liststore.clear()
        
        if hw:
            for key in sorted(hw.keys(), reverse=True):
                row = [None for _ in range(COLUMN_LENGTH)]
                row[COLUMN_NAME] = str(key)
                row[COLUMN_VALUE] = str(hw[key])
                self.liststore.prepend(row=row)
                

    def on_clicked_start(self, *args, **kwargs):
        self.glade.get_object('buttonComputerStart').set_sensitive(False)
        scan = self.glade.get_object('checkbuttonScan').get_active()
        wipe = self.glade.get_object('checkbuttonWipe').get_active()
        shutdown = self.glade.get_object('checkbuttonShutdown').get_active()
        autosubmit = self.glade.get_object('checkbuttonAutosubmit').get_active()
        badblocks = self.glade.get_object('checkbuttonBadblocks').get_active()
        method = self.glade.get_object("comboboxMethod").get_active_text()
        self.grouppage.process(self.computer, scan, wipe, method, badblocks,
                               shutdown=shutdown, autosubmit=autosubmit)

    def on_toggle_wipe(self, *args):
        if not self.glade.get_object('checkbuttonWipe').get_active():
            self.glade.get_object('comboboxMethod').set_sensitive(False)
        else:
            self.glade.get_object('comboboxMethod').set_sensitive(True)

    def on_toggle_scan(self, *args):
        if not self.glade.get_object('checkbuttonScan').get_active():
            self.glade.get_object('buttonComputerStart').set_sensitive(False)
            self.glade.get_object('checkbuttonWipe').set_sensitive(False)
            self.glade.get_object('checkbuttonBadblocks').set_sensitive(False)
            self.glade.get_object("comboboxMethod").set_sensitive(False)
            self.glade.get_object('checkbuttonAutosubmit').set_sensitive(False)
        else:
            self.glade.get_object('buttonComputerStart').set_sensitive(True)
            self.glade.get_object('checkbuttonWipe').set_sensitive(True)
            self.glade.get_object('checkbuttonBadblocks').set_sensitive(False)
            if self.glade.get_object('checkbuttonWipe').get_active():
                self.glade.get_object("comboboxMethod").set_sensitive(True)
            self.glade.get_object('checkbuttonAutosubmit').set_sensitive(True)

    def on_register(self, *args):
        self.grouppage.register_computer(self.computer)
        
    def on_delete(self, *args):
        self.grouppage.removeComputer(self.computer)

    def on_reload(self, *args):
        self.grouppage.reload_computer(self.computer)

    def update(self, *args):
        """Update all widgets from computer object"""
        is_connected = self.computer.is_connected()
        ready = not self.computer.is_active()
        self.glade.get_object('buttonComputerStart').set_sensitive(is_connected and ready)
        self.glade.get_object('buttonComputerRegister').set_sensitive(ready and bool(self.computer.id))
        self.glade.get_object('checkbuttonAutosubmit').set_sensitive(bool(self.computer.id))
        self.glade.get_object('checkbuttonAutosubmit').set_active(bool(self.computer.id))
        self.set_hardware()
        self.set_headline()
        return False
