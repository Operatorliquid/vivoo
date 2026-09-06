from __future__ import annotations

from pathlib import Path

from clipping.highlight_processor import ClipRequest, assemble_highlight
from delivery.evolution_client import EvolutionApiClient
from storage.media_repository import MediaRepository
from worker_api_client import WorkerApiClient


class HighlightWorker:
    def __init__(self, api: WorkerApiClient, media_root: Path, evolution: EvolutionApiClient | None = None, public_media_base_url: str = "", media_repository: MediaRepository | None = None) -> None:
        self.api = api
        self.media_root = media_root
        self.media = media_repository or MediaRepository(media_root)
        self.evolution = evolution
        self.public_media_base_url = public_media_base_url.rstrip("/")

    def process_once(self) -> bool:
        job = self.api.lease_next_job()
        if job is None:
            return False
        job_id = job["job_id"]
        resource_id = job.get("resource_id", job_id)
        print(f"Processing highlight {resource_id} (attempt {job.get('attempts', 1)})", flush=True)
        source_key = job.get("source_storage_key")
        source_path: Path | None = None
        output_path: Path | None = None
        try:
            if not source_key:
                raise RuntimeError("Highlight no tiene media fuente")
            source_path = self.media.materialize(source_key)
            if not source_path.is_file():
                raise FileNotFoundError(f"Media fuente no encontrada: {source_key}")
            output_key = job["output_storage_key"]
            output_path = self.media.working_path(output_key)
            assemble_highlight(ClipRequest(source_path, output_path, 0, max(1, int(job["duration_seconds"]))))
            self.media.publish(output_key, output_path)
            self.api.complete_job(job_id, True, output_key)
            print(f"Highlight {resource_id} available", flush=True)
            self._deliver(job)
        except Exception as error:
            print(f"Highlight {resource_id} failed: {error}", flush=True)
            self.api.complete_job(job_id, False, error=str(error))
        finally:
            self.media.release(*(path for path in (source_path, output_path) if path is not None))
        return True

    def _deliver(self, job: dict) -> None:
        for recipient in job.get("delivery_recipients", []):
            if self.evolution is None or not self.public_media_base_url:
                self._report_delivery(job, recipient, False, "Evolution API no está configurada")
                continue
            media_url = f"{self.public_media_base_url}/public/access/{recipient['access_token']}/highlights/{job['resource_id']}"
            try:
                self.evolution.send_video(
                    recipient["phone_e164"], media_url,
                    f"Hola {recipient['display_name']}, tu highlight de vivoo ya está listo.",
                    instance=str(job.get("evolution_instance") or self.evolution.config.instance),
                )
                self._report_delivery(job, recipient, True)
            except Exception as error:
                # Delivery failures must be retried by the delivery outbox, not mark video processing as failed.
                self._report_delivery(job, recipient, False, str(error))

    def _report_delivery(self, job: dict, recipient: dict, succeeded: bool, error: str | None = None) -> None:
        try:
            self.api.report_delivery(
                job["job_id"], recipient["phone_e164"], recipient["display_name"], succeeded, error,
            )
        except Exception:
            # El video ya fue procesado: una caída del callback no debe revertirlo.
            return
