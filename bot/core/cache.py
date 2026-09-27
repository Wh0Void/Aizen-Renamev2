"""
Dual-Tier Smart Memory & RAM Cache for Low-Memory Cloud Containers (Render / Koyeb).

Tier 1 — Bounded In-Memory LRU + TTL Cache (`LRUTTLCache` / `CacheManager`):
  - Caches MongoDB user documents (prefix, suffix, caption, thumbnail file_id,
    metadata, destination_channel, ban_status) with write-through updates.
  - Caches Force-Subscribe membership verification for 5 minutes.
  - Caches processed 320x320 JPEG thumbnails in RAM (`bytes`, capped at 16 MB total)
    so batch file renames never re-download or re-run Pillow on the same thumbnail.

Tier 2 — Smart RAM-Disk (`/dev/shm`) Router (`SmartRAMWorkspace`):
  - Uses Linux `/dev/shm` (in-memory tmpfs) for thumbnails and small files when
    sufficient container RAM is free, achieving zero-disk-I/O speed.
  - Automatically falls back to standard disk (`downloads/`) for large files
    (up to 2 GB) so 512 MB Render / Koyeb instances never hit OOM.
"""

from collections import OrderedDict
import logging
import os
import shutil
import sys
import threading
import time
from typing import Any, Dict, Optional, Tuple

from bot.core.fast_crypto import release_memory

logger = logging.getLogger(__name__)


class LRUTTLCache:
    """
    Bounded Least-Recently-Used (LRU) cache with monotonic Time-To-Live (TTL)
    and optional maximum byte budget enforcement.
    """

    def __init__(
        self,
        maxsize: int = 1024,
        ttl: float = 1800.0,
        max_bytes: Optional[int] = None,
        name: str = "cache",
    ) -> None:
        self.name = name
        self.maxsize = max(1, int(maxsize))
        self.ttl = float(ttl)
        self.max_bytes = max_bytes

        self._store: "OrderedDict[Any, Tuple[Any, float, int]]" = OrderedDict()
        self._current_bytes: int = 0
        self._lock = threading.RLock()

        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0

    @staticmethod
    def _estimate_size(value: Any) -> int:
        if isinstance(value, (bytes, bytearray, memoryview)):
            return len(value)
        if isinstance(value, str):
            return len(value.encode("utf-8", errors="ignore"))
        if isinstance(value, dict):
            return sum(
                LRUTTLCache._estimate_size(k) + LRUTTLCache._estimate_size(v)
                for k, v in value.items()
            ) + 64
        return 64

    def get(self, key: Any, default: Any = None) -> Any:
        """Retrieve item if present and not expired; updates LRU order."""
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self.misses += 1
                return default

            value, expires_at, size_bytes = entry
            if now >= expires_at:
                self._store.pop(key, None)
                self._current_bytes = max(0, self._current_bytes - size_bytes)
                self.misses += 1
                return default

            self._store.move_to_end(key)
            self.hits += 1
            if isinstance(value, dict):
                return dict(value)
            return value

    def set(self, key: Any, value: Any, ttl: Optional[float] = None) -> None:
        """Insert or update key with TTL and enforce item count + byte limits."""
        effective_ttl = self.ttl if ttl is None else float(ttl)
        expires_at = time.monotonic() + effective_ttl
        if isinstance(value, dict):
            value = dict(value)
        size_bytes = self._estimate_size(value)

        with self._lock:
            # Do not cache a single item larger than the entire byte budget
            if self.max_bytes is not None and size_bytes > self.max_bytes:
                return

            if key in self._store:
                _, _, old_size = self._store.pop(key)
                self._current_bytes = max(0, self._current_bytes - old_size)

            # Evict expired items first if near capacity
            if len(self._store) >= self.maxsize or (
                self.max_bytes is not None and self._current_bytes + size_bytes > self.max_bytes
            ):
                self._purge_expired_locked()

            # Evict oldest LRU entries until within maxsize and max_bytes
            while self._store and (
                len(self._store) >= self.maxsize
                or (
                    self.max_bytes is not None
                    and self._current_bytes + size_bytes > self.max_bytes
                )
            ):
                _, (_, _, evicted_size) = self._store.popitem(last=False)
                self._current_bytes = max(0, self._current_bytes - evicted_size)
                self.evictions += 1

            self._store[key] = (value, expires_at, size_bytes)
            self._current_bytes += size_bytes

    def update_dict_field(self, key: Any, field: str, field_value: Any) -> bool:
        """
        Write-through helper: if `key` is currently cached as a dict, update
        `field` in place without requiring a full DB reload.
        """
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            value, expires_at, old_size = entry
            if now >= expires_at or not isinstance(value, dict):
                self._store.pop(key, None)
                self._current_bytes = max(0, self._current_bytes - old_size)
                return False

            updated = dict(value)
            updated[field] = field_value
            new_size = self._estimate_size(updated)
            self._store[key] = (updated, time.monotonic() + self.ttl, new_size)
            self._store.move_to_end(key)
            self._current_bytes = max(0, self._current_bytes - old_size + new_size)
            return True

    def delete(self, key: Any) -> None:
        """Invalidate a specific key."""
        with self._lock:
            entry = self._store.pop(key, None)
            if entry is not None:
                _, _, old_size = entry
                self._current_bytes = max(0, self._current_bytes - old_size)

    def clear(self) -> None:
        """Clear all entries and reset byte counter."""
        with self._lock:
            self._store.clear()
            self._current_bytes = 0

    def _purge_expired_locked(self) -> int:
        now = time.monotonic()
        expired_keys = [k for k, (_, exp, _) in self._store.items() if now >= exp]
        for k in expired_keys:
            _, _, sz = self._store.pop(k)
            self._current_bytes = max(0, self._current_bytes - sz)
        return len(expired_keys)

    def stats(self) -> Dict[str, Any]:
        """Return cache metrics."""
        with self._lock:
            self._purge_expired_locked()
            total = self.hits + self.misses
            hit_rate = round((self.hits / total) * 100, 1) if total > 0 else 0.0
            return {
                "name": self.name,
                "items": len(self._store),
                "maxsize": self.maxsize,
                "size_kb": round(self._current_bytes / 1024, 1),
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate_pct": hit_rate,
            }


