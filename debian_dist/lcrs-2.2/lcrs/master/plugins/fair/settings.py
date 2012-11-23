import ConfigParser

FAIR_SERVER = 'localhost:8000'
USE_HTTPS = False
FAIR_SECRET_KEY = ""

CONFIG_FILE = "/etc/lcrs.fair.config"

config = ConfigParser.SafeConfigParser()
config.read([CONFIG_FILE])


if not config.has_section('network'):
    config.add_section('network')
