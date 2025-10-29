import datetime
import win32clipboard as wc
import win32con
import io
from PIL import ImageGrab
import os
import time
import ulid
import mimetypes
from clipboard.base import ClipboardItem
from typing import Dict, Any, Optional, Tuple, List


class CBI_Windows(ClipboardItem):
    """Windows-specific implementation of ClipboardItem."""

    def _get_cbi(self):
        payload = b""
        metaData = {}

        # First try images (ImageGrab)
        imagegrab_result = self._from_imagegrab()
        if imagegrab_result is not None:
            return imagegrab_result

        opened = False
        for _ in range(3):
            try:
                wc.OpenClipboard()
                opened = True
                break
            except Exception:
                time.sleep(0.05)

        try:
            # Handle multiple file paths (CF_HDROP)
            if opened and wc.IsClipboardFormatAvailable(win32con.CF_HDROP):
                try:
                    files = wc.GetClipboardData(win32con.CF_HDROP)
                except Exception:
                    files = []

                # Normalize file list
                if isinstance(files, str):
                    files = [files]

                valid_files: List[Tuple[bytes, Dict[str, Any]]] = []
                for path in files or []:
                    file_item = self._build_file_item(path)
                    if file_item is not None:
                        valid_files.append(file_item)

                # If multiple files, merge into one combined metadata
                if valid_files:
                    if len(valid_files) == 1:
                        return valid_files[0]
                    else:
                        combined_meta = {
                            "type": "file_group",
                            "count": len(valid_files),
                            "file_names": [meta["file_name"] for _, meta in valid_files],
                            "paths": [meta["path"] for _, meta in valid_files],
                            "owner_device": ""
                        }
                        return b"", combined_meta

            # Handle text (Unicode)
            if opened and wc.IsClipboardFormatAvailable(wc.CF_UNICODETEXT):
                try:
                    text = wc.GetClipboardData(wc.CF_UNICODETEXT)
                except Exception:
                    text = None
                if text is not None:
                    payload = text.encode("utf-8")
                    metaData.update({
                        "type": "text",
                        "length": len(text),
                        "owner_device": ""
                    })
                    return payload, metaData

        finally:
            if opened:
                try:
                    wc.CloseClipboard()
                except Exception:
                    pass

        return payload, metaData

    def _from_imagegrab(self) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        try:
            clipboard_data = ImageGrab.grabclipboard()
        except Exception:
            return None

        if clipboard_data is None:
            return None

        # If clipboard holds file paths
        if isinstance(clipboard_data, (list, tuple)):
            valid_files = []
            for path in clipboard_data:
                file_item = self._build_file_item(path)
                if file_item is not None:
                    valid_files.append(file_item)

            if valid_files:
                if len(valid_files) == 1:
                    return valid_files[0]
                else:
                    combined_meta = {
                        "type": "file_group",
                        "count": len(valid_files),
                        "file_names": [meta["file_name"] for _, meta in valid_files],
                        "paths": [meta["path"] for _, meta in valid_files],
                        "owner_device": ""
                    }
                    return b"", combined_meta
            return None

        # If clipboard holds an image
        if hasattr(clipboard_data, "save"):
            creation_time = datetime.datetime.now()
            output = io.BytesIO()
            try:
                clipboard_data.save(output, format="PNG")
            except Exception:
                return None
            payload = output.getvalue()
            metaData = {
                "type": "image",
                "file_name": str(ulid.ULID.from_datetime(creation_time)) + ".png",
                "file_size": len(payload),
                "creation_time": creation_time.isoformat(),
                "mime": "image/png",
                "owner_device": ""
            }
            return payload, metaData

        return None

    def _build_file_item(self, path: Any) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        if not path:
            return None

        if not isinstance(path, str):
            try:
                path = path.decode("utf-8")
            except Exception:
                return None

        normalized_path = os.path.normpath(path)
        if not os.path.exists(normalized_path) or not os.path.isfile(normalized_path):
            return None

        mime_type, _ = mimetypes.guess_type(normalized_path)
        try:
            with open(normalized_path, "rb") as f:
                payload = f.read()
        except OSError:
            payload = b""

        creation_time = None
        try:
            creation_dt = datetime.datetime.fromtimestamp(os.path.getctime(normalized_path))
            creation_time = creation_dt.isoformat()
        except OSError:
            pass

        metaData = {
            "type": "file",
            "file_name": os.path.basename(normalized_path),
            "file_size": len(payload),
            "creation_time": creation_time,
            "path": normalized_path,
            "mime": mime_type or "application/octet-stream",
            "owner_device": ""
        }
        return payload, metaData

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload": self.payload,
            "metadata": self.metaData,
            "timestamp": self.timestamp.isoformat()
        }
