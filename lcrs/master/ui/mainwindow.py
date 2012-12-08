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

import gobject, gtk
import os

from lcrs.master.ui.grouppage import GroupPage
from lcrs.master import config_master
from lcrs.master.ui.preferenceswindow import PreferencesWindow

import logging
logger = logging.getLogger('lcrs')

# should be replaced with something from logging module
LOG_ERR, LOG_WARNING, LOG_INFO = range(3)

class MainWindow():
    """
    Main class for application window.

    REMEMBER THREAD SAFETY!!
    """
    def __init__(self, *args, **kwargs):
        self.groups = {}
        self.computers = {}
        self.log = []
        self.plugin_hooks = {}
        self.plugins = []
        self.alive = True
        self.master_instance = kwargs['master_instance']
        self.config = self.master_instance.get_config()
        
        for plugin_class, options in config_master.ui_plugins.items():
            if not options.get('disabled', False):
                p = plugin_class(self, self.config)
                self.plugins.append(p)
                p.activate()
                logger.debug("activating %s" % plugin_class.name)
        
        self.glade = gtk.Builder()
        self.glade.add_from_file(
            os.path.join(config_master.MASTER_PATH, 'ui/glade/mainwindow.glade')
        )

        self.groupNotebook = self.getWidget('groupNotebook')
        
        self.groupNotebook.remove(self.getWidget('groupPage'))

        win = self.getWidget('mainWindow')

        win.connect("delete-event", self.on_delete_event)
        
        menu_preferences = self.getWidget('menuitempreferences')
        menu_preferences.connect('activate', self.open_preferences)
        
        self.glade.connect_signals(self)
        
        self.getWidget('buttonAddGroup').connect('clicked', self.add_group)
        
        self.win = win
        self.win.show()
        
        self.update_overall_status()

        self.alert_plugins('on-mainwindow-ready')
    
    def plugin_subscribe(self, hook_id, callback):
        old_list = self.plugin_hooks.get(hook_id, [])
        old_list.append(callback)
        self.plugin_hooks[hook_id] = old_list

    def alert_plugins(self, event, *args):
        """We only return a single value, even if there are more than
           One plugin. Anything else seems overkill.
        """
        return_value = None
        for plugin_func in self.plugin_hooks.get(event, []):
            return_value = plugin_func(*args)
        return return_value
    
    def show(self):
        self.win.show()
    
    def on_delete_event(self, *args):
        """
        Display manager closed window.
        """
        self.main_quit()
        return True # Do not destroy
    
    def on_log_menu_activate(self, *args):
        f = open(config_master.LOG_FILE, "r")
        textbuffer = self.getWidget('textbufferLog')
        textbuffer.set_text(f.read())
        
        self.dialog = self.getWidget('dialogLog')
        self.dialog.show_all()
        self.dialog.connect('delete_event', self.dialog.hide_on_delete)
    
    def on_log_close(self, *args):
        self.dialog.hide()
    
    def main_quit(self):
        def do_quit(dialog, response_id):
            if dialog:
                dialog.destroy()
            if not response_id == gtk.RESPONSE_YES: return
            self.alive = False
            self.win.destroy()
            gtk.main_quit()
        dialog = gtk.MessageDialog(parent=self.win,
                                   type=gtk.MESSAGE_QUESTION,
                                   buttons = gtk.BUTTONS_YES_NO,
                                   message_format="Do you really want to quit LCRS?")
        dialog.connect("response", do_quit)
        dialog.connect("close", do_quit, gtk.RESPONSE_NO)
        dialog.show()
        
    def getWidget(self, identifier):
        return self.glade.get_object(identifier)

    def _update_overall_status(self):
    
        no_computers = 0
        for g in self.groups.keys():
            no_computers = no_computers + len(g.computers)
        
        busy_computers = []
        for g in self.groups.keys():
            busy_computers += filter(lambda c: c.is_active(), g.computers)
        
        finished_computers = []
        for g in self.groups.keys():
            finished_computers += filter(lambda c: c.wiped and c.is_registered, g.computers)

        total_progress = 0.0
        no_busy_computers = float(len(busy_computers))
        for c in busy_computers:
            total_progress += c.progress() / no_busy_computers
        
        # Update window title
        if no_busy_computers > 0:
            self.win.set_title('LCRS (busy)')
        elif no_computers == 0:
            self.win.set_title('LCRS')
        elif len(finished_computers) == no_computers:
            self.win.set_title('LCRS (everything complete)')
        else:
            self.win.set_title('LCRS (inactive)')
        
        progress_label = "Total computers: %d / Busy: %d" % (no_computers, no_busy_computers)

        self.getWidget("labelProgressbarTotal").set_text(progress_label)
        self.getWidget('progressbarTotal').set_fraction(total_progress)
    
    def update_overall_status(self):
        gobject.idle_add(self._update_overall_status)
    
    def add_group(self):
        def do_add_group():
            name = self.getWidget("entryGroupname").get_text()
            self.master_instance.addGroup(name)
        gobject.idle_add(do_add_group)
    
    def appendGroup(self, group):
        def do_append_group(group):
            """
            Adds a new group to the UI.
            """
            assert not group in self.groups, "Group already added."
            groupPage = GroupPage(group, self)
            self.groupNotebook.insert_page(groupPage.getPageWidget(), groupPage.getLabelWidget(), len(self.groups))
            self.groupNotebook.prev_page()
            self.groups[group] = groupPage
            self.update_overall_status()
        gobject.idle_add(do_append_group, group)

    def appendComputer(self, computer, group=None):
        def do_append_computer(computer, group):
            """
                Append a table row to the model object and a page to the notebook.
                The page is GtkBuilder'ed from a Glade file.
            """
            self.update_overall_status()
            if not group:
                group = self.groups.keys()[0]
            self.groups[group].addComputer(computer)
            self.update_overall_status()
    
        gobject.idle_add(do_append_computer, computer, group)
        gobject.idle_add(self.alert_plugins, 'on-add-computer')
    
    def update_computer(self, computer):
        """Find a computer in the right group and update its GtkNotebook page..."""
        for group in self.groups.keys():
            if computer in group.computers:
                self.groups[group].update_computer(computer)
    
    def open_preferences(self, *args):
        _ = PreferencesWindow()


