from fastapi.testclient import TestClient

from app.sync import ClipboardSync
from services.approval_api_service import ApprovalApiService
from services.clipboard_service import CapturedClipboard
from services.pending_queue import PendingClipQueue


def clip(payload="hello", clip_type="text"):
    return CapturedClipboard(
        payload=payload, metadata={"type": clip_type}, timestamp="T")


def make_service(cors_origins=None):
    queue = PendingClipQueue()
    sent = []
    sync = ClipboardSync(
        None, broadcast=sent.append, pending_queue=queue, echo_guard_delay=0.0)
    service = ApprovalApiService(
        queue, sync, cors_origins=cors_origins or ["http://localhost:3000"])
    return service, queue, sent


class TestListPending:
    def test_empty_queue(self):
        service, _, _ = make_service()
        client = TestClient(service.build_app())
        res = client.get("/pending")
        assert res.status_code == 200
        assert res.json() == {"items": []}

    def test_returns_the_pending_item_with_expected_fields(self):
        service, queue, _ = make_service()
        queue.add(clip("hello"))
        client = TestClient(service.build_app())

        items = client.get("/pending").json()["items"]
        assert len(items) == 1

        item = items[0]
        assert set(item.keys()) == {
            "id", "type", "timestamp", "preview", "size_bytes", "metadata"}
        assert item["type"] == "text"
        assert item["timestamp"] == "T"
        assert item["preview"] == "hello"
        assert item["size_bytes"] == 5
        assert item["metadata"] == {"type": "text"}
        assert "payload" not in item


class TestApprove:
    def test_approves_and_broadcasts(self):
        service, queue, sent = make_service()
        pending = queue.add(clip("hello"))
        client = TestClient(service.build_app())

        res = client.post(f"/pending/{pending.id}/approve")
        assert res.status_code == 200
        assert res.json() == {"status": "approved", "id": pending.id}
        assert sent == [
            {"payload": "hello", "metadata": {"type": "text"}, "timestamp": "T"}]
        assert client.get("/pending").json() == {"items": []}

    def test_unknown_id_returns_404(self):
        service, _, sent = make_service()
        client = TestClient(service.build_app())
        res = client.post("/pending/does-not-exist/approve")
        assert res.status_code == 404
        assert sent == []


class TestReject:
    def test_rejects_without_broadcasting(self):
        service, queue, sent = make_service()
        pending = queue.add(clip("hello"))
        client = TestClient(service.build_app())

        res = client.post(f"/pending/{pending.id}/reject")
        assert res.status_code == 200
        assert res.json() == {"status": "rejected", "id": pending.id}
        assert sent == []
        assert client.get("/pending").json() == {"items": []}

    def test_unknown_id_returns_404(self):
        service, _, _ = make_service()
        client = TestClient(service.build_app())
        res = client.post("/pending/does-not-exist/reject")
        assert res.status_code == 404


class TestCors:
    def test_allowed_origin_gets_the_cors_header(self):
        service, _, _ = make_service(cors_origins=["http://localhost:3000"])
        client = TestClient(service.build_app())
        res = client.get(
            "/pending", headers={"Origin": "http://localhost:3000"})
        assert res.headers.get(
            "access-control-allow-origin") == "http://localhost:3000"
