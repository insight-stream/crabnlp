#!/usr/bin/env python
# coding: utf-8

# In[1]:


import asyncio
import os
from typing import List
from functools import partial

import openai

from crabnlp.youtube import adownload_captions_and_meta
from crabnlp.llms import chunk_a_text, chunk_texts, acreate_chatcompletion, tlen, GPT_MAX_CONTEXT_LEN
from crabnlp.llms import map_chatgpt, map_chatgpt_recursive


# In[2]:


def gather_information(question, text, context, source_type):
    return [
             {"role": "system", "content": context},
             {"role": "system", "content": f"Excerpt from the {source_type}\n\n{text}"},
             {"role": "user", "content": f"{question}"}
           ]


# In[3]:


def combine_and_answer(question, text, context):
    return [
             {"role": "system",
              "content": f"{context}. Given that:\n{text}"},
             {"role": "user",
              "content": f"{question}"}
           ]


# In[8]:


async def answer(question, text, context=None, source_type="text", verbose=False):
    if not context:
        context = "You are a helpfull assistant."
    gi = lambda t: gather_information(question, t, context, source_type=source_type)
    results, toks1 = await map_chatgpt(gi, text)
    if verbose:
        print(f"{results=}")
    ca = lambda t: combine_and_answer(question, t, context)
    answer, toks2 = await map_chatgpt_recursive(ca, results)
    return '\n'.join(answer).strip(), toks1 + toks2


# In[9]:


async def answer_on_video(question, text, title, verbose=False):
    context = f'You are answering questions on a video called "{title}"'
    return await answer(question, text, context=context, source_type="video", verbose=verbose)


# In[10]:


async def talk_to_llm(question, verbose=False):
    resp = await acreate_chatcompletion(
      messages=[
            {"role": "user", "content": f"{question}"}
      ]
    )
    return resp['choices'][0]['message']['content']


# In[ ]:





# # Videos being tested on
# ### Mdge9Yk7KTM
# A long president speech and question 'Что президент говорит о случаях братания?' have no answer in the speech. Answer should be very small
# 
# ### VROKh092UYc 
# A 3 hour long video gives physiological information about bith process. Question 'Напиши список вещей  которые нужно купить для ребёнка на первое время. В порядке их важности. Обязательно добавь в список градусник и обсуди их типы и какой лучше всего. Список остальных вещей тоже должен быть максимально конкретный.' is tricky because the video doesn't have answer to the video, but ChatGPT is trying to answer. Perhaps adding sources could help.

# In[118]:




