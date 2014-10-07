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
from u2flib_server.u2f_v2 import U2FEnrollment, U2FBinding, U2FChallenge
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
        enroll = U2FEnrollment(self._client.app_id, self._client.valid_facets)
        enroll_data = enroll.data
        self._memstore.store(self._client.id, user_id, enroll.challenge, {
            'request': enroll.serialize()
        })

        # SignRequest[]
        sign_requests = []
        user = self._get_user(user_id)
        if user is not None:
            for dev in user.devices.values():
                binding = U2FBinding.deserialize(dev.bind_data)
                challenge = binding.make_challenge('check-only')
                sign_requests.append(challenge.data)

        # To support multiple versions, add more RegisterRequests.
        return [enroll_data], sign_requests

    def register_complete(self, user_id, resp):
        memkey = resp.clientData.challenge
        data = self._memstore.retrieve(self._client.id, user_id, memkey)
        u2f_enroll = U2FEnrollment.deserialize(data['request'])
        bind = u2f_enroll.bind(resp)
        user = self._get_or_create_user(user_id)
        dev = user.add_device(bind.serialize())
        # TODO: Save registration time property.
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

    def get_descriptor(self, handle, filter=None):
        dev = self._session.query(Device).filter(Device.handle == handle).one()
        return dev.get_descriptor(filter)

    def get_descriptors(self, user_id, filter=None):
        user = self._get_user(user_id)
        if user is None:
            return []
        return [d.get_descriptor(filter) for d in user.devices.values()]

    def authenticate_start(self, user_id, invalidate=False):
        user = self._get_user(user_id)
        if user is None:
            return []

        sign_requests = []
        challenges = {}
        rand = rand_bytes(32)
        for handle, dev in user.devices.items():
            binding = U2FBinding.deserialize(dev.bind_data)
            challenge = binding.make_challenge(rand)
            sign_requests.append(challenge.data)
            challenges[handle] = {
                'keyHandle': challenge.data.keyHandle,
                'challenge': challenge.serialize()
            }
        self._memstore.store(self._client.id, user_id, rand, {
            'challenges': challenges
        })
        return sign_requests

    def authenticate_complete(self, user_id, resp):
        memkey = resp.clientData.challenge
        stored = self._memstore.retrieve(self._client.id, user_id, memkey)
        user = self._get_user(user_id)
        for handle, data in stored['challenges'].items():
            if data['keyHandle'] == resp.keyHandle:
                dev = user.devices[handle]
                binding = U2FBinding.deserialize(dev.bind_data)
                challenge = U2FChallenge.deserialize(binding,
                                                     data['challenge'])
                challenge.validate(resp)
                dev.authenticated_at = datetime.now()
                return handle
        else:
            raise ValueError('No device found for keyHandle: %s' %
                             resp.keyHandle)
