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

from u2flib_server.model import (JSONDict, RegisterResponse, SignResponse,
                                 U2fRegisterRequest, U2fSignRequest)

__all__ = [
    'RegisterRequestData',
    'RegisterResponseData',
    'SignResponseData',
    'SignResponseData'
]


class WithProps(object):

    @property
    def properties(self):
        return self.get('properties', {})


class WithDescriptors(object):

    @property
    def descriptors(self):
        return [JSONDict.wrap(x) for x in self['descriptors']]


class RegisterRequestData(U2fRegisterRequest, WithDescriptors):
    pass


class RegisterResponseData(JSONDict, WithProps):
    _required_fields = ['registerResponse']

    @property
    def registerResponse(self):
        return RegisterResponse.wrap(self['registerResponse'])

    @classmethod
    def wrap(cls, data):
        try:
            return super(RegisterResponseData, cls).wrap(data)
        except ValueError:
            response = RegisterResponse.wrap(data)
            return cls(registerResponse=response.json)


class SignRequestData(U2fSignRequest, WithDescriptors):
    pass


class SignResponseData(JSONDict, WithProps):
    _required_fields = ['signResponse']

    @property
    def signResponse(self):
        return SignResponse.wrap(self['signResponse'])

    @classmethod
    def wrap(cls, data):
        try:
            return super(SignResponseData, cls).wrap(data)
        except ValueError:
            response = SignResponse.wrap(data)
            return cls(signResponse=response.json)
