#!/usr/bin/python

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
import socket
import time
import json
import logging
import re
import os
import sys

# create logger
logger = logging.getLogger('lcrs_slave')
ch = logging.StreamHandler()
formatter = logging.Formatter('%(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
logger.setLevel(logging.INFO)

import settings
import protocol
from asyncproc import Process

class RequestException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)

class Slave():
    
    def __init__(self):
        self.socket = None
        self.state = protocol.IDLE
        self.__progress = 0.0
        self.shell_exec_cnt = 0
        self.shell_exec_results = {}
        
        self.thread = threading.Thread (target = self.listen,)
        self.thread.setDaemon(True)
        self.thread.start()
        
        self.__wipe_done = False
        self.__badblocks_done = False
        
        self.signal_mainthread_killall = False
        self.processes = []
        
        self.__fail_message = ""
        self.__wipe_output = None
        
        self.__active = True
    
    def stop(self):
        self.__active = False
    
    def listen(self, listen_port=settings.LISTEN_PORT):
        """
        Read messages from clients. If the client closes its
        connection, start from scratch.
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.socket.settimeout(2)
        self.socket.bind ( ('', listen_port) )
        self.socket.listen(10)
        
        logger.info("Now listening on TCP port %d" % (listen_port))
        
        while self.__active:
            try:
                client_socket, address = self.socket.accept()
                logger.debug("Received connection from %s." % str(address))
                t = threading.Thread(target=self.__client_thread, args=(client_socket,))
                t.setDaemon(True)
                t.start()
            except socket.timeout:
                continue
                    
        self.socket.close()
    
    def __client_thread(self, client_socket):
        while self.__active:
            try:
                client_socket.settimeout(settings.CLIENT_TIMEOUT)
                raw_data = client_socket.recv(settings.MAX_PACKET_SIZE)
                break
            except socket.timeout:
                logger.warning("Client timed out.")
                continue
            except socket.error, (__, errmsg):
                logger.warning("Error in connection: %s." % str(errmsg))
                break
        
        if not self.__active:
            client_socket.close()
            return

        if raw_data:
            try:
                data = self.process_request(raw_data)
                self.send_reply(client_socket, data)
            except RequestException, error_msg:
                logger.warning("Request exception: %s" % error_msg)
                self.state = protocol.FAIL
                self.send_reply(client_socket, str(error_msg))
            except socket.timeout:
                logger.error("Connection timeout sending reply.")
            except socket.error, (__, errmsg):
                logger.error("Error in socet while sending reply: %s." % str(errmsg))
            except:
                # A non-socket exception... try to send back the exception
                self.state = protocol.FAIL
                self.send_reply(client_socket, "Error in slave: %s" % sys.exc_info()[0])
                raise
            client_socket.close()
        
    
    def process_request(self, raw_data):
        """
        Process some JSON data received from the socket
        Should be blocking!
        """
        try:
            command, data = json.loads(raw_data)
        except ValueError:
            raise RequestException("Illegal JSON data - must be of type (command, data), got: %s" % str(raw_data))
        
        if command == protocol.SCAN:
            return self.scan(data)
        if command == protocol.WIPE:
            return self.wipe(data)
        if command == protocol.STATUS:
            return self.status(data)
        if command == protocol.HARDWARE:
            return self.hardware(data)
        if command == protocol.SHELL_EXEC:
            return self.shell_exec(data)
        if command == protocol.SHELL_RESULTS:
            return self.shell_results(data)
        if command == protocol.BADBLOCKS:
            return self.badblocks(data)
        if command == protocol.RESET:
            return self.reset(data)
        if command == protocol.DEBUG_MODE:
            return self.debug_mode(data)
        
        raise RequestException("Received unknown command ID: %s" % str(command))
        
    def send_reply(self, client_socket, data=None):
        try:
            client_socket.sendall(json.dumps([self.state, data]))
        except socket.timeout:
            logger.warning("Could not send response. Socket timeout.")
        except socket.error, (__, e_str):
            logger.warning("Could not send response. Socket died. %s" % str(e_str))
    
    def scan(self, data):
        """ Takes a list of strings to execute in a separate thread.
            Executes all the commands in the same order as they are listed.
            The thread function stores all output in a dictionary with the original
            command as key.
            Non-blocking!
            Use HARDWARE command to retrieve the list of data.
        """
        logger.info("Received SCAN command.")
        if self.state == protocol.BUSY:
            raise RequestException("Cannot execute SCAN - current state is BUSY.")
        
        self.state = protocol.BUSY
        
        # Check list...
        try:
            for c in data:
                if not type(c) == str and not type(c) == unicode:
                    raise TypeError
        except TypeError:
            raise RequestException("SCAN takes a list of strings as input (shell commands to execute). Got: %s" % str(data))
        
        self.scan_results = {}
        
        t = threading.Thread(target=self.__scan_thread, args=(data,))
        t.setDaemon(True)
        t.start()
        
        return None
        
    def wipe(self, data):
        logger.info("Received WIPE command.")
        if self.state == protocol.BUSY:
            raise RequestException("Cannot execute WIPE - current state is BUSY.")
        self.state = protocol.BUSY
        self.__wipe_done = False
        self.__progress = 0.0
        
        t = threading.Thread(target=self.__wipe_thread, args=(data,))
        t.setDaemon(True)
        t.start()

        return None
    
    def __wipe_thread(self, command):
        process = Process(command, shell=True)
        self.processes.append(process)
        re_pct = re.compile(r"(\d+)%", re.M)
        while True:
            # check to see if process has ended
            poll = process.wait(os.WNOHANG)
            if poll != None:
                break
            # print any new output
            stdout = process.read()
            m = re_pct.search(stdout)
            if m:
                pct = int(m.group(1))
                self.__progress = pct / 100.0
                logger.info("Wipe progress: %d%%" % (self.__progress*100))

        stderr = process.readerr()
        exit_status = process.wait()
        if exit_status > 0:
            self.state = protocol.FAIL
            self.__fail_message = ("Failed while wiping. Return code: %d, Stderr was: %s" % 
                                   (exit_status, stderr))
            logger.error(self.__fail_message)
            return
        self.__wipe_done = True
        self.__progress = 1.0
        self.state = protocol.IDLE
    
    def debug_mode(self, data):
        logger.setLevel(logging.DEBUG)
        logger.debug("Switched on debug mode")
        return None
    
    def badblocks(self, data):
        logger.info("Received BADBLOCKS command.")
        if self.state == protocol.BUSY:
            raise RequestException("Cannot execute BADBLOCKS - current state is BUSY.")
        self.state = protocol.BUSY
        self.__badblocks_done = False
        self.__progress = 0.0
        
        t = threading.Thread(target=self.__badblocks_thread, args=(data,))
        t.setDaemon(True)
        t.start()

        return None
    
    def __badblocks_thread(self, command):
        process = Process(command, shell=True)
        self.processes.append(process)
        re_pct = re.compile(r"(\d\d)\.\d+%", re.M)
        while True:
            # check to see if process has ended
            poll = process.wait(os.WNOHANG)
            if poll != None:
                break
            # print any new output
            stdout = process.read()
            m = re_pct.search(stdout)
            if m:
                pct = int(m.group(1))
                self.__progress = pct / 100.0
                logger.info("Badblocks progress: %d%%" % (self.__progress * 100))

        stderr = process.readerr()
        exit_status = process.wait()
        if exit_status > 0:
            self.state = protocol.FAIL
            self.__fail_message = ("Failed executing badblocks. Return code: %d, Stderr was: %s" % 
                                   (exit_status, stderr))
            logger.error(self.__fail_message)
            return
        self.__progress = 1.0
        self.__badblocks_done = True
        self.state = protocol.IDLE

    def shell_exec(self, data):
        logger.info("Received SHELL_EXEC command.")
        if self.state == protocol.BUSY:
            raise RequestException("Cannot execute SHELL_EXEC - current state is BUSY.")
        
        self.state = protocol.BUSY
        shell_exec_id = self.shell_exec_cnt
        self.shell_exec_cnt += 1
        
        t = threading.Thread(target=self.__shell_exec_thread, args=(data, shell_exec_id))
        t.setDaemon(True)
        t.start()
        
        return shell_exec_id


    def __shell_exec_thread(self, command, shell_exec_id):
        logger.info("Shell execution of: %s" % command)
        process = Process(command, shell=True)
        # Initiate process
        process.wait(os.WNOHANG)
        self.processes.append(process)
        # Blocking wait
        process.wait()
        self.shell_exec_results[shell_exec_id] = (process.read(), process.readerr())
        self.state = protocol.IDLE
    
    def shell_results(self, data):
        try:
            command_id = int(data)
        except ValueError:
            raise RequestException("SHELL_RESULTS takes one integer argument.")
        
        try:
            (stdin, stdout) = self.shell_exec_results[command_id]
            return (stdin, stdout)
        except KeyError:
            raise RequestException("No such result id. Maybe command hasn't finished.")
        
    def status(self, data):
        logger.debug("Received STATUS command.")
        return {'progress': self.__progress,
                'badblocks_done': self.__badblocks_done,
                'wipe_done': self.__wipe_done,
                'fail_message': self.__fail_message}
    
    def hardware(self, data):
        logger.info("Received HARDWARE command.")
        if self.hardware:
            return self.scan_results
        else:
            return None
    
    def __scan_thread(self, commands):
        # Execute a number of commands and return their output in the same order.
        command_cnt = float(len(commands))
        self.__progress = 0.0
        for cnt, command in enumerate(commands, start=1):
            logger.info("SCAN executing command: %s" % command)
            self.__progress = cnt / command_cnt
            logger.debug("Progress: %.2f" % self.__progress)
            try:
                process = Process(command, shell=True,)
                process.wait(os.WNOHANG)
                self.processes.append(process)
                process.wait()
                self.scan_results[command] = (process.read(), process.readerr())
            except OSError:
                self.scan_results[command] = ("", "Command does not exist")
        
        self.state = protocol.IDLE
    
    def killall(self):
    
        self.__wipe_done = False
        self.__fail_message = ""
        self.__badblocks_done = False
        # Signal the main thread to kill everything... can only be done from there!
        self.signal_mainthread_killall = True
            
    def reset(self, data):
        """Command asks the client to reset and terminate all running processes"""
        logger.info("Received RESET command.")
        self.state = protocol.RESET
        self.killall()
        return None
    
def kill_slave_processes(slave):
    for process in slave.processes:
        try:
            process.terminate()
        except OSError:
            # Nothing important, probably process is already done
            continue
        slave.processes.remove(process)

            
if __name__ == "__main__":
    
    print ("""

                                                                               
    _/          _/_/_/  _/_/_/      _/_/_/                    _/_/        _/   
   _/        _/        _/    _/  _/            _/      _/  _/    _/    _/_/    
  _/        _/        _/_/_/      _/_/        _/      _/      _/        _/     
 _/        _/        _/    _/        _/        _/  _/      _/          _/      
_/_/_/_/    _/_/_/  _/    _/  _/_/_/            _/      _/_/_/_/  _/  _/       

""")
    print ""
    print "----------------------------------------------------"
    print " Welcome to the LCRS slave server. Press Q to quit. "
    print "----------------------------------------------------"
    print ""
    
    slave = Slave()
    
    while True:
        
        # Monitor signal to terminate all processes
        # (this can only be done from main thread)
        if slave.signal_mainthread_killall: 
            kill_slave_processes(slave)
            slave.state = protocol.IDLE
            slave.signal_mainthread_killall = False
            
        s = raw_input()
        if s == 'q':
            print "Cleaning up..."
            kill_slave_processes(slave)
            slave.stop()
            print "Finished. Bye!"
            exit(0)
        else:
            time.sleep(1)
    