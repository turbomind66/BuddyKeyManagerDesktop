from __future__ import annotations

import base64
import json
import secrets
import uuid
from typing import Any
from urllib.parse import quote

import httpx

from app.models import Credential


class APIError(RuntimeError):
    pass


class BuddyAPI:
    REGIONS = {
        'cn': {'name': '中国区', 'upstream': 'https://copilot.tencent.com', 'domain': 'www.codebuddy.cn', 'origin': 'https://www.codebuddy.cn'},
        'global': {'name': '国际区', 'upstream': 'https://www.codebuddy.ai', 'domain': 'www.codebuddy.ai', 'origin': 'https://www.workbuddy.ai'},
    }

    def __init__(self, region: str = 'cn', timeout: float = 30):
        if region not in self.REGIONS:
            raise APIError('不支持的区域')
        self.region = region
        self.config = self.REGIONS[region]
        self.timeout = timeout

    @staticmethod
    def _jwt_payload(token: str) -> dict[str, Any]:
        try:
            part = token.split('.')[1]
            part += '=' * (-len(part) % 4)
            return json.loads(base64.urlsafe_b64decode(part.encode()).decode())
        except Exception:
            return {}

    @staticmethod
    def _headers() -> dict[str, str]:
        rid = uuid.uuid4().hex
        return {'Accept': 'application/json, text/plain, */*', 'Content-Type': 'application/json', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache', 'X-Requested-With': 'XMLHttpRequest', 'X-Domain': 'www.codebuddy.ai', 'X-No-Authorization': 'true', 'X-No-User-Id': 'true', 'X-No-Enterprise-Id': 'true', 'X-No-Department-Info': 'true', 'X-Product': 'SaaS', 'User-Agent': 'CLI/2.63.2 CodeBuddy/2.63.2', 'X-Request-ID': rid, 'X-B3-TraceId': rid, 'X-B3-SpanId': secrets.token_hex(4), 'X-B3-Sampled': '1'}

    @staticmethod
    def _inner(data: dict[str, Any]) -> dict[str, Any]:
        current: Any = data.get('data')
        for _ in range(3):
            if isinstance(current, dict) and isinstance(current.get('data'), dict) and len(current) <= 1:
                current = current['data']
            else:
                break
        return current if isinstance(current, dict) else {}

    async def create_auth_session(self, platform: str = 'CLI') -> tuple[str, str]:
        nonce = secrets.token_hex(8)
        url = f"{self.config['upstream']}/v2/plugin/auth/state?platform={quote(platform)}&nonce={nonce}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=self._headers(), json={'nonce': nonce})
        if response.status_code >= 400:
            raise APIError(f'创建授权失败：HTTP {response.status_code}')
        body = response.json()
        inner = self._inner(body)
        auth_url, state = inner.get('authUrl'), inner.get('state')
        if not auth_url or not state:
            raise APIError(f'授权接口响应缺少 authUrl/state：{response.text[:200]}')
        return auth_url, state

    async def poll_token(self, state: str) -> dict[str, Any] | None:
        url = f"{self.config['upstream']}/v2/plugin/auth/token?state={quote(state)}"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, headers=self._headers())
        body = response.json()
        if body.get('code') == 11217:
            return None
        if response.status_code >= 400 or (body.get('code') not in (None, 0)):
            raise APIError(f'轮询失败：{body.get("msg") or response.text[:200]}')
        inner = self._inner(body)
        if not inner.get('accessToken'):
            raise APIError('响应缺少 accessToken')
        return {'access_token': inner['accessToken'], 'refresh_token': inner.get('refreshToken', ''), 'expires_in': inner.get('expiresIn', 0), 'domain': inner.get('domain') or self.config['domain']}

    def credential_from_token(self, token: dict[str, Any]) -> Credential:
        payload = self._jwt_payload(token['access_token'])
        uid = str(payload.get('sub') or '')
        nickname = str(payload.get('preferred_username') or payload.get('email') or uid[:8])
        if not uid:
            raise APIError('无法从 access_token 解析 uid')
        return Credential.from_token(token, uid, nickname, self.region, token.get('domain') or self.config['domain'])

    async def ping(self, credential: Credential) -> tuple[bool, bool, str]:
        url = f"{self.config['upstream']}/v2/chat/completions"
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*', 'Authorization': f'Bearer {credential.access_token}', 'X-User-Id': credential.uid, 'X-Domain': credential.domain, 'X-Product': 'SaaS', 'User-Agent': 'CLI/2.63.2 CodeBuddy/2.63.2'}
        body = {'model': 'auto', 'stream': False, 'messages': [{'role': 'user', 'content': '你好'}]}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, headers=headers, json=body)
            if response.status_code == 200: return True, False, '有效'
            if response.status_code == 403: return False, True, '安全审核/风控拦截'
            if response.status_code == 401: return False, False, '未授权或 Token 过期'
            return False, False, f'HTTP {response.status_code}'
        except httpx.HTTPError as exc:
            return False, False, f'网络错误：{exc}'

    async def balance(self, credential: Credential) -> int:
        # 与原版一致的资源接口；仅返回聚合剩余值。
        url = f"{self.config['upstream']}/v2/billing/meter/get-user-resource"
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*', 'Authorization': f'Bearer {credential.access_token}', 'X-User-Id': credential.uid, 'X-Domain': credential.domain, 'X-Product': 'SaaS', 'User-Agent': 'CLI/2.63.2 CodeBuddy/2.63.2'}
        body = {'PageNumber': 1, 'PageSize': 100, 'ProductCode': 'p_tcaca', 'Status': [0, 3]}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=body)
        if response.status_code >= 400: raise APIError(f'余额查询失败：HTTP {response.status_code}')
        raw = response.json()
        accounts = (((raw.get('data') or {}).get('Response') or {}).get('Data') or {}).get('Accounts') or []
        total = 0
        for account in accounts:
            cycle_size = int(account.get('CycleCapacitySize') or 0)
            remain = int(account.get('CycleCapacityRemain') or account.get('CapacityRemain') or 0)
            total += max(remain if cycle_size else int(account.get('CapacityRemain') or remain), 0)
        return total
