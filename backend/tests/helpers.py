"""测试公共小工具：鉴权头、下单参数、造订单。"""

from datetime import date, timedelta

from app.core.security import create_access_token
from app.models import Booking


def auth_headers(user) -> dict[str, str]:
    """按用户签发 Token，等价于前端登录后拿到的 Authorization 头。"""
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def booking_payload(
    hotel,
    room_type,
    *,
    days_from: int = 7,
    nights: int = 2,
    rooms: int = 1,
    guests: int = 2,
    **extra,
) -> dict:
    check_in = date.today() + timedelta(days=days_from)
    payload = {
        "hotel_id": hotel.id,
        "room_type_id": room_type.id,
        "check_in_date": check_in.isoformat(),
        "check_out_date": (check_in + timedelta(days=nights)).isoformat(),
        "rooms": rooms,
        "guests": guests,
    }
    payload.update(extra)
    return payload


def seed_booking(
    db,
    *,
    user,
    hotel,
    room_type,
    status: str = "pending",
    days_from: int = 7,
    nights: int = 2,
    rooms: int = 1,
    guests: int = 2,
) -> Booking:
    """直接落一条订单，用于构造库存占用场景。"""
    check_in = date.today() + timedelta(days=days_from)
    check_out = check_in + timedelta(days=nights)
    booking = Booking(
        hotel_id=hotel.id,
        room_type_id=room_type.id,
        user_id=user.id,
        check_in_date=check_in,
        check_out_date=check_out,
        nights=nights,
        rooms=rooms,
        guests=guests,
        contact_phone="13900000000",
        total_amount=float(room_type.price) * nights * rooms,
        special_request="",
        status=status,
        remark="",
    )
    db.add(booking)
    db.flush()
    return booking
