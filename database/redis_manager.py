"""
Redis Management for ClipScape.

Handles all Redis operations for users, devices, networks, and clipboard items.
"""

import redis
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from ulid import ULID


class RedisManager:
    """
    Manages all Redis operations for ClipScape.
    
    Data Structure:
    - users:<userId> -> User data (hash)
    - device:<deviceId> -> Device data (hash)
    - network:<networkId> -> Network data (hash)
    - clipboard:<itemId> -> Clipboard item (hash)
    - user:<userId>:clipboards -> List of clipboard item IDs (list)
    - device:<deviceId>:clipboards -> List of clipboard item IDs (list)
    """
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0, 
                 password: Optional[str] = None, decode_responses: bool = True):
        """
        Initialize Redis connection.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (if required)
            decode_responses: Decode responses to strings
        """
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses
        )
        self._test_connection()
    
    def _test_connection(self):
        """Test Redis connection."""
        try:
            self.client.ping()
            print("Redis connection established successfully")
        except redis.ConnectionError as e:
            print(f"Failed to connect to Redis: {e}")
            raise
    
    # ==================== USER OPERATIONS ====================
    
    def create_user(self, user_id: Optional[str] = None, device_id: Optional[str] = None, 
                    networks: Optional[List[str]] = None) -> str:
        """
        Create a new user.
        
        Args:
            user_id: User ID (generated if not provided)
            device_id: Current device ID
            networks: List of network IDs user belongs to
            
        Returns:
            str: User ID
        """
        if user_id is None:
            user_id = f"u_{ULID()}"
        
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
        """
        Get user data.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict with user data or None
        """
        data = self.client.hgetall(f"user:{user_id}")
        if not data:
            return None
        
        # Parse JSON fields
        data['devices'] = json.loads(data.get('devices', '[]'))
        data['networks'] = json.loads(data.get('networks', '[]'))
        return data
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """
        Update user data.
        
        Args:
            user_id: User ID
            **kwargs: Fields to update (devices, networks, currentDevice)
            
        Returns:
            bool: Success status
        """
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
        """Add a device to user's device list."""
        user = self.get_user(user_id)
        if not user:
            return False
        
        devices = user['devices']
        if device_id not in devices:
            devices.append(device_id)
            return self.update_user(user_id, devices=devices)
        return True
    
    def add_network_to_user(self, user_id: str, network_id: str) -> bool:
        """Add a network to user's network list."""
        user = self.get_user(user_id)
        if not user:
            return False
        
        networks = user['networks']
        if network_id not in networks:
            networks.append(network_id)
            return self.update_user(user_id, networks=networks)
        return True
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user and their clipboard items."""
        # Delete user's clipboard items
        clipboard_ids = self.client.lrange(f"user:{user_id}:clipboards", 0, -1)
        for item_id in clipboard_ids:
            self.client.delete(f"clipboard:{item_id}")
        
        # Delete clipboard list
        self.client.delete(f"user:{user_id}:clipboards")
        
        # Delete user
        return bool(self.client.delete(f"user:{user_id}"))
    
    # ==================== DEVICE OPERATIONS ====================
    
    def create_device(self, device_id: Optional[str] = None, user_id: Optional[str] = None,
                     platform: Optional[str] = None, device_name: Optional[str] = None,
                     metadata: Optional[Dict] = None) -> str:
        """
        Create a new device.
        
        Args:
            device_id: Device ID (generated if not provided)
            user_id: Owner user ID
            platform: Platform name (windows, linux, macos, etc.)
            device_name: Human-readable device name
            metadata: Additional device metadata
            
        Returns:
            str: Device ID
        """
        if device_id is None:
            device_id = f"d_{ULID()}"
        
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
        
        # Add device to user's device list
        if user_id:
            self.add_device_to_user(user_id, device_id)
        
        return device_id
    
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get device data."""
        data = self.client.hgetall(f"device:{device_id}")
        if not data:
            return None
        
        data['metadata'] = json.loads(data.get('metadata', '{}'))
        return data
    
    def update_device(self, device_id: str, **kwargs) -> bool:
        """Update device data."""
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
        """Update device's last active timestamp."""
        return self.update_device(device_id, lastActive=datetime.now().isoformat())
    
    def delete_device(self, device_id: str) -> bool:
        """Delete a device and its clipboard items."""
        # Delete device's clipboard items
        clipboard_ids = self.client.lrange(f"device:{device_id}:clipboards", 0, -1)
        for item_id in clipboard_ids:
            self.client.delete(f"clipboard:{item_id}")
        
        # Delete clipboard list
        self.client.delete(f"device:{device_id}:clipboards")
        
        # Delete device
        return bool(self.client.delete(f"device:{device_id}"))
    
    # ==================== NETWORK OPERATIONS ====================
    
    def create_network(self, network_id: Optional[str] = None, network_name: Optional[str] = None,
                      owner_id: Optional[str] = None, devices: Optional[List[str]] = None) -> str:
        """
        Create a new network.
        
        Args:
            network_id: Network ID (generated if not provided)
            network_name: Network name
            owner_id: Owner user ID
            devices: List of device IDs in the network
            
        Returns:
            str: Network ID
        """
        if network_id is None:
            network_id = f"n_{ULID()}"
        
        network_data = {
            "networkId": network_id,
            "networkName": network_name or f"Network {network_id[:8]}",
            "ownerId": owner_id or "",
            "devices": json.dumps(devices or []),
            "createdAt": datetime.now().isoformat()
        }
        
        self.client.hset(f"network:{network_id}", mapping=network_data)
        
        # Add network to owner's network list
        if owner_id:
            self.add_network_to_user(owner_id, network_id)
        
        return network_id
    
    def get_network(self, network_id: str) -> Optional[Dict[str, Any]]:
        """Get network data."""
        data = self.client.hgetall(f"network:{network_id}")
        if not data:
            return None
        
        data['devices'] = json.loads(data.get('devices', '[]'))
        return data
    
    def update_network(self, network_id: str, **kwargs) -> bool:
        """Update network data."""
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
        """Add a device to network."""
        network = self.get_network(network_id)
        if not network:
            return False
        
        devices = network['devices']
        if device_id not in devices:
            devices.append(device_id)
            return self.update_network(network_id, devices=devices)
        return True
    
    def remove_device_from_network(self, network_id: str, device_id: str) -> bool:
        """Remove a device from network."""
        network = self.get_network(network_id)
        if not network:
            return False
        
        devices = network['devices']
        if device_id in devices:
            devices.remove(device_id)
            return self.update_network(network_id, devices=devices)
        return True
    
    def delete_network(self, network_id: str) -> bool:
        """Delete a network."""
        return bool(self.client.delete(f"network:{network_id}"))
    
    def get_user_networks(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all networks for a user."""
        user = self.get_user(user_id)
        if not user:
            return []
        
        networks = []
        for network_id in user['networks']:
            network = self.get_network(network_id)
            if network:
                networks.append(network)
        return networks
    
    # ==================== CLIPBOARD OPERATIONS ====================
    
    def create_clipboard_item(self, device_id: str, user_id: str, payload: bytes,
                             metadata: Dict[str, Any], item_id: Optional[str] = None) -> str:
        """
        Create a clipboard item.
        
        Args:
            device_id: Source device ID
            user_id: User ID
            payload: Clipboard content (bytes)
            metadata: Clipboard metadata
            item_id: Item ID (generated if not provided)
            
        Returns:
            str: Clipboard item ID
        """
        if item_id is None:
            item_id = f"i_{ULID()}"
        
        # Convert bytes to base64 for Redis storage
        import base64
        payload_encoded = base64.b64encode(payload).decode('utf-8') if isinstance(payload, bytes) else payload
        
        clipboard_data = {
            "itemId": item_id,
            "deviceId": device_id,
            "userId": user_id,
            "payload": payload_encoded,
            "metadata": json.dumps(metadata),
            "createdAt": datetime.now().isoformat()
        }
        
        self.client.hset(f"clipboard:{item_id}", mapping=clipboard_data)
        
        # Add to user's clipboard list
        self.client.lpush(f"user:{user_id}:clipboards", item_id)
        
        # Add to device's clipboard list
        self.client.lpush(f"device:{device_id}:clipboards", item_id)
        
        return item_id
    
    def get_clipboard_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get clipboard item."""
        data = self.client.hgetall(f"clipboard:{item_id}")
        if not data:
            return None
        
        # Decode payload from base64
        import base64
        try:
            data['payload'] = base64.b64decode(data['payload'])
        except Exception:
            pass
        
        data['metadata'] = json.loads(data.get('metadata', '{}'))
        return data
    
    def get_user_clipboards(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user's clipboard items."""
        item_ids = self.client.lrange(f"user:{user_id}:clipboards", 0, limit - 1)
        
        items = []
        for item_id in item_ids:
            item = self.get_clipboard_item(item_id)
            if item:
                items.append(item)
        return items
    
    def get_device_clipboards(self, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get device's clipboard items."""
        item_ids = self.client.lrange(f"device:{device_id}:clipboards", 0, limit - 1)
        
        items = []
        for item_id in item_ids:
            item = self.get_clipboard_item(item_id)
            if item:
                items.append(item)
        return items
    
    def delete_clipboard_item(self, item_id: str) -> bool:
        """Delete a clipboard item."""
        # Get item to find user and device
        item = self.get_clipboard_item(item_id)
        if not item:
            return False
        
        # Remove from user's list
        self.client.lrem(f"user:{item['userId']}:clipboards", 0, item_id)
        
        # Remove from device's list
        self.client.lrem(f"device:{item['deviceId']}:clipboards", 0, item_id)
        
        # Delete item
        return bool(self.client.delete(f"clipboard:{item_id}"))
    
    def clear_user_clipboards(self, user_id: str) -> bool:
        """Clear all clipboard items for a user."""
        item_ids = self.client.lrange(f"user:{user_id}:clipboards", 0, -1)
        
        for item_id in item_ids:
            self.client.delete(f"clipboard:{item_id}")
        
        self.client.delete(f"user:{user_id}:clipboards")
        return True
    
    # ==================== UTILITY OPERATIONS ====================
    
    def get_all_users(self) -> List[str]:
        """Get all user IDs."""
        keys = self.client.keys("user:*")
        return [key.split(':')[1] for key in keys if ':clipboards' not in key]
    
    def get_all_devices(self) -> List[str]:
        """Get all device IDs."""
        keys = self.client.keys("device:*")
        return [key.split(':')[1] for key in keys if ':clipboards' not in key]
    
    def get_all_networks(self) -> List[str]:
        """Get all network IDs."""
        keys = self.client.keys("network:*")
        return [key.split(':')[1] for key in keys]
    
    def health_check(self) -> Dict[str, Any]:
        """Get Redis health status."""
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
        """⚠️ WARNING: Delete all data from Redis. Use with caution!"""
        self.client.flushdb()
        return True
    
    def close(self):
        """Close Redis connection."""
        self.client.close()
