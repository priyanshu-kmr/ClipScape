"""The clipboard message envelope exchanged between peers.

Encode and decode live together so the format has exactly one definition and
can be round-tripped in a test. Pure: no sockets, no clipboard, no Redis.
"""

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple, Union

# Message types the receive side accepts. Note that the encode side can emit
# clipboard_folder and clipboard_file_group, which are absent here and are
# therefore dropped on arrival -- see follow-up #1.
CLIPBOARD_MESSAGE_TYPES: Tuple[str, ...] = (
    "clipboard_text",
    "clipboard_image",
    "clipboard_file",
)


@dataclass(frozen=True)
class InboundClip:
    payload: bytes
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None


def encode_clipboard_message(
    *,
    payload: Union[bytes, str],
    metadata: Mapping[str, Any],
    timestamp: str
) -> str:
    clip_type = metadata.get("type", "text")

    if isinstance(payload, bytes):
        payload_b64 = base64.b64encode(payload).decode("ascii")
    else:
        payload_b64 = base64.b64encode(
            str(payload).encode("utf-8")).decode("ascii")

    return json.dumps({
        "type": f"clipboard_{clip_type}",
        "payload": payload_b64,
        "metadata": metadata,
        "timestamp": timestamp,
    })


def is_clipboard_message(data: Mapping[str, Any]) -> bool:
    return data.get("type") in CLIPBOARD_MESSAGE_TYPES


def decode_clipboard_message(data: Mapping[str, Any]) -> InboundClip:
    payload_b64 = data.get("payload", "")
    metadata = data.get("metadata", {})
    timestamp = data.get("timestamp", None)

    if isinstance(payload_b64, str):
        payload = base64.b64decode(payload_b64)
    else:
        payload = payload_b64

    return InboundClip(payload=payload, metadata=metadata, timestamp=timestamp)
