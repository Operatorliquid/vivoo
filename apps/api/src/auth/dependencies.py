from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from secrets import compare_digest

from auth.account_service import account_service
from auth.local_auth import verify_agent_token
from config import settings


bearer = HTTPBearer(auto_error=False)


def get_current_owner(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    context = account_service.verify_session(credentials.credentials)
    if context is None or context.role != "owner":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return context.as_dependency()


def get_current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    context = account_service.verify_session(credentials.credentials)
    if context is None or context.role != "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso administrativo requerido")
    return context.as_dependency()


def get_current_agent(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid capture agent credentials")
    if settings.app_env != "production" and compare_digest(credentials.credentials, settings.local_agent_key):
        return {"agent_id": "local-agent", "camera_id": ""}
    try:
        camera = verify_agent_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid capture agent credentials") from None
    from services.store import store
    if not store.accept_camera_agent_token(camera["camera_id"], credentials.credentials):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Capture agent token was revoked")
    return {"agent_id": f"camera-agent:{camera['camera_id']}", "camera_id": camera["camera_id"]}


def get_current_worker(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, str]:
    if credentials is None or not compare_digest(credentials.credentials, settings.local_worker_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid media worker credentials")
    return {"worker_id": "local-worker"}
