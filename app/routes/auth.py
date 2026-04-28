import logging
import time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.auth.oauth import get_oauth_flow, save_credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/google", tags=["auth"])
_PENDING_OAUTH_FLOWS: dict[str, tuple[object, float]] = {}
_FLOW_TTL_SECONDS = 600


def _cleanup_expired_flows(now: float) -> None:
    expired = [
        state
        for state, (_flow, created_at) in _PENDING_OAUTH_FLOWS.items()
        if now - created_at > _FLOW_TTL_SECONDS
    ]
    for state in expired:
        _PENDING_OAUTH_FLOWS.pop(state, None)


@router.get("", operation_id="oauth_google_start", include_in_schema=True)
async def google_oauth_start():
    """Begin OAuth 2.0 authorization (browser redirect to Google)."""
    try:
        flow = get_oauth_flow()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    now = time.time()
    _cleanup_expired_flows(now)
    _PENDING_OAUTH_FLOWS[state] = (flow, now)
    return RedirectResponse(auth_url)


@router.get(
    "/callback",
    operation_id="oauth_google_callback",
    include_in_schema=True,
)
async def google_oauth_callback(
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
):
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    if not state:
        raise HTTPException(status_code=400, detail="Missing OAuth state")

    now = time.time()
    _cleanup_expired_flows(now)
    pending = _PENDING_OAUTH_FLOWS.pop(state, None)
    if pending is None:
        raise HTTPException(
            status_code=400,
            detail="OAuth state is missing or expired. Start again at /auth/google.",
        )
    flow = pending[0]

    # Log key exchange parameters (without secrets) to troubleshoot config mismatches.
    logger.info(
        "Attempting Google token exchange redirect_uri=%s client_id_suffix=%s",
        flow.redirect_uri,
        (flow.client_config.get("client_id", "")[-12:] if flow.client_config else ""),
    )

    try:
        flow.fetch_token(code=code)
    except Exception as e:
        response_text = getattr(getattr(e, "response", None), "text", "")
        exception_text = str(e).strip()
        exception_repr = repr(e).strip()
        exception_type = type(e).__name__
        logger.exception(
            "Token exchange failed redirect_uri=%s google_response=%s exception=%s repr=%s type=%s",
            flow.redirect_uri,
            response_text or "<no response body>",
            exception_text or "<no exception text>",
            exception_repr or "<no repr>",
            exception_type,
        )
        hint = "Could not exchange code for token"
        if response_text:
            hint = f"{hint}: {response_text}"
        elif exception_text:
            hint = f"{hint}: {exception_text}"
        elif exception_repr:
            hint = f"{hint}: {exception_repr}"
        else:
            hint = f"{hint}: {exception_type}"
        raise HTTPException(status_code=400, detail=hint) from e

    creds = flow.credentials
    save_credentials(creds)
    return {"ok": True, "message": "Google Calendar authorized. You can close this window."}
