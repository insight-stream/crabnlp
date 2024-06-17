#!/usr/bin/env python
# coding: utf-8

# In[3]:


import logging
from datetime import datetime

from pythonjsonlogger import jsonlogger


# In[4]:


class JsonFormatterWithTime(jsonlogger.JsonFormatter):
    def __init__(self) -> None:
        super().__init__('%(timestamp)s %(level)s %(name)s %(message)s', json_ensure_ascii=False)

    def add_fields(self, log_record, record, message_dict):
        super(JsonFormatterWithTime, self).add_fields(log_record, record, message_dict)
        if log_record.get('timestamp') == None:
            now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            log_record['timestamp'] = now
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname


# In[5]:


def get_json_logger(log_path, name='json_loader'):
    """Returns a logger that logs JSON objects to a file."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(JsonFormatterWithTime())
    logger.addHandler(file_handler)
    return logger


# In[6]:


def is_notebook() -> bool:
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True   # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False      # Probably standard Python interpreter


# In[1]:


def pretty_time(seconds_from_beginning):
    h = seconds_from_beginning // 3600
    m = (seconds_from_beginning % 3600) // 60
    s = int(seconds_from_beginning % 60)

    if h > 0:
        return f"{h:n}:{m:02n}:{s:02n}"
    else:
        return f"{m:n}:{s:02n}"


assert pretty_time(0.0) == '0:00'
assert pretty_time(60.0) == '1:00'
assert pretty_time(121.0) == '2:01'
assert pretty_time(777) == '12:57'
assert pretty_time(4000) == '1:06:40'


# In[2]:


def kk(dictionary: dict, space_sep_keywords, default=None):
    x = dict(dictionary)
    for kwd in space_sep_keywords.split():
        if not isinstance(x, dict):
            return default
        x = x.get(kwd)
        if x is None:
            return default
    return x


assert kk({'update': {'message': {'text': '123'}}}, 'update message text') == '123'
assert kk({'update': {'message': {'text': '123'}}}, 'update message from id') is None
assert kk({'update': {'message': {'text': '123'}}}, 'update message from id', 'UNKNOWN') == 'UNKNOWN'
assert kk({'update': ''}, 'update message', 'UNKNOWN') == 'UNKNOWN'

