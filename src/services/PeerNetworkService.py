"""Peer-to-peer network service for ClipScape.

This module provides a thin synchronous wrapper around ``network.ClipScapeNetwork``
so that other services can start discovery, manage peer connections, and
exchange messages without dealing with ``asyncio`` plumbing.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future
from typing import Callable, Optional, Sequence

from network import ClipScapeNetwork, ClipScapePeer

logger = logging.getLogger(__name__)


class PeerNetworkService:
    """High level service that manages ClipScape peer discovery and messaging."""

    def __init__(
        self,
        *,
        signaling_port: Optional[int] = None,
        device_name: Optional[str] = None,
        discovery_interval: float = 5.0,
        discovery_timeout: float = 2.0,
        on_peer_connected: Optional[Callable[[ClipScapePeer], None]] = None,
        on_peer_disconnected: Optional[Callable[[str], None]] = None,
        on_message: Optional[Callable[[str, str], None]] = None,
        auto_start: bool = False,
        network: Optional[ClipScapeNetwork] = None,
    ) -> None:
        self.discovery_interval = max(0.5, discovery_interval)
        self.discovery_timeout = max(0.5, discovery_timeout)

        if network is not None:
            self._network: ClipScapeNetwork = network
        else:
            network_kwargs = {}
            if signaling_port is not None:
                network_kwargs["signaling_port"] = signaling_port
            if device_name is not None:
                network_kwargs["device_name"] = device_name
            self._network = ClipScapeNetwork(**network_kwargs)

        self._on_peer_connected = on_peer_connected
        self._on_peer_disconnected = on_peer_disconnected
        self._on_message = on_message

        self._network.on_peer_connected(self._handle_peer_connected)
        self._network.on_peer_disconnected(self._handle_peer_disconnected)
        self._network.on_message(self._handle_message)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._server_task: Optional[asyncio.Task] = None
        self._discovery_task: Optional[asyncio.Task] = None
        self._stop_flag = threading.Event()
        self._started = threading.Event()
        self._lock = threading.RLock()

        if auto_start:
            self.start()

    # ------------------------------------------------------------------
    # Lifecycle management
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start the network service in a background event loop."""

        startup_failed = False
        startup_error: Optional[BaseException] = None

        with self._lock:
            if self.is_running:
                logger.debug("PeerNetworkService already running")
                return

            logger.info("Starting PeerNetworkService (port=%s)", self._network.signaling_port)

            self._stop_flag.clear()
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(
                target=self._run_loop,
                args=(self._loop,),
                daemon=True,
                name="clipscape-network-loop",
            )
            self._loop_thread.start()

            future = self._submit_coroutine(self._async_start())
            try:
                future.result(timeout=10.0)
            except Exception as exc:
                logger.exception("Failed to start PeerNetworkService")
                startup_failed = True
                startup_error = exc

        if startup_failed:
            self.stop()
            if startup_error is not None:
                raise startup_error
            raise RuntimeError("PeerNetworkService failed to start")

    def stop(self) -> None:
        """Stop the network service and tear down background tasks."""

        with self._lock:
            if not self.is_running:
                return

            logger.info("Stopping PeerNetworkService")
            self._stop_flag.set()

            future = self._submit_coroutine(self._async_stop())
            try:
                future.result(timeout=10.0)
            except Exception:
                logger.exception("Error while stopping PeerNetworkService")

            if self._loop:
                self._loop.call_soon_threadsafe(self._loop.stop)

        if self._loop_thread:
            self._loop_thread.join(timeout=2.0)

        self._loop = None
        self._loop_thread = None
        self._started.clear()

    def __enter__(self) -> "PeerNetworkService":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    @property
    def is_running(self) -> bool:
        return bool(self._loop and self._loop_thread and self._loop_thread.is_alive())

    @property
    def network(self) -> ClipScapeNetwork:
        """Return the backing ``ClipScapeNetwork`` instance."""

        return self._network

    def wait_until_ready(self, timeout: Optional[float] = None) -> bool:
        """Block until the service has initialised or ``timeout`` expires."""

        return self._started.wait(timeout=timeout)

    def broadcast_message(self, message: str) -> int:
        """Broadcast a text message to all connected peers."""

        return self._run_sync(self._network.broadcast_message, message)

    def broadcast_json(self, payload: dict) -> int:
        """Broadcast structured data to all connected peers."""

        return self._run_sync(self._network.broadcast_json, payload)

    def send_to_peer(self, peer_id: str, message: str) -> bool:
        """Send a message to a specific peer by identifier."""

        return self._run_sync(self._network.send_to_peer, peer_id, message)

    def send_json_to_peer(self, peer_id: str, payload: dict) -> bool:
        """Send structured data to a specific peer."""

        def _delegate() -> bool:
            peer = self._network.peers.get(peer_id)
            return peer.send_json(payload) if peer else False

        return self._run_sync(_delegate)

    def connected_peers(self) -> Sequence[ClipScapePeer]:
        """Return a snapshot of all currently connected peers."""

        peers = self._run_sync(self._network.get_connected_peers)
        return tuple(peers)

    def discover_now(self, timeout: Optional[float] = None) -> None:
        """Trigger a manual discovery cycle."""

        coro = self._network.discover_and_connect(timeout=timeout or self.discovery_timeout)
        future = self._submit_coroutine(coro)
        try:
            future.result()
        except Exception:
            logger.exception("Manual peer discovery failed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _run_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop=loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    async def _async_start(self) -> None:
        self._server_task = await self._network.start()
        try:
            await self._network.discover_and_connect(timeout=self.discovery_timeout)
        except Exception:
            logger.exception("Initial peer discovery failed")
        self._discovery_task = asyncio.create_task(self._discovery_loop(), name="clipscape-peer-discovery")
        self._started.set()

    async def _async_stop(self) -> None:
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
            self._discovery_task = None

        await self._network.stop()

        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
        self._server_task = None

    async def _discovery_loop(self) -> None:
        while not self._stop_flag.is_set():
            try:
                await self._network.discover_and_connect(timeout=self.discovery_timeout)
            except Exception:
                logger.exception("Peer discovery failed")
            await asyncio.sleep(self.discovery_interval)

    def _submit_coroutine(self, coro) -> Future:
        if not self._loop:
            raise RuntimeError("PeerNetworkService is not running")
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _run_sync(self, func, *args, **kwargs):
        async def runner():
            return func(*args, **kwargs)

        return self._submit_coroutine(runner()).result()

    # ------------------------------------------------------------------
    # Callback dispatch
    # ------------------------------------------------------------------
    def _handle_peer_connected(self, peer: ClipScapePeer) -> None:
        if self._on_peer_connected:
            try:
                self._on_peer_connected(peer)
            except Exception:
                logger.exception("Peer connected callback raised")

    def _handle_peer_disconnected(self, peer_id: str) -> None:
        if self._on_peer_disconnected:
            try:
                self._on_peer_disconnected(peer_id)
            except Exception:
                logger.exception("Peer disconnected callback raised")

    def _handle_message(self, peer_id: str, message: str) -> None:
        if self._on_message:
            try:
                self._on_message(peer_id, message)
            except Exception:
                logger.exception("Message callback raised")
