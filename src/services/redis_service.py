from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Union, TYPE_CHECKING
from urllib.parse import urlparse

from database.redis_manager import RedisManager

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from .clipboard_service import CapturedClipboard


def _load_env_file(env_path: Optional[Path] = None) -> None:
    path = env_path or Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return

    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except OSError:
        return


def _to_bool(value: Optional[str], default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    decode_responses: bool = True

    @classmethod
    def from_env(cls, *, env_path: Optional[Path] = None) -> "RedisConfig":
        _load_env_file(env_path)

        uri = os.getenv("REDIS_URI")
        if uri:
            return cls.from_uri(uri)

        host = os.getenv("REDIS_HOST", cls.host)
        port_raw = os.getenv("REDIS_PORT")
        db_raw = os.getenv("REDIS_DB")
        password = os.getenv("REDIS_PASSWORD") or None
        decode = _to_bool(os.getenv("REDIS_DECODE_RESPONSES"), default=True)

        port = int(port_raw) if port_raw else cls.port
        db = int(db_raw) if db_raw else cls.db

        return cls(host=host, port=port, db=db, password=password, decode_responses=decode)

    @classmethod
    def from_uri(cls, uri: str) -> "RedisConfig":
        parsed = urlparse(uri)
        if parsed.scheme not in {"redis", "rediss"}:
            raise ValueError(
                f"Unsupported Redis URI scheme: {parsed.scheme!r}")

        host = parsed.hostname or cls.host
        port = parsed.port or cls.port
        password = parsed.password or None
        db_fragment = parsed.path.lstrip("/")
        db = int(db_fragment) if db_fragment else cls.db

        decode = _to_bool(os.getenv("REDIS_DECODE_RESPONSES"), default=True)

        return cls(host=host, port=port, db=db, password=password, decode_responses=decode)

    def create_manager(self) -> RedisManager:
        return RedisManager(
            host=self.host,
            port=self.port,
            db=self.db,
            password=self.password,
            decode_responses=self.decode_responses,
        )


class RedisService:
    def __init__(
        self,
        manager: Optional[RedisManager] = None,
        config: Optional[RedisConfig] = None,
    ) -> None:
        self.config = config or RedisConfig.from_env()
        self.manager = manager or self.config.create_manager()

    def ensure_user(
        self,
        user_id: Optional[str] = None,
        *,
        device_id: Optional[str] = None,
        networks: Optional[Iterable[str]] = None,
    ) -> str:
        existing = user_id and self.manager.get_user(user_id)
        if existing:
            if device_id:
                self.manager.add_device_to_user(user_id, device_id)
            if networks:
                for network_id in networks:
                    self.manager.add_network_to_user(user_id, network_id)
            return user_id  # type: ignore[return-value]

        networks_list = list(networks or [])
        return self.manager.create_user(user_id=user_id, device_id=device_id, networks=networks_list)

    def ensure_device(
        self,
        *,
        user_id: str,
        device_id: Optional[str] = None,
        platform: Optional[str] = None,
        device_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if device_id:
            device = self.manager.get_device(device_id)
            if device:
                update_payload: Dict[str, Any] = {}
                if platform and device.get("platform") != platform:
                    update_payload["platform"] = platform
                if device_name and device.get("deviceName") != device_name:
                    update_payload["deviceName"] = device_name
                if metadata:
                    merged_meta = {**device.get("metadata", {}), **metadata}
                    update_payload["metadata"] = merged_meta
                if update_payload:
                    self.manager.update_device(device_id, **update_payload)
                return device_id

        return self.manager.create_device(
            device_id=device_id,
            user_id=user_id,
            platform=platform,
            device_name=device_name,
            metadata=metadata,
        )

    def save_clipboard_payload(
        self,
        *,
        user_id: str,
        device_id: str,
        payload: Union[bytes, str],
        metadata: Dict[str, Any],
        item_id: Optional[str] = None,
    ) -> str:
        payload_bytes = payload if isinstance(
            payload, bytes) else payload.encode("utf-8")
        return self.manager.create_clipboard_item(
            device_id=device_id,
            user_id=user_id,
            payload=payload_bytes,
            metadata=metadata,
            item_id=item_id,
        )

    def save_captured_clipboard(
        self,
        captured: "CapturedClipboard",
        *,
        user_id: str,
        device_id: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        metadata = dict(captured.metadata)
        if extra_metadata:
            metadata.update(extra_metadata)
        metadata.setdefault("owner_device", device_id)

        payload = captured.payload
        payload_bytes = payload if isinstance(
            payload, bytes) else payload.encode("utf-8")

        return self.save_clipboard_payload(
            user_id=user_id,
            device_id=device_id,
            payload=payload_bytes,
            metadata=metadata,
        )

    def ensure_network(
        self,
        *,
        owner_id: str,
        network_id: Optional[str] = None,
        network_name: Optional[str] = None,
        devices: Optional[Iterable[str]] = None,
    ) -> str:
        if network_id:
            record = self.manager.get_network(network_id)
            if record:
                update_payload: Dict[str, Any] = {}
                if network_name and record.get("networkName") != network_name:
                    update_payload["networkName"] = network_name
                if devices:
                    existing_devices = set(record.get("devices", []))
                    new_devices = list({*existing_devices, *devices})
                    update_payload["devices"] = new_devices
                if update_payload:
                    self.manager.update_network(network_id, **update_payload)
                return network_id

        device_list = list(devices or [])
        return self.manager.create_network(
            network_id=network_id,
            network_name=network_name,
            owner_id=owner_id,
            devices=device_list,
        )

    def get_user_clipboards(self, user_id: str, limit: int = 50):
        return self.manager.get_user_clipboards(user_id, limit=limit)

    def get_device_clipboards(self, device_id: str, limit: int = 50):
        return self.manager.get_device_clipboards(device_id, limit=limit)

    def close(self) -> None:
        self.manager.close()

    def __enter__(self) -> "RedisService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
