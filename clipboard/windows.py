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
from typing import Dict, Any

class CBI_Windows(ClipboardItem):
    """Windows-specific implementation of ClipboardItem."""
    
    def _get_cbi(self):
        payload = b""
        metaData = {}

        image = None
        try:
            image = ImageGrab.grabclipboard()
        except Exception:
            image = None
        if image is not None:
            try:
                if isinstance(image, (list, tuple)) and image:
                    path = image[0]
                    file_name = os.path.basename(path)
                    mime_type, _ = mimetypes.guess_type(path)
                    if os.path.exists(path) and os.path.isfile(path):
                        with open(path, "rb") as f:
                            payload = f.read()
                        file_size = len(payload)
                        creation_time = datetime.datetime.fromtimestamp(os.path.getctime(path)).isoformat()
                    else:
                        payload = b""
                        file_size = None
                        creation_time = None
                    metaData.update({
                        "type": "file",
                        "file_name": file_name,
                        "file_size": file_size,
                        "creation_time": creation_time,
                        "path": path,
                        "mime": mime_type or "",
                        "owner_device": ""
                    })
                    return payload, metaData
                creation_time = datetime.datetime.now()
                output = io.BytesIO()
                if hasattr(image, "save"):
                    image.save(output, format="PNG")
                    payload = output.getvalue()
                    metaData.update({
                        "type": "image",
                        "file_name": str(ulid.ULID.from_datetime(creation_time)) + ".png",
                        "file_size": len(payload),
                        "creation_time": creation_time.isoformat(),
                        "mime": "image/png",
                        "owner_device": ""
                    })
                    return payload, metaData
                else:
                    return b"", {}
            except Exception:
                return b"", {}

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
                files = wc.GetClipboardData(win32con.CF_HDROP)
                path = files[0]
                file_name = os.path.basename(path)
                mime_type, _ = mimetypes.guess_type(path)
                if os.path.exists(path) and os.path.isfile(path):
                    try:
                        with open(path, "rb") as f:
                            content = f.read()
                        file_size = len(content)
                        creation_time = datetime.datetime.fromtimestamp(os.path.getctime(path)).isoformat()
                        payload = content
                    except Exception:
                        payload = b""
                        file_size = os.path.getsize(path) if os.path.exists(path) else None
                        creation_time = datetime.datetime.fromtimestamp(os.path.getctime(path)).isoformat() if os.path.exists(path) else None
                else:
                    payload = b""
                    file_size = None
                    creation_time = None
                metaData.update({
                    "type": "file",
                    "file_name": file_name,
                    "file_size": file_size,
                    "creation_time": creation_time,
                    "path": path,
                    "mime": mime_type or "",
                    "owner_device": ""
                })
                return payload, metaData

            if opened and wc.IsClipboardFormatAvailable(wc.CF_UNICODETEXT):
                text = wc.GetClipboardData(wc.CF_UNICODETEXT)
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
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert clipboard item to dictionary format.
        
        Returns:
            Dict containing payload, metadata, and timestamp
        """
        return {
            "payload": self.payload,
            "metadata": self.metaData,
            "timestamp": self.timestamp.isoformat()
        }

    # def to_redis(self):
    #     return {
    #         "payload": self.payload,
    #         "metadata": self.metaData,
    #         "timestamp": self.timestamp.isoformat()
    #     }


# def print_clipboard_metadata(interval: float = 1.0):
#     try:
#         while True:
#             item = CBI_Windows()
#             print(item.metaData)
#             time.sleep(interval)
#     except KeyboardInterrupt:
#         pass

# if __name__ == "__main__":
#     print_clipboard_metadata()