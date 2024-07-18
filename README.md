<h1 align="center">Crabnlp Speaker Diarization Using OpenAI Whisper</h1>
<p align="center">
  <a href="https://github.com/insight-stream/crabnlp/stargazers">
    <img src="https://img.shields.io/github/stars/insight-stream/crabnlp.svg?colorA=orange&colorB=orange&logo=github"
         alt="GitHub stars">
  </a>
  <a href="https://github.com/insight-stream/crabnlp/issues">
        <img src="https://img.shields.io/github/issues/insight-stream/crabnlp.svg"
             alt="GitHub issues">
  </a>
  <a href="https://github.com/insight-stream/crabnlp/blob/master/LICENSE">
        <img src="https://img.shields.io/github/license/insight-stream/crabnlp.svg"
             alt="GitHub license">
  </a>
  </a>
  <a href="https://colab.research.google.com/github/insight-stream/crabnlp/blob/main/Whisper_Transcription_%2B_NeMo_Diarization.ipynb">
  <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open in Colab">
  </a>
 
</p>


# 
Crabnlp Transcription based on OpenAI Whisper and Custom Speaker Diarization 

<img src="https://github.blog/wp-content/uploads/2020/09/github-stars-logo_Color.png" alt="drawing" width="25"/> **Please, star the project on github (see top-right corner) if you appreciate my contribution to the community!**

## What is it
 
Crabnlp is a transcription and speaker diarization pipeline based on OpenAI Whisper and custom speaker diarization.

## Installation
Install the requirements
```
cd crabnlp
pip install -e crabnlp
```

### Example using transcribe
```
from crabnlp.transcribe import transcribe

transcription_result = transcribe('path/to/file')
```


## Known Limitations
- The system may not perform well in scenarios with overlapping speech or rapid speech.
- The system may not accurately identify speakers in scenarios with
- There might be some errors, please raise an issue if you encounter any.

## Future Improvements
- Improvement the quality of sound recognition

## Acknowledgements
This work is based on [OpenAI's Whisper](https://github.com/openai/whisper) , [Faster Whisper](https://github.com/guillaumekln/faster-whisper) , [Nvidia NeMo](https://github.com/NVIDIA/NeMo) , and [Facebook's Demucs](https://github.com/facebookresearch/demucs)