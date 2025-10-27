"""
ClipScape Network Package.

Provides P2P networking capabilities for clipboard synchronization.
"""

from network.peer import ClipScapePeer
from network.network import ClipScapeNetwork

__all__ = [
    'ClipScapePeer',
    'ClipScapeNetwork',
]
