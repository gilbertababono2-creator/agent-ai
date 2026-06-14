"""
Video editor module using MoviePy and FFmpeg
"""
import logging
import os
from pathlib import Path
from typing import List, Optional

from moviepy.editor import (
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    TextClip,
    ColorClip
)

from config import config

logger = logging.getLogger(__name__)

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
FPS = config.DEFAULT_FPS


def _fit_clip_to_vertical(clip: VideoFileClip, target_w=TARGET_WIDTH, target_h=TARGET_HEIGHT):
    """Resize and crop a clip to target vertical 9:16 frame while preserving aspect ratio"""
    # First, resize clip to fit width or height
    clip_w, clip_h = clip.size
    target_ar = target_w / target_h
    clip_ar = clip_w / clip_h

    if clip_ar > target_ar:
        # clip is wider than target, fit height and crop width
        new_h = target_h
        new_w = int(clip_ar * new_h)
    else:
        # clip is taller/narrower, fit width and crop height
        new_w = target_w
        new_h = int(new_w / clip_ar)

    clip_resized = clip.resize(height=new_h) if new_h < clip_h or new_h != clip_h else clip.resize(width=new_w)

    # center crop
    x1 = (clip_resized.w - target_w) // 2
    y1 = (clip_resized.h - target_h) // 2
    clip_cropped = clip_resized.crop(x1=x1, y1=y1, width=target_w, height=target_h)
    clip_cropped = clip_cropped.set_fps(FPS)
    return clip_cropped


class Editor:
    def __init__(self):
        self.output_dir = config.OUTPUT_DIR
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

    def assemble_video(
        self,
        source_files: List[str],
        voiceover_files: List[str],
        texts: List[str],
        duration: int,
        output_filename: Optional[str] = None,
    ) -> dict:
        """
        Assemble a vertical video (9:16) from source clips and voiceovers.
        - source_files: list of downloaded video file paths (can be empty)
        - voiceover_files: list of audio files (ordered)
        - texts: list of text overlays corresponding to voiceover segments
        - duration: total duration in seconds
        """
        try:
            logger.info("Assembling video...")
            segments = len(voiceover_files)
            if segments == 0:
                logger.error("No voiceover files provided")
                return {'success': False, 'error': 'no_voiceovers'}

            # Determine segment durations evenly
            seg_duration = max(1, duration // segments)

            clips = []
            src_index = 0

            for i in range(segments):
                # Use source clip if available, otherwise color clip
                if src_index < len(source_files) and os.path.exists(source_files[src_index]):
                    src = source_files[src_index]
                    try:
                        vclip = VideoFileClip(src)
                        # choose a subclip from start (or random in future)
                        start = 0
                        end = min(vclip.duration, start + seg_duration)
                        clip_part = vclip.subclip(start, end)
                        clip_part = _fit_clip_to_vertical(clip_part)
                        src_index += 1
                    except Exception as e:
                        logger.warning(f"Failed to process source {src}: {e}")
                        clip_part = ColorClip(size=(TARGET_WIDTH, TARGET_HEIGHT), color=(0,0,0), duration=seg_duration)
                else:
                    clip_part = ColorClip(size=(TARGET_WIDTH, TARGET_HEIGHT), color=(0,0,0), duration=seg_duration)

                # Add text overlay
                text = texts[i] if i < len(texts) else ""
                if text:
                    txt_clip = TextClip(txt=text, fontsize=80, color='white', font='Arial-Bold', size=(TARGET_WIDTH*0.9, None), method='label')
                    txt_clip = txt_clip.set_position(('center', TARGET_HEIGHT*0.1)).set_duration(clip_part.duration)
                    composed = CompositeVideoClip([clip_part, txt_clip])
                else:
                    composed = clip_part

                clips.append(composed)

            # Concatenate video clips
            final_video = concatenate_videoclips(clips, method='compose')

            # Concatenate audio files into one AudioFileClip
            audio_clips = [AudioFileClip(p) for p in voiceover_files]
            audio_concat = concatenate_videoclips([c.set_audio(a) for c, a in zip([ColorClip(size=(1,1), color=(0,0,0), duration=a.duration) for a in audio_clips], audio_clips)])
            # Alternative: build a single audio by concatenation via ffmpeg in future

            # Save audio to temp then set audio on final_video
            audio_combined_path = os.path.join(config.TEMP_DIR, 'combined_voiceover.mp3')
            # Use moviepy to write audiofile by concatenating AudioFileClip objects
            from moviepy.audio.io.AudioFileClip import concatenate_audioclips
            from moviepy.editor import AudioClip
            audio = concatenate_audioclips(audio_clips)
            audio.write_audiofile(audio_combined_path, fps=44100)

            final_audio = AudioFileClip(audio_combined_path)
            final_video = final_video.set_audio(final_audio)

            # Trim or pad to desired duration
            if final_video.duration > duration:
                final_video = final_video.subclip(0, duration)
            elif final_video.duration < duration:
                pad = ColorClip(size=(TARGET_WIDTH, TARGET_HEIGHT), color=(0,0,0), duration=duration - final_video.duration)
                final_video = concatenate_videoclips([final_video, pad], method='compose')

            # Output filepath
            output_filename = output_filename or f"video_{int(Path(output_filename or config.OUTPUT_DIR).stat().st_mtime if Path(config.OUTPUT_DIR).exists() else 0)}.mp4"
            output_path = os.path.join(self.output_dir, output_filename)

            logger.info(f"Rendering final video to {output_path} (this may take a while)")
            final_video.write_videofile(output_path, codec=config.DEFAULT_CODEC, fps=FPS, audio_codec='aac', threads=4, temp_audiofile=os.path.join(config.TEMP_DIR, 'temp-audio.m4a'), remove_temp=True)

            logger.info("✓ Video assembled")
            return {'success': True, 'output_path': output_path, 'duration': duration}

        except Exception as e:
            logger.error(f"Editor error: {e}")
            return {'success': False, 'error': str(e)}
