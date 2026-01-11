import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional, Union, Dict, Any

from clipboard import get_clipboard_item, ClipboardItem
from core.payload import poll_fingerprint

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapturedClipboard:
    payload: Union[bytes, str]
    metadata: Dict[str, Any]
    timestamp: str

    @classmethod
    def from_item(cls, item: ClipboardItem) -> "CapturedClipboard":
        payload: Union[bytes, str]
        if isinstance(item.payload, bytes):
            payload = item.payload
        else:
            payload = item.payload
        return cls(payload=payload, metadata=item.metaData, timestamp=item.timestamp.isoformat())


class ClipboardService:

    def __init__(
        self,
        on_capture: Optional[Callable[[CapturedClipboard], None]] = None,
        auto_register: bool = False,
    ) -> None:
        self._on_capture = on_capture or self._default_handler
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        self._is_running = False
        self.poll_interval = 0.25

        if auto_register:
            self.start()

    def start(self) -> None:
        with self._lock:
            if self._is_running:
                return

            self._stop_event.clear()
            self._is_running = True
            self._poll_thread = threading.Thread(
                target=self._poll_loop, daemon=True)
            self._poll_thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            self._stop_event.set()

        if self._poll_thread is not None:
            self._poll_thread.join(timeout=1.0)
            self._poll_thread = None

    def run_forever(self, poll_interval: float = 0.25) -> None:
        try:
            self.poll_interval = poll_interval
            if not self._is_running:
                self.start()

            while not self._stop_event.wait(timeout=poll_interval):
                continue
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def _poll_loop(self) -> None:
        last_hash = None
        first_run = True

        while not self._stop_event.is_set():
            try:
                item = get_clipboard_item()
                payload = getattr(item, "payload", None)
                meta = getattr(item, "metaData", None)
            except Exception:
                payload, meta = None, None

            if meta is not None:
                current_hash = poll_fingerprint(payload, meta)
            else:
                current_hash = None

            if first_run:
                last_hash = current_hash
                first_run = False
                time.sleep(self.poll_interval)
                continue

            if current_hash and current_hash != last_hash:
                try:
                    captured = CapturedClipboard.from_item(item)
                    clip_type = captured.metadata.get('type', 'unknown')
                    logger.info(f"Clipboard copied: {clip_type}")
                    self._on_capture(captured)
                except Exception as e:
                    logger.error(f"Error in on_capture: {e}")
                last_hash = current_hash

            self._stop_event.wait(self.poll_interval)

    @staticmethod
    def _default_handler(captured: CapturedClipboard) -> None:
        pass

    def __enter__(self) -> "ClipboardService":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(message)s")
    service = ClipboardService(auto_register=True)
    try:
        service.run_forever()
    except KeyboardInterrupt:
        pass
