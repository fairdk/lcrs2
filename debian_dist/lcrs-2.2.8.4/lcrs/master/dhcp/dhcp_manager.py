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

import threading
import socket
import IN

from pydhcplib import dhcp_packet
from pydhcplib import dhcp_network

from utils import octetsAsInts
from utils import fillFixedBuffer

"""
    This module deals with IP's represented as either string: '10.20.30.40' or lists of ints: [10,20,30,40]
    No other representation should be used. Various functions should convert on the go.
"""


class DHCPManager(dhcp_network.DhcpNetwork):
    """
    """
    def __init__ (self, get_address=None, serverAddress='10.20.20.1', netcard="eth1"):

        self.get_address = get_address
        self.serverAddress = serverAddress
        self.memory = {}
        
        dhcp_network.DhcpNetwork.__init__(self, netcard, "67", "68")

        self.EnableBroadcast()
        self.DisableReuseaddr()

        self.CreateSocket()
        self.BindToDevice()

        self.dhcpThread = threading.Thread (target = self.driveDHCPthread)
        self.dhcpThread.setDaemon(True)
        self.dhcpThread.start()


    def BindToDevice(self) :
        try :
            self.dhcp_socket.setsockopt(socket.SOL_SOCKET,IN.SO_BINDTODEVICE,self.listen_address+'\0')
        except socket.error, msg :
            raise Exception("DHCP server error binding to device (%s:%s): %s" % (self.listen_address, self.listen_port, str(msg)))

        try :
            self.dhcp_socket.bind(('', self.listen_port))
        except socket.error, msg :
            raise Exception("DHCP server error binding to device (%s:%s): %s" % (self.listen_address, self.listen_port, str(msg)))

    def addBootInfoAndBroadcast (self, packet, clientAddress):

        packet.SetMultipleOptions ({
            #'tftp_server_name': map(ord, '10.20.20.1'),
            #'bootfile_name': map(ord, 'pxelinux.0'),
            'server_identifier': octetsAsInts (self.serverAddress),
            'sname': fillFixedBuffer (64, self.serverAddress),      #map(ord,self.tftpServerAddress) + [0]*( 64-len(self.tftpServerAddress)),
            'file' : fillFixedBuffer (128, 'pxelinux.0'),           #map(ord,'pxelinux.0') + [0]*(128-len('pxelinux.0')),
            'ciaddr': octetsAsInts (self.serverAddress),                 #[10,20,20,100],
            'yiaddr': octetsAsInts (clientAddress),                 #[10,20,20,100],
            'siaddr': octetsAsInts (self.serverAddress)             #[10,20,20,1]
            })
        self.SendDhcpPacketTo (packet, "255.255.255.255", 68)

    def HandleDhcpDiscover(self, packet):
        clientMacAddress = ":".join ('%02x'%i for i in packet.GetHardwareAddress())
        try:
            clientAddress = self.get_address(clientMacAddress)
        except:
            return

        self.memory[ clientMacAddress ] = clientAddress

        packet.SetMultipleOptions ({'ip_address_lease_time': [0,2,0,0]})  # Think it means 2*256*256 seconds :)
        offer = dhcp_packet.DhcpPacket()
        offer.CreateDhcpOfferPacketFrom (packet)
        self.addBootInfoAndBroadcast (offer, clientAddress)

    def HandleDhcpRequest(self, packet):
        clientMacAddress = ":".join ('%02x'%i for i in packet.GetHardwareAddress())

        if clientMacAddress in self.memory:
            clientAddress = self.memory[ clientMacAddress ]

            packet.TransformToDhcpAckPacket()
            self.addBootInfoAndBroadcast (packet, clientAddress)
        else:
            print "Odd error: Why can't I remember this hardware/mac address?: " + clientMacAddress

    def driveDHCPthread (self):
        """
            The main driving loop that breathes life into the threadless DhcpServer
        """
        while True :
            self.GetNextDhcpPacket()

