import threading

from services.clipboard_service import CapturedClipboard
from services.pending_queue import PendingClipQueue


def clip(payload="hello", clip_type="text"):
    return CapturedClipboard(
        payload=payload, metadata={"type": clip_type}, timestamp="T")


class TestAdd:
    def test_returns_unique_ids_across_calls(self):
        queue = PendingClipQueue()
        a = queue.add(clip("one"))
        b = queue.add(clip("two"))
        assert a.id != b.id

    def test_wraps_the_captured_clip(self):
        queue = PendingClipQueue()
        captured = clip("hello")
        pending = queue.add(captured)
        assert pending.captured is captured
        assert pending.created_at == "T"


class TestListPending:
    def test_empty_queue(self):
        assert PendingClipQueue().list_pending() == []

    def test_preserves_insertion_order(self):
        queue = PendingClipQueue()
        first = queue.add(clip("one"))
        second = queue.add(clip("two"))
        third = queue.add(clip("three"))
        assert [p.id for p in queue.list_pending()] == [
            first.id, second.id, third.id]

    def test_reflects_multiple_simultaneous_items(self):
        queue = PendingClipQueue()
        queue.add(clip("one"))
        queue.add(clip("two"))
        assert len(queue.list_pending()) == 2
        assert len(queue) == 2


class TestPop:
    def test_removes_and_returns_the_item(self):
        queue = PendingClipQueue()
        pending = queue.add(clip("hello"))
        popped = queue.pop(pending.id)
        assert popped is pending
        assert queue.list_pending() == []

    def test_missing_id_returns_none(self):
        queue = PendingClipQueue()
        assert queue.pop("does-not-exist") is None

    def test_popped_item_is_gone_from_list_pending(self):
        queue = PendingClipQueue()
        first = queue.add(clip("one"))
        queue.add(clip("two"))
        queue.pop(first.id)
        remaining = queue.list_pending()
        assert first.id not in [p.id for p in remaining]
        assert len(remaining) == 1

    def test_double_pop_returns_none_the_second_time(self):
        queue = PendingClipQueue()
        pending = queue.add(clip("hello"))
        queue.pop(pending.id)
        assert queue.pop(pending.id) is None


class TestThreadSafety:
    def test_concurrent_adds_all_land(self):
        queue = PendingClipQueue()
        n = 50

        def add_one():
            queue.add(clip("x"))

        threads = [threading.Thread(target=add_one) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(queue) == n
        assert len({p.id for p in queue.list_pending()}) == n
