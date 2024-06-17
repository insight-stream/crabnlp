#!/usr/bin/env python
# coding: utf-8

import asyncio
import aiohttp
from typing import AsyncGenerator, Generator, Optional, List, Set
import json
import re
from contextlib import asynccontextmanager
from time import monotonic
from pathlib import Path

from crabnlp.youtube import is_youtube
from crabnlp.commons import get_json_logger


POLL_TIMEOUT = 1

ENTITY_BOT_COMMAND = 'bot_command'
ENTITY_URL = 'url'
ENTITY_TEXT_LINK = 'text_link'


def parse_entities(message: dict, type: str) -> Set[str]:
    text = message.get('text', '')
    return {text[e['offset']:(e['offset']+e['length'])] for e in message.get('entities', []) if e.get('type') == type}


_m = {'message_id': 370, 'from': {'id': 87799679, 'is_bot': False, 'first_name': 'Marat', 'username': 'tsundokum', 'language_code': 'en'}, 'chat': {'id': 87799679, 'first_name': 'Marat', 'username': 'tsundokum', 'type': 'private'}, 'date': 1678556500, 'text': '/balance www.leningrad.ru', 'entities': [{'offset': 0, 'length': 8, 'type': 'bot_command'}, {'offset': 9, 'length': 16, 'type': 'url'}]}
assert parse_entities(_m, ENTITY_BOT_COMMAND) == {'/balance'}
assert parse_entities(_m, ENTITY_URL) == {'www.leningrad.ru'}


def parse_youtube_urls(message) -> Set[str]:
    urls = parse_entities(message, ENTITY_URL)
    for ent in message.get('entities', []):
        if ent['type'] == 'text_link' and (url := ent.get('url')):
            urls.add(url)
    return {url for url in urls if is_youtube(url)}


_m = {'message_id': 204,
 'from': {'id': 6020972076,
  'is_bot': True,
  'first_name': '[DEV] infomat YouTube',
  'username': 'ru_infomat_bot'},
 'chat': {'id': 87799679,
  'first_name': 'Marat',
  'username': 'tsundokum',
  'type': 'private'},
 'date': 1678979352,
 'edit_date': 1678979358,
 'text': 'We are discussing How to get what you want... by Alex Hormozi.\n\nSend me a text message with your question\n\nEach answer or summary estimated cost is 1.80 RUB',
 'entities': [{'offset': 18,
   'length': 27,
   'type': 'text_link',
   'url': 'https://youtu.be/YaNX49ygr0I'},
  {'offset': 107, 'length': 49, 'type': 'italic'}],
 'reply_markup': {'inline_keyboard': [[{'text': 'Summary',
     'callback_data': '{"t": "summary", "vid": "YaNX49ygr0I"}'}]]}}
assert parse_youtube_urls(_m) == {'https://youtu.be/YaNX49ygr0I'}


