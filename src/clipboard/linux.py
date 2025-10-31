import datetime
import mimetypes
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse
import ulid

from clipboard.base import ClipboardItem


class LinuxClipboard(ClipboardItem):
    _FILE_TARGETS = {"x-special/gnome-copied-files", "text/uri-list"}
    _IMAGE_TARGETS = {
        "image/png": "image/png",
        "image/jpeg": "image/jpeg",
        "image/jpg": "image/jpeg",
        "image/pjpeg": "image/jpeg",
        "image/bmp": "image/bmp",
        "image/x-ms-bmp": "image/bmp",
        "image/webp": "image/webp",
    }
    _TEXT_TARGETS = {
        "text/plain",
        "text/plain;charset=utf-8",
        "text/plain;charset=utf8",
        "utf8_string",
        "string",
    }

    def _get_cbi(self) -> Tuple[bytes, Dict[str, Any]]:
        strategies = (
            self._from_wayland,
            self._from_xclip,
        )

        for strategy in strategies:
            try:
                result = strategy()
            except Exception:
                result = None
            if result:
                return result

        text_fallback = self._build_text_item(b"")
        if text_fallback:
            return text_fallback
        return b"", {"type": "text", "length": 0, "owner_device": ""}

    def _from_wayland(self) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        if not os.environ.get("WAYLAND_DISPLAY") or not shutil.which("wl-paste"):
            return None

        types = self._parse_type_list(
            self._run_command(["wl-paste", "--list-types"], timeout=1.5)
        )

        def reader(target: str) -> Optional[bytes]:
            command = ["wl-paste", "--type", target]
            if target.lower().startswith("text/"):
                command.append("--no-newline")
            return self._run_command(command, timeout=1.5)

        result = self._extract_from_types(types, reader)
        if result:
            return result

        text_bytes = self._run_command(
            ["wl-paste", "--no-newline"], timeout=1.5)
        if text_bytes:
            return self._build_text_item(text_bytes)

        return None

    def _from_xclip(self) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        if not shutil.which("xclip"):
            return None

        types = self._parse_type_list(
            self._run_command(
                ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                timeout=1.5,
            )
        )

        def reader(target: str) -> Optional[bytes]:
            return self._run_command(
                ["xclip", "-selection", "clipboard", "-t", target, "-o"],
                timeout=1.5,
            )

        result = self._extract_from_types(types, reader)
        if result:
            return result

        text_bytes = self._run_command(
            ["xclip", "-selection", "clipboard", "-o"],
            timeout=1.5,
        )
        if text_bytes:
            return self._build_text_item(text_bytes)

        return None

    def _extract_from_types(
        self,
        types: List[str],
        reader: Callable[[str], Optional[bytes]],
    ) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        if not types:
            return None

        for target in types:
            target_lower = target.lower()
            if target_lower in self._FILE_TARGETS:
                data = reader(target)
                if data:
                    file_item = self._build_file_item(data)
                    if file_item:
                        return file_item

        for target in types:
            target_lower = target.lower()
            if target_lower in self._IMAGE_TARGETS:
                data = reader(target)
                if data:
                    image_item = self._build_image_item(
                        data, self._IMAGE_TARGETS[target_lower]
                    )
                    if image_item:
                        return image_item

        for target in types:
            target_lower = target.lower()
            if target_lower in self._TEXT_TARGETS:
                data = reader(target)
                if data:
                    text_item = self._build_text_item(data)
                    if text_item:
                        return text_item

        return None

    def _build_file_item(self, data: bytes) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        for path in self._parse_paths(data):
            if not path.exists():
                continue

            if path.is_dir():
                return self._build_folder_item(path)

            if not path.is_file():
                continue

            MAX_FILE_SIZE = 100 * 1024 * 1024
            try:
                file_size = path.stat().st_size
                if file_size > MAX_FILE_SIZE:
                    payload = b""
                else:
                    payload = path.read_bytes()
            except OSError:
                payload = b""
                file_size = 0

            try:
                creation_time = datetime.datetime.fromtimestamp(
                    path.stat().st_ctime
                ).isoformat()
            except OSError:
                creation_time = None

            mime_type, _ = mimetypes.guess_type(str(path))

            metaData = {
                "type": "file",
                "file_name": path.name,
                "file_size": file_size,
                "creation_time": creation_time,
                "path": str(path),
                "mime": mime_type or "",
                "owner_device": "",
            }
            return payload, metaData

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

            try:
                creation_time = datetime.datetime.fromtimestamp(
                    folder_path.stat().st_ctime
                ).isoformat()
            except OSError:
                creation_time = None

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

    def _build_image_item(
        self, payload: bytes, mime_type: str
    ) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        if not payload:
            return None

        creation_time = datetime.datetime.now()
        extension = mimetypes.guess_extension(mime_type) or ""
        if extension in {".jpe", ""}:
            extension = ".jpeg" if mime_type == "image/jpeg" else ".bin"
        identifier = str(ulid.new()) if ulid is not None else uuid.uuid4().hex
        file_name = f"{identifier}{extension}"

        metaData = {
            "type": "image",
            "file_name": file_name,
            "file_size": len(payload),
            "creation_time": creation_time.isoformat(),
            "mime": mime_type,
            "owner_device": "",
        }

        return payload, metaData

    def _build_text_item(self, payload: Optional[bytes]) -> Optional[Tuple[bytes, Dict[str, Any]]]:
        if not payload:
            text = ""
        else:
            text = payload.decode("utf-8", errors="ignore")

        metaData = {
            "type": "text",
            "length": len(text),
            "owner_device": "",
        }

        return text.encode("utf-8"), metaData

    def _parse_type_list(self, data: Optional[bytes]) -> List[str]:
        if not data:
            return []
        text = data.decode("utf-8", errors="ignore")
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _parse_paths(self, data: bytes) -> List[Path]:
        text = data.decode("utf-8", errors="ignore")
        lines = [line.strip() for line in text.replace(
            "\r", "\n").split("\n") if line.strip()]
        if lines and lines[0].lower() in {"copy", "cut"}:
            lines = lines[1:]

        paths: List[Path] = []
        for entry in lines:
            parsed = urlparse(entry)
            if parsed.scheme == "file":
                candidate = Path(unquote(parsed.path))
            else:
                candidate = Path(unquote(entry))

            paths.append(candidate)

        return paths

    def _run_command(self, command: List[str], timeout: float) -> Optional[bytes]:
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=timeout,
            )
            return result.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def _set_clipboard(self, payload: bytes, metadata: Dict[str, Any]) -> bool:
        clip_type = metadata.get("type", "text")

        try:
            if shutil.which("wl-copy"):
                if clip_type == "text":
                    text = payload.decode("utf-8", errors="ignore")
                    subprocess.run(
                        ["wl-copy"],
                        input=text.encode("utf-8"),
                        check=True,
                        timeout=2.0
                    )
                    return True
                elif clip_type == "image":
                    mime = metadata.get("mime", "image/png")
                    subprocess.run(
                        ["wl-copy", "--type", mime],
                        input=payload,
                        check=True,
                        timeout=2.0
                    )
                    return True
                elif clip_type == "file":
                    from utils.file_manager import FileManager

                    file_manager = FileManager()
                    file_path = file_manager.save_file(payload, metadata)

                    if file_path and file_path.exists():
                        uri = file_path.as_uri()
                        subprocess.run(
                            ["wl-copy", "--type", "text/uri-list"],
                            input=uri.encode("utf-8"),
                            check=True,
                            timeout=2.0
                        )
                        return True
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

                        uri = temp_dir.as_uri()
                        subprocess.run(
                            ["wl-copy", "--type", "text/uri-list"],
                            input=uri.encode("utf-8"),
                            check=True,
                            timeout=2.0
                        )
                        return True
                    except Exception:
                        return False
                elif clip_type == "file_group":
                    from utils.file_manager import FileManager

                    file_manager = FileManager()
                    file_names = metadata.get("file_names", [])

                    uris = []
                    for file_name in file_names:
                        file_meta = {"file_name": file_name}
                        file_path = file_manager.save_file(b"", file_meta)
                        if file_path and file_path.exists():
                            uris.append(file_path.as_uri())

                    if uris:
                        uri_list = "\n".join(uris)
                        subprocess.run(
                            ["wl-copy", "--type", "text/uri-list"],
                            input=uri_list.encode("utf-8"),
                            check=True,
                            timeout=2.0
                        )
                        return True
                    return False

            elif shutil.which("xclip"):
                if clip_type == "text":
                    text = payload.decode("utf-8", errors="ignore")
                    subprocess.run(
                        ["xclip", "-selection", "clipboard"],
                        input=text.encode("utf-8"),
                        check=True,
                        timeout=2.0
                    )
                    return True
                elif clip_type == "image":
                    mime = metadata.get("mime", "image/png")
                    subprocess.run(
                        ["xclip", "-selection", "clipboard", "-t", mime],
                        input=payload,
                        check=True,
                        timeout=2.0
                    )
                    return True
                elif clip_type == "file":
                    from utils.file_manager import FileManager

                    file_manager = FileManager()
                    file_path = file_manager.save_file(payload, metadata)

                    if file_path and file_path.exists():
                        uri = file_path.as_uri()
                        subprocess.run(
                            ["xclip", "-selection", "clipboard",
                                "-t", "text/uri-list"],
                            input=uri.encode("utf-8"),
                            check=True,
                            timeout=2.0
                        )
                        return True
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

                        uri = temp_dir.as_uri()
                        subprocess.run(
                            ["xclip", "-selection", "clipboard",
                                "-t", "text/uri-list"],
                            input=uri.encode("utf-8"),
                            check=True,
                            timeout=2.0
                        )
                        return True
                    except Exception:
                        return False
                elif clip_type == "file_group":
                    from utils.file_manager import FileManager

                    file_manager = FileManager()
                    file_names = metadata.get("file_names", [])

                    uris = []
                    for file_name in file_names:
                        file_meta = {"file_name": file_name}
                        file_path = file_manager.save_file(b"", file_meta)
                        if file_path and file_path.exists():
                            uris.append(file_path.as_uri())

                    if uris:
                        uri_list = "\n".join(uris)
                        subprocess.run(
                            ["xclip", "-selection", "clipboard",
                                "-t", "text/uri-list"],
                            input=uri_list.encode("utf-8"),
                            check=True,
                            timeout=2.0
                        )
                        return True
                    return False

            return False

        except Exception:
            return False
