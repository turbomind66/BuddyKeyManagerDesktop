from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet


class SecureJsonStore:
    """本机配置加密存储。密钥文件权限尽量收紧；仍不应替代系统级凭据管理。"""

    def __init__(self, key_path: Path):
        self.key_path = key_path
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.exists():
            self.key = self.key_path.read_bytes()
        else:
            self.key = Fernet.generate_key()
            self.key_path.write_bytes(self.key)
            try:
                os.chmod(self.key_path, 0o600)
            except OSError:
                pass
        self.cipher = Fernet(self.key)

    def read(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            raw = self.cipher.decrypt(path.read_bytes())
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return default

    def write(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = self.cipher.encrypt(json.dumps(value, ensure_ascii=False).encode('utf-8'))
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_bytes(encrypted)
        temp.replace(path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
