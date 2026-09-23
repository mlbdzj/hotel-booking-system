"""客服助手可调用的工具集合：所有查询都按当前登录用户的权限范围返回数据。"""

import re
from datetime import date as date_type
from datetime import timedelta
from typing import Any, Callable, NamedTuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.knowledge import search_knowledge
from app.api.serializers import BOOKING_STATUS_TEXT, ROOM_TYPE_STATUS_TEXT
from app.db.session import SessionLocal
from app.models import Booking, Hotel, RoomType, User
from app.services.booking_service import ACTIVE_STATUS, remaining_rooms

BOOKING_RULES_TEXT = (
    "预订规则：\n"
    "1. 入住日期不能早于今天，退房日期必须晚于入住日期，最少入住 1 晚；\n"
    "2. 入住时间通常为 14:00 之后，退房时间为 12:00 之前，具体以酒店说明为准；\n"
    "3. 下单需选择房型与间数，间数不能超过该房型在入住日期内的剩余房量；\n"
    "4. 入住人数不能超过「房型可住人数 × 间数」，超员建议加订房间；\n"
    "5. 房费 = 房型单价 × 晚数 × 间数，下单时会自动计算总价；\n"
    "6. 提交后订单状态为「待确认」，酒店确认后预订生效；\n"
    "7. 待确认、已确认的订单可以取消；已拒绝、已取消、已完成的订单不可再操作。"
)

class _ToolArgs(BaseModel):
    """工具入参基类：模型多传的字段直接忽略，不因为无关字段让整次调用失败。"""

    model_config = ConfigDict(extra="ignore")


class SearchKnowledgeArgs(_ToolArgs):
    query: str = Field(description="检索关键词")


class ListHotelsArgs(_ToolArgs):
    keyword: str = Field(default="", description="按名称或地址过滤，可不填")
    city: str = Field(default="", description="按城市过滤，可不填")


class CheckRoomAvailabilityArgs(_ToolArgs):
    hotel_name: str = Field(description="酒店名称")
    check_in: str = Field(default="", description="入住日期，支持 2026-09-23 / 明天 / 下周五")
    check_out: str = Field(default="", description="退房日期，可不填（默认入住后 1 晚）")


class ListMyBookingsArgs(_ToolArgs):
    status: str = Field(
        default="",
        description="可选过滤：pending 待确认、confirmed 已确认、rejected 已拒绝、canceled 已取消、completed 已完成",
    )


# 无入参工具：list_pending_bookings / system_statistics / booking_rules
class NoToolArgs(_ToolArgs):
    pass


class PrepareBookingArgs(_ToolArgs):
    raw_text: str = Field(
        validation_alias=AliasChoices("raw_text", "text"),
        description="用户的原始描述，用于补齐未结构化提供的信息",
    )
    hotel_name: str = Field(default="", description="酒店名称")
    room_type_name: str = Field(default="", description="房型名称，例如「大床房」「双床房」")
    check_in: str = Field(default="", description="入住日期，支持 2026-09-23 / 明天 / 下周五")
    check_out: str = Field(default="", description="退房日期，可不填")
    nights: int | None = Field(default=None, description="入住晚数，缺省按 1 晚")
    rooms: int | None = Field(default=None, description="预订间数，缺省 1 间")
    guests: int | None = Field(default=None, description="入住人数")
    special_request: str = Field(default="", description="特殊要求，例如「安静楼层」「加床」")


def resolve_date(value: str | None) -> date_type:
    """把「今天/明天/下周五/9月24号」等写法解析成日期，解析不到时返回今天。"""
    return detect_date(value) or date_type.today()


