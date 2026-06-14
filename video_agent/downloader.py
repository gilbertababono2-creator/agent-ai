"""
Downloader module using yt-dlp
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any

import yt_dlp
from config import config

logger = logging.getLogger(__name__)

class Downloader:
    def __init__(self):
        self.temp_dir = config.TEMP_DIR
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        self.ydl_opts = {
            'outtmpl': os.path.join(self.temp_dir, '%(id)s.%(ext)s'),
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True
        }

    def download(self, url: str) -> Dict[str, Any]:
        """Download a video and return metadata including file path"""
        try:
            logger.info(f"Downloading: {url}")
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            if not info:
                logger.error(f"Failed to download or extract info for {url}")
                return {'success': False, 'error': 'no_info', 'url': url}

            # Determine file path
            ext = info.get('ext') or 'mp4'
            video_id = info.get('id')
            filename = os.path.join(self.temp_dir, f"{video_id}.{ext}")
            if not os.path.exists(filename):
                # try mp4
                filename_mp4 = os.path.join(self.temp_dir, f"{video_id}.mp4")
                if os.path.exists(filename_mp4):
                    filename = filename_mp4

            result = {
                'success': True,
                'url': url,
                'id': video_id,
                'title': info.get('title'),
                'duration': info.get('duration'),
                'filepath': filename,
                'uploader': info.get('uploader')
            }
            logger.info(f"Downloaded to {filename}")
            return result

        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            return {'success': False, 'error': str(e), 'url': url}
