from config import settings
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from routes.admin import router as admin_router
from routes.agent_events import router as agent_router
from routes.auth import router as auth_router
from routes.owner import router as owner_router
from routes.public_sessions import router as public_router
from routes.worker import router as worker_router
from services.health_service import health_service

settings.validate_production()

app = FastAPI(title="vivoo API", version="0.1.0")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public_router)
app.include_router(agent_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(owner_router)
app.include_router(worker_router)


@app.get("/health")
def health(response: Response) -> dict[str, object]:
    report, healthy = health_service.report()
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok", "service": "vivoo-api"}


@app.get("/health/ready")
def readiness(response: Response) -> dict[str, object]:
    return health(response)
