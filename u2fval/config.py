# Copyright (c) 2014 Yubico AB
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or
#   without modification, are permitted provided that the following
#   conditions are met:
#
#    1. Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#    2. Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

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
                          '/etc/yubico/u2fval/u2fval.conf'))
LOG_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(SETTINGS_FILE)),
                               'logging.conf')

VALUES = {
    'DATABASE_CONFIGURATION': 'db',
    'USE_MEMCACHED': 'mc',
    'MEMCACHED_SERVERS': 'mc_hosts',
    'METADATA': 'metadata',
    'ALLOW_UNTRUSTED': 'allow_untrusted'
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
    if e.errno not in [errno.ENOENT, errno.EACCES]:
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
