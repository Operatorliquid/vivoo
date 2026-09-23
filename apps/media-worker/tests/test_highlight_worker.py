from pathlib import Path
from uuid import UUID

from jobs.highlight_worker import HighlightWorker


class FakeApi:
    def __init__(self):
        self.completed = []
        self.deliveries = []

    def lease_next_job(self):
        return {
            "job_id": "00000000-0000-0000-0000-000000000001",
            "source_storage_key": "segments/source.mp4",
            "output_storage_key": "highlights/output.mp4",
            "duration_seconds": 30,
        }

    def complete_job(self, job_id, succeeded, output_storage_key=None, error=None):
        self.completed.append((job_id, succeeded, output_storage_key, error))

    def report_delivery(self, job_id, phone_e164, display_name, succeeded, error=None):
        self.deliveries.append((job_id, phone_e164, display_name, succeeded, error))


def test_worker_reports_failed_source_without_crashing(tmp_path: Path):
    api = FakeApi()
    assert HighlightWorker(api, tmp_path).process_once() is True
    assert api.completed[0][1] is False
    assert "Media fuente no encontrada" in api.completed[0][3]


def test_delivery_failure_stays_queued_instead_of_losing_the_message(tmp_path: Path):
    api = FakeApi()
    api.lease_next_job = lambda: None
    worker = HighlightWorker(api, tmp_path, evolution=None, public_media_base_url="http://api")
    worker.delivery_outbox.enqueue(
        "00000000-0000-0000-0000-000000000001", "highlight-1", "+5491155550118",
        "José", "http://api/highlight", "Listo", "vivoo-owner",
    )

    assert worker.process_once() is True
    assert worker.delivery_outbox.pending_count() == 1
    assert api.deliveries == []


def test_full_recording_is_watermarked_before_becoming_available(tmp_path: Path, monkeypatch):
    api = FakeApi()
    api.lease_next_job = lambda: {
        "job_id": "00000000-0000-0000-0000-000000000002",
        "job_type": "watermark_recording",
        "resource_id": "00000000-0000-0000-0000-000000000003",
        "source_storage_key": "sessions/one/recording/source.mp4",
        "output_storage_key": "recordings/one.mp4",
        "duration_seconds": 0,
    }
    source = tmp_path / "sessions/one/recording/source.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"raw-match")

    def fake_watermark(request):
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"vivoo-watermarked-match")
        return request.output_path

    monkeypatch.setattr("jobs.highlight_worker.watermark_recording", fake_watermark)

    assert HighlightWorker(api, tmp_path).process_once() is True
    assert api.completed[0][1:3] == (True, "recordings/one.mp4")
    assert not source.exists()
    assert (tmp_path / "recordings/one.mp4").read_bytes() == b"vivoo-watermarked-match"
