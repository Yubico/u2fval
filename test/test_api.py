from u2fval import app, exc
from u2fval.model import db, Client
from .soft_u2f_v2 import SoftU2FDevice
import unittest
import json


class RestApiTest(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['ALLOW_UNTRUSTED'] = True

        db.session.close()
        db.drop_all()
        db.create_all()
        db.session.add(Client('fooclient', 'https://example.com',
                              ['https://example.com']))
        db.session.commit()

        self.app = app.test_client()

    def test_call_without_client(self):
        err = json.loads(self.app.get('/').data.decode('utf8'))
        assert err['errorCode'] == exc.BadInputException.code

    def test_call_with_invalid_client(self):
        err = json.loads(
            self.app.get('/', environ_base={'REMOTE_USER': 'invalid'}
                         ).data.decode('utf8'))
        assert err['errorCode'] == exc.BadInputException.code

    def test_get_trusted_facets(self):
        resp = json.loads(
            self.app.get('/', environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert 'https://example.com' in resp['trustedFacets'][0]['ids']

    def test_list_empty_devices(self):
        resp = json.loads(
            self.app.get('/foouser', environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert resp == []

    def test_begin_auth_without_devices(self):
        err = json.loads(
            self.app.get('/foouser/authenticate',
                         environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert err['errorCode'] == exc.NoEligibleDevicesException.code

    def test_register(self):
        device = SoftU2FDevice()
        self.do_register(device, {'foo': 'bar'})

    def test_authenticate(self):
        device = SoftU2FDevice()
        self.do_register(device, {'foo': 'bar', 'baz': 'one'})
        descriptor = self.do_authenticate(device, {'baz': 'two'})
        assert descriptor['properties'] == {
            'foo': 'bar',
            'baz': 'two'
        }

    def test_get_properties(self):
        device = SoftU2FDevice()
        descriptor = self.do_register(device, {'foo': 'bar', 'baz': 'foo'})
        descriptor2 = json.loads(
            self.app.get('/foouser/' + descriptor['handle'],
                         environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert descriptor2['properties'] == {'foo': 'bar', 'baz': 'foo'}

    def test_get_devices(self):
        self.do_register(SoftU2FDevice())
        self.do_register(SoftU2FDevice())
        self.do_register(SoftU2FDevice())

        resp = json.loads(
            self.app.get('/foouser', environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert len(resp) == 3

    def test_delete_user(self):
        self.do_register(SoftU2FDevice())
        self.do_register(SoftU2FDevice())
        self.do_register(SoftU2FDevice())
        self.app.delete('/foouser',
                        environ_base={'REMOTE_USER': 'fooclient'})
        resp = json.loads(
            self.app.get('/foouser', environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert resp == []

    def test_delete_devices(self):
        d1 = self.do_register(SoftU2FDevice())
        d2 = self.do_register(SoftU2FDevice())
        d3 = self.do_register(SoftU2FDevice())

        self.app.delete('/foouser/' + d2['handle'],
                        environ_base={'REMOTE_USER': 'fooclient'})
        resp = json.loads(
            self.app.get('/foouser',
                         environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert len(resp) == 2
        self.app.delete('/foouser/' + d1['handle'],
                        environ_base={'REMOTE_USER': 'fooclient'})
        resp = json.loads(
            self.app.get('/foouser',
                         environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert resp == [d3]
        self.app.delete('/foouser/' + d3['handle'],
                        environ_base={'REMOTE_USER': 'fooclient'})
        resp = json.loads(
            self.app.get('/foouser',
                         environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert resp == []

    def do_register(self, device, properties=None):
        reg_req = json.loads(
            self.app.get('/foouser/register',
                         environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        assert len(reg_req['registeredKeys']) == \
            len(reg_req['descriptors'])

        reg_resp = device.register('https://example.com', reg_req['appId'],
                                   reg_req['registerRequests'][0]).json

        if properties is None:
            properties = {}
        descriptor = json.loads(self.app.post(
            '/foouser/register',
            data=json.dumps({
                'registerResponse': reg_resp,
                'properties': properties
            }),
            environ_base={'REMOTE_USER': 'fooclient'}
        ).data.decode('utf8'))
        assert descriptor['properties'] == properties
        return descriptor

    def do_authenticate(self, device, properties=None):
        aut_req = json.loads(
            self.app.get('/foouser/authenticate',
                         environ_base={'REMOTE_USER': 'fooclient'}
                         ).data.decode('utf8'))
        aut_resp = device.getAssertion('https://example.com', aut_req['appId'],
                                       aut_req['challenge'],
                                       aut_req['registeredKeys'][0]).json
        if properties is None:
            properties = {}
        return json.loads(self.app.post(
            '/foouser/authenticate',
            data=json.dumps({
                'signResponse': aut_resp,
                'properties': properties
            }),
            environ_base={'REMOTE_USER': 'fooclient'}
        ).data.decode('utf8'))
