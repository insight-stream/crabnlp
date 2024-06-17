import torch
from typing import Iterable, List, Tuple
from faster_whisper import WhisperModel
from pyannote.audio import Model
from einops import rearrange, repeat


segmentation_model = Model.from_pretrained("models/segmentation.pyannotate/pytorch_model.bin")
embedding_model = Model.from_pretrained("models/embedding.pyannotate/pytorch_model.bin")
transcriber_model = WhisperModel('models/whisper-medium-ct2', device='cpu', compute_type='int8')

SAMPLE_RATE = 16000
N_FFT = 400
N_MELS = 80
HOP_LENGTH = 160
CHUNK_LENGTH = 30
N_SAMPLES = CHUNK_LENGTH * SAMPLE_RATE  # 480000 samples in a 30-second chunk
N_FRAMES = N_SAMPLES // HOP_LENGTH  # 3000 frames in a mel spectrogram input
assert N_SAMPLES % HOP_LENGTH == 0
N_SAMPLES_PER_TOKEN = HOP_LENGTH * 2  # the initial convolutions has stride 2
FRAMES_PER_SECOND = SAMPLE_RATE // HOP_LENGTH  # 10ms per audio frame
assert SAMPLE_RATE % HOP_LENGTH == 0
TOKENS_PER_SECOND = SAMPLE_RATE // N_SAMPLES_PER_TOKEN  # 20ms per audio token
assert SAMPLE_RATE % N_SAMPLES_PER_TOKEN == 0


def _merge_pauses(time_ranges: List[Tuple[int, int]], speakers: List[int]) -> Tuple[List[Tuple[int, int]], List[int]]:
	_segments = []
	_speakers = []

	for (start, end), speaker in zip(time_ranges, speakers):
		prev_speaker = _speakers[-1] if len(_speakers) > 0 else None

		if speaker == prev_speaker:
			start_prev, _ = _segments.pop()
			_segments.append((start_prev, end))
		elif ((end - start < 3 * SAMPLE_RATE) and speaker == -1) or (end - start < 1 * SAMPLE_RATE):
			if len(_segments) > 0:
				start_prev, end = _segments.pop()
				_segments.append((start_prev, end))
		else:
			_segments.append((start, end))
			_speakers.append(speaker)

	return _segments, _speakers


def _diarize_speakers(pcm_sound: torch.Tensor, speaker_indexes: torch.Tensor) -> Iterable[Tuple[torch.Tensor, Tuple[int, int], int]]:
	assert pcm_sound.shape[1] == 1, 'for diarization should be only 1 channel presents'
	pcm_sound = pcm_sound.squeeze()
	assert len(pcm_sound) == len(speaker_indexes), "Input tensors must be the same length"
	
	# Get the indices where the speaker changes
	change_indices = torch.where(speaker_indexes[:-1] != speaker_indexes[1:])[0]
	change_indices = torch.cat((torch.tensor([0]), change_indices + 1, torch.tensor([len(pcm_sound)])))

	time_ranges = [(change_indices[i].item(), change_indices[i+1].item()) for i in range(len(change_indices)-1)]
	speakers = [ speaker_indexes[start].item() for start, _ in time_ranges]
	time_ranges, speakers = _merge_pauses(time_ranges, speakers)

	# Split pcm_sound into segments based on change_indices
	segments = [pcm_sound[start:end] for start, end in time_ranges]
	
	return zip(segments, [ (start // SAMPLE_RATE, end // SAMPLE_RATE) for start, end in time_ranges], speakers)

def _transcribe_pcm(pcm: torch.Tensor, prev_text: str) -> str:
	segment = (pcm.to(torch.float32) / 32768.0).numpy()
	segments, _ = transcriber_model.transcribe(segment, language='ru', temperature=0, condition_on_previous_text=True, initial_prompt=prev_text)
	return ' '.join([ segment.text for segment in segments ])

def _nearest(vector: torch.Tensor, db_matrix: torch.Tensor) -> int:
    return torch.argmin(torch.norm(db_matrix - vector.unsqueeze(0), dim=1)).item()

#def _nearest(vector: torch.Tensor, db_matrix: torch.Tensor) -> Tuple[int, torch.Tensor]:
#    nearest_idx = torch.argmin(torch.norm(db_matrix - vector.unsqueeze(0), dim=1)).item()
#    db_matrix[nearest_idx] = (vector + db_matrix[nearest_idx]) / 2
#    return nearest_idx, db_matrix

def _speakers_num(pcm: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
	samples_num, channels = pcm.shape
	with torch.no_grad():
		wave = rearrange(pcm, "sample channel -> 1 channel sample").to(dtype=torch.float32)
		segmentations = segmentation_model(wave)  # shape (batch, frames, speakers)

		batch_size, _, num_speakers = segmentations.shape
		inputs = wave.repeat(1, num_speakers, 1)
		weights = rearrange(segmentations, "batch frame spk -> (batch spk) frame")
		inputs = rearrange(inputs, "batch spk sample -> (batch spk) 1 sample")

		speaker_embeddings = rearrange(
			embedding_model(inputs, weights),
			"(batch spk) feat -> batch spk feat",
			batch=batch_size,
			spk=num_speakers
		) # shape (batch, speakers, emb_dim)

		seg_resolution = SAMPLE_RATE * segmentation_model.introspection.frames.step
		assert seg_resolution.is_integer()
		segmentations = repeat(segmentations, 
			"batch frame speaker -> batch (frame samples_in_window) speaker", 
			samples_in_window=int(seg_resolution)
		)
		nva_segments = (segmentations < 0.5).all(dim=2)
		current_speaker = segmentations.argmax(dim=2)
		current_speaker[nva_segments] = -1

		pad_left_val = samples_num - current_speaker.shape[-1]
		current_speaker = torch.nn.functional.pad(current_speaker, (pad_left_val, 0, 0, 0), 'constant', -1)
		current_speaker = current_speaker.squeeze()
		assert batch_size == 1

		assert speaker_embeddings.shape[0] == 1
		speaker_embeddings = speaker_embeddings.squeeze()

		return current_speaker, speaker_embeddings


def transcriber():
	prev_text = {}
	num_chunk = 0
	prev_speaker = None
	speakers_db = None

	async def inner(segment_psm_s: torch.Tensor) -> str:
		nonlocal prev_text, num_chunk, prev_speaker, speakers_db
		results = []

		speaker_ids, speaker_embeddings = _speakers_num(segment_psm_s)
		#if speakers_db == None:
		speakers_db = speaker_embeddings
		#else:
		#	pass

		for wave_seg, (start, end), speaker_num in _diarize_speakers(segment_psm_s, speaker_ids):
			segment = wave_seg.squeeze()
			speaker_name = 'Спикер ' + str(_nearest(speaker_embeddings[speaker_num], speakers_db))
			
			text = _transcribe_pcm(segment, prev_text.get(speaker_name))

			if speaker_name:
				if speaker_name != prev_speaker and prev_speaker == None:
					results.append(f'[{num_chunk * CHUNK_LENGTH + start}:{num_chunk * CHUNK_LENGTH + end}] {speaker_name}: {text}')
				elif speaker_name != prev_speaker and prev_speaker:
					results.append(f'\n[{num_chunk * CHUNK_LENGTH + start}:{num_chunk * CHUNK_LENGTH + end}] {speaker_name}: {text}')
				else:
					results.append(text)
				prev_text[speaker_name] = prev_text.get(speaker_name, '') + text
				prev_speaker = speaker_name
			else:
				results.append('\n')

		num_chunk += 1
		return ' '.join(results)

	return  inner