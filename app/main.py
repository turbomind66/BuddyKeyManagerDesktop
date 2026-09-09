from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import __version__, config
from app.models import AuthSession, Credential, STATUS_NAMES, now
from app.services.oauth import APIError, BuddyAPI
from app.services.push import PushClient, PushError
from app.services.secure_store import SecureJsonStore
from app.services.sms import EjiemaProvider, SmsError


class SessionRequest(BaseModel):
    region: str = 'cn'
    platform: str = 'CLI'


class NoteRequest(BaseModel):
    note: str = Field(default='', max_length=200)


class SmsSettingsRequest(BaseModel):
    provider: str = 'ejiema'
    token: str = ''


class SmsRequest(BaseModel):
    keyword: str = ''
    phone: str = ''


class PushSettingsRequest(BaseModel):
    base_url: str = ''
    password: str = ''


class AppState:
    def __init__(self) -> None:
        self.secure = SecureJsonStore(config.KEY_FILE)
        self.credentials: dict[str, Credential] = {}
        self.sessions: dict[str, AuthSession] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        self.load()

    def load(self) -> None:
        raw_credentials = self.secure.read(config.CREDENTIALS_FILE, [])
        for item in raw_credentials:
            try:
                credential = Credential(**item)
                self.credentials[f'{credential.region}:{credential.uid}'] = credential
            except TypeError:
                continue
        if config.SESSIONS_FILE.exists():
            try:
                data = json.loads(config.SESSIONS_FILE.read_text(encoding='utf-8'))
                self.sessions = {item['id']: AuthSession(**item) for item in data}
            except (OSError, ValueError, TypeError):
                self.sessions = {}
        for session in self.sessions.values():
            if session.status in {'pending', 'polling'} and now() - session.created_at < 600:
                session.status = 'pending'
            elif session.status in {'pending', 'polling'}:
                session.status = 'failed'
                session.last_error = '等待登录超时'
        self.persist()

    def persist(self) -> None:
        self.secure.write(config.CREDENTIALS_FILE, [credential.__dict__ for credential in self.credentials.values()])
        config.SESSIONS_FILE.write_text(json.dumps([session.to_dict() for session in self.sessions.values()], ensure_ascii=False, indent=2), encoding='utf-8')

    def settings(self) -> dict[str, Any]:
        return self.secure.read(config.SETTINGS_FILE, {'sms_provider': 'ejiema', 'sms_token': '', 'push_base_url': '', 'push_password': ''})

    def save_settings(self, data: dict[str, Any]) -> None:
        current = self.settings()
        current.update(data)
        self.secure.write(config.SETTINGS_FILE, current)

    def public_session(self, session: AuthSession) -> dict[str, Any]:
        data = session.to_dict()
        data['status_name'] = STATUS_NAMES.get(session.status, session.status)
        data['region_name'] = BuddyAPI.REGIONS.get(session.region, {}).get('name', session.region)
        data.pop('auth_url', None)
        data.pop('state', None)
        return data

    async def poll_session(self, session_id: str) -> None:
        session = self.sessions.get(session_id)
        if not session:
            return

        session.status = 'polling'
        self.persist()
        api = BuddyAPI(session.region)
        failures = 0

        for _ in range(100):
            try:
                await asyncio.sleep(3)
                token = await api.poll_token(session.state)
                if token is None:
                    continue

                credential = api.credential_from_token(token)
                key = f'{credential.region}:{credential.uid}'
                old = self.credentials.get(key)
                if old:
                    credential.note = old.note
                    credential.balance = old.balance
                    credential.alive = old.alive
                    credential.risk_controlled = old.risk_controlled
                    credential.saved_at = old.saved_at

                self.credentials[key] = credential
                session.status = 'completed'
                session.account_uid = credential.uid
                session.token_expires_at = credential.expires_at
                session.last_error = None
                self.persist()
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failures += 1
                session.last_error = str(exc)
                # 单次轮询错误不应立即结束会话；连续错误达到阈值才失败。
                if failures >= 3:
                    session.status = 'failed'
                    self.persist()
                    return

        if session.status != 'completed':
            session.status = 'failed'
            session.last_error = session.last_error or '等待登录超时'
        self.persist()


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    for session in state.sessions.values():
        if session.status == 'pending' and now() - session.created_at < 600:
            state.tasks[session.id] = asyncio.create_task(state.poll_session(session.id))
    yield
    for task in state.tasks.values():
        task.cancel()


