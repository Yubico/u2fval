from webtest import TestApp
from u2fval.model import Base
from u2fval.core.api import create_application
from u2fval.client.controller import ClientController
from u2fval.core import exc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .soft_u2f_v2 import SoftU2FDevice
import unittest
import os


class RestApiTest(unittest.TestCase):

    def setUp(self):
        os.environ['U2FVAL_SETTINGS'] = '/dev/null'
        from u2fval.config import settings
        settings['allow_untrusted'] = True

        engine = create_engine(settings['db'])
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        self.client_controller = ClientController(session)
        self.client_controller.create_client('fooclient',
                                             'https://example.com',
                                             ['https://example.com'])

        self.app = TestApp(create_application(settings, session))

    def test_call_without_client(self):
        err = self.app.get('/', status=400)
        assert err.json['errorCode'] == exc.BadInputException.code

    def test_call_with_invalid_client(self):
        err = self.app.get('/', status=400,
                           extra_environ={'REMOTE_USER': 'invalid'})
        assert err.json['errorCode'] == exc.BadInputException.code

    def test_get_trusted_facets(self):
        resp = self.app.get('/', extra_environ={'REMOTE_USER': 'fooclient'})
        assert 'https://example.com' in resp.json['trustedFacets'][0]['ids']

    def test_list_empty_devices(self):
        resp = self.app.get('/foouser',
                            extra_environ={'REMOTE_USER': 'fooclient'})
        assert resp.json == []

    def test_begin_auth_without_devices(self):
        err = self.app.get('/foouser/authenticate', status=400,
                           extra_environ={'REMOTE_USER': 'fooclient'})
        assert err.json['errorCode'] == exc.NoEligibleDevicesException.code

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
        descriptor2 = self.app.get('/foouser/' + descriptor['handle'],
                                   extra_environ={'REMOTE_USER': 'fooclient'})
        assert descriptor2.json['properties'] == {'foo': 'bar', 'baz': 'foo'}

    def test_get_devices(self):
        self.do_register(SoftU2FDevice())
        self.do_register(SoftU2FDevice())
        self.do_register(SoftU2FDevice())

        resp = self.app.get('/foouser',
                            extra_environ={'REMOTE_USER': 'fooclient'})
        descriptors = resp.json
        assert len(descriptors) == 3

    def test_delete_user(self):
        self.do_register(SoftU2FDevice())
        self.do_register(SoftU2FDevice())
        self.do_register(SoftU2FDevice())
        self.app.delete('/foouser',
                        extra_environ={'REMOTE_USER': 'fooclient'})
        resp = self.app.get('/foouser',
                            extra_environ={'REMOTE_USER': 'fooclient'})
        assert resp.json == []

    def test_delete_devices(self):
        d1 = self.do_register(SoftU2FDevice())
        d2 = self.do_register(SoftU2FDevice())
        d3 = self.do_register(SoftU2FDevice())

        self.app.delete('/foouser/' + d2['handle'],
                        extra_environ={'REMOTE_USER': 'fooclient'})
        resp = self.app.get('/foouser',
                            extra_environ={'REMOTE_USER': 'fooclient'})
        assert len(resp.json) == 2
        self.app.delete('/foouser/' + d1['handle'],
                        extra_environ={'REMOTE_USER': 'fooclient'})
        resp = self.app.get('/foouser',
                            extra_environ={'REMOTE_USER': 'fooclient'})
        assert resp.json == [d3]
        self.app.delete('/foouser/' + d3['handle'],
                        extra_environ={'REMOTE_USER': 'fooclient'})
        resp = self.app.get('/foouser',
                            extra_environ={'REMOTE_USER': 'fooclient'})
        assert resp.json == []

    def do_register(self, device, properties=None):
        reg_req = self.app.get('/foouser/register',
                               extra_environ={'REMOTE_USER': 'fooclient'})
        assert len(reg_req.json['authenticateRequests']) == \
            len(reg_req.json['authenticateDescriptors'])

        reg_resp = device.register(reg_req.json['registerRequests'][0],
                                   'https://example.com')

        if properties is None:
            properties = {}
        descriptor = self.app.post_json('/foouser/register', {
            'registerResponse': reg_resp.json,
            'properties': properties
        }, extra_environ={'REMOTE_USER': 'fooclient'})
        assert descriptor.json['properties'] == properties
        return descriptor.json

    def do_authenticate(self, device, properties=None):
        aut_req = self.app.get('/foouser/authenticate',
                               extra_environ={'REMOTE_USER': 'fooclient'})
        aut_resp = device.getAssertion(aut_req.json['authenticateRequests'][0],
                                       'https://example.com')
        if properties is None:
            properties = {}
        return self.app.post_json('/foouser/authenticate', {
            'authenticateResponse': aut_resp.json,
            'properties': properties
        }, extra_environ={'REMOTE_USER': 'fooclient'}).json
