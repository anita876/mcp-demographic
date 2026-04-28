import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before importing settings-dependent modules.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

from app.config import settings
from app.routes import auth as auth_routes
from app.routes import calendar as calendar_routes
from app.routes import demographics as demographics_routes
from app.routes import mcp as mcp_routes


def _configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _configure_logging()
    yield


app = FastAPI(
    title="Google Calendar MCP Tools",
    description=(
        "REST tools for agent systems: availability, create event, list events. "
        "Authorize once via GET /auth/google."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(calendar_routes.router)
app.include_router(demographics_routes.router)
app.include_router(mcp_routes.router)


@app.get("/", operation_id="root", tags=["meta"])
async def root():
    return {"status": "ok"}


@app.get("/health", operation_id="health", tags=["meta"])
async def health():
    return {"status": "ok"}
