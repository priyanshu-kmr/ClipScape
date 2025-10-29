import sys
import time
from pathlib import Path
from typing import Any

# Make src importable
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(SRC))

from clipboard import get_clipboard_item  # type: ignore


def _print_item(item: Any) -> None:
    """Print a human-friendly preview of the clipboard item.

    - For text: print decoded text.
    - For file: prefer the full path if available, otherwise the file name.
    - For image: print image file_name and mime if present.
    - Otherwise: print the metadata dict.
    """
    meta = getattr(item, "metaData", {}) or {}
    payload = getattr(item, "payload", None)
    t = meta.get("type")

    if t == "text":
        if isinstance(payload, (bytes, bytearray)):
            try:
                text = payload.decode("utf-8")
            except Exception:
                text = payload.decode("utf-8", errors="ignore")
        else:
            text = str(payload)
        print("Text copied:", text)
        return

    if t == "file":
        # Some platforms provide 'path' and some only 'file_name'
        path = meta.get("path")
        if path:
            print(f"File copied: path={path}")
            return
        file_name = meta.get("file_name")
        if file_name:
            print(f"File copied: name={file_name}")
            return
        # Last resort: show metadata
        print("File copied:", meta)
        return

    if t == "image":
        name = meta.get("file_name")
        mime = meta.get("mime")
        size = meta.get("file_size")
        print(f"Image copied: name={name}, size={size}, mime={mime}")
        return

    # Unknown type: print metadata for debugging
    print("Clipboard item:", meta)


def polling_loop(poll_interval: float = 0.5) -> None:
    last_meta = None
    last_payload = None
    print("Polling clipboard. Copy something (Ctrl+C) to stop.")
    try:
        while True:
            try:
                item = get_clipboard_item()
                payload = getattr(item, "payload", None)
                meta = getattr(item, "metaData", None)
            except Exception as exc:
                # ignore transient errors
                payload, meta = None, None

            if meta is not None and (meta != last_meta or payload != last_payload):
                _print_item(item)
                last_meta = meta
                last_payload = payload

            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nStopped polling.")


def main() -> None:
    polling_loop()


if __name__ == "__main__":
    main()