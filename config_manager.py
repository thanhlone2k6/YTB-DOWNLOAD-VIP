import json
import os

CONFIG_FILE = "config.json"

class ConfigManager:
    def __init__(self):
        self.default_config = {
            "download_path": os.path.join(os.getcwd(), "downloads"),
            "theme": "Dark",
            "auto_download": True
        }
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
             return self.default_config.copy()
        
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self.default_config.copy()

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key):
        return self.config.get(key, self.default_config.get(key))

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
