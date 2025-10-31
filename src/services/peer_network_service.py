import asyncio
import logging
import threading
import time
from typing import Optional, Callable, Dict, Any
import base64
import json

from network.network import ClipScapeNetwork

logger = logging.getLogger(__name__)


class PeerNetworkService:

    def __init__(
        self,
        signaling_port: int = 9999,
        device_name: Optional[str] = None,
        auto_start: bool = False,
        discovery_interval: float = 30.0
    ):
        self.signaling_port = signaling_port
        self.device_name = device_name
        self.discovery_interval = discovery_interval
        self.network: Optional[ClipScapeNetwork] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._ready = threading.Event()
        self.on_clipboard_received_callback: Optional[Callable[[
            Dict[str, Any]], None]] = None

        if auto_start:
            self.start()

    def start(self):
        if self._running:
            return

        self._running = True
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run_network_loop, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._running:
            return

        self._running = False

        if self._loop and self.network:
            asyncio.run_coroutine_threadsafe(self.network.stop(), self._loop)

        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

        self._ready.clear()

    def _run_network_loop(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._async_network_main())
        except Exception as e:
            logger.error(f"Network loop error: {e}")
        finally:
            if self._loop:
                self._loop.close()
                self._loop = None

    async def _async_network_main(self):
        try:
            self.network = ClipScapeNetwork(
                signaling_port=self.signaling_port,
                device_name=self.device_name
            )

            self.network.on_message(self._handle_peer_message)
            self.network.on_peer_connected(self._handle_peer_connected)
            self.network.on_peer_disconnected(self._handle_peer_disconnected)

            server_task = await self.network.start()
            self._ready.set()

            logger.info("Discovering peers...")
            await self.network.discover_and_connect(timeout=2.0)

            last_discovery = time.time()
            last_health_check = time.time()

            while self._running:
                await asyncio.sleep(1.0)

                if time.time() - last_health_check > 5.0:
                    connected_peers = self.network.get_connected_peers()
                    if not connected_peers and time.time() - last_discovery > 10.0:
                        logger.info("No connected peers, discovering...")
                        await self.network.discover_and_connect(timeout=2.0)
                        last_discovery = time.time()
                    last_health_check = time.time()

                if time.time() - last_discovery > self.discovery_interval:
                    logger.info("Re-discovering peers...")
                    await self.network.discover_and_connect(timeout=2.0)
                    last_discovery = time.time()

            await self.network.stop()

        except Exception as e:
            logger.error(f"Network main error: {e}")
            self._ready.set()

    def _handle_peer_connected(self, peer):
        logger.info(f"Peer connected: {peer.peer_name} ({peer.peer_id})")

    def _handle_peer_disconnected(self, peer_id: str):
        logger.info(f"Peer disconnected: {peer_id}")

    def _handle_peer_message(self, peer_id: str, message: str):
        try:
            data = json.loads(message)

            if data.get("type") in ["clipboard_text", "clipboard_image", "clipboard_file"]:
                if self.on_clipboard_received_callback:
                    self.on_clipboard_received_callback(data)

        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.error(f"Message handling error: {e}")

    def broadcast_clipboard(self, clipboard_data: Dict[str, Any]) -> bool:
        if not self._running or not self.network or not self._loop:
            return False

        try:
            message = self._prepare_clipboard_message(clipboard_data)
            future = asyncio.run_coroutine_threadsafe(
                self._async_broadcast(message),
                self._loop
            )
            count = future.result(timeout=5.0)
            return count > 0

        except Exception as e:
            logger.error(f"Broadcast error: {e}")
            return False

    async def _async_broadcast(self, message: str) -> int:
        if self.network:
            return self.network.broadcast_message(message)
        return 0

    def _prepare_clipboard_message(self, clipboard_data: Dict[str, Any]) -> str:
        metadata = clipboard_data.get("metadata", {})
        payload = clipboard_data.get("payload", b"")
        timestamp = clipboard_data.get("timestamp", "")
        clip_type = metadata.get("type", "text")

        if isinstance(payload, bytes):
            payload_b64 = base64.b64encode(payload).decode("ascii")
        else:
            payload_b64 = base64.b64encode(
                str(payload).encode("utf-8")).decode("ascii")

        message = {
            "type": f"clipboard_{clip_type}",
            "payload": payload_b64,
            "metadata": metadata,
            "timestamp": timestamp
        }

        return json.dumps(message)

    def send_to_peer(self, peer_id: str, message: str) -> bool:
        if not self._running or not self.network or not self._loop:
            return False

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._async_send_to_peer(peer_id, message),
                self._loop
            )
            return future.result(timeout=5.0)
        except Exception as e:
            logger.error(f"Send error: {e}")
            return False

    async def _async_send_to_peer(self, peer_id: str, message: str) -> bool:
        if self.network:
            return self.network.send_to_peer(peer_id, message)
        return False

    def send_json_to_peer(self, peer_id: str, data: dict) -> bool:
        return self.send_to_peer(peer_id, json.dumps(data))

    def discover_now(self):
        if not self._running or not self._loop or not self.network:
            return

        asyncio.run_coroutine_threadsafe(
            self.network.discover_and_connect(timeout=2.0),
            self._loop
        )

    def connected_peers(self):
        if self.network:
            return self.network.get_connected_peers()
        return []

    def wait_until_ready(self, timeout: float = 10.0) -> bool:
        return self._ready.wait(timeout=timeout)

    def on_clipboard_received(self, callback: Callable[[Dict[str, Any]], None]):
        self.on_clipboard_received_callback = callback

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
