#!/usr/bin/env python3

from clipboard import get_clipboard_class
from services.peer_network_service import PeerNetworkService
from services.clipboard_service import ClipboardService, CapturedClipboard
from services.redis_service import RedisService
import argparse
import logging
import os
import signal
import sys
import time
import base64
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ClipScapeApp:

    def __init__(
        self,
        port: int = 9999,
        device_name: Optional[str] = None,
        poll_interval: float = 0.25,
        discovery_interval: float = 30.0,
        use_redis: bool = True
    ):
        self.port = port
        self.device_name = device_name or self._get_default_device_name()
        self.poll_interval = poll_interval
        self.discovery_interval = discovery_interval
        self.use_redis = use_redis
        self.clipboard_service: Optional[ClipboardService] = None
        self.network_service: Optional[PeerNetworkService] = None
        self.redis_service: Optional[RedisService] = None
        self.user_id: Optional[str] = None
        self.device_id: Optional[str] = None
        self._last_sent_hash: Optional[str] = None
        self._setting_clipboard = False
        self.running = False

    def _get_default_device_name(self) -> str:
        import socket
        hostname = socket.gethostname()
        return hostname.split('.')[0]

    def _calculate_hash(self, payload, metadata: dict) -> str:
        import hashlib
        if isinstance(payload, str):
            payload_bytes = payload.encode('utf-8')
        else:
            payload_bytes = payload
        content = payload_bytes + metadata.get('type', '').encode('utf-8')
        return hashlib.md5(content).hexdigest()

    def _on_clipboard_change(self, captured: CapturedClipboard):
        if self._setting_clipboard:
            return

        current_hash = self._calculate_hash(
            captured.payload, captured.metadata)
        if current_hash == self._last_sent_hash:
            return

        self._last_sent_hash = current_hash

        clip_type = captured.metadata.get('type', 'unknown')
        payload_size = len(captured.payload) if isinstance(
            captured.payload, bytes) else len(str(captured.payload).encode('utf-8'))
        captured_for_broadcast = captured

        if self.redis_service and self.user_id and self.device_id:
            try:
                if clip_type in ['file', 'folder', 'file_group'] and payload_size > 1048576:
                    from utils.file_manager import FileManager
                    file_manager = FileManager()
                    if isinstance(captured.payload, bytes):
                        payload_bytes = captured.payload
                    elif isinstance(captured.payload, str):
                        payload_bytes = captured.payload.encode('utf-8')
                    else:
                        payload_bytes = bytes(captured.payload)
                    file_path = file_manager.save_file(
                        payload_bytes, captured.metadata)

                    if file_path:
                        metadata_copy = dict(captured.metadata)
                        metadata_copy['file_reference'] = str(file_path)
                        metadata_copy['payload_size'] = payload_size

                        captured_ref = CapturedClipboard(
                            payload=b"",
                            metadata=metadata_copy,
                            timestamp=captured.timestamp
                        )
                        self.redis_service.save_captured_clipboard(
                            user_id=self.user_id,
                            device_id=self.device_id,
                            captured=captured_ref
                        )
                        logger.info(
                            f"Saved to Redis (reference): {clip_type}, {payload_size} bytes")
                    else:
                        logger.error(f"Failed to save large file reference")
                else:
                    self.redis_service.save_captured_clipboard(
                        user_id=self.user_id,
                        device_id=self.device_id,
                        captured=captured
                    )
                    logger.info(f"Saved to Redis: {clip_type}")
            except Exception as e:
                logger.error(f"Redis save error: {e}")

        if self.network_service:
            clipboard_data = {
                "payload": captured_for_broadcast.payload,
                "metadata": captured_for_broadcast.metadata,
                "timestamp": captured_for_broadcast.timestamp
            }
            logger.info(f"Broadcasting clipboard: {clip_type}")
            self.network_service.broadcast_clipboard(clipboard_data)

    def _on_clipboard_received(self, data: dict):
        try:
            payload_b64 = data.get("payload", "")
            metadata = data.get("metadata", {})
            timestamp = data.get("timestamp", None)

            if isinstance(payload_b64, str):
                payload = base64.b64decode(payload_b64)
            else:
                payload = payload_b64

            self._setting_clipboard = True

            try:
                ClipboardClass = get_clipboard_class()
                success = ClipboardClass.set_clipboard(payload, metadata)

                if success:
                    clip_type = metadata.get('type', 'unknown')
                    logger.info(f"Clipboard received and set: {clip_type}")
                    self._last_sent_hash = self._calculate_hash(
                        payload, metadata)

                    if self.redis_service and self.user_id and self.device_id:
                        try:
                            from datetime import datetime
                            timestamp_str = timestamp if timestamp else datetime.now().isoformat()

                            payload_size = len(payload) if isinstance(
                                payload, bytes) else len(str(payload).encode('utf-8'))

                            if clip_type in ['file', 'folder', 'file_group'] and payload_size > 1048576:
                                from utils.file_manager import FileManager
                                file_manager = FileManager()

                                if isinstance(payload, bytes):
                                    payload_bytes = payload
                                elif isinstance(payload, str):
                                    payload_bytes = payload.encode('utf-8')
                                else:
                                    payload_bytes = bytes(payload)
                                file_path = file_manager.save_file(
                                    payload_bytes, metadata)

                                if file_path:
                                    metadata_copy = dict(metadata)
                                    metadata_copy['file_reference'] = str(
                                        file_path)
                                    metadata_copy['payload_size'] = payload_size

                                    captured = CapturedClipboard(
                                        payload=b"",
                                        metadata=metadata_copy,
                                        timestamp=timestamp_str
                                    )
                                    logger.info(
                                        f"Saved received clipboard to Redis (reference): {clip_type}, {payload_size} bytes")
                                else:
                                    captured = CapturedClipboard(
                                        payload=payload,
                                        metadata=metadata,
                                        timestamp=timestamp_str
                                    )
                                    logger.info(
                                        f"Saved received clipboard to Redis: {clip_type}")
                            else:
                                captured = CapturedClipboard(
                                    payload=payload,
                                    metadata=metadata,
                                    timestamp=timestamp_str
                                )
                                logger.info(
                                    f"Saved received clipboard to Redis: {clip_type}")

                            self.redis_service.save_captured_clipboard(
                                user_id=self.user_id,
                                device_id=self.device_id,
                                captured=captured
                            )
                        except Exception as e:
                            logger.error(
                                f"Redis save error for received clipboard: {e}")

            finally:
                time.sleep(0.1)
                self._setting_clipboard = False

        except Exception as e:
            logger.error(f"Error handling clipboard: {e}")
            self._setting_clipboard = False

    def start(self):
        if self.running:
            return

        print(
            f"Starting ClipScape - Device: {self.device_name}, Port: {self.port}")

        self.running = True

        try:
            if self.use_redis:
                try:
                    self.redis_service = RedisService()
                    self.user_id = self.redis_service.ensure_user()
                    self.device_id = self.redis_service.ensure_device(
                        user_id=self.user_id,
                        device_name=self.device_name,
                        platform=sys.platform
                    )
                    logger.info(
                        f"Redis connected - User: {self.user_id}, Device: {self.device_id}")
                except Exception as e:
                    logger.warning(
                        f"Redis unavailable, continuing without persistence: {e}")
                    self.use_redis = False

            self.network_service = PeerNetworkService(
                signaling_port=self.port,
                device_name=self.device_name,
                auto_start=True,
                discovery_interval=self.discovery_interval
            )

            self.network_service.on_clipboard_received(
                self._on_clipboard_received)

            if not self.network_service.wait_until_ready(timeout=10.0):
                logger.error("Network service failed to start")
                self.stop()
                return

            self.clipboard_service = ClipboardService(
                on_capture=self._on_clipboard_change,
                auto_register=True
            )
            self.clipboard_service.poll_interval = self.poll_interval

            print("ClipScape running. Press Ctrl+C to stop")

        except Exception as e:
            logger.error(f"Error starting: {e}")
            self.stop()

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

        try:
            from utils.file_manager import FileManager
            file_manager = FileManager()
            file_manager.cleanup_all_files()
            logger.info("Temp files cleaned up")
        except Exception as e:
            logger.warning(f"Could not clean temp files: {e}")

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


def parse_args():
    parser = argparse.ArgumentParser(
        description="ClipScape - Cross-platform clipboard synchronization"
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=int(os.getenv("NETWORK_PORT", "9999")),
        help="Network port for P2P communication (default: 9999)"
    )

    parser.add_argument(
        "-n", "--name",
        type=str,
        default=None,
        help="Device name (default: hostname)"
    )

    parser.add_argument(
        "-i", "--poll-interval",
        type=float,
        default=0.25,
        help="Clipboard polling interval in seconds (default: 0.25)"
    )

    parser.add_argument(
        "-d", "--discovery-interval",
        type=float,
        default=30.0,
        help="Peer discovery interval in seconds (default: 30.0)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose debug logging"
    )

    parser.add_argument(
        "--no-redis",
        action="store_true",
        help="Disable Redis clipboard persistence"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.INFO)

    app = ClipScapeApp(
        port=args.port,
        device_name=args.name,
        poll_interval=args.poll_interval,
        discovery_interval=args.discovery_interval,
        use_redis=not args.no_redis
    )

    def signal_handler(signum, frame):
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        app.run_forever()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
