# ClipScape Manager - Redis Data Management

This module provides Redis-based data management for ClipScape, handling users, devices, networks, and clipboard items.

## Architecture

```
manager/
├── __init__.py           # Package exports
├── redis_manager.py      # Redis management class
├── redis.py              # Schema documentation (legacy)
├── sql_manager.py        # SQL management (TODO)
└── mysql.py              # MySQL specific (TODO)
```

## Redis Data Structure

### Keys Pattern

```
user:<userId>                    - User data (hash)
user:<userId>:clipboards         - User's clipboard items (list)

device:<deviceId>                - Device data (hash)
device:<deviceId>:clipboards     - Device's clipboard items (list)

network:<networkId>              - Network data (hash)

clipboard:<itemId>               - Clipboard item data (hash)
```

### Data Models

#### User
```python
{
    "userId": "u_01HQXXX...",
    "devices": ["d_01HQXXX...", "d_01HQYYY..."],  # JSON array
    "networks": ["n_01HQXXX..."],                  # JSON array
    "currentDevice": "d_01HQXXX...",
    "createdAt": "2025-10-06T10:30:00"
}
```

#### Device
```python
{
    "deviceId": "d_01HQXXX...",
    "userId": "u_01HQXXX...",
    "platform": "windows",
    "deviceName": "Alice's Laptop",
    "metadata": {...},  # JSON object
    "createdAt": "2025-10-06T10:30:00",
    "lastActive": "2025-10-06T12:45:00"
}
```

#### Network
```python
{
    "networkId": "n_01HQXXX...",
    "networkName": "Home Network",
    "ownerId": "u_01HQXXX...",
    "devices": ["d_01HQXXX...", "d_01HQYYY..."],  # JSON array
    "createdAt": "2025-10-06T10:30:00"
}
```

#### Clipboard Item
```python
{
    "itemId": "i_01HQXXX...",
    "deviceId": "d_01HQXXX...",
    "userId": "u_01HQXXX...",
    "payload": "<base64_encoded_data>",
    "metadata": {
        "type": "text",
        "length": 123,
        ...
    },
    "createdAt": "2025-10-06T12:45:00"
}
```

## Usage

### Basic Setup

```python
from manager import RedisManager

# Initialize Redis connection
redis_mgr = RedisManager(
    host='localhost',
    port=6379,
    db=0,
    password=None  # If Redis requires authentication
)

# Check health
status = redis_mgr.health_check()
print(status)
```

### User Management

```python
# Create a new user
user_id = redis_mgr.create_user()
print(f"Created user: {user_id}")

# Create user with specific ID and device
user_id = redis_mgr.create_user(
    user_id="u_custom123",
    device_id="d_device456"
)

# Get user data
user = redis_mgr.get_user(user_id)
print(user)

# Update user
redis_mgr.update_user(user_id, currentDevice="d_newdevice")

# Add device to user
redis_mgr.add_device_to_user(user_id, "d_device789")

# Add network to user
redis_mgr.add_network_to_user(user_id, "n_network123")

# Delete user (also deletes their clipboard items)
redis_mgr.delete_user(user_id)

# Get all users
all_users = redis_mgr.get_all_users()
```

### Device Management

```python
# Create a device
device_id = redis_mgr.create_device(
    user_id="u_123",
    platform="windows",
    device_name="Alice's Laptop",
    metadata={
        "hostname": "DESKTOP-ABC",
        "ip": "192.168.1.100"
    }
)

# Get device data
device = redis_mgr.get_device(device_id)

# Update device
redis_mgr.update_device(
    device_id,
    deviceName="Alice's Desktop",
    platform="windows"
)

# Update device activity (last active timestamp)
redis_mgr.update_device_activity(device_id)

# Delete device
redis_mgr.delete_device(device_id)

# Get all devices
all_devices = redis_mgr.get_all_devices()
```

### Network Management

```python
# Create a network
network_id = redis_mgr.create_network(
    network_name="Home Network",
    owner_id="u_123",
    devices=["d_456", "d_789"]
)

# Get network data
network = redis_mgr.get_network(network_id)

# Update network
redis_mgr.update_network(
    network_id,
    networkName="Work Network"
)

# Add device to network
redis_mgr.add_device_to_network(network_id, "d_newdevice")

# Remove device from network
redis_mgr.remove_device_from_network(network_id, "d_olddevice")

# Get all networks for a user
user_networks = redis_mgr.get_user_networks("u_123")

# Delete network
redis_mgr.delete_network(network_id)

# Get all networks
all_networks = redis_mgr.get_all_networks()
```

