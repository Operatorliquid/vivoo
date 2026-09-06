from datetime import datetime, timedelta, timezone
from uuid import UUID

from domain.schemas import PresignUploadRequest
from fastapi.testclient import TestClient
from main import app
from services.store import store


client = TestClient(app)


def test_qr_session_normalizes_an_argentine_local_whatsapp_number() -> None:
    response = client.post('/public/fields/demo-field-02/sessions', json={
        'display_name': 'Jose',
        'phone_e164': '2227 462048',
        'recording_consent': True,
        'messaging_consent': True,
    }, headers={'Idempotency-Key': 'argentine-phone-normalization-01'})

    assert response.status_code == 201
    assert store.players[UUID(response.json()['player_id'])].phone_e164 == '+5492227462048'


def test_qr_context_resolves_demo_field() -> None:
    response = client.get('/public/fields/demo-field-02')
    assert response.status_code == 200
    assert response.json()['field_name'] == 'Cancha 02'
    assert response.json()['camera_status'] == 'live'
    assert response.json()['active_session_id'] is None


def test_qr_context_resolves_the_scanned_field() -> None:
    response = client.get('/public/fields/field-03')
    assert response.status_code == 200
    assert response.json()['field_name'] == 'Cancha 03'
    assert response.json()['camera_status'] == 'ready'


def test_cannot_start_session_on_unavailable_field() -> None:
    payload = {
        'display_name': 'Martín',
        'phone_e164': '+5491155550118',
        'recording_consent': True,
        'messaging_consent': True,
    }
    response = client.post('/public/fields/field-04/sessions', json=payload, headers={'Idempotency-Key': 'maintenance-field-01'})
    assert response.status_code == 409
    assert 'no está disponible' in response.json()['detail']


