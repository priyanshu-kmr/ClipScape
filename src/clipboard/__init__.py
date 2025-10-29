"""
Cross-platform clipboard management.

This package provides clipboard access across different operating systems
through a unified interface.
"""

from clipboard.base import ClipboardItem
from clipboard.factory import get_clipboard_class, get_clipboard_item

__all__ = [
    'ClipboardItem',
    'get_clipboard_class',
    'get_clipboard_item',
]
