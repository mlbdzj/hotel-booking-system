"""权限隔离：接口鉴权、角色边界、数据范围与确认阶段的二次校验。"""

from helpers import auth_headers, booking_payload, seed_booking


def test_protected_endpoints_require_login(client):
    for method, path in [
        ("get", "/api/bookings"),
        ("get", "/api/bookings/my"),
        ("get", "/api/stats/overview"),
        ("get", "/api/agent/status"),
        ("get", "/api/users"),
    ]:
        response = getattr(client, method)(path)
        assert response.status_code == 401, path
        assert response.json()["detail"] == "请先登录"


def test_forged_token_is_rejected(client, seed):
    headers = {"Authorization": "Bearer forged.payload"}
    assert client.get("/api/bookings/my", headers=headers).status_code == 401
    assert client.get("/api/stats/overview", headers=headers).status_code == 401


def test_disabled_account_cannot_use_token(client, seed):
    seed.stranger.status = 0
    response = client.get("/api/bookings/my", headers=auth_headers(seed.stranger))
    assert response.status_code == 403
    assert "账号已被禁用" in response.json()["detail"]


def test_member_cannot_list_all_bookings(client, seed, member_headers):
    response = client.get("/api/bookings", headers=member_headers)
    assert response.status_code == 403
    assert "仅管理员可操作" in response.json()["detail"]


def test_member_cannot_review_booking(client, seed, member_headers):
    created = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king), headers=member_headers
    ).json()
    response = client.post(
        f"/api/bookings/{created['id']}/review", json={"action": "confirm", "remark": ""}, headers=member_headers
    )
    assert response.status_code == 403


def test_member_cannot_delete_booking(client, seed, member_headers):
    created = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king), headers=member_headers
    ).json()
    response = client.delete(f"/api/bookings/{created['id']}", headers=member_headers)
    assert response.status_code == 403


def test_member_cannot_read_others_booking(client, seed, member_headers, stranger_headers):
    other = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king, days_from=10), headers=stranger_headers
    ).json()
    response = client.get(f"/api/bookings/{other['id']}", headers=member_headers)
    assert response.status_code == 403
    assert "无权查看该订单" in response.json()["detail"]


def test_member_cannot_cancel_others_booking(client, seed, member_headers, stranger_headers):
    other = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king, days_from=10), headers=stranger_headers
    ).json()
    response = client.post(f"/api/bookings/{other['id']}/cancel", headers=member_headers)
    assert response.status_code == 403


def test_member_can_cancel_own_booking(client, seed, member_headers):
    created = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king), headers=member_headers
    ).json()
    response = client.post(f"/api/bookings/{created['id']}/cancel", headers=member_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "canceled"


def test_cancel_is_rejected_for_already_canceled_booking(client, seed, member_headers):
    created = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king), headers=member_headers
    ).json()
    client.post(f"/api/bookings/{created['id']}/cancel", headers=member_headers)
    again = client.post(f"/api/bookings/{created['id']}/cancel", headers=member_headers)
    assert again.status_code == 400
    assert "无法取消" in again.json()["detail"]


def test_member_cannot_manage_users_and_knowledge(client, seed, member_headers):
    assert client.get("/api/users", headers=member_headers).status_code == 403
    assert (
        client.post(
            "/api/knowledge",
            json={"category": "测试", "question": "问题", "answer": "答案", "keywords": ""},
            headers=member_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/room-types",
            json={
                "hotel_id": seed.hotel.id,
                "name": "越权房型",
                "code": "X1",
                "bed_type": "大床",
                "price": 100,
                "capacity": 2,
                "quantity": 1,
                "status": "open",
            },
            headers=member_headers,
        ).status_code
        == 403
    )


def test_admin_sees_all_bookings_and_member_sees_own(client, seed, admin_headers, member_headers, stranger_headers):
    client.post("/api/bookings", json=booking_payload(seed.hotel, seed.king, days_from=7), headers=member_headers)
    client.post("/api/bookings", json=booking_payload(seed.hotel, seed.king, days_from=10), headers=stranger_headers)
    client.post("/api/bookings", json=booking_payload(seed.hotel, seed.twin, days_from=12), headers=stranger_headers)

    admin_view = client.get("/api/bookings", headers=admin_headers).json()
    member_view = client.get("/api/bookings/my", headers=member_headers).json()

    assert admin_view["total"] == 3
    assert member_view["total"] == 1
    assert all(item["username"] == "student" for item in member_view["items"])


