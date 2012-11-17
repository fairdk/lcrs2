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
from datetime import datetime
import os

from lcrs.master.ui.grouppage import GroupPage
from lcrs.master import config_master
import logging
logger = logging.getLogger('lcrs')

# should be replaced with something from logging module
LOG_ERR, LOG_WARNING, LOG_INFO = range(3)

class LogMsg:
    def __init__(self, msg, log_type=LOG_INFO, ts=None):
        if not ts:
            self.ts = datetime.now()
        else:
            self.ts = ts        
        self.msg = msg
        self.log_type = log_type

class MainWindow (object):
    """
    Main class for application window.  No widgets handled by this class -- only base
    data structures. Please see below implementation.
    
    Any public method should be listed here.
    
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
        
        for plugin_class, options in config_master.ui_plugins:
            if not options.get('disabled', False):
                p = plugin_class(self, self.config)
                self.plugins.append(p)
                p.activate()
                logger.debug("activating %s" % plugin_class.name)

    def plugin_subscribe(self, hook_id, callback):
        old_list = self.plugin_hooks.get(hook_id, [])
        old_list.append(callback)
        self.plugin_hooks[hook_id] = old_list

    def _appendLog(self, logMsg):
        self.log.append(logMsg)
    def appendLog(self, logMsg):
        gobject.idle_add(self._appendLog, logMsg)

    def _appendGroup (self, group):
        """
        Adds a new group to the UI.
        """
        assert not group in self.groups, "Group already added."
        self.appendLog(LogMsg("Appending group '%s'" % group.getName()))

    def appendGroup(self, group):
        gobject.idle_add(self._appendGroup, group)

    def _removeGroup (self, group):
        """
        Removes a group and destroys the group widget.
        """
        pass

    def removeGroup(self, group):
        gobject.idle_add(self._removeGroup, (group,))

    def _appendComputer (self, computer, group=None):
        """
            Append a table row to the model object and a page to the notebook.
            The page is GtkBuilder'ed from a Glade file.
        """
        self.appendLog(LogMsg("Adding computer..."))

    def appendComputer(self, computer, group=None):
        gobject.idle_add(self._appendComputer, computer, group)
        gobject.idle_add(self.alert_plugins, 'on-add-computer')

    def alert_plugins(self, event, *args):
        """We only return a single value, even if there are more than
           One plugin. Anything else seems overkill.
        """
        return_value = None
        for plugin_func in self.plugin_hooks.get(event, []):
            return_value = plugin_func(*args)
        return return_value
    


class BaseMainWindow(MainWindow):
    """
    Base implementation of ApplicationWindow
    """
    def __init__(self, *args, **kwargs):
        super(BaseMainWindow, self).__init__(*args, **kwargs)
    
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

        self.appendLog(LogMsg("Main window initialized..."))

        self.alert_plugins('on-mainwindow-ready')
    
    def show(self):
        self.win.show()
    
    def on_delete_event(self, *args):
        """
        Display manager closed window.
        """
        self.main_quit()
        return True # Do not destroy
    
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
        
        # Update status sidebar
        self.getWidget('labelTotalComputers').set_text(str(no_computers))
        self.getWidget('labelActiveComputers').set_text(str(len(busy_computers)))
        self.getWidget('labelFinishedComputers').set_text(str(len(finished_computers)))
        self.getWidget('progressbarTotal').set_fraction(total_progress)
    
    def update_overall_status(self):
        gobject.idle_add(self._update_overall_status)
    
    def add_group(self, *args):
        gobject.idle_add(self._add_group)
    
    def _add_group(self):
        name = self.getWidget("entryGroupname").get_text()
        self.master_instance.addGroup(name)
    
    def _appendLog(self, logMsg, *args, **kwargs):
        super(BaseMainWindow, self)._appendLog(logMsg, *args, **kwargs)
        buf = self.getWidget('textbufferLog')
        buf.insert(buf.get_end_iter(), logMsg.msg + "\n")

    def _appendGroup(self, group, *args, **kwargs):
        super(BaseMainWindow, self)._appendGroup(group, *args, **kwargs)        
        groupPage = GroupPage(group, self)
        self.groupNotebook.insert_page(groupPage.getPageWidget(), groupPage.getLabelWidget(), len(self.groups))
        self.groupNotebook.prev_page()
        self.groups[group] = groupPage
        self.update_overall_status()

    def _appendComputer (self, computer, group=None, **kwargs):
        super(BaseMainWindow, self)._appendComputer(computer, group, **kwargs)
        
        self.update_overall_status()
        if not group:
            group = self.groups.keys()[0]
        self.groups[group].addComputer(computer)
        self.update_overall_status()
        
    def open_preferences(self, *args):
        from preferenceswindow import PreferencesWindow
        _ = PreferencesWindow()


