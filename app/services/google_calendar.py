import logging
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.schemas.request_models import AvailabilityRequest, CreateEventRequest
from app.schemas.response_models import (
    AvailabilityResponse,
    ConflictItem,
    CreateEventResponse,
    ListEventsItem,
    ListEventsResponse,
)

logger = logging.getLogger(__name__)

CALENDAR_ID_PRIMARY = "primary"


def _ensure_aware(dt: datetime, tz_name: str) -> datetime:
    if dt.tzinfo is not None:
        return dt
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    return dt.replace(tzinfo=tz)


def _to_rfc3339(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z") if dt.tzinfo == timezone.utc else dt.isoformat()


def _parse_event_time(raw: dict[str, Any]) -> datetime:
    if "dateTime" in raw:
        s = raw["dateTime"]
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    if "date" in raw:
        return datetime.fromisoformat(raw["date"] + "T00:00:00+00:00")
    raise ValueError("Event has no start/end time")


def _events_overlap(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> bool:
    return not (a_end <= b_start or a_start >= b_end)


def build_calendar_service(creds: Credentials):
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


class GoogleCalendarService:
    def __init__(self, creds: Credentials):
        self._service = build_calendar_service(creds)

    def check_availability(self, req: AvailabilityRequest) -> AvailabilityResponse:
        start = _ensure_aware(req.start_time, req.time_zone)
        end = _ensure_aware(req.end_time, req.time_zone)
        if end <= start:
            raise ValueError("end_time must be after start_time")

        body = {
            "timeMin": _to_rfc3339(start),
            "timeMax": _to_rfc3339(end),
            "timeZone": req.time_zone,
            "items": [{"id": CALENDAR_ID_PRIMARY}],
        }
        try:
            fb = self._service.freebusy().query(body=body).execute()
        except HttpError as e:
            logger.exception("freebusy.query failed")
            raise RuntimeError(f"Google Calendar freebusy error: {e}") from e

        busy = (
            fb.get("calendars", {})
            .get(CALENDAR_ID_PRIMARY, {})
            .get("busy", [])
        )
        if not busy:
            return AvailabilityResponse(available=True, conflicts=[])

        conflicts = self._list_conflicts_in_window(start, end)
        return AvailabilityResponse(available=False, conflicts=conflicts)

    def _list_conflicts_in_window(
        self, window_start: datetime, window_end: datetime
    ) -> list[ConflictItem]:
        time_min = _to_rfc3339(window_start)
        time_max = _to_rfc3339(window_end)
        try:
            resp = (
                self._service.events()
                .list(
                    calendarId=CALENDAR_ID_PRIMARY,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
        except HttpError as e:
            logger.exception("events.list failed")
            raise RuntimeError(f"Google Calendar events.list error: {e}") from e

        items: list[ConflictItem] = []
        for ev in resp.get("items", []):
            status = ev.get("status")
            if status == "cancelled":
                continue
            try:
                es = _parse_event_time(ev["start"])
                ee = _parse_event_time(ev["end"])
            except (KeyError, ValueError):
                continue
            if _events_overlap(window_start, window_end, es, ee):
                items.append(
                    ConflictItem(
                        event_id=ev.get("id", ""),
                        summary=ev.get("summary", "(no title)"),
                        start=es,
                        end=ee,
                    )
                )
        return items

    def slot_is_free(self, start: datetime, end: datetime, time_zone: str) -> bool:
        req = AvailabilityRequest(
            start_time=start, end_time=end, time_zone=time_zone
        )
        return self.check_availability(req).available

    def create_event(self, req: CreateEventRequest) -> CreateEventResponse:
        start = _ensure_aware(req.start_time, req.time_zone)
        end = _ensure_aware(req.end_time, req.time_zone)
        if end <= start:
            raise ValueError("end_time must be after start_time")

        if not self.slot_is_free(start, end, req.time_zone):
            conflicts = self._list_conflicts_in_window(start, end)
            detail = ", ".join(c.summary for c in conflicts[:5]) or "unknown"
            raise ValueError(
                f"Time slot is not available (overlapping events: {detail})"
            )

        body: dict[str, Any] = {
            "summary": req.summary,
            "start": {"dateTime": _to_rfc3339(start), "timeZone": req.time_zone},
            "end": {"dateTime": _to_rfc3339(end), "timeZone": req.time_zone},
        }
        if req.description:
            body["description"] = req.description
        if req.attendees:
            body["attendees"] = [{"email": e} for e in req.attendees]

        try:
            created = (
                self._service.events()
                .insert(
                    calendarId=CALENDAR_ID_PRIMARY,
                    body=body,
                    sendUpdates="all" if req.attendees else "none",
                )
                .execute()
            )
        except HttpError as e:
            logger.exception("events.insert failed")
            raise RuntimeError(f"Google Calendar events.insert error: {e}") from e

        return CreateEventResponse(
            event_id=created.get("id", ""),
            status=created.get("status", "confirmed"),
            html_link=created.get("htmlLink", ""),
        )

    def list_events(
        self,
        start: datetime,
        end: datetime,
        time_zone: str,
        max_results: int = 50,
    ) -> ListEventsResponse:
        ws = _ensure_aware(start, time_zone)
        we = _ensure_aware(end, time_zone)
        time_min = _to_rfc3339(ws)
        time_max = _to_rfc3339(we)
        try:
            resp = (
                self._service.events()
                .list(
                    calendarId=CALENDAR_ID_PRIMARY,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=max_results,
                )
                .execute()
            )
        except HttpError as e:
            logger.exception("events.list failed")
            raise RuntimeError(f"Google Calendar events.list error: {e}") from e

        out: list[ListEventsItem] = []
        for ev in resp.get("items", []):
            if ev.get("status") == "cancelled":
                continue
            try:
                es = _parse_event_time(ev["start"])
                ee = _parse_event_time(ev["end"])
            except (KeyError, ValueError):
                continue
            out.append(
                ListEventsItem(
                    event_id=ev.get("id", ""),
                    summary=ev.get("summary", "(no title)"),
                    start=es,
                    end=ee,
                    html_link=ev.get("htmlLink"),
                )
            )
        return ListEventsResponse(events=out)
