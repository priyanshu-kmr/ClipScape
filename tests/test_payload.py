import hashlib

import pytest

from core.payload import (
    LARGE_PAYLOAD_THRESHOLD_BYTES,
    as_bytes,
    content_fingerprint,
    payload_size,
    poll_fingerprint,
    reference_metadata,
    should_offload,
)


class TestAsBytes:
    def test_bytes_pass_through(self):
        assert as_bytes(b"x") == b"x"

    def test_str_is_utf8_encoded(self):
        assert as_bytes("héllo") == b"h\xc3\xa9llo"

    def test_other_buffers_fall_back_to_bytes(self):
        assert as_bytes(bytearray(b"ab")) == b"ab"


class TestPayloadSize:
    def test_bytes_length(self):
        assert payload_size(b"abc") == 3

    def test_str_counts_utf8_bytes_not_characters(self):
        assert payload_size("héllo") == 6

    def test_empty(self):
        assert payload_size(b"") == 0


class TestShouldOffload:
    def test_exactly_at_threshold_is_not_offloaded(self):
        assert should_offload({"type": "file"},
                              LARGE_PAYLOAD_THRESHOLD_BYTES) is False

    def test_one_byte_over_threshold_is_offloaded(self):
        assert should_offload({"type": "file"},
                              LARGE_PAYLOAD_THRESHOLD_BYTES + 1) is True

    @pytest.mark.parametrize("clip_type", ["file", "folder", "file_group"])
    def test_offloadable_types(self, clip_type):
        assert should_offload({"type": clip_type}, 2 * 1024 * 1024) is True

    @pytest.mark.parametrize("clip_type", ["text", "image", "unknown"])
    def test_non_offloadable_types_never_offload(self, clip_type):
        assert should_offload({"type": clip_type}, 10 ** 9) is False

    def test_missing_type_does_not_offload(self):
        assert should_offload({}, 10 ** 9) is False

    def test_custom_threshold(self):
        assert should_offload({"type": "file"}, 11, threshold=10) is True
        assert should_offload({"type": "file"}, 10, threshold=10) is False


class TestReferenceMetadata:
    def test_adds_reference_and_size(self):
        result = reference_metadata(
            {"type": "file"}, file_path="/tmp/a.bin", size=42)
        assert result["file_reference"] == "/tmp/a.bin"
        assert result["payload_size"] == 42

    def test_file_path_is_stringified(self, tmp_path):
        target = tmp_path / "a.bin"
        result = reference_metadata({}, file_path=target, size=1)
        assert result["file_reference"] == str(target)
        assert isinstance(result["file_reference"], str)

    def test_preserves_existing_keys(self):
        result = reference_metadata(
            {"type": "file", "file_name": "a.bin"}, file_path="/tmp/a.bin", size=1)
        assert result["type"] == "file"
        assert result["file_name"] == "a.bin"

    def test_does_not_mutate_input(self):
        original = {"type": "file"}
        reference_metadata(original, file_path="/tmp/a.bin", size=1)
        assert original == {"type": "file"}


class TestContentFingerprint:
    def test_str_and_bytes_agree(self):
        meta = {"type": "text"}
        assert content_fingerprint("hello", meta) == content_fingerprint(
            b"hello", meta)

    def test_pinned_vector(self):
        assert content_fingerprint("hello", {"type": "text"}) == hashlib.md5(
            b"hellotext").hexdigest()

    def test_type_participates_in_the_hash(self):
        assert content_fingerprint(b"x", {"type": "text"}) != content_fingerprint(
            b"x", {"type": "image"})

    def test_missing_type_behaves_as_empty_string(self):
        assert content_fingerprint(b"x", {}) == content_fingerprint(
            b"x", {"type": ""})

    def test_only_type_is_considered_from_metadata(self):
        assert content_fingerprint(b"x", {"type": "text", "length": 1}) == \
            content_fingerprint(b"x", {"type": "text", "length": 999})

    def test_bytearray_happens_to_work(self):
        # bytearray + bytes concatenates, so this path agrees with as_bytes.
        assert content_fingerprint(bytearray(b"hello"), {"type": "text"}) == \
            content_fingerprint(b"hello", {"type": "text"})

    @pytest.mark.parametrize("payload", [memoryview(b"x"), 5, None])
    def test_raises_where_as_bytes_would_not(self, payload):
        # Pins the coercion gap: as_bytes(memoryview(b"x")) and as_bytes(5)
        # both succeed, but this hash raises. See follow-up #7 before
        # "unifying" the two coercions.
        with pytest.raises(TypeError):
            content_fingerprint(payload, {"type": "text"})


class TestPollFingerprint:
    def test_file_branch_ignores_the_payload_entirely(self):
        meta = {"type": "file", "path": "/a/b.bin",
                "file_name": "b.bin", "file_size": 10}
        assert poll_fingerprint(b"aaa", meta) == poll_fingerprint(b"zzz", meta)

    def test_file_branch_keys_on_path(self):
        base = {"type": "file", "file_name": "b.bin", "file_size": 10}
        assert poll_fingerprint(b"", {**base, "path": "/a/b.bin"}) != \
            poll_fingerprint(b"", {**base, "path": "/c/b.bin"})

    def test_bytes_branch_truncates_at_1kib(self):
        meta = {"type": "image"}
        a = b"a" * 2000 + b"X"
        b = b"a" * 2000 + b"Y"
        # Differences past byte 1024 are invisible to this hash. Follow-up #8.
        assert poll_fingerprint(a, meta) == poll_fingerprint(b, meta)

    def test_bytes_branch_sees_differences_within_1kib(self):
        meta = {"type": "image"}
        assert poll_fingerprint(b"a" * 100, meta) != poll_fingerprint(
            b"b" * 100, meta)

    def test_metadata_key_order_does_not_matter(self):
        assert poll_fingerprint(b"x", {"type": "image", "file_size": 1}) == \
            poll_fingerprint(b"x", {"file_size": 1, "type": "image"})

    def test_non_bytes_payload_branch(self):
        meta = {"type": "text"}
        assert poll_fingerprint("hello", meta) != poll_fingerprint(
            "world", meta)


def test_the_two_fingerprints_are_deliberately_different():
    # Regression pin: these two hashes are rival implementations that disagree
    # (follow-up #2). Unifying them is a behavior change, not a cleanup.
    payload, meta = b"hello", {"type": "text"}
    assert content_fingerprint(payload, meta) != poll_fingerprint(payload, meta)
