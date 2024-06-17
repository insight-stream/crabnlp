import asyncio
import json
import os
import sys
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Union

import aiohttp
import openai
from bs4 import BeautifulSoup

openai.api_key = os.getenv("OPENAI_KEY")
google_key = os.getenv("GOOGLE_KEY")


async def _search_knowledge(query: str) -> Optional[str]:
	try:
		query_encoded = urllib.parse.quote(query)
		url = "https://www.google.com/search?q=" + query_encoded
		request = urllib.request.Request(url)
		request.add_header(
			"User-Agent",
			"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36",
		)
		raw_response = urllib.request.urlopen(request).read()
		html = raw_response.decode("utf-8")
		soup = BeautifulSoup(html, "lxml")

		if soup.find("div", class_="LGOjhe"):
			return (
				soup.find("div", class_="LGOjhe")
				.find("span", class_="hgKElc")
				.text
			)
	except Exception as e:
		print(f"Could not find knowledge graph in the response {str(e)}", file=sys.stderr)
		return None


async def _search(query: str, count: int):
	async with aiohttp.ClientSession() as session:
		async with session.get(
			f"https://customsearch.googleapis.com/customsearch/v1?cr=ru&num={count}&cx=b0c159ac37f4a413c&q={query}&key={google_key}",
			timeout=5,
			headers={"Accept": "application/json"},
		) as response:
			json = await response.json()
			for item in json["items"]:
				yield item["snippet"]

async def _google(query: str) -> Optional[str]:
	try:
		knowledge_graph = await _search_knowledge(query)
		if knowledge_graph:
			return knowledge_graph
		
		res = []
		async for a in _search(query, 2):
			res.append(a)
		return '\n\n'.join(res)
	except Exception as e:
		print(f"Could not search {str(e)}", file=sys.stderr)
		return None
	
async def search_batch(csv: str) -> List[Dict[str, str]]:
	results = { q.strip(): await _google(q.strip()) for q in csv.replace('"', '').split("\n") if q.strip() != '' }
	return [
		{ 'question': key, 'answer': value } for key, value in results.items()
		if value is not None
	]