### Clipboard Management

```python
# Create clipboard item
item_id = redis_mgr.create_clipboard_item(
    device_id="d_123",
    user_id="u_456",
    payload=b"Hello, World!",
    metadata={
        "type": "text",
        "length": 13,
        "owner_device": "d_123"
    }
)

# Get clipboard item
item = redis_mgr.get_clipboard_item(item_id)
print(item['payload'])  # Returns bytes

# Get user's clipboard history (last 50 items)
user_clipboards = redis_mgr.get_user_clipboards("u_456", limit=50)

# Get device's clipboard history
device_clipboards = redis_mgr.get_device_clipboards("d_123", limit=20)

# Delete clipboard item
redis_mgr.delete_clipboard_item(item_id)

# Clear all clipboard items for a user
redis_mgr.clear_user_clipboards("u_456")
```

## Complete Integration Example

```python
from manager import RedisManager
from platforms import get_clipboard_item
from network import ClipScapeNetwork
import asyncio

# Initialize components
redis_mgr = RedisManager()

# Setup user and device
user_id = redis_mgr.create_user()
device_id = redis_mgr.create_device(
    user_id=user_id,
    platform="windows",
    device_name="My Laptop"
)

# Create or join network
network_id = redis_mgr.create_network(
    network_name="My Devices",
    owner_id=user_id,
    devices=[device_id]
)

async def sync_clipboard():
    # Create P2P network
    network = ClipScapeNetwork()
    
    # Handle incoming clipboard from peers
    def on_peer_clipboard(peer_id, message):
        import json
        data = json.loads(message)
        
        if data.get("type") == "clipboard":
            # Store in Redis
            redis_mgr.create_clipboard_item(
                device_id=data['device_id'],
                user_id=data['user_id'],
                payload=bytes.fromhex(data['payload']),
                metadata=data['metadata']
            )
            print(f"Stored clipboard from {peer_id}")
    
    network.on_message(on_peer_clipboard)
    
    # Start network
    await network.start()
    await network.discover_and_connect()
    
    # Monitor local clipboard
    last_clipboard = None
    while True:
        await asyncio.sleep(0.5)
        
        # Update device activity
        redis_mgr.update_device_activity(device_id)
        
        # Check clipboard
        clipboard = get_clipboard_item()
        
        if clipboard.payload != last_clipboard:
            # Store locally
            item_id = redis_mgr.create_clipboard_item(
                device_id=device_id,
                user_id=user_id,
                payload=clipboard.payload,
                metadata=clipboard.metaData
            )
            
            # Broadcast to network
            network.broadcast_json({
                "type": "clipboard",
                "device_id": device_id,
                "user_id": user_id,
                "payload": clipboard.payload.hex(),
                "metadata": clipboard.metaData
            })
            
            last_clipboard = clipboard.payload
            print(f"Synced clipboard: {item_id}")

# Run
try:
    asyncio.run(sync_clipboard())
except KeyboardInterrupt:
    redis_mgr.close()
```

## Advanced Usage

### Clipboard History Viewer

```python
def show_clipboard_history(user_id: str, redis_mgr: RedisManager):
    """Show user's clipboard history."""
    items = redis_mgr.get_user_clipboards(user_id, limit=10)
    
    print(f"\n{'='*60}")
    print(f"Clipboard History for User: {user_id}")
    print(f"{'='*60}\n")
    
    for i, item in enumerate(items, 1):
        metadata = item['metadata']
        created = item['createdAt']
        item_type = metadata.get('type', 'unknown')
        
        print(f"{i}. [{item_type}] - {created}")
        
        if item_type == 'text':
            preview = item['payload'][:50].decode('utf-8', errors='ignore')
            print(f"   Preview: {preview}...")
        elif item_type == 'file':
            print(f"   File: {metadata.get('file_name', 'unknown')}")
        elif item_type == 'image':
            print(f"   Image: {metadata.get('file_size', 0)} bytes")
        
        print()

# Usage
show_clipboard_history("u_123", redis_mgr)
```

### Network Status Dashboard

