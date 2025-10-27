"""
Platform-specific clipboard factory.

This module provides a factory function to get the appropriate clipboard
implementation for the current platform.
"""

import platform
from typing import Type
from clipboard.base import ClipboardItem


def get_clipboard_class() -> Type[ClipboardItem]:
    """
    Get the appropriate ClipboardItem implementation for the current platform.
    
    Returns:
        Type[ClipboardItem]: The platform-specific ClipboardItem class
        
    Raises:
        NotImplementedError: If the current platform is not supported
    """
    system = platform.system()
    
    if system == "Windows":
        from clipboard.windows import CBI_Windows
        return CBI_Windows
    elif system == "Linux":
        from clipboard.linux import CBI_Linux
        return CBI_Linux
    elif system == "Darwin":  # macOS
        # TODO: Implement macOS support
        raise NotImplementedError(f"macOS clipboard support not yet implemented")
    else:
        raise NotImplementedError(f"Platform '{system}' is not supported")


def get_clipboard_item() -> ClipboardItem:
    """
    Create and return a clipboard item for the current platform.
    
    Returns:
        ClipboardItem: Platform-specific clipboard item instance
        
    Raises:
        NotImplementedError: If the current platform is not supported
    """
    clipboard_class = get_clipboard_class()
    return clipboard_class()
