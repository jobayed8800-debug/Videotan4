import os
import torch
import subprocess
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class VoiceCloner:
    """Voice cloning using XTTS-v2"""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize voice cloner
        
        Args:
            model_path: Path to XTTS model checkpoint
        """
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self._load_model()
    
    def _load_model(self):
        """Load XTTS-v2 model"""
        try:
            from TTS.api import TTS
            
            self.model = TTS(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                progress_bar=False
            )
            logger.info("✅ XTTS-v2 model loaded")
        except Exception as e:
            logger.warning(f"⚠️ XTTS-v2 load failed: {e}")
            # Fallback to Coqui TTS
            try:
                from TTS.tts.configs.xtts_config import XttsConfig
                from TTS.tts.models.xtts import Xtts
                
                config = XttsConfig()
                config.load_json("path/to/xtts/config.json")
                self.model = Xtts.init_from_config(config)
                self.model.load_checkpoint(config, checkpoint_dir="path/to/xtts/")
                self.model.cuda()
                
                logger.info("✅ XTTS-v2 (custom) loaded")
            except Exception as e2:
                logger.warning(f"⚠️ Custom XTTS load failed: {e2}")
                self.model = None
    
    def clone_speaker(
        self,
        text: str,
        reference_audio: str,
        language: str = "bn",
        output_path: Optional[str] = None
    ) -> str:
        """Clone voice for a single segment"""
        if output_path is None:
            output_dir = "cloned_audio"
            os.makedirs(output_dir, exist_ok=True)
            output_path = f"{output_dir}/clone_{hash(text)}_{hash(reference_audio)}.wav"
        
        if self.model is not None:
            try:
                # Use XTTS-v2
                self.model.tts_to_file(
                    text=text,
                    speaker_wav=reference_audio,
                    language=language,
                    file_path=output_path
                )
                return output_path
            except Exception as e:
                logger.error(f"XTTS cloning failed: {e}")
        
        # Fallback: Use espeak-ng with different voices
        return self._fallback_tts(text, language, output_path)
    
    def clone_multiple_speakers(
        self,
        segments: List[Dict],
        speaker_mapping: Dict[str, str],
        output_dir: str = "cloned_audio"
    ) -> Dict[str, str]:
        """Clone voices for multiple speakers in parallel"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Group by speaker
        speaker_segments = {}
        for segment in segments:
            speaker = segment.get('speaker', 'SPEAKER_00')
            if speaker not in speaker_segments:
                speaker_segments[speaker] = []
            speaker_segments[speaker].append(segment)
        
        # Clone for each speaker
        cloned_paths = {}
        for speaker, segs in speaker_segments.items():
            ref_audio = speaker_mapping.get(speaker)
            if not ref_audio:
                logger.warning(f"No reference audio for {speaker}")
                ref_audio = speaker_mapping.get('SPEAKER_00')
            
            if ref_audio:
                # Clone with reference
                for seg in segs:
                    text = seg['text']
                    key = f"{speaker}_{seg['start']}"
                    output_path = f"{output_dir}/{key}.wav"
                    self.clone_speaker(text, ref_audio, "bn", output_path)
                    if speaker not in cloned_paths:
                        cloned_paths[speaker] = []
                    cloned_paths[speaker].append(output_path)
            else:
                # Generate synthetic voice without reference
                for seg in segs:
                    output_path = f"{output_dir}/{speaker}_{seg['start']}.wav"
                    self._synthetic_voice(seg['text'], output_path)
                    if speaker not in cloned_paths:
                        cloned_paths[speaker] = []
                    cloned_paths[speaker].append(output_path)
        
        return cloned_paths
    
    def _fallback_tts(self, text: str, language: str, output_path: str) -> str:
        """Fallback TTS using gTTS or espeak"""
        try:
            # Try gTTS for Bangla
            from gtts import gTTS
            tts = gTTS(text=text, lang='bn')
            tts.save(output_path)
            return output_path
        except:
            # Use espeak-ng
            try:
                cmd = [
                    'espeak-ng',
                    '-v', 'bn',
                    '-w', output_path,
                    text
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                return output_path
            except:
                # Generate silent audio
                cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=16000:cl=mono', '-t', '1', output_path]
                subprocess.run(cmd, check=True, capture_output=True)
                return output_path
    
    def _synthetic_voice(self, text: str, output_path: str) -> str:
        """Generate synthetic voice without reference"""
        return self._fallback_tts(text, 'bn', output_path)
