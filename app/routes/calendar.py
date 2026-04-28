import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.oauth import get_credentials
from app.schemas.request_models import (
    AvailabilityRequest,
    CreateEventRequest,
    ListEventsRequest,
)
from app.schemas.response_models import (
    AvailabilityResponse,
    CreateEventResponse,
    ListEventsResponse,
)
from app.services.google_calendar import GoogleCalendarService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools", tags=["mcp-tools"])


def get_calendar_service() -> GoogleCalendarService:
    try:
        creds = get_credentials()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return GoogleCalendarService(creds)


CalendarSvc = Annotated[GoogleCalendarService, Depends(get_calendar_service)]


@router.post(
    "/check-availability",
    operation_id="check_availability",
    response_model=AvailabilityResponse,
)
async def check_availability(payload: AvailabilityRequest, svc: CalendarSvc):
    """MCP tool: check if a time slot is free (uses Calendar freebusy + event details for conflicts)."""
    try:
        return svc.check_availability(payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        logger.exception("check_availability failed")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post(
    "/create-event",
    operation_id="create_event",
    response_model=CreateEventResponse,
)
async def create_event(payload: CreateEventRequest, svc: CalendarSvc):
    """MCP tool: create a booking when the slot is free."""
    try:
        return svc.create_event(payload)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RuntimeError as e:
        logger.exception("create_event failed")
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post(
    "/list-events",
    operation_id="list_events",
    response_model=ListEventsResponse,
)
async def list_events(payload: ListEventsRequest, svc: CalendarSvc):
    """Optional MCP tool: list events in a time window."""
    try:
        if payload.end_time <= payload.start_time:
            raise ValueError("end_time must be after start_time")
        return svc.list_events(
            payload.start_time,
            payload.end_time,
            payload.time_zone,
            max_results=payload.max_results,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        logger.exception("list_events failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
