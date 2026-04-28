from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class AvailabilityRequest(BaseModel):
    start_time: datetime = Field(..., description="Slot start (ISO 8601)")
    end_time: datetime = Field(..., description="Slot end (ISO 8601)")
    time_zone: str = Field(
        default="UTC",
        description="IANA timezone used when interpreting naive datetimes",
    )


class CreateEventRequest(BaseModel):
    summary: str = Field(..., min_length=1, max_length=1024)
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    time_zone: str = Field(default="UTC")
    attendees: list[EmailStr] = Field(default_factory=list)


class ListEventsRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    time_zone: str = Field(default="UTC")
    max_results: int = Field(default=50, ge=1, le=250)


class SaveDemographicsRequest(BaseModel):
    name: str = Field(..., min_length=1)
    age_range: str = Field(..., min_length=1)
    region: str = Field(..., min_length=1)
    ethnicity: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)


class GetDemographicsRequest(BaseModel):
    record_id: int = Field(..., ge=1)
