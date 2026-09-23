"""自然语言预订链路：口语解析、草稿不落库、确认幂等与本地引擎降级。"""

import json
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.agent.booking import build_draft, cn_to_int, parse_guests, parse_nights, parse_rooms, prepare_from_text
from app.models import Booking, ChatMessage, ChatSession
from helpers import seed_booking


@pytest.fixture
def chat_session(db, seed):
    session = ChatSession(user_id=seed.member.id, title="测试会话")
    db.add(session)
    db.commit()
    return session


def _draft_message(db, session, draft, content="（助手）这是为你准备的订单预览"):
    message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=content,
        source="local",
        tools="prepare_booking",
        action=json.dumps(draft, ensure_ascii=False),
    )
    db.add(message)
    db.commit()
    return message


def _booking_count(db) -> int:
    return db.scalar(select(func.count(Booking.id))) or 0


# ---------- 中文数字与口语解析 ----------


@pytest.mark.parametrize(
    "text, expected",
    [("两", 2), ("二", 2), ("十", 10), ("十二", 12), ("二十", 20), ("3", 3), ("10", 10)],
)
def test_cn_to_int(text, expected):
    assert cn_to_int(text) == expected


def test_cn_to_int_returns_none_for_unparsable():
    assert cn_to_int("") is None
    assert cn_to_int("很多") is None


@pytest.mark.parametrize(
    "text, expected",
    [("住两晚", 2), ("住 3 晚", 3), ("共五晚", 5), ("连住十二晚", 12), ("今晚", None)],
)
def test_parse_nights(text, expected):
    assert parse_nights(text) == expected


@pytest.mark.parametrize("text, expected", [("两间", 2), ("3 间", 3), ("要一间大床房", 1), ("没有", None)])
def test_parse_rooms(text, expected):
    assert parse_rooms(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [("2 个人", 2), ("两位客人", 2), ("3名成人", 3), ("四位", None)],
)
def test_parse_guests(text, expected):
    assert parse_guests(text) == expected


def test_draft_from_sentence_parses_all_fields(db, seed):
    """一句口语描述要能解析出酒店、房型、日期、晚数、间数、人数与特殊要求。"""
    draft = prepare_from_text(
        db, seed.member, "下周五入住两晚的杭州西湖智选假日酒店高级大床房，两间，4 个人，需要安静楼层"
    )
    payload = draft["payload"]

    assert payload["hotel_id"] == seed.hotel.id
    assert payload["room_type_id"] == seed.king.id
    assert payload["nights"] == 2
    assert payload["rooms"] == 2
    assert payload["guests"] == 4
    # 「需要」属于语气词，会在解析特殊要求时被剔除
    assert payload["special_request"] == "安静楼层"
    assert date.fromisoformat(payload["check_in_date"]) >= date.today()
    assert (
        date.fromisoformat(payload["check_out_date"]) - date.fromisoformat(payload["check_in_date"])
    ).days == 2
    assert draft["status"] == "pending"
    assert draft["problems"] == []


def test_draft_matches_hotel_short_name(db, seed):
    draft = prepare_from_text(db, seed.member, "下周三入住一晚的杭州西湖智选的双床房，2 个人")
    assert draft["payload"]["hotel_id"] == seed.hotel.id
    assert draft["payload"]["room_type_id"] == seed.twin.id


def test_draft_uses_single_night_when_not_mentioned(db, seed):
    draft = prepare_from_text(db, seed.member, "明天入住杭州西湖智选假日酒店高级大床房，2 个人")
    assert draft["payload"]["nights"] == 1
    assert draft["note"]


def test_draft_reports_missing_fields(db, seed):
    draft = prepare_from_text(db, seed.member, "帮我订个房")
    assert draft["status"] == "invalid"
    assert any("酒店" in item for item in draft["problems"])
    assert any("房型" in item for item in draft["problems"])
    assert any("日期" in item for item in draft["problems"])


def test_draft_detects_oversell(db, seed):
    seed_booking(db, user=seed.stranger, hotel=seed.hotel, room_type=seed.twin, rooms=1, days_from=7, nights=2)
    check_in = date.today() + timedelta(days=7)
    draft = build_draft(
        db,
        seed.member,
        hotel=seed.hotel,
        hotel_name=seed.hotel.name,
        room_type=seed.twin,
        check_in_date=check_in,
        check_out_date=check_in + timedelta(days=2),
        rooms=1,
        guests=2,
    )
    assert draft["status"] == "invalid"
    assert any("仅剩 0 间可订" in item for item in draft["problems"])


