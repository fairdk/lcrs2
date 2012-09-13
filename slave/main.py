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

import threading
import socket
import time
import subprocess
import json
import logging
import re

# create logger
logger = logging.getLogger('lcrs_slave')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

import settings
import protocol

class RequestException(Exception):
    def __init__(self, value):
        self.parameter = value
    def __str__(self):
        return repr(self.parameter)

class Slave():
    
    def __init__(self):
        self.socket = None
        self.state = protocol.IDLE
        self.progress = 0.0
        self.shell_exec_cnt = 0
        self.shell_exec_results = {}
        
        self.thread   = threading.Thread (target = self.listen,)
        self.thread.setDaemon(True)
        self.thread.start()
        
        self.__fail_message = ""
        self.__wipe_output = None

    def listen(self, listen_port=None):
        """
        Read messages from clients. If the client closes its
        connection, start from scratch.
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.socket.settimeout(2)
        self.socket.bind ( ('', listen_port if listen_port else settings.LISTEN_PORT) )
        self.socket.listen(10)

        while True:
            try:
                self.client, address = self.socket.accept()
                logger.info("Received connection from %s." % str(address))
            except socket.timeout:
                continue
            
            while True:
                try:
                    self.client.settimeout(settings.CLIENT_TIMEOUT)
                    raw_data = self.client.recv(settings.MAX_PACKET_SIZE)
                    break
                except socket.timeout:
                    logger.warning("Client timed out.")
                    continue
                except socket.error, (__, errmsg):
                    logger.warning("Error in connection: %s." % str(errmsg))
                    break
            
            if raw_data:
                try:
                    self.process_request(raw_data)
                except RequestException, error_msg:
                    logger.warning("Request exception: %s" % error_msg)
                    self.state = protocol.FAIL
                    self.send_reply(str(error_msg))
                    
                self.client.close()
            
        self.socket.close()

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
        
        raise RequestException("Received unknown command ID: %s" % str(command))
        
    def send_reply(self, data=None):
        try:
            self.client.sendall(json.dumps([self.state, data]))
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
        
        self.send_reply(None)
        
        t = threading.Thread(target=self.__scan_thread, args=(data,))
        t.setDaemon(True)
        t.start()
        
    def wipe(self, data):
        logger.info("Received WIPE command.")
        if self.state == protocol.BUSY:
            raise RequestException("Cannot execute WIPE - current state is BUSY.")
        self.state = protocol.BUSY
        self.progress = 0.0
        
        t = threading.Thread(target=self.__wipe_thread, args=(data,))
        t.setDaemon(True)
        t.start()

        self.send_reply(None)
    
    def __wipe_thread(self, command):
        process = subprocess.Popen(str(command), bufsize=1, stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE, shell=True, universal_newlines=True)
        print ""
        while process.poll() is None:
            stdout = process.stdout.readline()
            re_pct = re.compile(r"(\d+)%", re.M)
            m = re_pct.search(stdout)
            if m:
                pct = int(m.group(1))
                self.progress = pct / 100.0
                logger.info("Wipe progress: %d%%" % (self.progress*100))
        # TODO: What's this???
        re_something = re.compile("\w+")
        stderr = process.stdout.read()
        if re_something.match(stderr):
            self.state = protocol.FAIL
            self.__fail_message = "Failed while wiping. Stderr was: %s" % stderr
            logger.info(self.__fail_message)
            return
        if process.returncode > 0:
            self.state = protocol.FAIL
            self.__fail_message = "Wipe failed. Return code from wipe: %d" % process.returncode
            logger.info(self.__fail_message)
            return
        self.progress = 1.0
        self.state = protocol.IDLE
        
    def badblocks(self, data):
        logger.info("Received BADBLOCKS command.")
        if self.state == protocol.BUSY:
            raise RequestException("Cannot execute BADBLOCKS - current state is BUSY.")
        self.state = protocol.BUSY
        self.progress = 0.0
        
        t = threading.Thread(target=self.__badblocks_thread, args=(data,))
        t.setDaemon(True)
        t.start()

        self.send_reply(None)
    
    def __badblocks_thread(self, command):
        process = subprocess.Popen(str(command), stdout=subprocess.PIPE, 
                                   stderr=subprocess.STDOUT, shell=True)
        while process.poll() is None:
            stdout = process.stdout.read(16)
            re_pct = re.compile(r"(\d\d)\.\d+%", re.M)
            m = re_pct.search(stdout)
            if m:
                pct = int(m.group(1))
                self.progress = pct / 100.0
                logger.info("Badblocks progress: %d%%" % (self.progress * 100))
        if process.returncode > 0:
            self.state = protocol.FAIL
            self.__fail_message = "Badblocks detected!"
            return
        self.progress = 1.0
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
        
        self.send_reply(shell_exec_id)


    def __shell_exec_thread(self, command, shell_exec_id):
        logger.info("Shell execution of: %s" % command)
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   shell=True,)
        (stdout, stderr) = process.communicate()
        self.shell_exec_results[shell_exec_id] = (stdout, stderr)
        self.state = protocol.IDLE
    
    def shell_results(self, data):
        try:
            command_id = int(data)
        except ValueError:
            raise RequestException("SHELL_RESULTS takes one integer argument.")
        
        try:
            (stdin, stdout) = self.shell_exec_results[command_id]
            self.send_reply((stdin, stdout))
        except KeyError:
            raise RequestException("No such result id. Maybe command hasn't finished.")
        
    def status(self, data):
        logger.info("Received STATUS command.")
        if data and type(data) == dict:
            if data.get("fail_message", False):
                self.send_reply(self.__fail_message)
                return
        self.send_reply(self.progress)
    
    def hardware(self, data):
        logger.info("Received HARDWARE command.")
        if self.hardware:
            self.send_reply(self.scan_results)
        else:
            self.send_reply(None)
    
    def __scan_thread(self, commands):
        # Execute a number of commands and return their output in the same order.
        command_cnt = len(commands)
        cnt = 0.0
        self.progress = 0.0
        for command in commands:
            logger.info("SCAN executing command: %s" % command)
            cnt = cnt + 1.0
            self.progress = self.progress + cnt / command_cnt
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE,
                                           shell=True,)
                (stdout, stderr) = process.communicate()
                self.scan_results[command] = (stdout, stderr)
            except OSError:
                self.scan_results[command] = (stdout, "Command does not exist")
        
        self.state = protocol.IDLE
        
if __name__ == "__main__":
    
    print ("""
 __        ______ .______          _______.   ____    ____  ___        ___   
|  |      /      ||   _  \        /       |   \   \  /   / |__ \      / _ \  
|  |     |  ,----'|  |_)  |      |   (----`    \   \/   /     ) |    | | | | 
|  |     |  |     |      /        \   \         \      /     / /     | | | | 
|  `----.|  `----.|  |\  \----.----)   |         \    /     / /_   __| |_| | 
|_______| \______|| _| `._____|_______/           \__/     |____| (__)\___/  
                                                                             
""")
    print ""
    print "----------------------------------------------------"
    print " Welcome to the LCRS slave server. Press Q to quit. "
    print "----------------------------------------------------"
    print ""
    
    slave = Slave()
    
    while True:
        s = raw_input()
        if s == 'q':
            print "Goodbye!"
            exit(0)
        else:
            time.sleep(1)
    