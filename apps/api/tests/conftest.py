"""Shared API test fixtures will be added with the persistence slice."""

from copy import deepcopy

import pytest

from services.store import store


@pytest.fixture(autouse=True)
def reset_local_store():
    initial_fields = deepcopy(store.fields)
    initial_cameras = deepcopy(store.cameras)
    initial_club = deepcopy(store.club)
    initial_profile = deepcopy(store.profile)
    initial_notifications = deepcopy(store.notifications)
    initial_activity_events = deepcopy(store.activity_events)
    initial_buttons = deepcopy(store.buttons)
    initial_button_secrets = deepcopy(store.button_secrets)
    store.players.clear()
    store.player_access.clear()
    store.sessions.clear()
    store.sessions_by_token.clear()
    store.consents.clear()
    store.highlights.clear()
    store.recordings.clear()
    store.recordings_by_key.clear()
    store.processing_jobs.clear()
    store.processing_jobs_by_key.clear()
    store.events_by_key.clear()
    store.idempotency.clear()
    store.activity_events.clear()
    yield
    store.fields = initial_fields
    store.cameras = initial_cameras
    store.club = initial_club
    store.profile = initial_profile
    store.notifications = initial_notifications
    store.activity_events = initial_activity_events
    store.buttons = initial_buttons
    store.button_secrets = initial_button_secrets
