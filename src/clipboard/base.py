from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any
import datetime


class ClipboardItem(ABC):

    def __init__(self):
        payload, metaData = self._get_cbi()
        self.payload: bytes = payload
        self.metaData: Dict[str, Any] = metaData
        self.timestamp: datetime.datetime = datetime.datetime.now()

    @abstractmethod
    def _get_cbi(self) -> Tuple[bytes, Dict[str, Any]]:
        pass

    @abstractmethod
    def _set_clipboard(self, payload: bytes, metadata: Dict[str, Any]) -> bool:
        pass

    @classmethod
    def set_clipboard(cls, payload: bytes, metadata: Dict[str, Any]) -> bool:
        try:
            instance = cls.__new__(cls)
            return instance._set_clipboard(payload, metadata)
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "payload": self.payload,
            "metadata": self.metaData,
            "timestamp": self.timestamp.isoformat()
        }
