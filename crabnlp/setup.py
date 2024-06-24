from setuptools import setup

setup(
    name='crabnlp',
    version='1.0.0',
    description='NLP routines',
    packages=['crabnlp'],
    install_requires=[
        'openai',
        'pytube',
        'transformers',
        'PyICU',
        'pycld2',
        'polyglot',
        'tiktoken',
        'python-json-logger',
        'iso-639',
        'faster_whisper==0.5.0',
        'pyannote.audio==2.1.1'
    ],
)
