"""自然语言预订：解析口语需求 -> 生成订单草稿 -> 用户确认后下单。"""

import re
from datetime import date as date_type
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools import detect_date, match_hotel
from app.models import Booking, Hotel, RoomType, User
from app.schemas.booking import BookingIn
from app.services.booking_service import create_booking, nights_between, validate_booking

DEFAULT_NIGHTS = 1

DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_NUM = r"\d{1,3}|[零一二两三四五六七八九十]{1,3}"

NIGHTS_PATTERN = re.compile(rf"(?<!入)(?:住|共|连住)?\s*(?P<num>{CN_NUM})\s*(?:晚|夜)")
ROOMS_PATTERN = re.compile(rf"(?P<num>{CN_NUM})\s*(?:间|间房|间客房)")
GUESTS_PATTERN = re.compile(rf"(?P<num>{CN_NUM})\s*(?:个|位|名)?\s*(?:人|客人|成人|住客)")
CHECKOUT_PATTERN = re.compile(rf"(?P<num>{CN_NUM})\s*[日号]?\s*(?:退房|离店)")

FILLER_WORDS = (
    "帮我",
    "帮忙",
    "我想",
    "我要",
    "要",
    "请",
    "预订",
    "预定",
    "订",
    "的房间",
    "房间",
    "入住",
    "住",
    "晚",
    "天",
    "一共",
    "共",
    "个",
    "位",
    "名",
    "人",
    "间",
    "的",
    "去",
    "在",
    "和",
    "一起",
    "需要",
)


def cn_to_int(text: str) -> int | None:
    value = (text or "").strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    if value == "十":
        return 10
    if "十" in value:
        left, _, right = value.partition("十")
        tens = DIGITS.get(left, 1) if left else 1
        ones = DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    total = 0
    for char in value:
        if char not in DIGITS:
            return None
        total = total * 10 + DIGITS[char]
    return total


def _match_number(pattern: re.Pattern, text: str) -> int | None:
    match = pattern.search(text or "")
    if not match:
        return None
    return cn_to_int(match.group("num"))


def parse_nights(text: str) -> int | None:
    return _match_number(NIGHTS_PATTERN, text)


def parse_rooms(text: str) -> int | None:
    return _match_number(ROOMS_PATTERN, text)


def parse_guests(text: str) -> int | None:
    return _match_number(GUESTS_PATTERN, text)


def match_room_type(db: Session, hotel: Hotel | None, text: str) -> RoomType | None:
    if hotel is None:
        return None
    normalized = (text or "").replace(" ", "")
    for room_type in db.scalars(select(RoomType).where(RoomType.hotel_id == hotel.id)).all():
        for candidate in {room_type.name, room_type.bed_type}:
            if candidate and candidate.replace(" ", "") in normalized:
                return room_type
    return None


def extract_special_request(text: str, hotel: Hotel | None, room_type: RoomType | None) -> str:
    remaining = text or ""
    for item in (hotel.name if hotel else "", room_type.name if room_type else "", room_type.bed_type if room_type else ""):
        if item:
            remaining = remaining.replace(item, "").replace(item.replace(" ", ""), "")
    for word in ("今天", "明天", "后天", "下周一", "下周二", "下周三", "下周四", "下周五", "下周六", "下周日"):
        remaining = remaining.replace(word, "")
    remaining = re.sub(r"((下个?)+|本|这)?(周|星期)[一二三四五六日天]", "", remaining)
    remaining = remaining.replace("入住", "").replace("退房", "").replace("离店", "")
    remaining = NIGHTS_PATTERN.sub("", remaining)
    remaining = ROOMS_PATTERN.sub("", remaining)
    remaining = GUESTS_PATTERN.sub("", remaining)
    remaining = re.sub(r"\d{4}\s*[-/年]\s*\d{1,2}\s*[-/月]\s*\d{1,2}\s*[日号]?", "", remaining)
    remaining = re.sub(r"\d{1,2}\s*[-/月]\s*\d{1,2}\s*[日号]?", "", remaining)
    remaining = re.sub(r"\d{1,2}\s*[日号]", "", remaining)
    # 先删长词再删短词，避免「需要安静楼层」被切成「需安静楼层」
    for word in sorted(FILLER_WORDS, key=len, reverse=True):
        remaining = remaining.replace(word, "")
    remaining = re.sub(r"[，。,.、！!？?；;:：\s]+", "", remaining)
    return remaining[:60] if len(remaining) >= 2 else ""


