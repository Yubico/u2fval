#    Copyright (C) 2014  Yubico AB
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import imp
import errno
import os
from u2fval import default_settings
import logging
import logging.config

__all__ = [
    'settings'
]

SETTINGS_FILE = os.getenv('U2FVAL_SETTINGS', os.path.join(
                          '/etc/yubico/u2f-val/u2f-val.conf'))
LOG_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(SETTINGS_FILE)),
                               'logging.conf')

VALUES = {
    'DATABASE_CONFIGURATION': 'db',
    'USE_MEMCACHED': 'mc',
    'MEMCACHED_SERVERS': 'mc_hosts'
}


def parse(conf, settings={}):
    for confkey, settingskey in VALUES.items():
        try:
            settings[settingskey] = conf.__getattribute__(confkey)
        except AttributeError:
            pass
    return settings


settings = parse(default_settings)

dont_write_bytecode = sys.dont_write_bytecode
try:
    sys.dont_write_bytecode = True
    user_settings = imp.load_source('user_settings', SETTINGS_FILE)
    settings = parse(user_settings, settings)
except IOError as e:
    if not e.errno in [errno.ENOENT, errno.EACCES]:
        raise e
finally:
    sys.dont_write_bytecode = dont_write_bytecode

# Set up logging
try:
    logging.config.fileConfig(LOG_CONFIG_FILE)
except:
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)
    log.exception("Unable to configure logging. Logging to console.")
