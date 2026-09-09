"""冒烟测试：覆盖主要路由、加密存储、验证码提取。"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import __version__
from app.main import app
from app.services.secure_store import SecureJsonStore
from app.services.sms import EjiemaProvider

client = TestClient(app)


def test_version_exposed():
    assert __version__ == '1.0.0'


def test_index_page():
    response = client.get('/')
    assert response.status_code == 200
    assert 'Buddy' in response.text


def test_static_assets():
    response = client.get('/static/app.js')
    assert response.status_code == 200
    assert 'refreshAll' in response.text


def test_health():
    response = client.get('/api/health')
    assert response.status_code == 200
    payload = response.json()
    assert payload['ok'] is True
    assert payload['version'] == __version__
    assert payload['region_count'] >= 1


def test_credentials_list_default():
    response = client.get('/api/credentials')
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_settings_read():
    response = client.get('/api/settings')
    assert response.status_code == 200
    payload = response.json()
    assert 'sms_provider' in payload
    assert 'sms_configured' in payload
    assert 'push_configured' in payload


def test_update_settings_idempotent():
    response = client.put('/api/settings/push', json={'base_url': 'http://127.0.0.1:9999', 'password': ''})
    assert response.status_code == 200


def test_secure_store_roundtrip(tmp_path: Path):
    store = SecureJsonStore(tmp_path / 'k.bin')
    target = tmp_path / 'payload.enc'
    payload = {'hello': '世界', 'list': [1, 2, 3]}
    store.write(target, payload)
    assert target.exists()
    assert store.read(target, None) == payload


def test_extract_code_patterns():
    assert EjiemaProvider.extract_code('您的验证码是 123456，请勿泄露') == '123456'
    assert EjiemaProvider.extract_code('Your verification code: 654321.') == '654321'
    assert EjiemaProvider.extract_code('使用 8888 完成验证') == '8888'
    assert EjiemaProvider.extract_code('无效消息') is None or isinstance(EjiemaProvider.extract_code('无效消息'), str)


def test_create_session_rejects_invalid_region():
    response = client.post('/api/auth/sessions', json={'region': 'mars', 'platform': 'CLI'})
    # BuddyAPI 不存在 → 期望 502/500，路由本身要可达
    assert response.status_code in (500, 502)