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
            "No OAuth token found. Complete the browser flow at GET /auth/google first."
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
