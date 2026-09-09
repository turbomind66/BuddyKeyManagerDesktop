from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv('BKM_DATA_DIR', BASE_DIR / 'data')).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

HOST = os.getenv('BKM_HOST', '127.0.0.1')
PORT = int(os.getenv('BKM_PORT', '8765'))
OPEN_BROWSER = os.getenv('BKM_OPEN_BROWSER', 'true').lower() in {'1', 'true', 'yes', 'on'}

CREDENTIALS_FILE = DATA_DIR / 'credentials.enc'
SESSIONS_FILE = DATA_DIR / 'sessions.json'
SETTINGS_FILE = DATA_DIR / 'settings.enc'
KEY_FILE = DATA_DIR / '.key'
