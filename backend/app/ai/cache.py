import threading
from collections import OrderedDict
from typing import Optional, Tuple

class AICache:
    """Memory cache to avoid hitting the DB for high-frequency identical AI requests."""

    def __init__(self, max_size: int = 1000):
        # OrderedDict used to efficiently evict oldest entries (LRU-like cache based on insertion order)
        self.cache: OrderedDict[Tuple[str, str], dict] = OrderedDict()
        self.max_size = max_size
        self.lock = threading.Lock()

    def get(self, organization_id: str, request_hash: str) -> Optional[dict]:
        key = (organization_id, request_hash)
        with self.lock:
            if key in self.cache:
                return self.cache[key]
        return None

    def set(self, organization_id: str, request_hash: str, result_dict: dict) -> None:
        key = (organization_id, request_hash)
        with self.lock:
            if key in self.cache:
                # Move to end if updating
                del self.cache[key]
            elif len(self.cache) >= self.max_size:
                # Evict oldest entry (first item in ordered dict)
                self.cache.popitem(last=False)
            self.cache[key] = result_dict

_memory_cache = AICache()
