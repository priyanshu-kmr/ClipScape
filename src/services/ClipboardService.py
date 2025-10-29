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
import keyboard

from clipboard import get_clipboard_item, ClipboardItem

logger = logging.getLogger(__name__)

# Default hotkey for developer builds. ``ctrl+alt+9`` is rarely used by Windows apps.
DEFAULT_HOTKEY = "ctrl+alt+9"


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
        hotkey: str = DEFAULT_HOTKEY,
        on_capture: Optional[Callable[[CapturedClipboard], None]] = None,
        auto_register: bool = False,
    ) -> None:
        """Initialise the service.

        Args:
            hotkey: Global hotkey combination to trigger capture.
            on_capture: Optional callback that receives the ``CapturedClipboard``.
            auto_register: When ``True`` the hotkey is registered immediately.
        """
        self.hotkey = hotkey
        self._on_capture = on_capture or self._default_handler
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._hotkey_handle: Optional[int] = None
        self._is_registered = False

        if auto_register:
            self.start()

    # ---------------------------------------------------------------------
    # Lifecycle management
    # ---------------------------------------------------------------------
    def start(self) -> None:
        """Register the configured hotkey."""
        if keyboard is None:
            raise RuntimeError(
                "The 'keyboard' package is required to use ClipboardService hotkeys. "
                "Install it with 'pip install keyboard'."
            )

        with self._lock:
            if self._is_registered:
                logger.debug("ClipboardService hotkey already registered")
                return

            logger.info("Registering clipboard hotkey: %s", self.hotkey)
            self._stop_event.clear()
            self._hotkey_handle = keyboard.add_hotkey(
                self.hotkey,
                callback=self._handle_hotkey,
                suppress=False,
                trigger_on_release=True,
            )
            self._is_registered = True

    def stop(self) -> None:
        """Remove the hotkey and stop the listener."""
        with self._lock:
            if not self._is_registered:
                return

            logger.info("Unregistering clipboard hotkey: %s", self.hotkey)
            if self._hotkey_handle is not None and keyboard is not None:
                keyboard.remove_hotkey(self._hotkey_handle)
            self._hotkey_handle = None
            self._is_registered = False
            self._stop_event.set()

    def run_forever(self, poll_interval: float = 0.25) -> None:
        """Convenience loop that keeps the service alive until ``stop`` is called."""
        try:
            if not self._is_registered:
                self.start()

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
        """Internal keyboard callback for hotkey activation."""
        try:
            logger.debug("Hotkey pressed; capturing clipboard")
            item = get_clipboard_item()
            captured = CapturedClipboard.from_item(item)
            self._on_capture(captured)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Failed to capture clipboard: %s", exc)

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
    logger.info("ClipboardService running; press %s to capture, Ctrl+C to exit", DEFAULT_HOTKEY)

    try:
        service.run_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
