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

class Group:
    """
        Handles logical stuff for all the MasterComputers that has been put inside it.
    """
    
    def __init__(self, name='N/A'):
        self.name = name
        self.computers = []
        
        # Should this group be delete-able?
        self.cannotDelete = False
        
    def addComputer (self, computer):
        if computer in self.computers: return
        self.computers.append (computer)
    
    def removeComputer(self, computer):
        try:
            self.computers.remove(computer)
        except:
            pass
    
    def getName(self):
        return self.name
