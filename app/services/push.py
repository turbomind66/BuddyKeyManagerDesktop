from __future__ import annotations

import httpx

from app.models import Credential


class PushError(RuntimeError):
    pass


class PushClient:
    def __init__(self, base_url: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.password = password

    async def push(self, credential: Credential) -> dict:
        if not self.base_url or not self.password:
            raise PushError('未配置 Buddy2API 地址或密码')
        async with httpx.AsyncClient(timeout=30) as client:
            login = await client.post(f'{self.base_url}/admin/login', json={'password': self.password})
            if login.status_code >= 400: raise PushError(f'管理端登录失败：HTTP {login.status_code}')
            cookies = login.cookies
            payload = {'access_token': credential.access_token, 'refresh_token': credential.refresh_token, 'token_type': 'Bearer', 'expires_at': credential.expires_at, 'domain': credential.domain, 'nickname': credential.nickname}
            result = await client.post(f'{self.base_url}/admin/account/import', json=payload, cookies=cookies)
            if result.status_code >= 400: raise PushError(f'导入失败：HTTP {result.status_code}')
            return result.json()
