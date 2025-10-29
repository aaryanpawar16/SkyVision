from fastapi import APIRouter
from ..db import ping

router = APIRouter()

@router.get("/healthz")
def healthz():
    # Liveness: say service is up without touching DB
    return {"service": "skyvision-backend", "ok": True}

@router.get("/readyz")
def readyz():
    # Readiness: include DB check
    return {"service": "skyvision-backend", **ping()}
