"""Persistence of a single captured clip.

Owns the one policy decision that used to be duplicated across the send and
receive paths: payloads over the threshold whose type is offloadable get
written to disk and stored in Redis as a reference instead of inline.
"""

import logging
from typing import Any, Optional

from core.payload import (
    LARGE_PAYLOAD_THRESHOLD_BYTES,
    as_bytes,
    payload_size,
    reference_metadata,
    should_offload,
)
from services.clipboard_service import CapturedClipboard
from services.redis_service import RedisService
from utils.file_manager import FileManager

logger = logging.getLogger(__name__)

LOCAL = "local"
REMOTE = "remote"


class ClipboardStore:
    """Saves clips to Redis, offloading large file payloads to disk first.

    `origin` distinguishes a locally copied clip from one received from a peer.
    The two differ in their log wording and -- deliberately preserved from the
    original implementation -- in what happens when the disk write fails: a
    local clip is dropped, a remote one falls back to storing the full payload
    inline. See follow-up #4.
    """

    def __init__(
        self,
        redis_service: Optional[RedisService],
        *,
        user_id: Optional[str],
        device_id: Optional[str],
        file_manager: Optional[FileManager] = None,
        threshold: int = LARGE_PAYLOAD_THRESHOLD_BYTES,
    ) -> None:
        self._redis_service = redis_service
        self._user_id = user_id
        self._device_id = device_id
        self._file_manager = file_manager
        self._threshold = threshold

    @property
    def enabled(self) -> bool:
        return bool(self._redis_service and self._user_id and self._device_id)

    def save(self, captured: CapturedClipboard, *, origin: str = LOCAL) -> None:
        if not self.enabled:
            return

        clip_type = captured.metadata.get('type', 'unknown')
        prefix = "Saved to Redis" if origin == LOCAL else "Saved received clipboard to Redis"

        try:
            size = payload_size(captured.payload)

            if should_offload(captured.metadata, size, threshold=self._threshold):
                to_store = self._offload(captured, size=size, origin=origin)
                if to_store is None:
                    return
                self._write(to_store)
                logger.info(f"{prefix} (reference): {clip_type}, {size} bytes")
            else:
                self._write(captured)
                logger.info(f"{prefix}: {clip_type}")
        except Exception as e:
            suffix = "" if origin == LOCAL else " for received clipboard"
            logger.error(f"Redis save error{suffix}: {e}")

    def _offload(
        self,
        captured: CapturedClipboard,
        *,
        size: int,
        origin: str,
    ) -> Optional[CapturedClipboard]:
        """Write the payload to disk and return a reference-only clip.

        Returns None when the write failed and the clip should be dropped
        (local origin); returns the original clip when it should be stored
        inline instead (remote origin).
        """
        file_path = self._files().save_file(
            as_bytes(captured.payload), captured.metadata)

        if not file_path:
            if origin == LOCAL:
                logger.error("Failed to save large file reference")
                return None
            return captured

        return CapturedClipboard(
            payload=b"",
            metadata=reference_metadata(
                captured.metadata, file_path=file_path, size=size),
            timestamp=captured.timestamp,
        )

    def _files(self) -> FileManager:
        # Constructed lazily: FileManager.__init__ mkdir's ~/.clipscape/files,
        # and that directory must only appear once a large clip is actually
        # offloaded, not at startup.
        if self._file_manager is None:
            self._file_manager = FileManager()
        return self._file_manager

    def _write(self, captured: CapturedClipboard) -> Any:
        return self._redis_service.save_captured_clipboard(
            user_id=self._user_id,
            device_id=self._device_id,
            captured=captured,
        )


def cleanup_managed_files(file_manager: Optional[FileManager] = None) -> None:
    try:
        manager = file_manager or FileManager()
        manager.cleanup_all_files()
        logger.info("Temp files cleaned up")
    except Exception as e:
        logger.warning(f"Could not clean temp files: {e}")
