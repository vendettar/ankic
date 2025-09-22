"""Caching engine (memory + disk, layered) with stats and TTL.

Provides:
- CacheStrategy protocol
- MemoryCache, DiskCache, LayeredCache
- CacheEngine (public engine facade)
"""

import hashlib
import json
import pickle
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol, cast, runtime_checkable

from ..config.settings import settings
from ..exceptions import CacheError
from ..logging_config import get_logger
from ..models.cache_models import CacheConfig, CacheEntry, CacheStats
from ..utils.error_handler import handle_errors

logger = get_logger(__name__)


@runtime_checkable
class CacheStrategy(Protocol):
    """Protocol for cache implementation strategies"""

    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, ttl: int | None = None) -> None: ...

    def delete(self, key: str) -> bool: ...

    def clear(self) -> None: ...

    def keys(self) -> list[str]: ...

    def size(self) -> int: ...


class MemoryCache(CacheStrategy):
    def __init__(self, max_size: int = 1000):
        self._cache: dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired():
                entry.touch()
                return entry.data
            elif entry:
                del self._cache[key]
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_lru()

            expires_at = None
            if ttl:
                expires_at = datetime.now() + timedelta(seconds=ttl)

            self._cache[key] = CacheEntry(key=key, data=value, expires_at=expires_at)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._cache.keys())

    def size(self) -> int:
        with self._lock:
            total_size = 0
            for entry in self._cache.values():
                try:
                    total_size += len(pickle.dumps(entry.data))
                except Exception:
                    total_size += len(str(entry.data)) * 2
            return total_size

    def _evict_lru(self) -> None:
        if not self._cache:
            return
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[lru_key]


class DiskCache(CacheStrategy):
    def __init__(self, cache_dir: Path, max_size_mb: int = 100):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._index_file = self.cache_dir / "cache_index.json"
        self._index: dict[str, dict[str, Any]] = self._load_index()
        self._lock = threading.RLock()

    def _load_index(self) -> dict[str, dict[str, Any]]:
        try:
            if self._index_file.exists():
                with open(self._index_file, encoding="utf-8") as f:
                    data = json.load(f)
                    return cast(dict[str, dict[str, Any]], data)
        except Exception as e:
            logger.warning(f"Failed to load cache index: {e}")
        return {}

    def _save_index(self) -> None:
        try:
            with open(self._index_file, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cache index: {e}")

    def _hash_key(self, key: str) -> str:
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def _get_file_path(self, key: str) -> Path:
        key_hash = self._hash_key(key)
        return self.cache_dir / f"{key_hash}.cache"

    def get(self, key: str) -> Any | None:
        with self._lock:
            try:
                meta = self._index.get(key)
                if not meta:
                    return None

                exp = meta.get("expires_at")
                if exp and datetime.fromisoformat(exp) < datetime.now():
                    # Expired: delete and return None
                    self.delete(key)
                    return None

                file_path = self._get_file_path(key)
                if not file_path.exists():
                    self._index.pop(key, None)
                    self._save_index()
                    return None

                with open(file_path, "rb") as f:
                    try:
                        value = pickle.load(f)
                    except Exception:
                        # Fallback to JSON for simple structures
                        f.seek(0)
                        value = json.loads(f.read().decode("utf-8"))

                # Update last accessed
                meta["last_accessed"] = datetime.now().isoformat()
                self._save_index()
                return value

            except Exception as e:
                logger.warning(f"Cache get failed for {key}: {e}")
                return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        with self._lock:
            try:
                file_path = self._get_file_path(key)
                with open(file_path, "wb") as f:
                    try:
                        pickle.dump(value, f)
                    except Exception:
                        f.close()
                        with open(file_path, "w", encoding="utf-8") as jf:
                            json.dump(value, jf, ensure_ascii=False)

                metadata: dict[str, Any] = {
                    "created_at": datetime.now().isoformat(),
                    "last_accessed": datetime.now().isoformat(),
                    "file_size": file_path.stat().st_size,
                }
                if ttl:
                    metadata["expires_at"] = (
                        datetime.now() + timedelta(seconds=ttl)
                    ).isoformat()

                self._index[key] = metadata
                self._save_index()
                self._enforce_size_limit()

            except Exception as e:
                logger.error(f"Failed to cache entry {key}: {e}")
                raise CacheError("set", "disk", e) from e

    def delete(self, key: str) -> bool:
        with self._lock:
            if key not in self._index:
                return False
            try:
                fp = self._get_file_path(key)
                if fp.exists():
                    fp.unlink()
                del self._index[key]
                self._save_index()
                return True
            except Exception as e:
                logger.warning(f"Failed to delete cache entry {key}: {e}")
                return False

    def clear(self) -> None:
        with self._lock:
            try:
                for cache_file in self.cache_dir.glob("*.cache"):
                    cache_file.unlink()
                self._index.clear()
                self._save_index()
            except Exception as e:
                logger.error(f"Failed to clear cache: {e}")

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._index.keys())

    def size(self) -> int:
        with self._lock:
            return sum(m.get("file_size", 0) for m in self._index.values())

    def _enforce_size_limit(self) -> None:
        current_size = self.size()
        if current_size <= self.max_size_bytes:
            return
        sorted_keys = sorted(
            self._index.keys(),
            key=lambda k: self._index[k].get("last_accessed", "1970-01-01"),
        )
        for key in sorted_keys:
            if self.size() <= self.max_size_bytes * 0.8:
                break
            self.delete(key)


