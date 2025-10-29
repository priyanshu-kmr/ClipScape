from typing import TypedDict, Optional, List, Dict, Union
from datetime import datetime
from pydantic import BaseModel, Field
from ulid import ULID
from clipboard.windows import get_platform
import database.redis as redis

class CreateUser(BaseModel):
    userId: str = Field(default_factory=lambda: str(ULID.from_datetime(datetime.now())))
    username: str
    email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now())

class Login(BaseModel):
    userId: str = Field(default_factory=lambda: str(ULID.from_datetime(datetime.now())))
    username: str
    email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now())

class Device(BaseModel):
    deviceId: str = Field(default_factory=lambda: f"d_{ULID.from_datetime(datetime.now())}")
    userId: str
    deviceName: str
    deviceType: str = Field(default_factory=lambda: f"{get_platform()}")
    lastSeen: datetime = Field(default_factory=lambda: datetime.now())

class Shared(BaseModel):
    itemId: str
    userId: str
    targetId: str # will change. can be a specifc device or network


    

class ClipboardLog(BaseModel):
    itemId: str = Field(default_factory=lambda: f"i_{ULID.from_datetime(datetime.now())}")
    deviceId: str
    userId: str
    content: bytes  
    mime: str
    metadata: str
    creation: datetime = Field(default_factory=lambda: datetime.now())
    ttl: Optional[datetime] = None
    status: int  # 0: in redis with persistent storage, 1: in redis no persistent, 2: removed from redis


# ----------redis schema----------

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
