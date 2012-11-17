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

def octetsAsInts (s='10.20.20.1'):
    '''
        Converts a 4-octet represented as a string to an int-array representation
    '''
    if type(s) == str:
        return [int(c) for c in s.split('.')]
    elif type(s) == list:
        return s
    else:
        raise Exception('octetsAsInts cannot deal with this thing: ' + repr(s))

def octetsAsString (c=[10,20,20,1]):
    '''
        Converts a 4-octet represented as an int-array representation to a string
    '''
    if type(c) == str:
        return c
    elif type(c) == list:
        return ".".join (str(i) for i in c)
    else:
        raise Exception('octetsAsString cannot deal with this thing: ' + repr(c))


def fillFixedBuffer (size, octets, filler=0):
    if type(octets) == 'str':
        octets = octetsAsString(octets)

    return map (ord,octets) + [0]*( size-len(octets) )

