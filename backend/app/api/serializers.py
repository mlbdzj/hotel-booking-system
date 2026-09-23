from datetime import date, datetime

from app.models import Booking, Hotel, RoomType, User

BOOKING_STATUS_TEXT = {
    "pending": "待确认",
    "confirmed": "已确认",
    "rejected": "已拒绝",
    "canceled": "已取消",
    "completed": "已完成",
}

ROOM_TYPE_STATUS_TEXT = {
    "open": "可预订",
    "maintenance": "维护中",
    "closed": "停售",
}


def hotel_to_dict(hotel: Hotel, room_type_count: int = 0, booking_count: int = 0) -> dict:
    return {
        "id": hotel.id,
        "name": hotel.name,
        "city": hotel.city,
        "address": hotel.address,
        "star": hotel.star,
        "room_count": hotel.room_count,
        "check_in_time": hotel.check_in_time,
        "check_out_time": hotel.check_out_time,
        "status": hotel.status,
        "description": hotel.description,
        "created_at": hotel.created_at,
        "room_type_count": room_type_count,
        "booking_count": booking_count,
    }


def room_type_to_dict(room_type: RoomType, hotel_name: str = "") -> dict:
    return {
        "id": room_type.id,
        "name": room_type.name,
        "code": room_type.code,
        "bed_type": room_type.bed_type,
        "hotel_id": room_type.hotel_id,
        "hotel_name": hotel_name,
        "price": float(room_type.price or 0),
        "capacity": room_type.capacity,
        "quantity": room_type.quantity,
        "status": room_type.status,
        "description": room_type.description,
        "created_at": room_type.created_at,
    }


def booking_to_dict(
    booking: Booking,
    hotel_name: str = "",
    room_type_name: str = "",
    user: User | None = None,
    reviewer: User | None = None,
) -> dict:
    return {
        "id": booking.id,
        "hotel_id": booking.hotel_id,
        "hotel_name": hotel_name,
        "room_type_id": booking.room_type_id,
        "room_type_name": room_type_name,
        "user_id": booking.user_id,
        "username": user.username if user else "",
        "user_name": (user.name or user.username) if user else "",
        "check_in_date": booking.check_in_date,
        "check_out_date": booking.check_out_date,
        "nights": booking.nights,
        "rooms": booking.rooms,
        "guests": booking.guests,
        "contact_phone": booking.contact_phone,
        "total_amount": float(booking.total_amount or 0),
        "special_request": booking.special_request,
        "status": booking.status,
        "status_text": BOOKING_STATUS_TEXT.get(booking.status, booking.status),
        "remark": booking.remark,
        "reviewer_name": (reviewer.name or reviewer.username) if reviewer else "",
        "reviewed_at": booking.reviewed_at,
        "created_at": booking.created_at,
    }


def refresh_completed_status(db, bookings: list[Booking]) -> None:
    """退房日期已过的已确认订单，自动标记为已完成。"""
    today = date.today()
    changed = False
    for booking in bookings:
        if booking.status == "confirmed" and booking.check_out_date < today:
            booking.status = "completed"
            changed = True
    if changed:
        db.commit()
