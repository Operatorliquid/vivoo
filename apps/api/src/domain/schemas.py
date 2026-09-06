from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


EventType = Literal["gesture", "manual", "physical_button", "automatic_sport_event"]


class FieldContext(BaseModel):
    field_id: UUID
    club_name: str
    venue_name: str
    field_name: str
    sport_code: str
    status: Literal["active", "inactive", "maintenance"]
    camera_status: Literal["live", "ready", "offline"] = "offline"
    active_session_id: UUID | None = None
    recording_status: Literal["idle", "starting", "recording", "stopping"] = "idle"


class StartSessionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str = Field(min_length=2, max_length=100)
    phone_e164: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")
    recording_consent: Literal[True]
    messaging_consent: bool
    policy_version: str = Field(default="2026-01", max_length=32)

    @field_validator("phone_e164", mode="before")
    @classmethod
    def normalize_whatsapp_phone(cls, value: object) -> str:
        raw = str(value).strip()
        digits = "".join(character for character in raw if character.isdigit())
        explicit_international = raw.startswith("+") or digits.startswith("00")
        if digits.startswith("00"):
            digits = digits[2:]
        if explicit_international or digits.startswith("54"):
            if digits.startswith("54") and not digits.startswith("549"):
                digits = f"549{digits[2:].lstrip('0')}"
            return f"+{digits}"
        local = digits.lstrip("0")
        if len(local) == 12:
            for index in (2, 3, 4):
                if local[index:index + 2] == "15":
                    local = f"{local[:index]}{local[index + 2:]}"
                    break
        return f"+549{local}"


class SessionJoinResponse(BaseModel):
    session_id: UUID
    session_token: str
    field_name: str
    sport_code: str
    status: Literal["pending", "active"]
    player_id: UUID | None = None
    access_token: str | None = None


class PlayerJoinResponse(BaseModel):
    session_id: UUID
    player_id: UUID
    access_token: str


class PlayerHighlight(BaseModel):
    id: UUID
    title: str
    occurred_at: datetime
    duration_seconds: int
    status: Literal["processing", "available", "failed"]
    media_path: str | None = None


class PlayerMediaPage(BaseModel):
    session_id: UUID
    player_name: str
    club_name: str
    field_name: str
    sport_code: str
    started_at: datetime
    recording_status: Literal["in_progress", "processing", "available", "expired"]
    recording_path: str | None = None
    recording_expires_at: datetime | None = None
    highlights: list[PlayerHighlight]


class CaptureEventRequest(BaseModel):
    source_id: str = Field(min_length=2, max_length=120)
    event_type: EventType
    occurred_at: datetime
    confidence: float | None = Field(default=None, ge=0, le=1)
    buffer_start_at: datetime | None = None
    buffer_end_at: datetime | None = None
    initiating_player_id: UUID | None = None
    source_storage_key: str | None = Field(default=None, max_length=500)


class WorkerJobCompleteRequest(BaseModel):
    succeeded: bool
    output_storage_key: str | None = None
    error: str | None = Field(default=None, max_length=500)


class WorkerDeliveryResultRequest(BaseModel):
    phone_e164: str = Field(min_length=6, max_length=32)
    display_name: str = Field(min_length=1, max_length=120)
    succeeded: bool
    error: str | None = Field(default=None, max_length=500)


class EventAcceptedResponse(BaseModel):
    event_id: UUID
    highlight_id: UUID
    status: Literal["accepted", "processing"]


class PresignUploadRequest(BaseModel):
    session_id: UUID
    media_type: Literal["segment", "recording", "highlight_source"]
    content_type: str
    size_bytes: int = Field(gt=0)
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class PresignUploadResponse(BaseModel):
    upload_url: str
    storage_key: str
    expires_at: datetime


class ResumableUploadResponse(BaseModel):
    upload_id: str
    storage_key: str
    part_size: int
    received_parts: list[int]
    size_bytes: int
    checksum: str


class ResumableUploadCompleteRequest(BaseModel):
    session_id: UUID
    media_type: Literal["segment", "recording", "highlight_source"]
    upload_id: str = Field(min_length=16, max_length=128)
    storage_key: str = Field(min_length=8, max_length=500)
    size_bytes: int = Field(gt=0)
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class CompleteUploadRequest(BaseModel):
    session_id: UUID
    media_type: Literal["segment", "recording", "highlight_source"]
    storage_key: str = Field(min_length=8, max_length=500)
    size_bytes: int = Field(gt=0)
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class HeartbeatRequest(BaseModel):
    device_id: str = Field(min_length=2, max_length=120)
    observed_at: datetime
    camera_status: Literal["online", "offline", "degraded"]
    active_session_id: UUID | None = None
    agent_version: str = Field(min_length=1, max_length=32)
    detector_status: str | None = Field(default=None, max_length=32)
    detector_fps: float | None = Field(default=None, ge=0, le=120)
    detector_last_frame_at: datetime | None = None


class AgentCameraConfig(BaseModel):
    camera_id: str
    field_id: str
    field_name: str
    stream_url: str
    host: str
    rtsp_port: int
    username: str
    password: str
    stream_path: str
    detection_mode: Literal["arms_up", "manual"]
    recording_enabled: bool
    active_session_id: UUID | None = None
