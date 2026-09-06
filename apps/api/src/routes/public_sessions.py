from fastapi import APIRouter, Header
from domain.schemas import FieldContext, PlayerJoinResponse, PlayerMediaPage, SessionJoinResponse, StartSessionRequest
from services.media_storage import media_storage
from services.store import store


router = APIRouter(prefix="/public", tags=["Public Player"])


@router.get("/fields/{field_token}", response_model=FieldContext)
def get_field_context(field_token: str):
    return store.field_context(field_token)


@router.post("/fields/{field_token}/sessions", response_model=SessionJoinResponse, status_code=201)
def start_session(field_token: str, payload: StartSessionRequest, idempotency_key: str = Header(..., alias="Idempotency-Key")):
    context = store.field_context(field_token)
    session, player, access_token = store.start_session(field_token, payload, idempotency_key)
    return SessionJoinResponse(session_id=session.id, session_token=session.token, field_name=context["field_name"], sport_code=context["sport_code"], status="active", player_id=player.id if player else None, access_token=access_token)


@router.post("/sessions/{session_token}/players", response_model=PlayerJoinResponse, status_code=201)
def join_session(session_token: str, payload: StartSessionRequest, idempotency_key: str = Header(..., alias="Idempotency-Key")):
    session, player, access_token = store.join_session(session_token, payload, idempotency_key)
    return PlayerJoinResponse(session_id=session.id, player_id=player.id, access_token=access_token)


@router.get("/access/{access_token}", response_model=PlayerMediaPage)
def get_player_media(access_token: str):
    page = store.player_media_page(access_token)
    return page


@router.get("/access/{access_token}/recording")
def get_full_recording(access_token: str):
    _, storage_key = store.resolve_player_media(access_token)
    return media_storage.playback_response(storage_key, "courtvision-partido.mp4")


@router.get("/access/{access_token}/highlights/{highlight_id}")
def get_highlight(access_token: str, highlight_id: str):
    from uuid import UUID
    _, storage_key = store.resolve_player_media(access_token, UUID(highlight_id))
    return media_storage.playback_response(storage_key, "courtvision-highlight.mp4")
