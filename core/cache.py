"""
Deduplication cache with TTL support.
Prevents duplicate alerts within time window.
"""
import time
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DeduplicationCache:
    """
    Time-based deduplication cache.
    
    Stores dedup keys with timestamps and expires them after TTL.
    Thread-safe for single-threaded async usage.
    """
    
    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live for cache entries (default 5 minutes)
        """
        self._cache: Dict[str, float] = {}
        self._ttl = ttl_seconds
    
    def _cleanup(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, v in self._cache.items() if now - v > self._ttl]
        for k in expired:
            del self._cache[k]
    
    def is_duplicate(self, key: str) -> bool:
        """
        Check if key exists in cache (not expired).
        
        Args:
            key: Deduplication key (e.g., "city_threattype")
            
        Returns:
            True if duplicate (already seen within TTL)
        """
        if not key:
            return False
        
        self._cleanup()
        
        if key in self._cache:
            age = int(time.time() - self._cache[key])
            logger.debug(f"Duplicate found: {key} (age: {age}s)")
            return True
        
        return False
    
    def add(self, key: str) -> None:
        """
        Add key to cache with current timestamp.
        
        Args:
            key: Deduplication key
        """
        if key:
            self._cache[key] = time.time()
            logger.debug(f"Added to cache: {key}")
    
    def check_and_add(self, key: str) -> bool:
        """
        Atomic check-and-add operation.
        
        Args:
            key: Deduplication key
            
        Returns:
            True if was duplicate (key existed), False if new (key added)
        """
        if self.is_duplicate(key):
            return True
        self.add(key)
        return False
    
    def clear(self) -> None:
        """Clear all entries."""
        self._cache.clear()
    
    @property
    def size(self) -> int:
        """Current cache size."""
        self._cleanup()
        return len(self._cache)
    
    def get_age(self, key: str) -> Optional[int]:
        """Get age of cached entry in seconds, or None if not found."""
        if key in self._cache:
            return int(time.time() - self._cache[key])
        return None
