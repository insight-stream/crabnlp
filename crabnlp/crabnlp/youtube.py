#!/usr/bin/env python
# coding: utf-8

import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import urlparse, parse_qs
from http.client import IncompleteRead
from time import sleep
import aiohttp
import re
import json
from typing import Generator, List, Tuple
from html.parser import HTMLParser

from pytube import YouTube

from crabnlp.billing import split_by_pages


## The most effective language according to GPT-3.5-turbo byte encoding
_LANG_PRIORITY = tuple('en fr da sv no nl id pt pt-BR pt-PT de et it es sl ro fi lv lt tr sk pl cs zh zh-CN zh-TW ja hu ko bg ru uk el'.split())


def get_yt_id_from_url(url):
    parsed_url = urlparse(url)
    if 'v' in parse_qs(parsed_url.query):
        return parse_qs(parsed_url.query)['v'][0]
    else:
        return parsed_url.path.rsplit('/', 1)[-1]


assert get_yt_id_from_url("https://youtu.be/K4xqY-3ODKY") == "K4xqY-3ODKY"
assert get_yt_id_from_url("https://www.youtube.com/watch?v=K4xqY-3ODKY") == "K4xqY-3ODKY"
assert get_yt_id_from_url("https://youtu.be/lmtGYIqWPcg?feature=share") == "lmtGYIqWPcg"


def is_youtube(url: str) -> bool:
    parsed_url = urlparse(url)
    return parsed_url.netloc in {"youtu.be", "youtube.com", "m.youtube.com", "www.youtube.com"}


assert is_youtube("https://youtu.be/K4xqY-3ODKY")
assert not is_youtube("https://arxiv.org/abs/1811.00146")
assert is_youtube('https://www.youtube.com/watch?v=qnav9vgHDHs')


def get_youtube_meta(y: YouTube):
    info = {k: getattr(y, k) for k in [
        'author',
        'description',
        'title',
        'channel_id',
        'keywords',
        'length',
        'views']}
    info['publish_date'] = y.publish_date.date().isoformat()
    return info


def choose_caption(captions):
    assert captions
    if len(captions) == 1:
        return next(iter(captions))
    return sorted(captions, key=lambda c: len(c))[0]


assert choose_caption({"en": None}) == 'en'
assert choose_caption({'en', 'en.uYU-mmqFLq8','en.JkeT_87f4cc'}) == 'en'


def simplify_youtube_url(url):
    """For some reasons urls in youtu.be doesn't allow downloading captions"""
    p = urlparse(url)
    if p.netloc in {'youtu.be'}:
        vid = get_yt_id_from_url(url)
        return f"https://www.youtube.com/watch?v={vid}"
    return url


assert simplify_youtube_url("https://youtu.be/K4xqY-3ODKY") == "https://www.youtube.com/watch?v=K4xqY-3ODKY"
assert simplify_youtube_url("https://www.youtube.com/watch?v=K4xqY-3ODKY") == "https://www.youtube.com/watch?v=K4xqY-3ODKY"
assert simplify_youtube_url("https://youtu.be/lmtGYIqWPcg?feature=share") == 'https://www.youtube.com/watch?v=lmtGYIqWPcg'


def download_captions_and_meta(url):
    url = simplify_youtube_url(url)

    for _ in range(4):
        try:
            yt = YouTube(url)
            cnames = yt.captions.lang_code_index
            break
        except IncompleteRead:
            sleep(1)
            continue
    if not cnames:
        raise RuntimeError("No captions", f"No captions available for the video in {url}. If you really need summary for the video let us know in https://t.me/transcraber_community")

    cname = choose_caption(cnames)
    tree = ET.fromstring(yt.captions[cname].xml_captions)
    ws = []
    current_p_time = 0
    for elem in tree.iter():
        if elem.tag not in 'sp':
            continue
        if elem.tag == 'p':
            current_p_time = int(elem.attrib.get('t', '0'))

        if elem.tag in 'sp' and isinstance(elem.text, str):
            t = elem.text.strip()
            ws.append({'t': t,
                       's': (int(elem.attrib.get('t', '0')) + current_p_time) / 1000})
    r = get_youtube_meta(yt)
    r['captions'] = ws
    r['captions_track'] = cname
    return r

# caps = download_captions_and_meta("https://www.youtube.com/watch?v=Npe-oRYOwAw")
# caps = download_captions_and_meta("https://www.youtube.com/watch?v=__RAXBLt1iM")  ## TODO: text withing <p> has newlines that should be deleted
# caps = download_captions_and_meta("https://www.youtube.com/watch?v=otbnC2zE2rw")


async def adownload_captions(video_id: str):
    url = f'https://www.youtube.com/watch?v={video_id}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f'Error {response.status} fetching {url}: {await response.text()}')

            page = await response.text()
            pattern = r'[uU]rl":"(https://www.youtube.com/api/timedtext.*?)"'
            match = re.search(pattern, page)
            if not match:
                return
            subtitle_url = match.group(1).replace('\\u0026', '&')
        async with session.get(subtitle_url) as response:
            if response.status != 200:
                raise RuntimeError(f'Error {response.status} fetching {subtitle_url}: {await response.text()}')
            subs = await response.text()

    tree = ET.fromstring(subs)
    ws = []
    for elem in tree.iter():
        if elem.tag != 'text':
            continue
        t = elem.text
        if t:
            ws.append({'t': unescape(t.strip()),
                       's': float(elem.attrib.get('start')),
                       'd': float(elem.attrib.get('dur'))})
    return ws


