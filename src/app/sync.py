"""Bidirectional clipboard mediation.

Local capture -> persist + broadcast. Remote message -> apply to the clipboard
+ persist. Owns the echo-suppression state that keeps a clip written by a peer
from being immediately re-broadcast back.
"""

import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from clipboard import get_clipboard_class
from core.payload import content_fingerprint
from core.wire import decode_clipboard_message
from services.clipboard_service import CapturedClipboard
from services.clipboard_store import LOCAL, REMOTE, ClipboardStore
from services.pending_queue import PendingClipQueue

logger = logging.getLogger(__name__)


def _default_clipboard_writer(payload: bytes, metadata: Dict[str, Any]) -> bool:
    return get_clipboard_class().set_clipboard(payload, metadata)


def _now() -> str:
    return datetime.now().isoformat()


class ClipboardSync:

    def __init__(
        self,
        store: Optional[ClipboardStore],
        broadcast: Optional[Callable[[Dict[str, Any]], bool]] = None,
        *,
        clipboard_writer: Callable[[bytes, Dict[str, Any]],
                                   bool] = _default_clipboard_writer,
        echo_guard_delay: float = 0.1,
        now: Callable[[], str] = _now,
        pending_queue: Optional[PendingClipQueue] = None,
    ) -> None:
        self._store = store
        self._broadcast = broadcast
        self._write_clipboard = clipboard_writer
        self._echo_guard_delay = echo_guard_delay
        self._now = now
        self._pending_queue = pending_queue

        self._last_sent_hash: Optional[str] = None
        self._setting_clipboard = False

    def on_local_capture(self, captured: CapturedClipboard) -> None:
        if self._setting_clipboard:
            return

        current_hash = content_fingerprint(captured.payload, captured.metadata)
        if current_hash == self._last_sent_hash:
            return

        self._last_sent_hash = current_hash

        clip_type = captured.metadata.get('type', 'unknown')

        if self._store:
            self._store.save(captured, origin=LOCAL)

        if self._pending_queue is not None:
            pending = self._pending_queue.add(captured)
            logger.info(f"Queued for approval: {clip_type} ({pending.id})")
            return

        if self._broadcast is not None:
            clipboard_data = {
                "payload": captured.payload,
                "metadata": captured.metadata,
                "timestamp": captured.timestamp
            }
            logger.info(f"Broadcasting clipboard: {clip_type}")
            self._broadcast(clipboard_data)

    def approve(self, clip_id: str) -> bool:
        if self._pending_queue is None:
            return False

        pending = self._pending_queue.pop(clip_id)
        if pending is None:
            return False

        if self._broadcast is not None:
            clipboard_data = {
                "payload": pending.captured.payload,
                "metadata": pending.captured.metadata,
                "timestamp": pending.captured.timestamp,
            }
            clip_type = pending.captured.metadata.get('type', 'unknown')
            logger.info(
                f"Broadcasting approved clipboard: {clip_type} ({clip_id})")
            self._broadcast(clipboard_data)

        return True

    def reject(self, clip_id: str) -> bool:
        if self._pending_queue is None:
            return False

        return self._pending_queue.pop(clip_id) is not None

    def on_remote_message(self, data: Dict[str, Any]) -> None:
        try:
            clip = decode_clipboard_message(data)

            self._setting_clipboard = True

            try:
                success = self._write_clipboard(clip.payload, clip.metadata)

                if success:
                    clip_type = clip.metadata.get('type', 'unknown')
                    logger.info(f"Clipboard received and set: {clip_type}")
                    self._last_sent_hash = content_fingerprint(
                        clip.payload, clip.metadata)

                    if self._store:
                        self._store.save(
                            CapturedClipboard(
                                payload=clip.payload,
                                metadata=clip.metadata,
                                timestamp=clip.timestamp or self._now()
                            ),
                            origin=REMOTE,
                        )
            finally:
                time.sleep(self._echo_guard_delay)
                self._setting_clipboard = False

        except Exception as e:
            logger.error(f"Error handling clipboard: {e}")
            self._setting_clipboard = False
