"""
storage.py - In-Memory Storage for Decentralized Disaster Response System

This module provides thread-safe in-memory storage for help requests.
It handles message deduplication, TTL-based expiry, and query operations.

Production Considerations:
- Could be backed by SQLite for persistence across restarts
- In mesh networks, storage should be bounded to prevent memory exhaustion
- Periodic cleanup removes expired messages

Offline/Mesh Scenario Notes:
- Local storage serves as a cache/buffer when disconnected
- Sync protocols would merge storage from reconnected peers
- CRDT-based storage could enable conflict-free merges
"""

import threading
from typing import Dict, List, Optional, Set
from datetime import datetime
import logging

from models import HelpRequest, GeoLocation

logger = logging.getLogger(__name__)


class MessageStorage:
    """
    Thread-safe in-memory storage for help request messages.
    
    Key Features:
    - UUID-based deduplication prevents duplicate processing
    - TTL-based automatic expiry
    - Thread-safe operations for concurrent access
    - Geospatial queries (simplified distance-based)
    
    In production, this could be extended with:
    - Persistent storage (SQLite, LevelDB)
    - Spatial indexing (R-tree) for efficient geo-queries
    - Bloom filters for fast duplicate detection
    """
    
    def __init__(self, max_messages: int = 10000):
        """
        Initialize storage with optional capacity limit.
        
        Args:
            max_messages: Maximum number of messages to store.
                         Oldest messages are evicted when limit is reached.
        """
        self._messages: Dict[str, HelpRequest] = {}
        self._seen_ids: Set[str] = set()  # For deduplication even after expiry
        self._lock = threading.RLock()
        self._max_messages = max_messages
        
        # Statistics
        self._total_received = 0
        self._duplicates_rejected = 0
        
        logger.info(f"MessageStorage initialized with capacity: {max_messages}")
    
    def store(self, message: HelpRequest) -> bool:
        """
        Store a help request message.
        
        Args:
            message: The HelpRequest to store.
            
        Returns:
            True if message was stored (new message),
            False if duplicate or expired.
        """
        with self._lock:
            # Check for duplicates using UUID
            if message.id in self._seen_ids:
                self._duplicates_rejected += 1
                logger.debug(f"Duplicate message rejected: {message.id}")
                return False
            
            # Check if message is already expired
            if message.is_expired():
                logger.debug(f"Expired message rejected: {message.id}")
                return False
            
            # Evict oldest messages if at capacity
            if len(self._messages) >= self._max_messages:
                self._evict_oldest()
            
            # Store the message
            self._messages[message.id] = message
            self._seen_ids.add(message.id)
            self._total_received += 1
            
            logger.info(f"Stored message: {message.id} (type: {message.request_type})")
            return True
    
    def has_seen(self, message_id: str) -> bool:
        """
        Check if a message ID has been seen before.
        
        This is used by the gossip protocol to avoid
        rebroadcasting messages we've already processed.
        """
        with self._lock:
            return message_id in self._seen_ids
    
    def get(self, message_id: str) -> Optional[HelpRequest]:
        """Retrieve a specific message by ID."""
        with self._lock:
            return self._messages.get(message_id)
    
    def get_all(self, include_expired: bool = False) -> List[HelpRequest]:
        """
        Retrieve all stored messages.
        
        Args:
            include_expired: If True, includes expired messages.
            
        Returns:
            List of HelpRequest messages, sorted by timestamp (newest first).
        """
        with self._lock:
            if include_expired:
                messages = list(self._messages.values())
            else:
                messages = [m for m in self._messages.values() if not m.is_expired()]
            
            return sorted(messages, key=lambda m: m.timestamp, reverse=True)
    
    def get_by_type(self, request_type: str) -> List[HelpRequest]:
        """Filter messages by request type."""
        with self._lock:
            return [
                m for m in self._messages.values()
                if m.request_type == request_type and not m.is_expired()
            ]
    
    def get_nearby(
        self,
        location: GeoLocation,
        radius_km: float = 10.0
    ) -> List[HelpRequest]:
        """
        Get messages within a certain radius of a location.
        
        This uses a simplified distance calculation (Haversine formula).
        In production, use proper spatial indexing for efficiency.
        
        Args:
            location: Center point for the search.
            radius_km: Search radius in kilometers.
            
        Returns:
            List of nearby HelpRequests, sorted by distance.
        """
        import math
        
        def haversine_distance(loc1: GeoLocation, loc2: GeoLocation) -> float:
            """Calculate distance between two points in kilometers."""
            R = 6371  # Earth's radius in km
            
            lat1, lon1 = math.radians(loc1.latitude), math.radians(loc1.longitude)
            lat2, lon2 = math.radians(loc2.latitude), math.radians(loc2.longitude)
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            
            return R * c
        
        with self._lock:
            nearby = []
            for msg in self._messages.values():
                if msg.is_expired():
                    continue
                distance = haversine_distance(location, msg.location)
                if distance <= radius_km:
                    nearby.append((distance, msg))
            
            # Sort by distance
            nearby.sort(key=lambda x: x[0])
            return [msg for _, msg in nearby]
    
    def cleanup_expired(self) -> int:
        """
        Remove expired messages from storage.
        
        Returns:
            Number of messages removed.
        """
        with self._lock:
            expired_ids = [
                msg_id for msg_id, msg in self._messages.items()
                if msg.is_expired()
            ]
            
            for msg_id in expired_ids:
                del self._messages[msg_id]
            
            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} expired messages")
            
            return len(expired_ids)
    
    def _evict_oldest(self) -> None:
        """Evict the oldest 10% of messages when at capacity."""
        if not self._messages:
            return
        
        # Sort by timestamp and remove oldest 10%
        sorted_msgs = sorted(
            self._messages.items(),
            key=lambda x: x[1].timestamp
        )
        
        evict_count = max(1, len(sorted_msgs) // 10)
        for msg_id, _ in sorted_msgs[:evict_count]:
            del self._messages[msg_id]
        
        logger.info(f"Evicted {evict_count} oldest messages due to capacity limit")
    
    def get_stats(self) -> dict:
        """Get storage statistics."""
        with self._lock:
            active_count = sum(1 for m in self._messages.values() if not m.is_expired())
            return {
                "total_stored": len(self._messages),
                "active_messages": active_count,
                "expired_messages": len(self._messages) - active_count,
                "total_received": self._total_received,
                "duplicates_rejected": self._duplicates_rejected,
                "seen_ids_count": len(self._seen_ids)
            }
    
    def clear(self) -> None:
        """Clear all stored messages (for testing)."""
        with self._lock:
            self._messages.clear()
            self._seen_ids.clear()
            logger.info("Storage cleared")


# Global storage instance
message_storage = MessageStorage()
