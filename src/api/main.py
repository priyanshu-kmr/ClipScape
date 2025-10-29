from fastapi import APIRouter, UploadFile, File
from database.redis_manager import RedisManager
import uvicorn

router = APIRouter("clip")

@router.post("/upload")
def test():
    pass