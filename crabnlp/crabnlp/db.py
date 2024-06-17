#!/usr/bin/env python
# coding: utf-8

# In[1]:


import dbm
import json
import pickle


# In[2]:


def _transaction_key(user_id: int):
    return f"{user_id}_transactions"


class Storage:
    def __init__(self, filename):
        self.filename = filename
        with dbm.open(filename, 'c'):
            pass

    def get_user(self, user_id: int):
        with dbm.open(self.filename) as db:
            try:
                bu = db[str(user_id)]
                return json.loads(bu)
            except KeyError:
                return None

    def create_user_if_needed(self,
                              tg_id: int,
                              tg_username: str,
                              wellcome_balance: int):
        """Returns `True` if a new user has been created"""
        u = self.get_user(tg_id)
        if u:
            return False
        with dbm.open(self.filename, 'w') as db:
            u = {'username': tg_username,
                 'balance': wellcome_balance}
            db[str(tg_id)] = json.dumps(u)

            tk = _transaction_key(tg_id)
            assert tk not in db

            ts = [
                {'delta': wellcome_balance,
                 'reason': 'wellcome'}
            ]
            db[tk] = json.dumps(ts)

            return True

    def get_transactions(self, user_id: int):
        with dbm.open(self.filename) as db:
            tk = _transaction_key(user_id)
            try:
                return json.loads(db[tk])
            except KeyError:
                return

    def _change_balance(self,
                       tg_id: int,
                       amount: int,
                       reason: str):
        user = self.get_user(tg_id)
        assert user
        transactions = self.get_transactions(tg_id)
        assert transactions

        with dbm.open(self.filename, 'w') as db:
            tk = _transaction_key(tg_id)
            tr = {'delta': amount,
                  'reason': reason}
            transactions.append(tr)
            db[tk] = json.dumps(transactions)

            user['balance'] += amount
            db[str(tg_id)] = json.dumps(user)

    def charge_user(self,
                    tg_id: int,
                    amount: int,
                    reason: str):
        assert amount > 0
        self._change_balance(tg_id, -amount, reason)

    def topup(self,
              tg_id: int,
              amount: int,
              reason: str):
        assert amount > 0
        self._change_balance(tg_id, amount, reason)

    def get_value(self, key, default=None, decode=pickle.loads):
        k = str(key)
        with dbm.open(self.filename) as db:
            if k in db:
                return decode(db[k])
            else:
                return default

    def set_value(self, key, value, encode=pickle.dumps):
        k = str(key)
        v = encode(value)
        with dbm.open(self.filename, 'w') as db:
            db[k] = v

    def __getitem__(self, key):
        return self.get_value(key)

    def __setitem__(self, key, value):
        return self.set_value(key, value)


# In[6]:


if __name__ == '__main__':
    import tempfile
    import random
    from pathlib import Path
    import glob
    import os

    fn = Path(tempfile.gettempdir()) / f"dbm-test-{random.randint(100000000, 900000000)}"

    try:
        s = Storage(fn)

        assert not s.get_user(100)
        assert s.create_user_if_needed(100, 'tester', 100 * 100)
        assert s.get_user(100) == {'username': 'tester', 'balance': 10000}
        assert s.get_transactions(100) == [{'delta': 10000, 'reason': 'wellcome'}]

        s.charge_user(100, 99, 'spent')
        assert s.get_user(100) == {'username': 'tester', 'balance': 9901}
        s.topup(100, 22222, 'paid')
        assert s.get_user(100) == {'username': 'tester', 'balance': 32123}
        assert s.get_transactions(100) == [
            {'delta': 10000, 'reason': 'wellcome'},
            {'delta': -99, 'reason': 'spent'},
            {'delta': 22222, 'reason': 'paid'}]

        s.set_value(1234, '67890')
        assert s.get_value(1234, '67890')

        s.set_value('dict', {'hello': 'there'})
        assert s.get_value('dict') == {'hello': 'there'}

        s.set_value('333', [1, 2, {6, 7}, '7'])
        assert s.get_value(333) == [1, 2, {6, 7}, '7']

        s[444] = {'j': 'k', 'l': [1, 2, 3]}
        assert s[444] == {'j': 'k', 'l': [1, 2, 3]}
    finally:
        for ff in glob.glob(str(fn) + '*'):
            os.remove(ff)

