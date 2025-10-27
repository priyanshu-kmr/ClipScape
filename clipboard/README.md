# Platforms Module

This module provides cross-platform clipboard management with a unified interface.

## Architecture

The module uses the **Abstract Factory Pattern** to support multiple operating systems:

```
platforms/
├── __init__.py          # Package exports
├── base.py              # Abstract base class
├── factory.py           # Platform detection and factory
├── windows.py           # Windows implementation
├── linux.py             # Linux implementation (TODO)
└── README.md            # This file
```

## Core Classes

### `ClipboardItem` (Abstract Base Class)

The base class that all platform-specific implementations must inherit from.

**Attributes:**
- `payload: bytes` - The clipboard content as bytes
- `metaData: Dict[str, Any]` - Metadata about the clipboard item
- `timestamp: datetime` - When the clipboard was captured

**Methods:**
- `_get_cbi() -> Tuple[bytes, Dict[str, Any]]` - Abstract method to get clipboard content
- `to_dict() -> Dict[str, Any]` - Convert to dictionary format

### Platform Implementations

#### `CBI_Windows` (Windows)
✅ **Fully Implemented**

Supports:
- Text clipboard (CF_UNICODETEXT)
- Images (via PIL ImageGrab)
- Files (CF_HDROP)

Metadata includes:
- `type`: 'text', 'image', or 'file'
- `file_name`, `file_size`, `mime_type` (for files/images)
- `length` (for text)
- `creation_time`, `path` (for files)

#### `CBI_Linux` (Linux)
⚠️ **Stub Implementation**

TODO: Implement support for:
- X11 clipboard (using xclip/xsel)
- Wayland clipboard (using wl-clipboard)
- Text, images, and files

#### `CBI_macOS` (macOS)
❌ **Not Yet Implemented**

TODO: Implement using:
- `pasteboard` module or
- PyObjC bindings to NSPasteboard

## Usage

### Simple Usage (Recommended)

```python
from platforms import get_clipboard_item

# Automatically detects platform and returns appropriate instance
clipboard = get_clipboard_item()

print(f"Type: {clipboard.metaData['type']}")
print(f"Payload size: {len(clipboard.payload)} bytes")
print(f"Timestamp: {clipboard.timestamp}")
```

### Advanced Usage

```python
from platforms import get_clipboard_class

# Get the class for current platform
ClipboardClass = get_clipboard_class()

# Create multiple instances
clip1 = ClipboardClass()
# ... user copies something else ...
clip2 = ClipboardClass()

# Compare clipboard changes
if clip1.payload != clip2.payload:
    print("Clipboard changed!")
```

### Platform-Specific Usage

```python
from platforms.windows import CBI_Windows

# Directly use Windows implementation
clipboard = CBI_Windows()
```

## Adding New Platforms

To add support for a new platform:

1. **Create implementation file** (e.g., `macos.py`):
```python
from platforms.base import ClipboardItem

class CBI_macOS(ClipboardItem):
    def _get_cbi(self):
        # Implement clipboard reading
        payload = b""
        metaData = {}
        # ... your implementation ...
        return payload, metaData
```

2. **Update factory.py**:
```python
def get_clipboard_class():
    system = platform.system()
    
    if system == "Darwin":  # macOS
        from platforms.macos import CBI_macOS
        return CBI_macOS
    # ... existing code ...
```

3. **Test your implementation**:
```python
# Test all clipboard types
clipboard = get_clipboard_item()
assert clipboard.payload is not None
assert 'type' in clipboard.metaData
```

## Metadata Standards

All implementations should follow these metadata conventions:

### Text Clipboard
```python
{
    "type": "text",
    "length": int,  # Character count
    "owner_device": str  # Device identifier
}
```

### Image Clipboard
```python
{
    "type": "image",
    "file_name": str,  # Generated filename
    "file_size": int,  # Bytes
    "creation_time": str,  # ISO format
    "mime": str,  # e.g., "image/png"
    "owner_device": str
}
```

### File Clipboard
```python
{
    "type": "file",
    "file_name": str,
    "file_size": int,  # Bytes, or None if unreadable
    "creation_time": str,  # ISO format
    "path": str,  # Original file path
    "mime": str,  # MIME type
    "owner_device": str
}
```

## Error Handling

All implementations should:
- Return empty payload `b""` on errors
- Return minimal metadata `{"type": "text", "owner_device": ""}` on errors
- Never raise exceptions from `_get_cbi()` (catch and handle internally)
- Log errors for debugging (optional)

## Testing

```python
# Example test structure
import unittest
from platforms import get_clipboard_item, get_clipboard_class

class TestClipboard(unittest.TestCase):
    def test_factory_returns_instance(self):
        clipboard = get_clipboard_item()
        self.assertIsNotNone(clipboard)
        self.assertIsInstance(clipboard.payload, bytes)
    
    def test_metadata_has_type(self):
        clipboard = get_clipboard_item()
        self.assertIn('type', clipboard.metaData)
    
    def test_to_dict(self):
        clipboard = get_clipboard_item()
        data = clipboard.to_dict()
        self.assertIn('payload', data)
        self.assertIn('metadata', data)
        self.assertIn('timestamp', data)
```

## Dependencies

### Windows
- `pywin32` - Windows clipboard access
- `Pillow` - Image handling
- `ulid-py` - Unique identifiers

### Linux (Planned)
- `subprocess` - For xclip/xsel
- Or `PyQt5`/`PyGTK` - For native clipboard APIs

### macOS (Planned)
- `pyobjc` - NSPasteboard bindings
- Or `pasteboard` - Pure Python wrapper

## License

Part of the ClipScape project.