class Telegram:
    def __init__(self, token, logging_directory):
        self.polling_offset = 0
        self.token = token
        self.updates_logger = get_json_logger(Path(logging_directory) / 'updates.jl', 'updates')
        self.posts_logger = get_json_logger(Path(logging_directory) / 'posts.jl', 'posts')

    async def post(self, method: str, fail_on_error=False, **kwargs):
        url = f'https://api.telegram.org/bot{self.token}/{method}'
        async with aiohttp.ClientSession() as session:
            started = monotonic()
            async with session.post(url, json=kwargs) as response:
                try:
                    j = await response.json()
                except:
                    j = {'text': await response.text}
                rt = monotonic() - started
                self.posts_logger.info({'method': method, 'status': response.status,
                                        'request': kwargs, 'response': j,
                                        'response_time': rt})
                if fail_on_error and response.status != 200:
                    raise Exception(f'Failed to call `{method}`: {response.status}, {await response.text()}')
                return j

    async def upload_video(self, file_path, **kwargs):
        url = f'https://api.telegram.org/bot{self.token}/sendVideo'
        data = aiohttp.FormData(quote_fields=False)
        data.add_field(
            "video", open(file_path, 'rb')
        )
        for k, v in kwargs.items():
            v_ = v if type(v) != int else json.dumps(v)
            data.add_field(k, json.dumps(v), content_type='application/json')
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                return await response.json()

    async def delete_message(self, fail_on_error=False, **kwargs) -> dict:
        return await self.post('deleteMessage', **kwargs)

    async def edit_message_text(self, fail_on_error=False, **kwargs) -> dict:
        return await self.post('editMessageText', **kwargs)

    @staticmethod
    def _split_by_chunks(text, max_page_size: int) -> Generator[str, None, None]:
        paragraphs = text.split('\n')
        acc = ''
        for p in paragraphs:
            if len(p) > max_page_size:
                raise Exception(f'Invalid page: too long line in message {text}')

            new_acc = (acc + '\n' + p).lstrip()
            if len(new_acc) > max_page_size:
                yield acc
                acc = p
            else:
                acc = new_acc

        yield acc

    async def send_message_typing(self, typing_delay_sec=2, **kwargs):
        async with self.chat_action(chat_id=kwargs['chat_id']):
            await asyncio.sleep(typing_delay_sec)
            await self.send_message(**kwargs)

    async def send_message(self, fail_on_error=True, **kwargs) -> Optional[dict]:
        LIMIT = 4096
        text = kwargs.get('text')
        if not text:
            return

        async def send_func(**override_kwargs) -> dict:
            params = dict(kwargs)
            params.update(override_kwargs)
            return await self.post('sendMessage', fail_on_error=fail_on_error, **params)

        reply_id = None
        for chunk in self._split_by_chunks(text, LIMIT):
            if reply_id == None:
                r = await send_func(text=chunk)
            else:
                r = await send_func(text=chunk, reply_to_message_id=reply_id) 
            reply_id = r.get('result', {}).get('message_id')

        return r

    async def poll(self, poll_timeout=POLL_TIMEOUT) -> AsyncGenerator:
        async with aiohttp.ClientSession() as session:
            while True:
                url = f'https://api.telegram.org/bot{self.token}/getUpdates?limit=1&offset={self.polling_offset}'
                async with session.get(url) as response:
                    resp = await response.json()
                    if (updates := resp.get('result')) is not None:
                        for u in updates:
                            self.polling_offset = u['update_id'] + 1
                            self.updates_logger.info(u)
                            yield u
                    else:
                        print('NO RESULT', resp)
                        self.updates_logger.error(resp)

                await asyncio.sleep(poll_timeout)

    @asynccontextmanager
    async def chat_action(self, chat_id, action='typing'):
        lock = asyncio.Event()
        async def act(lock):
            while not lock.is_set():
                await self.post('sendChatAction', action=action, chat_id=chat_id)
                await asyncio.sleep(5)
        asyncio.create_task(act(lock))
        try:
            yield
        finally:
            lock.set()


assert list(Telegram._split_by_chunks("line1\n\nline2", 1000)) == ['line1\n\nline2']
assert list(Telegram._split_by_chunks("line1\n\nline2", 5)) == ['line1', 'line2']


def escape_markdown(text: str, version: int = 1, entity_type: str = None) -> str:
    """
    Helper function to escape telegram markup symbols.
    (copied from `https://github.com/python-telegram-bot/python-telegram-bot/blob/1fdaaac8094c9d76c34c8c8e8c9add16080e75e7/telegram/utils/helpers.py#L149-L174`)
    Args:
        text (:obj:`str`): The text.
        version (:obj:`int` | :obj:`str`): Use to specify the version of telegrams Markdown.
            Either ``1`` or ``2``. Defaults to ``1``.
        entity_type (:obj:`str`, optional): For the entity types ``PRE``, ``CODE`` and the link
            part of ``TEXT_LINKS``, only certain characters need to be escaped in ``MarkdownV2``.
            See the official API documentation for details. Only valid in combination with
            ``version=2``, will be ignored else.
    """
    if int(version) == 1:
        escape_chars = r'_*`['
    elif int(version) == 2:
        if entity_type in ['pre', 'code']:
            escape_chars = r'\`'
        elif entity_type == 'text_link':
            escape_chars = r'\)'
        else:
            escape_chars = r'_*[]()~`>#+-=|{}.!'
    else:
        raise ValueError('Markdown version must be either 1 or 2!')

    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)


assert escape_markdown('Hi there_') == 'Hi there\\_'

