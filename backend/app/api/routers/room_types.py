from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.api.serializers import room_type_to_dict
from app.db.session import get_db
from app.models import Hotel, RoomType, User
from app.schemas.common import Message, Page
from app.schemas.room_type import RoomTypeIn, RoomTypeOut

router = APIRouter(prefix="/api/room-types", tags=["房型管理"])


def _hotel_name_map(db: Session, hotel_ids: list[int]) -> dict[int, str]:
    if not hotel_ids:
        return {}
    rows = db.execute(select(Hotel.id, Hotel.name).where(Hotel.id.in_(hotel_ids))).all()
    return {row[0]: row[1] for row in rows}


@router.get("", response_model=Page[RoomTypeOut])
def list_room_types(
    keyword: str = Query(default=""),
    hotel_id: int | None = Query(default=None),
    status_filter: str = Query(default="", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = []
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(
            RoomType.name.like(like) | RoomType.code.like(like) | RoomType.bed_type.like(like)
        )
    if hotel_id:
        conditions.append(RoomType.hotel_id == hotel_id)
    if status_filter:
        conditions.append(RoomType.status == status_filter)

    total = db.scalar(select(func.count(RoomType.id)).where(*conditions)) or 0
    room_types = db.scalars(
        select(RoomType)
        .where(*conditions)
        .order_by(RoomType.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    names = _hotel_name_map(db, [item.hotel_id for item in room_types])
    return {
        "total": total,
        "items": [room_type_to_dict(item, names.get(item.hotel_id, "")) for item in room_types],
    }


@router.get("/all", response_model=list[RoomTypeOut])
def list_all_room_types(
    hotel_id: int | None = Query(default=None),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conditions = []
    if hotel_id:
        conditions.append(RoomType.hotel_id == hotel_id)
    room_types = db.scalars(
        select(RoomType).where(*conditions).order_by(RoomType.price.asc())
    ).all()
    names = _hotel_name_map(db, [item.hotel_id for item in room_types])
    return [room_type_to_dict(item, names.get(item.hotel_id, "")) for item in room_types]


@router.post("", response_model=RoomTypeOut, status_code=status.HTTP_201_CREATED)
def create_room_type(
    payload: RoomTypeIn, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    hotel = db.get(Hotel, payload.hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所属酒店不存在")
    if payload.code:
        exists = db.scalar(select(RoomType).where(RoomType.code == payload.code))
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房型编号已存在")
    room_type = RoomType(**payload.model_dump())
    db.add(room_type)
    db.commit()
    db.refresh(room_type)
    return room_type_to_dict(room_type, hotel.name)


@router.put("/{room_type_id}", response_model=RoomTypeOut)
def update_room_type(
    room_type_id: int,
    payload: RoomTypeIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    room_type = db.get(RoomType, room_type_id)
    if room_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房型不存在")
    hotel = db.get(Hotel, payload.hotel_id)
    if hotel is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所属酒店不存在")
    if payload.code:
        exists = db.scalar(
            select(RoomType).where(RoomType.code == payload.code, RoomType.id != room_type_id)
        )
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房型编号已存在")
    for field, value in payload.model_dump().items():
        setattr(room_type, field, value)
    db.commit()
    db.refresh(room_type)
    return room_type_to_dict(room_type, hotel.name)


@router.delete("/{room_type_id}", response_model=Message)
def delete_room_type(
    room_type_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    room_type = db.get(RoomType, room_type_id)
    if room_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房型不存在")
    from app.models import Booking

    booking_count = db.scalar(select(func.count(Booking.id)).where(Booking.room_type_id == room_type_id))
    if booking_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该房型已有订单记录，无法删除")
    db.delete(room_type)
    db.commit()
    return Message(message="删除成功")
