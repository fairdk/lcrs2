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

import ConfigParser
import os, sys

import logging
logger = logging.getLogger('lcrs')

DEBUG = False

TFTP_COMMAND = "in.tftpd -a %(ip)s -s -l -v -v -v -L %(path)s"

MASTER_PATH = os.path.abspath(__file__)
MASTER_PATH = os.path.split(MASTER_PATH)[0]
MASTER_PATH = os.path.abspath(MASTER_PATH)

# TODO: Is this really necessary??
sys.path.append(".")
sys.path.append(MASTER_PATH)

ui_plugins = [
    #(ExamplePlugin, {'disabled': False,}),
    #(FairIDPlugin, {'disabled': False,}),
    #(FairRegisterPlugin, {'disabled': False,}),
    #(FairLoginPlugin, {'disabled': False,}),
]

DEFAULT_CONFIG_FILE = os.path.join(MASTER_PATH, "config_master_default.cfg")

CONFIG_FILE = os.path.expanduser('~/.coresu.cfg')

config = ConfigParser.SafeConfigParser()
config.readfp(open(DEFAULT_CONFIG_FILE))
config.read([CONFIG_FILE])

if not config.has_section('network'):
    config.add_section('network')

if not config.has_section('tftp'):
    config.add_section('tftp')

if not config.has_section('plugins'):
    config.add_section('plugins')

def load_plugins():
    import plugins
    import inspect, pkgutil
    for (__, module_name, __) in list(pkgutil.iter_modules(plugins.__path__)):
        
        module = __import__("%s.%s" % (plugins.__name__, module_name)).__dict__[module_name]
        for cls in dir(module):
            cls=getattr(module,cls)
            if (inspect.isclass(cls)
                and cls.__name__ != plugins.BasePlugin.__name__ #@UndefinedVariable
                and issubclass(cls, plugins.BasePlugin)):
                logger.debug('found in {f}: {c}'.format(f=module.__name__,c=cls))
                ui_plugins.append((cls, {'disabled': False}))
    
# Set config variables
dhcpServerAddress   = config.get('network', 'server-ip')
dhcpInterface       = config.get('network', 'server-iface')
dhcpPrefix          = config.get('network', 'dhcp-prefix')
dhcpIpRange         = range(
  config.getint('network', 'dhcp-range-lower'),
  config.getint('network', 'dhcp-range-upper')+1
)
tftpRoot            = config.get('tftp', 'tftp-root-dir')
tftpTftpy          = bool(config.getint('tftp', 'use_tftpy'))

if not dhcpIpRange:
    logger.error("Wrong initial DHCP in configuration... exiting")
    sys.exit(1)

def write_config():
    
    config.set('network', 'server-ip', dhcpServerAddress)
    config.set('network', 'server-iface', dhcpInterface)
    config.set('network', 'dhcp-prefix', dhcpPrefix)
    config.set('network', 'dhcp-range-lower', str(min(dhcpIpRange)))
    config.set('network', 'dhcp-range-upper', str(max(dhcpIpRange)))
    config.set('tftp', 'tftp-root-dir', tftpRoot)
    config.set('tftp', 'use_tftpy', str(int(tftpTftpy)))
    
    f = open(CONFIG_FILE, 'wb')
    config.write(f)

