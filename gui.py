import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import time
from PIL import Image, ImageTk
import urllib.request
import io
import requests
import webbrowser
import sys
from downloader import VideoDownloader
from config_manager import ConfigManager

# --- CONFIG & CONSTANTS ---
CURRENT_VERSION = "2.6.0"
REPO_OWNER = "thanhlone2k6"
REPO_NAME = "YTB-DOWNLOAD-VIP"

# --- THEME CONFIGURATION ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Color Palette (Based on screenshot/modern dark theme)
COLORS = {
    "bg": "#0b1120",           # Main Background (very dark blue/black)
    "panel": "#151b2b",        # Panel/Card Background
    "accent": "#3b82f6",       # Primary Action Blue (like 'Paste' button)
    "accent_hover": "#2563eb",
    "text": "#ffffff",
    "text_sec": "#94a3b8",     # Secondary Text (Slate-400)
    "danger": "#ef4444",       # Red
    "success": "#10b981",      # Green
    "border": "#1e293b",       # Border color
    "progress": "#3b82f6"      # Progress bar color
}

class TaskCard(ctk.CTkFrame):
    def __init__(self, parent, url, download_path, downloader_instance, remove_callback, is_audio=False):
        super().__init__(parent, fg_color=COLORS["panel"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        self.url = url
        self.download_path = download_path
        self.downloader = downloader_instance
        self.remove_callback = remove_callback
        self.is_audio = is_audio
        self.is_downloading = False
        self.stop_event = False # Not fully implemented for yt-dlp stop, but used for logic state

        self.setup_ui()
        self.start_processing()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        
        # 1. Icon / Thumbnail (Left)
        # Using a neutral placeholder initially
        self.thumb_frame = ctk.CTkFrame(self, width=120, height=68, fg_color="black", corner_radius=8)
        self.thumb_frame.grid(row=0, column=0, rowspan=2, padx=12, pady=12, sticky="ns")
        self.thumb_frame.grid_propagate(False)
        
        self.thumb_label = ctk.CTkLabel(self.thumb_frame, text="", image=None)
        self.thumb_label.pack(expand=True, fill="both")

        # 2. Info (Title & Meta)
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=(12, 0))
        
        self.title_label = ctk.CTkLabel(self.info_frame, text="Fetching metadata...", font=("Segoe UI", 14, "bold"), text_color=COLORS["text"], anchor="w")
        self.title_label.pack(fill="x")
        
        self.meta_label = ctk.CTkLabel(self.info_frame, text=f"initializing • {self.url}", font=("Segoe UI", 12), text_color=COLORS["text_sec"], anchor="w")
        self.meta_label.pack(fill="x")

        # 3. Status / Speed (Right Top)
        self.status_label = ctk.CTkLabel(self, text="Waiting...", font=("Segoe UI", 12, "bold"), text_color=COLORS["accent"], anchor="e")
        self.status_label.grid(row=0, column=2, padx=15, pady=(12, 0), sticky="e")

        # 4. Progress Bar & Controls (Bottom Row)
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_frame.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 15), pady=(5, 12))
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=8, corner_radius=4, progress_color=COLORS["progress"])
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.progress_bar.set(0)
        
        self.percent_label = ctk.CTkLabel(self.progress_frame, text="0%", font=("Segoe UI", 12), text_color=COLORS["text"], width=40)
        self.percent_label.pack(side="left")

        # Controls
        self.btn_copy = ctk.CTkButton(self.progress_frame, text="📋", width=30, height=30, fg_color="transparent", hover_color=COLORS["border"], command=self.copy_link)
        self.btn_copy.pack(side="left", padx=2)
        
        self.btn_open = ctk.CTkButton(self.progress_frame, text="📂", width=30, height=30, fg_color="transparent", hover_color=COLORS["border"], command=self.open_folder)
        self.btn_open.pack(side="left", padx=2)
        
        self.btn_del = ctk.CTkButton(self.progress_frame, text="🗑", width=30, height=30, fg_color="transparent", hover_color=COLORS["danger"], command=self.on_delete)
        self.btn_del.pack(side="left", padx=2)

    def start_processing(self):
        threading.Thread(target=self._download_task, daemon=True).start()

    def _download_task(self):
        # Step 1: Get Info (and update UI)
        if self.stop_event: return

        self.title_label.configure(text="Getting info...")
        try:
             info = self.downloader.get_video_info(self.url)
             if self.stop_event: return # Check stop again

             if 'error' in info:
                 self.status_label.configure(text="Error", text_color=COLORS["danger"])
                 self.meta_label.configure(text=str(info['error']))
                 return
             
             # Update Metadata
             title = info.get('title', 'Unknown Title')
             platform = info.get('extractor_key', 'Web')
             
             self.after(0, lambda: self.title_label.configure(text=title))
             self.after(0, lambda: self.meta_label.configure(text=f"{platform} • Best Quality"))
             
             # Load Thumbnail
             thumb_url = info.get('thumbnail')
             if thumb_url:
                 self._load_thumbnail(thumb_url)
                 
             # Check if playlist
             self.is_playlist = False
             self.playlist_title = None
             playlist_entries = None
             
             if info.get('_type') == 'playlist' or 'entries' in info:
                 self.is_playlist = True
                 self.playlist_title = info.get('title', 'Unknown Playlist')
                 playlist_entries = list(info.get('entries', []))
                 self.after(0, lambda: self.meta_label.configure(text=f"Playlist • {len(playlist_entries)} Videos"))

             # Playlist Selection
             self.selected_items_str = None
             if self.is_playlist and playlist_entries:
                 self.after(0, lambda: self.status_label.configure(text="Waiting for selection..."))
                 
                 selection_event = threading.Event()
                 
                 def on_selected(items_str):
                     self.selected_items_str = items_str
                     selection_event.set()
                 
                 # Show dialog on main thread
                 self.after(0, lambda: PlaylistSelectionDialog(self, playlist_entries, on_selected))
                 
                 # Wait
                 selection_event.wait()
                 
                 if not self.selected_items_str:
                     # User closed/cancelled - Stop task
                     self.after(0, lambda: self.status_label.configure(text="Cancelled"))
                     return

        except Exception as e:
            print(f"Metadata error: {e}")
            if "Stopped by user" in str(e): return
            if not self.is_playlist: # Don't error out if cancelled playlist
                 self.after(0, lambda: self.status_label.configure(text="Error"))
        # Step 2: Start Download
        self.is_downloading = True
        self.after(0, lambda: self.status_label.configure(text="Downloading..."))
        
        def progress_hook(d):
            if self.stop_event:
                raise Exception("Stopped by user")

            if d['status'] == 'downloading':
                try:
                    # Calculate progress manually for robustness
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    
                    if total > 0:
                        percent_val = downloaded / total
                        p_str = f"{percent_val:.1%}"
                    else:
                        percent_val = 0
                        p_str = "N/A"
                    
                    # Speed
                    speed_val = d.get('speed', 0)
                    speed_str = "N/A"
                    if speed_val:
                        speed_mb = speed_val / 1024 / 1024
                        speed_str = f"{speed_mb:.1f} MB/s"
                        
                    # Total Size
                    total_str = "?"
                    if total:
                        total_mb = total / 1024 / 1024
                        total_str = f"{total_mb:.1f} MB"

                    # Playlist Progress
                    prefix = ""
                    p_index = d.get('playlist_index')
                    p_count = d.get('playlist_count') or d.get('n_entries')
                    if p_index and p_count:
                        prefix = f"[{p_index}/{p_count}] "

                    self.after(0, lambda: self.progress_bar.set(percent_val))
                    self.after(0, lambda: self.percent_label.configure(text=p_str))
                    self.after(0, lambda: self.status_label.configure(text=f"{prefix}{speed_str} • {total_str}"))
                except Exception as e:
                    print(f"Hook Error: {e}")
            elif d['status'] == 'finished':
                # Only indicate full completion if not a playlist (playlist handles individual completions)
                # But here we just update 100% for the current file
                self.after(0, lambda: self.progress_bar.set(1))
                self.after(0, lambda: self.percent_label.configure(text="100%"))
                self.after(0, lambda: self.status_label.configure(text="Completed", text_color=COLORS["success"]))

        fmt = 'audio' if self.is_audio else 'video'
        success, msg = self.downloader.download_video(self.url, self.download_path, format_type=fmt, progress_hook=progress_hook, playlist_name=self.playlist_title, playlist_items=getattr(self, 'selected_items_str', None))
        
        self.is_downloading = False
        if not success:
             state_text = "Stopped" if "Stopped by user" in str(msg) else "Failed"
             state_color = COLORS["text_sec"] if state_text == "Stopped" else COLORS["danger"]
             self.after(0, lambda: self.status_label.configure(text=state_text, text_color=state_color))
             if state_text != "Stopped":
                 self.after(0, lambda: self.meta_label.configure(text=msg))

    def _load_thumbnail(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = response.read()
            img = Image.open(io.BytesIO(data))
            # Resize
            img.thumbnail((120, 68))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(120, 68))
            
            self.img_ref = ctk_img # Keep reference
            self.after(0, lambda: self.thumb_label.configure(image=ctk_img))
        except:
            pass

    def open_folder(self):
        if os.path.exists(self.download_path):
            os.startfile(self.download_path)

    def copy_link(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.url)
            self.status_label.configure(text="Copied!", text_color=COLORS["accent"])
            self.after(2000, lambda: self.status_label.configure(text="Waiting...", text_color=COLORS["text"]))
        except:
             pass

    def on_delete(self):
        self.stop_event = True
        if self.remove_callback:
            self.remove_callback(self)
        self.destroy()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Downloader Pro")
        self.geometry("1100x700")
        self.configure(fg_color=COLORS["bg"])
        
        self.config = ConfigManager()
        self.downloader = VideoDownloader()

        self.setup_layout()
        self.load_settings()

    def setup_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- LEFT SIDEBAR ---
        self.sidebar = ctk.CTkFrame(self, fg_color=COLORS["panel"], width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Logo / Branding
        self.lbl_brand = ctk.CTkLabel(self.sidebar, text="⬇ Download Vipp", font=("Segoe UI", 20, "bold"), text_color=COLORS["text"])
        self.lbl_brand.pack(pady=(30, 0), padx=20, anchor="w")
        
        self.lbl_author = ctk.CTkLabel(self.sidebar, text="By Thành Nguyễn", font=("Segoe UI", 12), text_color=COLORS["text_sec"])
        self.lbl_author.pack(pady=(0, 40), padx=20, anchor="w")

        # Menu Items
        self.menu_btn_downloads = self.create_sidebar_btn("Downloads", True)
        self.menu_btn_downloads.pack(fill="x", padx=10, pady=5)

        # Version & Update
        self.lbl_version = ctk.CTkLabel(self.sidebar, text=f"Version: {CURRENT_VERSION}", font=("Segoe UI", 12), text_color=COLORS["text_sec"])
        self.lbl_version.pack(side="bottom", pady=(5, 20))
        
        self.btn_check_update = ctk.CTkButton(self.sidebar, text="🔄 Check Update", fg_color="transparent", hover_color=COLORS["border"], 
                                              anchor="center", height=30, font=("Segoe UI", 12), command=self.manual_check_update)
        self.btn_check_update.pack(side="bottom", fill="x", padx=20, pady=5)

        # --- MAIN CONTENT AREA ---
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(2, weight=1) # Task list expands

        # 1. Header Input Area
        self.input_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.input_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        
        # URL Input Row
        self.url_frame = ctk.CTkFrame(self.input_frame, fg_color=COLORS["panel"], corner_radius=10, border_width=1, border_color=COLORS["border"])
        self.url_frame.pack(fill="x", pady=(0, 10))
        
        self.url_entry = ctk.CTkEntry(self.url_frame, placeholder_text="Paste video link here (YouTube, TikTok, Facebook...)", 
                                      border_width=0, fg_color="transparent", height=50, font=("Segoe UI", 14))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=15)
        self.url_entry.bind("<Return>", self.add_task_event)
        self.url_entry.bind("<Control-v>", self.on_paste)

        self.btn_paste = ctk.CTkButton(self.url_frame, text="PASTE", width=80, fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self.paste_from_clipboard)
        self.btn_paste.pack(side="right", padx=10, pady=10)

        # Save Location Row (Under input as requested)
        self.path_frame = ctk.CTkFrame(self.input_frame, fg_color="transparent")
        self.path_frame.pack(fill="x")
        
        ctk.CTkLabel(self.path_frame, text="Save to:", text_color=COLORS["text_sec"]).pack(side="left", padx=(0, 10))
        
        self.path_entry = ctk.CTkEntry(self.path_frame, width=300, fg_color=COLORS["panel"], border_width=1, border_color=COLORS["border"])
        self.path_entry.pack(side="left", fill="x", expand=True)
        
        self.btn_browse = ctk.CTkButton(self.path_frame, text="📂", width=40, fg_color=COLORS["panel"], hover_color=COLORS["border"], command=self.browse_folder)
        self.btn_browse.pack(side="left", padx=(10, 0))
        
        # Audio Only Checkbox
        self.audio_only_var = ctk.BooleanVar(value=False)
        self.chk_audio = ctk.CTkCheckBox(self.path_frame, text="Chỉ tải MP3", variable=self.audio_only_var, font=("Segoe UI", 12), text_color=COLORS["text"])
        self.chk_audio.pack(side="left", padx=(20, 0))

        # 2. Section Title
        self.lbl_section = ctk.CTkLabel(self.main_area, text="Downloading", font=("Segoe UI", 18, "bold"), text_color=COLORS["text"], anchor="w")
        self.lbl_section.grid(row=1, column=0, sticky="w", pady=(10, 15))

        # 3. Task List (Scrollable)
        self.tasks_scroll = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent", label_text="")
        self.tasks_scroll.grid(row=2, column=0, sticky="nsew")

    def create_sidebar_btn(self, text, is_active):
        color = COLORS["accent"] if is_active else "transparent"
        text_col = COLORS["text"] if is_active else COLORS["text_sec"]
        return ctk.CTkButton(self.sidebar, text=text, fg_color=color, text_color=text_col, hover_color=COLORS["border"], anchor="w", height=45, font=("Segoe UI", 14))

    def load_settings(self):
        saved_path = self.config.get("download_path")
        if os.path.exists(saved_path):
            self.path_entry.insert(0, saved_path)
        else:
            self.path_entry.insert(0, os.getcwd())

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.path_entry.delete(0, 'end')
            self.path_entry.insert(0, path)
            self.config.set("download_path", path)

    def paste_from_clipboard(self):
        try:
            content = self.clipboard_get()
            self.url_entry.delete(0, 'end')
            self.url_entry.insert(0, content)
            self.add_task(content)
        except:
            pass

    def on_paste(self, event):
        # Allow default paste to happen, then trigger add
        # We need a slight delay to let the entry update
        self.after(50, self.check_entry_and_add)

    def check_entry_and_add(self):
        url = self.url_entry.get().strip()
        if url:
             self.add_task(url)

    def add_task_event(self, event):
        url = self.url_entry.get().strip()
        if url:
            self.add_task(url)

    def add_task(self, url):
        # Validate simple URL
        if not url.startswith("http"):
            return # Ignore non-links

        save_path = self.path_entry.get()
        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path)
            except:
                messagebox.showerror("Error", "Invalid download path")
                return

        # Clear input if auto-add logic
        self.url_entry.delete(0, 'end')

        # Create Task Card
        is_audio = self.audio_only_var.get()
        card = TaskCard(self.tasks_scroll, url, save_path, self.downloader, self.remove_task, is_audio=is_audio)
        
        # Insert at TOP logic
        children = self.tasks_scroll.winfo_children()
        
        # Since 'card' is already created as a child, it is technically last in list internally
        # But we can repack it.
        # However, winfo_children includes the new card? 
        # Actually in CTkScrollableFrame, we pack into self.tasks_scroll (which is a frame).
        
        child_widgets = [c for c in self.tasks_scroll.winfo_children() if isinstance(c, TaskCard) and c != card]
        
        if child_widgets:
            # Pack before the first current card
            card.pack(before=child_widgets[0], fill="x", pady=5)
        else:
            card.pack(fill="x", pady=5)
        
        # Update section title count?
        # self.lbl_section.configure(text=f"Downloading ({len(self.tasks_scroll.winfo_children())})")

    def remove_task(self, task_widget):
        task_widget.destroy()

    def manual_check_update(self):
        self.btn_check_update.configure(state="disabled", text="Checking...")
        threading.Thread(target=self.run_check, args=(True,), daemon=True).start()

    def check_update(self):
        # Chạy kiểm tra trong một luồng riêng để không làm treo giao diện
        threading.Thread(target=self.run_check, args=(False,), daemon=True).start()

    def run_check(self, is_manual=False):
        try:
            # URL to check version
            VERSION_URL = "https://raw.githubusercontent.com/thanhlone2k6/YTB-DOWNLOAD-VIP/main/version.json"
            response = requests.get(VERSION_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("version", "1.0.0")
                download_url = data.get("url", "")
                
                # Check version
                if latest_version > CURRENT_VERSION:
                    self.after(0, lambda: self.show_update_popup(latest_version, download_url))
                elif is_manual:
                     self.after(0, lambda: messagebox.showinfo("Update", "Bạn đang dùng phiên bản mới nhất!"))
            
            if is_manual:
                self.after(0, lambda: self.btn_check_update.configure(state="normal", text="🔄 Check Update"))
                
        except Exception as e:
            print(f"Update Check Error: {e}")
            if is_manual:
                 self.after(0, lambda: messagebox.showerror("Error", "Không thể kiểm tra cập nhật"))
                 self.after(0, lambda: self.btn_check_update.configure(state="normal", text="🔄 Check Update"))

    def show_update_popup(self, version, url):
        try:
            popup = ctk.CTkToplevel(self)
            popup.title("Cập nhật mới 🚀")
            popup.geometry("340x220")
            popup.attributes("-topmost", True)
            
            # Center on screen
            popup.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - (340 // 2)
            y = self.winfo_y() + (self.winfo_height() // 2) - (220 // 2)
            popup.geometry(f"+{x}+{y}")

            ctk.CTkLabel(popup, text=f"✨ Đã có bản {version}", font=("Segoe UI", 16, "bold"), text_color=COLORS["accent"]).pack(pady=(20, 5))
            ctk.CTkLabel(popup, text="Có tính năng mới đang chờ bạn!\nBấm cài đặt để tự động update ngay.", font=("Segoe UI", 12)).pack(pady=5)

            # Progress for download
            self.dl_progress = ctk.CTkProgressBar(popup, width=200, height=10, progress_color=COLORS["success"])
            self.dl_progress.set(0)
            
            self.btn_update = ctk.CTkButton(popup, text="Cài đặt ngay (1 Click)", fg_color=COLORS["success"], hover_color="#059669", 
                                            command=lambda: self.perform_update(url, popup))
            self.btn_update.pack(pady=20)
            
        except:
             pass

    def perform_update(self, url, popup):
        # Disable button
        self.btn_update.configure(state="disabled", text="Đang tải về...")
        self.dl_progress.pack(pady=5)
        
        threading.Thread(target=self._download_and_install, args=(url, popup), daemon=True).start()

    def _download_and_install(self, url, popup):
        try:
            # 1. Download new exe to temp name
            response = requests.get(url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            new_exe_name = "new_version.exe"
            
            downloaded = 0
            with open(new_exe_name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            prog = downloaded / total_size
                            self.after(0, lambda: self.dl_progress.set(prog))

            self.after(0, lambda: self.btn_update.configure(text="Đang cài đặt..."))
            
            # 2. Create Batch script to replace file
            # Windows không cho xóa file đang chạy, nên cần script ngoài
            current_exe = os.path.basename(sys.executable)
            if not current_exe.endswith(".exe"): current_exe = "DownloaderPro_v2.exe" # Fallback if running from script
            
            bat_script = f"""
@echo off
timeout /t 2 /nobreak >nul
del "{current_exe}"
move "{new_exe_name}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
"""
            with open("updater.bat", "w") as f:
                f.write(bat_script)
            
            # 3. Launch script and exit
            self.after(0, lambda: os.startfile("updater.bat"))
            self.after(100, self.destroy)
            
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Lỗi Update", str(e)))
            self.after(0, lambda: self.btn_update.configure(state="normal", text="Thử lại"))

if __name__ == "__main__":
    import sys # Need sys for executable path
    app = App()
    app.after(2000, app.check_update)
    app.mainloop()

class PlaylistSelectionDialog(ctk.CTkToplevel):
    def __init__(self, parent, video_list, on_confirm):
        super().__init__(parent)
        self.title("Select Videos to Download")
        self.geometry("600x500")
        self.on_confirm = on_confirm
        self.check_vars = []
        
        # Make modal-like
        self.transient(parent)
        self.grab_set()
        
        # Title
        ctk.CTkLabel(self, text=f"Found {len(video_list)} videos", font=("Arial", 18, "bold")).pack(pady=10)
        
        # Scrollable List
        self.scroll_frame = ctk.CTkScrollableFrame(self, width=550, height=350)
        self.scroll_frame.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Populate
        # video_list is list of dicts from 'entries'
        for i, vid in enumerate(video_list, 1):
            title = vid.get('title', f"Video {i}")
            # Limit title length
            if len(title) > 60: title = title[:57] + "..."
            
            var = ctk.BooleanVar(value=True)
            self.check_vars.append((i, var))
            
            row = ctk.CTkFrame(self.scroll_frame)
            row.pack(fill="x", pady=2)
            
            cb = ctk.CTkCheckBox(row, text=f"{i}. {title}", variable=var, width=500)
            cb.pack(side="left", padx=5, pady=5)
            
        # Buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=10, fill="x", side="bottom")
        
        ctk.CTkButton(btn_frame, text="Select All", command=self.select_all).pack(side="left", padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="Deselect All", command=self.deselect_all).pack(side="left", padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="Download Selected", command=self.confirm, fg_color="#28a745", hover_color="#218838").pack(side="right", padx=20, pady=10)

    def select_all(self):
        for _, var in self.check_vars: var.set(True)

    def deselect_all(self):
        for _, var in self.check_vars: var.set(False)

    def confirm(self):
        # Gather selected indices
        selected = []
        for i, var in self.check_vars:
            if var.get():
                selected.append(str(i))
        
        if not selected:
            return # Do nothing if empty? Or allow close?
            
        # Join as string for yt-dlp "1,2,5-7" style (simplest is comma separated)
        selection_str = ",".join(selected)
        self.on_confirm(selection_str)
        self.destroy()