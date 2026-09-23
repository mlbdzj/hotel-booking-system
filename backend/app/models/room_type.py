from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RoomType(Base):
    """房型：属于某家酒店，带价格、可住人数与房量（库存）。"""

    __tablename__ = "room_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hotel_id: Mapped[int] = mapped_column(ForeignKey("hotel.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    bed_type: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    # 可住人数（每间）
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # 房量，也就是该房型的库存间数
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # open: 可预订，maintenance: 维护中，closed: 停售
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[object] = mapped_column(DateTime, nullable=False, server_default=func.now())

    hotel = relationship("Hotel", back_populates="room_types")
