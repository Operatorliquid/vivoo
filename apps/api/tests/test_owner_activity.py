from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def owner_headers() -> dict[str, str]:
    response = client.post('/auth/login', json={
        'email': 'owner@courtvision.local',
        'password': 'courtvision-demo',
    })
    return {'Authorization': f"Bearer {response.json()['access_token']}"}


def test_activity_tracks_recording_highlight_and_delivery_with_targets() -> None:
    session = client.post('/public/fields/field-01/sessions', json={
        'display_name': 'Martina',
        'phone_e164': '+5491155550190',
        'recording_consent': True,
        'messaging_consent': True,
    }, headers={'Idempotency-Key': 'activity-session-01'})
    assert session.status_code == 201

    captured = client.post(f"/agent/sessions/{session.json()['session_id']}/events", json={
        'source_id': 'activity-event-01',
        'event_type': 'physical_button',
        'occurred_at': '2026-09-02T17:00:00Z',
        'source_storage_key': 'segments/activity-source.mp4',
    }, headers={
        'Idempotency-Key': 'activity-event-01',
        'Authorization': 'Bearer courtvision-local-agent',
    })
    assert captured.status_code == 202

    job = client.get('/worker/jobs/next', headers={'Authorization': 'Bearer courtvision-local-worker'}).json()
    completed = client.post(f"/worker/jobs/{job['job_id']}/complete", json={
        'succeeded': True,
        'output_storage_key': job['output_storage_key'],
    }, headers={'Authorization': 'Bearer courtvision-local-worker'})
    assert completed.status_code == 204
    delivered = client.post(f"/worker/jobs/{job['job_id']}/delivery", json={
        'phone_e164': '+5491155550190',
        'display_name': 'Martina',
        'succeeded': True,
    }, headers={'Authorization': 'Bearer courtvision-local-worker'})
    assert delivered.status_code == 204

    activity = client.get('/owner/activity', headers=owner_headers())
    assert activity.status_code == 200
    items = activity.json()['items']
    assert any(item['kind'] == 'recording' and item['title'] == 'Grabación iniciada' and item['href'] == '/fields/field-01' for item in items)
    assert any(item['kind'] == 'highlight' and item['highlight_id'] == captured.json()['highlight_id'] and item['href'].startswith('/library?highlight=') for item in items)
    assert any(item['kind'] == 'delivery' and item['status'] == 'success' and item['title'] == 'Highlight enviado por WhatsApp' for item in items)


def test_activity_records_failed_delivery_without_failing_the_video() -> None:
    session = client.post('/public/fields/field-01/sessions', json={
        'display_name': 'Tomás',
        'phone_e164': '+5491155550191',
        'recording_consent': True,
        'messaging_consent': True,
    }, headers={'Idempotency-Key': 'activity-session-02'})
    event = client.post(f"/agent/sessions/{session.json()['session_id']}/events", json={
        'source_id': 'activity-event-02',
        'event_type': 'gesture',
        'occurred_at': '2026-09-02T17:05:00Z',
        'source_storage_key': 'segments/activity-source-02.mp4',
    }, headers={'Idempotency-Key': 'activity-event-02', 'Authorization': 'Bearer courtvision-local-agent'})
    job = client.get('/worker/jobs/next', headers={'Authorization': 'Bearer courtvision-local-worker'}).json()
    client.post(f"/worker/jobs/{job['job_id']}/complete", json={
        'succeeded': True, 'output_storage_key': job['output_storage_key'],
    }, headers={'Authorization': 'Bearer courtvision-local-worker'})
    failed = client.post(f"/worker/jobs/{job['job_id']}/delivery", json={
        'phone_e164': '+5491155550191',
        'display_name': 'Tomás',
        'succeeded': False,
        'error': 'Evolution API no está disponible',
    }, headers={'Authorization': 'Bearer courtvision-local-worker'})
    assert failed.status_code == 204

    items = client.get('/owner/activity', headers=owner_headers()).json()['items']
    failure = next(item for item in items if item['kind'] == 'delivery')
    assert failure['status'] == 'error'
    assert failure['highlight_id'] == event.json()['highlight_id']
    assert 'Evolution' in failure['detail']