app = FastAPI(title='BuddyKeyManager Desktop', version=__version__, lifespan=lifespan)
app.mount('/static', StaticFiles(directory=Path(__file__).parent / 'static'), name='static')


def get_credential(uid: str) -> Credential:
    decoded = unquote(uid)
    credential = state.credentials.get(decoded)
    if credential:
        return credential
    # 兼容旧版前端仅传 uid 的调用；如果跨区域存在同 uid，则拒绝猜测。
    matches = [value for value in state.credentials.values() if value.uid == decoded]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise HTTPException(404, '凭证不存在')
    raise HTTPException(409, '不同区域存在相同 uid，请使用带区域的凭证标识')


@app.get('/')
async def index():
    return FileResponse(Path(__file__).parent / 'templates' / 'index.html')


@app.get('/api/health')
async def health():
    return {'ok': True, 'version': __version__, 'region_count': len(BuddyAPI.REGIONS)}


@app.get('/api/settings')
async def get_settings():
    settings = state.settings()
    return {
        'sms_provider': settings.get('sms_provider', 'ejiema'),
        'sms_configured': bool(settings.get('sms_token')),
        'push_configured': bool(settings.get('push_base_url') and settings.get('push_password')),
        'push_base_url': settings.get('push_base_url', ''),
    }


@app.put('/api/settings/sms')
async def put_sms_settings(payload: SmsSettingsRequest):
    if payload.provider != 'ejiema':
        raise HTTPException(400, '暂不支持该接码平台')
    current = state.settings()
    token = payload.token.strip() or current.get('sms_token', '')
    state.save_settings({'sms_provider': payload.provider, 'sms_token': token})
    return {'ok': True}


@app.put('/api/settings/push')
async def put_push_settings(payload: PushSettingsRequest):
    base_url = payload.base_url.strip().rstrip('/')
    current = state.settings()
    password = payload.password or current.get('push_password', '')
    state.save_settings({'push_base_url': base_url, 'push_password': password})
    return {'ok': True, 'configured': bool(base_url and password)}


@app.get('/api/auth/sessions')
async def list_sessions():
    return [state.public_session(s) for s in sorted(state.sessions.values(), key=lambda x: x.created_at, reverse=True)]


@app.post('/api/auth/sessions')
async def create_session(payload: SessionRequest):
    try:
        api = BuddyAPI(payload.region)
        auth_url, oauth_state = await api.create_auth_session(payload.platform)
    except (APIError, ValueError) as exc:
        raise HTTPException(502, str(exc)) from exc
    session = AuthSession(id=str(uuid.uuid4()), state=oauth_state, auth_url=auth_url, region=payload.region, platform=payload.platform, created_at=now())
    state.sessions[session.id] = session
    state.persist()
    state.tasks[session.id] = asyncio.create_task(state.poll_session(session.id))
    if config.OPEN_BROWSER:
        threading.Thread(target=webbrowser.open, args=(auth_url,), daemon=True).start()
    return {'id': session.id, 'auth_url': auth_url}


@app.delete('/api/auth/sessions/{session_id}')
async def delete_session(session_id: str):
    task = state.tasks.pop(session_id, None)
    if task: task.cancel()
    state.sessions.pop(session_id, None)
    state.persist()
    return {'ok': True}


@app.get('/api/credentials')
async def list_credentials():
    values = sorted(state.credentials.values(), key=lambda c: (not bool(c.note), -c.saved_at))
    return [credential.to_public_dict() for credential in values]


@app.get('/api/credentials/export')
async def export_credentials():
    # 仅在用户主动点击导出时提供敏感字段。
    payload = json.dumps([credential.to_export_dict() for credential in state.credentials.values()], ensure_ascii=False, indent=2).encode('utf-8')
    export_file = config.DATA_DIR / 'credentials-export.json'
    export_file.write_bytes(payload)
    return FileResponse(export_file, filename='buddy-credentials.json', media_type='application/json')


