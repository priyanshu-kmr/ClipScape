#!/usr/bin/env python3

from clipboard import get_clipboard_class
from services.peer_network_service import PeerNetworkService
from services.clipboard_service import ClipboardService, CapturedClipboard
from services.redis_service import RedisService

from fastapi import FastAPI, APIRouter

app = FastAPI()
router = APIRouter()

@router.get("/")
def root():
    return {"status": 200}



app.include_router(router)