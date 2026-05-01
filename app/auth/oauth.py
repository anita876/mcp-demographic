import json
import logging
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Refreshed credentials when tokens are loaded from GOOGLE_OAUTH_TOKEN_JSON (env cannot be updated at runtime).
_env_token_runtime_cache: Optional[Credentials] = None


def _token_path() -> Path:
    path = settings.token_path_resolved
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _credentials_from_dict(data: dict[str, Any]) -> Credentials:
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id") or settings.google_client_id,
        client_secret=data.get("client_secret") or settings.google_client_secret,
        scopes=data.get("scopes") or SCOPES,
    )


def get_oauth_flow(redirect_uri: Optional[str] = None) -> Flow:
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in the environment."
        )
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri or settings.oauth_redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri or settings.oauth_redirect_uri,
    )


def save_credentials(creds: Credentials) -> None:
    global _env_token_runtime_cache
    if settings.google_oauth_token_json.strip():
        _env_token_runtime_cache = creds
    path = _token_path()
    payload = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Stored OAuth token at %s", path)


def load_credentials() -> Optional[Credentials]:
    global _env_token_runtime_cache

    env_raw = settings.google_oauth_token_json.strip()
    if env_raw:
        if _env_token_runtime_cache is not None:
            return _env_token_runtime_cache
        try:
            data = json.loads(env_raw)
        except json.JSONDecodeError as e:
            logger.warning("Invalid GOOGLE_OAUTH_TOKEN_JSON: %s", e)
            return None
        if not isinstance(data, dict):
            logger.warning("GOOGLE_OAUTH_TOKEN_JSON must be a JSON object")
            return None
        return _credentials_from_dict(data)

    path = settings.token_path_resolved
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not read token file: %s", e)
        return None
    return _credentials_from_dict(data)


def get_credentials() -> Credentials:
    creds = load_credentials()
    if creds is None:
        raise FileNotFoundError(
            "No OAuth token found. Set GOOGLE_OAUTH_TOKEN_JSON or complete "
            "the browser flow at GET /auth/google first."
        )
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            logger.info("Refreshing expired OAuth token")
            creds.refresh(Request())
            save_credentials(creds)
        else:
            raise RuntimeError(
                "Stored credentials are invalid and cannot be refreshed. "
                "Re-authorize via GET /auth/google."
            )
    return creds