def test_admin_can_filter_bookings_by_status(client, seed, admin_headers, member_headers):
    pending = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king, days_from=7), headers=member_headers
    ).json()
    confirmed = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.twin, days_from=20), headers=member_headers
    ).json()
    client.post(
        f"/api/bookings/{confirmed['id']}/review", json={"action": "confirm", "remark": ""}, headers=admin_headers
    )

    only_pending = client.get("/api/bookings", params={"status": "pending"}, headers=admin_headers).json()
    assert [item["id"] for item in only_pending["items"]] == [pending["id"]]

    only_confirmed = client.get("/api/bookings", params={"status": "confirmed"}, headers=admin_headers).json()
    assert [item["id"] for item in only_confirmed["items"]] == [confirmed["id"]]


def test_admin_review_confirms_booking(client, seed, admin_headers, member_headers):
    created = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king), headers=member_headers
    ).json()
    response = client.post(
        f"/api/bookings/{created['id']}/review",
        json={"action": "confirm", "remark": "已确认，房间已保留"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "confirmed"
    assert body["remark"] == "已确认，房间已保留"
    assert body["reviewer_name"] == seed.admin.name
    assert body["reviewed_at"] is not None


def test_admin_review_rejects_booking(client, seed, admin_headers, member_headers):
    created = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king), headers=member_headers
    ).json()
    response = client.post(
        f"/api/bookings/{created['id']}/review",
        json={"action": "reject", "remark": "该日期房源紧张"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_review_twice_is_rejected(client, seed, admin_headers, member_headers):
    created = client.post(
        "/api/bookings", json=booking_payload(seed.hotel, seed.king), headers=member_headers
    ).json()
    payload = {"action": "confirm", "remark": ""}
    assert client.post(f"/api/bookings/{created['id']}/review", json=payload, headers=admin_headers).status_code == 200
    again = client.post(f"/api/bookings/{created['id']}/review", json=payload, headers=admin_headers)
    assert again.status_code == 400
    assert "已处理" in again.json()["detail"]


def test_review_revalidates_inventory(client, seed, db, admin_headers):
    """确认阶段二次校验：两条待确认订单抢同一间房，谁都无法确认，释放一条后才能确认。"""
    first = seed_booking(db, user=seed.member, hotel=seed.hotel, room_type=seed.twin, rooms=1, days_from=7, nights=2)
    second = seed_booking(db, user=seed.stranger, hotel=seed.hotel, room_type=seed.twin, rooms=1, days_from=7, nights=2)

    # 双床房只有 1 间，两条在途订单已经互相占满，确认时排除自身后剩余仍是 0
    blocked = client.post(
        f"/api/bookings/{first.id}/review", json={"action": "confirm", "remark": ""}, headers=admin_headers
    )
    assert blocked.status_code == 400
    assert "仅剩 0 间" in blocked.json()["detail"]

    # 释放另一条占位订单后，剩余房量恢复，确认即可通过
    assert client.post(f"/api/bookings/{second.id}/cancel", headers=admin_headers).status_code == 200
    ok = client.post(
        f"/api/bookings/{first.id}/review", json={"action": "confirm", "remark": ""}, headers=admin_headers
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "confirmed"


def test_member_stats_are_scoped_to_own_bookings(client, seed, admin_headers, member_headers, stranger_headers):
    client.post("/api/bookings", json=booking_payload(seed.hotel, seed.king, days_from=7), headers=member_headers)
    client.post("/api/bookings", json=booking_payload(seed.hotel, seed.king, days_from=10), headers=stranger_headers)
    client.post("/api/bookings", json=booking_payload(seed.hotel, seed.twin, days_from=12), headers=stranger_headers)

    admin_view = client.get("/api/stats/overview", headers=admin_headers).json()
    member_view = client.get("/api/stats/overview", headers=member_headers).json()

    assert admin_view["booking_total"] == 3
    assert member_view["booking_total"] == 1
    assert len(member_view["recent_bookings"]) == 1
    # 门店与房型规模属于公共信息，会员同样可见
    assert member_view["hotel_total"] == admin_view["hotel_total"]


def test_agent_tools_follow_user_role(client, seed, admin_headers, member_headers):
    """普通会员问「待确认订单」只能拿到权限说明，管理员能拿到列表。"""
    member_reply = client.post(
        "/api/agent/chat", json={"message": "有哪些待确认订单？"}, headers=member_headers
    ).json()
    admin_reply = client.post(
        "/api/agent/chat", json={"message": "有哪些待确认订单？"}, headers=admin_headers
    ).json()

    assert member_reply["reply"]["content"] != admin_reply["reply"]["content"]
    assert "管理员" in member_reply["reply"]["content"]
