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

from u2fval.model import Client, User, Device
from u2flib_server.u2f_v2 import (start_register, complete_register,
                                  start_authenticate, verify_authenticate)
from u2flib_server.utils import rand_bytes
from datetime import datetime
import logging


__all__ = ['U2FController']
log = logging.getLogger(__name__)


class U2FController(object):

    def __init__(self, session, memstore, client_name):
        self._session = session
        self._memstore = memstore
        self._client = session.query(Client) \
            .filter(Client.name == client_name).one()

    def _get_user(self, user_id):
        return self._session.query(User) \
            .filter(User.client_id == self._client.id) \
            .filter(User.name == user_id).first()

    def _get_device(self, handle):
        return self._session.query(Device).join(Device.user) \
            .filter(User.client_id == self._client.id) \
            .filter(Device.handle == handle).first()

    def _get_or_create_user(self, user_id):
        user = self._get_user(user_id)
        if user is None:
            user = User(user_id)
            self._client.users.append(user)
            log.info('User created: "%s/%s"' % (self._client.name, user_id))
        return user

    @property
    def client_name(self):
        return self._client.name

    def get_trusted_facets(self):
        return {
            'trustedFacets': [{
                'version': {'major': 2, 'minor': 0},
                'ids': self._client.valid_facets
            }]
        }

    def delete_user(self, user_id):
        user = self._get_user(user_id)
        if user is not None:
            self._session.delete(user)
            log.info('User deleted: "%s/%s"' % (self._client.name, user_id))

    def register_start(self, user_id):
        # RegisterRequest
        register_request = start_register(self._client.app_id)
        self._memstore.store(self._client.id, user_id,
                             register_request.challenge,
                             {'request': register_request})

        # SignRequest[]
        sign_requests = []
        user = self._get_user(user_id)
        if user is not None:
            for dev in user.devices.values():
                sign_requests.append(
                    start_authenticate(dev.bind_data, 'check-only'))

        # To support multiple versions, add more RegisterRequests.
        return [register_request], sign_requests

    def register_complete(self, user_id, resp):
        memkey = resp.clientData.challenge
        data = self._memstore.retrieve(self._client.id, user_id, memkey)
        bind, cert = complete_register(data['request'], resp,
                                       self._client.valid_facets)
        user = self._get_or_create_user(user_id)
        dev = user.add_device(bind.json, cert)
        log.info('User: "%s/%s" - Device registered: "%s"' % (
            self._client.name, user_id, dev.handle))
        return dev.handle

    def unregister(self, handle):
        dev = self._get_device(handle)
        self._session.delete(dev)
        log.info('User: "%s/%s" - Device unregistered: "%s"' % (
            self._client.name, dev.user.name, handle))

    def set_props(self, handle, props):
        dev = self._get_device(handle)
        dev.properties.update(props)

    def _do_get_descriptor(self, user_db_id, handle, filter):
        dev = self._session.query(Device) \
            .filter(Device.user_id == user_db_id) \
            .filter(Device.handle == handle).first()
        if dev is None:
            raise ValueError('No device matches descriptor: %s' % handle)
        return dev.get_descriptor(filter)

    def get_descriptor(self, user_id, handle, filter=None):
        user = self._get_user(user_id)
        return self._do_get_descriptor(user.id, handle, filter)

    def get_descriptors(self, user_id, filter=None):
        user = self._get_user(user_id)
        if user is None:
            return []
        return [d.get_descriptor(user_id, filter)
                for d in user.devices.values()]

    def authenticate_start(self, user_id, invalidate=False):
        user = self._get_user(user_id)
        if user is None:
            return []

        sign_requests = []
        challenges = {}
        rand = rand_bytes(32)
        for handle, dev in user.devices.items():
            challenge = start_authenticate(dev.bind_data, rand)
            sign_requests.append(challenge)
            challenges[handle] = {
                'keyHandle': challenge.keyHandle,
                'challenge': challenge
            }
        self._memstore.store(self._client.id, user_id, rand, challenges)
        return sign_requests

    def authenticate_complete(self, user_id, resp):
        memkey = resp.clientData.challenge
        challenges = self._memstore.retrieve(self._client.id, user_id, memkey)
        user = self._get_user(user_id)
        for handle, data in challenges.items():
            if data['keyHandle'] == resp.keyHandle:
                dev = user.devices[handle]
                verify_authenticate(
                    dev.bind_data,
                    data['challenge'],
                    resp,
                    self._client.valid_facets
                )
                dev.authenticated_at = datetime.now()
                return handle
        else:
            raise ValueError('No device found for keyHandle: %s' %
                             resp.keyHandle)
