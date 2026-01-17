"""Pure helpers for the approval-gated pending-clip queue.

No I/O, no queue/service state -- just id generation and the UI-facing summary
shape, kept separate so both are directly unit-testable. See services/pending_queue.py
for the stateful queue that owns pending items.
"""

from typing import Any, Dict, Mapping, Union

from core.payload import payload_size


def new_pending_id() -> str:
    import ulid
    return str(ulid.new())


def summarize_for_ui(
    clip_type: str,
    payload: Union[bytes, str],
    metadata: Mapping[str, Any],
    *,
    preview_chars: int = 200,
) -> Dict[str, Any]:
    if clip_type == "text":
        preview = _text_preview(payload, preview_chars)
    else:
        preview = (
            metadata.get("file_name")
            or metadata.get("folder_name")
            or ", ".join(metadata.get("file_names", []) or [])
        )

    return {
        "preview": preview,
        "size_bytes": payload_size(payload),
    }


def _text_preview(payload: Union[bytes, str], preview_chars: int) -> str:
    try:
        text = payload.decode("utf-8", errors="ignore") if isinstance(
            payload, bytes) else str(payload)
    except Exception:
        return ""

    if len(text) > preview_chars:
        return text[:preview_chars] + "..."
    return text
