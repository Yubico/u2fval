from __future__ import absolute_import

from . import app, exc
from .model import db, Client, User
from .transactiondb import DBStore
from flask import g, request, jsonify
from werkzeug.contrib.cache import SimpleCache, MemcachedCache
from u2flib_server.utils import websafe_decode
from u2flib_server.u2f import (begin_registration, complete_registration,
                               begin_authentication, complete_authentication)
from u2flib_server.attestation import MetadataProvider, create_resolver
from .jsobjects import (RegisterRequestData, RegisterResponseData,
                        SignRequestData, SignResponseData)
from datetime import datetime
from hashlib import sha256
from six.moves.urllib.parse import unquote
import json
import os
import re


if app.config['USE_MEMCACHED']:
    cache = MemcachedCache(app.config['MEMCACHED_SERVERS'])
else:
    cache = SimpleCache()


store = DBStore()


def create_metadata_provider(location):
    if os.path.isfile(location) \
            or (os.path.isdir(location) and os.listdir(location)):
        resolver = create_resolver(location)
    else:
        resolver = None
    return MetadataProvider(resolver)


metadata = create_metadata_provider(app.config.get('METADATA'))


def get_attestation(cert):
    key = sha256(cert).hexdigest()
    attestation = cache.get(key)
    if attestation is None:
        attestation = metadata.get_attestation(cert) or ''  # Cache "missing"
        cache.set(key, attestation, timeout=0)
    return attestation


def get_metadata(dev):
    key = 'cert_metadata/%d' % dev.certificate_id
    data = cache.get(key)
    if data is None:
        data = {}
        attestation = get_attestation(dev.certificate.der)
        if attestation:
            if attestation.vendor_info:
                data['vendor'] = attestation.vendor_info
            if attestation.device_info:
                data['device'] = attestation.device_info
        cache.set(key, data, timeout=0)
    return data


def get_client():
    client = getattr(g, 'client', None)
    if client is None:
        name = request.environ.get('REMOTE_USER')
        if name is None and app.debug and request.authorization:
            name = request.authorization.username
        if name is None:
            raise exc.BadInputException('No client specified')
        try:
            g.client = client = Client.query.filter(Client.name == name).one()
        except:
            raise exc.NotFoundException('Client not found')
    return client


def get_user(user_id):
    return get_client().users.filter(User.name == user_id).first()


# Exception handling


@app.errorhandler(400)
def handle_bad_request(error):
    resp = jsonify({
        'errorCode': exc.BadInputException.code,
        'errorMessage': error.description
    })
    resp.status_code = error.code
    return resp


@app.errorhandler(ValueError)
def handle_value_error(error):
    resp = jsonify({
        'errorCode': exc.BadInputException.code,
        'errorMessage': str(error)
    })
    resp.status_code = 400
    return resp


@app.errorhandler(exc.U2fException)
def handle_http_exception(error):
    resp = jsonify({
        'errorCode': error.code,
        'errorMessage': error.message
    })
    resp.status_code = error.status_code
    return resp


# Request handling


@app.route('/')
def trusted_facets():
    client = get_client()
    return jsonify({
        'trustedFacets': [{
            'version': {'major': 1, 'minor': 0},
            'ids': client.valid_facets
        }]
    })


@app.route('/<user_id>', methods=['GET', 'DELETE'], strict_slashes=False)
def user(user_id):
    user = get_user(user_id)
    if request.method == 'DELETE':
        if user:
            app.logger.info('Delete user: "%s/%s"', user.client.name,
                            user.name)
            db.session.delete(user)
            db.session.commit()
        return ('', 204)
    else:
        if user is not None:
            descriptors = [d.get_descriptor(get_metadata(d))
                           for d in user.devices.values()]
        else:
            descriptors = []
        return jsonify(descriptors)


def _get_registered_key(dev, descriptor):
    key = json.loads(dev.bind_data)
    # Only keep appId if different from the "main" one.
    if key.get('appId') == get_client().app_id:
        del key['appId']
    # The 'version' field used to be missing in RegisteredKey.
    if 'version' not in key:
        key['version'] = 'U2F_V2'
    # Use transports from descriptor (which includes metadata)
    key['transports'] = descriptor['transports']

    return key


def _register_request(user_id, challenge, properties):
    client = get_client()
    user = get_user(user_id)
    registered_keys = []
    descriptors = []
    if user is not None:
        for dev in user.devices.values():
            descriptor = dev.get_descriptor(get_metadata(dev))
            descriptors.append(descriptor)
            key = _get_registered_key(dev, descriptor)
            registered_keys.append(key)
    request_data = begin_registration(
        client.app_id,
        registered_keys,
        challenge
    )
    request_data['properties'] = properties
    store.store(client.id, user_id, challenge, request_data.json)

    data = RegisterRequestData.wrap(request_data.data_for_client)
    data['descriptors'] = descriptors
    return data


def _register_response(user_id, response_data):
    client = get_client()
    user = get_user(user_id)
    register_response = response_data.registerResponse
    challenge = register_response.clientData.challenge
    request_data = store.retrieve(client.id, user_id, challenge)
    if request_data is None:
        raise exc.NotFoundException('Transaction not found')
    request_data = json.loads(request_data)
    registration, cert = complete_registration(
        request_data, register_response, client.valid_facets)
    attestation = get_attestation(cert)
    if not app.config['ALLOW_UNTRUSTED'] and not attestation.trusted:
        raise exc.BadInputException('Device attestation not trusted')
    if user is None:
        app.logger.info('Creating user: %s/%s', client.name, user_id)
        user = User(user_id)
        client.users.append(user)
    transports = sum(t.value for t in attestation.transports or [])
    dev = user.add_device(registration.json, cert, transports)
    # Properties from the initial request have a lower precedence.
    dev.update_properties(request_data['properties'])
    dev.update_properties(response_data.properties)
    db.session.commit()
    app.logger.info('Registered device: %s/%s/%s', client.name, user_id,
                    dev.handle)
    return dev.get_descriptor(get_metadata(dev))