```python
def show_network_status(network_id: str, redis_mgr: RedisManager):
    """Show network status with all devices."""
    network = redis_mgr.get_network(network_id)
    
    if not network:
        print("Network not found")
        return
    
    print(f"\n{'='*60}")
    print(f"Network: {network['networkName']} ({network_id})")
    print(f"Owner: {network['ownerId']}")
    print(f"{'='*60}\n")
    
    print("Devices:")
    for device_id in network['devices']:
        device = redis_mgr.get_device(device_id)
        if device:
            print(f"  • {device['deviceName']} ({device['platform']})")
            print(f"    Last Active: {device['lastActive']}")
            
            # Show recent clipboard count
            clipboards = redis_mgr.get_device_clipboards(device_id, limit=5)
            print(f"    Recent Clipboards: {len(clipboards)}")
        print()

# Usage
show_network_status("n_123", redis_mgr)
```

### Cleanup Old Clipboards

```python
from datetime import datetime, timedelta

def cleanup_old_clipboards(user_id: str, redis_mgr: RedisManager, days: int = 30):
    """Delete clipboard items older than specified days."""
    items = redis_mgr.get_user_clipboards(user_id, limit=1000)
    
    cutoff = datetime.now() - timedelta(days=days)
    deleted_count = 0
    
    for item in items:
        created = datetime.fromisoformat(item['createdAt'])
        if created < cutoff:
            redis_mgr.delete_clipboard_item(item['itemId'])
            deleted_count += 1
    
    print(f"Deleted {deleted_count} old clipboard items")
    return deleted_count

# Usage
cleanup_old_clipboards("u_123", redis_mgr, days=7)
```

## Configuration

### Redis Configuration

For production, configure Redis with:

```bash
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru  # Evict least recently used keys
```

### Connection Pool

For high-performance applications:

```python
from redis import ConnectionPool

pool = ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=50,
    decode_responses=True
)

redis_mgr = RedisManager(connection_pool=pool)
```

## Error Handling

```python
from redis.exceptions import ConnectionError, TimeoutError

try:
    redis_mgr = RedisManager(host='localhost', port=6379)
    user_id = redis_mgr.create_user()
except ConnectionError as e:
    print(f"Cannot connect to Redis: {e}")
except TimeoutError as e:
    print(f"Redis operation timed out: {e}")
finally:
    redis_mgr.close()
```

## Best Practices

1. **Always close connections**: Use context managers or explicit `close()` calls
2. **Limit clipboard history**: Set reasonable limits (e.g., 50-100 items per user)
3. **Regular cleanup**: Schedule cleanup of old clipboard items
4. **Update device activity**: Regularly update `lastActive` timestamp
5. **Use ULID for IDs**: Provides time-ordered, unique identifiers
6. **Monitor memory**: Redis is in-memory, watch memory usage
7. **Backup data**: Regular Redis snapshots or AOF persistence

## Performance Considerations

- **Pagination**: Use `limit` parameter for clipboard queries
- **Indexes**: Redis doesn't support indexes, structure keys carefully
- **Expiration**: Consider using TTL for temporary clipboard items
- **Pipeline**: Batch multiple operations for better performance

```python
# Example: Batch operations
pipe = redis_mgr.client.pipeline()
pipe.hset("user:u_123", "field", "value")
pipe.lpush("user:u_123:clipboards", "i_456")
pipe.execute()
```

## Dependencies

```toml
[dependencies]
redis = "^5.0.0"
ulid-py = "^1.1.0"
```

## Testing

```python
import pytest
from manager import RedisManager

@pytest.fixture
def redis_mgr():
    mgr = RedisManager(db=15)  # Use test database
    yield mgr
    mgr.flush_all()  # Clean up
    mgr.close()

def test_create_user(redis_mgr):
    user_id = redis_mgr.create_user()
    assert user_id.startswith("u_")
    
    user = redis_mgr.get_user(user_id)
    assert user is not None
    assert user['userId'] == user_id
```

## Future Enhancements

- [ ] Add clipboard item expiration (TTL)
- [ ] Implement pagination for large lists
- [ ] Add search functionality for clipboard items
- [ ] Support clipboard tags/categories
- [ ] Add encryption for sensitive clipboard data
- [ ] Implement Redis Streams for real-time sync
- [ ] Add metrics and monitoring
- [ ] Support Redis Cluster for scalability
