from webtest import TestApp
from u2fval.model import Base
from u2fval.core.api import create_application
from u2fval.client.controller import ClientController
from u2fval.core import exc
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import unittest
import os


class RestApiTest(unittest.TestCase):

    def setUp(self):
        os.environ['U2FVAL_SETTINGS'] = '/dev/null'
        from u2fval.config import settings

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

    def test_begin_register(self):
        reg_req = self.app.get('/foouser/register',
                               extra_environ={'REMOTE_USER': 'fooclient'})
        assert reg_req.json['authenticateRequests'] == []
        assert reg_req.json['authenticateDescriptors'] == []