class SmartRAMWorkspace:
    """
    Smart RAM-Disk (`/dev/shm`) & Disk Workspace Router.

    - On Linux containers (Render / Koyeb), checks `/dev/shm` availability and
      live memory pressure.
    - Stores thumbnails and small files (`<= max_ram_file_mb`) in `/dev/shm`
      when sufficient free memory exists, eliminating slow container disk I/O.
    - Automatically routes large files (up to 2 GB) to standard disk (`downloads/`)
      so 512 MB containers never hit OOM.
    """

    def __init__(
        self,
        disk_dir: str = "downloads",
        shm_root: str = "/dev/shm/rename_bot_cache",
        max_ram_file_mb: int = int(os.environ.get("RAM_CACHE_MAX_MB", "40")),
        min_free_ram_mb: int = 160,
    ) -> None:
        self.disk_dir = os.path.abspath(disk_dir)
        self.shm_dir = shm_root
        self.max_ram_file_bytes = max(1, int(max_ram_file_mb)) * 1024 * 1024
        self.min_free_ram_bytes = max(64, int(min_free_ram_mb)) * 1024 * 1024

        os.makedirs(self.disk_dir, exist_ok=True)
        self.shm_available: bool = self._init_shm()

    def _init_shm(self) -> bool:
        if sys.platform.startswith("linux") and os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK):
            try:
                os.makedirs(self.shm_dir, exist_ok=True)
                return True
            except Exception as exc:
                logger.debug("Could not initialize /dev/shm workspace: %s", exc)
        return False

    def get_memory_info(self) -> Dict[str, float]:
        """Return process RSS and available system/container memory in MB."""
        rss_mb = 0.0
        avail_mb = 512.0
        try:
            import psutil  # type: ignore

            proc = psutil.Process(os.getpid())
            rss_mb = round(proc.memory_info().rss / (1024 * 1024), 1)
            vm = psutil.virtual_memory()
            avail_mb = round(vm.available / (1024 * 1024), 1)
        except Exception:
            pass
        return {"process_rss_mb": rss_mb, "available_ram_mb": avail_mb}

    def should_use_ram_disk(self, file_size_bytes: int = 0) -> bool:
        """
        Decide whether a file of `file_size_bytes` can safely be placed in `/dev/shm`
        without risking OOM on a 512 MB Render / Koyeb container.
        """
        if not self.shm_available:
            return False
        if file_size_bytes < 0 or file_size_bytes > self.max_ram_file_bytes:
            return False

        try:
            usage = shutil.disk_usage("/dev/shm")
            if usage.free < (file_size_bytes + self.min_free_ram_bytes // 2):
                return False
        except Exception:
            return False

        mem = self.get_memory_info()
        # Keep at least min_free_ram_mb headroom and keep process RSS under 340 MB
        if mem["process_rss_mb"] > 340.0:
            return False
        if mem["available_ram_mb"] < (file_size_bytes / (1024 * 1024)) + (self.min_free_ram_bytes / (1024 * 1024)):
            return False

        return True

    def resolve_transfer_path(self, filename: str, file_size_bytes: int = 0) -> str:
        """
        Return an absolute file path inside `/dev/shm` (for small files/thumbnails)
        or `downloads/` (for large files up to 2 GB).
        """
        safe_name = os.path.basename(filename) or f"file_{int(time.time())}"
        base_dir = self.shm_dir if self.should_use_ram_disk(file_size_bytes) else self.disk_dir
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, safe_name)

    def resolve_thumb_path(self, name: str) -> str:
        """Return optimal path for temporary thumbnail processing."""
        safe_name = os.path.basename(name) or f"thumb_{int(time.time())}.jpg"
        base_dir = self.shm_dir if self.shm_available else self.disk_dir
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, safe_name)

    @staticmethod
    def cleanup_files(*paths: Optional[str]) -> None:
        """Safely remove temporary files/directories and trigger OS memory release."""
        for path in paths:
            if not path:
                continue
            try:
                if os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
            except Exception as exc:
                logger.debug("Cleanup ignored for %s: %s", path, exc)
        release_memory()


