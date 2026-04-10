import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from phoenix.otel import register
from starlette.requests import Request
from starlette.responses import Response

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.db import init_db
from app.deps import AppDeps
from app.logging import setup_logging
from app.routes.incidents import router as incidents_router
from app.routes.stream import router as stream_router
from app.routes.webhooks import router as webhooks_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    setup_logging(json_logs=True)
    phoenix_endpoint = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "")
    if phoenix_endpoint:
        register(
            project_name="sre-triage",
            endpoint=phoenix_endpoint,
            batch=True,
            verbose=False,
            auto_instrument=True,
        )
    await init_db()
    async with httpx.AsyncClient() as client:
        _app.state.deps = AppDeps(http_client=client)
        yield


limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])
app = FastAPI(title="SRE Incident Triage Agent", lifespan=lifespan)
app.state.limiter = limiter
def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RateLimitExceeded)
    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(incidents_router)
app.include_router(stream_router)
app.include_router(webhooks_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
