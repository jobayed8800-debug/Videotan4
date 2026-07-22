import os
import subprocess
import json
import shutil
from typing import Optional, Dict, Callable
import logging
from datetime import datetime

from pipeline.audio_extractor import AudioExtractor
from pipeline.transcriber import WhisperTranscriber
from pipeline.translator import NLLBTranslator
from pipeline.voice_cloner import VoiceCloner
from pipeline.video_merger import VideoMerger

logger = logging.getLogger(__name__)


class BanglaVideoDubber:
    """Main pipeline orchestrator"""
    
    def __init__(self):
        self.audio_extractor = AudioExtractor()
        self.transcriber = WhisperTranscriber()
        self.translator = NLLBTranslator()
        self.voice_cloner = VoiceCloner()
        self.video_merger = VideoMerger()
    
    def process(
        self,
        video_path: str,
        source_lang: str = "en",
        target_lang: str = "bn",
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        Process video through the complete dubbing pipeline
        
        Args:
            video_path: Path to input video
            source_lang: Source language code (en, hi, ur, ar, zh, etc.)
            target_lang: Target language code (bn for Bangla)
            output_path: Output path for dubbed video
            progress_callback: Async callback for progress updates
            
        Returns:
            Path to dubbed video
        """
        if output_path is None:
            output_dir = "outputs"
            os.makedirs(output_dir, exist_ok=True)
            output_path = f"{output_dir}/dubbed_{int(datetime.now().timestamp())}.mp4"
        
        # Step 1: Extract Audio
        if progress_callback:
            progress_callback(10, "অডিও এক্সট্র্যাক্ট করা হচ্ছে")
        
        audio_path = self.audio_extractor.extract(video_path)
        logger.info(f"✅ Audio extracted: {audio_path}")
        
        # Step 2: Transcribe with timestamp
        if progress_callback:
            progress_callback(25, "ট্রান্সক্রিপশন চলছে")
        
        transcript_segments = self.transcriber.transcribe(audio_path, source_lang)
        logger.info(f"✅ Transcribed {len(transcript_segments)} segments")
        
        # Step 3: Translate to Bangla
        if progress_callback:
            progress_callback(40, "বাংলায় অনুবাদ করা হচ্ছে")
        
        translated_segments = self.translator.translate_batch(
            transcript_segments, 
            source_lang, 
            target_lang
        )
        logger.info(f"✅ Translated {len(translated_segments)} segments")
        
        # Step 4: Voice Cloning per speaker
        if progress_callback:
            progress_callback(60, "ভয়েস ক্লোনিং চলছে")
        
        # Extract speaker references from the audio
        speaker_mapping = self._extract_speaker_references(transcript_segments, audio_path)
        
        cloned_audio_paths = self.voice_cloner.clone_multiple_speakers(
            translated_segments,
            speaker_mapping,
            output_dir=os.path.dirname(output_path)
        )
        logger.info(f"✅ Voice cloning completed for {len(cloned_audio_paths)} speakers")
        
        # Step 5: Merge audio with timing
        if progress_callback:
            progress_callback(80, "অডিও সিঙ্ক করা হচ্ছে")
        
        dubbed_audio_path = self._sync_audio_with_timeline(
            translated_segments,
            cloned_audio_paths,
            audio_path
        )
        logger.info(f"✅ Audio synced: {dubbed_audio_path}")
        
        # Step 6: Merge with video
        if progress_callback:
            progress_callback(90, "ভিডিও মার্জ করা হচ্ছে")
        
        final_output = self.video_merger.merge(video_path, dubbed_audio_path, output_path)
        logger.info(f"✅ Final video: {final_output}")
        
        # Step 7: Cleanup
        self._cleanup(audio_path, cloned_audio_paths, dubbed_audio_path)
        
        if progress_callback:
            progress_callback(100, "সম্পন্ন!")
        
        return final_output
    
    def _extract_speaker_references(self, segments: list, audio_path: str) -> Dict:
        """Extract speaker reference audio files for each speaker"""
        speaker_mapping = {}
        
        for segment in segments:
            speaker = segment.get('speaker', 'SPEAKER_00')
            if speaker not in speaker_mapping:
                # Extract a short clip for each speaker (2-3 seconds)
                start = segment.get('start', 0)
                end = min(start + 3, segment.get('end', start + 3))
                
                ref_path = f"refs/{speaker}_{int(start)}.wav"
                os.makedirs("refs", exist_ok=True)
                
                # Extract using ffmpeg
                cmd = [
                    'ffmpeg', '-y',
                    '-i', audio_path,
                    '-ss', str(start),
                    '-to', str(end),
                    '-ac', '1',
                    ref_path
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                speaker_mapping[speaker] = ref_path
        
        return speaker_mapping
    
    def _sync_audio_with_timeline(
        self,
        segments: list,
        cloned_audio_paths: Dict,
        original_audio_path: str
    ) -> str:
        """Sync cloned audio clips with original timeline"""
        # Create silent audio
        output_path = "dubbed_audio_sync.wav"
        
        # Use FFmpeg to concatenate with silence gaps
        # Complex filter for audio concatenation with timing
        
        # For each segment, place cloned audio at the correct timestamp
        filter_parts = []
        inputs = []
        for i, segment in enumerate(segments):
            speaker = segment.get('speaker', 'SPEAKER_00')
            audio_file = cloned_audio_paths.get(speaker)
            if not audio_file:
                continue
            
            # Calculate offset in seconds
            start = segment.get('start', 0)
            
            # Add input
            input_idx = len(inputs)
            inputs.append('-i')
            inputs.append(audio_file)
            
            # Add to filter with delay
            filter_parts.append(
                f'[{input_idx}:a]adelay={int(start*1000)}|{int(start*1000)}[a{input_idx}]'
            )
        
        # Add original audio as background
        inputs.insert(0, '-i')
        inputs.insert(0, original_audio_path)
        filter_parts.append(f'[0:a]volume=0.05[orig]')
        
        # Mix all together
        mix_inputs = '[' + ']'.join([f'a{i}' for i in range(len(inputs)//2)]) + ']'
        filter_parts.append(f'{mix_inputs}[orig]amix=inputs={len(inputs)//2+1}:duration=longest[out]')
        
        cmd = [
            'ffmpeg', '-y',
            *inputs,
            '-filter_complex', ';'.join(filter_parts),
            '-map', '[out]',
            '-acodec', 'pcm_s16le',
            output_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    
    def _cleanup(self, *paths):
        """Delete temporary files"""
        for path in paths:
            if path and os.path.exists(path):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                except:
                    pass
