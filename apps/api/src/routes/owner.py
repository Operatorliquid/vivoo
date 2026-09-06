from typing import Literal
from uuid import UUID

from auth.dependencies import get_current_owner
from auth.local_auth import (
    AGENT_TOKEN_TTL_SECONDS,
    issue_agent_token,
    issue_owner_media_ticket,
    verify_owner_media_ticket,
)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from services.evolution_service import EvolutionServiceError, evolution_service
from services.media_storage import media_storage
from services.store import store

router = APIRouter(prefix="/owner", tags=["Owner"])
def _issue_camera_agent_token(owner_id: str, camera_id: str) -> str:
    token = issue_agent_token(camera_id)
    store.set_camera_agent_token(owner_id, camera_id, token)
    return token


class FieldUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=60)
    status: Literal["active", "inactive", "maintenance"] | None = None
    detection_mode: Literal["arms_up", "manual"] | None = None


class HighlightBatchDelete(BaseModel):
    highlight_ids: list[UUID] = Field(min_length=1, max_length=100)


class RecordingBatchDelete(BaseModel):
    recording_ids: list[UUID] = Field(min_length=1, max_length=100)


class FieldCreate(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    sport_code: Literal["padel", "football"] = "padel"
    detection_mode: Literal["arms_up", "manual"] = "arms_up"
    camera_name: str | None = Field(default=None, min_length=2, max_length=80)
    camera_host: str | None = Field(default=None, min_length=2, max_length=240)
    camera_rtsp_port: int = Field(default=554, ge=1, le=65535)
    camera_username: str | None = Field(default=None, max_length=120)
    camera_password: str | None = Field(default=None, max_length=240)
    camera_stream_path: str | None = Field(default=None, max_length=240)
    camera_serial_number: str | None = Field(default=None, min_length=2, max_length=80)


class CameraCreate(BaseModel):
    field_id: str
    name: str = Field(min_length=2, max_length=80)
    serial_number: str | None = Field(default=None, max_length=80)
    stream_url: str | None = Field(default=None, max_length=240)
    host: str | None = Field(default=None, min_length=2, max_length=240)
    rtsp_port: int = Field(default=554, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, max_length=240)
    stream_path: str | None = Field(default=None, max_length=240)


class CameraUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    serial_number: str | None = Field(default=None, max_length=80)
    stream_url: str | None = Field(default=None, max_length=240)
    host: str | None = Field(default=None, min_length=2, max_length=240)
    rtsp_port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, max_length=240)
    stream_path: str | None = Field(default=None, max_length=240)
    status: Literal["live", "ready", "offline"] | None = None


class ButtonUpdate(BaseModel):
    device_id: str = Field(min_length=2, max_length=120)
    secret: str = Field(min_length=8, max_length=240)


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    phone: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=80)


class ClubUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    city: str | None = Field(default=None, min_length=2, max_length=80)
    logo_data_url: str | None = Field(default=None, max_length=700_000)

    @field_validator("logo_data_url")
    @classmethod
    def validate_logo_data_url(cls, value: str | None) -> str | None:
        if value in {None, ""}:
            return value
        allowed_prefixes = ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")
        if not value.startswith(allowed_prefixes):
            raise ValueError("El logo debe ser PNG, JPG o WebP")
        return value


@router.get("/clubs")
def list_clubs(current_owner: dict[str, str] = Depends(get_current_owner)):
    return {"items": store.owner_clubs(current_owner["owner_id"])}


@router.get("/fields")
def list_fields(current_owner: dict[str, str] = Depends(get_current_owner)):
    return {"items": store.owner_fields(current_owner["owner_id"])}


@router.post("/fields")
def create_field(payload: FieldCreate, current_owner: dict[str, str] = Depends(get_current_owner)):
    created = store.create_owner_field(
        current_owner["owner_id"],
        payload.name,
        payload.sport_code,
        payload.detection_mode,
        payload.camera_name,
        payload.camera_serial_number,
        payload.camera_host,
        payload.camera_rtsp_port,
        payload.camera_username,
        payload.camera_password,
        payload.camera_stream_path,
    )
    camera = created.get("camera")
    if isinstance(camera, dict):
        return {**created, "agent_token": _issue_camera_agent_token(current_owner["owner_id"], str(camera["id"]))}
    return created


