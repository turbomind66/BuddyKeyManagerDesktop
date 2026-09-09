from __future__ import annotations

import re
from typing import Any

import httpx


class SmsError(RuntimeError):
    pass


class EjiemaProvider:
    name = 'ejiema'
    base_url = 'https://api.ejiema.com/zc/data.php'

    def __init__(self, token: str):
        self.token = token

    async def call(self, params: dict[str, str]) -> str:
        if not self.token:
            raise SmsError('未设置接码 Token')
        params = {'token': self.token, **params}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(self.base_url, params=params)
            if response.status_code >= 400: raise SmsError(f'HTTP {response.status_code}')
            text = response.text.strip()
            if text.startswith('ERROR:'): raise SmsError(text)
            return text
        except httpx.HTTPError as exc:
            raise SmsError(f'网络错误：{exc}') from exc

    async def get_phone(self, keyword: str) -> str:
        return await self.call({'code': 'getPhone', 'keyWord': keyword, 'cardType': '全部'})

    async def get_message(self, phone: str, keyword: str) -> str:
        return await self.call({'code': 'getMsg', 'phone': phone, 'keyWord': keyword})

    async def release(self, phone: str) -> str:
        return await self.call({'code': 'release', 'phone': phone})

    async def block(self, phone: str) -> str:
        return await self.call({'code': 'block', 'phone': phone})

    @staticmethod
    def extract_code(message: str) -> str | None:
        patterns = [r'验证码\s*(?:是|为|：|:)?\s*([0-9]{4,8})', r'code\s*(?:是|为|：|:)?\s*([0-9]{4,8})', r'([0-9]{6})(?:[，,。\s]|$)']
        for pattern in patterns:
            match = re.search(pattern, message, re.I)
            if match: return match.group(1)
        parts = re.findall(r'\d{4,8}', message)
        return parts[-1] if parts else None
