"""订单业务规则：页面下单与助手下单共用同一套校验（含房量库存与防超卖）。"""

from datetime import date as date_type
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Booking, Hotel, RoomType, User
from app.schemas.booking import BookingIn

# 占用房量的订单状态：待确认与已确认都会占住库存
ACTIVE_STATUS = ("pending", "confirmed")


def nights_between(check_in: date_type, check_out: date_type) -> int:
    return (check_out - check_in).days


def occupied_rooms(
    db: Session,
    room_type_id: int,
    check_in: date_type,
    check_out: date_type,
    exclude_id: int | None = None,
) -> int:
    """统计与 [check_in, check_out) 有重叠的有效订单已占用的间数。"""
    conditions = [
        Booking.room_type_id == room_type_id,
        Booking.status.in_(ACTIVE_STATUS),
        Booking.check_in_date < check_out,
        Booking.check_out_date > check_in,
    ]
    if exclude_id:
        conditions.append(Booking.id != exclude_id)
    return db.scalar(select(func.coalesce(func.sum(Booking.rooms), 0)).where(*conditions)) or 0


def remaining_rooms(
    db: Session,
    room_type: RoomType,
    check_in: date_type,
    check_out: date_type,
    exclude_id: int | None = None,
) -> int:
    return max(0, room_type.quantity - occupied_rooms(db, room_type.id, check_in, check_out, exclude_id))


def validate_booking(db: Session, user: User, payload: BookingIn) -> tuple[Hotel, RoomType]:
    """校验订单是否可下单，返回 (酒店, 房型)；不合法时抛 HTTPException。"""
    hotel = db.get(Hotel, payload.hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="酒店不存在")
    if hotel.status != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该酒店暂停营业")

    room_type = db.get(RoomType, payload.room_type_id)
    if room_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房型不存在")
    if room_type.hotel_id != hotel.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该房型不属于所选酒店")
    if room_type.status != "open":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该房型暂不可预订")

    if payload.check_in_date < date_type.today():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="入住日期不能早于今天")
    if payload.rooms > room_type.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"该房型房量只有 {room_type.quantity} 间"
        )
    if payload.guests > room_type.capacity * payload.rooms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"入住人数超过上限（每间可住 {room_type.capacity} 人，共 {payload.rooms} 间）",
        )

    remaining = remaining_rooms(db, room_type, payload.check_in_date, payload.check_out_date)
    if payload.rooms > remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{payload.check_in_date} 至 {payload.check_out_date} 期间该房型仅剩 {remaining} 间可订"
            ),
        )
    return hotel, room_type


def build_booking(db: Session, user: User, payload: BookingIn) -> Booking:
    """校验并构造（未落库）的订单对象，含晚数与总价计算。"""
    hotel, room_type = validate_booking(db, user, payload)
    nights = nights_between(payload.check_in_date, payload.check_out_date)
    total_amount = Decimal(str(room_type.price)) * nights * payload.rooms

    return Booking(
        hotel_id=hotel.id,
        room_type_id=room_type.id,
        user_id=user.id,
        check_in_date=payload.check_in_date,
        check_out_date=payload.check_out_date,
        nights=nights,
        rooms=payload.rooms,
        guests=payload.guests,
        contact_phone=payload.contact_phone or user.phone or "",
        total_amount=total_amount,
        special_request=payload.special_request,
        status="pending",
        remark="",
    )


def create_booking(db: Session, user: User, payload: BookingIn) -> Booking:
    booking = build_booking(db, user, payload)
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking
