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

import httplib, urllib, hashlib
import subprocess
import gtk
import settings
import os
import simplejson as json
import shlex

URL_REGISTER = "/materials/barcode/"
URL_REGISTER_WEBSERVICE = "/materials/coresu/register/webservice/"

from plugins import BasePlugin

class FairRegisterPlugin(BasePlugin):

    name = "FAIR computer registration"
    description = ("Posts data to fairdanmark.dk and uses xdg-open to load a browser with a window to verify the computer.")

    def __init__(self, mainwindow_instance):
        self.mainwindow_instance = mainwindow_instance
    
    def on_delete_event(self):
        pass
    
    def activate(self):
        self.mainwindow_instance.plugin_subscribe('on-register-computer', self.on_register)
        self.mainwindow_instance.plugin_subscribe('on-auto-submit', self.on_auto_submit)
    
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
        
        url = "http://%s%s%s" % (settings.FAIR_SERVER, URL_REGISTER, computer.id)
        username = os.getenv("SUDO_USER")
        
        if username:
            process = subprocess.Popen(shlex.split("su %s -c \"xdg-open %s\"" % (username, url)))
        else:
            process = subprocess.Popen(shlex.split("xdg-open %s" % url))
        
        
        def on_close(dialog, *args):
            dialog.destroy()

