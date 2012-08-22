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
import logging
import time
import socket
import sys
import simplejson as json
from datetime import datetime

from slave import protocol
from slave import settings as slave_settings
import re
import random

# create logger
logger = logging.getLogger('lcrs_master')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


# Exceptions. All are handled within the computer object!
class ConnectionException(Exception):
    """Raised when a socket error occurs"""
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)

class ResponseFailException(Exception):
    """Raised when remote site sends back"""
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)

# States of the master-side representation of the slave
NOT_CONNECTED, CONNECTED, SCANNING, SCANNED, WIPING, WIPED, FAIL = range(7)

# Shell commands for the first iteration and functions for analyzing data
SCAN_ITERATION_1 = {
    "/usr/sbin/lspci": "analyze_lspci_data",
    "dmesg": "analyze_dmesg_data",
    "dmidecode -s system-manufacturer": "analyze_dmidecode_manufacturer",
    "dmidecode -s system-uuid": "analyze_dmidecode_uuid",
    "dmidecode -s system-serial-number": "analyze_dmidecode_system_sn",
    "dmidecode -s baseboard-serial-number": "analyze_dmidecode_bios_sn",
    "dmidecode -t system": "analyze_dmidecode_system",
    "dmidecode --string chassis-type": "analyze_dmidecode_chassis_type",
    "cat /proc/meminfo": "analyze_meminfo_data",
    "dmidecode -t memory": "analyze_dmidecode_memory",
    "cat /proc/cpuinfo": "analyze_cpu_data",
    "cat /proc/sys/dev/cdrom/info": "analyze_cdrom_info",
}

# Shell commands for second iteration. Each command has a tuple (analyze function, command parser)
# for analyzing output and parsing the command (for possible inclusion of data from the first iteration)
SCAN_ITERATION_2 = {
    "echo %(sdX)s && hdparm -i /dev/%(sdX)s": ("analyze_hdparm", lambda com, hw: [com % {'sdX': key} for key in hw.get("Hard drives", {}).keys()]),
    "echo %(sdX)s && sdparm -q -p sn /dev/%(sdX)s": ("analyze_sdparm", lambda com, hw: [com % {'sdX': key} for key in hw.get("Hard drives", {}).keys()]),
    "echo %(sdX)s && blockdev --getsize64 /dev/%(sdX)s": ("analyze_blockdev", lambda com, hw: [com % {'sdX': key} for key in hw.get("Hard drives", {}).keys()]),
}

HDD_DUMP_COMMAND = "dd if=/dev/%(dev)s ibs=%(blocksize)d count=%(blocks)d skip=%(offset)d | hexdump -v"
HDD_DUMP_BLOCKSIZE = 512
HDD_DUMP_BLOCKS = 1
        
WIPE_METHODS = {
    "Wipe (zeros)": "wipe -z -v -l0 -p1 /dev/%(dev)s"
}

BADBLOCKS = "badblocks -c 1 -s /dev/%(dev)s"

