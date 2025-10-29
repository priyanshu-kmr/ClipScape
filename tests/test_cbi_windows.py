from pathlib import Path
import sys
import time
import platform

# ensure src is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
sys.path.insert(0, str(SRC))

from clipboard.windows import CBI_Windows  # type: ignore


def main(poll_interval: float = 0.5) -> None:
    if platform.system().lower() != "windows":
        print("This watcher is for Windows only.")
        return

    watcher = CBI_Windows()
    last_meta = None
    last_payload = b""

    print("Clipboard watcher running. Copy something — Ctrl+C in this terminal to stop.")
    try:
        while True:
            try:
                payload, meta = watcher._get_cbi()
            except Exception as exc:
                # keep running on transient errors
                print("Error reading clipboard:", exc)
                payload, meta = None, None

            if meta is not None and (meta != last_meta or payload != last_payload):
                t = meta.get("type")
                if t == "text":
                    text = (payload or b"").decode("utf-8", errors="ignore")
                    print("Text copied:", text)
                elif t == "file":
                    name = meta.get("file_name")
                    size = meta.get("file_size")
                    path = meta.get("path")
                    print(f"File copied: name={name}, size={size}, path={path}")
                elif t == "image":
                    name = meta.get("file_name")
                    size = meta.get("file_size")
                    mime = meta.get("mime")
                    print(f"Image copied: name={name}, size={size}, mime={mime}")
                else:
                    print(meta)

                last_meta = meta
                last_payload = payload

            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\nWatcher stopped.")


if __name__ == "__main__":
    main()