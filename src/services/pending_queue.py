"""In-memory queue of locally captured clips awaiting user approval.

Written from the clipboard poll thread (ClipboardSync.on_local_capture),
read/mutated from the approval API's server thread -- a single lock around an
OrderedDict is sufficient since every operation is O(1) dict/list work, never
blocked on I/O.
"""

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Optional

from core.pending import new_pending_id
from services.clipboard_service import CapturedClipboard


@dataclass(frozen=True)
class PendingClip:
    id: str
    captured: CapturedClipboard
    created_at: str


class PendingClipQueue:

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: "OrderedDict[str, PendingClip]" = OrderedDict()

    def add(self, captured: CapturedClipboard) -> PendingClip:
        pending = PendingClip(
            id=new_pending_id(), captured=captured, created_at=captured.timestamp)
        with self._lock:
            self._items[pending.id] = pending
        return pending

    def list_pending(self) -> List[PendingClip]:
        with self._lock:
            return list(self._items.values())

    def pop(self, clip_id: str) -> Optional[PendingClip]:
        with self._lock:
            return self._items.pop(clip_id, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