class CacheManager:
    """
    Central coordinator for all in-memory LRU/TTL caches and `/dev/shm` workspace.
    """

    def __init__(self) -> None:
        user_ttl = float(os.environ.get("USER_CACHE_TTL", "1800"))
        # 1. User settings & ban status cache (max 1024 users, 30 min TTL)
        self.user_cache = LRUTTLCache(
            maxsize=1024,
            ttl=user_ttl,
            max_bytes=8 * 1024 * 1024,  # 8 MB max
            name="user_db_cache",
        )
        # 2. Force-Sub verification cache (max 2048 users, 5 min TTL)
        self.fsub_cache = LRUTTLCache(
            maxsize=2048,
            ttl=300.0,
            max_bytes=2 * 1024 * 1024,  # 2 MB max
            name="force_sub_cache",
        )
        # 3. Processed 320x320 JPEG thumbnail bytes cache (max 64 thumbs or 16 MB RAM)
        self.thumb_cache = LRUTTLCache(
            maxsize=64,
            ttl=user_ttl,
            max_bytes=16 * 1024 * 1024,  # 16 MB max
            name="thumbnail_ram_cache",
        )
        # 4. Total users count cache (60s TTL for fast /status & /users)
        self.stats_cache = LRUTTLCache(
            maxsize=16,
            ttl=60.0,
            name="stats_cache",
        )

    def clear_all(self) -> None:
        """Flush all in-memory caches and trim heap memory."""
        self.user_cache.clear()
        self.fsub_cache.clear()
        self.thumb_cache.clear()
        self.stats_cache.clear()
        release_memory()

    def get_summary(self) -> Dict[str, Any]:
        """Return combined cache and memory telemetry for `/status`."""
        return {
            "user_cache": self.user_cache.stats(),
            "fsub_cache": self.fsub_cache.stats(),
            "thumb_cache": self.thumb_cache.stats(),
            "memory": ram_workspace.get_memory_info(),
            "shm_enabled": ram_workspace.shm_available,
        }


ram_workspace = SmartRAMWorkspace()
cache_manager = CacheManager()
