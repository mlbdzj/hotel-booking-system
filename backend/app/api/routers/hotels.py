from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.serializers import ROOM_TYPE_STATUS_TEXT, hotel_to_dict
from app.db.session import get_db
from app.models import Booking, Hotel, RoomType, User
from app.schemas.common import Message, Page
from app.schemas.hotel import HotelIn, HotelOut
from app.services.booking_service import nights_between, remaining_rooms

router = APIRouter(prefix="/api/hotels", tags=["酒店管理"])


def _counts(db: Session, hotel_ids: list[int]) -> dict[int, dict[str, int]]:
    result = {hotel_id: {"room_type_count": 0, "booking_count": 0} for hotel_id in hotel_ids}
    if not hotel_ids:
        return result
    for hotel_id, count in db.execute(
        select(RoomType.hotel_id, func.count(RoomType.id))
        .where(RoomType.hotel_id.in_(hotel_ids))
        .group_by(RoomType.hotel_id)
    ).all():
        result[hotel_id]["room_type_count"] = count
    for hotel_id, count in db.execute(
        select(Booking.hotel_id, func.count(Booking.id))
        .where(Booking.hotel_id.in_(hotel_ids))
        .group_by(Booking.hotel_id)
    ).all():
        result[hotel_id]["booking_count"] = count
    return result


@router.get("", response_model=Page[HotelOut])
def list_hotels(
    keyword: str = Query(default=""),
    city: str = Query(default=""),
    status_filter: int | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = []
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(Hotel.name.like(like) | Hotel.address.like(like))
    if city:
        conditions.append(Hotel.city == city)
    if status_filter is not None:
        conditions.append(Hotel.status == status_filter)

    total = db.scalar(select(func.count(Hotel.id)).where(*conditions)) or 0
    hotels = db.scalars(
        select(Hotel)
        .where(*conditions)
        .order_by(Hotel.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    counts = _counts(db, [hotel.id for hotel in hotels])
    items = [
        hotel_to_dict(hotel, counts[hotel.id]["room_type_count"], counts[hotel.id]["booking_count"])
        for hotel in hotels
    ]
    return {"total": total, "items": items}


@router.get("/{hotel_id}", response_model=HotelOut)
def get_hotel(hotel_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    hotel = db.get(Hotel, hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="酒店不存在")
    counts = _counts(db, [hotel.id])
    return hotel_to_dict(hotel, counts[hotel.id]["room_type_count"], counts[hotel.id]["booking_count"])


@router.get("/{hotel_id}/availability")
def hotel_availability(
    hotel_id: int,
    check_in: date_type = Query(description="入住日期 YYYY-MM-DD"),
    check_out: date_type = Query(description="退房日期 YYYY-MM-DD"),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hotel = db.get(Hotel, hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="酒店不存在")
    if check_out <= check_in:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="退房日期必须晚于入住日期")

    room_types = db.scalars(
        select(RoomType).where(RoomType.hotel_id == hotel_id).order_by(RoomType.price.asc())
    ).all()
    items = []
    for room_type in room_types:
        remaining = remaining_rooms(db, room_type, check_in, check_out)
        items.append(
            {
                "id": room_type.id,
                "name": room_type.name,
                "bed_type": room_type.bed_type,
                "price": float(room_type.price or 0),
                "capacity": room_type.capacity,
                "quantity": room_type.quantity,
                "remaining": remaining,
                "status": room_type.status,
                "status_text": ROOM_TYPE_STATUS_TEXT.get(room_type.status, room_type.status),
                "bookable": room_type.status == "open" and remaining > 0,
            }
        )

    return {
        "hotel_id": hotel_id,
        "hotel_name": hotel.name,
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "nights": nights_between(check_in, check_out),
        "check_in_time": hotel.check_in_time,
        "check_out_time": hotel.check_out_time,
        "room_types": items,
    }


@router.post("", response_model=HotelOut, status_code=status.HTTP_201_CREATED)
def create_hotel(payload: HotelIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    exists = db.scalar(select(Hotel).where(Hotel.name == payload.name))
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="酒店名称已存在")
    hotel = Hotel(**payload.model_dump())
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return hotel_to_dict(hotel)


@router.put("/{hotel_id}", response_model=HotelOut)
def update_hotel(
    hotel_id: int, payload: HotelIn, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    hotel = db.get(Hotel, hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="酒店不存在")
    duplicated = db.scalar(select(Hotel).where(Hotel.name == payload.name, Hotel.id != hotel_id))
    if duplicated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="酒店名称已存在")
    for field, value in payload.model_dump().items():
        setattr(hotel, field, value)
    db.commit()
    db.refresh(hotel)
    counts = _counts(db, [hotel.id])
    return hotel_to_dict(hotel, counts[hotel.id]["room_type_count"], counts[hotel.id]["booking_count"])


@router.delete("/{hotel_id}", response_model=Message)
def delete_hotel(hotel_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    hotel = db.get(Hotel, hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="酒店不存在")
    booking_count = db.scalar(select(func.count(Booking.id)).where(Booking.hotel_id == hotel_id))
    if booking_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该酒店已有订单记录，无法删除")
    room_type_count = db.scalar(select(func.count(RoomType.id)).where(RoomType.hotel_id == hotel_id))
    if room_type_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先删除该酒店下的房型")
    db.delete(hotel)
    db.commit()
    return Message(message="删除成功")
