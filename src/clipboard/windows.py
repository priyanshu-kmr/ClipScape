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


class WindowsClipboard(ClipboardItem):
    def _get_cbi(self):
        payload = b""
        metaData = {}

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
            if opened and wc.IsClipboardFormatAvailable(win32con.CF_HDROP):
                try:
                    files = wc.GetClipboardData(win32con.CF_HDROP)
                except Exception:
                    files = []

                if isinstance(files, str):
                    files = [files]

                valid_files: List[Tuple[bytes, Dict[str, Any]]] = []
                for path in files or []:
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
                            "file_names": [meta["file_name"] if meta.get("type") != "folder" else meta.get("folder_name") for _, meta in valid_files],
                            "paths": [meta["path"] for _, meta in valid_files],
                            "owner_device": ""
                        }
                        return b"", combined_meta

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
                        "file_names": [meta["file_name"] if meta.get("type") != "folder" else meta.get("folder_name") for _, meta in valid_files],
                        "paths": [meta["path"] for _, meta in valid_files],
                        "owner_device": ""
                    }
                    return b"", combined_meta
            return None

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
                "file_name": str(ulid.new()) + ".png",
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
        if not os.path.exists(normalized_path):
            return None

        if os.path.isdir(normalized_path):
            return self._build_folder_item(normalized_path)

        if not os.path.isfile(normalized_path):
            return None

        mime_type, _ = mimetypes.guess_type(normalized_path)

        file_size = 0
        try:
            file_size = os.path.getsize(normalized_path)
        except OSError:
            pass

        MAX_FILE_SIZE = 100 * 1024 * 1024
        if file_size > MAX_FILE_SIZE:
            payload = b""
        else:
            try:
                with open(normalized_path, "rb") as f:
                    payload = f.read()
            except OSError:
                payload = b""

        creation_time = None
        try:
            creation_dt = datetime.datetime.fromtimestamp(
                os.path.getctime(normalized_path))
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

    def _build_folder_item(self, folder_path: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        import json
        import zipfile
        from io import BytesIO

        try:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, folder_path)
                        try:
                            zip_file.write(file_path, arcname)
                        except Exception:
                            pass

            payload = zip_buffer.getvalue()

            creation_time = None
            try:
                creation_dt = datetime.datetime.fromtimestamp(
                    os.path.getctime(folder_path))
                creation_time = creation_dt.isoformat()
            except OSError:
                pass

            metaData = {
                "type": "folder",
                "folder_name": os.path.basename(folder_path),
                "file_size": len(payload),
                "creation_time": creation_time,
                "path": folder_path,
                "mime": "application/zip",
                "owner_device": ""
            }
            return payload, metaData
        except Exception:
            return None

    def _set_clipboard(self, payload: bytes, metadata: Dict[str, Any]) -> bool:
        clip_type = metadata.get("type", "text")

        opened = False
        try:
            for _ in range(3):
                try:
                    wc.OpenClipboard()
                    opened = True
                    break
                except Exception:
                    time.sleep(0.05)

            if not opened:
                return False

            wc.EmptyClipboard()

            if clip_type == "text":
                text = payload.decode("utf-8", errors="ignore")
                wc.SetClipboardData(wc.CF_UNICODETEXT, text)
                return True

            elif clip_type == "image":
                from PIL import Image
                try:
                    image = Image.open(io.BytesIO(payload))

                    if image.mode not in ("RGB", "RGBA"):
                        image = image.convert("RGB")
                    elif image.mode == "RGBA":
                        background = Image.new(
                            "RGB", image.size, (255, 255, 255))
                        background.paste(image, mask=image.split()[3])
                        image = background

                    output = io.BytesIO()
                    image.save(output, "BMP")
                    bmp_data = output.getvalue()

                    if len(bmp_data) > 14:
                        dib_data = bmp_data[14:]
                        wc.SetClipboardData(win32con.CF_DIB, dib_data)
                        return True
                    return False
                except Exception:
                    return False

            elif clip_type == "file":
                from pathlib import Path
                from utils.file_manager import FileManager

                file_manager = FileManager()
                file_path = file_manager.save_file(payload, metadata)

                if file_path and file_path.exists():
                    try:
                        wc.SetClipboardData(
                            win32con.CF_HDROP, [str(file_path)])
                        return True
                    except Exception:
                        return False
                return False

            elif clip_type == "folder":
                from pathlib import Path
                from utils.file_manager import FileManager
                import zipfile
                import tempfile

                file_manager = FileManager()
                folder_name = metadata.get("folder_name", "folder")

                temp_dir = Path(tempfile.gettempdir()) / \
                    ".clipscape_temp" / folder_name
                temp_dir.mkdir(parents=True, exist_ok=True)

                try:
                    zip_bytes = io.BytesIO(payload)
                    with zipfile.ZipFile(zip_bytes, 'r') as zip_file:
                        zip_file.extractall(temp_dir)

                    wc.SetClipboardData(win32con.CF_HDROP, [str(temp_dir)])
                    return True
                except Exception:
                    return False

            elif clip_type == "file_group":
                from pathlib import Path
                from utils.file_manager import FileManager

                file_manager = FileManager()
                file_names = metadata.get("file_names", [])

                saved_paths = []
                for file_name in file_names:
                    file_meta = {"file_name": file_name}
                    file_path = file_manager.save_file(b"", file_meta)
                    if file_path and file_path.exists():
                        saved_paths.append(str(file_path))

                if saved_paths:
                    try:
                        wc.SetClipboardData(win32con.CF_HDROP, saved_paths)
                        return True
                    except Exception:
                        return False
                return False

            return False

        except Exception:
            return False
        finally:
            if opened:
                try:
                    wc.CloseClipboard()
                except Exception:
                    pass
