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

from u2fserver.core.controller import U2FController
from u2fserver.core.jsobjects import (
    RegisterRequestData, RegisterResponseData, AuthenticateRequestData,
    AuthenticateResponseData)
from webob.dec import wsgify
from webob import exc, Response
import json


__all__ = ['create_application']


class U2FServerApplication(object):

    def __init__(self, session, memstore):
        self._session = session
        self._memstore = memstore

    @wsgify
    def __call__(self, request):
        client_name = request.path_info_pop()
        if not client_name:
            raise exc.HTTPNotFound
        try:
            resp = self.client(request, client_name)
            if not isinstance(resp, Response):
                resp = Response(json.dumps(resp),
                                content_type='application/json')
            return resp
        except:
            self._session.rollback()
            raise
        finally:
            self._session.commit()

    def client(self, request, client_name):
        uuid = request.path_info_pop()
        if not uuid:
            raise exc.HTTPNotFound
        controller = U2FController(self._session, self._memstore, client_name)
        return self.user(request, controller, uuid.encode('utf-8'))


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
            filter = request.params.get('filter')
            if filter is not None:
                filter = filter.split(',')
            return controller.get_descriptors(uuid, filter)
        elif request.method == 'DELETE':
            controller.delete_user(uuid)
            return exc.HTTPNoContent()
        else:
            raise exc.HTTPMethodNotAllowed

    def register(self, request, controller, uuid):
        if request.method == 'GET':
            register_requests, sign_requests = controller.register_start(uuid)
            return RegisterRequestData(
                registerRequests=register_requests,
                authenticateRequests=sign_requests
            )
        elif request.method == 'POST':
            data = RegisterResponseData(request.body)
            try:
                handle = controller.register_complete(uuid, data.registerResponse)
            except KeyError:
                raise exc.HTTPBadRequest
            controller.set_props(handle, data.setProps)
            return controller.get_descriptor(handle, data.getProps)
        else:
            raise exc.HTTPMethodNotAllowed

    def authenticate(self, request, controller, uuid):
        if request.method == 'GET':
            sign_requests = controller.authenticate_start(uuid)
            return AuthenticateRequestData(
                authenticateRequests=sign_requests
            )
        elif request.method == 'POST':
            data = AuthenticateResponseData(request.body)
            try:
                handle = controller.authenticate_complete(
                    uuid, data.authenticateResponse)
            except KeyError:
                raise exc.HTTPBadRequest
            controller.set_props(handle, data.setProps)
            return controller.get_descriptor(handle, data.getProps)
        else:
            raise exc.HTTPMethodNotAllowed

    def device(self, request, controller, uuid, handle):
        if request.method == 'GET':
            filter = request.params.get('filter')
            if filter is not None:
                filter = filter.split(',')
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


def create_application(settings):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from u2fserver.core.transactionmc import MemcachedStore
    from u2fserver.core.transactiondb import DBStore
    engine = create_engine(settings['db'], echo=True)

    Session = sessionmaker(bind=engine)
    session = Session()

    if settings['mc']:
        memstore = MemcachedStore(settings['mc_hosts'])
    else:
        memstore = DBStore(session)

    return U2FServerApplication(session, memstore)


if __name__ == '__main__':
    from u2fserver.model import Base, Client
    from wsgiref.simple_server import make_server
    from u2fserver.core.transactionmc import MemcachedStore
    from u2fserver.core.transactiondb import DBStore
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

    #memstore = MemcachedStore('127.0.0.1:11211')
    memstore = DBStore(session)

    application = U2FServerApplication(session, memstore)

    httpd = make_server('0.0.0.0', 4711, application)
    httpd.serve_forever()
