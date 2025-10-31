

import redis
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import ulid


class RedisManager:

    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0,
                 password: Optional[str] = None, decode_responses: bool = True):
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses
        )
        self._test_connection()

    def _test_connection(self):
        try:
            self.client.ping()
        except redis.ConnectionError as e:
            raise

    def create_user(self, user_id: Optional[str] = None, device_id: Optional[str] = None,
                    networks: Optional[List[str]] = None) -> str:
        if user_id is None:
            user_id = f"u_{ulid.new()}"

        user_data = {
            "userId": user_id,
            "devices": json.dumps([device_id] if device_id else []),
            "networks": json.dumps(networks or []),
            "currentDevice": device_id or "",
            "createdAt": datetime.now().isoformat()
        }

        self.client.hset(f"user:{user_id}", mapping=user_data)
        return user_id

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        data = self.client.hgetall(f"user:{user_id}")
        if not data:
            return None

        data['devices'] = json.loads(data.get('devices', '[]'))
        data['networks'] = json.loads(data.get('networks', '[]'))
        return data

    def update_user(self, user_id: str, **kwargs) -> bool:
        if not self.client.exists(f"user:{user_id}"):
            return False

        update_data = {}
        if 'devices' in kwargs:
            update_data['devices'] = json.dumps(kwargs['devices'])
        if 'networks' in kwargs:
            update_data['networks'] = json.dumps(kwargs['networks'])
        if 'currentDevice' in kwargs:
            update_data['currentDevice'] = kwargs['currentDevice']

        if update_data:
            self.client.hset(f"user:{user_id}", mapping=update_data)
        return True

    def add_device_to_user(self, user_id: str, device_id: str) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False

        devices = user['devices']
        if device_id not in devices:
            devices.append(device_id)
            return self.update_user(user_id, devices=devices)
        return True

    def add_network_to_user(self, user_id: str, network_id: str) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False

        networks = user['networks']
        if network_id not in networks:
            networks.append(network_id)
            return self.update_user(user_id, networks=networks)
        return True

    def delete_user(self, user_id: str) -> bool:
        clipboard_ids = self.client.lrange(f"user:{user_id}:clipboards", 0, -1)
        for item_id in clipboard_ids:
            self.client.delete(f"clipboard:{item_id}")

        self.client.delete(f"user:{user_id}:clipboards")
        return bool(self.client.delete(f"user:{user_id}"))

    def create_device(self, device_id: Optional[str] = None, user_id: Optional[str] = None,
                      platform: Optional[str] = None, device_name: Optional[str] = None,
                      metadata: Optional[Dict] = None) -> str:
        if device_id is None:
            device_id = f"d_{ulid.new()}"

        device_data = {
            "deviceId": device_id,
            "userId": user_id or "",
            "platform": platform or "",
            "deviceName": device_name or "",
            "metadata": json.dumps(metadata or {}),
            "createdAt": datetime.now().isoformat(),
            "lastActive": datetime.now().isoformat()
        }

        self.client.hset(f"device:{device_id}", mapping=device_data)

        if user_id:
            self.add_device_to_user(user_id, device_id)

        return device_id

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        data = self.client.hgetall(f"device:{device_id}")
        if not data:
            return None

        data['metadata'] = json.loads(data.get('metadata', '{}'))
        return data

    def update_device(self, device_id: str, **kwargs) -> bool:
        if not self.client.exists(f"device:{device_id}"):
            return False

        update_data = {}
        if 'platform' in kwargs:
            update_data['platform'] = kwargs['platform']
        if 'deviceName' in kwargs:
            update_data['deviceName'] = kwargs['deviceName']
        if 'metadata' in kwargs:
            update_data['metadata'] = json.dumps(kwargs['metadata'])
        if 'lastActive' in kwargs:
            update_data['lastActive'] = kwargs['lastActive']

        if update_data:
            self.client.hset(f"device:{device_id}", mapping=update_data)
        return True

    def update_device_activity(self, device_id: str) -> bool:
        return self.update_device(device_id, lastActive=datetime.now().isoformat())

    def delete_device(self, device_id: str) -> bool:
        clipboard_ids = self.client.lrange(
            f"device:{device_id}:clipboards", 0, -1)
        for item_id in clipboard_ids:
            self.client.delete(f"clipboard:{item_id}")

        self.client.delete(f"device:{device_id}:clipboards")

        return bool(self.client.delete(f"device:{device_id}"))

    def create_network(self, network_id: Optional[str] = None, network_name: Optional[str] = None,
                       owner_id: Optional[str] = None, devices: Optional[List[str]] = None) -> str:
        if network_id is None:
            network_id = f"n_{ulid.new()}"

        network_data = {
            "networkId": network_id,
            "networkName": network_name or f"Network {network_id[:8]}",
            "ownerId": owner_id or "",
            "devices": json.dumps(devices or []),
            "createdAt": datetime.now().isoformat()
        }

        self.client.hset(f"network:{network_id}", mapping=network_data)

        if owner_id:
            self.add_network_to_user(owner_id, network_id)

        return network_id

    def get_network(self, network_id: str) -> Optional[Dict[str, Any]]:
        data = self.client.hgetall(f"network:{network_id}")
        if not data:
            return None

        data['devices'] = json.loads(data.get('devices', '[]'))
        return data

    def update_network(self, network_id: str, **kwargs) -> bool:
        if not self.client.exists(f"network:{network_id}"):
            return False

        update_data = {}
        if 'networkName' in kwargs:
            update_data['networkName'] = kwargs['networkName']
        if 'ownerId' in kwargs:
            update_data['ownerId'] = kwargs['ownerId']
        if 'devices' in kwargs:
            update_data['devices'] = json.dumps(kwargs['devices'])

        if update_data:
            self.client.hset(f"network:{network_id}", mapping=update_data)
        return True

    def add_device_to_network(self, network_id: str, device_id: str) -> bool:
        network = self.get_network(network_id)
        if not network:
            return False

        devices = network['devices']
        if device_id not in devices:
            devices.append(device_id)
            return self.update_network(network_id, devices=devices)
        return True

    def remove_device_from_network(self, network_id: str, device_id: str) -> bool:
        network = self.get_network(network_id)
        if not network:
            return False

        devices = network['devices']
        if device_id in devices:
            devices.remove(device_id)
            return self.update_network(network_id, devices=devices)
        return True

    def delete_network(self, network_id: str) -> bool:
        return bool(self.client.delete(f"network:{network_id}"))

    def get_user_networks(self, user_id: str) -> List[Dict[str, Any]]:
        user = self.get_user(user_id)
        if not user:
            return []

        networks = []
        for network_id in user['networks']:
            network = self.get_network(network_id)
            if network:
                networks.append(network)
        return networks

    def create_clipboard_item(self, device_id: str, user_id: str, payload: bytes,
                              metadata: Dict[str, Any], item_id: Optional[str] = None) -> str:
        if item_id is None:
            item_id = f"i_{ulid.new()}"

        import base64
        payload_encoded = base64.b64encode(payload).decode(
            'utf-8') if isinstance(payload, bytes) else payload

        clipboard_data = {
            "itemId": item_id,
            "deviceId": device_id,
            "userId": user_id,
            "payload": payload_encoded,
            "metadata": json.dumps(metadata),
            "createdAt": datetime.now().isoformat()
        }

        self.client.hset(f"clipboard:{item_id}", mapping=clipboard_data)
        self.client.lpush(f"user:{user_id}:clipboards", item_id)
        self.client.lpush(f"device:{device_id}:clipboards", item_id)

        return item_id

    def get_clipboard_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        data = self.client.hgetall(f"clipboard:{item_id}")
        if not data:
            return None

        import base64
        try:
            data['payload'] = base64.b64decode(data['payload'])
        except Exception:
            pass

        data['metadata'] = json.loads(data.get('metadata', '{}'))
        return data

    def get_user_clipboards(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        item_ids = self.client.lrange(
            f"user:{user_id}:clipboards", 0, limit - 1)

        items = []
        for item_id in item_ids:
            item = self.get_clipboard_item(item_id)
            if item:
                items.append(item)
        return items

    def get_device_clipboards(self, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        item_ids = self.client.lrange(
            f"device:{device_id}:clipboards", 0, limit - 1)

        items = []
        for item_id in item_ids:
            item = self.get_clipboard_item(item_id)
            if item:
                items.append(item)
        return items

    def delete_clipboard_item(self, item_id: str) -> bool:
        item = self.get_clipboard_item(item_id)
        if not item:
            return False

        self.client.lrem(f"user:{item['userId']}:clipboards", 0, item_id)
        self.client.lrem(f"device:{item['deviceId']}:clipboards", 0, item_id)

        return bool(self.client.delete(f"clipboard:{item_id}"))

    def clear_user_clipboards(self, user_id: str) -> bool:
        item_ids = self.client.lrange(f"user:{user_id}:clipboards", 0, -1)

        for item_id in item_ids:
            self.client.delete(f"clipboard:{item_id}")

        self.client.delete(f"user:{user_id}:clipboards")
        return True

    def get_all_users(self) -> List[str]:
        keys = self.client.keys("user:*")
        return [key.split(':')[1] for key in keys if ':clipboards' not in key]

    def get_all_devices(self) -> List[str]:
        keys = self.client.keys("device:*")
        return [key.split(':')[1] for key in keys if ':clipboards' not in key]

    def get_all_networks(self) -> List[str]:
        keys = self.client.keys("network:*")
        return [key.split(':')[1] for key in keys]

    def health_check(self) -> Dict[str, Any]:
        info = self.client.info()
        return {
            "status": "healthy",
            "connected_clients": info.get('connected_clients', 0),
            "used_memory": info.get('used_memory_human', 'unknown'),
            "total_keys": self.client.dbsize(),
            "users": len(self.get_all_users()),
            "devices": len(self.get_all_devices()),
            "networks": len(self.get_all_networks())
        }

    def flush_all(self) -> bool:
        self.client.flushdb()
        return True

    def close(self):
        self.client.close()
