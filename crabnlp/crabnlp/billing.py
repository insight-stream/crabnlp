
from functools import wraps
import os
from typing import Generator, List, Optional, Tuple
from crabnlp.db import Storage

import math

from crabnlp.llms import tlen


ADMINS = {'bavadim979'}
GPT_MODEL_NAME = "gpt-3.5-turbo"
GPT_MAX_CONTEXT_LEN = 4096
PAGE_SIZE = GPT_MAX_CONTEXT_LEN // 2



STORAGE_FN = os.environ.get('INFOMAT_BOT_STORAGE', 'data/infomat/users.db')
db = Storage(STORAGE_FN)


def calc_price_cents(text_or_token_count: str | int) -> int:
    """Returns price in RUB * 100.
    Assumes USD=75 RUB
    Markup=3"""
    if isinstance(text_or_token_count, str):
        count = tlen(text_or_token_count)
    elif isinstance(text_or_token_count, int):
        count = text_or_token_count
    else:
        raise RuntimeError(f'Unknown `type(text_or_token_count)` {type(text_or_token_count)}')

    return math.ceil(count / (1000 / 100) * 0.002 * 75 * 3)

def split_by_pages(arr: List[Tuple[str, int]]) -> Generator[List[str], None, None]:
    batch_cost = 0
    batch = []
    for utterance in arr:
        batch_cost += tlen(utterance['t'])
        batch.append(utterance)

        if batch_cost > PAGE_SIZE:
            yield batch
            batch.clear()
            batch_cost = 0
    yield batch


class NotEnoughMoney(Exception):
    def __init__(self, message, price, balance):
        self.message = message
        self.price = price
        self.balance = balance
        super().__init__()


def create_user_if_needed(tg_id: int, tg_username: str, wellcome_balance: int):
    is_new = db.create_user_if_needed(tg_id, tg_username, wellcome_balance)
    user = db.get_user(tg_id)
    return user, is_new

def check_balance(func):
    async def inner(*args, **kwargs):
        user_id = kwargs.get('user_id')
        user_name = kwargs.get('user_name')
        text = kwargs.get('text')
        if user_id == None or text == None:
            raise ValueError('user_id and text are required for billing transaction')

        user, _ = create_user_if_needed(user_id, user_name, 0)
        balance = user['balance']
        p = calc_price_cents(text)
        if balance < p:
            raise NotEnoughMoney('not enough money for transaction', price=p, balance=balance)
        else:
            res = await func(*args, **kwargs)
            db.charge_user(user_id, p, 'timecodes')
            return res, p

    return inner

def only_admin(func):
    async def inner(*args, **kwargs):
        admin_name = kwargs.get('admin_name')
        if admin_name in ADMINS:
            return True, await func(*args, **kwargs)
        else:
            return False, None
    return inner

def user_balance(user_id, user_name) -> int:
    user, _ = create_user_if_needed(user_id, user_name, 0)
    return user['balance']

def topup(user_id, cents, reason):
    user = db.get_user(user_id)
    if user == None:
        raise ValueError('User %s not found' % user_id)
    db.topup(user_id, cents, reason)
