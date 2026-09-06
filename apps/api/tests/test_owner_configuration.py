from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def owner_headers() -> dict[str, str]:
    response = client.post('/auth/login', json={'email': 'owner@courtvision.local', 'password': 'courtvision-demo'})
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def test_owner_can_list_and_update_fields() -> None:
    headers = owner_headers()
    logo = 'data:image/png;base64,iVBORw0KGgo='
    club = client.patch('/owner/club', headers=headers, json={'name': 'Arena Norte', 'city': 'La Plata', 'logo_data_url': logo})
    assert club.status_code == 200
    assert club.json()['name'] == 'Arena Norte'
    assert club.json()['logo_data_url'] == logo
    assert client.get('/owner/dashboard', headers=headers).json()['club']['logo_data_url'] == logo

    fields = client.get('/owner/fields', headers=headers)
    assert fields.status_code == 200
    assert len(fields.json()['items']) == 4

    updated = client.patch('/owner/fields/field-04', headers=headers, json={'name': 'Cancha Arena', 'recording_enabled': False, 'detection_mode': 'arms_up'})
    assert updated.status_code == 200
    assert updated.json()['name'] == 'Cancha Arena'
    assert updated.json()['recording_enabled'] is True

    created = client.post('/owner/fields', headers=headers, json={
        'name': 'Cancha Patio',
        'sport_code': 'padel',
        'detection_mode': 'manual',
        'camera_name': 'PTZ Patio',
        'camera_host': '192.168.1.50',
        'camera_rtsp_port': 554,
        'camera_username': 'admin',
        'camera_password': 'secret-camera-password',
        'camera_stream_path': '/Streaming/Channels/101',
    })
    assert created.status_code == 200
    field_id = created.json()['id']
    assert created.json()['recording_enabled'] is True
    assert created.json()['camera']['name'] == 'PTZ Patio'
    assert created.json()['camera']['host'] == '192.168.1.50'
    assert created.json()['camera']['password_configured'] is True
    assert 'password' not in created.json()['camera']

    camera = client.post('/owner/cameras', headers=headers, json={'field_id': 'field-04', 'name': 'PTZ Patio 2', 'serial_number': 'CV-PTZ-100', 'stream_url': 'rtsp://edge.local/patio-2'})
    assert camera.status_code == 200
    assert camera.json()['field_id'] == 'field-04'
    camera_updated = client.patch(f"/owner/cameras/{camera.json()['id']}", headers=headers, json={
        'host': '10.0.0.50',
        'rtsp_port': 8554,
        'username': 'operator',
        'password': 'updated-camera-password',
        'stream_path': '/live/patio-2',
    })
    assert camera_updated.status_code == 200
    assert camera_updated.json()['stream_url'] == 'rtsp://10.0.0.50:8554/live/patio-2'
    assert camera_updated.json()['password_configured'] is True
    assert 'password' not in camera_updated.json()
    agent_token = client.post(f"/owner/cameras/{camera.json()['id']}/agent-token", headers=headers)
    assert agent_token.status_code == 200
    assert agent_token.json()['expires_in'] > 0
    config = client.get(f"/agent/cameras/{camera.json()['id']}/config", headers={'Authorization': f"Bearer {agent_token.json()['token']}"})
    assert config.status_code == 200
    assert config.json()['host'] == '10.0.0.50'
    assert config.json()['password'] == 'updated-camera-password'
    assert client.get('/owner/fields', headers=headers).json()['items'][-1]['camera']['name'] == 'PTZ Patio'

    removed_camera = client.delete(f"/owner/cameras/{camera.json()['id']}", headers=headers)
    assert removed_camera.status_code == 204
    removed_field = client.delete(f'/owner/fields/{field_id}', headers=headers)
    assert removed_field.status_code == 204


def test_tapo_stream_path_is_the_default_for_camera_connections() -> None:
    headers = owner_headers()
    field = client.post('/owner/fields', headers=headers, json={
        'name': 'Cancha Tapo',
        'camera_name': 'Tapo principal',
        'camera_host': '192.168.1.80',
    })
    assert field.status_code == 200
    assert field.json()['camera']['stream_path'] == '/stream1'
    assert field.json()['camera']['stream_url'] == 'rtsp://192.168.1.80:554/stream1'
    assert client.delete(f"/owner/fields/{field.json()['id']}", headers=headers).status_code == 204


