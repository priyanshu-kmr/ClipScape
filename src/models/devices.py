from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Devices:
    """Lightweight representation of a device record."""
    platform: Optional[str]
    device_id: str
    ip: str
    