class LayeredCache(CacheStrategy):
    def __init__(self, memory_cache: CacheStrategy, disk_cache: CacheStrategy):
        self.memory_cache: CacheStrategy = memory_cache
        self.disk_cache: CacheStrategy = disk_cache
        self._lock = threading.RLock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            value = self.memory_cache.get(key)
            if value is not None:
                return value
            value = self.disk_cache.get(key)
            if value is not None:
                self.memory_cache.set(key, value)
                return value
            return None

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        with self._lock:
            self.memory_cache.set(key, value, ttl)
            self.disk_cache.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        with self._lock:
            mem_deleted = self.memory_cache.delete(key)
            disk_deleted = self.disk_cache.delete(key)
            return mem_deleted or disk_deleted

    def clear(self) -> None:
        with self._lock:
            self.memory_cache.clear()
            self.disk_cache.clear()

    def keys(self) -> list[str]:
        with self._lock:
            all_keys = set(self.memory_cache.keys())
            all_keys.update(self.disk_cache.keys())
            return list(all_keys)

    def size(self) -> int:
        with self._lock:
            return self.disk_cache.size()


class CacheEngine:
    def __init__(self, config: CacheConfig, cache_dir: Path | None = None):
        self.config = config
        self.cache_dir = cache_dir or Path(".cache")
        memory_cache: CacheStrategy = MemoryCache(max_size=1000)
        if getattr(settings, "cache", None) and getattr(
            settings.cache, "disable_disk", False
        ):
            # Use in-memory cache only to avoid filesystem IO in tests/CI
            disk_cache: CacheStrategy = MemoryCache(max_size=1000)
        else:
            disk_cache = DiskCache(self.cache_dir, config.max_size_mb)
        self.cache = LayeredCache(memory_cache, disk_cache)

        self._stats = CacheStats(
            total_entries=0,
            valid_entries=0,
            expired_entries=0,
            cache_size_mb=0.0,
            hit_rate=0.0,
            last_cleanup=None,
        )
        self._hits = 0
        self._misses = 0

    @handle_errors(default_return=None, operation_name="cache_get")
    def get(self, key: str) -> Any | None:
        value = self.cache.get(key)
        if value is not None:
            self._hits += 1
        else:
            self._misses += 1
        return value

    @handle_errors(operation_name="cache_set")
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl or (self.config.ttl_days * 24 * 3600)
        self.cache.set(key, value, ttl)

    @handle_errors(default_return=False, operation_name="cache_delete")
    def delete(self, key: str) -> bool:
        return self.cache.delete(key)

    @handle_errors(operation_name="cache_clear")
    def clear(self) -> None:
        self.cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> CacheStats:
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
        keys = self.cache.keys()
        size_mb = self.cache.size() / (1024 * 1024)
        return CacheStats(
            total_entries=len(keys),
            valid_entries=len(keys),
            expired_entries=0,
            cache_size_mb=size_mb,
            hit_rate=hit_rate,
            last_cleanup=None,
        )

    @handle_errors(operation_name="cache_cleanup")
    def cleanup_expired(self) -> int:
        return 0

    def get_cache_key(self, word: str) -> str:
        return hashlib.md5(word.lower().encode()).hexdigest()

    # Convenience for higher-level facades
    def get_cached_word_info(self, word: str) -> dict[str, Any] | None:
        key = self.get_cache_key(word)
        return self.get(key)

    def cache_word_info(self, word: str, word_info: dict[str, Any]) -> None:
        key = self.get_cache_key(word)
        self.set(key, word_info)
