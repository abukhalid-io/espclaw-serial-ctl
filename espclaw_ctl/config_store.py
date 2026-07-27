"""Small persisted-preferences store shared by the CLI and GUI.

Only ever stores non-secret convenience fields (last serial port, last SSID
used) — never WiFi passwords or API keys. See README "Security Notes".
"""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".espclaw_ctl"
CONFIG_PATH = CONFIG_DIR / "config.json"


def load():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return {}


def save(**updates):
    data = load()
    data.update(updates)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
