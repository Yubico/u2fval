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

from sqlalchemy import (Column, Integer, String, Text, ForeignKey, Sequence,
                        Boolean, DateTime, BigInteger, UniqueConstraint)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, backref, object_session
from sqlalchemy.orm.collections import attribute_mapped_collection
from uuid import uuid4
from datetime import datetime
from hashlib import sha1
import json


Base = declarative_base()


class Client(Base):
    __tablename__ = 'clients'

    id = Column(Integer, Sequence('client_id_seq'), primary_key=True)
    name = Column(String(32), nullable=False, unique=True)
    app_id = Column(String(256), nullable=False)
    _valid_facets = Column('valid_facets', Text(), default='[]')

    def __init__(self, name, app_id, facets):
        self.name = name
        self.app_id = app_id
        self.valid_facets = facets

    @hybrid_property
    def valid_facets(self):
        return json.loads(self._valid_facets)

    @valid_facets.setter
    def valid_facets(self, facets):
        if not isinstance(facets, list):
            raise TypeError('facets must be a list')
        self._valid_facets = json.dumps(facets)


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (UniqueConstraint('client_id', 'name',
                                       name='_client_user_uc'),)

    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    name = Column(String(40), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'))
    client = relationship(Client, backref=backref('users'))
    devices = relationship(
        'Device',
        backref='user',
        order_by='Device.handle',
        collection_class=attribute_mapped_collection('handle'),
        cascade='all, delete-orphan'
    )
    transactions = relationship(
        'Transaction',
        backref='user',
        order_by='Transaction.created_at.desc()',
        lazy='dynamic',
        cascade='all, delete-orphan')

    def __init__(self, name):
        if len(name) > 40:
            self.name = sha1(name).hexdigest()
        else:
            self.name = name

    def add_device(self, bind_data, cert, properties=None):
        certificate = object_session(self).query(Certificate) \
            .filter(Certificate.fingerprint == cert.get_fingerprint()) \
            .first()
        if certificate is None:
            certificate = Certificate(cert)
        return Device(self, bind_data, certificate, properties)


class Certificate(Base):
    __tablename__ = 'certificates'

    id = Column(Integer, Sequence('certificate_id_seq'), primary_key=True)
    fingerprint = Column(String(32), nullable=False, unique=True)
    _der = Column('der', Text(), nullable=False)

    @hybrid_property
    def der(self):
        return self._der.decode('base64')

    @der.setter
    def der(self, der):
        self._der = der.encode('base64')

    def __init__(self, cert):
        self.fingerprint = cert.get_fingerprint()
        self.der = cert.as_der()


class Device(Base):
    __tablename__ = 'devices'

    id = Column(Integer, Sequence('device_id_seq'), primary_key=True)
    handle = Column(String(32), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    bind_data = Column(Text())
    certificate_id = Column(Integer, ForeignKey('certificates.id'))
    certificate = relationship('Certificate')
    compromised = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    authenticated_at = Column(DateTime)
    counter = Column(BigInteger)
    _properties = relationship(
        'Property',
        backref='device',
        order_by='Property.key',
        collection_class=attribute_mapped_collection('key'),
        cascade='all, delete-orphan'
    )
    properties = association_proxy(
        '_properties',
        'value',
        creator=lambda k, v: Property(k, v)
    )

    def __init__(self, user, bind_data, certificate, properties=None):
        if properties is None:
            properties = {}
        self.handle = uuid4().hex
        self.bind_data = bind_data
        self.properties.update(properties)
        self.user = user
        self.certificate = certificate

    def get_descriptor(self, metadata=None):
        authenticated = self.authenticated_at
        if authenticated is not None:
            authenticated = authenticated.isoformat() + 'Z'

        data = {
            'handle': self.handle,
            'compromised': self.compromised,
            'created': self.created_at.isoformat() + 'Z',
            'lastUsed': authenticated,
            'properties': dict(self.properties)
        }

        if metadata is not None:
            data['metadata'] = metadata

        return data


class Property(Base):
    __tablename__ = 'properties'

    id = Column(Integer, Sequence('property_id_seq'), primary_key=True)
    key = Column(String(32))
    value = Column(Text())
    device_id = Column(Integer, ForeignKey('devices.id'))

    def __init__(self, key, value):
        self.key = key
        self.value = value


# Used for storing transactions in the DB instead of memcached
# See transactiondb.py for more details.
class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, Sequence('transaction_id_seq'), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    transaction_id = Column(String(64), nullable=False, unique=True)
    _data = Column(Text())
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, transaction_id, data):
        self.transaction_id = transaction_id
        self.data = data

    @hybrid_property
    def data(self):
        return json.loads(self._data)

    @data.setter
    def data(self, value):
        self._data = json.dumps(value)
