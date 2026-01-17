from core.pending import new_pending_id, summarize_for_ui


class TestNewPendingId:
    def test_returns_a_non_empty_string(self):
        assert isinstance(new_pending_id(), str)
        assert len(new_pending_id()) > 0

    def test_two_calls_differ(self):
        assert new_pending_id() != new_pending_id()


class TestSummarizeForUi:
    def test_text_preview_short(self):
        summary = summarize_for_ui("text", b"hello", {"type": "text"})
        assert summary["preview"] == "hello"
        assert summary["size_bytes"] == 5

    def test_text_preview_truncates_long_text(self):
        payload = ("a" * 250).encode("utf-8")
        summary = summarize_for_ui(
            "text", payload, {"type": "text"}, preview_chars=200)
        assert summary["preview"] == "a" * 200 + "..."

    def test_text_preview_handles_str_payload(self):
        summary = summarize_for_ui("text", "hello", {"type": "text"})
        assert summary["preview"] == "hello"

    def test_text_preview_degrades_gracefully_on_bad_bytes(self):
        summary = summarize_for_ui(
            "text", b"\xff\xfe not valid utf-8", {"type": "text"})
        assert isinstance(summary["preview"], str)

    def test_file_preview_uses_file_name(self):
        summary = summarize_for_ui(
            "file", b"", {"type": "file", "file_name": "report.pdf"})
        assert summary["preview"] == "report.pdf"

    def test_folder_preview_uses_folder_name(self):
        summary = summarize_for_ui(
            "folder", b"", {"type": "folder", "folder_name": "Photos"})
        assert summary["preview"] == "Photos"

    def test_file_group_preview_joins_file_names(self):
        summary = summarize_for_ui(
            "file_group", b"",
            {"type": "file_group", "file_names": ["a.txt", "b.txt"]})
        assert summary["preview"] == "a.txt, b.txt"

    def test_image_size_bytes_matches_payload_length(self):
        summary = summarize_for_ui(
            "image", b"x" * 42, {"type": "image", "file_name": "shot.png"})
        assert summary["size_bytes"] == 42
