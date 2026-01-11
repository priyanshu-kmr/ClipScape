"""Service lifecycle: construct, wire, tear down."""

import logging
import sys
import time
from typing import Optional

from app.config import AppConfig
from app.sync import ClipboardSync
from services.clipboard_service import ClipboardService
from services.clipboard_store import ClipboardStore, cleanup_managed_files
from services.peer_network_service import PeerNetworkService
from services.redis_service import RedisService

logger = logging.getLogger(__name__)


class ClipScapeApp:

    def __init__(self, config: AppConfig):
        self.config = config
        self._use_redis = config.use_redis
        self.clipboard_service: Optional[ClipboardService] = None
        self.network_service: Optional[PeerNetworkService] = None
        self.redis_service: Optional[RedisService] = None
        self.store: Optional[ClipboardStore] = None
        self.sync: Optional[ClipboardSync] = None
        self.user_id: Optional[str] = None
        self.device_id: Optional[str] = None
        self.running = False

    def start(self):
        if self.running:
            return

        print(
            f"Starting ClipScape - Device: {self.config.device_name}, Port: {self.config.port}")

        self.running = True

        try:
            if self._use_redis:
                self._start_redis()

            self.store = ClipboardStore(
                self.redis_service,
                user_id=self.user_id,
                device_id=self.device_id,
            )

            self.network_service = PeerNetworkService(
                signaling_port=self.config.port,
                device_name=self.config.device_name,
                auto_start=True,
                discovery_interval=self.config.discovery_interval
            )

            self.sync = ClipboardSync(
                self.store,
                broadcast=self.network_service.broadcast_clipboard,
            )

            self.network_service.on_clipboard_received(
                self.sync.on_remote_message)

            if not self.network_service.wait_until_ready(timeout=10.0):
                logger.error("Network service failed to start")
                self.stop()
                return

            self.clipboard_service = ClipboardService(
                on_capture=self.sync.on_local_capture,
                auto_register=True
            )
            self.clipboard_service.poll_interval = self.config.poll_interval

            print("ClipScape running. Press Ctrl+C to stop")

        except Exception as e:
            logger.error(f"Error starting: {e}")
            self.stop()

    def _start_redis(self):
        try:
            self.redis_service = RedisService()
            self.user_id = self.redis_service.ensure_user()
            self.device_id = self.redis_service.ensure_device(
                user_id=self.user_id,
                device_name=self.config.device_name,
                platform=sys.platform
            )
            logger.info(
                f"Redis connected - User: {self.user_id}, Device: {self.device_id}")
        except Exception as e:
            logger.warning(
                f"Redis unavailable, continuing without persistence: {e}")
            self._use_redis = False

    def stop(self):
        if not self.running:
            return

        self.running = False

        if self.clipboard_service:
            self.clipboard_service.stop()

        if self.network_service:
            self.network_service.stop()

        if self.redis_service:
            if self.device_id:
                try:
                    logger.info("Clearing device data from Redis...")
                    self.redis_service.manager.delete_device(self.device_id)
                    logger.info("Redis data cleared")
                except Exception as e:
                    logger.warning(f"Could not clear Redis data: {e}")
            self.redis_service.close()

        cleanup_managed_files()

        print("ClipScape stopped")

    def run_forever(self):
        self.start()

        try:
            while self.running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            self.stop()
