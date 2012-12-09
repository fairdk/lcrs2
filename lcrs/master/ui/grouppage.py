# -*- coding: utf-8 -*-
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

import gtk, gobject
import os
import time

from computerpanel import ComputerPanel
from reportdialog import ReportDialog
from getid import GetID
from lcrs.master.plugins import CallbackFailed
from lcrs.master import config_master
from lcrs.master.ui.decorators import idle_add_decorator

COLUMN_LENGTH = 10
(COLUMN_STATUS_ICON, COLUMN_ICON_SIZE, COLUMN_ID, COLUMN_ID_FONT,
 COLUMN_NETWORK, COLUMN_PROGRESS, COLUMN_WIPED, COLUMN_REGISTERED, 
 COLUMN_ACTIVITY, COLUMN_COMPUTER) = range(COLUMN_LENGTH)

import threading

class GroupPage():

    def __init__(self, group, mainwindow):
    
        self.group = group
        self.mainwindow = mainwindow
        self.current_computer = None
                
        glade = gtk.Builder()
        glade.add_objects_from_file(
            os.path.join(config_master.MASTER_PATH, 'ui/glade/mainwindow.glade'),
            ['groupPage']
        )
        
        self.glade = glade
        self.glade.connect_signals(self.mainwindow)
        
        self.iters = {}
        self.busy_panel = None

        self.groupPage = glade.get_object('groupPage')
        self.groupLabel = gtk.Label ()
        self.setTitle()
        
        self.treeview = glade.get_object('treeviewGroup')
        self.groupPanes = glade.get_object('groupPanes')
        
        self.groupPanes.remove(self.treeview)
        
        scrolledWindow = gtk.ScrolledWindow()
        
        scrolledWindow.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolledWindow.add(self.treeview)
        self.groupPanes.add1(scrolledWindow)
        scrolledWindow.show_all()

        self.panels = {}
        
        l = gtk.Label("Connect a computer to get started...")
        self.set_content_pane(l)
        
        self.treeview.connect("cursor-changed", self.on_cursor_changed)
        
        glade.get_object('toolbuttonRegister').connect('clicked', self.on_register_computer)
        glade.get_object('toolbuttonReset').connect('clicked', self.on_reset_computer)
        glade.get_object('toolbuttonDelete').connect('clicked', self.on_delete_computer)
        
        glade.get_object('toolbuttonReport').connect('clicked', self.on_save_report)
        glade.get_object('toolbuttonQuit').connect('clicked', self.on_quit)
        
        self.set_toolbar()
        
        # Status icon column
        cell = gtk.CellRendererPixbuf()
        col = gtk.TreeViewColumn("", cell, icon_name=COLUMN_STATUS_ICON, stock_size=COLUMN_ICON_SIZE)
        self.treeview.append_column(col)

        # ID column
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn("ID", cell, text=COLUMN_ID, font=COLUMN_ID_FONT)
        self.treeview.append_column(col)

        # Network column
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Network", cell, text=COLUMN_NETWORK)
        self.treeview.append_column(col)

        # Progress column
        cell = gtk.CellRendererProgress()
        col = gtk.TreeViewColumn("Progress", cell, value=COLUMN_PROGRESS)
        self.treeview.append_column(col)

        # Column for wiped icon
        cell = gtk.CellRendererPixbuf()
        col = gtk.TreeViewColumn("Wiped", cell, icon_name=COLUMN_WIPED, stock_size=COLUMN_ICON_SIZE)
        self.treeview.append_column(col)

        # Column for registered icon
        cell = gtk.CellRendererPixbuf()
        col = gtk.TreeViewColumn("Registered", cell, icon_name=COLUMN_REGISTERED, stock_size=COLUMN_ICON_SIZE)
        self.treeview.append_column(col)

        # Activity column
        cell = gtk.CellRendererText()
        col = gtk.TreeViewColumn("Activity", cell, text=COLUMN_ACTIVITY)
        self.treeview.append_column(col)
        
        # set model (i.e. the data it contains. We assume this is not done via glade.)
        self.liststore = gtk.ListStore(gobject.TYPE_STRING, 
                                       gobject.TYPE_INT, 
                                       gobject.TYPE_STRING, 
                                       gobject.TYPE_STRING, 
                                       gobject.TYPE_STRING, 
                                       gobject.TYPE_INT,     # Progress
                                       gobject.TYPE_STRING,  # Wiped
                                       gobject.TYPE_STRING,  # Registered
                                       gobject.TYPE_STRING,  # Activity
                                       gobject.TYPE_PYOBJECT,# Computer object
                                      )
        self.treeview.set_model(self.liststore)
        
        #self.treeview.drag_source_unset()
        #self.treeview.drag_dest_unset()
        #self.treeview.set_reorderable(True)
        
        t = threading.Thread(target=self.poll_computers)
        t.setDaemon(True)
        t.start()
    
    @idle_add_decorator
    def set_toolbar(self,):
        if self.current_computer:
            self.glade.get_object('toolbuttonRegister').set_sensitive(bool(self.current_computer.id))
            self.glade.get_object('toolbuttonReset').set_sensitive(True)
            self.glade.get_object('toolbuttonDelete').set_sensitive(True)
        else:
            self.glade.get_object('toolbuttonRegister').set_sensitive(False)
            self.glade.get_object('toolbuttonReset').set_sensitive(False)
            self.glade.get_object('toolbuttonDelete').set_sensitive(False)

    def getPageWidget(self):
        return self.groupPage
    
    def set_content_pane(self, new_pane):
        old_pane = self.groupPanes.get_child2()
        if old_pane == new_pane: return
        if old_pane:
            self.groupPanes.remove(old_pane)
        self.groupPanes.add2(new_pane)
    
    def on_cursor_changed(self, treeview):
        computer = self.get_selected_computer()
        if computer:
            self.show_computer(computer)
            
            
    def on_drag_data_received(self, treeview, context, x, y, selection, info, timestamp):
        model = treeview.get_model()
        data = selection.data
        drop_info = treeview.get_dest_row_at_pos(x, y)
        if drop_info:
            path, position = drop_info
            __ = model.get_iter(path)
            if (position == gtk.TREE_VIEW_DROP_BEFORE
                or position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE):
                pass
                #model.insert_before(iter, [data])
            else:
                pass
                #model.insert_after(iter, [data])
        else:
            pass
        if context.action == gtk.gdk.ACTION_MOVE: #@UndefinedVariable
            context.finish(True, True, timestamp)
            print data
        return

    
    def on_drag_data_get(self, treeview, context, selection, info, timestamp):
        pass
        #treeselection = treeview.get_selection()
        #model, iter = treeselection.get_selected()
        #data = model.get_value(iter, 0)
        #selection.set(selection.target, 8, data)

    def on_get_id(self, data, computer, *args):
        self.show_get_id(computer)

    def on_cancel_get_id(self, computer):
        self.show_computer(computer)

    def process(self, computer, scan, wipe, method, badblocks=False, autosubmit=False):
        """
        Process scan and wipe requests. Receive callbacks from Computer object's threads.
        REMEMBER THREAD SAFETY!!!!
        """
        #gobject.idle_add(self.show_busy, computer)

        def computer_progress(computer, progress):
            gobject.idle_add(self.__update_computer, computer, True)

        def do_wipe():
            
            def computer_finished(computer):
                gobject.idle_add(self.__update_computer, computer)
                if computer.wiped:
                    self.mainwindow.alert_plugins('on-wipe-finished', computer)
                    if autosubmit:
                        self.mainwindow.alert_plugins('on-auto-submit', computer)

            def computer_failed(computer):
                gobject.idle_add(self.__update_computer, computer)

            computer.wipe(method, badblocks=badblocks,
                          callback_progress=computer_progress,
                          callback_finished=computer_finished,
                          callback_failed=computer_failed)
        
        def do_scan():
        
            def finished(computer):
                gobject.idle_add(self.__update_computer, computer)
                self.mainwindow.alert_plugins('on-scan-finished', computer)
                if wipe:
                    do_wipe()

            def failed(computer):
                gobject.idle_add(self.__update_computer, computer)

            computer.scan(callback_progress=computer_progress,
                          callback_finished=finished,
                          callback_failed=failed)

        if scan:
            do_scan()
        

    def set_id(self, computer, input_id):

        self.show_busy(computer)
        
        def get_id_thread():
            if not input_id:
                new_id = None
            else:
                new_id = input_id
                old_id = computer.id
                computer.id = new_id if new_id != "" else None
                if not new_id:
                    gtk.idle_add(self.show_computer, computer)
                    return
                try:
                    self.mainwindow.alert_plugins('on-set-id', computer, input_id)
                except CallbackFailed:
                    computer.id = old_id
                    gobject.idle_add(self.show_get_id, computer)
                    return
            
            gobject.idle_add(self.__update_computer, computer)
            gobject.idle_add(self.show_computer, computer)
            
            if computer.id in [c.id for c in filter(lambda c: c != computer, self.group.computers)]:
                @idle_add_decorator
                def show_error():
                    def on_close(dialog, *args):
                        dialog.destroy()
                    dialog = gtk.MessageDialog(parent=self.mainwindow.win,
                                               type=gtk.MESSAGE_ERROR,
                                               buttons = gtk.BUTTONS_CLOSE,
                                               message_format="That ID is already in use!")
                    dialog.connect("response", on_close)
                    dialog.show()
                    self.show_computer(computer)
                    return
                show_error()
        
        t = threading.Thread(target=get_id_thread)
        t.setDaemon(True)
        t.start()
        
    def poll_computers(self):
        """
        Update the state of each computer.
        REMEMBER THREAD SAFETY!!!
        """
        while self.mainwindow.alive:
            for computer in self.group.computers:
                conn_before = computer.is_connected()
                computer.update_state()
                # Update currently displayed computer if it's changed!
                if conn_before != computer.is_connected():
                    if self.current_computer == computer or not self.current_computer:
                        gobject.idle_add(self.show_computer, computer)
                gobject.idle_add(self.__update_computer, computer, True)
            time.sleep(2)
    
    def show_computer(self, computer, small_update=False):

        if computer in self.panels.keys():
            panel = self.panels[computer]
            panel.update(small_update=small_update)
        else:
            panel = ComputerPanel(computer, self)
            panel.update(small_update=small_update)
            self.panels[computer] = panel
        
        if self.current_computer != computer:
            self.current_computer = computer
            self.set_content_pane(panel.get_widget())
        
        self.set_toolbar()

    def show_get_id(self, computer):
        self.set_toolbar()
        getid = GetID(computer, self)
        self.set_content_pane(getid.get_widget())
        self.current_computer = None
        getid.focus_id_entry()

    def show_busy(self, computer):

        if not self.busy_panel:
            glade = gtk.Builder()
            glade.add_objects_from_file(os.path.join(config_master.MASTER_PATH, 'ui/glade/throbber.glade'), ['eventboxWait'])
            mainContainer = glade.get_object('eventboxWait')
            glade.connect_signals(self.mainwindow)
            #throbber_animation = gtk.gdk.PixbufAnimation('ui/glade/throbber.gif')        #@UndefinedVariable
            #throbber = glade.get_object('throbberImage')
            #throbber.set_from_animation(throbber_animation)
            mainContainer.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("white")) #@UndefinedVariable
            self.busy_panel = mainContainer
        
        self.current_computer = None
        self.set_toolbar()
        self.set_content_pane(self.busy_panel)

    def show_nothing(self):
        
        self.glade.get_object('toolbuttonRegister').set_sensitive(False)
        self.glade.get_object('toolbuttonReset').set_sensitive(False)
        self.glade.get_object('toolbuttonDelete').set_sensitive(False)

        mainContainer = gtk.Frame()
        mainContainer.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("white")) #@UndefinedVariable
        self.set_content_pane(mainContainer)
        
    def getLabelWidget(self):
        return self.groupLabel

    def setTitle(self):
        self.groupLabel.set_text ('%s (%d)' % (self.group.getName(), len(self.group.computers)))

    def addComputer(self, computer):
        """
        Adds a Computer object to the liststore and treeview
        SHOULD BE THREAD SAFE!
        """
        
        self.setTitle()
        
        # Ignore computers that are already present
        if computer in self.iters.keys(): return
        
        row = [None for _ in range(COLUMN_LENGTH)]
        row[COLUMN_STATUS_ICON] = connection_icon(computer.is_connected())
        row[COLUMN_ICON_SIZE] = 4.0
        row[COLUMN_ID] = str(computer.id) if computer.id else "No ID"
        row[COLUMN_ID_FONT] = "normal 18"
        row[COLUMN_NETWORK] = "IP: %s\nMAC: %s" % (str(computer.ipAddress), str(computer.macAddress))
        row[COLUMN_PROGRESS] = computer.progress() * 100
        row[COLUMN_ACTIVITY] = computer.activity()
        row[COLUMN_COMPUTER] = computer
        row[COLUMN_WIPED] = wiped_icon(computer.wiped)
        row[COLUMN_REGISTERED] = register_icon(computer.is_registered)
        
        it = self.liststore.prepend(row=row)
        self.iters[computer] = it
        
    def get_selected_computer(self):
        cursor = self.treeview.get_cursor()
        if not cursor[0]:
            return None
        pos = cursor[0][0]
        it = self.liststore.get_iter(pos)
        return self.liststore.get(it, COLUMN_COMPUTER)[0]
        
    
    def on_delete_computer(self, *args):
        computer = self.get_selected_computer()
        if computer:
            self.removeComputer(computer)
        
    def on_reset_computer(self, *args):
        """
        May be called from other UI elements
        """
        computer = self.get_selected_computer()
        
        def on_dialog_reset(dialog, response_id):
            if dialog:
                dialog.destroy()
            if not response_id == gtk.RESPONSE_YES: return
            computer.reset()
            computer.update_state()
            self.__update_computer(computer)
            if computer in self.panels:
                self.panels[computer].update()
        
        if computer:
            dialog = gtk.MessageDialog(parent=self.mainwindow.win,
                                       type=gtk.MESSAGE_QUESTION,
                                       buttons = gtk.BUTTONS_YES_NO,
                                       message_format="Are you sure you comeplete want to reset this computer? This will attempt to stop all currently executing processes (ie. wiping) on the remote side and delete all data gathered about the computer.\n\nUse this function in case you are experiencing lock-ups.")
            dialog.connect("response", on_dialog_reset)
            dialog.connect("close", on_dialog_reset, gtk.RESPONSE_NO)
            dialog.show()

    
    def on_register_computer(self, *args):
        computer = self.get_selected_computer()
        if computer:
            self.register_computer(computer)

    def register_computer(self, computer):
        
        @idle_add_decorator
        def do_register(dialog, response_id, computer, *args):
            if dialog:
                dialog.destroy()
            if response_id == gtk.RESPONSE_NO:
                computer.is_registered = False
                return
            try:
                computer.is_registered = True
                self.mainwindow.alert_plugins('on-register-computer', computer)
            except CallbackFailed:
                pass
            self.update_computer(computer)

        if not computer.wiped:
            dialog = gtk.MessageDialog(parent=self.mainwindow.win,
                                       type=gtk.MESSAGE_QUESTION,
                                       buttons = gtk.BUTTONS_YES_NO,
                                       message_format="This computer is not wiped. Are you sure you want to register it?")
            dialog.connect("response", do_register, computer)
            dialog.connect("close", do_register, gtk.RESPONSE_NO, computer)
            dialog.show()
        else:
            do_register(None, None, computer)
    
    
    def removeComputer(self, computer):
        it = self.iters.get(computer, False)
        def do_delete(dialog, response_id):
            if dialog:
                dialog.destroy()
            if not response_id == gtk.RESPONSE_YES: return
            self.group.removeComputer(computer)
            self.liststore.remove(it)
            del self.iters[computer]
            self.mainwindow.update_overall_status()
            self.setTitle()
            if it:
                # Mark another computer as selected:
                path = self.treeview.get_path_at_pos(0,0)
                if path:
                    self.treeview.set_cursor(path[0])
            if computer in self.panels:
                if self.current_computer == computer:
                    self.show_nothing()
                del self.panels[computer]

        if it:
            dialog = gtk.MessageDialog(parent=self.mainwindow.win,
                                       type=gtk.MESSAGE_QUESTION,
                                       buttons = gtk.BUTTONS_YES_NO,
                                       message_format="Are you sure, you want to remove the computer from the list? (nothing will be deleted from the database)")
            dialog.connect("response", do_delete)
            dialog.connect("close", do_delete, gtk.RESPONSE_NO)
            dialog.show()
    
    def update_computer(self, computer):
        gobject.idle_add(self.__update_computer, computer)
    
    def __update_computer(self, computer, small_update=False):
        """small_update: denotes that hardware info and other such things should not be updated..."""
        
        it = self.iters.get(computer, False)
        if it and self.liststore.iter_is_valid(it):
            is_connected = computer.is_connected()
            self.liststore.set_value(it, COLUMN_STATUS_ICON, connection_icon(is_connected))
            self.liststore.set_value(it, COLUMN_ID, str(computer.id) if computer.id else "No ID")
            progress = computer.progress()
            self.liststore.set_value(it, COLUMN_PROGRESS, progress * 100 if type(progress) in (float, int) else 0)
            self.liststore.set_value(it, COLUMN_ACTIVITY, computer.activity())
            self.liststore.set_value(it, COLUMN_WIPED, wiped_icon(computer.wiped))
            self.liststore.set_value(it, COLUMN_REGISTERED, register_icon(computer.is_registered))
            self.mainwindow.update_overall_status()
        
        if computer == self.current_computer:
            self.show_computer(computer, small_update=small_update)        
            self.set_toolbar()
        
        
    def on_save_report(self, *args):
        __ = ReportDialog(self.group, self.mainwindow.groups)
    
    def on_quit(self, *args):
        self.mainwindow.main_quit()
    
def connection_icon(is_connected):
    if is_connected:
        return "network-idle"
    else:
        return "network-offline"

def wiped_icon(is_submitted):
    if is_submitted:
        return "gtk-yes"
    else:
        return "gtk-no"

def register_icon(is_submitted):
    if is_submitted:
        return "gtk-yes"
    else:
        return "gtk-no"
