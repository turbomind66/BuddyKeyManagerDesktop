from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import time
import uuid


def now() -> int:
    return int(time.time())


@dataclass
class AuthSession:
    id: str
    state: str
    auth_url: str
    region: str
    platform: str
    created_at: int
    status: str = 'pending'
    account_uid: str | None = None
    last_error: str | None = None
    token_expires_at: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Credential:
    uid: str
    enterprise_id: str
    nickname: str
    access_token: str
    refresh_token: str
    expires_at: int
    domain: str
    region: str = 'cn'
    note: str | None = None
    saved_at: int = 0
    balance: int = -1
    alive: bool | None = None
    risk_controlled: bool = False

    @classmethod
    def from_token(cls, token: dict[str, Any], uid: str, nickname: str, region: str, domain: str) -> 'Credential':
        current = now()
        expires_in = int(token.get('expires_in') or 0)
        return cls(
            uid=uid,
            enterprise_id='',
            nickname=nickname or uid[:8],
            access_token=token['access_token'],
            refresh_token=token.get('refresh_token', ''),
            expires_at=current + (expires_in or 60 * 24 * 3600),
            domain=domain,
            region=region,
            saved_at=current,
        )

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop('access_token', None)
        data.pop('refresh_token', None)
        data['region_name'] = '中国区' if self.region == 'cn' else '国际区'
        data['key'] = f'{self.region}:{self.uid}'
        return data

    def to_export_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['region_name'] = '中国区' if self.region == 'cn' else '国际区'
        return data


STATUS_NAMES = {'pending': '等待登录', 'polling': '等待授权结果', 'completed': '已完成', 'failed': '失败'}