def parse_booking_text(db: Session, text: str) -> dict:
    hotel = match_hotel(db, text)
    room_type = match_room_type(db, hotel, text)
    check_in = detect_date(text)
    nights = parse_nights(text)

    check_out = None
    match = CHECKOUT_PATTERN.search(text)
    if match and check_in is not None:
        day = cn_to_int(match.group("num"))
        if day and 1 <= day <= 31:
            candidate = date_type(check_in.year, check_in.month, day)
            if candidate <= check_in:
                candidate = candidate + timedelta(days=32)
                candidate = date_type(candidate.year, candidate.month, day)
            check_out = candidate

    single_night_assumed = False
    if check_out is None and check_in is not None:
        if nights:
            check_out = check_in + timedelta(days=nights)
        else:
            check_out = check_in + timedelta(days=DEFAULT_NIGHTS)
            single_night_assumed = True

    return {
        "hotel": hotel,
        "hotel_name": hotel.name if hotel else "",
        "room_type": room_type,
        "room_type_name": room_type.name if room_type else "",
        "check_in_date": check_in,
        "check_out_date": check_out,
        "nights": nights_between(check_in, check_out) if check_in and check_out else nights,
        "rooms": parse_rooms(text),
        "guests": parse_guests(text),
        "special_request": extract_special_request(text, hotel, room_type),
        "assumed_single_night": single_night_assumed,
    }


def build_draft(
    db: Session,
    user: User,
    *,
    hotel: Hotel | None,
    hotel_name: str = "",
    room_type: RoomType | None,
    check_in_date: date_type | None,
    check_out_date: date_type | None,
    rooms: int | None,
    guests: int | None,
    special_request: str = "",
    note: str = "",
) -> dict:
    """生成订单草稿：包含解析结果、校验问题与摘要，不写数据库。"""
    problems: list[str] = []
    rooms = rooms or 1

    if hotel is None:
        problems.append(f"没有找到名为「{hotel_name}」的酒店，请确认酒店名称" if hotel_name else "还需要确认预订哪家酒店")
    if room_type is None:
        problems.append("还需要确认房型（例如大床房、双床房）")
    if check_in_date is None:
        problems.append("还需要确认入住日期")
    if check_out_date is None:
        problems.append("还需要确认退房日期或入住晚数")
    if guests is None:
        problems.append("还需要确认入住人数")
    if check_in_date and check_out_date and check_out_date <= check_in_date:
        problems.append("退房日期必须晚于入住日期")

    nights = nights_between(check_in_date, check_out_date) if check_in_date and check_out_date else None
    price = float(room_type.price or 0) if room_type else 0
    total_amount = round(price * (nights or 0) * rooms, 2)

    if not problems and hotel and room_type and check_in_date and check_out_date:
        payload = BookingIn(
            hotel_id=hotel.id,
            room_type_id=room_type.id,
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            rooms=rooms,
            guests=guests or 1,
            special_request=special_request or "",
        )
        try:
            validate_booking(db, user, payload)
        except HTTPException as error:
            problems.append(str(error.detail))

    draft = {
        "type": "booking_draft",
        "status": "invalid" if problems else "pending",
        "problems": problems,
        "note": note,
        "payload": {
            "hotel_id": hotel.id if hotel else None,
            "hotel_name": hotel.name if hotel else (hotel_name or ""),
            "room_type_id": room_type.id if room_type else None,
            "room_type_name": room_type.name if room_type else "",
            "check_in_date": check_in_date.isoformat() if check_in_date else "",
            "check_out_date": check_out_date.isoformat() if check_out_date else "",
            "nights": nights,
            "rooms": rooms,
            "guests": guests,
            "price": price,
            "total_amount": total_amount,
            "special_request": special_request or "",
        },
        "summary": "",
        "booking_id": None,
    }
    draft["summary"] = summarize_draft(draft)
    return draft


