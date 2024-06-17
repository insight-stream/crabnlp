#!/usr/bin/env python3
# coding: utf-8

from functools import cache, wraps
import os
import sys
import re
import math
from typing import AsyncGenerator, Generator, List, Optional, Tuple
import asyncio
import aiohttp
from iso639 import languages
from crabnlp.commons import pretty_time


OPENAI_KEY = os.environ['OPENAI']
SUMMARIZATION_THRESHOLD = 256

cache = {}
def memoize(func):
    """
    (c) 2021 Nathan Henrie, MIT License
    https://n8henrie.com/2021/11/decorator-to-memoize-sync-or-async-functions-in-python/
    """

    async def memoized_async_func(*args, **kwargs):
        key = (args, frozenset(sorted(kwargs.items())))
        if key in cache:
            return cache[key]
        result = await func(*args, **kwargs)
        cache[key] = result
        return result

    def memoized_sync_func(*args, **kwargs):
        key = (args, frozenset(sorted(kwargs.items())))
        if key in cache:
            return cache[key]
        result = func(*args, **kwargs)
        cache[key] = result
        return result

    if asyncio.iscoroutinefunction(func):
        return memoized_async_func
    return memoized_sync_func


async def req(prompt, session: aiohttp.ClientSession) -> str:
    TRIES = 3
    for _ in range(TRIES):
        try:
            async with session.post('https://api.openai.com/v1/chat/completions', headers={
                    "Authorization": f"Bearer {OPENAI_KEY}",
                    "Content-Type": "application/json",
                }, json = {
                    "model": "gpt-3.5-turbo",
                    "temperature": 0,
                    "messages": prompt
            }) as res:

                body = await res.json()

                if res.status != 200:
                    print(body, file=sys.stderr)
                    await asyncio.sleep(3)
                    continue

                body = body['choices'][0]
                if body['finish_reason'] == 'stop':
                    break
                else:
                    print('too short summarization context')
                    # todo switched of for price consistence
                    break
        except aiohttp.client_exceptions.ClientOSError as e:
            await asyncio.sleep(3)
            continue


    if not ('message' in body):
        raise Exception(f"unable to summarize message {body['error']['message']}")

    return body['message']['content']

@memoize
async def gpt_md(page: str, lang: Optional[str]) -> str:
    if lang == None:
        TASK = f'Write a short summary and TL;DR, preserve references in brackets, use language of the original text:\n\n'
    else:
        lang_name = languages.get(alpha2=lang).name
        TASK = f'Write a short summary and TL;DR, preserve references in brackets, translate to {lang_name}:\n\n'
    history = [TASK + ("Качество нормальное, за эти деньги хорошо. "
        "Конечно же есть недостатки по пошиву (1). Брала XXL потому что рост 180 см, так советовал продавец(2). "
        "На фото я кушала 3 раза уже (3), но пояс очень сильно торчит (4). Этот размер на красавиц с большими объёмами, "
        "но явно не на талию 70 см, в ягодицах объём 100, но тоже большеваты (5). Зато в ногах отлично и длина очень хорошая (6). "
        "У меня очень длинные ноги и мне хорошо (7). Пояс приходится подворачивать, это очень неудобно (8). Возможно найду Ателье, "
        "где смогут ушить их (9). Тянутся невероятно :) но вот воняют ужасно (10). Уже неделю адский запах не выветривается (11). "
        "Тёплые, но в мороз -20 градусов они не спасут на голое тело (12). Не верьте отзывам, они наверно шерстяные колготки под "
        "них одевают (13). В помещение ноги не преют, хотя думала будут потеть сильно (14). С радостью бы такие и другого цвета "
        "купила, но на 2 размера меньше (15). Но тогда длина будет короткой (16). Продавец, может попробуете шить несколько штук на "
        "высоких и стройных девушек (17)? На рынке нет никого предлагающего длинные леггинсы (18)."),
    (
        "# Отзыв на леггинсы\n\n"
        "- нормальное качество, но есть недостатки по пошиву (1)\n"
        "- модель подходит девушкам с большими объемами и длинными ногами (5, 6)\n"
        "- автору велики, придется обращаться в ателье (9)\n"
        "- присутствует неприятный запах (11)\n"
        "- в сильный мороз холодные, но в помещении не будет жарко (12, 14)\n\n"
        "TL;DR: леггинсы имеют хорошие качество, длинные и на большой размер."
    )]

    if len(page) < SUMMARIZATION_THRESHOLD:
        return page
    else:
        async with aiohttp.ClientSession() as session:
            example_prompt = TASK + page
            history_last = history[:2] + [example_prompt]      
            history_last = [ {"role": "user" if i % 2 == 0 else 'assistant', "content": txt} for i, txt in enumerate(history_last) ] 
            
            res = await req(history_last, session)
            history.append(example_prompt)
            history.append(res)
            return res

def enrich_links(text, refs, base_url) -> str:
    start_time = None
    
    match = re.search(r'\(((\d+)(-\d+)?)((\, \d+)+|(\d+-\d+))?\)', text)
    while match:
        item_num = int(match.group(2))

        if item_num != None:
            if (len(refs) > item_num) and (refs[item_num] != None):
                start_time = math.floor(refs[item_num])
                text = text[0:match.span()[0]] + f'<a href="{base_url + str(start_time)}">[{pretty_time(start_time)}]</a>' + text[match.span()[1]:]
            else:
                text = text[0:match.span()[0]] + text[match.span()[1]:]
        match = re.search(r'\(((\d+)(-\d+)?)((\, \d+)+|(\d+-\d+))?\)', text)

    return text


def parse_page(chapter: str, segments: list) -> Tuple[Optional[str], str, List[Tuple[str, int]]]:
    doc_sum = chapter.split('TL;DR:')
    if len(doc_sum) == 2:
        tldr = doc_sum[1]
        body = doc_sum[0]
    else:
        body = chapter
        tldr = None

    parts = body.split('\n')
    bullets = parts[1:]
    title = parts[0].replace('#', '').strip()
    
    bullets_links = []
    for bullet_text in bullets:
        if len(bullet_text.strip()) == 0:
            continue
        bullet_text = bullet_text.replace('\t', '').replace('-', '').strip()
        match = re.search(r'\(((\d+)(-\d+)?)((\, \d+)+|(\d+-\d+))?\)', bullet_text)
        if match:
            item_num = int(match.group(2))
            text = bullet_text[0:match.span()[0]] + bullet_text[match.span()[1]:]
            if len(segments) > item_num:
                start_time = math.floor(segments[item_num])
            else:
                start_time = None
        else:
            text = bullet_text
            start_time = None
            
        bullets_links.append((text.strip(), start_time))

    return tldr, title, bullets_links


async def summarize_with_timecodes(text_with_refs, refs, base_url, translate_to_languaage_code: Optional[str]) -> str:
    chapter = await gpt_md(text_with_refs, translate_to_languaage_code)
    tldr, title, bullets_times = parse_page(chapter, refs)
    if tldr == None:
        item_text = title
    else:
        item_text = tldr 
        
    item_text = enrich_links(item_text, refs, base_url)
    
    start_times = [ start_time for _, start_time in bullets_times if start_time != None]

    if refs == None or len(refs) == 0:
        return item_text

    if len(start_times) != 0:
        start_time = start_times[0]
    else:
        start_time = math.floor(refs[0])
    res = f'<a href="{base_url + str(start_time)}">[{pretty_time(start_time)}]</a> {item_text}'

    return res
