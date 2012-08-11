#!/usr/bin/python

#
# LCRS Copyright (C) 2009-2011
# - Rene Jensen
# - Michael Wojciechowski
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

import gtk
gtk.gdk.threads_init() #@UndefinedVariable

import gobject
import sys
import os
import subprocess
import re

MASTER_PATH = os.path.abspath(__file__)
MASTER_PATH = os.path.split(MASTER_PATH)[0]
MASTER_PATH = os.path.join(MASTER_PATH, "..")
MASTER_PATH = os.path.abspath(MASTER_PATH)

sys.path.append(".")
sys.path.append(MASTER_PATH)

import logging
import socket
import threading

from ui import splash
from ui.mainwindow import BaseMainWindow
import config_master

from group import Group
from computer import Computer

class GtkMaster():
    """
    """
    def __init__(self):
        
        # Check if the selected interface is configured correctly...
        network_up = False
        try:
            ifconfig = subprocess.check_output(["ifconfig", config_master.dhcpInterface])
            p_ifconfig = re.compile(r"inet\s*addr:\s*%s" % re.escape(config_master.dhcpServerAddress))
            if not p_ifconfig.search(ifconfig):
                self.thread_failure_notify("The network interface (%s) is not up running with the correct IP address (%s). Check your settings or make sure that the network is running. Then restart." % (config_master.dhcpInterface, config_master.dhcpServerAddress))
            else:
                network_up = True
        except:
            self.thread_failure_notify("The network interface (%s) that is configured for the master server does not exist. Please check your settings or make sure that the network is running. Then restart." % config_master.dhcpInterface)
        
        #self.splash_window = splash.SplashWindow(self.start_main_window)     
        self.start_main_window()
        self.dhcpIp4Range = [ config_master.dhcpPrefix + str(ip) for ip in config_master.dhcpIpRange ]
        
        # The IP address has to match the address of the interface
        # used to send the dhcp packets.
        if network_up:
            
            try:
                from dhcp import DHCPManager
                self.dhcpmgr = DHCPManager (self.get_dhcp_address,
                                            config_master.dhcpServerAddress, config_master.dhcpInterface)
            except ImportError:
                self.thread_failure_notify("Could not start DHCP server. You do not have pydhcplib install. Try to run sudo apt-get install python-pydhcplib.")            
            except:
                self.thread_failure_notify("Could not start DHCP server. Please check that you are running the program as root and that no other instances of a DHCP server is running (e.g. another instance of LCRS).")            

        def tftpyListen():
            import tftpy #@UnresolvedImport
            try:
                tftpy.TftpShared.setLogLevel(logging.FATAL)
                tftp_path = os.path.abspath(config_master.tftpRoot)
                if not os.path.exists(tftp_path):
                    error = "TFTP directory does not exist! Could not start TFTP server. Please check your settings."
                    print error
                    self.thread_failure_notify(error)
                else:
                    print "Starting TFTP server in %s " % tftp_path
                    tftpserver = tftpy.TftpServer(tftp_path)
                    tftpserver.listen(listenip=config_master.dhcpServerAddress, listenport=69)
            except socket.error:
                error = "Error assigning IP %s address for TFTP server. Another one is running or you didn't run this program with root permissions. Perhaps another instance of the program is left running or you have started this instance before the ports could be freed." % config_master.dhcpServerAddress
                print error
                self.thread_failure_notify(error)
            except tftpy.TftpShared.TftpException:
                tftpyListen()

        def tftpdListen():
            tftp_path = os.path.abspath(config_master.tftpRoot)
            if not os.path.exists(tftp_path):
                error = "TFTP directory does not exist! Could not start TFTP server. Please check your settings."
                print error
                self.thread_failure_notify(error)
            else:
                os.system("killall in.tftpd")
                os.system("stop tftpd-hpa")
                print "Starting in.tftpd server in %s " % tftp_path
                ret = os.system("in.tftpd -a %s -s -l %s" % (config_master.dhcpServerAddress,
                                                             tftp_path))
                if ret != 0:
                    self.thread_failure_notify("Could not start TFTP server. Are you running the program with root privileges? Maybe you should do apt-get install tftpd-hpa")

        if network_up:
            self.tftp_thread = threading.Thread (target = tftpyListen if config_master.tftpTftpy else tftpdListen)
            self.tftp_thread.setDaemon(True)
            self.tftp_thread.start()
    
    def thread_failure_notify(self, msg):

        gobject.idle_add(self.thread_failure_notify_do, msg)

    def thread_failure_notify_do(self, msg):

        def on_close(dialog, *args):
            dialog.destroy()
        
        dialog = gtk.MessageDialog(message_format=msg,
                                   flags = gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                                   buttons = gtk.BUTTONS_OK,
                                   type=gtk.MESSAGE_ERROR)
        dialog.connect("response", on_close)
        dialog.show()

    def start_main_window(self):
        self.appWindow = BaseMainWindow()
        self.groups = []

        self.addGroup("New/busy")
        self.addGroup("Wiped")
        self.addGroup("Failed")
        
        #newmaster = Computer("Test", "127.0.0.1", "00:00:00:00:00")
        #self.groups[0].addComputer(newmaster)
        #self.appWindow.appendComputer(newmaster, self.groups[0])


    def get_dhcp_address (self, hwAddr):
        
        for computer in sum([g.computers for g in self.groups], []):
            if computer.macAddress == hwAddr:
                return computer.ipAddress
        
        ip = self.dhcpIp4Range.pop(0)
        
        newmaster = Computer(None, str(ip), str(hwAddr))
        self.groups[0].addComputer(newmaster)
        self.appWindow.appendComputer(newmaster, self.groups[0])
        return ip
    
    def addGroup(self, name):
        group = Group(name)
        self.groups.append(group)
        self.appWindow.appendGroup(group)

if __name__ == '__main__':

    app = GtkMaster()
    gtk.main()

    # Clean up
    os.system("killall in.tftpd")
    
