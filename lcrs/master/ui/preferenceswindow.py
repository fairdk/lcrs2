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
import os

from lcrs.master import config_master

class PreferencesWindow:
    def __init__(self):
        self.uiApp = gtk.Builder()
        self.uiApp.add_from_file(
            os.path.join(config_master.MASTER_PATH, 'ui/glade/preferences.glade')
        )
        self.uiApp.connect_signals (self)

        self.window = self.uiApp.get_object ('preferences-window')
        self.window.connect("delete-event", self.on_delete_event)
        
        self.set_values()
        
        self.window.show()

    def get_widget(self, key):
        """Use this object as a dictionary of widgets"""
        return self.uiApp.get_object(key)

    def close_window(self):
        self.save_config()
        self.window.destroy()

    def on_delete_event(self, widget, callback_data):
        """
        Display manager closed window.
        """
        self.close_window()
        return True

    def on_close(self, widget):
        self.close_window()

    def set_values(self):
        lstore = gtk.ListStore(gobject.TYPE_STRING)
        lstore.append((config_master.dhcpInterface,))
        self.get_widget('server-iface').set_model(lstore)
        self.get_widget('server-iface').set_text_column(0)
        self.get_widget('server-iface').set_active(0)
        self.get_widget('server-ip').set_text(config_master.dhcpServerAddress)
        self.get_widget('dhcp-prefix').set_text(config_master.dhcpPrefix)
        self.get_widget('dhcp-range-lower').set_value(min(config_master.dhcpIpRange))
        self.get_widget('dhcp-range-upper').set_value(max(config_master.dhcpIpRange))
        self.get_widget('tftp-rootfolder').set_current_folder(config_master.tftpRoot)
        self.get_widget('tftpy').set_active(config_master.tftpTftpy)

    def save_config(self, *args):
        
        config_master.dhcpServerAddress = self.get_widget('server-ip').get_text()
        config_master.dhcpInterface = self.get_widget('server-iface').get_active_text()
        config_master.dhcpPrefix = self.get_widget('dhcp-prefix').get_text()
        dhcp_range_lower = self.get_widget('dhcp-range-lower').get_value_as_int()
        dhcp_range_upper = self.get_widget('dhcp-range-upper').get_value_as_int()
        config_master.dhcpIpRange = range(dhcp_range_lower, dhcp_range_upper+1)
        config_master.tftpRoot = self.get_widget('tftp-rootfolder').get_current_folder()
        config_master.tftpTftpy = self.get_widget('tftpy').get_active()
        config_master.write_config()
                
        
