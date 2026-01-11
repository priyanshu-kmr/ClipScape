import logging

import pytest

from services.clipboard_service import CapturedClipboard
from services.clipboard_store import LOCAL, REMOTE, ClipboardStore

MIB = 1024 * 1024


class FakeRedisService:
    def __init__(self, raises=None):
        self.saved = []
        self._raises = raises

    def save_captured_clipboard(self, *, user_id, device_id, captured):
        if self._raises:
            raise self._raises
        self.saved.append((user_id, device_id, captured))
        return "i_fake"


class FakeFileManager:
    def __init__(self, result="/tmp/clipscape/big.bin"):
        self.calls = []
        self._result = result

    def save_file(self, payload, metadata):
        self.calls.append((payload, metadata))
        return self._result


def clip(payload, clip_type, timestamp="T"):
    return CapturedClipboard(
        payload=payload, metadata={"type": clip_type, "file_name": "big.bin"},
        timestamp=timestamp)


def make_store(redis=None, files=None, **overrides):
    kwargs = {"user_id": "u_1", "device_id": "d_1"}
    kwargs.update(overrides)
    return ClipboardStore(
        redis if redis is not None else FakeRedisService(),
        file_manager=files,
        **kwargs,
    )


class TestEnabled:
    def test_enabled_with_everything_present(self):
        assert make_store().enabled is True

    @pytest.mark.parametrize("missing", ["redis", "user_id", "device_id"])
    def test_disabled_when_any_piece_is_missing(self, missing):
        redis = FakeRedisService()
        kwargs = {"user_id": "u_1", "device_id": "d_1"}
        if missing == "redis":
            redis = None
        else:
            kwargs[missing] = None
        store = ClipboardStore(redis, **kwargs)
        assert store.enabled is False

    def test_disabled_store_saves_nothing(self):
        redis = FakeRedisService()
        files = FakeFileManager()
        store = ClipboardStore(
            redis, user_id=None, device_id="d_1", file_manager=files)
        store.save(clip(b"x" * (2 * MIB), "file"))
        assert redis.saved == []
        assert files.calls == []


class TestSmallClips:
    def test_text_clip_stored_unchanged(self):
        redis = FakeRedisService()
        store = make_store(redis)
        captured = clip("hello", "text")
        store.save(captured)
        assert redis.saved == [("u_1", "d_1", captured)]

    def test_large_text_is_not_offloaded(self):
        redis, files = FakeRedisService(), FakeFileManager()
        make_store(redis, files).save(clip("x" * (2 * MIB), "text"))
        assert files.calls == []
        assert len(redis.saved[0][2].payload) == 2 * MIB

    def test_small_file_is_not_offloaded(self):
        redis, files = FakeRedisService(), FakeFileManager()
        make_store(redis, files).save(clip(b"x" * 100, "file"))
        assert files.calls == []
        assert redis.saved[0][2].payload == b"x" * 100


class TestOffload:
    def test_large_file_is_written_to_disk_and_stored_as_reference(self):
        redis, files = FakeRedisService(), FakeFileManager()
        make_store(redis, files).save(clip(b"x" * (2 * MIB), "file"))

        assert files.calls[0][0] == b"x" * (2 * MIB)

        stored = redis.saved[0][2]
        assert stored.payload == b""
        assert stored.metadata["file_reference"] == "/tmp/clipscape/big.bin"
        assert stored.metadata["payload_size"] == 2 * MIB

    def test_offload_preserves_timestamp(self):
        redis = FakeRedisService()
        make_store(redis, FakeFileManager()).save(
            clip(b"x" * (2 * MIB), "file", timestamp="2026-01-01"))
        assert redis.saved[0][2].timestamp == "2026-01-01"

    def test_original_metadata_is_not_mutated(self):
        captured = clip(b"x" * (2 * MIB), "file")
        make_store(FakeRedisService(), FakeFileManager()).save(captured)
        assert "file_reference" not in captured.metadata

    def test_custom_threshold(self):
        redis, files = FakeRedisService(), FakeFileManager()
        make_store(redis, files, threshold=10).save(clip(b"x" * 50, "file"))
        assert files.calls != []


class TestOffloadFailureDivergesByOrigin:
    """save_file returning None is handled differently per direction.

    Preserved from the original implementation; see follow-up #4.
    """

    def test_local_drops_the_clip(self, caplog):
        redis = FakeRedisService()
        files = FakeFileManager(result=None)
        with caplog.at_level(logging.ERROR):
            make_store(redis, files).save(
                clip(b"x" * (2 * MIB), "file"), origin=LOCAL)
        assert redis.saved == []
        assert "Failed to save large file reference" in caplog.text

    def test_remote_falls_back_to_storing_inline(self):
        redis = FakeRedisService()
        files = FakeFileManager(result=None)
        make_store(redis, files).save(
            clip(b"x" * (2 * MIB), "file"), origin=REMOTE)
        assert len(redis.saved) == 1
        assert redis.saved[0][2].payload == b"x" * (2 * MIB)


class TestErrorHandling:
    def test_redis_exception_is_swallowed_and_logged(self, caplog):
        redis = FakeRedisService(raises=RuntimeError("boom"))
        with caplog.at_level(logging.ERROR):
            make_store(redis).save(clip("hello", "text"), origin=LOCAL)
        assert "Redis save error: boom" in caplog.text

    def test_remote_error_message_is_distinct(self, caplog):
        redis = FakeRedisService(raises=RuntimeError("boom"))
        with caplog.at_level(logging.ERROR):
            make_store(redis).save(clip("hello", "text"), origin=REMOTE)
        assert "Redis save error for received clipboard: boom" in caplog.text


class TestFileManagerLaziness:
    def test_file_manager_is_not_built_for_small_clips(self, monkeypatch):
        # FileManager.__init__ mkdir's ~/.clipscape/files, so it must not be
        # constructed until a clip actually needs offloading.
        import services.clipboard_store as module

        def explode():
            raise AssertionError("FileManager was constructed eagerly")

        monkeypatch.setattr(module, "FileManager", lambda *a, **k: explode())

        store = ClipboardStore(
            FakeRedisService(), user_id="u_1", device_id="d_1")
        store.save(clip("hello", "text"))
        store.save(clip(b"x" * 100, "file"))

    def test_file_manager_is_reused_across_offloads(self):
        files = FakeFileManager()
        store = make_store(FakeRedisService(), files)
        store.save(clip(b"x" * (2 * MIB), "file"))
        store.save(clip(b"y" * (2 * MIB), "file"))
        assert len(files.calls) == 2
