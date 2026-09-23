from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Booking(Base):
    """订单：某房型在 [check_in_date, check_out_date) 区间内预订若干间。"""

    __tablename__ = "booking"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), nullable=False, index=True)
    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_type.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id"), nullable=False, index=True)
    check_in_date: Mapped[object] = mapped_column(Date, nullable=False, index=True)
    check_out_date: Mapped[object] = mapped_column(Date, nullable=False, index=True)
    nights: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rooms: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    guests: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    contact_phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    special_request: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # pending: 待确认，confirmed: 已确认，rejected: 已拒绝，canceled: 已取消，completed: 已完成
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    remark: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("sys_user.id"), nullable=True)
    reviewed_at: Mapped[object | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=func.now())

    hotel = relationship("Hotel", back_populates="bookings")
    room_type = relationship("RoomType")
    user = relationship("User", back_populates="bookings", foreign_keys=[user_id])
