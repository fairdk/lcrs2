#
# LCRS Copyright (C) 2009-2012
# - Benjamin Bach
# - Rene Jensen
# - Michael Wojciechowski
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

from lcrs.slave import protocol
from lcrs.slave import settings as slave_settings

import re
import random

# create logger
logger = logging.getLogger('lcrs')

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


# Computer states in master's end of the line...    
# Logic inference on state is treated here in order to deduct
# meaningful treatment elsewhere and produce correct output in the UI. 
class State:
    (NOT_CONNECTED, 
     CONNECTED, 
     INITIALIZED,
     SCANNING, 
     SCAN_FAILED,
     SCANNED,
     WIPING, 
     WIPE_FAILED,
     WIPED, 
     SHUTDOWN_REQUESTED,
     SHUTDOWN_DETECTED) = range(11)
    
    def __init__(self):
        self.lock = threading.RLock()
        self.__state = State.NOT_CONNECTED
        self.__connected = False
        # Current activity info
        self.__info = "Not connected"
        # Remember previous activities so we can switch back to last
        # update if computer reconnects
        self.__wipe_info = ""
        self.__scan_info = ""
        self.__progress = 0.0
    
    def update(self, state, info=None, progress=None):
        self.lock.acquire()
        if state == State.CONNECTED:
            self.__connected = True
            if self.__state < State.INITIALIZED or self.__state > State.SHUTDOWN_REQUESTED:
                self.__state = State.INITIALIZED
                self.__info = "Ready"
            elif self.__state < State.WIPING:
                self.__info = self.__scan_info
            elif self.__state < State.SHUTDOWN_REQUESTED:
                self.__info = self.__wipe_info
            else:
                self.__info = "Connected"
            self.lock.release()
            return
        if state == State.NOT_CONNECTED:
            self.__info = "Not connected"
            self.__connected = False
            self.lock.release()
            return
        
        if not progress is None:
            self.update_progress(progress)
        
        self.__state = state
        if not info is None:
            self.__info = info
            if self.state in [State.SCANNING, State.SCANNED, State.SCAN_FAILED]:
                self.__scan_info = info
            if self.state in [State.WIPING, State.WIPED, State.WIPE_FAILED]:
                self.__wipe_info = info
    
        self.lock.release()
        return

    def update_progress(self, progress):
        """Progress is expressed as a floating percentage"""
        self.lock.acquire()
        if not progress is None and self.state in [State.SCANNING, State.WIPING]:
            self.__progress = progress
        self.lock.release()
    
    @property
    def is_connected(self):
        self.lock.acquire()
        _is_connected = self.__connected
        self.lock.release()
        return _is_connected
    
    @property
    def is_busy(self):
        self.lock.acquire()
        _is_busy = self.__state in [State.SCANNING, State.WIPING]
        self.lock.release()
        return _is_busy
    
    @property
    def info(self):
        self.lock.acquire()
        _info = self.__info
        self.lock.release()
        return _info
    
    @property
    def state(self):
        self.lock.acquire()
        _state = self.__state
        self.lock.release()
        return _state
    
    @property
    def progress(self):
        self.lock.acquire()
        _progress = self.__progress
        self.lock.release()
        return _progress

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
    "cat /proc/acpi/battery/BAT0/info": "analyze_battery_info",
}

#dd if=/dev/dvd of=/dev/null count=1 2>/dev/null; if [ $? -eq 0 ]; then echo "disk found"; else echo "no disk"; fi

# Shell commands for second iteration. Each command has a tuple (analyze function, command parser)
# for analyzing output and parsing the command (for possible inclusion of data from the first iteration)
SCAN_ITERATION_2 = {
    "echo %(sdX)s && hdparm -i /dev/%(sdX)s": ("analyze_hdparm", lambda com, hw: [com % {'sdX': key} for key in hw.get("Hard drives", {}).keys()]),
    "echo %(sdX)s && sdparm -q -p sn /dev/%(sdX)s": ("analyze_sdparm", lambda com, hw: [com % {'sdX': key} for key in hw.get("Hard drives", {}).keys()]),
    "echo %(sdX)s && blockdev --getsize64 /dev/%(sdX)s": ("analyze_blockdev", lambda com, hw: [com % {'sdX': key} for key in hw.get("Hard drives", {}).keys()]),
    "echo %(sdX)s && readlink -f /sys/block/%(sdX)s/": ("analyze_sysblock", lambda com, hw: [com % {'sdX': key} for key in hw.get("Hard drives", {}).keys()]),
}