IGNORE_TAGS = {'link', 'meta', 'input'}


class _YouTubeDetailsHtmlParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside_tags = []
        self.result = None

    def handle_starttag(self, tag, attrs):
        if tag in IGNORE_TAGS:
            return
        self.inside_tags.append(tag)

    def handle_endtag(self, tag):
        if tag in IGNORE_TAGS:
            return
        assert self.inside_tags[-1] == tag, f"Error closing {tag} when {self.inside_tags=}"
        self.inside_tags.pop()

    def handle_data(self, data):
        pattern = r'[uU]rl":"(https://www.youtube.com/api/timedtext.*?)"'
        match = re.search(pattern, data)
        if match:
            self.result = data


def _extract_details(page):
    parser = _YouTubeDetailsHtmlParser()
    parser.feed(re.sub(r"^<\![^>]+>", '', page))

    code = parser.result
    s = code.find('{')
    e = code.rfind('}')
    data = json.loads(code[s:e+1])

    meta = {
        'captionTracks': data['captions']['playerCaptionsTracklistRenderer']['captionTracks']
    }

    if m := data.get('microformat', {}).get('playerMicroformatRenderer'):
        meta['title'] = m.get('title', {}).get('simpleText')
        meta['description'] = m.get('description', {}).get('simpleText')
        for k in ['lengthSeconds',
                    'ownerProfileUrl',
                    'externalChannelId',
                    'isFamilySafe',
                    'isUnlisted',
                    'hasYpcMetadata',
                    'viewCount',
                    'category',
                    'publishDate',
                    'ownerChannelName',
                    'uploadDate']:
            if k in m:
                meta[k] = m.get(k)
        meta['author_name'] = meta.get('ownerChannelName')

    return meta


async def adownload_meta(vid: str):
    url = f'https://www.youtube.com/watch?v={vid}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f'Error {response.status} fetching {url}: {await response.text()}')
            page = await response.text()
    return _extract_details(page)


def _select_track(tracks):
    tracks = [ct for ct in tracks if 'baseUrl' in ct]
    if len(tracks) > 1:
        auto = [t for t in tracks if t.get('vssId', '').startswith('a.')]
        if len(auto) == 1:
            lang = auto[0].get('languageCode')
            priority = (lang,) + _LANG_PRIORITY
        else:
            priority = _LANG_PRIORITY

        def p(track):
            try:
                r = priority.index(track.get('languageCode'))
                if track.get('vssId').startswith('a.'):
                    r += 0.5
                return r
            except ValueError:
                return 999
        return min(tracks, key=p)
    elif len(tracks) == 1:
        return tracks[0]


assert _select_track([]) is None
assert _select_track([{'baseUrl': '', 'vssId': '.en', 'languageCode': 'en'}])['languageCode'] == 'en'
assert _select_track([{'baseUrl': '', 'vssId': '.en', 'languageCode': 'en'},
                      {'baseUrl': '', 'vssId': 'a.sl', 'languageCode': 'sl'},
                      {'baseUrl': '', 'vssId': '.sl', 'languageCode': 'sl'}])['vssId'] == '.sl'


async def adownload_captions_and_meta(vid: str) -> dict:
    meta = await adownload_meta(vid)
    track = _select_track(meta['captionTracks'])
    if track is not None and (base_url := track.get('baseUrl')):
        async with aiohttp.ClientSession() as session:
            async with session.get(base_url) as response:
                if response.status != 200:
                    raise RuntimeError(f'Error {response.status} fetching {base_url}: {await response.text()}')
                subs = await response.text()

        tree = ET.fromstring(subs)
        ws = []
        for elem in tree.iter():
            if elem.tag != 'text':
                continue
            t = elem.text
            if t:
                ws.append({'t': unescape(t.strip()),
                        's': float(elem.attrib.get('start')),
                        'd': float(elem.attrib.get('dur'))})
        meta['captions'] = ws
    return meta


def extract_youtube_subtitels_and_refs_pages(captions: List[Tuple[str, int]]) -> Generator[Tuple[str, List[int]], None, None]:
    for captions_batch in split_by_pages(captions):
        batch = []
        acc = ''
        start = None

        for caption in captions_batch:
            if start is None:
                start = caption['s']

            txt = caption['t'].strip()
            if len(txt) == 0:
                continue

            if len(acc) == 0:
                acc += txt
            elif txt[0].isupper() or len(acc) > 128:
                batch.append((acc, start))
                acc = txt
                start = caption['s']
            else:
                acc += ' ' + txt
        batch.append((acc.strip(), start))

        txts, times = zip(*batch)
        txt = ' '.join([f'{t} ({i})' for i, t in enumerate(txts)])

        yield txt, times

