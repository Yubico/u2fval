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


from u2fval.model import Client
from sqlalchemy.orm import exc
import re
import logging


__all__ = ['ClientController']
log = logging.getLogger(__name__)


NAME_PATTERN = re.compile(r'^[a-zA-Z0-9-_.]{3,}$')


def ensure_valid_name(name):
    if len(name) < 3:
        raise ValueError('Client names must be at least 3 characters')
    if not NAME_PATTERN.match(name):
        raise ValueError('Client names may only contain the characters a-z, '
                         'A-Z, 0-9, "." (period), "_" (underscore), and "-" '
                         '(dash)')


class ClientController(object):

    def __init__(self, session):
        self._session = session

    def get_client(self, name):
        try:
            return self._session.query(Client) \
                .filter(Client.name == name) \
                .one()
        except exc.NoResultFound:
            raise KeyError('No Client with name %s found' % name)

    def create_client(self, name, app_id, valid_facets):
        ensure_valid_name(name)

        try:
            self.get_client(name)
            raise ValueError('Client already exists: %s' % name)
        except KeyError:
            client = Client(name, app_id, valid_facets)
            self._session.add(client)
            log.info('Client created: %s', name)

    def update_client(self, name, app_id=None, valid_facets=None):
        client = self.get_client(name)
        if app_id is not None:
            client.app_id = app_id
        if valid_facets is not None:
            client.valid_facets = valid_facets

    def delete_client(self, name):
        client = self.get_client(name)
        self._session.delete(client)
        log.info('Client deleted: %s', name)

    def list_clients(self):
        return [c[0] for c in self._session.query(Client.name).all()]
