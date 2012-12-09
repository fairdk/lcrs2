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
import gobject

CALLBACK_FAILED = "callback failed!"
URL_REGISTER = "/materials/barcode/"
URL_REGISTER_WEBSERVICE = "/materials/coresu/register/webservice/"

import gtk
import httplib, urllib, hashlib
import subprocess
import os
import simplejson as json
import shlex

import threading

from lcrs.master.plugins import CallbackFailed, BasePlugin

import logging
logger = logging.getLogger("lcrs")

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
                json_return_data = json.loads(r1.read())
                computer_id = json_return_data.get('id', None)
                if not computer_id:
                    raise CallbackFailed()
                computer.id = computer_id
                computer.wiped = json_return_data.get('wiped', False)
                return
            else:
                fail_msg = r1.read()
            conn.close()
        except:
            fail_msg = "Could not connect to FAIR server: %s" % self.get_config("fair_server")
            
        if fail_msg:

            self.show_error_msg(fail_msg)
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
            if self.get_config("use_https"):
                conn = httplib.HTTPSConnection(self.get_config("fair_server"))
            else:
                conn = httplib.HTTPConnection(self.get_config("fair_server"))
            conn.request("POST", "/materials/coresu/login/", params, headers)
            r1 = conn.getresponse()
            if r1.status == 200:
                self.mainwindow_instance.fair_username = username
                self.mainwindow_instance.fair_password = password
                self.win.destroy()
            else:
                fail_msg = r1.read()
            conn.close()
        except:
            fail_msg = "Could not connect to FAIR server"
            
        if fail_msg:
            self.glade.get_object('buttonLogin').set_sensitive(True)            
            self.show_error_msg(fail_msg, parent=self.win)
    
    
    def on_auto_submit(self, computer):
        m = hashlib.md5()
        m.update(self.get_config("fair_key"))
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
        if self.get_config("use_https"):
            conn = httplib.HTTPSConnection(self.get_config("fair_server"))
        else:
            conn = httplib.HTTPConnection(self.get_config("fair_server"))
        conn.request("POST", URL_REGISTER_WEBSERVICE, params, headers)
        response = conn.getresponse()
        data = response.read()
        if response.status != 200:
            errmsg = "autosubmit plugin failed: %s" % str(data)
            self.show_error_msg(errmsg)
            logger.critical(errmsg)
        conn.close()

    def on_register(self, computer):
        
        def register_thread():
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
    
        t = threading.Thread(target=register_thread)
        t.setDaemon(True)
        t.start()
        