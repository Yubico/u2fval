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

import memcache

__all__ = ['MemcachedStore']


class MemcachedStore(object):
    def __init__(self, hosts, max_transactions=5, ttl=300):
        self._mc = memcache.Client(hosts)
        self._max_transactions = max_transactions
        self._ttl = ttl

    def store(self, uuid, transaction_id, data):
        transaction_id = transaction_id.encode('hex')
        keys = self._mc.get(uuid) or []
        if len(keys) + 1 >= self._max_transactions:
            self._mc.delete('%s_%s' % (uuid, keys.pop(0)))
        keys.append(transaction_id)
        t_key = '%s_%s' % (uuid, transaction_id)
        self._mc.set_multi({
            uuid: keys,
            t_key: data
        }, self._ttl)

    def retrieve(self, uuid, transaction_id):
        transaction_id = transaction_id.encode('hex')
        t_key = '%s_%s' % (uuid, transaction_id)
        data = self._mc.get_multi([uuid, t_key])
        keys = data.get(uuid)
        value = data[t_key]
        if keys:
            keys.remove(transaction_id)
            self._mc.set(uuid, keys, self._ttl)
        if value:
            self._mc.delete(t_key)
        return value
