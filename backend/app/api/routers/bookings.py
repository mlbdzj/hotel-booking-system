from datetime import date as date_type
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.serializers import booking_to_dict, refresh_completed_status
from app.db.session import get_db
from app.models import Booking, Hotel, RoomType, User
from app.schemas.booking import BookingIn, BookingOut, BookingReview
from app.schemas.common import Message, Page
from app.services.booking_service import ACTIVE_STATUS, create_booking, remaining_rooms

router = APIRouter(prefix="/api/bookings", tags=["订单管理"])


def _serialize(db: Session, bookings: list[Booking]) -> list[dict]:
    if not bookings:
        return []
    hotel_names = dict(
        db.execute(select(Hotel.id, Hotel.name).where(Hotel.id.in_({item.hotel_id for item in bookings}))).all()
    )
    room_type_names = dict(
        db.execute(
            select(RoomType.id, RoomType.name).where(RoomType.id.in_({item.room_type_id for item in bookings}))
        ).all()
    )
    user_ids = {item.user_id for item in bookings} | {item.reviewer_id for item in bookings if item.reviewer_id}
    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()}

    return [
        booking_to_dict(
            item,
            hotel_names.get(item.hotel_id, ""),
            room_type_names.get(item.room_type_id, ""),
            users.get(item.user_id),
            users.get(item.reviewer_id) if item.reviewer_id else None,
        )
        for item in bookings
    ]


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking_endpoint(
    payload: BookingIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = create_booking(db, current_user, payload)
    return _serialize(db, [booking])[0]


@router.get("/my", response_model=Page[BookingOut])
def list_my_bookings(
    status_filter: str = Query(default="", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = [Booking.user_id == current_user.id]
    if status_filter:
        conditions.append(Booking.status == status_filter)

    total = db.scalar(select(func.count(Booking.id)).where(*conditions)) or 0
    bookings = db.scalars(
        select(Booking)
        .where(*conditions)
        .order_by(Booking.check_in_date.desc(), Booking.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    refresh_completed_status(db, list(bookings))
    return {"total": total, "items": _serialize(db, list(bookings))}


@router.get("", response_model=Page[BookingOut])
def list_bookings(
    status_filter: str = Query(default="", alias="status"),
    hotel_id: int | None = Query(default=None),
    check_in_date: date_type | None = Query(default=None),
    keyword: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    conditions = []
    if status_filter:
        conditions.append(Booking.status == status_filter)
    if hotel_id:
        conditions.append(Booking.hotel_id == hotel_id)
    if check_in_date:
        conditions.append(Booking.check_in_date == check_in_date)
    if keyword:
        like = f"%{keyword.strip()}%"
        user_ids = select(User.id).where(or_(User.username.like(like), User.name.like(like)))
        conditions.append(Booking.user_id.in_(user_ids))

    total = db.scalar(select(func.count(Booking.id)).where(*conditions)) or 0
    bookings = db.scalars(
        select(Booking)
        .where(*conditions)
        .order_by(
            case((Booking.status == "pending", 0), else_=1),
            Booking.check_in_date.desc(),
            Booking.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    refresh_completed_status(db, list(bookings))
    return {"total": total, "items": _serialize(db, list(bookings))}


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if booking.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看该订单")
    return _serialize(db, [booking])[0]


@router.post("/{booking_id}/review", response_model=BookingOut)
def review_booking(
    booking_id: int,
    payload: BookingReview,
    reviewer: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if booking.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该订单已处理，无法重复操作")

    if payload.action == "confirm":
        room_type = db.get(RoomType, booking.room_type_id)
        if room_type is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房型不存在")
        remaining = remaining_rooms(
            db, room_type, booking.check_in_date, booking.check_out_date, exclude_id=booking.id
        )
        if booking.rooms > remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"该房型在入住日期内仅剩 {remaining} 间，无法确认该订单",
            )
        booking.status = "confirmed"
    else:
        booking.status = "rejected"

    booking.remark = payload.remark
    booking.reviewer_id = reviewer.id
    booking.reviewed_at = datetime.now()
    db.commit()
    db.refresh(booking)
    return _serialize(db, [booking])[0]


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    if booking.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权操作该订单")
    if booking.status not in ACTIVE_STATUS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前状态的订单无法取消")

    booking.status = "canceled"
    if current_user.role == "admin":
        booking.remark = "管理员取消"
    db.commit()
    db.refresh(booking)
    return _serialize(db, [booking])[0]


@router.delete("/{booking_id}", response_model=Message)
def delete_booking(booking_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    db.delete(booking)
    db.commit()
    return Message(message="删除成功")
