from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any
import datetime


class ClipboardItem(ABC):
    """
    Abstract base class for clipboard items across different platforms.
    
    Subclasses should implement platform-specific clipboard access logic.
    """
    
    def __init__(self):
        """Initialize clipboard item by fetching current clipboard content."""
        payload, metaData = self._get_cbi()
        self.payload: bytes = payload
        self.metaData: Dict[str, Any] = metaData
        self.timestamp: datetime.datetime = datetime.datetime.now()
    
    @abstractmethod
    def _get_cbi(self) -> Tuple[bytes, Dict[str, Any]]:
        """
        Platform-specific method to get clipboard content.
        
        Returns:
            Tuple[bytes, Dict[str, Any]]: A tuple containing:
                - payload: The clipboard content as bytes
                - metaData: Dictionary containing metadata about the clipboard item
                    - type: 'text', 'image', or 'file'
                    - Additional metadata specific to the type
        """
        pass
    
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

    