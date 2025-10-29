"""Clipboard service for ClipScape.

This module exposes a simple service class that listens for a developer hotkey
and snapshots the current clipboard contents using the platform clipboard
implementations found in ``src.clipboard``.
"""


import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Union, Dict, Any

from clipboard import get_clipboard_item, ClipboardItem

logger = logging.getLogger(__name__)

# Default hotkey for developer builds. ``ctrl+alt+9`` is rarely used by Windows apps.



@dataclass(frozen=True)
class CapturedClipboard:
    """Light-weight DTO that normalises clipboard data for downstream services."""

    payload: Union[bytes, str]
    metadata: Dict[str, Any]
    timestamp: str

    @classmethod
    def from_item(cls, item: ClipboardItem) -> "CapturedClipboard":
        payload: Union[bytes, str]
        if isinstance(item.payload, bytes):
            payload = item.payload
        else:  # Guard just in case a platform returns str.
            payload = item.payload  # type: ignore[assignment]
        return cls(payload=payload, metadata=item.metaData, timestamp=item.timestamp.isoformat())


class ClipboardService:
    """Service that captures clipboard snapshots via a hotkey trigger."""

    def __init__(
        self,
        on_capture: Optional[Callable[[CapturedClipboard], None]] = None,
        auto_register: bool = False,
    ) -> None:
        """Initialise the service.

        Args:
            hotkey: Global hotkey combination to trigger capture.
            on_capture: Optional callback that receives the ``CapturedClipboard``.
            auto_register: When ``True`` the hotkey is registered immediately.
        """
        self._on_capture = on_capture or self._default_handler
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        self._is_running = False
        # default poll interval (seconds)
        self.poll_interval = 0.25

        if auto_register:
            self.start()

    # ---------------------------------------------------------------------
    # Lifecycle management
    # ---------------------------------------------------------------------
    def start(self) -> None:
        """Start background polling of the clipboard.

        The polling thread snapshots the clipboard and calls the configured
        capture callback when a change is detected.
        """
        with self._lock:
            if self._is_running:
                logger.debug("ClipboardService already running")
                return

            logger.info("Starting ClipboardService polling (interval=%s)s", self.poll_interval)
            self._stop_event.clear()
            self._is_running = True
            self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self._poll_thread.start()

    def stop(self) -> None:
        """Stop the background polling thread."""
        with self._lock:
            if not self._is_running:
                return

            logger.info("Stopping ClipboardService polling")
            self._is_running = False
            self._stop_event.set()

        # join thread outside the lock
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=1.0)
            self._poll_thread = None

    def run_forever(self, poll_interval: float = 0.25) -> None:
        """Run the service in the foreground until stopped.

        This method sets the polling interval and blocks until `stop()` is
        called or Ctrl+C is pressed.
        """
        try:
            self.poll_interval = poll_interval
            if not self._is_running:
                self.start()

            # block until stop
            while not self._stop_event.wait(timeout=poll_interval):
                continue
        except KeyboardInterrupt:  # Allow Ctrl+C exits during development.
            logger.info("ClipboardService interrupted by user")
        finally:
            self.stop()

    # ---------------------------------------------------------------------
    # Event handling
    # ---------------------------------------------------------------------
    def _handle_hotkey(self) -> None:
        """Deprecated placeholder kept for compatibility.

        Hotkeys were removed in favor of polling. This method still snapshots
        the clipboard if called directly.
        """
        try:
            item = get_clipboard_item()
            captured = CapturedClipboard.from_item(item)
            self._on_capture(captured)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to capture clipboard: %s", exc)

    def _poll_loop(self) -> None:
        """Background polling loop."""
        last_meta = None
        last_payload = None
        while not self._stop_event.is_set():
            try:
                item = get_clipboard_item()
                payload = getattr(item, "payload", None)
                meta = getattr(item, "metaData", None)
            except Exception:
                payload, meta = None, None

            if meta is not None and (meta != last_meta or payload != last_payload):
                try:
                    captured = CapturedClipboard.from_item(item)
                    self._on_capture(captured)
                except Exception:
                    logger.exception("Error while calling on_capture")
                last_meta = meta
                last_payload = payload

            self._stop_event.wait(self.poll_interval)

    @staticmethod
    def _default_handler(captured: CapturedClipboard) -> None:
        """Fallback handler that logs captured clipboard metadata."""
        preview: Union[str, bytes]
        payload = captured.payload
        if isinstance(payload, bytes):
            preview = payload[:60]
        else:
            preview = payload[:60]
        logger.info(
            "Clipboard captured @ %s | type=%s | preview=%r",
            captured.timestamp,
            captured.metadata.get("type", "unknown"),
            preview,
        )

    # ---------------------------------------------------------------------
    # Context manager helpers
    # ---------------------------------------------------------------------
    def __enter__(self) -> "ClipboardService":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


def main() -> None:  # pragma: no cover - manual development hook
    """Simple manual test harness for the service."""
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    service = ClipboardService(auto_register=True)
    logger.info("ClipboardService running (polling). Ctrl+C to exit")

    try:
        service.run_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
