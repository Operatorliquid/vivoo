from __future__ import annotations

from pathlib import Path

from clipping.highlight_processor import ClipRequest, assemble_highlight
from delivery.evolution_client import EvolutionApiClient
from delivery.outbox import DeliveryOutbox, DeliveryItem
from storage.media_repository import MediaRepository
from worker_api_client import WorkerApiClient


class HighlightWorker:
    def __init__(self, api: WorkerApiClient, media_root: Path, evolution: EvolutionApiClient | None = None, public_media_base_url: str = "", media_repository: MediaRepository | None = None) -> None:
        self.api = api
        self.media_root = media_root
        self.media = media_repository or MediaRepository(media_root)
        self.evolution = evolution
        self.public_media_base_url = public_media_base_url.rstrip("/")
        self.delivery_outbox = DeliveryOutbox(media_root / ".vivoo-delivery-outbox.sqlite3")

    def process_once(self) -> bool:
        delivery = self.delivery_outbox.claim_next()
        if delivery is not None:
            self._deliver_once(delivery)
            return True
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
            self._enqueue_deliveries(job)
            self.api.complete_job(job_id, True, output_key)
            print(f"Highlight {resource_id} available", flush=True)
        except Exception as error:
            print(f"Highlight {resource_id} failed: {error}", flush=True)
            self.api.complete_job(job_id, False, error=str(error))
        finally:
            self.media.release(*(path for path in (source_path, output_path) if path is not None))
        return True

    def _enqueue_deliveries(self, job: dict) -> None:
        for recipient in job.get("delivery_recipients", []):
            media_url = f"{self.public_media_base_url}/public/access/{recipient['access_token']}/highlights/{job['resource_id']}"
            self.delivery_outbox.enqueue(
                str(job["job_id"]), str(job["resource_id"]), recipient["phone_e164"],
                recipient["display_name"], media_url,
                f"Hola {recipient['display_name']}, tu highlight de vivoo ya está listo.",
                str(job.get("evolution_instance") or (self.evolution.config.instance if self.evolution else "courtvision")),
            )

    def _deliver_once(self, item: DeliveryItem) -> None:
        if item.state == "pending":
            try:
                if self.evolution is None or not self.public_media_base_url:
                    raise RuntimeError("Evolution API no está configurada")
                self.evolution.send_video(
                    item.phone_e164, item.media_url, item.caption, instance=item.instance,
                )
                self.delivery_outbox.mark_sent(item.id)
            except Exception as error:
                self.delivery_outbox.mark_send_failure(item, str(error))
                print(f"WhatsApp delivery deferred: {error}", flush=True)
                return
            item = DeliveryItem(
                item.id, item.job_id, item.phone_e164, item.display_name, item.media_url,
                item.caption, item.instance, "sent", item.send_attempts, item.created_at, None,
            )
        try:
            self.api.report_delivery(
                item.job_id, item.phone_e164, item.display_name,
                item.state == "sent", item.last_error if item.state == "failed" else None,
            )
            self.delivery_outbox.complete(item.id)
        except Exception as error:
            # Si el envío ya salió, sólo se reintenta el callback para no duplicar el mensaje.
            self.delivery_outbox.mark_callback_failure(item.id, str(error))