def test_start_session_requires_consent_and_is_idempotent() -> None:
    payload = {
        'display_name': 'Martín',
        'phone_e164': '+5491155550118',
        'recording_consent': True,
        'messaging_consent': True,
    }
    headers = {'Idempotency-Key': 'test-session-martin-01'}
    first = client.post('/public/fields/demo-field-02/sessions', json=payload, headers=headers)
    second = client.post('/public/fields/demo-field-02/sessions', json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()['session_id'] == second.json()['session_id']
    assert first.json()['field_name'] == 'Cancha 02'
    assert first.json()['access_token'].startswith('pa.')
    assert second.json()['access_token'] == first.json()['access_token']


def test_player_access_page_exposes_full_recording_and_highlights() -> None:
    session = client.post('/public/fields/demo-field-02/sessions', json={
        'display_name': 'Lucía',
        'phone_e164': '+5491155550199',
        'recording_consent': True,
        'messaging_consent': True,
    }, headers={'Idempotency-Key': 'player-access-01'})
    assert session.status_code == 201
    access_token = session.json()['access_token']
    recording = client.post('/agent/uploads/presign', json={
        'session_id': session.json()['session_id'],
        'media_type': 'recording',
        'content_type': 'video/mp4',
        'size_bytes': 12,
        'checksum': 'b31e6b0dabd618d2d0279207bb6693bda956ab2a6fe629abb2f33bf236be9e71',
    }, headers={'Authorization': 'Bearer courtvision-local-agent'})
    assert recording.status_code == 200
    storage_key = recording.json()['storage_key']
    uploaded = client.put(f'/agent/dev/uploads/{storage_key}', content=b'whole-match', headers={'Authorization': 'Bearer courtvision-local-agent'})
    assert uploaded.status_code == 204
    completed = client.post('/agent/uploads/complete', json={
        'session_id': session.json()['session_id'],
        'media_type': 'recording',
        'storage_key': storage_key,
        'size_bytes': len(b'whole-match'),
        'checksum': 'b31e6b0dabd618d2d0279207bb6693bda956ab2a6fe629abb2f33bf236be9e71',
    }, headers={'Authorization': 'Bearer courtvision-local-agent'})
    assert completed.status_code == 204
    event = client.post(f"/agent/sessions/{session.json()['session_id']}/events", json={
        'source_id': 'player-access-event-01',
        'event_type': 'physical_button',
        'occurred_at': '2026-08-12T15:00:00Z',
        'source_storage_key': 'sessions/source.mp4',
    }, headers={'Idempotency-Key': 'player-access-event-01', 'Authorization': 'Bearer courtvision-local-agent'})
    page = client.get(f'/public/access/{access_token}')
    assert page.status_code == 200
    assert page.json()['recording_status'] == 'available'
    assert page.json()['recording_path'].endswith('/recording')
    assert page.json()['highlights'][0]['status'] == 'processing'


def test_recording_retry_tracks_the_new_checksum_until_completion() -> None:
    session = client.post('/public/fields/field-01/sessions', json={
        'display_name': 'Retry Recording',
        'phone_e164': '+5491155550177',
        'recording_consent': True,
        'messaging_consent': False,
    }, headers={'Idempotency-Key': 'recording-retry-session'})
    session_id = UUID(session.json()['session_id'])
    first = PresignUploadRequest(
        session_id=session_id, media_type='recording', content_type='video/mp4', size_bytes=10, checksum='a' * 64,
    )
    second = PresignUploadRequest(
        session_id=session_id, media_type='recording', content_type='video/mp4', size_bytes=20, checksum='b' * 64,
    )

    store.register_media_upload(first)
    recording = store.recordings[session_id]
    first_key = recording.storage_key
    store.register_media_upload(second)
    second_key = recording.storage_key

    assert second_key.endswith('b' * 64)
    assert first_key not in store.recordings_by_key
    assert store.recordings_by_key[second_key] == recording.id
    store.mark_media_upload_available(second_key)
    assert recording.status == 'available'


def test_event_is_idempotent_for_same_source() -> None:
    payload = {
        'display_name': 'Sofía',
        'phone_e164': '+5491155550119',
        'recording_consent': True,
        'messaging_consent': True,
    }
    session = client.post('/public/fields/demo-field-02/sessions', json=payload, headers={'Idempotency-Key': 'test-session-sofia-01'})
    session_id = session.json()['session_id']
    event = {'source_id': 'camera-02-event-001', 'event_type': 'manual', 'occurred_at': '2026-08-07T21:00:00Z', 'buffer_start_at': '2026-08-07T20:59:35Z', 'buffer_end_at': '2026-08-07T21:00:00Z', 'source_storage_key': 'segments/source.mp4'}
    headers = {'Idempotency-Key': 'camera-02-event-001', 'Authorization': 'Bearer courtvision-local-agent'}
    first = client.post(f'/agent/sessions/{session_id}/events', json=event, headers=headers)
    second = client.post(f'/agent/sessions/{session_id}/events', json=event, headers=headers)
    assert first.status_code == 202
    assert second.json()['highlight_id'] == first.json()['highlight_id']
    highlight = store.highlights[UUID(first.json()['highlight_id'])]
    assert highlight.duration_seconds == 25
    job = store.lease_next_job()
    assert job is not None
    assert job['source_storage_key'] == 'segments/source.mp4'


def test_abandoned_worker_lease_is_recovered() -> None:
    session = client.post('/public/fields/demo-field-02/sessions', json={
        'display_name': 'Lease Recovery',
        'phone_e164': '+5491155550125',
        'recording_consent': True,
        'messaging_consent': False,
    }, headers={'Idempotency-Key': 'lease-recovery-session-01'})
    event = client.post(f"/agent/sessions/{session.json()['session_id']}/events", json={
        'source_id': 'lease-recovery-event-01',
        'event_type': 'gesture',
        'occurred_at': '2026-08-07T21:00:00Z',
        'source_storage_key': 'segments/lease-recovery.mp4',
    }, headers={
        'Idempotency-Key': 'lease-recovery-event-01',
        'Authorization': 'Bearer courtvision-local-agent',
    })
    assert event.status_code == 202
    first = store.lease_next_job()
    assert first is not None
    record = store.processing_jobs[UUID(first['job_id'])]
    record.leased_at = datetime.now(timezone.utc) - timedelta(minutes=10)

    recovered = store.lease_next_job()

    assert recovered is not None
    assert recovered['job_id'] == first['job_id']
    assert recovered['attempts'] == 2


def test_agent_heartbeat_updates_camera_health() -> None:
    response = client.post('/agent/heartbeat', json={
        'device_id': 'CV-PTZ-002',
        'observed_at': '2026-08-07T21:00:00Z',
        'camera_status': 'offline',
        'agent_version': '0.1.0',
    }, headers={'Authorization': 'Bearer courtvision-local-agent'})
    assert response.status_code == 204
    assert client.get('/public/fields/demo-field-02').json()['camera_status'] == 'offline'


def test_agent_routes_require_agent_key() -> None:
    response = client.post('/agent/heartbeat', json={
        'device_id': 'CV-PTZ-002',
        'observed_at': '2026-08-07T21:00:00Z',
        'camera_status': 'online',
        'agent_version': '0.1.0',
    })
    assert response.status_code == 401


def test_worker_can_lease_and_complete_highlight_job() -> None:
    session_payload = {
        'display_name': 'Worker Test',
        'phone_e164': '+5491155550124',
        'recording_consent': True,
        'messaging_consent': False,
    }
    session = client.post('/public/fields/demo-field-02/sessions', json=session_payload, headers={'Idempotency-Key': 'worker-session-01'})
    event = {
        'source_id': 'worker-event-01',
        'event_type': 'manual',
        'occurred_at': '2026-08-07T21:00:00Z',
        'source_storage_key': 'segments/worker-source.mp4',
    }
    event_response = client.post(
        f"/agent/sessions/{session.json()['session_id']}/events",
        json=event,
        headers={'Idempotency-Key': 'worker-event-01', 'Authorization': 'Bearer courtvision-local-agent'},
    )
    job_response = client.get('/worker/jobs/next', headers={'Authorization': 'Bearer courtvision-local-worker'})
    assert event_response.status_code == 202
    assert job_response.status_code == 200
    job = job_response.json()
    completed = client.post(f"/worker/jobs/{job['job_id']}/complete", json={'succeeded': True, 'output_storage_key': job['output_storage_key']}, headers={'Authorization': 'Bearer courtvision-local-worker'})
    assert completed.status_code == 204
