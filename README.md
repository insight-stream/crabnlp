# crabnlp
Library for spech2text, diarization and summarization meetings.
### Install
```
cd crabnlp
pip install -e crabnlp
```

### Example using transcribe
```
from crabnlp.transcribe import transcribe

transcription_result = transcribe('path/to/file')
```
Result:
('text', None)