def detect_date(value: str | None) -> date_type | None:
    text = (value or "").strip()
    if not text:
        return None
    today = date_type.today()
    relative = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2, "大后天": 3}
    for word, offset in relative.items():
        if word in text:
            return today + timedelta(days=offset)

    match = re.search(r"(\d{4})\s*[-/年]\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})", text)
    if match:
        return date_type(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = re.search(r"(\d{1,2})\s*[-/月]\s*(\d{1,2})[日号]?", text)
    if match:
        return date_type(today.year, int(match.group(1)), int(match.group(2)))

    weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    match = re.search(r"(下周|下星期|本周|这周|周|星期)([一二三四五六日天])", text)
    if match:
        target = weekday_map[match.group(2)]
        if match.group(1).startswith("下"):
            # 下周X：先跳到下周一，再加上星期偏移
            next_monday = today + timedelta(days=7 - today.weekday())
            return next_monday + timedelta(days=target)
        offset = (target - today.weekday()) % 7
        return today + timedelta(days=offset or 7)

    try:
        return date_type.fromisoformat(text)
    except ValueError:
        return None


def hotel_aliases(hotel: Hotel) -> list[str]:
    name = (hotel.name or "").replace(" ", "")
    if not name:
        return []
    short = name
    for suffix in ("假日酒店", "大酒店", "酒店", "宾馆", "公寓"):
        if short.endswith(suffix) and len(short) > len(suffix):
            short = short[: -len(suffix)]
            break
    aliases = {name, short}
    return [item for item in aliases if len(item) >= 2]


def match_hotel(db: Session, text: str) -> Hotel | None:
    normalized = (text or "").replace(" ", "")
    if not normalized:
        return None
    matched: Hotel | None = None
    matched_length = 0
    for hotel in db.scalars(select(Hotel)).all():
        for alias in hotel_aliases(hotel):
            if alias in normalized and len(alias) > matched_length:
                matched = hotel
                matched_length = len(alias)
    return matched


def _hotel_brief(db: Session, hotel: Hotel) -> dict:
    room_type_count = db.scalar(select(func.count(RoomType.id)).where(RoomType.hotel_id == hotel.id)) or 0
    return {
        "name": hotel.name,
        "city": hotel.city,
        "address": hotel.address,
        "star": hotel.star,
        "room_count": hotel.room_count,
        "check_in_time": hotel.check_in_time,
        "check_out_time": hotel.check_out_time,
        "status": "营业中" if hotel.status == 1 else "暂停营业",
        "room_type_count": room_type_count,
        "description": hotel.description,
    }


def _booking_brief(booking: Booking, hotel_name: str = "", room_type_name: str = "") -> dict:
    return {
        "id": booking.id,
        "hotel_name": hotel_name,
        "room_type_name": room_type_name,
        "check_in_date": booking.check_in_date.isoformat(),
        "check_out_date": booking.check_out_date.isoformat(),
        "nights": booking.nights,
        "rooms": booking.rooms,
        "guests": booking.guests,
        "total_amount": float(booking.total_amount or 0),
        "special_request": booking.special_request,
        "status": BOOKING_STATUS_TEXT.get(booking.status, booking.status),
        "remark": booking.remark,
    }


def _booking_names(db: Session, booking: Booking) -> tuple[str, str]:
    hotel = db.get(Hotel, booking.hotel_id)
    room_type = db.get(RoomType, booking.room_type_id)
    return (hotel.name if hotel else ""), (room_type.name if room_type else "")


def search_knowledge_tool(db: Session, query: str) -> dict:
    results = search_knowledge(db, query, limit=3)
    if not results:
        results = search_knowledge(db, query, limit=3, min_score=0.15)
    return {
        "results": [
            {"category": item["category"], "question": item["question"], "answer": item["answer"]}
            for item in results
        ]
    }


def list_hotels_tool(db: Session, keyword: str = "", city: str = "") -> dict:
    hotels = db.scalars(select(Hotel).order_by(Hotel.id.asc())).all()
    if keyword:
        text = keyword.strip()
        hotels = [item for item in hotels if text in item.name or text in item.address]
    if city:
        hotels = [item for item in hotels if city in item.city]
    return {"hotels": [_hotel_brief(db, item) for item in hotels]}


def check_room_availability_tool(
    db: Session, hotel_name: str, check_in: str = "", check_out: str = ""
) -> dict:
    hotel = match_hotel(db, hotel_name)
    if hotel is None:
        return {
            "error": "没有匹配到酒店，请确认名称",
            "available_hotels": [item.name for item in db.scalars(select(Hotel)).all()],
        }

    start = resolve_date(check_in)
    end = detect_date(check_out) if check_out else None
    if end is None or end <= start:
        end = start + timedelta(days=1)

    room_types = db.scalars(
        select(RoomType).where(RoomType.hotel_id == hotel.id).order_by(RoomType.price.asc())
    ).all()
    return {
        "hotel_name": hotel.name,
        "city": hotel.city,
        "address": hotel.address,
        "check_in": start.isoformat(),
        "check_out": end.isoformat(),
        "nights": (end - start).days,
        "check_in_time": hotel.check_in_time,
        "check_out_time": hotel.check_out_time,
        "status": "营业中" if hotel.status == 1 else "暂停营业",
        "room_types": [
            {
                "name": item.name,
                "bed_type": item.bed_type,
                "price": float(item.price or 0),
                "capacity": item.capacity,
                "quantity": item.quantity,
                "remaining": remaining_rooms(db, item, start, end),
                "status": ROOM_TYPE_STATUS_TEXT.get(item.status, item.status),
            }
            for item in room_types
        ],
    }


def list_my_bookings_tool(db: Session, user: User, status_text: str = "") -> dict:
    conditions = [Booking.user_id == user.id]
    if status_text:
        matched = [key for key, value in BOOKING_STATUS_TEXT.items() if value == status_text]
        matched += [key for key in BOOKING_STATUS_TEXT if key == status_text]
        conditions.append(Booking.status.in_(matched or [status_text]))

    bookings = db.scalars(
        select(Booking)
        .where(*conditions)
        .order_by(Booking.check_in_date.desc(), Booking.id.desc())
        .limit(10)
    ).all()
    items = []
    for booking in bookings:
        hotel_name, room_type_name = _booking_names(db, booking)
        items.append(_booking_brief(booking, hotel_name, room_type_name))
    return {"total": len(items), "bookings": items}


def list_pending_bookings_tool(db: Session, user: User) -> dict:
    if user.role != "admin":
        return {"error": "只有酒店管理员可以查看全部待确认订单，普通用户只能查看自己的订单"}

    bookings = db.scalars(
        select(Booking)
        .where(Booking.status == "pending")
        .order_by(Booking.check_in_date.asc(), Booking.id.asc())
        .limit(20)
    ).all()
    items = []
    for booking in bookings:
        hotel_name, room_type_name = _booking_names(db, booking)
        brief = _booking_brief(booking, hotel_name, room_type_name)
        applicant = db.get(User, booking.user_id)
        brief["guest"] = (applicant.name or applicant.username) if applicant else ""
        items.append(brief)
    return {"total": len(items), "bookings": items}


def system_statistics_tool(db: Session, user: User) -> dict:
    is_admin = user.role == "admin"
    scope = [] if is_admin else [Booking.user_id == user.id]
    today = date_type.today()
    total_rooms = db.scalar(select(func.coalesce(func.sum(RoomType.quantity), 0))) or 0
    occupied_today = (
        db.scalar(
            select(func.coalesce(func.sum(Booking.rooms), 0)).where(
                Booking.status.in_(ACTIVE_STATUS),
                Booking.check_in_date <= today,
                Booking.check_out_date > today,
            )
        )
        or 0
    )
    return {
        "hotel_total": db.scalar(select(func.count(Hotel.id))) or 0,
        "room_type_total": db.scalar(select(func.count(RoomType.id))) or 0,
        "user_total": (db.scalar(select(func.count(User.id))) or 0) if is_admin else "无权限查看",
        "booking_total": db.scalar(select(func.count(Booking.id)).where(*scope)) or 0,
        "pending_total": db.scalar(
            select(func.count(Booking.id)).where(*scope, Booking.status == "pending")
        )
        or 0,
        "occupancy_rate": round(occupied_today * 100 / total_rooms) if total_rooms else 0,
        "scope": "全部门店数据" if is_admin else "仅统计当前登录用户的订单",
    }


def booking_rules_tool() -> dict:
    return {"rules": BOOKING_RULES_TEXT}


# ===== 工具注册表 =====
# 名称 / 描述 / 入参模型 / 处理器集中在这里，新增一个工具要同时改三处：
# 入参模型、适配器、注册表条目。发给模型的 JSON Schema 由入参模型自动生成。


class ToolSpec(NamedTuple):
    description: str
    args: type[_ToolArgs]
    handler: Callable[[Session, User, Any], dict]


def _handle_search_knowledge(db: Session, user: User, args: SearchKnowledgeArgs) -> dict:
    return search_knowledge_tool(db, args.query)


def _handle_list_hotels(db: Session, user: User, args: ListHotelsArgs) -> dict:
    return list_hotels_tool(db, args.keyword, args.city)


def _handle_check_room_availability(db: Session, user: User, args: CheckRoomAvailabilityArgs) -> dict:
    return check_room_availability_tool(db, args.hotel_name, args.check_in, args.check_out)


def _handle_list_my_bookings(db: Session, user: User, args: ListMyBookingsArgs) -> dict:
    return list_my_bookings_tool(db, user, args.status)


def _handle_list_pending_bookings(db: Session, user: User, args: NoToolArgs) -> dict:
    return list_pending_bookings_tool(db, user)


def _handle_system_statistics(db: Session, user: User, args: NoToolArgs) -> dict:
    return system_statistics_tool(db, user)


def _handle_booking_rules(db: Session, user: User, args: NoToolArgs) -> dict:
    return booking_rules_tool()


def _handle_prepare_booking(db: Session, user: User, args: PrepareBookingArgs) -> dict:
    # 延迟导入：booking.py 反向依赖本模块的 detect_date / match_hotel
    from app.agent.booking import prepare_from_arguments

    return prepare_from_arguments(db, user, args.model_dump())


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "search_knowledge": ToolSpec(
        "检索酒店客服知识库（入住退房、押金发票、取消政策、会员等问题）",
        SearchKnowledgeArgs,
        _handle_search_knowledge,
    ),
    "list_hotels": ToolSpec(
        "查询酒店列表，含城市、地址、星级、房型数量与营业状态",
        ListHotelsArgs,
        _handle_list_hotels,
    ),
    "check_room_availability": ToolSpec(
        "查询某酒店在指定入住/退房日期内的房型、价格与剩余房量，用于判断还能不能订",
        CheckRoomAvailabilityArgs,
        _handle_check_room_availability,
    ),
    "list_my_bookings": ToolSpec(
        "查询当前登录用户自己的订单与状态",
        ListMyBookingsArgs,
        _handle_list_my_bookings,
    ),
    "list_pending_bookings": ToolSpec(
        "查询待确认订单列表，仅管理员可用",
        NoToolArgs,
        _handle_list_pending_bookings,
    ),
    "system_statistics": ToolSpec(
        "查询经营统计：酒店数、房型数、订单数、待确认数、今日入住与入住率",
        NoToolArgs,
        _handle_system_statistics,
    ),
    "booking_rules": ToolSpec(
        "获取酒店预订规则（入住退房时间、房量、人数、取消政策）",
        NoToolArgs,
        _handle_booking_rules,
    ),
    "prepare_booking": ToolSpec(
        "根据用户需求生成订单预览卡片。注意：这不会真正下单，"
        "系统会把预览展示成卡片，用户点击「确认下单」后才会创建订单；"
        "缺少信息或房量不足时会在 problems 中说明。",
        PrepareBookingArgs,
        _handle_prepare_booking,
    ),
}


