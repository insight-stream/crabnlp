import os

import openai
openai.api_key = os.environ['OPENAI']


def transcribe(filepath):
	if os.stat(filepath).st_size > 25000000:
		raise Exception(f'File too big: {filepath} for transcription')
	MODEL_NAME = 'whisper-1'
	with open(filepath, 'rb') as f:
		transcript = openai.Audio.transcribe(MODEL_NAME, f, response_format='verbose_json')
	return transcript['text'], None