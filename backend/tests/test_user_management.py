"""会员删除：同步清理关联的订单与对话，且不允许删除当前登录账号。

回归背景：删除会员时若只删 sys_user，会因 booking.user_id / chat_session.user_id
存在外键引用而失败；本文件锁定「级联清理」这一行为。
"""

from sqlalchemy import select

from app.models import Booking, ChatMessage, ChatSession, User
from helpers import booking_payload


def test_admin_cannot_delete_self(client, seed, admin_headers):
    response = client.delete(f"/api/users/{seed.admin.id}", headers=admin_headers)
    assert response.status_code == 400
    assert "不能删除当前登录账号" in response.json()["detail"]


def test_admin_can_delete_member_with_related_records(client, seed, db, admin_headers, member_headers):
    # 该会员先产生一条订单，并通过助手发起一次对话（产生会话与消息）
    client.post("/api/bookings", json=booking_payload(seed.hotel, seed.king), headers=member_headers)
    client.post("/api/agent/chat", json={"message": "入住时间是几点？"}, headers=member_headers)

    session = db.scalars(select(ChatSession).where(ChatSession.user_id == seed.member.id)).first()
    assert session is not None
    session_id = session.id

    response = client.delete(f"/api/users/{seed.member.id}", headers=admin_headers)
    assert response.status_code == 200

    # 会员本体、其订单、其对话（含消息）都应被清理，不留悬挂外键
    assert db.get(User, seed.member.id) is None
    assert list(db.scalars(select(Booking).where(Booking.user_id == seed.member.id))) == []
    assert list(db.scalars(select(ChatSession).where(ChatSession.user_id == seed.member.id))) == []
    assert list(db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id))) == []
