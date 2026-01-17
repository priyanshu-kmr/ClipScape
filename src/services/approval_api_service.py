"""Local HTTP API exposing the pending-clip approval queue to the UI.

Runs FastAPI/uvicorn on its own daemon thread with its own asyncio event loop,
mirroring PeerNetworkService's background-thread pattern -- this process's main
loop is ClipScapeApp.run_forever's blocking time.sleep loop, not asyncio, so
uvicorn needs a loop of its own.
"""

import asyncio
import logging
import threading
from contextlib import asynccontextmanager
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.sync import ClipboardSync
from core.pending import summarize_for_ui
from services.pending_queue import PendingClip, PendingClipQueue

logger = logging.getLogger(__name__)


class ApprovalApiService:

    def __init__(
        self,
        pending_queue: PendingClipQueue,
        sync: ClipboardSync,
        *,
        host: str = "127.0.0.1",
        port: int = 8787,
        cors_origins: Optional[List[str]] = None,
        auto_start: bool = False,
    ) -> None:
        self._queue = pending_queue
        self._sync = sync
        self.host = host
        self.port = port
        self.cors_origins = cors_origins or ["http://localhost:3000"]

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

        if auto_start:
            self.start()

    def build_app(self) -> FastAPI:
        ready = self._ready

        @asynccontextmanager
        async def lifespan(_: FastAPI):
            ready.set()
            yield

        app = FastAPI(lifespan=lifespan)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

        @app.get("/pending")
        def list_pending():
            return {"items": [self._to_json(p) for p in self._queue.list_pending()]}

        @app.post("/pending/{clip_id}/approve")
        def approve_clip(clip_id: str):
            if not self._sync.approve(clip_id):
                raise HTTPException(status_code=404, detail="not found")
            return {"status": "approved", "id": clip_id}

        @app.post("/pending/{clip_id}/reject")
        def reject_clip(clip_id: str):
            if not self._sync.reject(clip_id):
                raise HTTPException(status_code=404, detail="not found")
            return {"status": "rejected", "id": clip_id}

        return app

    def _to_json(self, pending: PendingClip) -> dict:
        captured = pending.captured
        clip_type = captured.metadata.get("type", "unknown")
        summary = summarize_for_ui(clip_type, captured.payload, captured.metadata)
        return {
            "id": pending.id,
            "type": clip_type,
            "timestamp": captured.timestamp,
            "preview": summary["preview"],
            "size_bytes": summary["size_bytes"],
            "metadata": captured.metadata,
        }

    def start(self) -> None:
        if self._thread:
            return

        self._ready.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        config = uvicorn.Config(
            self.build_app(),
            host=self.host,
            port=self.port,
            loop="asyncio",
            log_level="warning",
        )
        self._server = uvicorn.Server(config)

        try:
            self._loop.run_until_complete(self._server.serve())
        except Exception as e:
            logger.error(f"Approval API service error: {e}")
            self._ready.set()
        finally:
            self._loop.close()
            self._loop = None

    def wait_until_ready(self, timeout: float = 10.0) -> bool:
        return self._ready.wait(timeout=timeout)

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True

        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

        self._ready.clear()
