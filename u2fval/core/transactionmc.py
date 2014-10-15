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

import memcache

__all__ = ['MemcachedStore']


class MemcachedStore(object):
    def __init__(self, hosts, max_transactions=5, ttl=300):
        self._mc = memcache.Client(hosts)
        self._max_transactions = max_transactions
        self._ttl = ttl

    def store(self, client_id, user_id, transaction_id, data):
        mc_key = '%s/%s' % (client_id, user_id)
        transaction_id = transaction_id.encode('hex')
        keys = self._mc.get(mc_key) or []
        if len(keys) + 1 >= self._max_transactions:
            self._mc.delete('%s_%s' % (mc_key, keys.pop(0)))
        keys.append(transaction_id)
        t_key = '%s_%s' % (mc_key, transaction_id)
        self._mc.set_multi({
            mc_key: keys,
            t_key: data
        }, self._ttl)

    def retrieve(self, client_id, user_id, transaction_id):
        mc_key = '%s/%s' % (client_id, user_id)
        transaction_id = transaction_id.encode('hex')
        t_key = '%s_%s' % (mc_key, transaction_id)
        data = self._mc.get_multi([mc_key, t_key])
        keys = data.get(mc_key)
        value = data[t_key]
        if keys:
            keys.remove(transaction_id)
            self._mc.set(mc_key, keys, self._ttl)
        if value:
            self._mc.delete(t_key)
        return value
