from uuid import UUID

from auth.dependencies import get_current_agent
from domain.schemas import (
    AgentCameraConfig,
    CaptureEventRequest,
    CompleteUploadRequest,
    EventAcceptedResponse,
    HeartbeatRequest,
    PresignUploadRequest,
    PresignUploadResponse,
    ResumableUploadCompleteRequest,
    ResumableUploadResponse,
)
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from services.media_storage import media_storage
from services.store import store

router = APIRouter(prefix="/agent", tags=["Capture Agent"])


@router.post("/heartbeat", status_code=204)
def heartbeat(payload: HeartbeatRequest, agent: dict[str, str] = Depends(get_current_agent)):
    if agent["camera_id"] and agent["camera_id"] != payload.device_id:
        raise HTTPException(status_code=403, detail="El agente no está vinculado a esta cámara")
    if payload.active_session_id is not None:
        store.assert_agent_session(agent["camera_id"], payload.active_session_id)
    store.record_agent_heartbeat(
        payload.device_id,
        payload.camera_status,
        payload.observed_at,
        payload.active_session_id,
        payload.detector_status,
        payload.detector_fps,
        payload.detector_last_frame_at,
    )


@router.get("/cameras/{camera_id}/config", response_model=AgentCameraConfig)
def camera_config(camera_id: str, agent: dict[str, str] = Depends(get_current_agent)):
    if agent["camera_id"] and agent["camera_id"] != camera_id:
        raise HTTPException(status_code=403, detail="El agente no está vinculado a esta cámara")
    return store.agent_camera_config(camera_id)


@router.post("/sessions/{session_id}/events", response_model=EventAcceptedResponse, status_code=202)
def submit_event(session_id: UUID, payload: CaptureEventRequest, idempotency_key: str = Header(..., alias="Idempotency-Key"), agent: dict[str, str] = Depends(get_current_agent)):
    store.assert_agent_session(agent["camera_id"], session_id)
    event_id, highlight_id = store.create_event(session_id, payload, idempotency_key)
    return EventAcceptedResponse(event_id=event_id, highlight_id=highlight_id, status="processing")


@router.post("/uploads/presign", response_model=PresignUploadResponse)
def presign_upload(payload: PresignUploadRequest, agent: dict[str, str] = Depends(get_current_agent)):
    store.assert_agent_session(agent["camera_id"], payload.session_id)
    store.register_media_upload(payload)
    return media_storage.presign_upload(payload)


@router.post("/uploads/resumable", response_model=ResumableUploadResponse)
def start_resumable_upload(payload: PresignUploadRequest, agent: dict[str, str] = Depends(get_current_agent)):
    store.assert_agent_session(agent["camera_id"], payload.session_id)
    store.register_media_upload(payload)
    return media_storage.start_resumable(payload, agent["camera_id"])


@router.put("/uploads/resumable/{upload_id}/parts/{part_number}", status_code=204)
async def upload_resumable_part(upload_id: str, part_number: int, request: Request, agent: dict[str, str] = Depends(get_current_agent)):
    manifest = media_storage.resumable_manifest(upload_id)
    if agent["camera_id"] and manifest.get("camera_id") != agent["camera_id"]:
        raise HTTPException(status_code=403, detail="La subida pertenece a otra cámara")
    await media_storage.save_resumable_part(upload_id, part_number, request.stream())


@router.post("/uploads/resumable/{upload_id}/complete", status_code=204)
def complete_resumable_upload(upload_id: str, payload: ResumableUploadCompleteRequest, agent: dict[str, str] = Depends(get_current_agent)):
    store.assert_agent_session(agent["camera_id"], payload.session_id)
    manifest = media_storage.resumable_manifest(upload_id)
    if (
        payload.upload_id != upload_id
        or manifest.get("session_id") != str(payload.session_id)
        or manifest.get("media_type") != payload.media_type
        or (agent["camera_id"] and manifest.get("camera_id") != agent["camera_id"])
    ):
        raise HTTPException(status_code=403, detail="La subida pertenece a otra cámara")
    media_storage.complete_resumable(upload_id, payload.storage_key, payload.size_bytes, payload.checksum)
    store.mark_media_upload_available(payload.storage_key)


@router.put("/dev/uploads/{storage_path:path}", include_in_schema=False, status_code=204)
async def upload_local(storage_path: str, request: Request, agent: dict[str, str] = Depends(get_current_agent)):
    store.assert_agent_storage_path(agent["camera_id"], storage_path)
    await media_storage.save_local_upload_stream(storage_path, request.stream())


@router.post("/uploads/complete", status_code=204)
def complete_upload(payload: CompleteUploadRequest, agent: dict[str, str] = Depends(get_current_agent)):
    store.assert_agent_session(agent["camera_id"], payload.session_id)
    expected_key = f"sessions/{payload.session_id}/{payload.media_type}/{payload.checksum}"
    if payload.storage_key != expected_key:
        raise HTTPException(status_code=409, detail="La clave del video no coincide con la reserva")
    media_storage.verify_upload(payload.storage_key, payload.size_bytes, payload.checksum)
    store.mark_media_upload_available(payload.storage_key)
