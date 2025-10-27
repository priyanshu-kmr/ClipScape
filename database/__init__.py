"""
Manager Package for ClipScape.

Provides data management classes for various storage backends.
"""

from database.redis_manager import RedisManager

__all__ = [
    'RedisManager',
]