@app.patch('/api/credentials/{uid}')
async def update_credential(uid: str, payload: NoteRequest):
    credential = get_credential(uid)
    credential.note = payload.note.strip() or None
    state.persist()
    return credential.to_public_dict()


@app.delete('/api/credentials/{uid}')
async def delete_credential(uid: str):
    credential = get_credential(uid)
    state.credentials.pop(f'{credential.region}:{credential.uid}', None)
    state.persist()
    return {'ok': True}


@app.post('/api/credentials/{uid}/ping')
async def ping_credential(uid: str):
    credential = get_credential(uid)
    ok, risk, message = await BuddyAPI(credential.region).ping(credential)
    credential.alive, credential.risk_controlled = ok, risk
    state.persist()
    return {'ok': ok, 'risk_controlled': risk, 'message': message}


@app.post('/api/credentials/ping-all')
async def ping_all():
    results = []
    for credential in list(state.credentials.values()):
        ok, risk, message = await BuddyAPI(credential.region).ping(credential)
        credential.alive, credential.risk_controlled = ok, risk
        results.append({'uid': credential.uid, 'ok': ok, 'risk': risk, 'message': message})
    state.persist()
    return results


@app.post('/api/credentials/{uid}/push')
async def push_credential(uid: str):
    credential = get_credential(uid)
    settings = state.settings()
    try:
        result = await PushClient(settings.get('push_base_url', ''), settings.get('push_password', '')).push(credential)
    except (PushError, httpx.HTTPError) as exc:
        raise HTTPException(502, str(exc)) from exc
    return {'ok': True, 'result': result}


@app.post('/api/credentials/push-all')
async def push_all_credentials():
    settings = state.settings()
    client = PushClient(settings.get('push_base_url', ''), settings.get('push_password', ''))
    results = []
    for credential in list(state.credentials.values()):
        try:
            result = await client.push(credential)
            results.append({'uid': credential.uid, 'ok': True, 'result': result})
        except (PushError, httpx.HTTPError) as exc:
            results.append({'uid': credential.uid, 'ok': False, 'message': str(exc)})
    return results


@app.post('/api/credentials/{uid}/balance')
async def query_balance(uid: str):
    credential = get_credential(uid)
    try:
        total = await BuddyAPI(credential.region).balance(credential)
    except (APIError, httpx.HTTPError) as exc:
        raise HTTPException(502, str(exc)) from exc
    credential.balance = total
    state.persist()
    return {'total': total}


def provider() -> EjiemaProvider:
    settings = state.settings()
    if settings.get('sms_provider', 'ejiema') != 'ejiema':
        raise HTTPException(400, '暂不支持该接码平台')
    return EjiemaProvider(settings.get('sms_token', ''))


@app.post('/api/sms/get_phone')
async def sms_get_phone(payload: SmsRequest):
    try:
        phone = await provider().get_phone(payload.keyword)
        return {'phone': phone, 'message': f'取号成功：{phone}'}
    except SmsError as exc: raise HTTPException(502, str(exc)) from exc


@app.post('/api/sms/get_message')
async def sms_get_message(payload: SmsRequest):
    try:
        message = await provider().get_message(payload.phone, payload.keyword)
        return {'message': message, 'code': EjiemaProvider.extract_code(message)}
    except SmsError as exc: raise HTTPException(502, str(exc)) from exc


@app.post('/api/sms/release')
async def sms_release(payload: SmsRequest):
    try: return {'message': await provider().release(payload.phone)}
    except SmsError as exc: raise HTTPException(502, str(exc)) from exc


@app.post('/api/sms/block')
async def sms_block(payload: SmsRequest):
    try: return {'message': await provider().block(payload.phone)}
    except SmsError as exc: raise HTTPException(502, str(exc)) from exc


def run() -> None:
    print(f'BuddyKeyManager Desktop: http://{config.HOST}:{config.PORT}')
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level='info')
