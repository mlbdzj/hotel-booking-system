from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Hotel(Base):
    """酒店（门店）。"""

    __tablename__ = "hotel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    city: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    address: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    star: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    room_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    check_in_time: Mapped[str] = mapped_column(String(5), nullable=False, default="14:00")
    check_out_time: Mapped[str] = mapped_column(String(5), nullable=False, default="12:00")
    # 1: 营业中（可预订），0: 暂停营业
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=func.now())

    room_types = relationship("RoomType", back_populates="hotel")
    bookings = relationship("Booking", back_populates="hotel")
