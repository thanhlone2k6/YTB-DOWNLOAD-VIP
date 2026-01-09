import yt_dlp
import os
import threading

class VideoDownloader:
    def __init__(self):
        pass

    def _get_cookie_file(self, url):
        # Use the master cookie file provided
        if os.path.exists("cookies.txt"):
            return "cookies.txt"
        return None

    def get_video_info(self, url):
        """
        Extracts video information without downloading.
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        cookie_file = self._get_cookie_file(url)
        if cookie_file:
            # print(f"Using cookie file: {cookie_file}") # Optional logging
            ydl_opts['cookiefile'] = cookie_file

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except Exception as e:
            return {'error': str(e)}

    def download_video(self, url, output_path, format_type='video', progress_hook=None):
        """
        Downloads the video.
        format_type: 'video' (best video+audio) or 'audio' (mp3)
        """
        ydl_opts = {
            'progress_hooks': [progress_hook] if progress_hook else [],
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        cookie_file = self._get_cookie_file(url)
        if cookie_file:
            print(f"Using cookie file: {cookie_file}")
            ydl_opts['cookiefile'] = cookie_file

        # 1. Output Template Logic (Instagram Folder)
        if "instagram.com" in url:
             # Structure: output_path / Title / Title-ID.ext
             ydl_opts['outtmpl'] = os.path.join(output_path, '%(title).100s', '%(title).100s-%(id)s.%(ext)s')
        else:
             ydl_opts['outtmpl'] = os.path.join(output_path, '%(title)s.%(ext)s')

        # 2. Format Logic (Auto MP4)
        if format_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # Force MP4 container merging if needed
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True, "Download Complete"
        except Exception as e:
            return False, str(e)
