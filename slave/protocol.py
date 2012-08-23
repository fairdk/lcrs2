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

# States of the slave application
( IDLE,
  FAIL,
  BUSY,
  DISCONNECTED ) = range(4)

def translate_state(state):
    global IDLE, FAIL, BUSY
    if state == IDLE:
        return "idle"
    if state == FAIL:
        return "fail"
    if state == BUSY:
        return "busy"
    if state == DISCONNECTED:
        return "disconnected"

# Request IDs
(
    SCAN, # Start scanning for hardware
    WIPE, # Start wiping
    STATUS, # Get current status (state, progress)
    HARDWARE, # Get results from SCAN command
    SHELL_EXEC, # Execute a single command and return command ID
    SHELL_RESULTS, # Get results of a command ID
    BADBLOCKS, # Get results of a command ID
) = range(7) 

