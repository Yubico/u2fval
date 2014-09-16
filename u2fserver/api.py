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

from u2fserver.controller import U2FController
from webob.dec import wsgify
from webob import exc, Response
import json


class U2FServerApplication(object):

    def __init__(self, session, memstore):
        self._session = session
        self._memstore = memstore

    @wsgify
    def __call__(self, request):
        client_id = request.path_info_pop()
        if not client_id:
            raise exc.HTTPNotFound
        try:
            resp = self.client(request, client_id)
            if not isinstance(resp, Response):
                resp = Response(json.dumps(resp),
                                content_type='application/json')
            return resp
        except:
            self._session.rollback()
            raise
        finally:
            if self._session.dirty:
                self._session.commit()

    def client(self, request, client_id):
        uuid = request.path_info_pop()
        if not uuid:
            raise exc.HTTPNotFound
        controller = U2FController(self._session, self._memstore, client_id)
        return self.user(request, controller, uuid)


    def user(self, request, controller, uuid):
        if request.path_info_peek():
            page = request.path_info_pop()
            if page == 'register':
                return self.register(request, controller, uuid)
            elif page == 'authenticate':
                return self.authenticate(request, controller, uuid)
            else:
                return self.device(request, controller, uuid, page)

        if request.method == 'GET':
            filter = request.params.get('filter', None)
            return controller.get_descriptors(uuid, filter)
        elif request.method == 'DELETE':
            controller.delete_user(uuid)
            return exc.HTTPNoContent()
        else:
            raise exc.HTTPMethodNotAllowed

    def register(self, request, controller, uuid):
        if request.method == 'GET':
            return controller.register_start(uuid)
        elif request.method == 'POST':
            result = json.loads(request.body)
            u2f_response = result['registerResponse']
            handle = controller.register_complete(u2f_response)
            get_props = result.get('getProps', [])
            set_props = result.get('setProps', {})
            controller.set_props(handle, set_props)
            return controller.get_descriptor(handle, get_props)
        else:
            raise exc.HTTPMethodNotAllowed

    def authenticate(self, request, controller, uuid):
        if request.method == 'GET':
            return controller.authenticate_start(uuid)
        elif request.method == 'POST':
            result = json.loads(request.body)
            u2f_response = result['authenticateResponse']
            handle = controller.authenticate_complete(u2f_response)
            get_props = result.get('getProps', [])
            set_props = result.get('setProps', {})
            controller.set_props(handle, set_props)
            return controller.get_descriptor(handle, get_props)
        else:
            raise exc.HTTPMethodNotAllowed

    def device(self, request, controller, uuid, handle):
        if request.method == 'GET':
            filter = request.params.get('filter', None)
            return controller.get_descriptor(handle, filter)
        elif request.method == 'POST':
            props = json.loads(request.body)
            controller.set_props(handle, props)
            return exc.HTTPNoContent()
        elif request.method == 'DELETE':
            controller.unregister(handle)
            return exc.HTTPNoContent()
        else:
            raise exc.HTTPMethodNotAllowed


if __name__ == '__main__':
    from u2fserver.model import Base, Client
    from wsgiref.simple_server import make_server
    from u2fserver.memstore import MemStore
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine('sqlite:///:memory:', echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    # Set up a demo Client, with the ID 1.
    session.add(Client('http://demo.yubico.com/app-identity',
                       ['http://demo.yubico.com']))
    session.commit()

    application = U2FServerApplication(session, MemStore())

    httpd = make_server('0.0.0.0', 4711, application)
    httpd.serve_forever()
