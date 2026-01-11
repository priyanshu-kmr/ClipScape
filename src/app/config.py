"""Resolved runtime configuration."""

import argparse
import os
import socket
from dataclasses import dataclass
from typing import Optional


def default_device_name() -> str:
    return socket.gethostname().split('.')[0]


def default_port() -> int:
    return int(os.getenv("NETWORK_PORT", "9999"))


@dataclass(frozen=True)
class AppConfig:
    port: int
    device_name: str
    poll_interval: float
    discovery_interval: float
    use_redis: bool

    @classmethod
    def create(
        cls,
        *,
        port: Optional[int] = None,
        device_name: Optional[str] = None,
        poll_interval: float = 0.25,
        discovery_interval: float = 30.0,
        use_redis: bool = True,
    ) -> "AppConfig":
        return cls(
            port=port if port is not None else default_port(),
            device_name=device_name or default_device_name(),
            poll_interval=poll_interval,
            discovery_interval=discovery_interval,
            use_redis=use_redis,
        )

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "AppConfig":
        return cls.create(
            port=args.port,
            device_name=args.name,
            poll_interval=args.poll_interval,
            discovery_interval=args.discovery_interval,
            use_redis=not args.no_redis,
        )
