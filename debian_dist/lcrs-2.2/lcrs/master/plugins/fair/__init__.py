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

CALLBACK_FAILED = "callback failed!"
URL_REGISTER = "/materials/barcode/"
URL_REGISTER_WEBSERVICE = "/materials/coresu/register/webservice/"

import gtk
import httplib, urllib, hashlib
import subprocess
import settings
import os
import simplejson as json
import shlex

from lcrs.master.plugins import CallbackFailed, BasePlugin

class FairIDPlugin(BasePlugin):
    
    plugin_id = "fair"
    name = "FAIR Plugins"
    description = ("""Login to FAIR servers. Get IDs from the database and return """ 
                   """their full title to be displayed in the UI. """
                   """Submit hardware data to web service. """)
    
    config = {'fair_server': ('Server name', 'www.fairdanmark.dk'),
              'fair_key': ('Server key', 'inputsecretvalue'),
              'use_https': ('Use SSL (secure) connection', True),
              }

    def __init__(self, *args, **kwargs):
        BasePlugin.__init__(self, *args, **kwargs)
        self.mainwindow_instance.fair_username = ""
        self.mainwindow_instance.fair_password = ""
        self.inserted = False
    
    def activate(self):
        self.mainwindow_instance.plugin_subscribe('on-set-id', self.on_set_id)
        self.mainwindow_instance.plugin_subscribe('on-mainwindow-ready', self.on_ready_login)
        self.mainwindow_instance.plugin_subscribe('on-register-computer', self.on_register)
        self.mainwindow_instance.plugin_subscribe('on-auto-submit', self.on_auto_submit)
    
    def deactivate(self):
        pass

    def on_set_id(self, computer, input_id):
        
        fail_msg = None
        try:
            if self.get_config("use_https"):
                conn = httplib.HTTPSConnection(self.get_config("fair_server"))
            else:
                conn = httplib.HTTPConnection(self.get_config("fair_server"))
            conn.request("GET", "/materials/coresu/getid/?id=%s" % input_id)
            r1 = conn.getresponse()
            if r1.status == 200:
                return r1.read()
            else:
                fail_msg = r1.read()
            conn.close()
        except:
            fail_msg = "Could not connect to FAIR server: %s" % self.get_config("fair_server")
            
        if fail_msg:

            def on_close(dialog, *args):
                dialog.destroy()

            dialog = gtk.MessageDialog(parent=self.mainwindow_instance.win,
                                       type=gtk.MESSAGE_ERROR,
                                       buttons = gtk.BUTTONS_CLOSE,
                                       message_format=fail_msg)
            dialog.connect("response", on_close)
            dialog.show()
            
            raise CallbackFailed()

    def on_ready_login(self, *args):
        
        # Add to file menu in mainwindow instance
        if not self.inserted:
            filemenu = self.mainwindow_instance.glade.get_object('menuFile')
            fairlogin = gtk.MenuItem(label="FAIR Login")
            fairlogin.connect('activate', self.on_ready_login)
            filemenu.insert(fairlogin, 2)
            filemenu.show_all()
            self.inserted = True

        glade = gtk.Builder()
        glade.add_from_file(
            os.path.join(self.config_master.MASTER_PATH, 'plugins/fair/glade/login.glade')
        )
        
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
        username = self.glade.get_object('entryUsername').get_text()
        password = self.glade.get_object('entryPassword').get_text()

        m = hashlib.md5()
        m.update(self.get_config("fair_key"))
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
                conn = httplib.HTTPSConnection(self.get_config("fair_server"))
            else:
                conn = httplib.HTTPConnection(self.get_config("fair_server"))
            conn.request("POST", "/materials/coresu/login/", params, headers)
            r1 = conn.getresponse()
            if r1.status == 200:
                self.mainwindow_instance.fair_username = username
                self.mainwindow_instance.fair_password = password
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
            
    
    
    def on_auto_submit(self, computer):
        m = hashlib.md5()
        m.update(settings.FAIR_SECRET_KEY)
        m.update(self.mainwindow_instance.fair_username)
        m.update(self.mainwindow_instance.fair_password)
        checksum = m.hexdigest()

        if hasattr(computer, 'hw_info'):
            json_data = json.dumps(computer.hw_info)
        else:
            json_data = ""

        params = urllib.urlencode({'username': str(self.mainwindow_instance.fair_username),
                                   'password': str(self.mainwindow_instance.fair_password),
                                   'wiped': "1" if computer.wiped else "",
                                   'barcode': str(computer.id),
                                   'hash': checksum,
                                   'json': json_data,
                                   })
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain"}
        if getattr(settings, 'USE_HTTPS', True):
            conn = httplib.HTTPSConnection(settings.FAIR_SERVER)
        else:
            conn = httplib.HTTPConnection(settings.FAIR_SERVER)
        conn.request("POST", URL_REGISTER_WEBSERVICE, params, headers)
        response = conn.getresponse()
        data = response.read()
        if response.status != 200:
            # TODO: Handle this in the log file
            print "ERROR IN REGISTRATION: %s" % data
        conn.close()


    def on_register(self, computer, grouppage):
        
        computer.is_registered = True
        grouppage.update_row(computer)
        self.on_auto_submit(computer)
        
        if self.get_config("use_https"):
            url = "https://%s%s%s" % (self.get_config("fair_server"), URL_REGISTER, computer.id)
        else:
            url = "http://%s%s%s" % (self.get_config("fair_server"), URL_REGISTER, computer.id)
        username = os.getenv("SUDO_USER")
        
        if username:
            subprocess.Popen(shlex.split("su %s -c \"xdg-open %s\"" % (username, url)))
        else:
            subprocess.Popen(shlex.split("xdg-open %s" % url))
        
        
        def on_close(dialog, *args):
            dialog.destroy()

