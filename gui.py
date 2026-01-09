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
from downloader import VideoDownloader
from config_manager import ConfigManager

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
                 
        except Exception as e:
            print(f"Metadata error: {e}")

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

                    self.after(0, lambda: self.progress_bar.set(percent_val))
                    self.after(0, lambda: self.percent_label.configure(text=p_str))
                    self.after(0, lambda: self.status_label.configure(text=f"{speed_str} • {total_str}"))
                except Exception as e:
                    print(f"Hook Error: {e}")
            elif d['status'] == 'finished':
                self.after(0, lambda: self.progress_bar.set(1))
                self.after(0, lambda: self.percent_label.configure(text="100%"))
                self.after(0, lambda: self.status_label.configure(text="Completed", text_color=COLORS["success"]))

        fmt = 'audio' if self.is_audio else 'video'
        success, msg = self.downloader.download_video(self.url, self.download_path, format_type=fmt, progress_hook=progress_hook)
        
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

        # Settings at bottom
        # Settings at bottom removed as requested

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

    def check_update(self):
        # Chạy kiểm tra trong một luồng riêng để không làm treo giao diện
        threading.Thread(target=self.run_check, daemon=True).start()

    def run_check(self):
        try:
            VERSION_URL = "https://raw.githubusercontent.com/thanhlone2k6/YTB-DOWNLOAD-VIP/main/version.json"
            response = requests.get(VERSION_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("version", "1.0.0")
                download_url = data.get("url", "")
                
                # Simple comparison
                if latest_version > "1.0.0":
                    self.after(0, lambda: self.show_update_popup(latest_version, download_url))
        except Exception as e:
            print(f"Lỗi check update rồi ông cháu ơi: {e}")

    def show_update_popup(self, version, url):
        # Tạo một cái popup chuẩn vibe Glassmorphism
        try:
            popup = ctk.CTkToplevel(self)
            popup.title("Update nè!")
            popup.geometry("300x200")
            popup.attributes("-topmost", True) # Cho hiện lên trên cùng

            label = ctk.CTkLabel(popup, text=f"Đã có bản {version}!\nAe tải về dùng cho mượt nhé.", font=("Arial", 14))
            label.pack(pady=20)

            btn = ctk.CTkButton(popup, text="Tải ngay", command=lambda: [webbrowser.open(url), popup.destroy()])
            btn.pack(pady=10)
        except:
             pass

if __name__ == "__main__":
    app = App()
    app.after(2000, app.check_update) # Check after 2s
    app.mainloop()
