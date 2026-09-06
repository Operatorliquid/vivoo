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
