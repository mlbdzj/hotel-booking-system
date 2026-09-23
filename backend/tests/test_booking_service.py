"""订单业务规则：晚数、库存区间占用、剩余房量与价格计算（service 层）。"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.schemas.booking import BookingIn
from app.services.booking_service import (
    build_booking,
    nights_between,
    occupied_rooms,
    remaining_rooms,
    validate_booking,
)
from helpers import seed_booking


def _in(days: int) -> date:
    return date.today() + timedelta(days=days)


def _payload(
    hotel, room_type, *, check_in: date, check_out: date, rooms: int = 1, guests: int = 2, **extra
):
    return BookingIn(
        hotel_id=hotel.id,
        room_type_id=room_type.id,
        check_in_date=check_in,
        check_out_date=check_out,
        rooms=rooms,
        guests=guests,
        **extra,
    )


# ---------- 晚数 ----------


def test_nights_between_counts_calendar_days():
    assert nights_between(date(2026, 9, 21), date(2026, 9, 24)) == 3
    assert nights_between(date(2026, 9, 21), date(2026, 9, 22)) == 1


def test_nights_between_crosses_month_boundary():
    assert nights_between(date(2026, 9, 30), date(2026, 10, 2)) == 2


# ---------- 库存区间占用 ----------


def test_occupied_rooms_is_zero_without_booking(db, seed):
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 0


@pytest.mark.parametrize(
    "existing_in, existing_out, query_in, query_out",
    [
        (7, 9, 7, 9),  # 完全重合
        (7, 9, 8, 10),  # 右侧部分重合
        (7, 9, 6, 8),  # 左侧部分重合
        (7, 12, 8, 9),  # 查询区间被包含
        (8, 9, 7, 12),  # 查询区间包含已有
        (7, 9, 8, 9),  # 单晚落在区间内
    ],
)
def test_occupied_rooms_counts_overlapping_ranges(db, seed, existing_in, existing_out, query_in, query_out):
    seed_booking(
        db,
        user=seed.member,
        hotel=seed.hotel,
        room_type=seed.king,
        rooms=1,
        days_from=existing_in,
        nights=existing_out - existing_in,
    )
    assert occupied_rooms(db, seed.king.id, _in(query_in), _in(query_out)) == 1


def test_occupied_rooms_ignores_adjacent_range(db, seed):
    """[入住, 退房) 左闭右开：上一单退房当天入住不算占用。"""
    seed_booking(db, user=seed.member, hotel=seed.hotel, room_type=seed.king, days_from=7, nights=2)
    assert occupied_rooms(db, seed.king.id, _in(9), _in(11)) == 0
    assert occupied_rooms(db, seed.king.id, _in(5), _in(7)) == 0


@pytest.mark.parametrize("status", ["rejected", "canceled"])
def test_occupied_rooms_ignores_inactive_status(db, seed, status):
    seed_booking(
        db, user=seed.member, hotel=seed.hotel, room_type=seed.king, rooms=2, status=status, days_from=7, nights=2
    )
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 0


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_occupied_rooms_counts_active_status(db, seed, status):
    seed_booking(
        db, user=seed.member, hotel=seed.hotel, room_type=seed.king, rooms=2, status=status, days_from=7, nights=2
    )
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 2


def test_occupied_rooms_sums_multiple_bookings(db, seed):
    seed_booking(db, user=seed.member, hotel=seed.hotel, room_type=seed.king, rooms=1, days_from=7, nights=2)
    seed_booking(db, user=seed.stranger, hotel=seed.hotel, room_type=seed.king, rooms=2, days_from=8, nights=2)
    assert occupied_rooms(db, seed.king.id, _in(8), _in(9)) == 3


def test_occupied_rooms_excludes_own_booking(db, seed):
    booking = seed_booking(
        db, user=seed.member, hotel=seed.hotel, room_type=seed.king, rooms=2, days_from=7, nights=2
    )
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 2
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9), exclude_id=booking.id) == 0


def test_occupied_rooms_only_counts_target_room_type(db, seed):
    seed_booking(db, user=seed.member, hotel=seed.hotel, room_type=seed.twin, rooms=1, days_from=7, nights=2)
    assert occupied_rooms(db, seed.king.id, _in(7), _in(9)) == 0


# ---------- 剩余房量 ----------


def test_remaining_rooms_equals_quantity_minus_occupied(db, seed):
    seed_booking(db, user=seed.member, hotel=seed.hotel, room_type=seed.king, rooms=2, days_from=7, nights=2)
    assert seed.king.quantity == 3
    assert remaining_rooms(db, seed.king, _in(7), _in(9)) == 1


def test_remaining_rooms_never_negative(db, seed):
    """历史脏数据导致占用超过房量时，剩余房量兜底为 0。"""
    seed_booking(db, user=seed.member, hotel=seed.hotel, room_type=seed.twin, rooms=5, days_from=7, nights=2)
    assert remaining_rooms(db, seed.twin, _in(7), _in(9)) == 0


# ---------- 下单校验 ----------


def test_validate_rejects_check_in_before_today(db, seed):
    payload = _payload(seed.hotel, seed.king, check_in=_in(-1), check_out=_in(1))
    with pytest.raises(HTTPException) as error:
        validate_booking(db, seed.member, payload)
    assert error.value.status_code == 400
    assert "入住日期不能早于今天" in error.value.detail


def test_validate_rejects_rooms_over_quantity(db, seed):
    payload = _payload(seed.hotel, seed.king, check_in=_in(7), check_out=_in(9), rooms=20, guests=2)
    with pytest.raises(HTTPException) as error:
        validate_booking(db, seed.member, payload)
    assert "房量只有" in error.value.detail


def test_validate_rejects_guests_over_capacity(db, seed):
    payload = _payload(seed.hotel, seed.king, check_in=_in(7), check_out=_in(9), rooms=2, guests=5)
    with pytest.raises(HTTPException) as error:
        validate_booking(db, seed.member, payload)
    assert "入住人数超过上限" in error.value.detail


def test_validate_allows_guests_up_to_capacity_times_rooms(db, seed):
    payload = _payload(seed.hotel, seed.king, check_in=_in(7), check_out=_in(9), rooms=2, guests=4)
    hotel, room_type = validate_booking(db, seed.member, payload)
    assert hotel.id == seed.hotel.id
    assert room_type.id == seed.king.id


def test_validate_rejects_closed_hotel(db, seed):
    payload = _payload(seed.closed_hotel, seed.closed_room, check_in=_in(7), check_out=_in(9))
    with pytest.raises(HTTPException) as error:
        validate_booking(db, seed.member, payload)
    assert error.value.status_code == 400
    assert "暂停营业" in error.value.detail


def test_validate_rejects_unopened_room_type(db, seed):
    payload = _payload(seed.hotel, seed.maintenance, check_in=_in(7), check_out=_in(9))
    with pytest.raises(HTTPException) as error:
        validate_booking(db, seed.member, payload)
    assert "暂不可预订" in error.value.detail


def test_validate_rejects_room_type_from_other_hotel(db, seed):
    payload = _payload(seed.hotel, seed.closed_room, check_in=_in(7), check_out=_in(9))
    with pytest.raises(HTTPException) as error:
        validate_booking(db, seed.member, payload)
    assert "不属于所选酒店" in error.value.detail


def test_validate_rejects_missing_hotel(db, seed):
    payload = BookingIn(
        hotel_id=9999,
        room_type_id=seed.king.id,
        check_in_date=_in(7),
        check_out_date=_in(9),
        rooms=1,
        guests=2,
    )
    with pytest.raises(HTTPException) as error:
        validate_booking(db, seed.member, payload)
    assert error.value.status_code == 404


def test_validate_rejects_oversell_with_remaining_in_message(db, seed):
    """双床房只有 1 间：已被占用后再订 1 间必须被拒，并提示剩余数量。"""
    seed_booking(db, user=seed.member, hotel=seed.hotel, room_type=seed.twin, rooms=1, days_from=7, nights=2)
    payload = _payload(seed.hotel, seed.twin, check_in=_in(7), check_out=_in(9))
    with pytest.raises(HTTPException) as error:
        validate_booking(db, seed.member, payload)
    assert "仅剩 0 间可订" in error.value.detail


# ---------- 价格与落库前的构造 ----------


def test_build_booking_calculates_total_amount(db, seed):
    payload = _payload(seed.hotel, seed.king, check_in=_in(7), check_out=_in(10), rooms=2, guests=4)
    booking = build_booking(db, seed.member, payload)
    assert booking.nights == 3
    assert booking.total_amount == Decimal("458") * 3 * 2
    assert float(booking.total_amount) == 2748.0


def test_build_booking_sets_pending_status_and_owner(db, seed):
    payload = _payload(seed.hotel, seed.king, check_in=_in(7), check_out=_in(8))
    booking = build_booking(db, seed.member, payload)
    assert booking.status == "pending"
    assert booking.user_id == seed.member.id
    assert booking.remark == ""


def test_build_booking_falls_back_to_user_phone(db, seed):
    seed.member.phone = "13800000000"
    payload = _payload(seed.hotel, seed.king, check_in=_in(7), check_out=_in(8))
    booking = build_booking(db, seed.member, payload)
    assert booking.contact_phone == "13800000000"


def test_build_booking_keeps_explicit_phone(db, seed):
    seed.member.phone = "13800000000"
    payload = _payload(seed.hotel, seed.king, check_in=_in(7), check_out=_in(8), contact_phone="13911112222")
    booking = build_booking(db, seed.member, payload)
    assert booking.contact_phone == "13911112222"
