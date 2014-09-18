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


from u2fval.model import User, Transaction
from datetime import datetime, timedelta


class DBStore(object):

    def __init__(self, session, max_transactions=5, ttl=300):
        self._session = session
        self._max_transactions = max_transactions
        self._ttl = ttl

    def _delete_expired(self):
        expiration = datetime.now() - timedelta(seconds=self._ttl)
        self._session.query(Transaction) \
            .filter(Transaction.created_at < expiration).delete()

    def store(self, uuid, transaction_id, data):
        transaction_id = transaction_id.encode('hex')
        user = self._session.query(User).filter(User.uuid == uuid).first()
        if user is None:
            user = User(uuid)
            self._session.add(user)
        else:
            self._delete_expired()
            # Delete oldest transactions until we have room for one more.
            for transaction in user.transactions \
                    .offset(self._max_transactions - 1).all():
                self._session.delete(transaction)
        user.transactions.append(Transaction(transaction_id, data))

    def retrieve(self, uuid, transaction_id):
        transaction_id = transaction_id.encode('hex')
        self._delete_expired()
        transaction = self._session.query(Transaction) \
            .filter(Transaction.transaction_id == transaction_id).one()
        if transaction.user.uuid != uuid:
            raise ValueError('Transaction not valid for uuid: %s' % uuid)
        self._session.delete(transaction)
        return transaction.data
