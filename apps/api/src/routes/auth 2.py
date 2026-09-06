from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from auth.dependencies import get_current_owner
from auth.local_auth import DEMO_EMAIL, DEMO_OWNER_ID, DEMO_PASSWORD, issue_local_token
from fastapi import Depends
from services.store import store


router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)


class OwnerUser(BaseModel):
    id: str
    email: str
    display_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: OwnerUser


def demo_user() -> OwnerUser:
    profile = store.owner_profile(DEMO_OWNER_ID)
    return OwnerUser(id=profile["id"], email=profile["email"], display_name=profile["display_name"], role=profile["role"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    if payload.email.lower() != DEMO_EMAIL or payload.password != DEMO_PASSWORD:
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    return LoginResponse(access_token=issue_local_token(), user=demo_user())


@router.get("/me", response_model=OwnerUser)
def me(current_owner: dict[str, str] = Depends(get_current_owner)):
    return demo_user()
