import base64
import json

from app.sync import ClipboardSync
from core.wire import encode_clipboard_message
from services.clipboard_service import CapturedClipboard
from services.clipboard_store import LOCAL, REMOTE
from services.pending_queue import PendingClipQueue


class FakeStore:
    def __init__(self):
        self.saved = []

    def save(self, captured, *, origin=LOCAL):
        self.saved.append((origin, captured))


class FakeWriter:
    def __init__(self, result=True):
        self.calls = []
        self._result = result

    def __call__(self, payload, metadata):
        self.calls.append((payload, metadata))
        return self._result


def make_sync(store=None, broadcasts=None, writer=None, now=lambda: "NOW"):
    return ClipboardSync(
        store if store is not None else FakeStore(),
        broadcast=broadcasts.append if broadcasts is not None else None,
        clipboard_writer=writer or FakeWriter(),
        echo_guard_delay=0.0,
        now=now,
    )


def clip(payload, clip_type="text", timestamp="T"):
    return CapturedClipboard(
        payload=payload, metadata={"type": clip_type}, timestamp=timestamp)


def message(payload=b"hello", clip_type="text", timestamp="T"):
    return json.loads(encode_clipboard_message(
        payload=payload, metadata={"type": clip_type}, timestamp=timestamp))


class TestLocalCapture:
    def test_stores_and_broadcasts(self):
        store, sent = FakeStore(), []
        captured = clip("hello")
        make_sync(store, sent).on_local_capture(captured)

        assert store.saved == [(LOCAL, captured)]
        assert sent == [{"payload": "hello",
                         "metadata": {"type": "text"}, "timestamp": "T"}]

    def test_identical_clip_twice_is_suppressed(self):
        store, sent = FakeStore(), []
        sync = make_sync(store, sent)
        sync.on_local_capture(clip("hello"))
        sync.on_local_capture(clip("hello"))
        assert len(store.saved) == 1
        assert len(sent) == 1

    def test_distinct_clips_both_go_through(self):
        store, sent = FakeStore(), []
        sync = make_sync(store, sent)
        sync.on_local_capture(clip("one"))
        sync.on_local_capture(clip("two"))
        assert len(store.saved) == 2
        assert len(sent) == 2

    def test_broadcast_carries_the_full_original_payload(self):
        # Even for a clip the store will offload to disk, the wire gets the
        # whole thing.
        sent = []
        big = b"x" * (2 * 1024 * 1024)
        make_sync(FakeStore(), sent).on_local_capture(clip(big, "file"))
        assert sent[0]["payload"] == big

    def test_broadcast_still_fires_when_persistence_fails(self):
        # Redis being down must not stop peer sync. ClipboardStore swallows its
        # own errors, so on_local_capture never sees them.
        class FailingStore:
            def __init__(self):
                self.attempts = 0

            def save(self, captured, *, origin=LOCAL):
                self.attempts += 1  # swallows internally, like the real store

        store, sent = FailingStore(), []
        ClipboardSync(store, broadcast=sent.append, clipboard_writer=FakeWriter(),
                      echo_guard_delay=0.0).on_local_capture(clip("hello"))

        assert store.attempts == 1
        assert len(sent) == 1

    def test_works_without_a_broadcaster(self):
        store = FakeStore()
        ClipboardSync(store, broadcast=None, clipboard_writer=FakeWriter(),
                      echo_guard_delay=0.0).on_local_capture(clip("hello"))
        assert len(store.saved) == 1

    def test_works_without_a_store(self):
        sent = []
        ClipboardSync(None, broadcast=sent.append, clipboard_writer=FakeWriter(),
                      echo_guard_delay=0.0).on_local_capture(clip("hello"))
        assert len(sent) == 1


