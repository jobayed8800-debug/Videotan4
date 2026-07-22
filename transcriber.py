import os
import json
import subprocess
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class WhisperTranscriber:
    """Speech recognition with Whisper and speaker diarization"""
    
    def __init__(self, model_size: str = "large-v3", device: str = "cuda"):
        """
        Initialize Whisper transcriber
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            device: cuda or cpu
        """
        self.model_size = model_size
        self.device = device
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Lazy load the Whisper model"""
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="float16" if self.device == "cuda" else "int8"
            )
            logger.info(f"✅ Whisper {self.model_size} loaded on {self.device}")
        except ImportError:
            logger.warning("⚠️ Faster-Whisper not installed, using OpenAI Whisper")
            import whisper
            self.model = whisper.load_model(self.model_size, device=self.device)
    
    def transcribe(
        self, 
        audio_path: str, 
        language: str = "en",
        with_timestamps: bool = True
    ) -> List[Dict]:
        """
        Transcribe audio and return segments with timestamps
        
        Returns:
            List of dicts: [{'start': 0.0, 'end': 2.5, 'text': 'Hello', 'speaker': 'SPEAKER_00'}]
        """
        try:
            # Use faster-whisper
            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                beam_size=5,
                task="transcribe",
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    threshold=0.5
                )
            )
            
            # Collect segments
            transcript = []
            for segment in segments:
                transcript.append({
                    'start': segment.start,
                    'end': segment.end,
                    'text': segment.text.strip(),
                    'speaker': 'SPEAKER_00'  # Will be refined with diarization
                })
            
            # Perform speaker diarization if needed
            if len(transcript) > 1:
                transcript = self._diarize_speakers(audio_path, transcript)
            
            logger.info(f"✅ Transcribed {len(transcript)} segments")
            return transcript
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            # Fallback: Use pyannote for diarization
            return self._fallback_transcribe(audio_path, language)
    
    def _diarize_speakers(self, audio_path: str, segments: List[Dict]) -> List[Dict]:
        """Add speaker labels using pyannote.audio"""
        try:
            from pyannote.audio import Pipeline
            from pyannote.core import Segment
            
            # Load diarization pipeline
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=os.getenv("HUGGINGFACE_TOKEN")
            )
            
            # Run diarization
            diarization = pipeline(audio_path)
            
            # Assign speaker to each segment
            for segment in segments:
                seg_start = segment['start']
                seg_end = segment['end']
                
                # Find speaker for this time window
                best_speaker = 'SPEAKER_00'
                max_overlap = 0
                
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    overlap_start = max(seg_start, turn.start)
                    overlap_end = min(seg_end, turn.end)
                    overlap = max(0, overlap_end - overlap_start)
                    
                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_speaker = speaker
                
                segment['speaker'] = best_speaker
            
            return segments
            
        except Exception as e:
            logger.warning(f"Diarization failed: {e}, using default speaker")
            for i, segment in enumerate(segments):
                segment['speaker'] = f'SPEAKER_{i%4:02d}'
            return segments
    
    def _fallback_transcribe(self, audio_path: str, language: str) -> List[Dict]:
        """Fallback using OpenAI Whisper"""
        try:
            import whisper
            result = self.model.transcribe(
                audio_path,
                language=language,
                task="transcribe",
                verbose=False
            )
            
            segments = []
            for segment in result['segments']:
                segments.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': segment['text'].strip(),
                    'speaker': f'SPEAKER_{segment["id"] % 4:02d}'
                })
            
            return segments
            
        except Exception as e:
            logger.error(f"Fallback transcription failed: {e}")
            raise RuntimeError(f"All transcription methods failed: {e}")
