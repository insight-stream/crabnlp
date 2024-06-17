from crabnlp.tg import Telegram
from crabnlp.maildb import get_onboarding, set_onboarding

ONBOARDING_STATE_EXPECTING_YOUTUBE = 'expecting_yt'
ONBOARDING_STATE_EXPECTING_QUESTION = 'expecting_question'
ONBOARDING_STATE_FINISHED = 'finished'

# duplicated same function from infomat.bot.py
def M(lang_to_message: dict, language, default_language='en'):
    if (resp := lang_to_message.get(language)):
        return resp
    else:
        return lang_to_message[default_language]
    

messages_onboarding_intro = {
    'ru': "🎓\nСейчас я покажу вам, как пользоваться мной. Представим, что вы хотите узнать секрет счастья из видео https://www.youtube.com/watch?v=8KkKuTCFvzI , но смотреть видеоролик не хотите.",
    'en': "🎓\nI'll show you how to use me. Let's imagine that you want to learn about the secret of happiness from the video https://www.youtube.com/watch?v=8KkKuTCFvzI , but don't want to watch the video."
}
messages_onboarding_copy = {
    'ru': """🎓\nПСначала вам нужно скопировать ссылку и отдельным сообщением прислать ее мне.\n\nПопробуйте сделать это сейчас.""",
    'en': "🎓\nThe first step is to copy the link and send it to me as a separate message.\n\nTry it now."
}
messages_onboarding_pinned = {
    'ru': """🎓\nЯ прикрепил сообщение ☝️, чтобы мы не забывали, какое видео обсуждаем. В этом сообщении есть кнопка запроса краткого содержания 📝. Но наша цель — получить ответ на конкретный вопрос!""",
    'en': "🎓\nI've attached a message ☝️ so we don't forget which video we're discussing. This post has a button to request a summary 📝. But our goal is to get an answer to a specific question."
}
messages_onboarding_own_question = {
    'ru': """🎓\nПридумайте вопрос по этому ролику и пришлите мне его отдельным сообщением. Ответ будет на том языке, на котором сформулирован вопрос.\n\nПопробуйте сейчас.""",
    'en': "🎓\nCome up with a question about this video and send it to me in a separate message. The answer will be in the language of the question.\n\nTry it now."
}
messages_onboarding_copy_question = {
    'ru': """🎓\nНапишите мне отдельным сообщением вопрос: "Какой главный секрет счастья?" Ответ будет на том языке, на котором сформулирован вопрос.\n\nПопробуйте сейчас.""",
    'en': """🎓\nWrite me a separate message with the question: "What is the main secret of happiness?" The answer will be in the language of the question.\n\nTry it now."""
}


messages_onboarding_wording = {
    'ru': """🎓\nФормулировка важна. Например, если к вопросу добавить "Подробный ответ", то ответ будет больше страницы на смартфоне.""",
    'en': """🎓\nFormulation is important. For example, if you add "Detailed answer" to the question, then the answer will be more than a page on a smartphone."""
}
messages_onboarding_price = {
    'ru': """🎓\nОбратите внимание на стоимость после значка 💸 в прикрепленном сообщении. Это примерная стоимость каждого запроса к видео. В /help вы сможете подробнее узнать, как формируется стоимость.""",
    'en': "🎓\nPay attention to the cost after the 💸 emoji in the pinned message. This is the approximate cost of each video request. In /help you can find out more about how the cost is formed."
}
messages_onboarding_finished = {
    'ru': """🎓\nНа этом обучение завершено. Если у вас остались вопросы, то можете их задать в группе поддержки https://t.me/infomat_community или воспользоваться командой /help""",
    'en': "🎓\nThis completes the tutorial. If you have any questions, you can ask them in the support group https://t.me/infomat_community or use the /help command"
}


async def on_start(tg, user_id, lang: str, is_new: bool, logger=None):
    is_repeated = get_onboarding(user_id) is not None
    if is_repeated:
        set_onboarding(user_id, None)

    if logger:
        logger.info('onboarding', extra={'onboarding_state': 'started', 
                                         'chat_id': user_id, 'is_repeated': is_repeated})

    await tg.send_message_typing(chat_id=user_id, disable_web_page_preview=True,
                                 text=M(messages_onboarding_intro, lang))
        
    await tg.send_message_typing(chat_id=user_id,
                                 text=M(messages_onboarding_copy, lang))
    set_onboarding(user_id, ONBOARDING_STATE_EXPECTING_YOUTUBE)
    if logger:
        logger.info('onboarding', extra={'onboarding_state': ONBOARDING_STATE_EXPECTING_YOUTUBE, 
                                         'chat_id': user_id, 'is_repeated': is_repeated})


async def on_url_sent(tg: Telegram, user_id: int, update: dict, vid: str, lang: str, logger=None):
    if get_onboarding(user_id) != ONBOARDING_STATE_EXPECTING_YOUTUBE:
        return

    message = update['message']

    await tg.send_message_typing(chat_id=message['chat']['id'],
                                 text=M(messages_onboarding_pinned, lang))
    
    if vid != '8KkKuTCFvzI':
        await tg.send_message_typing(chat_id=message['chat']['id'],
                                     text=M(messages_onboarding_own_question, lang))
    else:
        await tg.send_message_typing(chat_id=message['chat']['id'],
                                     text=M(messages_onboarding_copy_question, lang))                            
        
    set_onboarding(user_id, ONBOARDING_STATE_EXPECTING_QUESTION)
    if logger:
        logger.info('onboarding', extra={'onboarding_state': ONBOARDING_STATE_EXPECTING_QUESTION, 
                                         'vid': vid, 'update': update, 'user_id': user_id})


async def on_question_answered(tg: Telegram, user_id: int, lang: str, logger=None):
    if get_onboarding(user_id) != ONBOARDING_STATE_EXPECTING_QUESTION:
        return
    
    await tg.send_message_typing(chat_id=user_id, text=M(messages_onboarding_wording, lang))
    
    chat_info = await tg.post('getChat', chat_id=user_id)
    if pinned := chat_info['result'].get('pinned_message'):
        reply_to_message_id = pinned.get('message_id')
    await tg.send_message_typing(chat_id=user_id, reply_to_message_id=reply_to_message_id,
                                 text=M(messages_onboarding_price, lang))

    await tg.send_message_typing(chat_id=user_id, text=M(messages_onboarding_finished, lang))
    
    set_onboarding(user_id, ONBOARDING_STATE_FINISHED)
    if logger:
        logger.info('onboarding', extra={'onboarding_state': ONBOARDING_STATE_FINISHED,
                                         'user_id': user_id})