class TestApprovalGating:
    def _sync(self, store=None, sent=None, queue=None):
        return ClipboardSync(
            store if store is not None else FakeStore(),
            broadcast=sent.append if sent is not None else None,
            clipboard_writer=FakeWriter(),
            echo_guard_delay=0.0,
            pending_queue=queue if queue is not None else PendingClipQueue(),
        )

    def test_capture_goes_to_queue_not_broadcast(self):
        queue, sent = PendingClipQueue(), []
        self._sync(sent=sent, queue=queue).on_local_capture(clip("hello"))
        assert sent == []
        assert len(queue.list_pending()) == 1

    def test_store_still_saves_immediately_in_approval_mode(self):
        store = FakeStore()
        self._sync(store=store).on_local_capture(clip("hello"))
        assert len(store.saved) == 1
        assert store.saved[0][0] == LOCAL

    def test_multiple_captures_all_remain_pending(self):
        queue = PendingClipQueue()
        sync = self._sync(queue=queue)
        sync.on_local_capture(clip("one"))
        sync.on_local_capture(clip("two"))
        sync.on_local_capture(clip("three"))
        pending = queue.list_pending()
        assert len(pending) == 3
        assert len({p.id for p in pending}) == 3

    def test_approve_broadcasts_the_pending_item_with_original_payload(self):
        queue, sent = PendingClipQueue(), []
        sync = self._sync(sent=sent, queue=queue)
        sync.on_local_capture(clip("hello"))
        pending_id = queue.list_pending()[0].id

        assert sync.approve(pending_id) is True
        assert sent == [{"payload": "hello",
                         "metadata": {"type": "text"}, "timestamp": "T"}]
        assert queue.list_pending() == []

    def test_approve_unknown_id_returns_false_and_does_not_broadcast(self):
        sent = []
        sync = self._sync(sent=sent)
        assert sync.approve("does-not-exist") is False
        assert sent == []

    def test_reject_removes_without_ever_broadcasting(self):
        queue, sent = PendingClipQueue(), []
        sync = self._sync(sent=sent, queue=queue)
        sync.on_local_capture(clip("hello"))
        pending_id = queue.list_pending()[0].id

        assert sync.reject(pending_id) is True
        assert sent == []
        assert queue.list_pending() == []

    def test_reject_unknown_id_returns_false(self):
        sync = self._sync()
        assert sync.reject("does-not-exist") is False

    def test_approve_and_reject_are_no_ops_without_a_pending_queue(self):
        sync = make_sync()
        assert sync.approve("anything") is False
        assert sync.reject("anything") is False


class TestRemoteMessage:
    def test_writes_decoded_bytes_to_the_clipboard(self):
        writer = FakeWriter()
        make_sync(writer=writer).on_remote_message(message(b"hello"))
        assert writer.calls == [(b"hello", {"type": "text"})]

    def test_stores_with_remote_origin(self):
        store = FakeStore()
        make_sync(store).on_remote_message(message(b"hello"))
        origin, captured = store.saved[0]
        assert origin == REMOTE
        assert captured.payload == b"hello"
        assert captured.timestamp == "T"

    def test_missing_timestamp_falls_back_to_now(self):
        store = FakeStore()
        make_sync(store, now=lambda: "GENERATED").on_remote_message(
            {"payload": base64.b64encode(b"hi").decode(), "metadata": {"type": "text"}})
        assert store.saved[0][1].timestamp == "GENERATED"

    def test_failed_clipboard_write_stores_nothing(self):
        store = FakeStore()
        make_sync(store, writer=FakeWriter(result=False)).on_remote_message(
            message(b"hello"))
        assert store.saved == []

    def test_malformed_message_is_swallowed(self):
        store = FakeStore()
        sync = make_sync(store)
        sync.on_remote_message({"payload": "!!! not base64 !!!"})
        assert store.saved == []

    def test_guard_is_released_after_a_failed_write(self):
        sync = make_sync(writer=FakeWriter(result=False))
        sync.on_remote_message(message(b"hello"))
        assert sync._setting_clipboard is False

    def test_guard_is_released_after_an_exception(self):
        def explode(payload, metadata):
            raise RuntimeError("clipboard is busy")

        sync = make_sync(writer=explode)
        sync.on_remote_message(message(b"hello"))
        assert sync._setting_clipboard is False


class TestEchoSuppression:
    def test_clip_written_by_a_peer_is_not_rebroadcast(self):
        store, sent = FakeStore(), []
        sync = make_sync(store, sent)

        sync.on_remote_message(message(b"hello"))
        # The poll loop now sees the clipboard the peer just wrote.
        sync.on_local_capture(clip(b"hello"))

        assert sent == []
        assert [origin for origin, _ in store.saved] == [REMOTE]

    def test_a_genuinely_new_local_clip_after_a_remote_one_is_broadcast(self):
        sent = []
        sync = make_sync(FakeStore(), sent)
        sync.on_remote_message(message(b"hello"))
        sync.on_local_capture(clip(b"something else"))
        assert len(sent) == 1

    def test_capture_during_an_in_flight_write_is_ignored(self):
        store, sent = FakeStore(), []
        sync = make_sync(store, sent)
        sync._setting_clipboard = True
        sync.on_local_capture(clip("hello"))
        assert store.saved == []
        assert sent == []
