from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Union


@dataclass(frozen=True)
class ClipboardItem:
	"""Immutable clipboard item snapshot used across services and persistence."""
	item_id: str
	device_id: str
	payload: Union[bytes, str]
	metadata: Dict[str, Any]
	created_at: datetime
