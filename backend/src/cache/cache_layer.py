"""Blindspot — Cache Layer

Similarity-based caching for LLM responses.
Supports disk persistence for demo fallback reliability.
"""

import json
import hashlib
import os
import logging
from typing import Dict, Any, Optional
from src.config import settings, DATA_DIR

logger = logging.getLogger(__name__)

class CacheLayer:
    """Handles similarity-based caching for LLM responses."""

    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_dir = os.path.join(DATA_DIR, "demo_contracts")
        os.makedirs(self.cache_dir, exist_ok=True)
        self._load_cache()

    def _load_cache(self):
        """Load all cached responses from disk."""
        if not os.path.exists(self.cache_dir):
            return
            
        for filename in os.listdir(self.cache_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.cache_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "key" in data and "response" in data:
                            self.cache[data["key"]] = data["response"]
                except Exception as e:
                    logger.warning(f"Failed to load cache from {filename}: {e}")

    def get_cache_key(self, inputs: Dict[str, Any]) -> str:
        """Generate cache key from inputs."""
        key_str = json.dumps(inputs, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get_cached_response(
        self,
        cache_key: str,
        similarity_threshold: float = 0.95
    ) -> Optional[str]:
        """Get cached response if available."""
        # For now, we do exact match on the cache_key (MD5 hash).
        return self.cache.get(cache_key)

    def set_cached_response(self, cache_key: str, response: str, prefix: str = "cache"):
        """Cache a response to memory and disk."""
        self.cache[cache_key] = response
        
        # Persist to disk
        filename = f"{prefix}_{cache_key[:8]}.json"
        path = os.path.join(self.cache_dir, filename)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "key": cache_key,
                    "response": response
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist cache to {filename}: {e}")

# Global instance
global_cache = CacheLayer()
