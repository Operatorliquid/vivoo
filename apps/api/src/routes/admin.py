from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from auth.account_service import AuthContext, account_service
from auth.dependencies import bearer, get_current_admin
from routes.auth import LoginRequest, LoginResponse, OwnerUser
from services.admin_store import admin_store
from services.store import store


router = APIRouter(prefix="/admin", tags=["Platform administration"])


class CustomerCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=10, max_length=256)
    club_name: str = Field(min_length=2, max_length=80)
    city: str = Field(default="", max_length=80)


def _login_response(token: str, context: AuthContext) -> LoginResponse:
    return LoginResponse(
        access_token=token,
        user=OwnerUser(
            id=context.user_id,
            email=context.email,
            display_name=context.display_name,
            role=context.role,
        ),
    )


@router.post("/auth/login", response_model=LoginResponse)
def admin_login(payload: LoginRequest):
    context = account_service.authenticate_admin(payload.email, payload.password)
    if context is None:
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    return _login_response(account_service.issue_session(context), context)


@router.post("/auth/refresh", response_model=LoginResponse)
def admin_refresh(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    _current_admin: dict[str, str] = Depends(get_current_admin),
):
    rotated = account_service.rotate_session(credentials.credentials)
    if rotated is None or rotated[1].role != "platform_admin":
        raise HTTPException(status_code=401, detail="La sesión ya no es válida")
    return _login_response(rotated[0], rotated[1])


@router.post("/auth/logout", status_code=204)
def admin_logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    _current_admin: dict[str, str] = Depends(get_current_admin),
):
    account_service.revoke_session(credentials.credentials)


@router.get("/overview")
def admin_overview(_current_admin: dict[str, str] = Depends(get_current_admin)):
    return admin_store.overview()


@router.get("/customers/{customer_id}")
def admin_customer(customer_id: str, _current_admin: dict[str, str] = Depends(get_current_admin)):
    customer = admin_store.customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return customer


@router.post("/customers", status_code=201)
def create_customer(payload: CustomerCreate, _current_admin: dict[str, str] = Depends(get_current_admin)):
    try:
        context = account_service.create_owner_account(payload.email, payload.password, payload.display_name)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    tenant = store.register_owner(context.owner_id, context.email, context.display_name)
    tenant.update_owner_club(context.owner_id, {"name": payload.club_name.strip(), "city": payload.city.strip()})
    customer = admin_store.customer(context.user_id)
    if customer is None:
        raise HTTPException(status_code=500, detail="El usuario se creó, pero no pudimos leer su ficha")
    return customer