def _strip_titles(node: Any) -> Any:
    """去掉 Pydantic 自动补的 title，只保留 type / description / default 这些对模型有用的字段。"""
    if isinstance(node, dict):
        return {key: _strip_titles(value) for key, value in node.items() if key != "title"}
    if isinstance(node, list):
        return [_strip_titles(item) for item in node]
    return node


def _tool_schema(name: str, spec: ToolSpec) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": spec.description,
            "parameters": _strip_titles(spec.args.model_json_schema()),
        },
    }


TOOL_SCHEMAS = [_tool_schema(name, spec) for name, spec in TOOL_REGISTRY.items()]
TOOL_NAMES = list(TOOL_REGISTRY)


def _format_validation_error(error: ValidationError) -> str:
    parts = []
    for item in error.errors()[:4]:
        location = ".".join(str(part) for part in item.get("loc") or ()) or "参数"
        parts.append(f"{location}: {item.get('msg', '不合法')}")
    return "；".join(parts) or "参数不合法"


def execute_tool(name: str, arguments: dict, db: Session, user: User) -> dict:
    """校验模型给的参数后执行工具。

    参数不合契约时把原因作为工具结果回给模型（而不是抛异常），模型可以据此重新调用。
    """
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        return {"error": f"未知工具：{name}"}

    try:
        args = spec.args.model_validate(arguments or {})
    except ValidationError as error:
        return {"error": f"工具 {name} 的参数不合法：{_format_validation_error(error)}"}

    return spec.handler(db, user, args)
