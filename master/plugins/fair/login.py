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

import httplib, urllib
import gtk

import settings

from plugins import BasePlugin #@UnresolvedImport

class FairLoginPlugin(BasePlugin):

    name = "FAIR Login"
    description = ("Sends the scanned result in raw JSON to the FAIR server where"
                   " it can then be stored. The interface is done with GtkMozEmbed")

    def __init__(self, mainwindow_instance):
        self.mainwindow_instance = mainwindow_instance
        self.mainwindow_instance.fair_username = ""
        self.mainwindow_instance.fair_password = ""
        self.inserted = False
        
    def activate(self):
        self.mainwindow_instance.plugin_subscribe('on-mainwindow-ready', self.on_ready)
    
    def on_ready(self, *args):
        
        # Add to file menu in mainwindow instance
        if not self.inserted:
            filemenu = self.mainwindow_instance.glade.get_object('menuFile')
            fairlogin = gtk.MenuItem(label="FAIR Login")
            fairlogin.connect('activate', self.on_ready)
            filemenu.insert(fairlogin, 2)
            filemenu.show_all()
            self.inserted = True

        glade = gtk.Builder()
        glade.add_from_file('plugins/fair/glade/login.glade')
        
        glade.get_object('buttonCancel').connect('clicked', self.close)
        glade.get_object('buttonLogin').connect('clicked', self.login)
        glade.get_object('entryUsername').connect('activate', self.login)
        glade.get_object('entryPassword').connect('activate', self.login)
        
        win = glade.get_object('windowFairLogin')
        win.show_all()

        self.win = win
        self.glade = glade
        
    def close(self, *args):
        self.win.destroy()

    def login(self, *args):
        import hashlib
        username = self.glade.get_object('entryUsername').get_text()
        password = self.glade.get_object('entryPassword').get_text()

        m = hashlib.md5()
        m.update(settings.FAIR_SECRET_KEY)
        m.update(username)
        m.update(password)

        checksum = m.hexdigest()
        
        fail_msg = None
        try:
            self.glade.get_object('buttonLogin').set_sensitive(False)
            params = urllib.urlencode({'u': username, 'p': password, 'c': checksum})
            headers = {"Content-type": "application/x-www-form-urlencoded",
                       "Accept": "text/plain"}
            if getattr(settings, 'USE_HTTPS', True):
                conn = httplib.HTTPSConnection(settings.FAIR_SERVER)
            else:
                conn = httplib.HTTPConnection(settings.FAIR_SERVER)
            conn.request("POST", "/materials/coresu/login/", params, headers)
            r1 = conn.getresponse()
            if r1.status == 200:
                self.mainwindow_instance.fair_username = username
                self.mainwindow_instance.fair_password = password
                from master.ui.mainwindow import LogMsg
                self.mainwindow_instance.appendLog(LogMsg("FAIR: Logged in as %s" % username))
                self.win.destroy()
                #def on_close(dialog, *args):
                #    dialog.destroy()
                #    self.win.destroy()
                #dialog = gtk.MessageDialog(parent=self.win,
                #                           type=gtk.MESSAGE_INFO,
                #                           buttons = gtk.BUTTONS_CLOSE,
                #                           message_format="You are now logged in!",)
                #dialog.set_modal(True)
                #dialog.connect("response", on_close)
                #dialog.show()

            else:
                self.glade.get_object('buttonLogin').set_sensitive(True)
                fail_msg = r1.read()
            conn.close()
        except:
            fail_msg = "Could not connect to FAIR server"
            
        
        if fail_msg:

            def on_close(dialog, *args):
                self.glade.get_object('buttonLogin').set_sensitive(True)
                dialog.destroy()

            dialog = gtk.MessageDialog(parent=self.win,
                                       type=gtk.MESSAGE_ERROR,
                                       buttons = gtk.BUTTONS_CLOSE,
                                       message_format=fail_msg,)
            dialog.set_modal(True)
            dialog.connect("response", on_close)
            dialog.show()
            
