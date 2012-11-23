# -*- coding: utf-8 -*-
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
from datetime import datetime

import os

from lcrs.master import reports, config_master

class ReportDialog:
    def __init__(self, group_clicked, all_groups):
        self.glade = gtk.Builder()
        self.glade.add_from_file(
            os.path.join(config_master.MASTER_PATH, 'ui/glade/mainwindow.glade')
        )
        
        self.window = self.glade.get_object ('dialogReport')
        self.window.connect("delete-event", self.on_delete_event)
        
        self.group = group_clicked
        self.all_groups = all_groups
        
        self.get_widget("saveThis").set_label("Save \"%s\"" % self.group.getName())
        self.get_widget("entryName").set_text("lcrs_report_%s" % (datetime.now().strftime("%Y-%m-%d")))
        self.get_widget("entryName").connect("changed", self.on_change_name)
        
        self.get_widget("filechooserbuttonPath").set_current_folder(config_master.USER_HOME)
        
        self.get_widget("filechooserbuttonPath").add_shortcut_folder(config_master.USER_HOME)
        
        self.get_widget("cancel").connect("clicked", self.on_cancel)
        self.get_widget("saveThis").connect("clicked", self.on_save_this)
        self.get_widget("saveAll").connect("clicked", self.on_save_all)
        
        self.glade.connect_signals(self)

        self.window.show()

    def get_widget(self, key):
        """Use this object as a dictionary of widgets"""
        return self.glade.get_object(key)

    def quit(self): #@ReservedAssignment
        self.window.destroy()
    
    def on_change_name(self, *args):
        text = self.get_widget("entryName").get_text().lower()
        original_text = text
        not_allowed_characters = ",:/\\\"|><"
        
        for c in text:
            if c in not_allowed_characters:
                original_text = original_text.replace(c, "_")
        
        self.get_widget("entryName").set_text(original_text)
        
        self.get_widget("saveThis").set_sensitive(original_text != "")
        self.get_widget("saveAll").set_sensitive(original_text != "")
    
    def on_delete_event(self, widget, callback_data):
        """
        Display manager closed window.
        """
        self.quit()
        return False

    def on_close(self, widget):
        self.quit()

    def on_cancel(self, *args):
        self.quit()
    
    def on_save_this(self, *args):
        self.save_report([self.group])
    def on_save_all(self, *args):
        self.save_report(self.all_groups)
    
    def save_report(self, groups):
        data = reports.make_report(groups, "html")
        folder = self.get_widget("filechooserbuttonPath").get_current_folder()
        filename = self.get_widget("entryName").get_text() + ".html"
        fullpath = os.path.join(folder, filename)
        try:
            f = file(fullpath, "w")
            f.write(data)
            os.chown(fullpath, config_master.USER_UID, config_master.USER_GID)
        except:
            self.fail("Could not write to file %s" % fullpath)
        finally:
            self.success("Report saved!")
            self.quit()


    def fail(self, msg):
        def on_close(dialog, *args):
            dialog.destroy()
    
        dialog = gtk.MessageDialog(parent=self.window,
                                   type=gtk.MESSAGE_ERROR,
                                   buttons = gtk.BUTTONS_CLOSE,
                                   message_format=msg,)
        dialog.set_modal(True)
        dialog.connect("response", on_close)
        dialog.show()

    def success(self, msg):
        def on_close(dialog, *args):
            dialog.destroy()
    
        dialog = gtk.MessageDialog(parent=self.window,
                                   type=gtk.MESSAGE_INFO,
                                   buttons = gtk.BUTTONS_CLOSE,
                                   message_format=msg,)
        dialog.set_modal(True)
        dialog.connect("response", on_close)
        dialog.show()
                
