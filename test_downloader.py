
from downloader import VideoDownloader
import os

def test_download():
    dl = VideoDownloader()
    url = "https://www.youtube.com/watch?v=BaW_jenozKc" # harmless video
    print(f"Testing info fetch for {url}")
    info = dl.get_video_info(url)
    if 'error' in info:
        print(f"Info Error: {info['error']}")
    else:
        print("Info fetch success")
        print(f"Title: {info.get('title')}")
        
    # Try download
    if not os.path.exists("test_dl"):
        os.makedirs("test_dl")
        
    print("Testing download...")
    success, msg = dl.download_video(url, "test_dl")
    print(f"Download Success: {success}")
    print(f"Download Msg: {msg}")

if __name__ == "__main__":
    test_download()
