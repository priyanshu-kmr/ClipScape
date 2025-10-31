import datetime
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import ulid

try:
    from AppKit import NSPasteboard, NSPasteboardTypeString, NSPasteboardTypePNG, NSPasteboardTypeTIFF, NSPasteboardTypeFileURL
    from Foundation import NSURL
    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False

from clipboard.base import ClipboardItem


class MacOSClipboard(ClipboardItem):

    def _get_cbi(self) -> Tuple[bytes, Dict[str, Any]]:
        if not HAS_APPKIT:
            return b"", {"type": "text", "length": 0, "owner_device": ""}

        pasteboard = NSPasteboard.generalPasteboard()

        if NSPasteboardTypeFileURL in pasteboard.types():
            result = self._get_files(pasteboard)
            if result:
                return result

        if NSPasteboardTypePNG in pasteboard.types():
            result = self._get_image(
                pasteboard, NSPasteboardTypePNG, "image/png", ".png")
            if result:
                return result

        if NSPasteboardTypeTIFF in pasteboard.types():
            result = self._get_image(
                pasteboard, NSPasteboardTypeTIFF, "image/tiff", ".tiff")
            if result:
                return result

        if NSPasteboardTypeString in pasteboard.types():
            result = self._get_text(pasteboard)
            if result:
                return result

        return b"", {"type": "text", "length": 0, "owner_device": ""}

    def _get_text(self, pasteboard) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        try:
            text = pasteboard.stringForType_(NSPasteboardTypeString)
            if text:
                payload = text.encode("utf-8")
                metadata = {
                    "type": "text",
                    "length": len(text),
                    "owner_device": ""
                }
                return payload, metadata
        except Exception:
            pass
        return None

    def _get_image(self, pasteboard, pb_type: str, mime_type: str, extension: str) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        try:
            data = pasteboard.dataForType_(pb_type)
            if data:
                payload = bytes(data)
                creation_time = datetime.datetime.now()
                file_name = f"{ulid.new()}{extension}"

                metadata = {
                    "type": "image",
                    "file_name": file_name,
                    "file_size": len(payload),
                    "creation_time": creation_time.isoformat(),
                    "mime": mime_type,
                    "owner_device": ""
                }
                return payload, metadata
        except Exception:
            pass
        return None

    def _get_files(self, pasteboard) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        try:
            file_urls = pasteboard.readObjectsForClasses_options_([
                                                                  NSURL], None)

            if not file_urls:
                return None

            files_data = []
            for url in file_urls:
                if url.isFileURL():
                    path = Path(url.path())
                    if path.exists():
                        file_item = self._build_file_item(path)
                        if file_item:
                            files_data.append(file_item)

            if not files_data:
                return None

            if len(files_data) == 1:
                return files_data[0]

            combined_meta = {
                "type": "file_group",
                "count": len(files_data),
                "file_names": [meta["file_name"] if meta.get("type") != "folder" else meta.get("folder_name") for _, meta in files_data],
                "paths": [meta["path"] for _, meta in files_data],
                "owner_device": ""
            }
            return b"", combined_meta

        except Exception:
            pass
        return None

    def _build_file_item(self, path: Path) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        try:
            if path.is_dir():
                return self._build_folder_item(path)

            MAX_FILE_SIZE = 100 * 1024 * 1024
            file_size = path.stat().st_size if path.exists() else 0

            if file_size > MAX_FILE_SIZE:
                payload = b""
            else:
                payload = path.read_bytes()

            mime_type, _ = mimetypes.guess_type(str(path))

            creation_time = None
            try:
                creation_time = datetime.datetime.fromtimestamp(
                    path.stat().st_birthtime).isoformat()
            except (OSError, AttributeError):
                try:
                    creation_time = datetime.datetime.fromtimestamp(
                        path.stat().st_ctime).isoformat()
                except OSError:
                    pass

            metadata = {
                "type": "file",
                "file_name": path.name,
                "file_size": len(payload),
                "creation_time": creation_time,
                "path": str(path),
                "mime": mime_type or "application/octet-stream",
                "owner_device": ""
            }
            return payload, metadata
        except Exception:
            return None

    def _build_folder_item(self, folder_path: Path) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        import zipfile
        from io import BytesIO

        try:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for file_path in folder_path.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(folder_path)
                        try:
                            zip_file.write(file_path, arcname)
                        except Exception:
                            pass

            payload = zip_buffer.getvalue()

            creation_time = None
            try:
                creation_time = datetime.datetime.fromtimestamp(
                    folder_path.stat().st_birthtime).isoformat()
            except (OSError, AttributeError):
                try:
                    creation_time = datetime.datetime.fromtimestamp(
                        folder_path.stat().st_ctime).isoformat()
                except OSError:
                    pass

            metadata = {
                "type": "folder",
                "folder_name": folder_path.name,
                "file_size": len(payload),
                "creation_time": creation_time,
                "path": str(folder_path),
                "mime": "application/zip",
                "owner_device": ""
            }
            return payload, metadata
        except Exception:
            return None

    def _set_clipboard(self, payload: bytes, metadata: Dict[str, Any]) -> bool:
        if not HAS_APPKIT:
            return False

        clip_type = metadata.get("type", "text")

        try:
            pasteboard = NSPasteboard.generalPasteboard()
            pasteboard.clearContents()

            if clip_type == "text":
                text = payload.decode("utf-8", errors="ignore")
                pasteboard.setString_forType_(text, NSPasteboardTypeString)
                return True

            elif clip_type == "image":
                from Foundation import NSData
                mime = metadata.get("mime", "image/png")
                ns_data = NSData.dataWithBytes_length_(payload, len(payload))

                if "png" in mime.lower():
                    pasteboard.setData_forType_(ns_data, NSPasteboardTypePNG)
                elif "tiff" in mime.lower() or "tif" in mime.lower():
                    pasteboard.setData_forType_(ns_data, NSPasteboardTypeTIFF)
                else:
                    pasteboard.setData_forType_(ns_data, NSPasteboardTypePNG)

                return True

            elif clip_type == "file":
                from utils.file_manager import FileManager

                file_manager = FileManager()
                file_path = file_manager.save_file(payload, metadata)

                if file_path and file_path.exists():
                    try:
                        file_url = NSURL.fileURLWithPath_(str(file_path))
                        pasteboard.writeObjects_([file_url])
                        return True
                    except Exception:
                        return False
                return False

            elif clip_type == "folder":
                from utils.file_manager import FileManager
                import zipfile
                import tempfile

                folder_name = metadata.get("folder_name", "folder")

                temp_dir = Path(tempfile.gettempdir()) / \
                    ".clipscape_temp" / folder_name
                temp_dir.mkdir(parents=True, exist_ok=True)

                try:
                    from io import BytesIO
                    zip_bytes = BytesIO(payload)
                    with zipfile.ZipFile(zip_bytes, 'r') as zip_file:
                        zip_file.extractall(temp_dir)

                    file_url = NSURL.fileURLWithPath_(str(temp_dir))
                    pasteboard.writeObjects_([file_url])
                    return True
                except Exception:
                    return False

            elif clip_type == "file_group":
                from utils.file_manager import FileManager

                file_manager = FileManager()
                file_names = metadata.get("file_names", [])

                file_urls = []
                for file_name in file_names:
                    file_meta = {"file_name": file_name}
                    file_path = file_manager.save_file(b"", file_meta)
                    if file_path and file_path.exists():
                        file_url = NSURL.fileURLWithPath_(str(file_path))
                        file_urls.append(file_url)

                if file_urls:
                    try:
                        pasteboard.writeObjects_(file_urls)
                        return True
                    except Exception:
                        return False
                return False

            return False

        except Exception:
            return False
