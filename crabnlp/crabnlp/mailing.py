import asyncio

from crabnlp.tg import Telegram
from crabnlp.maildb import register_new_user, MailingInfo


MAIL_ASKING_TIPS = 'asking_tips'

# for user_id, mailings in maildb.get_users_mailings():
    

async def on_start(tg: Telegram, user_id: int, lang: str, is_new: bool, logger=None):
    if is_new:
        register_new_user(user_id)


async def mail_asking_24h(mailing_info: MailingInfo, mailings: set[str], now_ts, bot: Telegram):
    """Send question asking tips after 24 passed after registration"""
    if MAIL_ASKING_TIPS in mailings or not mailing_info.registered_at:
        return
    
    wait_sec = max(24 * 3600 - (now_ts - mailing_info.registered_at), 0)
    
    print('wait time', wait_sec)
    # await asyncio.sleep(wait_sec)

    bot.send_message(chat_id=mailing_info.user_id,
                    text="""Как бы я хорошо ни резюмировал видеоролики, всегда найдутся те, кому не подошло. Это связано """)
    
