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

from u2flib_server.jsapi import (JSONDict, RegisterRequest, RegisterResponse,
                                 SignRequest, SignResponse)

__all__ = [
    'RegisterRequestData',
    'RegisterResponseData',
    'AuthenticateRequestData',
    'AuthenticateResponseData'
]


class WithProps(object):

    @property
    def properties(self):
        return self.get('properties', {})


class RegisterRequestData(JSONDict):

    @property
    def authenticateRequests(self):
        return map(SignRequest, self['authenticateRequests'])

    @property
    def registerRequests(self):
        return map(RegisterRequest, self['registerRequests'])


class RegisterResponseData(JSONDict, WithProps):

    @property
    def registerResponse(self):
        return RegisterResponse(self['registerResponse'])


class AuthenticateRequestData(JSONDict):

    @property
    def authenticateRequests(self):
        return map(SignRequest, self['authenticateRequests'])


class AuthenticateResponseData(JSONDict, WithProps):

    @property
    def authenticateResponse(self):
        return SignResponse(self['authenticateResponse'])
