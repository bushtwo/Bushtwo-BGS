import json
import os
import sys

DEFAULT_CONFIG = {
    "folders": [],
    "include_subfolders": True,
    "timer_mode": "interval",      # "interval" or "day"
    "interval_seconds": 300,
    "scaling_mode": "Fill",
    "run_at_startup": False,
    "start_minimized": False,
    "close_to_tray": True,
    "is_paused": False,
    "last_wallpaper": None,
    "last_day_switched": None,
    "history": []
}


class ConfigManager:
    """Manages loading, updating, and saving configuration to a persistent JSON file."""

    def __init__(self, config_filename="config.json"):
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.app_dir, config_filename)
        self.config = self.load()

    def load(self) -> dict:
        """Loads configuration from JSON or returns defaults if file does not exist."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    merged = dict(DEFAULT_CONFIG)
                    merged.update(data)
                    merged["interval_seconds"] = max(5, min(86400, int(merged.get("interval_seconds", 300))))
                    return merged
            except Exception as e:
                print(f"Error loading config file: {e}")
        return dict(DEFAULT_CONFIG)

    def save(self):
        """Saves current configuration to JSON file."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            try:
                appdata = os.environ.get('APPDATA', '')
                if appdata:
                    fallback_dir = os.path.join(appdata, "BushtwoBGS")
                    os.makedirs(fallback_dir, exist_ok=True)
                    self.config_path = os.path.join(fallback_dir, "config.json")
                    with open(self.config_path, "w", encoding="utf-8") as f:
                        json.dump(self.config, f, indent=4)
            except Exception:
                print(f"Error saving config file: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

    def update(self, key_values: dict):
        self.config.update(key_values)
        self.save()
