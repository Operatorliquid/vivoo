"""Standalone media worker entrypoint for local and AWS edge deployments."""

import os
import time
from pathlib import Path

from delivery.evolution_client import EvolutionApiClient, EvolutionConfig
from jobs.highlight_worker import HighlightWorker
from storage.media_repository import MediaRepository
from worker_api_client import WorkerApiClient, WorkerApiError


def build_worker() -> HighlightWorker:
    media_root = Path(os.getenv("LOCAL_MEDIA_ROOT", "/tmp/courtvision-media"))
    evolution = EvolutionApiClient(EvolutionConfig(
        base_url=os.getenv("EVOLUTION_API_URL", ""),
        api_key=os.getenv("EVOLUTION_API_KEY", ""),
        instance=os.getenv("EVOLUTION_INSTANCE", "courtvision"),
        enabled=os.getenv("EVOLUTION_ENABLED", "false").lower() == "true",
    ))
    return HighlightWorker(
        WorkerApiClient(os.getenv("COURTVISION_API_URL", "http://127.0.0.1:8000"), os.getenv("LOCAL_WORKER_KEY", "courtvision-local-worker")),
        media_root,
        evolution=evolution,
        public_media_base_url=os.getenv(
            "EVOLUTION_MEDIA_BASE_URL",
            os.getenv("PUBLIC_MEDIA_BASE_URL", "http://127.0.0.1:8000"),
        ),
        media_repository=MediaRepository(
            media_root,
            os.getenv("AWS_S3_MEDIA_BUCKET", ""),
            os.getenv("AWS_REGION", "sa-east-1"),
        ),
    )


def main() -> None:
    worker = build_worker()
    print("vivoo media worker ready")
    last_heartbeat = 0.0
    while True:
        try:
            now = time.monotonic()
            if now - last_heartbeat >= 15:
                worker.api.heartbeat()
                last_heartbeat = now
            processed = worker.process_once()
        except WorkerApiError:
            processed = False
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
