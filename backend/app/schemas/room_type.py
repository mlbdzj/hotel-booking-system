from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROOM_TYPE_STATUS = {"open", "maintenance", "closed"}


class RoomTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    code: str = Field(default="", max_length=50)
    bed_type: str = Field(default="", max_length=40)
    hotel_id: int = Field(ge=1)
    price: float = Field(default=0, ge=0, le=999999)
    capacity: int = Field(default=2, ge=1, le=20)
    quantity: int = Field(default=1, ge=1, le=999)
    status: str = "open"
    description: str = ""

    @field_validator("status")
    @classmethod
    def check_status(cls, value: str) -> str:
        if value not in ROOM_TYPE_STATUS:
            raise ValueError("房型状态不合法")
        return value


class RoomTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    bed_type: str
    hotel_id: int
    hotel_name: str = ""
    price: float
    capacity: int
    quantity: int
    status: str
    description: str
    created_at: datetime | None = None
