"""BuddyKeyManagerDesktop —— GitHub REST 推送脚本（受限网络环境用）。

不走 git push，直接调 GitHub Contents API 逐文件 PUT。
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import httpx
import winreg

OWNER = "turbomind66"
REPO = "BuddyKeyManagerDesktop"
BRANCH = "main"
ROOT = Path(r"E:\OFFICE\00Py_project\WorkBuddy\BuddyKeyManagerDesktop")

EXCLUDE_DIRS = {".venv", ".git", "__pycache__", ".workbuddy", "data", ".pytest_cache"}
EXCLUDE_FILE_NAMES = {".env"}


def get_pat() -> str:
    """从注册表读取用户级环境变量 workbuddy-github。"""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
        value, _ = winreg.QueryValueEx(key, "workbuddy-github")
    if not value:
        raise SystemExit("PAT 为空")
    return value


def list_local_files() -> list:
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if rel.name in EXCLUDE_FILE_NAMES:
            continue
        files.append(path)
    files.sort(key=lambda p: str(p.relative_to(ROOT)).lower())
    return files


def put_file(client, rel_path: str, content: bytes):
    api = f"/repos/{OWNER}/{REPO}/contents/{rel_path}"
    head = client.get(api, params={"ref": BRANCH})
    body = {
        "message": f"feat: add {rel_path}",
        "content": base64.b64encode(content).decode(),
        "branch": BRANCH,
    }
    if head.status_code == 200 and isinstance(head.json(), dict) and "sha" in head.json():
        body["sha"] = head.json()["sha"]
        body["message"] = f"chore: update {rel_path}"
    put = client.put(api, json=body, timeout=60)
    if put.status_code in (200, 201):
        data = put.json()
        commit_sha = (data.get("commit") or {}).get("sha", "")[:8]
        return put.status_code, f"ok {commit_sha}"
    return put.status_code, put.text[:240]


def main() -> int:
    pat = get_pat()
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bkm-desktop-uploader",
    }
    files = list_local_files()
    print(f"[scan] {len(files)} files to push", flush=True)
    ok = fail = 0
    with httpx.Client(base_url="https://api.github.com", headers=headers, timeout=60) as client:
        for idx, path in enumerate(files, 1):
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            content = path.read_bytes()
            status, info = put_file(client, rel, content)
            tag = "OK" if status in (200, 201) else "FAIL"
            print(f"[{tag:>4}] {status} {rel}  ({idx}/{len(files)}) {info[:60]}", flush=True)
            if status in (200, 201):
                ok += 1
            else:
                fail += 1
            time.sleep(0.15)
    print(f"\n[done] ok={ok} fail={fail}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())