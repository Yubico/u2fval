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


from u2fserver.model import Client
from sqlalchemy.orm import exc
import re


__all__ = ['create_controller']


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
            existing = self.get_client(name)
            raise ValueError('Client already exists: %s' % name)
        except KeyError:
            client = Client(name, app_id, valid_facets)
            self._session.add(client)

    def update_client(self, name, app_id=None, valid_facets=None):
        client = self.get_client(name)
        if app_id is not None:
            client.app_id = app_id
        if valid_facets is not None:
            client.valid_facets = valid_facets

    def delete_client(self, name):
        client = self.get_client(name)
        self._session.delete(client)

    def list_clients(self):
        return [c[0] for c in self._session.query(Client.name).all()]
