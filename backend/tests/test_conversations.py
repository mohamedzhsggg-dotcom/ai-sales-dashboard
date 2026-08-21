"""Tests for conversations API."""

from app.models import Conversation, Message, User


class TestConversationsAPI:
    def test_create_conversation(self, db, tenant_a, client, auth_headers):
        resp = client.post(
            "/api/v1/conversations",
            json={"platform": "facebook", "subject": "Test conversation"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["platform"] == "facebook"
        assert data["status"] == "open"

    def test_list_conversations(self, db, tenant_a, client, auth_headers):
        client.post(
            "/api/v1/conversations",
            json={"platform": "instagram", "subject": "List test"},
            headers=auth_headers,
        )
        resp = client.get("/api/v1/conversations", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_get_conversation_detail(self, db, tenant_a, client, auth_headers):
        create_resp = client.post(
            "/api/v1/conversations",
            json={"platform": "facebook", "subject": "Detail test"},
            headers=auth_headers,
        )
        conv_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == conv_id

    def test_add_message(self, db, tenant_a, client, auth_headers):
        create_resp = client.post(
            "/api/v1/conversations",
            json={"platform": "facebook"},
            headers=auth_headers,
        )
        conv_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Hello from test", "direction": "outbound"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "Hello from test"
        assert data["direction"] == "outbound"

    def test_messages_appear_in_detail(self, db, tenant_a, client, auth_headers):
        create_resp = client.post(
            "/api/v1/conversations",
            json={"platform": "instagram"},
            headers=auth_headers,
        )
        conv_id = create_resp.json()["id"]

        client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Msg 1", "direction": "inbound"},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"content": "Msg 2", "direction": "outbound"},
            headers=auth_headers,
        )

        resp = client.get(f"/api/v1/conversations/{conv_id}", headers=auth_headers)
        assert resp.status_code == 200
        messages = resp.json()["messages"]
        assert len(messages) == 2

    def test_filter_by_status(self, db, tenant_a, client, auth_headers):
        client.post(
            "/api/v1/conversations",
            json={"platform": "facebook", "subject": "Open conv"},
            headers=auth_headers,
        )
        resp = client.get("/api/v1/conversations?status=open", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(c["status"] == "open" for c in items)

    def test_update_conversation_status(self, db, tenant_a, client, auth_headers):
        create_resp = client.post(
            "/api/v1/conversations",
            json={"platform": "facebook"},
            headers=auth_headers,
        )
        conv_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/conversations/{conv_id}?status=closed",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "closed"

    def test_tenant_isolation(self, db, tenant_a, client, auth_headers):
        client.post(
            "/api/v1/conversations",
            json={"platform": "facebook", "subject": "T1 conv"},
            headers=auth_headers,
        )
        resp = client.get("/api/v1/conversations", headers=auth_headers)
        items = resp.json()["items"]
        user = db.query(User).filter(User.email == "admin-a@example.com").first()
        assert all(c["tenant_id"] == user.tenant_id for c in items)

    def test_nonexistent_conversation(self, db, tenant_a, client, auth_headers):
        resp = client.get("/api/v1/conversations/99999", headers=auth_headers)
        assert resp.status_code == 404
