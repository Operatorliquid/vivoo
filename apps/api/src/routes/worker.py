from uuid import UUID

from auth.dependencies import get_current_worker
from domain.schemas import WorkerDeliveryResultRequest, WorkerJobCompleteRequest
from fastapi import APIRouter, Depends, Response, status
from services.health_service import health_service
from services.media_storage import media_storage
from services.store import store

router = APIRouter(prefix="/worker", tags=["Media Worker"])


@router.post("/heartbeat", status_code=204)
def worker_heartbeat(_: dict[str, str] = Depends(get_current_worker)):
    deleted = store.purge_expired_recordings(media_storage.delete)
    health_service.record_worker({"state": "running", "expired_recordings_deleted": deleted})


@router.get("/jobs/next")
def lease_next_job(_: dict[str, str] = Depends(get_current_worker)):
    job = store.lease_next_job()
    if job is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return job


@router.post("/jobs/{job_id}/complete", status_code=204)
def complete_job(job_id: UUID, payload: WorkerJobCompleteRequest, _: dict[str, str] = Depends(get_current_worker)):
    store.complete_job(job_id, payload.succeeded, payload.output_storage_key, payload.error)


@router.post("/jobs/{job_id}/delivery", status_code=204)
def record_delivery(job_id: UUID, payload: WorkerDeliveryResultRequest, _: dict[str, str] = Depends(get_current_worker)):
    store.record_delivery(job_id, payload.phone_e164, payload.display_name, payload.succeeded, payload.error)
