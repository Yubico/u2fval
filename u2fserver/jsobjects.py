from u2flib_server.jsapi import (JSONDict, RegisterRequest, RegisterResponse,
                                 SignRequest, SignResponse)

__all__ = [
    'RegisterRequestData',
    'RegisterResponseData',
    'AuthenticateRequestData',
    'AuthenticateResponseData'
]


class RegisterRequestData(JSONDict):

    @property
    def authenticateRequests(self):
        return map(SignRequest, self['authenticateRequests'])

    @property
    def registerRequests(self):
        return map(RegisterRequest, self['registerRequests'])


class RegisterResponseData(JSONDict):

    @property
    def registerResponse(self):
        return RegisterResponse(self['registerResponse'])

    @property
    def getProps(self):
        return self.get('getProps', [])

    @property
    def setProps(self):
        return self.get('setProps', {})


class AuthenticateRequestData(JSONDict):

    @property
    def authenticateRequests(self):
        return map(SignRequest, self['authenticateRequests'])


class AuthenticateResponseData(JSONDict):

    @property
    def authenticateResponse(self):
        return SignResponse(self['authenticateResponse'])

    @property
    def getProps(self):
        return self.get('getProps', [])

    @property
    def setProps(self):
        return self.get('setProps', {})