HDD_DUMP_COMMAND = "dd if=/dev/%(dev)s ibs=%(blocksize)d count=%(blocks)d skip=%(offset)d | hexdump -v"
HDD_DUMP_BLOCKSIZE = 512
HDD_DUMP_BLOCKS = 1
        
WIPE_METHODS = {
    "Wipe (zeros)": "wipe -z -v -l0 -p1 /dev/%(dev)s",
#    "ATA Secure Erase": "wipe -z -v -l0 -p1 /dev/%(dev)s",
}

# TODO: Output badblocks in a file to check later perhaps?
BADBLOCKS = "badblocks -e 1 -s -o /tmp/badblocks /dev/%(dev)s"

class Computer():
    """
    """
    
    def __init__(self, computer_id, ipAddress, macAddress, config_master):

        self.id = computer_id or 0
        self.ipAddress = ipAddress
        self.macAddress = macAddress
        
        self.state = State()

        # Activity information
        self.state.update(State.NOT_CONNECTED, "Initializing connection...")
        
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
        
        self.shutdown_after_wiping = False
        
        self.debug_mode_request = config_master.DEBUG

        self.is_registered = False # Says whether the computer has been registered in some database

        self.__slave__uuid = None
        self.__slave_uuid_conflict = False

    def scan(self, callback_progress=None, callback_finished=None, 
             callback_failed=None):
        """Spawn scan process and receive call backs"""
        self.scanned = False

        logger.debug("Starting hardware scan thread...")
        
        if self.state.is_busy:
            return
        self.state.update(State.SCANNING, "Scanning...")
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
            progress = progress * scan1_share
            self.state.update(State.SCANNING, info=protocol.translate_state(state),
                              progress=progress)
            callback_progress(self, progress) if callback_progress else ()
        
        def callback_progress2(progress, state):
            progress = progress * scan2_share
            self.state.update(State.SCANNING, info=protocol.translate_state(state),
                              progress=progress)
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
            self.state.update(State.SCAN_FAILED, "Scan failed: %s" % (msg))
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

        if not state == protocol.FAIL:
            self.state.update(State.SCANNED, info="Scanning finished", progress=1.0)
            self.scanned = True
        else:
            self.state.update(State.SCAN_FAILED, info="Scanning failed", progress=1.0)
        callback_finished(self) if callback_finished else ()
    
    def __request_and_monitor(self, scan_commands, callback_progress=None, 
                              callback_finished=None, callback_failed=None):
        
        request = (protocol.SCAN, scan_commands)
        status, data = self.__send_to_slave(request)
        
        # If something went wrong...
        if status == protocol.FAIL:
            callback_failed(self) if callback_failed else ()
            logger.warning("SCAN failed. Reason: %s" % str(data))
            self.state.update(State.SCAN_FAILED, "Scan failed: %s" % str(data))
            return False
        
        # Start monitoring scan 1
        self.state.update(State.SCANNING, "Scanning...")
        while not self.scanned:
            (state, data) = self.slave_state()
            progress = data.get('progress', None) if type(data) == dict else None
            callback_progress(progress, state) if callback_progress else ()
            logger.debug("Assuming progress: %s" % progress)
            if state == protocol.FAIL:
                self.state.update(State.SCAN_FAILED, "Scan failed during execution")
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
        for __ in range(1):
            # Retry 1 times
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout (2.0)
                s.connect( (self.ipAddress, slave_settings.LISTEN_PORT) )
                s.settimeout (1.0)
                s.send(request)
                self.state.update(State.CONNECTED)
                break
            except socket.timeout:
                time.sleep(1)
            except socket.error:
                s.close()
                self.state.update(State.NOT_CONNECTED, "Could not connect")
                logger.error("Could not connect")
                raise ConnectionException("Could not connect")
            except:
                s.close()
                e = sys.exc_info()[1]
                self.state.update(State.NOT_CONNECTED, "Error connecting.")
                logger.error(e)
                raise ConnectionException("Could not connect")
        
        if not self.state.is_connected:
            s.close()
            raise ConnectionException("Timeout connecting")

        retries = 0
        max_retries = 2
        while True:
            try:
                s.settimeout (5.0)
                reply = reply + s.recv (slave_settings.MAX_PACKET_SIZE)
                self.state.update(State.CONNECTED)
                reply = json.loads(reply)
                break
            except json.JSONDecodeError:
                continue
            except ValueError:
                continue
            except socket.timeout:
                retries += 1
                if retries > max_retries:
                    s.close()
                    raise ConnectionException("Timeout while receiving reply")
                self.state.update(State.NOT_CONNECTED, "Connection timeout")
                continue
            except socket.error:
                s.close()
                self.state.update(State.NOT_CONNECTED, "Connection failure")
                logger.error("Could not connect after sending request")
                raise ConnectionException("Could not connect")
            
        s.close()
        return reply

    def slave_state(self, **kwargs):
        """Get status message and progress from slave
        """
        if self.debug_mode_request:
            try:
                request = (protocol.DEBUG_MODE, [])
                state, response = self.__send_to_slave(request)
                self.debug_mode_request = False
                logger.debug("Requested debug mode for computer ID %s, response: %s" % (str(self.id), response))
            except ConnectionException:
                pass
        try:
            request = (protocol.STATUS, kwargs)
            state, data = self.__send_to_slave(request)
            return state, data
        except ConnectionException:
            return (protocol.DISCONNECTED, "Could not connect")

    def update_state(self):
        state, data = self.slave_state()
        if not state == protocol.DISCONNECTED:
            self.state.update_progress(data.get('progress', None))
            slave__uuid = data.get('uuid', None)
            if not self.__slave__uuid is None and self.__slave__uuid != slave__uuid:
                self.__slave_uuid_conflict = True
                logger.critical("A conflict has been discovered on ip: %s" % self.ipAddress)
            self.__slave__uuid = slave__uuid
    
    def wipe(self, method, badblocks=False,
             callback_finished=None, callback_failed=None,
             callback_progress=None):
        """Spawn wipe process and receive call backs"""
        if not self.scanned:
            return
        
        logger.info("Now wiping hard drives on IP: %s" % str(self.ipAddress))
        
        self.wiped = False
        self.state.update(State.WIPING, "Starting wipe...")
        self.wipe_method = method
        self.drives = self.hw_info.get('Hard drives', {}).keys()        
        self.wiped = False
        self.wipe_started_on = datetime.now()

        if not self.drives:
            self.state.update(State.WIPE_FAILED, info="No hard drives detected", progress=1.0)
            callback_failed(self) if callback_failed else ()
            return
        
        callback_progress(self, self.progress()) if callback_progress else ()

        t = threading.Thread(target=self.__wipe_thread, 
                             args=(method, badblocks,
                                   callback_finished, callback_failed,
                                   callback_progress))
        t.setDaemon(True)
        t.start()
    
    def __wipe_thread(self, method, badblocks=False,
                        callback_finished=None, callback_failed=None,
                        callback_progress=None):
        wipe_cnt = 0
        for dev_name in self.drives:
            wipe_cnt = wipe_cnt + 1
            callback_progress(self, self.progress()) if callback_progress else ()

            try:
                # 1) Get a dump
                logger.debug("Fetching before dump for computer ID %s" % str(self.id))
                self.hw_info["Hard drives"][dev_name]["Dump before"] = self.__wipe_dump(dev_name)
                logger.debug("Received before dump from Computer ID %s" % str(self.id))
                
                if badblocks:
                    self.state.update(State.WIPING, "Checking for badblocks on drive %d of %d" % (wipe_cnt, len(self.drives)))
                    try:
                        self.__bad_blocks(dev_name, callback_progress)
                    except ResponseFailException, msg:
                        self.state.update(State.WIPE_FAILED, "Badblocks failed on drive %d: %s" % (wipe_cnt, str(msg)), progress=0.0)
                        callback_failed(self) if callback_failed else ()
                        return
                self.state.update(State.WIPING, "Wiping drive %d of %d" % (wipe_cnt, len(self.drives)))
                self.__wipe_drive(dev_name, method, callback_progress)
                logger.debug("Fetching after dump for computer ID %s" % str(self.id))
                self.hw_info["Hard drives"][dev_name]["Dump after"] = self.__wipe_dump(dev_name)
                logger.debug("Received after dump from Computer ID %s" % str(self.id))

            except ResponseFailException, msg:
                self.state.update(State.WIPE_FAILED, "Wipe failed on drive %d: %s" % (wipe_cnt, str(msg)), progress=0.0)
                callback_failed(self) if callback_failed else ()
                return

            dump_check = self.__verify_after_dump(self.hw_info["Hard drives"][dev_name].get("Dump after", " 1"))
            if not dump_check:
                self.state.update(State.WIPE_FAILED, "Dump after did not pass (drive %d of %d)" % (wipe_cnt, len(self.drives)))
                callback_failed(self) if callback_failed else ()
                return                
        
        self.wiped = True
        self.state.update(State.WIPED, info="All drives wiped!", progress=1.0)
        self.wipe_finished_on = datetime.now()
        callback_finished(self) if callback_finished else ()
        if self.drives and self.shutdown_after_wiping:
            self.shutdown()
    
    def __verify_after_dump(self, dump_data):
        """
        Example of valid after data:
        0000000 0000 0000 0000
        0000001 0000 0000 0000
        0000002 0000 0000 0000
        Check is just to ensure that everything is zeros except the first
        index number.
        """
        for line in dump_data.split("\n"):
            for group in (line.split(" "))[1:]:
                for char in group.strip():
                    if not char == "0":
                        return False
        return True
        
    
    def __bad_blocks(self, dev_name, callback_progress):
        """Check a drive for bad blocks"""
        
        badblocks_command = BADBLOCKS % {'dev': dev_name,}
        request = (protocol.BADBLOCKS, badblocks_command)
        self.__send_to_slave(request)
        
        self.state.update_progress(0.0)
        callback_progress(self, self.progress()) if callback_progress else ()

        logger.debug("Doing badblocks on Computer ID %s" % str(self.id))
        
        while True:
            
            state, data = self.slave_state()
            
            if type(data) == dict and data.get('badblocks_done', False):
                self.state.update_progress(1.0)
                self.hw_info["Hard drives"][dev_name]["Badblocks"] = False
                break

            elif state == protocol.FAIL:
                logger.error("Badblocks detected! Output was: %s" % str(data))
                self.hw_info["Hard drives"][dev_name]["Badblocks"] = True
                raise ResponseFailException("Badblocks detected (/dev/%s)!" % dev_name)
            
            elif state == protocol.BUSY:
                progress = data.get('progress', None) if type(data) == dict else None
                self.state.update_progress(progress)
                logger.debug("Received data assuming to be progress while doing badblocks and BUSY: %s" % str(data))
            
            elif state == protocol.DISCONNECTED:
                self.state.update(State.NOT_CONNECTED, "Not connected")
            
            elif state == protocol.IDLE:
                logger.error("Badblocks was interrupted. Error: %s" % str(data))
                err_msg = "Badblocks was interrupted. Error: %s" % str(data)
                self.state.update(State.WIPE_FAILED, err_msg)
                raise ResponseFailException(err_msg)
            
            logger.debug("Badblocks doing callback_progress")
            callback_progress(self, self.progress()) if callback_progress else ()
            logger.debug("Badblocks did callback_progress")
            time.sleep(2)
    
    def __wipe_drive(self, dev_name, method, callback_progress=None):
        
        #TODO: Standardise these values all over the project!
        self.hw_info["Hard drives"][dev_name]["Wipe method"] = "wipe standard"
        self.hw_info["Hard drives"][dev_name]["Passes"] = 1

        self.state.update_progress(0.0)
        callback_progress(self, self.progress()) if callback_progress else ()

        wipe_command = WIPE_METHODS[method] % {'dev': dev_name,}
        request = (protocol.WIPE, wipe_command)
        self.__send_to_slave(request)
        
        while True:
            
            state, data = self.slave_state()

            if type(data) == dict and data.get('wipe_done', False):
                self.state.update_progress(1.0)
                logger.info("Finished: Computer ID %s" % str(self.id))
                break
            
            elif state == protocol.FAIL:
                logger.error("Something went wrong when wiping: %s" % str(data))
                err_msg = "Failed getting WIPE_OUTPUT: %s" % str(data)
                self.state.update(State.WIPE_FAILED, err_msg)
                raise ResponseFailException(err_msg)
            
            elif state == protocol.IDLE:
                logger.error("Wipe was interrupted. Error: %s" % str(data))
                err_msg = "Wipe was interrupted. Error: %s" % str(data)
                self.state.update(State.WIPE_FAILED, err_msg)
                raise ResponseFailException(err_msg)

            elif state == protocol.BUSY:
                progress = data.get('progress', None) if type(data) == dict else None
                self.state.update_progress(progress)
                logger.debug("Received data assuming to be progress while doing wipe and BUSY: %s" % str(data))
            
            elif state == protocol.DISCONNECTED:
                self.state.update(State.NOT_CONNECTED, "Not connected")
            
            callback_progress(self, self.progress()) if callback_progress else ()
            time.sleep(2)
        
    
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

    def shutdown(self):
        """Asks the slave to perform a shutdown"""
        try:
            self.state.update(State.SHUTDOWN_REQUESTED, "Shutdown requested")
            (state, data) = self.__send_to_slave((protocol.SHELL_EXEC, "poweroff")) #@UnusedVariable
        except ConnectionException, __:
            pass
        self.state.update(State.SHUTDOWN_DETECTED, "Shutdown detected")
        
    def reset(self):
        """Asks the slave to reset everything"""
        try:
            (state, data) = self.__send_to_slave((protocol.RESET, None)) #@UnusedVariable
            self.state.update(State.INITIALIZED, "Reset")
            self.wiped = False
            self.scanned = False
        except ConnectionException, __:
            self.state.update(self.state, "Reset failed")

    def is_connected(self):
        """No wait return state of connection"""
        return self.state.is_connected

    def is_active(self):
        """No wait return busy state"""
        return self.state.is_busy
    
    def is_scanning(self):
        return self.state.state == State.SCANNING
    
    def activity(self):
        return self.state.info
    
    def progress(self):
        return self.state.progress
    
    def slave_uuid_conflict(self):
        return self.__slave_uuid_conflict
    
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
        
        ata_controllers = {}
        re_ata_controllers = re.compile(r"^(ata\d)\:\s*(.+)")
        for line in stdout.split("\n"):
            m = re_ata_controllers.search(line)
            if m:
                ata_name = m.group(1)
                info = m.group(2)
                ata_controllers[ata_name] = {'info': info,
                                             'pata': "PATA" in info,
                                             'sata': "SATA" in info}
                logger.info("Found ATA controller %s" % ata_name)
        
        hw_info["Hard drive controllers"] = ata_controllers
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
    
    def analyze_battery_info(self, stdout, stderr, hw_info):
        filter_key_value = re.compile(r"^(\w[\w\s]+):\s+(\w[\w\s]+)$")
        design_capacity = ""
        last_full_capacity = ""
        for line in stdout.split("\n"):
            key_value = filter_key_value.search(line)
            if not key_value: continue
            key, value = key_value.group(1), key_value.group(2)
            if key == 'design capacity':
                design_capacity = value
            elif key == 'last full capacity':
                last_full_capacity = value
        if design_capacity and last_full_capacity:
            hw_info['Battery'] = ("Design capacity: %s, Last full capacity: %s" % 
                                  (design_capacity, last_full_capacity) )
            filter_number = re.compile(r"^(\d+).*")
            match_number_design = filter_number.search(design_capacity)
            match_number_full = filter_number.search(last_full_capacity)
            if match_number_design and match_number_full:
                design_cap = match_number_design.group(1)
                last_full_cap = match_number_full.group(1)
                hw_info['Battery life'] = float(last_full_cap) / float(design_cap)
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
    
    def analyze_sysblock(self, stdout, stderr, hw_info):
        if stdout:
            dev_name = stdout.split("\n")[0]
            if not dev_name:
                return hw_info
            for ata_name, info_dict in hw_info['Hard drive controllers'].items():
                if '/'+ata_name in stdout:
                    if info_dict['pata']:
                        hw_info["Hard drives"][dev_name]["Interface"] = 'PATA'
                    if info_dict['sata']:
                        hw_info["Hard drives"][dev_name]["Interface"] = 'SATA'
        return hw_info
    