def test_draft_never_writes_to_database(db, seed):
    before = _booking_count(db)
    draft = prepare_from_text(db, seed.member, "下周五入住两晚的杭州西湖智选假日酒店高级大床房，2 个人")
    assert draft["status"] == "pending"
    assert _booking_count(db) == before


# ---------- 确认 / 取消草稿 ----------


def _confirm(client, session, message, headers):
    return client.post(
        "/api/agent/actions/confirm",
        json={"session_id": session.id, "message_id": message.id},
        headers=headers,
    )


def test_confirm_draft_creates_pending_booking(client, db, seed, member_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "下周五入住两晚的杭州西湖智选假日酒店高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["action"]["status"] == "confirmed"
    assert body["booking"]["status"] == "pending"
    assert body["booking"]["user_id"] == seed.member.id
    assert body["booking"]["total_amount"] == draft["payload"]["total_amount"]
    assert "订单已提交" in body["message"]["content"]

    saved = db.get(Booking, body["booking"]["id"])
    assert saved is not None
    assert saved.rooms == draft["payload"]["rooms"]


def test_confirm_draft_is_idempotent(client, db, seed, member_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "下周五入住两晚的杭州西湖智选假日酒店高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    first = _confirm(client, chat_session, message, member_headers)
    assert first.status_code == 200
    count_after_first = _booking_count(db)

    second = _confirm(client, chat_session, message, member_headers)
    assert second.status_code == 400
    assert second.json()["detail"] == "该操作已经处理过了"
    assert _booking_count(db) == count_after_first


def test_confirm_rejects_draft_with_problems(client, db, seed, member_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "帮我订个房")
    message = _draft_message(db, chat_session, draft)

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert "订单信息还不完整" in response.json()["detail"]
    assert _booking_count(db) == 0


def test_confirm_marks_draft_failed_when_inventory_changed(client, db, seed, member_headers, chat_session):
    """草稿生成后房量被抢光：确认时二次校验失败，草稿标记为 failed。"""
    draft = prepare_from_text(db, seed.member, "下周五入住两晚的杭州西湖智选假日酒店高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    payload = draft["payload"]
    check_in = date.fromisoformat(payload["check_in_date"])
    seed_booking(
        db,
        user=seed.stranger,
        hotel=seed.hotel,
        room_type=seed.king,
        rooms=3,
        days_from=(check_in - date.today()).days,
        nights=payload["nights"],
    )

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert "仅剩 0 间可订" in response.json()["detail"]

    stored = json.loads(db.get(ChatMessage, message.id).action)
    assert stored["status"] == "failed"
    assert "仅剩 0 间可订" in stored["error"]


def test_cancelled_draft_cannot_be_confirmed(client, db, seed, member_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "下周五入住两晚的杭州西湖智选假日酒店高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    cancel = client.post(
        "/api/agent/actions/cancel",
        json={"session_id": chat_session.id, "message_id": message.id},
        headers=member_headers,
    )
    assert cancel.status_code == 200
    assert cancel.json()["action"]["status"] == "canceled"

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert _booking_count(db) == 0


def test_other_user_cannot_confirm_someone_elses_draft(client, db, seed, stranger_headers, chat_session):
    draft = prepare_from_text(db, seed.member, "下周五入住两晚的杭州西湖智选假日酒店高级大床房，2 个人")
    message = _draft_message(db, chat_session, draft)

    response = _confirm(client, chat_session, message, stranger_headers)
    assert response.status_code == 404
    assert "对话不存在" in response.json()["detail"]


def test_confirm_rejects_message_without_action(client, db, seed, member_headers, chat_session):
    message = ChatMessage(
        session_id=chat_session.id, role="assistant", content="入住时间是 14:00 之后。", source="local"
    )
    db.add(message)
    db.commit()

    response = _confirm(client, chat_session, message, member_headers)
    assert response.status_code == 400
    assert "没有可确认的操作" in response.json()["detail"]


# ---------- 本地知识库引擎（降级路径） ----------


def test_local_engine_answers_from_knowledge_base(client, seed, member_headers):
    response = client.post(
        "/api/agent/chat", json={"message": "请问入住和退房时间是几点？"}, headers=member_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local"
    assert "14:00" in body["reply"]["content"]


def test_agent_status_reports_local_provider_and_tools(client, member_headers):
    response = client.get("/api/agent/status", headers=member_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "local"
    assert body["llm_enabled"] is False
    assert body["knowledge_total"] == 1
    assert len(body["tools"]) == 8