@router.patch("/club")
def update_club(payload: ClubUpdate, current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.update_owner_club(current_owner["owner_id"], payload.model_dump(exclude_unset=True))


@router.patch("/fields/{field_id}")
def update_field(field_id: str, payload: FieldUpdate, current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.update_owner_field(current_owner["owner_id"], field_id, payload.model_dump(exclude_unset=True))


@router.post("/fields/{field_id}/recording/start")
def start_field_recording(field_id: str, current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.start_owner_recording(current_owner["owner_id"], field_id)


@router.post("/fields/{field_id}/recording/stop")
def stop_field_recording(field_id: str, current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.stop_owner_recording(current_owner["owner_id"], field_id)


@router.post("/sessions/{session_id}/access/revoke")
def revoke_session_access(session_id: UUID, current_owner: dict[str, str] = Depends(get_current_owner)):
    return {"revoked": store.revoke_session_player_access(current_owner["owner_id"], session_id)}


@router.delete("/fields/{field_id}", status_code=204)
def delete_field(field_id: str, current_owner: dict[str, str] = Depends(get_current_owner)):
    store.delete_owner_field(current_owner["owner_id"], field_id)


@router.put("/fields/{field_id}/button")
def update_button(field_id: str, payload: ButtonUpdate, current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.update_owner_button(current_owner["owner_id"], field_id, payload.device_id, payload.secret)


@router.get("/cameras")
def list_cameras(current_owner: dict[str, str] = Depends(get_current_owner)):
    return {"items": store.owner_cameras(current_owner["owner_id"])}


@router.post("/cameras")
def create_camera(payload: CameraCreate, current_owner: dict[str, str] = Depends(get_current_owner)):
    camera = store.create_owner_camera(current_owner["owner_id"], payload.field_id, payload.name, payload.serial_number, payload.stream_url, payload.host, payload.rtsp_port, payload.username, payload.password, payload.stream_path)
    return {**camera, "agent_token": _issue_camera_agent_token(current_owner["owner_id"], camera["id"])}


@router.post("/cameras/{camera_id}/agent-token")
def create_camera_agent_token(camera_id: str, current_owner: dict[str, str] = Depends(get_current_owner)):
    if not any(camera["id"] == camera_id for camera in store.owner_cameras(current_owner["owner_id"])):
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    return {
        "camera_id": camera_id,
        "token": _issue_camera_agent_token(current_owner["owner_id"], camera_id),
        "expires_in": AGENT_TOKEN_TTL_SECONDS,
    }


@router.delete("/cameras/{camera_id}/agent-link", status_code=204)
def unlink_camera_agent(camera_id: str, current_owner: dict[str, str] = Depends(get_current_owner)):
    if not any(camera["id"] == camera_id for camera in store.owner_cameras(current_owner["owner_id"])):
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    store.revoke_camera_agent_token(current_owner["owner_id"], camera_id)


@router.patch("/cameras/{camera_id}")
def update_camera(camera_id: str, payload: CameraUpdate, current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.update_owner_camera(current_owner["owner_id"], camera_id, payload.model_dump(exclude_unset=True))


@router.delete("/cameras/{camera_id}", status_code=204)
def delete_camera(camera_id: str, current_owner: dict[str, str] = Depends(get_current_owner)):
    store.delete_owner_camera(current_owner["owner_id"], camera_id)


@router.get("/profile")
def profile(current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.owner_profile(current_owner["owner_id"])


@router.patch("/profile")
def update_profile(payload: ProfileUpdate, current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.update_owner_profile(current_owner["owner_id"], payload.model_dump(exclude_unset=True))


@router.get("/whatsapp")
def whatsapp_status(current_owner: dict[str, str] = Depends(get_current_owner)):
    try:
        return evolution_service.status(current_owner["owner_id"]).as_dict()
    except EvolutionServiceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/whatsapp/connect")
def whatsapp_connect(current_owner: dict[str, str] = Depends(get_current_owner)):
    try:
        return evolution_service.connect(current_owner["owner_id"]).as_dict()
    except EvolutionServiceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.delete("/whatsapp", status_code=200)
def whatsapp_disconnect(current_owner: dict[str, str] = Depends(get_current_owner)):
    try:
        return evolution_service.disconnect(current_owner["owner_id"]).as_dict()
    except EvolutionServiceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/notifications")
def notifications(current_owner: dict[str, str] = Depends(get_current_owner)):
    return {"items": store.owner_notifications(current_owner["owner_id"])}


@router.get("/activity")
def activity(current_owner: dict[str, str] = Depends(get_current_owner)):
    return {"items": store.owner_activity(current_owner["owner_id"])}


@router.post("/notifications/read-all")
def mark_all_notifications_read(current_owner: dict[str, str] = Depends(get_current_owner)):
    return {"items": store.mark_all_notifications_read(current_owner["owner_id"])}


@router.delete("/notifications", status_code=204)
def delete_all_notifications(current_owner: dict[str, str] = Depends(get_current_owner)):
    store.delete_all_notifications(current_owner["owner_id"])


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.mark_notification_read(current_owner["owner_id"], notification_id)


@router.get("/dashboard")
def dashboard(current_owner: dict[str, str] = Depends(get_current_owner)):
    return store.owner_dashboard(current_owner["owner_id"])


@router.get("/highlights")
def highlights(current_owner: dict[str, str] = Depends(get_current_owner)):
    items = store.owner_highlights(current_owner["owner_id"])
    for item in items:
        item["media_path"] = None
        item["download_path"] = None
        if item.pop("media_available", False):
            highlight_id = str(item["id"])
            ticket = issue_owner_media_ticket(current_owner["owner_id"], highlight_id)
            path = f"/owner/highlights/{highlight_id}/media?ticket={ticket}"
            item["media_path"] = path
            item["download_path"] = f"{path}&download=1"
    return {"items": items}


@router.post("/highlights/delete-batch")
def delete_highlights_batch(payload: HighlightBatchDelete, current_owner: dict[str, str] = Depends(get_current_owner)):
    highlight_ids = list(dict.fromkeys(payload.highlight_ids))
    storage_keys = list(dict.fromkeys(
        key
        for highlight_id in highlight_ids
        for key in store.owner_highlight_storage_keys(current_owner["owner_id"], highlight_id)
    ))
    # Validate the complete selection before deleting the first object. Storage
    # deletion is idempotent, so a network retry cannot create duplicate state.
    for storage_key in storage_keys:
        media_storage.delete(storage_key)
    for highlight_id in highlight_ids:
        store.delete_owner_highlight(current_owner["owner_id"], highlight_id)
    return {"deleted": len(highlight_ids), "highlight_ids": highlight_ids}


@router.delete("/highlights/{highlight_id}", status_code=204)
def delete_highlight(highlight_id: UUID, current_owner: dict[str, str] = Depends(get_current_owner)):
    storage_keys = store.owner_highlight_storage_keys(current_owner["owner_id"], highlight_id)
    for storage_key in storage_keys:
        media_storage.delete(storage_key)
    store.delete_owner_highlight(current_owner["owner_id"], highlight_id)


@router.get("/highlights/{highlight_id}/media")
def highlight_media(highlight_id: UUID, ticket: str, download: bool = False):
    try:
        ticket_owner = verify_owner_media_ticket(ticket, str(highlight_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="El acceso al video venció") from None
    storage_key = store.resolve_owner_highlight_media(ticket_owner["owner_id"], highlight_id)
    return media_storage.playback_response(
        storage_key,
        f"courtvision-{str(highlight_id)[:8]}.mp4",
        download=download,
    )


@router.get("/recordings")
def recordings(current_owner: dict[str, str] = Depends(get_current_owner)):
    # If the process stopped after S3 accepted the object but before the final
    # state write, recover it while loading the owner's library.
    store.reconcile_owner_recordings(current_owner["owner_id"], media_storage.completed_upload_exists)
    items = store.owner_recordings(current_owner["owner_id"])
    for item in items:
        item["media_path"] = None
        item["download_path"] = None
        if item.pop("media_available", False):
            recording_id = str(item["id"])
            ticket = issue_owner_media_ticket(current_owner["owner_id"], recording_id)
            path = f"/owner/recordings/{recording_id}/media?ticket={ticket}"
            item["media_path"] = path
            item["download_path"] = f"{path}&download=1"
    return {"items": items}


@router.post("/recordings/delete-batch")
def delete_recordings_batch(payload: RecordingBatchDelete, current_owner: dict[str, str] = Depends(get_current_owner)):
    recording_ids = list(dict.fromkeys(payload.recording_ids))
    storage_keys = list(dict.fromkeys(
        key
        for recording_id in recording_ids
        for key in store.owner_recording_storage_keys(current_owner["owner_id"], recording_id)
    ))
    for storage_key in storage_keys:
        media_storage.delete(storage_key)
    for recording_id in recording_ids:
        store.delete_owner_recording(current_owner["owner_id"], recording_id)
    return {"deleted": len(recording_ids), "recording_ids": recording_ids}


@router.delete("/recordings/{recording_id}", status_code=204)
def delete_recording(recording_id: UUID, current_owner: dict[str, str] = Depends(get_current_owner)):
    storage_keys = store.owner_recording_storage_keys(current_owner["owner_id"], recording_id)
    for storage_key in storage_keys:
        media_storage.delete(storage_key)
    store.delete_owner_recording(current_owner["owner_id"], recording_id)


@router.get("/recordings/{recording_id}/media")
def recording_media(recording_id: UUID, ticket: str, download: bool = False):
    try:
        ticket_owner = verify_owner_media_ticket(ticket, str(recording_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="El acceso al video venció") from None
    storage_key = store.resolve_owner_recording_media(ticket_owner["owner_id"], recording_id)
    return media_storage.playback_response(
        storage_key,
        f"vivoo-partido-{str(recording_id)[:8]}.mp4",
        download=download,
    )
