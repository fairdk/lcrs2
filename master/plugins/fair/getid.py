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

import httplib
import gtk

from plugins import CallbackFailed, BasePlugin #@UnresolvedImport

import settings

class FairIDPlugin(BasePlugin):
    
    name = "FAIR ID plugin"
    description = "Gets IDs from the database and returns their full title to be displayed in the UI."

    def __init__(self, mainwindow_instance):
        self.mainwindow_instance = mainwindow_instance
    
    def activate(self):
        self.mainwindow_instance.plugin_subscribe('on-set-id', self.on_set_id)
    
    def on_set_id(self, computer, input_id):
        
        fail_msg = None
        try:
            conn = httplib.HTTPSConnection(settings.FAIR_SERVER)
            conn.request("GET", "/materials/coresu/getid/?id=%s" % input_id)
            r1 = conn.getresponse()
            if r1.status == 200:
                return r1.read()
            else:
                fail_msg = r1.read()
            conn.close()
        except:
            fail_msg = "Could not connect to FAIR server"
            
        
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
    
    def deactivate(self):
        pass
            
