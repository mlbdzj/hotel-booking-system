from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookingIn(BaseModel):
    hotel_id: int = Field(ge=1)
    room_type_id: int = Field(ge=1)
    check_in_date: date
    check_out_date: date
    rooms: int = Field(default=1, ge=1, le=20)
    guests: int = Field(default=1, ge=1, le=100)
    contact_phone: str = Field(default="", max_length=20)
    special_request: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def check_dates(self):
        if self.check_out_date <= self.check_in_date:
            raise ValueError("退房日期必须晚于入住日期")
        return self


class BookingReview(BaseModel):
    action: str = Field(pattern="^(confirm|reject)$")
    remark: str = Field(default="", max_length=255)


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hotel_id: int
    hotel_name: str = ""
    room_type_id: int
    room_type_name: str = ""
    user_id: int
    username: str = ""
    user_name: str = ""
    check_in_date: date
    check_out_date: date
    nights: int
    rooms: int
    guests: int
    contact_phone: str = ""
    total_amount: float = 0
    special_request: str = ""
    status: str
    status_text: str = ""
    remark: str = ""
    reviewer_name: str = ""
    reviewed_at: datetime | None = None
    created_at: datetime | None = None


class StatOverview(BaseModel):
    hotel_total: int
    room_type_total: int
    user_total: int
    booking_total: int
    pending_total: int
    today_check_in_total: int
    occupancy_rate: int
    week_total: int
    week_start: date
    week_end: date
    hotel_ranking: list[dict]
    recent_bookings: list[BookingOut]
