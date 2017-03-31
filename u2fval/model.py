from __future__ import absolute_import

from . import app
from u2flib_server.model import Transport
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.associationproxy import association_proxy
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import Encoding
from base64 import b64encode, b64decode
from binascii import b2a_hex
from datetime import datetime
import json
import os


db = SQLAlchemy(app)


class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, db.Sequence('client_id_seq'), primary_key=True)
    name = db.Column(db.String(40), nullable=False, unique=True)
    app_id = db.Column(db.String(256), nullable=False)
    _valid_facets = db.Column('valid_facets', db.Text(), default='[]')

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


def _calculate_fingerprint(cert):
    return b2a_hex(cert.fingerprint(hashes.SHA256())).decode('ascii')


class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = (db.UniqueConstraint('client_id', 'name',
                                          name='_client_user_uc'),)

    id = db.Column(db.Integer, db.Sequence('user_id_seq'), primary_key=True)
    name = db.Column(db.String(40), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'))
    client = db.relationship(Client,
                             backref=db.backref('users', lazy='dynamic'))
    devices = db.relationship(
        'Device',
        backref='user',
        order_by='Device.handle',
        collection_class=attribute_mapped_collection('handle'),
        cascade='all, delete-orphan'
    )
    transactions = db.relationship(
        'Transaction',
        backref='user',
        order_by='Transaction.created_at.desc()',
        lazy='dynamic',
        cascade='all, delete-orphan')

    def __init__(self, name):
        self.name = name

    def add_device(self, bind_data, cert_der, transports=0):
        cert = x509.load_der_x509_certificate(cert_der, default_backend())
        certificate = db.session.query(Certificate) \
            .filter(Certificate.fingerprint == _calculate_fingerprint(cert)) \
            .first()
        if certificate is None:
            certificate = Certificate(cert)
        return Device(self, bind_data, certificate, transports)


class Certificate(db.Model):
    __tablename__ = 'certificates'

    id = db.Column(db.Integer, db.Sequence('certificate_id_seq'),
                   primary_key=True)
    # The fingerprint field is larger than needed, to accomodate longer
    # fingerprints in the future.
    fingerprint = db.Column(db.String(128), nullable=False, unique=True)
    _der = db.Column('der', db.Text(), nullable=False)

    @hybrid_property
    def der(self):
        return b64decode(self._der)

    @der.setter
    def der(self, der):
        self._der = b64encode(der)

    def __init__(self, cert):
        self.fingerprint = _calculate_fingerprint(cert)
        self.der = cert.public_bytes(Encoding.DER)

    def get_pem(self):
        cert = x509.load_der_x509_certificate(self.der, default_backend())
        return cert.public_bytes(Encoding.PEM)


class Device(db.Model):
    __tablename__ = 'devices'

    id = db.Column(db.Integer, db.Sequence('device_id_seq'), primary_key=True)
    handle = db.Column(db.String(32), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    bind_data = db.Column(db.Text())
    certificate_id = db.Column(db.Integer, db.ForeignKey('certificates.id'))
    certificate = db.relationship('Certificate')
    compromised = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    authenticated_at = db.Column(db.DateTime)
    counter = db.Column(db.BigInteger)
    transports = db.Column(db.BigInteger)
    _properties = db.relationship(
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

    def __init__(self, user, bind_data, certificate, transports=0):
        self.handle = b2a_hex(os.urandom(16)).decode('ascii')
        self.bind_data = bind_data
        self.user = user
        self.certificate = certificate
        self.transports = transports

    def update_properties(self, props):
        for k, v in props.items():
            if v is None:
                del self.properties[k]
            else:
                self.properties[k] = v

    def get_descriptor(self, metadata=None):
        authenticated = self.authenticated_at
        if authenticated is not None:
            authenticated = authenticated.isoformat() + 'Z'

        transports = [t.key for t in Transport if t.value & self.transports]
        data = {
            'handle': self.handle,
            'transports': transports,
            'compromised': self.compromised,
            'created': self.created_at.isoformat() + 'Z',
            'lastUsed': authenticated,
            'properties': dict(self.properties)
        }

        if metadata is not None:
            data['metadata'] = metadata

        return data


class Property(db.Model):
    __tablename__ = 'properties'

    id = db.Column(db.Integer, db.Sequence('property_id_seq'),
                   primary_key=True)
    key = db.Column(db.String(40))
    value = db.Column(db.Text())
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id'))

    def __init__(self, key, value):
        self.key = key
        self.value = value


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id = db.Column(db.Integer, db.Sequence('transaction_id_seq'),
                   primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    transaction_id = db.Column(db.String(64), nullable=False, unique=True)
    _data = db.Column(db.Text())
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, transaction_id, data):
        self.transaction_id = transaction_id
        self.data = data

    @hybrid_property
    def data(self):
        return json.loads(self._data)

    @data.setter
    def data(self, value):
        self._data = json.dumps(value)
