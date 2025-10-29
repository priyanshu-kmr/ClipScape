"""
Redis Schema Documentation for ClipScape.

This file documents the data structure used in Redis.
"""

# Data Structure Overview:

# User Structure:
# users: {
#     userId: {
#         "userId": "u_1b22b92...",
#          "username": "user1",
#         "devices": ["device1", "device2", ...],
#         "networks": ["network1", "network2", ...],
#         "currentDevice": "deviceId"
#     }
# }

# Device Structure:
# device: {
#     "deviceId": "d_A2293B...",
#     "platform": "windows/iOS/android/linux/macos",
#     "userId": "u_1b22b92...",
#     "deviceName": "My Laptop",
#     "metadata": {...},
#     "lastActive": "2025-10-06T10:30:00"
# }

# Network Structure (P2P Network Ledger):
# networkLedger: {
#   "network111": {
#     "networkName": "network_A",
#     "ownerId": "user123",
#     "devices": ["device1", "device2", "device3"]
#   },
#   "network222": {
#     "networkName": "network_B",
#     "ownerId": "user456",
#     "devices": ["device4", "device5"]
#   }
# }

# Clipboard Item Structure:
# clipboard: {
#     "itemId": "i_C3B92A...",
#     "deviceId": "d_A2293B...",
#     "userId": "u_1b22b92...",
#     "payload": "<base64_encoded_data>",
#     "metadata": {
#         "type": "text/image/file",
#         "length": 123,
#         ...
#     },
#     "createdAt": "2025-10-06T12:45:00"
# }



