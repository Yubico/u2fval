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

from u2fval.core.controller import U2FController
from u2fval.core.jsobjects import (
    RegisterRequestData, RegisterResponseData, AuthenticateRequestData,
    AuthenticateResponseData)
from webob.dec import wsgify
from webob import exc, Response
import json


__all__ = ['create_application']


def json_error(e, message=None, code=None):
    if type(e) == type:
        e = e()
    if code is None:
        code = e.status_code
    if message is None:
        message = e.message
    e.content_type = 'application/json'
    e.body = json.dumps({'errorCode': code, 'errorMessage': message})
    return e


def parse_filter(value):
    if value is not None:
        return value.split(',')
    return None


class U2FServerApplication(object):

    def __init__(self, session, memstore):
        self._session = session
        self._memstore = memstore

    @wsgify
    def __call__(self, request):
        client_name = request.environ.get('REMOTE_USER')
        if not client_name:
            raise json_error(exc.HTTPNotFound('Client not specified'))
        try:
            resp = self.client(request, client_name)
            if not isinstance(resp, Response):
                resp = Response(json.dumps(resp),
                                content_type='application/json')
            return resp
        except Exception as e:
            self._session.rollback()
            if isinstance(e, exc.HTTPException):
                if e.content_type != 'application/json':
                    e = json_error(e)
            else:
                e = json_error(exc.HTTPServerError(e.message))
            raise e
        finally:
            self._session.commit()

    def client(self, request, client_name):
        user_id = request.path_info_pop()
        controller = U2FController(self._session, self._memstore, client_name)
        if not user_id:
            if request.method == 'GET':
                return controller.get_trusted_facets()
            else:
                raise exc.HTTPMethodNotAllowed
        return self.user(request, controller, user_id.encode('utf-8'))

    def user(self, request, controller, user_id):
        if request.path_info_peek():
            page = request.path_info_pop()
            if page == 'register':
                return self.register(request, controller, user_id)
            elif page == 'authenticate':
                return self.authenticate(request, controller, user_id)
            else:
                return self.device(request, controller, user_id, page)

        if request.method == 'GET':
            properties = parse_filter(request.params.get('filter'))
            return controller.get_descriptors(user_id, properties)
        elif request.method == 'DELETE':
            controller.delete_user(user_id)
            return exc.HTTPNoContent()
        else:
            raise exc.HTTPMethodNotAllowed

    def register(self, request, controller, user_id):
        if request.method == 'GET':
            register_requests, sign_requests = controller.register_start(
                user_id)
            return RegisterRequestData(
                registerRequests=register_requests,
                authenticateRequests=sign_requests
            )
        elif request.method == 'POST':
            data = RegisterResponseData(request.body)
            try:
                handle = controller.register_complete(user_id,
                                                      data.registerResponse)
            except KeyError:
                raise exc.HTTPBadRequest
            controller.set_props(handle, data.properties)

            properties = parse_filter(request.params.get('filter'))
            return controller.get_descriptor(user_id, handle, properties)
        else:
            raise exc.HTTPMethodNotAllowed

    def authenticate(self, request, controller, user_id):
        if request.method == 'GET':
            sign_requests = controller.authenticate_start(user_id)
            return AuthenticateRequestData(
                authenticateRequests=sign_requests
            )
        elif request.method == 'POST':
            data = AuthenticateResponseData(request.body)
            try:
                handle = controller.authenticate_complete(
                    user_id, data.authenticateResponse)
            except KeyError:
                raise exc.HTTPBadRequest
            controller.set_props(handle, data.properties)

            properties = parse_filter(request.params.get('filter'))
            return controller.get_descriptor(user_id, handle, properties)
        else:
            raise exc.HTTPMethodNotAllowed

    def device(self, request, controller, user_id, handle):
        try:
            if request.method == 'GET':
                properties = parse_filter(request.params.get('filter'))
                return controller.get_descriptor(user_id, handle, properties)
            elif request.method == 'POST':
                props = json.loads(request.body)
                controller.set_props(handle, props)
                return exc.HTTPNoContent()
            elif request.method == 'DELETE':
                controller.unregister(handle)
                return exc.HTTPNoContent()
            else:
                raise exc.HTTPMethodNotAllowed
        except ValueError as e:
            raise exc.HTTPNotFound(e.message)


def create_application(settings):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(settings['db'], echo=True)

    Session = sessionmaker(bind=engine)
    session = Session()

    if settings['mc']:
        from u2fval.core.transactionmc import MemcachedStore
        memstore = MemcachedStore(settings['mc_hosts'])
    else:
        from u2fval.core.transactiondb import DBStore
        memstore = DBStore(session)

    return U2FServerApplication(session, memstore)
