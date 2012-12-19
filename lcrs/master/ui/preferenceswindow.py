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

import logging
import subprocess
import re
logger = logging.getLogger('lcrs')

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
        
        self.selected_plugin_class = None
        
        self.set_interface_options()
        
        self.set_values()
        self.set_combobox_plugins()
        
        self.get_widget("comboboxPlugins").connect('changed', self.on_combobox_plugins_change)
        self.get_widget("checkbuttonEnablePlugin").connect('toggled', self.on_checkbutton_plugin_enable_change)
        
        self.window.show()
    
    def set_interface_options(self):
        
        self.iface_lstore = gtk.ListStore(gobject.TYPE_STRING)
        ifconfig_out = subprocess.check_output("ifconfig")
        pattern_ifconfig =re.compile(r"^(\w+)\s*", re.MULTILINE)
        matches = pattern_ifconfig.findall(ifconfig_out)
        for match in matches:
            self.iface_lstore.append((match,))
        self.get_widget('server-iface').set_model(self.iface_lstore)
        #self.get_widget('server-iface').set_text_column(0)        
    
    def get_widget(self, key):
        """Use this object as a dictionary of widgets"""
        return self.uiApp.get_object(key)

    def close_window(self):
        self.save_config()
        self.window.destroy()
    
    def on_change_entry_pluginconfig(self, widget, plugin_class, key):
        logger.debug("Entry changing %s, %s to %s" % (plugin_class.plugin_id, key, widget.get_text()))
        config_master.ui_plugins[plugin_class][key] = widget.get_text()
    
    def on_change_checkbutton_pluginconfig(self, widget, plugin_class, key):
        logger.debug("Checkbutton changing %s, %s" % (plugin_class.plugin_id, key))
        config_master.ui_plugins[plugin_class][key] = widget.get_active()

    def set_combobox_plugins(self):
        cb = self.get_widget("comboboxPlugins")
        cb_liststore = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT, gobject.TYPE_PYOBJECT)
        cb.set_model(cb_liststore)
        cell = gtk.CellRendererText()
        cb.pack_start(cell, True)
        cb.add_attribute(cell, 'text', 0)
        for plugin_class, plugin_config in config_master.ui_plugins.items():
            cb_liststore.append(row=(plugin_class.name, plugin_class, plugin_config))
    
    def on_combobox_plugins_change(self, *args):
        selected = self.get_widget("comboboxPlugins").get_active()
        model = self.get_widget("comboboxPlugins").get_model()
        
        selected_iter = model.get_iter(selected)
        plugin_class = model.get(selected_iter, 1)[0]
        plugin_config = model.get(selected_iter, 2)[0]
        
        self.selected_plugin_class = plugin_class
        
        config_table = gtk.Table(len(plugin_class.config), 2, False)
        
        self.get_widget("labelPluginDescription").set_text(plugin_class.description)
        
        # NB! Do not change this pattern as the variable scope
        # inside the for loop makes the references to the invariants
        # change if the lambda is declared inside the for loop!
        def get_onchange(func, widget, plugin_class, entry_key):
            return lambda *x: func(widget, plugin_class, entry_key)
        
        for cnt, (k, v) in enumerate(plugin_class.config.items()):
            label = gtk.Label(str=v[0])
            label.set_alignment(0.0, 0.5)
            config_table.attach(label, 0, 1, cnt, cnt+1, xoptions=gtk.FILL|gtk.EXPAND, yoptions=0,
                                xpadding=10, ypadding=10)
            if isinstance(v[1], basestring):
                entry = gtk.Entry()
                on_change = get_onchange(self.on_change_entry_pluginconfig, entry, plugin_class, k)
                entry.connect('changed', on_change)
                entry.set_text(plugin_config[k])
                config_table.attach(entry, 1, 2, cnt, cnt+1, xpadding=10, ypadding=10)
            else:
                checkbutton = gtk.CheckButton()
                on_change = get_onchange(self.on_change_checkbutton_pluginconfig, checkbutton, plugin_class, k)
                checkbutton.connect('toggled', on_change)
                checkbutton.set_active(plugin_config[k])
                config_table.attach(checkbutton, 1, 2, cnt, cnt+1, xpadding=10, ypadding=10)
        
        config_table.show_all()
        
        current_child = self.get_widget("alignmentPluginsConfiguration").get_child()
        if current_child:
            self.get_widget("alignmentPluginsConfiguration").remove(current_child)
        self.get_widget("alignmentPluginsConfiguration").add(config_table)
        
        self.get_widget("alignmentPluginsConfiguration").show()
        
        self.get_widget("checkbuttonEnablePlugin").set_active(not plugin_config['disabled'])
        
    
    def on_checkbutton_plugin_enable_change(self, *args):
        if not self.selected_plugin_class:
            return
        config_master.ui_plugins[self.selected_plugin_class]['disabled'] = (
            not self.get_widget("checkbuttonEnablePlugin").get_active()
        )
    
    def on_delete_event(self, widget, callback_data):
        """
        Display manager closed window.
        """
        self.close_window()
        return True

    def on_close(self, widget):
        self.close_window()

    def set_values(self):
        self.iface_lstore.prepend((config_master.dhcpInterface,))
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
                
        
