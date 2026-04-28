from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ConflictItem(BaseModel):
    event_id: str
    summary: str
    start: datetime
    end: datetime


class AvailabilityResponse(BaseModel):
    available: bool
    conflicts: list[ConflictItem] = Field(default_factory=list)


class CreateEventResponse(BaseModel):
    event_id: str
    status: str
    html_link: str


class ListEventsItem(BaseModel):
    event_id: str
    summary: str
    start: datetime
    end: datetime
    html_link: Optional[str] = None


class ListEventsResponse(BaseModel):
    events: list[ListEventsItem] = Field(default_factory=list)


class DemographicsRecord(BaseModel):
    id: int
    name: str
    age_range: str
    region: str
    ethnicity: str
    language: str
    saved_at: str


class SaveDemographicsResponse(BaseModel):
    status: str
    id: int
    name: str
    age_range: str
    region: str
    ethnicity: str
    language: str
    saved_at: str


class ListAllDemographicsResponse(BaseModel):
    total: int
    records: list[DemographicsRecord] = Field(default_factory=list)
