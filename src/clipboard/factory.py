import platform
from typing import Type
from clipboard.base import ClipboardItem


def get_clipboard_class() -> Type[ClipboardItem]:
    system = platform.system()

    if system == "Windows":
        from clipboard.windows import WindowsClipboard
        return WindowsClipboard
    elif system == "Linux":
        from clipboard.linux import LinuxClipboard
        return LinuxClipboard
    elif system == "Darwin":
        from clipboard.macos import MacOSClipboard
        return MacOSClipboard
    else:
        raise NotImplementedError(f"Platform '{system}' is not supported")


def get_clipboard_item() -> ClipboardItem:
    clipboard_class = get_clipboard_class()
    return clipboard_class()
