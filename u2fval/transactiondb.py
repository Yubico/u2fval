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

from __future__ import absolute_import

from .model import db, User, Transaction
from u2flib_server.utils import sha_256
from datetime import datetime, timedelta
from binascii import b2a_hex


class DBStore(object):

    def __init__(self, max_transactions=5, ttl=300):
        self._max_transactions = max_transactions
        self._ttl = ttl

    def _delete_expired(self):
        expiration = datetime.utcnow() - timedelta(seconds=self._ttl)
        Transaction.query \
            .filter(Transaction.created_at < expiration).delete()

    def store(self, client_id, user_id, transaction_id, data):
        transaction_id = b2a_hex(sha_256(transaction_id))
        user = User.query \
            .filter(User.client_id == client_id) \
            .filter(User.name == user_id).first()
        if user is None:
            user = User(user_id)
            user.client_id = client_id
            db.session.add(user)
        else:
            self._delete_expired()
            # Delete oldest transactions until we have room for one more.
            for transaction in user.transactions \
                    .offset(self._max_transactions - 1).all():
                db.session.delete(transaction)
        user.transactions.append(Transaction(transaction_id, data))
        db.session.commit()

    def retrieve(self, client_id, user_id, transaction_id):
        transaction_id = b2a_hex(sha_256(transaction_id))
        self._delete_expired()
        transaction = Transaction.query \
            .filter(Transaction.transaction_id == transaction_id).first()
        if transaction is None:
            raise ValueError('Invalid transaction')
        if transaction.user.name != user_id or \
                transaction.user.client_id != client_id:
            raise ValueError('Transaction not valid for user_id: %s'
                             % user_id)
        db.session.delete(transaction)
        db.session.commit()
        return transaction.data
