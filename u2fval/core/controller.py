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

from u2fval.model import Client, User, Device
from u2fval.core.exc import (BadInputException, NoEligableDevicesException,
                             DeviceCompromisedException)
from u2flib_server.u2f_v2 import (start_register, complete_register,
                                  start_authenticate, verify_authenticate)
from u2flib_server.utils import rand_bytes
from datetime import datetime
import logging


__all__ = ['U2FController']
log = logging.getLogger(__name__)


class U2FController(object):

    def __init__(self, session, memstore, client_name, metadata,
                 require_trusted=True):
        self._session = session
        self._memstore = memstore
        self._client = session.query(Client) \
            .filter(Client.name == client_name).one()
        self._metadata = metadata
        self._require_trusted = require_trusted

    def _get_user(self, username):
        return self._session.query(User) \
            .filter(User.client_id == self._client.id) \
            .filter(User.name == username).first()

    def _get_device(self, handle):
        return self._session.query(Device).join(Device.user) \
            .filter(User.client_id == self._client.id) \
            .filter(Device.handle == handle).first()

    def _get_or_create_user(self, username):
        user = self._get_user(username)
        if user is None:
            user = User(username)
            self._client.users.append(user)
            log.info('User created: "%s/%s"', self._client.name, username)
        return user

    @property
    def client_name(self):
        return self._client.name

    def get_trusted_facets(self):
        return {
            'trustedFacets': [{
                'version': {'major': 1, 'minor': 0},
                'ids': self._client.valid_facets
            }]
        }

    def delete_user(self, username):
        user = self._get_user(username)
        if user is not None:
            self._session.delete(user)
            log.info('User deleted: "%s/%s"', self._client.name, username)

    def register_start(self, username):
        # RegisterRequest
        register_request = start_register(self._client.app_id)
        self._memstore.store(self._client.id, username,
                             register_request.challenge,
                             {'request': register_request})

        # SignRequest[]
        sign_requests = []
        user = self._get_user(username)
        if user is not None:
            for dev in user.devices.values():
                sign_requests.append(
                    start_authenticate(dev.bind_data, 'check-only'))

        # To support multiple versions, add more RegisterRequests.
        return [register_request], sign_requests

    def register_complete(self, username, resp):
        memkey = resp.clientData.challenge
        data = self._memstore.retrieve(self._client.id, username, memkey)
        bind, cert = complete_register(data['request'], resp,
                                       self._client.valid_facets)
        attestation = self._metadata.get_attestation(cert)
        if self._require_trusted and not attestation.trusted:
            raise BadInputException('Device type is not trusted')
        user = self._get_or_create_user(username)
        dev = user.add_device(bind.json, cert)
        log.info('User: "%s/%s" - Device registered: "%s"',
            self._client.name, username, dev.handle)
        return dev.handle

    def unregister(self, handle):
        dev = self._get_device(handle)
        self._session.delete(dev)
        log.info('User: "%s/%s" - Device unregistered: "%s"',
            self._client.name, dev.user.name, handle)

    def set_props(self, handle, props):
        dev = self._get_device(handle)
        dev.properties.update(props)

    def _do_get_descriptor(self, user, handle):
        if user is not None:
            dev = self._session.query(Device) \
                .filter(Device.user_id == user.id) \
                .filter(Device.handle == handle).first()
        if user is None or dev is None:
            raise BadInputException('No device matches descriptor: %s' % handle)
        return dev.get_descriptor(self._metadata.get_metadata(dev))

    def get_descriptor(self, username, handle):
        user = self._get_user(username)
        return self._do_get_descriptor(user, handle)

    def get_descriptors(self, username):
        user = self._get_user(username)
        if user is None:
            return []
        return [d.get_descriptor(self._metadata.get_metadata(d))
                for d in user.devices.values()]

    def authenticate_start(self, username, invalidate=False):
        user = self._get_user(username)
        if user is None or len(user.devices) == 0:
            log.info('User "%s" has no devices registered', username)
            raise NoEligableDevicesException('No devices registered', [])

        sign_requests = []
        challenges = {}
        rand = rand_bytes(32)

        for handle, dev in user.devices.items():
            if not dev.compromised:
                challenge = start_authenticate(dev.bind_data, rand)
                sign_requests.append(challenge)
                challenges[handle] = {
                    'keyHandle': challenge.keyHandle,
                    'challenge': challenge
                }

        if not sign_requests:
            raise NoEligableDevicesException(
                'All devices compromised',
                [d.get_descriptor() for d in user.devices.values()]
            )
        self._memstore.store(self._client.id, username, rand, challenges)
        return sign_requests

    def authenticate_complete(self, username, resp):
        memkey = resp.clientData.challenge
        challenges = self._memstore.retrieve(self._client.id, username, memkey)
        user = self._get_user(username)
        for handle, data in challenges.items():
            if data['keyHandle'] == resp.keyHandle:
                dev = user.devices[handle]
                if dev.compromised:
                    raise BadInputException('Device is compromised')

                counter, presence = verify_authenticate(
                    dev.bind_data,
                    data['challenge'],
                    resp,
                    self._client.valid_facets
                )
                if presence == chr(0):
                    raise Exception('User presence byte not set!')
                if counter > (dev.counter or -1):
                    dev.counter = counter
                    dev.authenticated_at = datetime.now()
                    return handle
                dev.compromised = True
                raise DeviceCompromisedException('Device counter mismatch',
                                                 dev.get_descriptor())
        else:
            raise BadInputException('No device found for keyHandle: %s' %
                                    resp.keyHandle)
