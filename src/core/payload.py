"""Pure payload arithmetic shared by the capture, persistence and sync paths.

Nothing here touches the filesystem, Redis, the network or the system clipboard,
so every function is directly unit-testable.
"""

import hashlib
import os
from typing import Any, Dict, FrozenSet, Mapping, Union

LARGE_PAYLOAD_THRESHOLD_BYTES: int = 1_048_576

OFFLOADABLE_TYPES: FrozenSet[str] = frozenset({"file", "folder", "file_group"})


def as_bytes(payload: Any) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode('utf-8')
    return bytes(payload)


def payload_size(payload: Any) -> int:
    if isinstance(payload, bytes):
        return len(payload)
    return len(str(payload).encode('utf-8'))


def should_offload(
    metadata: Mapping[str, Any],
    size: int,
    *,
    threshold: int = LARGE_PAYLOAD_THRESHOLD_BYTES
) -> bool:
    return metadata.get('type', 'unknown') in OFFLOADABLE_TYPES and size > threshold


def reference_metadata(
    metadata: Mapping[str, Any],
    *,
    file_path: Union[str, os.PathLike],
    size: int
) -> Dict[str, Any]:
    copied = dict(metadata)
    copied['file_reference'] = str(file_path)
    copied['payload_size'] = size
    return copied


def content_fingerprint(payload: Any, metadata: Mapping[str, Any]) -> str:
    # Deliberately not routed through as_bytes: this coercion has no fallback
    # for non-bytes/non-str payloads, and callers depend on that. See the
    # follow-up list before unifying the two.
    if isinstance(payload, str):
        payload_bytes = payload.encode('utf-8')
    else:
        payload_bytes = payload
    content = payload_bytes + metadata.get('type', '').encode('utf-8')
    return hashlib.md5(content).hexdigest()


def poll_fingerprint(payload: Any, metadata: Mapping[str, Any]) -> str:
    """Change-detection hash used by the clipboard poll loop.

    Intentionally different from content_fingerprint: file-ish clips are keyed
    on their path metadata rather than their bytes, and byte payloads are
    truncated to 1 KiB.
    """
    meta_str = str(sorted(metadata.items()))
    clip_type = metadata.get('type', 'unknown')

    if clip_type in ['file', 'folder', 'file_group']:
        path_info = metadata.get('path', '') or metadata.get('paths', [])
        file_name = metadata.get('file_name', '') or metadata.get(
            'folder_name', '')
        hash_input = f"{clip_type}:{path_info}:{file_name}:{metadata.get('file_size', 0)}".encode(
            'utf-8')
    elif isinstance(payload, bytes):
        hash_input = payload[:1024] + meta_str.encode('utf-8')
    else:
        hash_input = str(payload).encode('utf-8') + meta_str.encode('utf-8')

    return hashlib.md5(hash_input).hexdigest()
