# serializers/operating_hour.py
from datetime import time
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

DayOfWeek = Literal["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


class OperatingHourCreateSchema(BaseModel):
    day_of_week: DayOfWeek
    open_time: Optional[time] = None  # send like "09:00"
    close_time: Optional[time] = None  # send like "17:00"
    is_closed: bool = False

    @model_validator(mode="after")
    def check_times(self):
        if not self.is_closed:
            if self.open_time is None or self.close_time is None:
                raise ValueError("open_time and close_time are required unless is_closed is true")
            if self.open_time == self.close_time:
                raise ValueError("open_time and close_time can't be the same")
        return self


class OperatingHourUpdateSchema(BaseModel):
    """All optional. Only send what you want to change."""

    day_of_week: Optional[DayOfWeek] = None
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: Optional[bool] = None


class OperatingHourSchema(BaseModel):
    """What the API sends back about an operating hour."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    business_id: int
    branch_id: int
    day_of_week: str
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool