#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
import functools
from time import monotonic
import asyncio
from typing import Optional, List, Callable

import tiktoken
import openai
from openai.error import RateLimitError


# In[2]:


GPT_MODEL_NAME = "gpt-3.5-turbo"
GPT_MAX_CONTEXT_LEN = 4096
tok = tiktoken.encoding_for_model(GPT_MODEL_NAME)
openai.api_key = os.environ['OPENAI']


# In[3]:


def tlen(text: str) -> int:
    return len(tok.encode(text))


# In[4]:


def calc_overhead(messages):
    return int(tlen(repr(messages)) * 1.1)


# In[5]:


def chunk_a_text(text: str, max_tokens: int, overlapping: Optional[int | float] = None):
    if overlapping is None:
        overlapping = int(max_tokens/10)
    elif isinstance(overlapping, float):
        overlapping = int(max_tokens * overlapping)
    t = tok.encode(text)
    for i in range(0, len(t), max_tokens-overlapping):
        yield tok.decode(t[i:(i+max_tokens)]).strip()


assert list(chunk_a_text("1 2 3 4 5 6 7 8 9 10", 8, 4)) == \
        ['1 2 3 4', '3 4 5 6', '5 6 7 8', '7 8 9 10', '9 10']


def chunk_texts(lines: List[str], max_tokens=GPT_MAX_CONTEXT_LEN-256, join_lines_char=''):
    """Chunk a list of lines, try minimazing spliting a line 
    (for instance, every line is a sentence)"""
    if not lines:
        return
    for i in range(len(lines), 1, -1):
        if tlen(join_lines_char.join(lines[:i])) <= max_tokens:
            yield join_lines_char.join(lines[:i])
            yield from chunk_texts(lines[max(i, 0):], max_tokens=max_tokens, join_lines_char=join_lines_char)
            break
    else:
        yield from chunk_a_text(lines[0], max_tokens=max_tokens)
        yield from chunk_texts(lines[1:], max_tokens=max_tokens, join_lines_char=join_lines_char)


assert list(chunk_texts(['hello world!', 'one two three'], 2)) == ['hello world', '!', 'one two', 'three']
assert list(chunk_texts(['one two three', 'four five six', 'seven eight nine ten'], 6, join_lines_char=' ')) \
 == ['one two three four five six', 'seven eight nine ten']


# In[6]:


def backoff(*exceptions, max_wait_sec=60, start=1, base=1.5):
    if not exceptions:
        exceptions = [Exception]

    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            start_time = monotonic()
            i = 0
            while monotonic() - start_time < max_wait_sec + 0.1:
                try:
                    return await func(*args, **kwargs)
                except Exception as ex:
                    if not isinstance(ex, tuple(exceptions)):
                        raise ex
                    print(f'Backing off `{func.__name__}`')
                    wait_time = min(start*base**i, start_time + max_wait_sec - monotonic())
                    if wait_time < 0:
                        raise ex
                    await asyncio.sleep(wait_time)
                    i += 1
        return wrapped
    return wrapper


# In[7]:


@backoff(RateLimitError)
async def acreate_chatcompletion(messages, model_name=GPT_MODEL_NAME):
    return await openai.ChatCompletion.acreate(
      model=model_name,
      messages=messages
    )


# In[8]:


async def map_chatgpt(messages_generator: Callable[[str], List], text: str | tuple | list,
                      answer_ratio=1/3, overlapping=0.1) -> tuple[List[str], int]:
    overhead = calc_overhead(messages_generator(''))

    chunk_size = int((GPT_MAX_CONTEXT_LEN-overhead)*(1-answer_ratio))
    if isinstance(text, str):
        chunking = chunk_a_text(text, chunk_size, overlapping=overlapping)
    else:
        chunking = chunk_texts(text, chunk_size)

    tasks = []
    for c in chunking:
        gi_messages = messages_generator(c)
        tasks.append(asyncio.create_task(acreate_chatcompletion(gi_messages)))
    resps = await asyncio.gather(*tasks)
    results, toks = zip(*[(r['choices'][0]['message']['content'], r['usage']['total_tokens']) for r in resps])
    return results, sum(toks)


async def map_chatgpt_recursive(messages_generator: Callable[[str], List], text: str | tuple | list,
                                answer_ratio=1/3, min_improvement=0.3,
                                tokens_already_used=0) -> tuple[List[str], int]:
    tok_before = tlen(text if isinstance(text, str) else ' '.join(text))
    results, tok_used = await map_chatgpt(messages_generator, text)
    tok_after = tlen(' '.join(results))
    if tok_after > (1-min_improvement)*tok_before:
        return results, tokens_already_used + tok_used
    else:
        return await map_chatgpt_recursive(messages_generator, results, answer_ratio=answer_ratio,
                                           min_improvement=min_improvement, 
                                           tokens_already_used=tokens_already_used + tok_used)
