import base64
import json

import pytest

from core.wire import (
    CLIPBOARD_MESSAGE_TYPES,
    InboundClip,
    decode_clipboard_message,
    encode_clipboard_message,
    is_clipboard_message,
)


class TestEncode:
    def test_envelope_has_exactly_the_four_keys(self):
        msg = json.loads(encode_clipboard_message(
            payload=b"x", metadata={"type": "text"}, timestamp="T"))
        assert set(msg) == {"type", "payload", "metadata", "timestamp"}

    def test_type_is_prefixed(self):
        msg = json.loads(encode_clipboard_message(
            payload=b"x", metadata={"type": "image"}, timestamp="T"))
        assert msg["type"] == "clipboard_image"

    def test_missing_type_defaults_to_text(self):
        msg = json.loads(encode_clipboard_message(
            payload=b"x", metadata={}, timestamp="T"))
        assert msg["type"] == "clipboard_text"

    def test_bytes_payload_is_base64(self):
        msg = json.loads(encode_clipboard_message(
            payload=b"\x00\xff", metadata={}, timestamp="T"))
        assert base64.b64decode(msg["payload"]) == b"\x00\xff"

    def test_str_payload_is_utf8_then_base64(self):
        msg = json.loads(encode_clipboard_message(
            payload="héllo", metadata={}, timestamp="T"))
        assert base64.b64decode(msg["payload"]) == "héllo".encode("utf-8")

    def test_metadata_and_timestamp_pass_through(self):
        meta = {"type": "file", "file_name": "a.bin", "file_size": 3}
        msg = json.loads(encode_clipboard_message(
            payload=b"abc", metadata=meta, timestamp="2026-01-01T00:00:00"))
        assert msg["metadata"] == meta
        assert msg["timestamp"] == "2026-01-01T00:00:00"


class TestDecode:
    def test_base64_str_payload_is_decoded(self):
        clip = decode_clipboard_message(
            {"payload": base64.b64encode(b"abc").decode("ascii")})
        assert clip.payload == b"abc"

    def test_already_bytes_payload_passes_through(self):
        clip = decode_clipboard_message({"payload": b"raw"})
        assert clip.payload == b"raw"

    def test_empty_message_yields_empty_clip(self):
        assert decode_clipboard_message({}) == InboundClip(b"", {}, None)

    def test_missing_timestamp_is_none(self):
        clip = decode_clipboard_message({"payload": "", "metadata": {}})
        assert clip.timestamp is None


class TestRoundTrip:
    def test_binary_payload_survives(self):
        meta = {"type": "file", "file_name": "a.bin"}
        encoded = encode_clipboard_message(
            payload=b"\x00\xff\xfe", metadata=meta, timestamp="T")
        clip = decode_clipboard_message(json.loads(encoded))
        assert clip.payload == b"\x00\xff\xfe"
        assert clip.metadata == meta
        assert clip.timestamp == "T"

    def test_empty_payload_survives(self):
        encoded = encode_clipboard_message(
            payload=b"", metadata={"type": "file_group"}, timestamp="T")
        assert decode_clipboard_message(json.loads(encoded)).payload == b""


class TestIsClipboardMessage:
    @pytest.mark.parametrize("clip_type", CLIPBOARD_MESSAGE_TYPES)
    def test_accepted_types(self, clip_type):
        assert is_clipboard_message({"type": clip_type}) is True

    @pytest.mark.parametrize("clip_type", ["clipboard_folder", "clipboard_file_group"])
    def test_folder_and_file_group_are_dropped(self, clip_type):
        # Current behavior, deliberately pinned: the encode side emits these
        # but the receive side rejects them, so folder/file-group sync is dead
        # on the wire. Update this test as part of fixing follow-up #1.
        assert is_clipboard_message({"type": clip_type}) is False

    def test_unrelated_and_missing_types(self):
        assert is_clipboard_message({"type": "offer"}) is False
        assert is_clipboard_message({}) is False
