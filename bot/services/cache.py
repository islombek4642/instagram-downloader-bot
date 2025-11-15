import asyncio
import time
from typing import Dict, List, Optional, Tuple


class SimpleCache:
    """Instagram media uchun oddiy in-memory kesh tizimi."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[List[str], float]] = {}
        self._access_times: Dict[str, float] = {}
    
    def get(self, key: str) -> Optional[List[str]]:
        """Keshdan qiymat olish."""
        if key not in self._cache:
            return None
        
        media_urls, timestamp = self._cache[key]
        current_time = time.time()
        
        # TTL tekshirish
        if current_time - timestamp > self.ttl_seconds:
            self._remove(key)
            return None
        
        # Access time yangilash (LRU uchun)
        self._access_times[key] = current_time
        return media_urls
    
    def set(self, key: str, value: List[str]) -> None:
        """Keshga qiymat qo'yish."""
        current_time = time.time()
        
        # Agar kesh to'lgan bo'lsa, eng kam ishlatilgan elementni o'chirish
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_lru()
        
        self._cache[key] = (value, current_time)
        self._access_times[key] = current_time
    
    def _remove(self, key: str) -> None:
        """Keshdan element o'chirish."""
        self._cache.pop(key, None)
        self._access_times.pop(key, None)
    
    def _evict_lru(self) -> None:
        """Eng kam ishlatilgan elementni keshdan o'chirish."""
        if not self._access_times:
            return
        
        # Eng kam ishlatilgan kalitni topish
        lru_key = min(self._access_times.keys(), key=lambda k: self._access_times[k])
        self._remove(lru_key)
    
    def clear(self) -> None:
        """Keshni tozalash."""
        self._cache.clear()
        self._access_times.clear()
    
    def stats(self) -> Dict[str, int]:
        """Kesh statistikasi."""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
        }


# Global kesh instance
_media_cache = SimpleCache(max_size=100, ttl_seconds=1800)  # 30 daqiqa


def get_cached_media(instagram_url: str) -> Optional[List[str]]:
    """Instagram URL uchun keshlangan media olish."""
    return _media_cache.get(instagram_url)


def cache_media(instagram_url: str, media_urls: List[str]) -> None:
    """Instagram media ni keshga saqlash."""
    if media_urls:  # Faqat bo'sh bo'lmagan ro'yxatlarni keshlash
        _media_cache.set(instagram_url, media_urls)


def clear_cache() -> None:
    """Keshni tozalash."""
    _media_cache.clear()


def get_cache_stats() -> Dict[str, int]:
    """Kesh statistikasi."""
    return _media_cache.stats()
