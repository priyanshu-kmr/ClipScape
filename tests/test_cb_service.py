import sys
import time
import platform
from pathlib import Path

# Make src importable
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(SRC))

from services.ClipboardService import ClipboardService, CapturedClipboard  # type: ignore
from clipboard import get_clipboard_item  # type: ignore

def print_capture(captured: CapturedClipboard) -> None:
    t = captured.metadata.get("type", "unknown")
    if t == "text":
        payload = captured.payload
        if isinstance(payload, (bytes, bytearray)):
            text = payload.decode("utf-8", errors="ignore")
        else:
            text = str(payload)
        print("Text copied:", text)
    elif t == "file":
        name = captured.metadata.get("file_name")
        size = captured.metadata.get("file_size")
        print(f"File copied: name={name}, size={size}")
    elif t == "image":
        name = captured.metadata.get("file_name")
        size = captured.metadata.get("file_size")
        mime = captured.metadata.get("mime")
        print(f"Image copied: name={name}, size={size}, mime={mime}")
    else:
        print("Clipboard captured:", captured.metadata)

def polling_loop(poll_interval: float = 0.5) -> None:
    """Fallback loop when global hotkeys are not available."""
    last_meta = None
    last_payload = None
    print("Polling clipboard. Copy something (Ctrl+C) to stop.")
    try:
        while True:
            try:
                item = get_clipboard_item()
                payload = item.payload
                meta = item.metaData
            except Exception as exc:
                # ignore transient errors
                payload, meta = None, None

            if meta is not None and (meta != last_meta or payload != last_payload):
                captured = CapturedClipboard.from_item(item)  # type: ignore[arg-type]
                print_capture(captured)
                last_meta = meta
                last_payload = payload
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nStopped polling.")

def main() -> None:
    print(f"Platform: {platform.system()}. Starting ClipboardService test.")
    service = ClipboardService(on_capture=print_capture, auto_register=False)
    try:
        # Try to register the hotkey-based service first.
        service.start()
        print("ClipboardService running; press the configured hotkey to capture (default ctrl+alt+9). Ctrl+C to exit.")
        try:
            service.run_forever()
        finally:
            service.stop()
    except Exception as exc:
        # If hotkeys cannot be registered (missing permissions/package), fallback to polling.
        print("Could not start hotkey service (falling back to polling):", exc)
        polling_loop()

if __name__ == "__main__":
    main()