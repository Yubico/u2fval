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

from flask import Flask
import os

__version__ = "2.0.0"


app = Flask(__name__)
app.config.from_object('u2fval.default_settings')

# If U2FVAL_SETTINGS is specified, load that file. Otherwise, load a file from
# /etc/yubico/u2fval/ if it exists.
silent = True
conf_file = os.environ.get('U2FVAL_SETTINGS')
if conf_file:
    silent = False
    if not os.path.isabs(conf_file):
        conf_file = os.path.join(os.getcwd(), conf_file)
else:
    conf_file = '/etc/yubico/u2fval/u2fval.conf'

app.config.from_pyfile(conf_file, silent=silent)

# The previous version used DATABASE_CONFIGURATION.
db_conn = app.config.get('DATABASE_CONFIGURATION')
if db_conn is not None:
    app.logger.warn('The DATABASE_CONFIGURATION setting is deprecated, you '
                    'should use SQLALCHEMY_DATABASE_URI instead!')
    app.config['SQLALCHEMY_DATABASE_URI'] = db_conn

import u2fval.view  # noqa
import u2fval.model  # noqa
