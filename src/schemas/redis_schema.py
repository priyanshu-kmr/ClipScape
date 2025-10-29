
from typing import TypedDict, Optional, List, Dict, Union
from datetime import datetime
from pydantic import BaseModel, Field
from ulid import ULID
from clipboard.windows import get_platform
import database.redis as redis

class Users(BaseModel): # persistent storage
    userId: str
    devices: List[str]
    networks: List[str]
    deviceId: str # current device user is using

class ClipboardItem(BaseModel): # optional by defualt not every item is persistent
    itemId: str = Field(default_factory=lambda: f"i_{ULID.from_datetime(datetime.now())}")
    deviceId: str
    userId: str
    payload: Union[bytes, str]  # str for text
    metadata: Dict[str, str]

class Network(BaseModel): # P2P network. need to decide
    networkId: str
    devices: List[str]
    ...