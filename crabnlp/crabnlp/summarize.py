#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
from typing import List
import concurrent.futures
import asyncio

import openai
from polyglot.detect import Detector
from polyglot.detect.base import UnknownLanguage
import tiktoken

from crabnlp.llm import tlen, create, acreate_chatcompletion, chunk_a_text


# In[2]:


# # import sys
# !{sys.executable} -m pip install deepl


# In[3]:


# GPT_MODEL_NAME = "text-curie-001"
# GPT_MODEL_NAME = "text-davinci-003"
GPT_MODEL_NAME = "gpt-3.5-turbo"
GPT_MODEL_MAX_TOKENS = 2049
openai.api_key = os.environ['OPENAI']

tok = tiktoken.encoding_for_model(GPT_MODEL_NAME)


# In[4]:


# from 002_multilang_summarization.ipynb

PROMPT_SUMMARY = {
    'en': 'Summarize the text',
    'bg': 'Обобщаване на текста',
    'cs': 'Shrnutí textu',
    'da': 'Sammenfatning af teksten',
    'de': 'Fassen Sie den Text zusammen',
    'el': 'Συνοψίστε το κείμενο',
    'es': 'Resumir el texto',
    'et': 'Võtke tekst kokku',
    'fi': 'Tiivistä teksti',
    'fr': 'Résumez le texte',
    'hu': 'A szöveg összefoglalása',
    'nn': 'Oppsummer teksten',
    'it': 'Riassumere il testo',
    'ja': '本文を要約する',
    'ko': '텍스트 요약',
    'lt': 'Apibendrinti tekstą',
    'lv': 'Apkopojiet tekstu',
    'nl': 'De tekst samenvatten',
    'pl': 'Podsumuj tekst',
    'pt': 'Resumir o texto',
    'ro': 'Rezumați textul',
    'ru': 'Резюмируйте текст',
    'sk': 'Zhrňte text',
    'sl': 'Povzemanje besedila',
    'sv': 'Sammanfattning av texten',
    'tr': 'Metni özetleyin',
    'uk': 'Підсумуйте текст',
    'zh': '归纳文本'}


# In[5]:





# In[15]:


def summarize_with_gpt(text, model_name=GPT_MODEL_NAME):
    assert text
    assert isinstance(text, str)

    try:
        lang = Detector(text).language.code
    except UnknownLanguage as ex:
        print(ex)
        lang = 'en'

    resp = openai.ChatCompletion.create(
      model=model_name,
      messages=[
            {"role": "system", "content": ""},
            {"role": "user", "content": f"{text}\n\n{PROMPT_SUMMARY.get(lang, 'en')}"}
      ]
    )
    return resp['choices'][0]['message']['content']


async def asummarize_with_gpt(text, model_name=GPT_MODEL_NAME):
    assert text
    assert isinstance(text, str)

    try:
        lang = Detector(text).language.code
    except UnknownLanguage as ex:
        print(ex)
        lang = 'en'

    resp = await openai.ChatCompletion.acreate(
      model=model_name,
      messages=[
            {"role": "system", "content": ""},
            {"role": "user", "content": f"{text}\n\n{PROMPT_SUMMARY.get(lang, 'en')}"}
      ]
    )
    return resp['choices'][0]['message']['content']


async def asummarize_with_chatgpt(text, model_name=GPT_MODEL_NAME):
    assert text
    assert isinstance(text, str)

    try:
        lang = Detector(text).language.code
    except UnknownLanguage as ex:
        print(ex)
        lang = 'en'

    resp = await acreate_chatcompletion(
      messages=[
            {"role": "system", "content": ""},
            {"role": "user", "content": f"{text}\n\n{PROMPT_SUMMARY.get(lang, 'en')}"}
      ]
    )
    return resp['choices'][0]['message']['content'], resp['usage']['total_tokens']


# In[16]:


def summarize_by_chunk(text, chunk_size_in_tokens=2000, max_workers=5):
    chunks = list(chunk_a_text(text, chunk_size_in_tokens))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        sums = executor.map(summarize_with_gpt, chunks)
        return sums


# In[17]:


async def asummarize_by_chunk(text, chunk_size_in_tokens=2000):
    chunks = list(chunk_a_text(text, chunk_size_in_tokens))

    tasks = []
    for c in chunks:
        tasks.append(asyncio.create_task(asummarize_with_chatgpt(c)))

    result = await asyncio.gather(*tasks)
    sums, toks = zip(*result)
    return '\n'.join(s.strip() for s in sums), sum(toks)


# In[18]:


async def recursive_summarize_with_gpt(text, tries=0, chunk_size_in_tokens=None):
    if tries > 5:
        raise RuntimeError("Summarization error", f"Too many attempts. Are you trying to reduce irredubable piece of text? {text=}")
    if chunk_size_in_tokens is None:
        chunk_size_in_tokens = GPT_MODEL_MAX_TOKENS - 256 - 10
    sums = []
    for text in chunk_a_text(text, chunk_size_in_tokens):
        sums.append(await asummarize_with_gpt(text))
    if len(sums) == 1:
        return sums[0]
    else:
        print(sums)
        return await summarize_by_chunk('\n'.join(sums),
                                                  tries=tries+1,
                                                  chunk_size_in_tokens=chunk_size_in_tokens)


# In[19]:


# if __name__ == '__main__':
#     from crabnlp.youtube import adownload_captions
#     caps = await adownload_captions("DwhoDLW2dTM")
#     text = ' '.join(w['text'] for w in caps)
#     s, toks = await asummarize_by_chunk(text, chunk_size_in_tokens=3000)
#     print(toks, s)


# In[ ]:




