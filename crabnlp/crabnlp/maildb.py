####################################################
## DATABASE FOR ONBOARDING AND MAILING ACTIVITIES ##
####################################################
import os
from time import time
from typing import TypedDict, Generator, List

from crabnlp.db import Storage


ONBOARDING_STORAGE = os.environ.get('INFOMAT_BOT_STORAGE_MAILING', 'data/infomat/mailing.db')

mailing_db = Storage(ONBOARDING_STORAGE)

KEY_ONBOARDING = 'onboarding'
KEY_REGISTRATION_TS = 'reg-ts'
KEY_MAILING_SET = 'mailing-set'

class MailingInfo(TypedDict):
    user_id: int
    registered_at: float
    mailing_set: set[str]


def k(user_id: int | str, key_name):
    return f"{user_id}_{key_name}"


assert k(123, 'born') == '123_born'


def set_onboarding(user_id: int, state: str):
    mailing_db[k(user_id, KEY_ONBOARDING)] = state


def get_onboarding(user_id: int):
    return mailing_db[k(user_id, KEY_ONBOARDING)]


def register_new_use(user_id: int):
    mailing_db[k(user_id, KEY_REGISTRATION_TS)] = time()
    mailing_db[k(user_id, KEY_MAILING_SET)] = set()


def get_users_mailings() -> Generator[MailingInfo, None, None]:
    for ur in mailing_db:
        if ur.endswith(k('', KEY_REGISTRATION_TS)):
            user_id = ur.split('_', 1)[0]
            m = mailing_db[k(user_id, KEY_MAILING_SET)]
            r = mailing_db[k(user_id, KEY_REGISTRATION_TS)]
            info: MailingInfo = {'user_id': user_id,
                                 'registered_at': r,
                                 'mailing_set': m}
            yield info


