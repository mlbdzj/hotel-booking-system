from datetime import date as date_type
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.serializers import refresh_completed_status
from app.db.session import get_db
from app.models import Booking, Hotel, RoomType, User
from app.services.booking_service import ACTIVE_STATUS

router = APIRouter(prefix="/api/stats", tags=["统计"])

# 计入订单量统计的状态：已取消、已拒绝不算
COUNTED_STATUS = ("pending", "confirmed", "completed")


@router.get("/overview")
def overview(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date_type.today()
    is_admin = current_user.role == "admin"
    scope = [] if is_admin else [Booking.user_id == current_user.id]

    # 本周：周一 ~ 周日
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    hotel_total = db.scalar(select(func.count(Hotel.id))) or 0
    room_type_total = db.scalar(select(func.count(RoomType.id))) or 0
    user_total = db.scalar(select(func.count(User.id))) or 0
    booking_total = db.scalar(select(func.count(Booking.id)).where(*scope)) or 0
    pending_total = (
        db.scalar(select(func.count(Booking.id)).where(*scope, Booking.status == "pending")) or 0
    )
    today_check_in_total = (
        db.scalar(
            select(func.count(Booking.id)).where(
                *scope, Booking.check_in_date == today, Booking.status.in_(ACTIVE_STATUS)
            )
        )
        or 0
    )
    week_total = (
        db.scalar(
            select(func.count(Booking.id)).where(
                *scope,
                Booking.check_in_date >= week_start,
                Booking.check_in_date <= week_end,
                Booking.status.in_(COUNTED_STATUS),
            )
        )
        or 0
    )

    # 今日入住率：今日在住间数 / 全部房量
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
    occupancy_rate = round(occupied_today * 100 / total_rooms) if total_rooms else 0

    # 本周订单排行：按本周入住的订单数排序（不做百分比换算）
    ranking_rows = db.execute(
        select(Hotel.id, Hotel.name, func.count(Booking.id))
        .join(
            Booking,
            (Booking.hotel_id == Hotel.id)
            & (Booking.check_in_date >= week_start)
            & (Booking.check_in_date <= week_end)
            & (Booking.status.in_(COUNTED_STATUS)),
            isouter=True,
        )
        .group_by(Hotel.id, Hotel.name)
        .order_by(func.count(Booking.id).desc(), Hotel.id.asc())
    ).all()
    hotel_ranking = [
        {"hotel_id": row[0], "hotel_name": row[1], "booking_count": row[2]} for row in ranking_rows
    ]

    recent = db.scalars(
        select(Booking)
        .where(*scope)
        .order_by(Booking.created_at.desc(), Booking.id.desc())
        .limit(6)
    ).all()
    refresh_completed_status(db, list(recent))

    from app.api.serializers import booking_to_dict

    hotel_names = dict(db.execute(select(Hotel.id, Hotel.name)).all())
    room_type_names = dict(db.execute(select(RoomType.id, RoomType.name)).all())
    user_ids = {item.user_id for item in recent}
    users = {user.id: user for user in db.scalars(select(User).where(User.id.in_(user_ids))).all()}

    return {
        "hotel_total": hotel_total,
        "room_type_total": room_type_total,
        "user_total": user_total,
        "booking_total": booking_total,
        "pending_total": pending_total,
        "today_check_in_total": today_check_in_total,
        "occupancy_rate": occupancy_rate,
        "week_total": week_total,
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "hotel_ranking": hotel_ranking,
        "recent_bookings": [
            booking_to_dict(
                item,
                hotel_names.get(item.hotel_id, ""),
                room_type_names.get(item.room_type_id, ""),
                users.get(item.user_id),
            )
            for item in recent
        ],
    }