class Computer():
    """
    """

    def __init__(self, computer_id, ipAddress, macAddress):

        self.id         = computer_id
        self.ipAddress  = ipAddress
        self.macAddress = macAddress

        # Activity information
        self.__is_active = False
        self.__is_connected = False
        self.__state = NOT_CONNECTED
        self.__activity = "Not connected"
        
        self.__progress = 0.0 # 0.0 - 1.0 indicating progress of current operation
        
        # Info from hardware scan
        self.hw_info = {}
        self.scanned = False # If false, we should not allow wipe operation

        # Information from wipe job
        self.wiped = False
        self.wipe_started_on = None
        self.wipe_finished_on = None
        self.wipe_duration = None
        self.wipe_method = None
        self.wipe_hexsample_before = None # Hex-digest of some sector on HD
        self.wipe_hexsample_after  = None # Hex-digest of some sector on HD

        self.is_registered = False # Says whether the computer has been registered in some database

    def scan(self, callback_progress=None, callback_finished=None, 
             callback_failed=None):
        """Spawn scan process and receive call backs"""
        self.scanned = False
        if self.__is_active:
            return
        self.__is_active = True
        self.__state = SCANNING
        t = threading.Thread(target=self.__scan_thread, args=(callback_progress, 
                                                              callback_finished, 
                                                              callback_failed))
        t.setDaemon(True)
        t.start()
        
    def __scan_thread(self, callback_progress=None, callback_finished=None, 
                      callback_failed=None):
        """
        Send a list of commands to the slave, and poll the slave for progress updates.
        Finally, analyze the output of all the commands.
        """
        
        # Some progress related fractions
        total_amount_of_commands = len(SCAN_ITERATION_1.keys())+len(SCAN_ITERATION_2.keys())
        scan1_share = len(SCAN_ITERATION_1.keys()) / float(total_amount_of_commands)
        scan2_share = len(SCAN_ITERATION_2.keys()) / float(total_amount_of_commands)
        
        def callback_progress1(progress, state):
            self.__progress = progress / scan1_share
            self.__activity = protocol.translate_state(state)
            callback_progress(self, progress) if callback_progress else ()
        
        def callback_progress2(progress, state):
            self.__progress = progress / scan2_share
            self.__activity = protocol.translate_state(state)
            callback_progress(self, progress) if callback_progress else ()

        # Send the scan1 list of commands to execute
        commands = SCAN_ITERATION_1.keys()
        
        try:
            if not self.__request_and_monitor(commands, callback_progress1,
                                              callback_finished, callback_failed):
                return
            
            # Get results from scan 1
            request = (protocol.HARDWARE, None)
            __, data = self.__send_to_slave(request)
            self.__analyze_scan_data(data)
        except ConnectionException, msg:
            self.__activity = "Scan failed: %s" % (msg)
            self.__is_active = False
            callback_failed(self) if callback_failed else ()
            return
            
        # Send the scan2 list of commands to execute
        commands = []
        for command, (__, parse_command) in SCAN_ITERATION_2.items():
            if parse_command:
                commands = commands + parse_command(command, self.hw_info)
            else:
                commands.append(command)

        if not self.__request_and_monitor(commands, callback_progress2,
                                          callback_finished, callback_failed):
            return

        # Get results from scan 2
        request = (protocol.HARDWARE, None)
        state, data = self.__send_to_slave(request)
        self.__analyze_scan_data(data)

        self.__progress = 1.0
        self.__activity = "Scanning finished" if not state == protocol.FAIL else "Scanning failed"
        self.__is_active = False
        self.__state = SCANNED
        self.scanned = True
        callback_finished(self) if callback_finished else ()
    
    def __request_and_monitor(self, scan_commands, callback_progress=None, 
                              callback_finished=None, callback_failed=None):
        
        request = (protocol.SCAN, scan_commands)
        status, data = self.__send_to_slave(request)
        
        # If something went wrong...
        if status == protocol.FAIL:
            callback_failed(self) if callback_failed else ()
            logger.warning("SCAN failed. Reason: %s" % str(data))
            self.__state = FAIL
            self.__activity = str(data)
            self.__is_active = False
            return False
        
        # Start monitoring scan 1
        self.__activity = "Scanning"
        while not self.scanned:
            (state, progress) = self.slave_state()
            callback_progress(progress, state) if callback_progress else ()
            if state == protocol.FAIL:
                self.__activity = "Scan failed"
                self.__state = FAIL
                self.__is_active = False
                logger.warning("SCAN failed during execution.")
                callback_failed(self) if callback_failed else ()
                return False
            if state == protocol.IDLE:
                return True
            time.sleep(1)
    
    def __analyze_scan_data(self, data):
        
        for k1, (stdout, stderr) in data.items():
            
            for command, analyze_func in SCAN_ITERATION_1.items():
                if k1 == command:
                    if callable(analyze_func):
                        func = analyze_func
                    else:
                        func = getattr(self, analyze_func)
                    self.hw_info = func(stdout, stderr, self.hw_info)
    
            for command, (analyze_func, parse_command) in SCAN_ITERATION_2.items():
                if parse_command:
                    commands = parse_command(command, self.hw_info)
                else:
                    commands = [command]
                for command in commands:
                    if k1 == command:
                        if callable(analyze_func):
                            func = analyze_func
                        else:
                            func = getattr(self, analyze_func)
                        self.hw_info = func(stdout, stderr, self.hw_info)

    def __send_to_slave(self, request):
        request = json.dumps(request)
        reply = ""
        for __ in range(10):
            # Retry 10 times
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout (2.0)
                s.connect( (self.ipAddress, slave_settings.LISTEN_PORT) )
                s.settimeout (10.0)
                s.send(request)
                if not self.__is_connected:
                    self.__activity = "Connected"
                    self.__is_connected = True
                break
            except socket.timeout:
                time.sleep(1)
                self.__is_connected = False
            except socket.error:
                s.close()
                self.__activity = "Not connected"
                self.__is_connected = False
                logger.error("Could not connect")
                raise ConnectionException("Could not connect")
            except:
                s.close()
                e = sys.exc_info()[1]
                self.__activity = "Error connecting."
                logger.error(e)
                self.__is_connected = False
                raise ConnectionException("Could not connect")
        
        if not self.__is_connected:
            s.close()
            raise ConnectionException("Timeout connecting")

        retries = 0
        while True:
            try:
                reply = reply + s.recv (slave_settings.MAX_PACKET_SIZE)
                self.__is_connected = True
                reply = json.loads(reply)
                break
            except json.JSONDecodeError:
                continue
            except ValueError:
                continue
            except socket.timeout:
                s.close()
                retries += 1
                if retries > 5: raise ConnectionException("Timeout while receiving reply")
                time.sleep(10)
                self.__is_connected = False
                continue
            except socket.error:
                s.close()
                self.__activity = "Not connected"
                self.__is_connected = False
                logger.error("Could not connect after sending request")
                raise ConnectionException("Could not connect")
            
        s.close()
        return reply

    def slave_state(self, **kwargs):
        """Get status message and progress from slave
        """
        try:
            request = (protocol.STATUS, kwargs)
            state, progress = self.__send_to_slave(request)
            return state, progress
        except ConnectionException:
            return (protocol.FAIL, "Could not connect")

    def update_state(self):
        __, progress = self.slave_state()
        self.__progress = progress
    
    def wipe(self, method, badblocks=False,
             callback_finished=None, callback_failed=None,
             callback_progress=None):
        """Spawn wipe process and receive call backs"""
        if not self.scanned:
            return
        
        logger.info("Now wiping hard drives on IP: %s" % str(self.ipAddress))
        
        self.__is_active = True
        self.wiped = False
        self.__state = WIPING
        self.wipe_method = method
        self.drives = self.hw_info.get('Hard drives', {}).keys()        
        self.wiped = False
        self.wipe_started_on = datetime.now()

        if not self.drives:
            self.__activity = "No hard drives detected!"
            self.__progress = 1.0
            self.__is_active = False
            callback_failed(self) if callback_failed else ()
            return
        
        callback_progress(self, self.__progress) if callback_progress else ()
        wipe_cnt = 0
        for dev_name in self.drives:
            wipe_cnt = wipe_cnt + 1
            self.__activity = "Wiping drive %d of %d" % (wipe_cnt, len(self.drives))
            callback_progress(self, self.__progress) if callback_progress else ()
            try:
                self.__wipe_drive(dev_name, method, badblocks, callback_progress)
            except ResponseFailException, msg:
                self.__activity = "Wipe failed on drive %d: %s" % (wipe_cnt, str(msg))
                self.__is_active = False
                callback_failed(self) if callback_failed else ()
                return

        self.__activity = "All drives wiped!"
        self.__progress = 1.0
        self.__is_active = False
        self.wiped = True
        self.__state = WIPED
        self.wipe_finished_on = datetime.now()
        callback_finished(self) if callback_finished else ()

    def __wipe_drive(self, dev_name, method, badblocks=False, callback_progress=None):
        
        self.__progress = 0.0
        self.hw_info["Hard drives"][dev_name]["Dump before"] = self.__wipe_dump(dev_name)
        
        #TODO: Standardise these values all over the project!
        self.hw_info["Hard drives"][dev_name]["Wipe method"] = "wipe standard"
        self.hw_info["Hard drives"][dev_name]["Passes"] = 1
        callback_progress(self, self.__progress) if callback_progress else ()

        if badblocks:
            badblocks_command = BADBLOCKS % {'dev': dev_name,}
            request = (protocol.BADBLOCKS, badblocks_command)
            self.__send_to_slave(request)
            
            while True:
                
                state, data = self.slave_state(fail_message=True)
                if state == protocol.FAIL:
                    logger.error("Badblocks detected! Output was: %s" % str(data))
                    self.hw_info["Hard drives"][dev_name]["Badblocks"] = True
                    raise ResponseFailException("Badblocks detected!")
                # TODO: Make a better solution for detecting finished jobs??
                if state == protocol.IDLE:
                    self.__progress = 1.0
                    self.hw_info["Hard drives"][dev_name]["Badblocks"] = False
                    break
                progress = data
                callback_progress(self, progress) if callback_progress else ()
                time.sleep(2)

        wipe_command = WIPE_METHODS[method] % {'dev': dev_name,}
        request = (protocol.WIPE, wipe_command)
        self.__send_to_slave(request)
        
        while True:
            
            state, data = self.slave_state(fail_message=True)
            if state == protocol.FAIL:
                logger.error("Something went wrong when wiping: %s" % str(data))
                raise ResponseFailException("Failed getting WIPE_OUTPUT: %s" % str(data))
            if state == protocol.IDLE:
                self.__progress = 1.0
                logger.info("Finished: Computer ID %d" % self.id)
                break
            progress = data
            callback_progress(self, progress) if callback_progress else ()
            time.sleep(2)
        
        logger.info("Fetching dump for computer ID %d" % self.id)
        self.hw_info["Hard drives"][dev_name]["Dump after"] = self.__wipe_dump(dev_name)
    
    def __wipe_dump(self, dev_name):
        
        size_mb = self.hw_info["Hard drives"][dev_name].get("Size", 0)
        
        if size_mb:
            offset = random.randint(0, size_mb*1024*1024 / HDD_DUMP_BLOCKSIZE - 1)
        else:
            offset = 1

        command = HDD_DUMP_COMMAND % {'dev': dev_name,
                                      'blocksize': HDD_DUMP_BLOCKSIZE,
                                      'blocks': HDD_DUMP_BLOCKS,
                                      'offset': offset}
        
        (state, data) = self.__send_to_slave((protocol.SHELL_EXEC, command))
        
        if state == protocol.FAIL:
            logger.error("Something went wrong sending a SHELL_EXEC: %s" % str(data))
            raise ResponseFailException("Could not send request for hard drive dump")
        
        exec_id = data
        
        for __ in range(20):
            state, ___ = self.slave_state()
            logger.info("Trying to poll for SHELL_RESULTS, slave state is %s" % protocol.translate_state(state))
            if state == protocol.IDLE:
                (state, data) = self.__send_to_slave((protocol.SHELL_RESULTS, exec_id))
                if state == protocol.FAIL:
                    logger.error("Something went wrong getting SHELL_RESULTS: %s" % str(data))
                    raise ResponseFailException("Failed getting results from command ID %d" % exec_id)
                (stdout, ___) = data
                return stdout
            time.sleep(0.2)
            
        logger.error("Could not retrieve HDD dump. Timed out!")
        raise ResponseFailException("Could not retrieve HDD dump. Timed out! Maybe the hard drive has bad sectors?")

    def wipe_update(self, progress):
        """Callback from WipeProcess"""
        self.__activity = "Wiping drive %d of %d" % (self.current_drive+1, len(self.drives))
        self.__progress = progress
        self.wipe_duration = datetime.now() - self.wipe_started_on

    def wipe_finished(self, before_dump="", after_dump=""):
        """Callback from WipeProcess"""
        self.__progress = 0.0
        wiped_drive = self.drives[self.current_drive]
        self.hw_info['FixedHardDrive'][wiped_drive]['wiped'] = True
        self.hw_info['FixedHardDrive'][wiped_drive]['wipe_method'] = "wipe standard"
        self.hw_info['FixedHardDrive'][wiped_drive]['passes'] = 1
        self.hw_info['FixedHardDrive'][wiped_drive]['wipe_before'] = before_dump
        self.hw_info['FixedHardDrive'][wiped_drive]['wipe_after'] = after_dump
        if self.current_drive+1 < len(self.drives):
            self.current_drive = self.current_drive + 1
            self.wipe_current()
        else:
            self.wiped = True
            self.__is_active = False
            self.__progress = 1.0
            self.wipe_finished_on = datetime.now()
            self.__activity = "All drives wiped"
            for callback in self.wipe_finished_callbacks:
                callback(self)

    def wipe_failed(self, reason="Wipe failed"):
        self.wiped = False
        self.__is_active = False
        self.__activity = reason
        self.wipe_duration = None
        self.wipe_finished = None
        for callback in self.wipe_failed_callbacks:
            callback(self)

    def shutdown(self):
        """Asks the slave to perform a shutdown"""
        self.__activity = "Shutdown requested"
        (state, data) = self.__send_to_slave((protocol.SHELL_EXEC, "halt")) #@UnusedVariable
        
    def is_connected(self):
        return self.__is_connected

    def is_active(self):
        return self.__is_active

    def activity(self):
        return self.__activity
    
    def state(self):
        return self.__state
    
    def progress(self):
        if self.__progress < 0:
            return 0.0
        if self.__progress > 1:
            return 1.0
        return self.__progress

    
    
    def analyze_cpu_data(self ,stdout, stderr, hw_info):

        # /proc/cpuinfo
        re_processor_name = re.compile(r"^model name\s+\:\s*(.+)\s*", re.MULTILINE)
        re_processor_mhz = re.compile(r"^cpu MHz\s+\:\s*(\d+)", re.MULTILINE)
        re_processor_cores = re.compile(r"^cores\s+\:\s*(\d+)", re.MULTILINE)
    
        m = re_processor_name.search(stdout)
        cpu_name = m.group(1) if m else None
        
        m = re_processor_mhz.search(stdout)
        cpu_mhz = m.group(1) if m else None
        
        m = re_processor_cores.search(stdout)
        cpu_cores = m.group(1) if m else None
        
        hw_info["CPU"] = {'name': cpu_name,
                          'mhz': cpu_mhz,
                          'cores': cpu_cores,}
        
        return hw_info

    def analyze_lspci_data(self ,stdout, stderr, hw_info):

        re_graphics_card = re.compile(r"VGA compatible controller\:\s*(.+)\s*$", re.M | re.I)
        re_network_card = re.compile(r"Network controller\:\s*(.+)\s*$", re.M | re.I)
        re_ethernet_card = re.compile(r"Ethernet controller\:\s*(.+)\s*$", re.M | re.I)
        re_usb_controller = re.compile(r"USB controller\:\s*(.+)\s*$", re.M | re.I)
    
        m = re_graphics_card.search(stdout)
        graphics = m.group(1) if m else None
        
        m = re_network_card.search(stdout)
        network = m.group(1) if m else None
        
        m = re_ethernet_card.search(stdout)
        ethernet = m.group(1) if m else None
        
        m = re_usb_controller.search(stdout)
        usb_controller = m.group(1) if m else None

        hw_info["VGA controller"]  = graphics
        hw_info["Wireless controller"]  = network
        hw_info["Ethernet controller"]  = ethernet
        hw_info["USB"] = bool(usb_controller)
        
        return hw_info
    
    def analyze_dmesg_data(self ,stdout, stderr, hw_info):
        """
        Find hard drives...
        """
        re_hard_drive = re.compile(r"\[(sd.)\].+(hardware sectors|logical blocks)", re.I)
        harddrives = {}
        for line in stdout.split("\n"):
            m = re_hard_drive.search(line)
            if m:
                dev_name = m.group(1)
                harddrives[dev_name] = {}
                logger.info("Found disk device /dev/%s" % dev_name)

        hw_info["Hard drives"] = harddrives
        return hw_info
    
    def analyze_dmidecode_memory(self, stdout, stderr, hw_info):
        re_memory = re.compile(r"^\s+Size:\s+(\d+)\sMB",)
        memory = 0
        for line in stdout.split("\n"):
            m = re_memory.search(line)
            memory += int(m.group(1)) if m else 0
        if memory > 0:
            hw_info["Memory"] = memory
        return hw_info
    
    def analyze_dmidecode_system(self, stdout, stderr, hw_info):
        re_family = re.compile(r"^\s+Family:\s+(.+)\s*$", re.M)
        m = re_family.search(stdout)
        hw_info["Type"] = m.group(1) if m else None
        return hw_info

    def analyze_dmidecode_system_sn(self, stdout, stderr, hw_info):
        re_memory = re.compile(r"^\s*([^\#].+)\s*$", re.MULTILINE)
        m = re_memory.search(stdout)
        hw_info["System S/N"] = m.group(1) if m else None
        return hw_info
    
    def analyze_dmidecode_bios_sn(self, stdout, stderr, hw_info):
        re_memory = re.compile(r"^\s*([^\#].+)\s*$", re.M)
        m = re_memory.search(stdout)
        hw_info["BIOS S/N"] = m.group(1) if m else None
        return hw_info

    def analyze_dmidecode_uuid(self, stdout, stderr, hw_info):
        re_memory = re.compile(r"^\s*([^\#].+)\s*$", re.M)
        m = re_memory.search(stdout)
        hw_info["System UUID"] = m.group(1) if m else None
        return hw_info
    
    def analyze_dmidecode_chassis_type(self, stdout, stderr, hw_info):
        re_memory = re.compile(r"^\s*([^\#].+)\s*$", re.M)
        m = re_memory.search(stdout)
        hw_info["Chassis"] = m.group(1) if m else None
        hw_info["Laptop"] = True if hw_info["Chassis"] in ["Notebook", "Portable"] else False
        return hw_info
    
    def analyze_dmidecode_manufacturer(self, stdout, stderr, hw_info):
        re_memory = re.compile(r"^\s*([^\#].+)\s*$", re.M)
        m = re_memory.search(stdout)
        hw_info["System manufacturer"] = m.group(1) if m else None
        return hw_info

    def analyze_meminfo_data(self, stdout, stderr, hw_info):
        """
        Find RAM capacity
        """
        if hw_info.get("Memory", None):
            return hw_info
        re_memory = re.compile(r"^MemTotal:\s+(\d+)", re.I | re.M)
        m = re_memory.search(stdout)
        memory = int(m.group(1)) / 1024 if m else 0
        hw_info["Memory"] = memory
        return hw_info

    def analyze_cdrom_info(self, stdout, stderr, hw_info):
        filter_key_value = re.compile(r"^(\w[\w\s]+):\s+(\w[\w\s]+)$")
        drive_info = {}
        drive_name = ""
        for line in stdout.split("\n"):
            key_value = filter_key_value.search(line)
            if not key_value: continue
            key, value = key_value.group(1), key_value.group(2)
            if key == 'drive name':
                drive_name = value
                drive_info[drive_name] = {}
                drive_info[drive_name]['CD-ROM'] = True
            elif key == 'drive speed':
                drive_info[drive_name]['speed'] = value
            elif key == 'Can write CD-R' and value == "1":
                drive_info[drive_name]['CD-R'] = True
            elif key == 'Can write CD-RW' and value == "1":
                drive_info[drive_name]['CD-RW'] = True
            elif key == 'Can read DVD' and value == "1":
                drive_info[drive_name]['DVD'] = True
            elif key == 'Can write DVD-R' and value == "1":
                drive_info[drive_name]['DVD-R'] = True
        if drive_info:
            hw_info['Optical drive'] = drive_info
        return hw_info

    def analyze_hdparm(self, stdout, stderr, hw_info):
        filter_hdparm = re.compile(r"SerialNo=([\w\-]+)")
        if stdout:
            dev_name = stdout.split("\n")[0]
            if not dev_name:
                return hw_info
            m = filter_hdparm.search(stdout)
            if m:
                hw_info["Hard drives"][dev_name]["Serial"] = m.group(1)
        return hw_info

    def analyze_sdparm(self, stdout, stderr, hw_info):
        filter_sdparm = re.compile(r"VPD\spage\:\s*\n\s*([\w\-\_]+)", re.M)
        if stdout:
            dev_name = stdout.split("\n")[0]
            if not dev_name:
                return hw_info
            m = filter_sdparm.search(stdout)
            if m:
                hw_info["Hard drives"][dev_name]["Serial"] = m.group(1)
        return hw_info

    def analyze_blockdev(self, stdout, stderr, hw_info):
        filter_blockdev = re.compile(r"^(\d+)$", re.MULTILINE)
        if stdout:
            dev_name = stdout.split("\n")[0]
            if not dev_name:
                return hw_info
            m = filter_blockdev.search(stdout)
            if m:
                size_mb = int(m.group(1)) / 1024**2
                hw_info["Hard drives"][dev_name]["Size"] = size_mb
        return hw_info

    def whatever(self ,stdout, stderr, hw_info):
        # TODO: Why is this function here?
        return hw_info
