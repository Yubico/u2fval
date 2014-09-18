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

from sqlalchemy import (Column, Integer, String, Text, ForeignKey, Sequence,
                        DateTime)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, backref
from sqlalchemy.orm.collections import attribute_mapped_collection
from uuid import uuid4
import json
import datetime


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

    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    uuid = Column(String(32), nullable=False, unique=True)
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

    def __init__(self, uuid):
        self.uuid = uuid

    def add_device(self, bind_data, properties=None):
        return Device(self, bind_data, properties)


class Device(Base):
    __tablename__ = 'devices'

    id = Column(Integer, Sequence('device_id_seq'), primary_key=True)
    handle = Column(String(32), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    bind_data = Column(Text())
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

    def __init__(self, user, bind_data, properties=None):
        if properties is None:
            properties = {}
        self.handle = uuid4().hex
        self.bind_data = bind_data
        self.properties.update(properties)
        self.user = user

    def get_descriptor(self, filter=None):
        data = {'handle': self.handle}
        if filter is None:
            data['properties'] = dict(self.properties)
        else:
            data['properties'] = {k:self.properties.get(k) for k in filter}
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
    created_at = Column(DateTime, default=datetime.datetime.now)

    def __init__(self, transaction_id, data):
        self.transaction_id = transaction_id
        self.data = data

    @hybrid_property
    def data(self):
        return json.loads(self._data)

    @data.setter
    def data(self, value):
        self._data = json.dumps(value)


if __name__ == '__main__':
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine('sqlite:///:memory:', echo=True)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    user = User("test-user")
    device = user.add_device('data', {'createdAt': 'unknown'})

    session.add(user)
    session.commit()

    user = session.query(User).first()
    print user.devices[0].properties['createdAt']