def summarize_draft(draft: dict) -> str:
    payload = draft["payload"]
    if draft["problems"]:
        return "还差这些信息或需要调整：" + "；".join(draft["problems"])

    def weekday(value: str) -> str:
        try:
            target = date_type.fromisoformat(value)
        except ValueError:
            return ""
        return "（周" + "一二三四五六日"[target.weekday()] + "）"

    return (
        f"{payload['hotel_name']}｜{payload['room_type_name']}｜"
        f"{payload['check_in_date']}{weekday(payload['check_in_date'])} 入住，"
        f"{payload['check_out_date']} 退房，共 {payload['nights']} 晚｜"
        f"{payload['rooms']} 间 / {payload['guests']} 人｜"
        f"总价 ¥{payload['total_amount']:.0f}"
        + (f"｜特殊要求：{payload['special_request']}" if payload["special_request"] else "")
    )


def prepare_from_text(db: Session, user: User, text: str) -> dict:
    parsed = parse_booking_text(db, text)
    note = ""
    if parsed.get("assumed_single_night"):
        note = "没有识别到入住晚数，暂按 1 晚计算，如需调整请重新说明。"
    return build_draft(
        db,
        user,
        hotel=parsed["hotel"],
        hotel_name=parsed["hotel_name"],
        room_type=parsed["room_type"],
        check_in_date=parsed["check_in_date"],
        check_out_date=parsed["check_out_date"],
        rooms=parsed["rooms"],
        guests=parsed["guests"],
        special_request=parsed["special_request"],
        note=note,
    )


def prepare_from_arguments(db: Session, user: User, arguments: dict) -> dict:
    """大模型工具入口：合并结构化参数与原始描述后生成草稿。"""
    raw_text = str(arguments.get("raw_text") or arguments.get("text") or "").strip()
    parsed = parse_booking_text(db, raw_text) if raw_text else {}

    hotel = match_hotel(db, str(arguments.get("hotel_name") or "")) or parsed.get("hotel")
    room_type = match_room_type(db, hotel, str(arguments.get("room_type_name") or "")) or parsed.get("room_type")

    check_in = detect_date(str(arguments.get("check_in") or "")) or parsed.get("check_in_date")
    check_out = detect_date(str(arguments.get("check_out") or "")) or parsed.get("check_out_date")

    nights = arguments.get("nights")
    try:
        nights = int(nights) if nights is not None else parsed.get("nights")
    except (TypeError, ValueError):
        nights = parsed.get("nights")
    if check_in and not check_out and nights:
        check_out = check_in + timedelta(days=nights)

    def _int(value, fallback):
        try:
            return int(value) if value is not None else fallback
        except (TypeError, ValueError):
            return fallback

    rooms = _int(arguments.get("rooms"), parsed.get("rooms"))
    guests = _int(arguments.get("guests"), parsed.get("guests"))
    special_request = str(arguments.get("special_request") or "").strip() or parsed.get("special_request") or ""

    note = ""
    if parsed.get("assumed_single_night") and not check_out:
        note = "没有识别到入住晚数，暂按 1 晚计算，如需调整请重新说明。"

    return build_draft(
        db,
        user,
        hotel=hotel,
        hotel_name=str(arguments.get("hotel_name") or ""),
        room_type=room_type,
        check_in_date=check_in,
        check_out_date=check_out,
        rooms=rooms,
        guests=guests,
        special_request=special_request,
        note=note,
    )


def confirm_draft(db: Session, user: User, draft: dict) -> Booking:
    """用户确认后真正创建订单，仍然走完整校验（含房量库存）。"""
    payload = draft.get("payload") or {}
    if not payload.get("hotel_id") or not payload.get("room_type_id"):
        raise HTTPException(status_code=400, detail="订单信息不完整，请重新发起预订")

    booking_payload = BookingIn(
        hotel_id=payload["hotel_id"],
        room_type_id=payload["room_type_id"],
        check_in_date=date_type.fromisoformat(payload["check_in_date"]),
        check_out_date=date_type.fromisoformat(payload["check_out_date"]),
        rooms=int(payload.get("rooms") or 1),
        guests=int(payload.get("guests") or 1),
        special_request=(payload.get("special_request") or "")[:200],
    )
    return create_booking(db, user, booking_payload)
