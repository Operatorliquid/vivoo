from fastapi.testclient import TestClient

from auth.account_service import AccountService, MemoryAccountRepository, hash_password, verify_password
from main import app


client = TestClient(app)


def test_owner_login_and_protected_dashboard() -> None:
    login = client.post('/auth/login', json={'email': 'owner@courtvision.local', 'password': 'courtvision-demo'})
    assert login.status_code == 200
    token = login.json()['access_token']

    unauthenticated = client.get('/owner/dashboard')
    assert unauthenticated.status_code == 401

    dashboard = client.get('/owner/dashboard', headers={'Authorization': f'Bearer {token}'})
    assert dashboard.status_code == 200
    assert dashboard.json()['club']['name'] == ''
    assert len(dashboard.json()['cameras']) == 4


def test_owner_login_rejects_invalid_credentials() -> None:
    response = client.post('/auth/login', json={'email': 'owner@courtvision.local', 'password': 'not-the-password'})
    assert response.status_code == 401


def test_owner_session_is_opaque_rotatable_and_revocable() -> None:
    login = client.post('/auth/login', json={'email': 'owner@courtvision.local', 'password': 'courtvision-demo'})
    token = login.json()['access_token']
    assert token.startswith('cv_session_')
    assert 'owner@courtvision.local' not in token

    rotated = client.post('/auth/refresh', headers={'Authorization': f'Bearer {token}'})
    assert rotated.status_code == 200
    replacement = rotated.json()['access_token']
    assert replacement != token
    assert client.get('/auth/me', headers={'Authorization': f'Bearer {token}'}).status_code == 401
    assert client.get('/auth/me', headers={'Authorization': f'Bearer {replacement}'}).status_code == 200

    assert client.post('/auth/logout', headers={'Authorization': f'Bearer {replacement}'}).status_code == 204
    assert client.get('/auth/me', headers={'Authorization': f'Bearer {replacement}'}).status_code == 401


def test_passwords_are_salted_and_recovery_tokens_are_single_use() -> None:
    first = hash_password('a-secure-password')
    second = hash_password('a-secure-password')
    assert first != second
    assert 'a-secure-password' not in first
    assert verify_password('a-secure-password', first)
    assert not verify_password('wrong-password', first)

    service = AccountService()
    assert isinstance(service.repository, MemoryAccountRepository)
    before = service.authenticate('owner@courtvision.local', 'courtvision-demo')
    assert before is not None
    active_session = service.issue_session(before)
    reset_token = service.request_password_reset('owner@courtvision.local')
    assert reset_token is not None
    assert service.reset_password(reset_token, 'a-new-secure-password')
    assert not service.reset_password(reset_token, 'another-secure-password')
    assert service.verify_session(active_session) is None
    assert service.authenticate('owner@courtvision.local', 'courtvision-demo') is None
    assert service.authenticate('owner@courtvision.local', 'a-new-secure-password') is not None