def test_owner_can_manage_profile_and_notifications() -> None:
    headers = owner_headers()
    profile = client.get('/owner/profile', headers=headers)
    assert profile.status_code == 200
    assert profile.json()['role'] == 'owner'

    notifications = client.get('/owner/notifications', headers=headers)
    assert notifications.status_code == 200
    marked_all = client.post('/owner/notifications/read-all', headers=headers)
    assert marked_all.status_code == 200
    assert marked_all.json()['items'] == []
    deleted_all = client.delete('/owner/notifications', headers=headers)
    assert deleted_all.status_code == 204
    assert client.get('/owner/notifications', headers=headers).json()['items'] == []


def test_owner_can_configure_a_physical_button_per_field() -> None:
    headers = owner_headers()
    response = client.put('/owner/fields/field-02/button', headers=headers, json={'device_id': 'CV-BTN-02', 'secret': 'courtvision-button-02'})
    assert response.status_code == 200
    assert response.json()['button']['device_id'] == 'CV-BTN-02'
    assert 'secret' not in response.json()['button']


def test_camera_agent_token_rotation_and_unlink_revoke_previous_tokens() -> None:
    headers = owner_headers()
    camera = client.post(
        '/owner/cameras',
        headers=headers,
        json={'field_id': 'field-04', 'name': 'Cámara segura', 'stream_url': 'rtsp://edge.local/secure'},
    )
    assert camera.status_code == 200
    camera_id = camera.json()['id']
    first_token = camera.json()['agent_token']

    first_config = client.get(
        f'/agent/cameras/{camera_id}/config',
        headers={'Authorization': f'Bearer {first_token}'},
    )
    assert first_config.status_code == 200

    rotated = client.post(f'/owner/cameras/{camera_id}/agent-token', headers=headers)
    assert rotated.status_code == 200
    second_token = rotated.json()['token']
    assert second_token != first_token
    assert client.get(
        f'/agent/cameras/{camera_id}/config',
        headers={'Authorization': f'Bearer {first_token}'},
    ).status_code == 401
    assert client.get(
        f'/agent/cameras/{camera_id}/config',
        headers={'Authorization': f'Bearer {second_token}'},
    ).status_code == 200

    assert client.delete(f'/owner/cameras/{camera_id}/agent-link', headers=headers).status_code == 204
    assert client.get(
        f'/agent/cameras/{camera_id}/config',
        headers={'Authorization': f'Bearer {second_token}'},
    ).status_code == 401


def test_camera_agent_cannot_write_to_another_cameras_session() -> None:
    headers = owner_headers()
    session = client.post(
        '/public/fields/field-01/sessions',
        headers={'Idempotency-Key': 'cross-camera-session'},
        json={
            'display_name': 'Jugador Seguro',
            'phone_e164': '+5491112345678',
            'recording_consent': True,
            'messaging_consent': False,
        },
    )
    assert session.status_code == 201
    camera_two = client.post('/owner/cameras/camera-02/agent-token', headers=headers)
    assert camera_two.status_code == 200
    agent_headers = {'Authorization': f"Bearer {camera_two.json()['token']}"}

    upload = client.post(
        '/agent/uploads/presign',
        headers=agent_headers,
        json={
            'session_id': session.json()['session_id'],
            'media_type': 'recording',
            'content_type': 'video/mp4',
            'size_bytes': 1024,
            'checksum': 'a' * 64,
        },
    )
    assert upload.status_code == 403

    event = client.post(
        f"/agent/sessions/{session.json()['session_id']}/events",
        headers={**agent_headers, 'Idempotency-Key': 'cross-camera-event'},
        json={
            'source_id': 'cross-camera-source',
            'event_type': 'gesture',
            'occurred_at': '2026-09-02T12:00:00Z',
        },
    )
    assert event.status_code == 403