@app.route('/<user_id>/register', methods=['GET', 'POST'])
def register(user_id):
    if request.method == 'POST':
        # Response
        return jsonify(_register_response(
            user_id, RegisterResponseData.wrap(request.get_json(force=True))))
    else:
        # Request
        challenge = request.args.get('challenge', type=websafe_decode)
        if challenge is None:
            challenge = os.urandom(32)
        properties = request.args.get('properties', {},
                                      lambda x: json.loads(unquote(x)))

        return jsonify(_register_request(user_id, challenge, properties))


def _sign_request(user_id, challenge, handles, properties):
    client = get_client()
    user = get_user(user_id)
    if user is None or len(user.devices) == 0:
        app.logger.info('User "%s" has no devices registered', user_id)
        raise exc.NoEligibleDevicesException('No devices registered', [])

    registered_keys = []
    descriptors = []
    handle_map = {}

    if not handles:
        handles = user.devices.keys()

    for handle in handles:
        try:
            dev = user.devices[handle]
        except KeyError:
            raise exc.BadInputException('Invalid device handle: ' + handle)
        if not dev.compromised:
            descriptor = dev.get_descriptor(get_metadata(dev))
            descriptors.append(descriptor)
            key = _get_registered_key(dev, descriptor)
            registered_keys.append(key)
            handle_map[key['keyHandle']] = dev.handle

    if not registered_keys:
        raise exc.NoEligibleDevicesException(
            'All devices compromised',
            [d.get_descriptor() for d in user.devices.values()]
        )

    request_data = begin_authentication(
        client.app_id,
        registered_keys,
        challenge
    )
    request_data['handleMap'] = handle_map
    request_data['properties'] = properties

    store.store(client.id, user_id, challenge, request_data.json)
    data = SignRequestData.wrap(request_data.data_for_client)
    data['descriptors'] = descriptors
    return data


def _sign_response(user_id, response_data):
    client = get_client()
    user = get_user(user_id)
    sign_response = response_data.signResponse
    challenge = sign_response.clientData.challenge
    request_data = store.retrieve(client.id, user_id, challenge)
    if request_data is None:
        raise exc.NotFoundException('Transaction not found')
    request_data = json.loads(request_data)
    device, counter, presence = complete_authentication(
        request_data, sign_response, client.valid_facets)
    dev = user.devices[request_data['handleMap'][device['keyHandle']]]
    if dev.compromised:
        raise exc.DeviceCompromisedException('Device is compromised',
                                             dev.get_descriptor())
    if presence == 0:
        raise exc.BadInputException('User presence byte not set')
    if counter > (dev.counter or -1):
        dev.counter = counter
        dev.authenticated_at = datetime.now()
        dev.update_properties(request_data['properties'])
        dev.update_properties(response_data.properties)
        db.session.commit()
        return dev.get_descriptor(get_metadata(dev))
    else:
        dev.compromised = True
        db.session.commit()
        raise exc.DeviceCompromisedException('Device counter mismatch',
                                             dev.get_descriptor())


@app.route('/<user_id>/sign', methods=['GET', 'POST'])
def sign(user_id):
    if request.method == 'POST':
        # Response
        return jsonify(_sign_response(
            user_id, SignResponseData.wrap(request.get_json(force=True))))
    else:
        # Request
        challenge = request.args.get('challenge', type=websafe_decode)
        if challenge is None:
            challenge = os.urandom(32)
        properties = request.args.get('properties', {},
                                      lambda x: json.loads(unquote(x)))
        handles = request.args.getlist('handle')

        return jsonify(_sign_request(user_id, challenge, handles, properties))


_HANDLE_PATTERN = re.compile(r'^[a-f0-9]{32}$')


@app.route('/<user_id>/<handle>', methods=['GET', 'POST', 'DELETE'])
def device(user_id, handle):
    if _HANDLE_PATTERN.match(handle) is None:
        raise exc.BadInputException('Invalid device handle: ' + handle)

    user = get_user(user_id)
    try:
        dev = user.devices[handle]
    except (AttributeError, KeyError):
        raise exc.NotFoundException('Device not found')

    if request.method == 'DELETE':
        if dev is not None:
            app.logger.info('Delete handle: %s/%s/%s', user.client.name,
                            user.name, handle)
            db.session.delete(dev)
            db.session.commit()
        return ('', 204)
    elif request.method == 'POST':
        if dev is None:
            raise exc.NotFoundException('Device not found')
        dev.update_properties(request.get_json(force=True))
        db.session.commit()
    else:
        if dev is None:
            raise exc.NotFoundException('Device not found')
    return jsonify(dev.get_descriptor(get_metadata(dev)))


@app.route('/<user_id>/<handle>/certificate')
def device_certificate(user_id, handle):
    user = get_user(user_id)
    if user is None:
        raise exc.NotFoundException('Device not found')
    try:
        dev = user.devices[handle]
    except KeyError:
        raise exc.BadInputException('Invalid device handle: ' + handle)
    return dev.certificate.get_pem()
