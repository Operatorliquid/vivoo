import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from auth.account_service import AuthContext, account_service
from auth.dependencies import bearer, get_current_owner


router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=10, max_length=256)


class OwnerUser(BaseModel):
    id: str
    email: str
    display_name: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: OwnerUser


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20)
    password: str = Field(min_length=10, max_length=256)


def _response(token: str, context: AuthContext | dict[str, str]) -> LoginResponse:
    values = context.as_dependency() if isinstance(context, AuthContext) else context
    return LoginResponse(
        access_token=token,
        user=OwnerUser(
            id=values["user_id"],
            email=values["email"],
            display_name=values["display_name"],
            role=values["role"],
        ),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    context = account_service.authenticate_owner(payload.email, payload.password)
    if context is None:
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    return _response(account_service.issue_session(context), context)


@router.get("/me", response_model=OwnerUser)
def me(current_owner: dict[str, str] = Depends(get_current_owner)):
    return OwnerUser(
        id=current_owner["user_id"],
        email=current_owner["email"],
        display_name=current_owner["display_name"],
        role=current_owner["role"],
    )


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    current_owner: dict[str, str] = Depends(get_current_owner),
):
    rotated = account_service.rotate_session(credentials.credentials)
    if rotated is None:
        raise HTTPException(status_code=401, detail="La sesión ya no es válida")
    return _response(rotated[0], current_owner)


@router.post("/logout", status_code=204)
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    _current_owner: dict[str, str] = Depends(get_current_owner),
):
    account_service.revoke_session(credentials.credentials)


@router.post("/password-reset/request")
def request_password_reset(payload: PasswordResetRequest):
    token = account_service.request_password_reset(payload.email)
    response: dict[str, object] = {"accepted": True}
    if token and os.getenv("APP_ENV", "local") != "production":
        response["reset_token"] = token
    return response


@router.post("/password-reset/confirm", status_code=204)
def confirm_password_reset(payload: PasswordResetConfirm):
    try:
        changed = account_service.reset_password(payload.token, payload.password)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if not changed:
        raise HTTPException(status_code=400, detail="El enlace venció o ya fue utilizado")
