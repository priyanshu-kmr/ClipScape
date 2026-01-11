"""Minimal Redis manager exposing generic CRUD helpers."""

from typing import Any, Dict, List, Optional

import redis


class RedisManager:
    """Thin wrapper around redis-py providing basic CRUD operations."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0, password: Optional[str] = None, decode_responses: bool = True) -> None:
        self.client = redis.Redis(host=host, port=port, db=db, password=password, decode_responses=decode_responses)
        self._test_connection()

    def _test_connection(self) -> None:
        self.client.ping()

    def _key(self, resource_type: str, resource_id: str) -> str:
        return f"{resource_type}:{resource_id}"

    def create(self, resource_type: str, resource_id: str, data: Dict[str, Any]) -> str:
        """Create a hash record for the given resource type and id."""
        key = self._key(resource_type, resource_id)
        self.client.hset(key, mapping=data)
        return key

    def read(self, resource_type: str, resource_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a hash record; returns None when missing."""
        key = self._key(resource_type, resource_id)
        record = self.client.hgetall(key)
        return record or None

    def update(self, resource_type: str, resource_id: str, updates: Dict[str, Any]) -> bool:
        """Update fields on an existing hash record."""
        key = self._key(resource_type, resource_id)
        if not self.client.exists(key):
            return False
        if updates:
            self.client.hset(key, mapping=updates)
        return True

    def delete(self, resource_type: str, resource_id: str) -> bool:
        """Delete a hash record for the given resource."""
        key = self._key(resource_type, resource_id)
        return bool(self.client.delete(key))

    def list_ids(self, resource_type: str) -> List[str]:
        """List all ids for a resource type based on the stored keys."""
        prefix = f"{resource_type}:"
        keys = self.client.keys(f"{resource_type}:*")
        return [k[len(prefix):] for k in keys]

    def close(self) -> None:
        self.client.close()
