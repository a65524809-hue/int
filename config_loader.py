"""Load and validate config from config.json."""
import json
import os
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DEFAULTS = {
    "gemini_api_key": "",
    "hotkey_record": ["alt", "r"],
    "hotkey_clear": ["alt", "c"],
    "llm_model": "gemini-2.5-flash",
    "transparency": 0.8,
    "stt_provider": "gemini",
    "exclude_from_capture": True,
}


def load_config():
    """Load config from config.json; merge with defaults."""
    cfg = dict(DEFAULTS)
    if os.path.isfile(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            cfg.update(loaded)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[Config] Error reading config: {e}", file=sys.stderr)
    return cfg
