"""Cache for scan results to avoid re-scanning unchanged files.

Stores scan results keyed by file path + content hash. When a file
hasn't changed, the cached result is returned instead of re-scanning.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


# Default cache location
CACHE_DIR = Path.home() / ".config" / "xanalyze" / "cache"
CACHE_FILE = CACHE_DIR / "scan_cache.json"


def _content_hash(text: str) -> str:
    """Fast hash of file content."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:16]


def _file_hash(path: str) -> str:
    """Hash of file path + modification time."""
    try:
        stat = os.stat(path)
        key = f"{path}:{stat.st_mtime}:{stat.st_size}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()[:16]
    except OSError:
        return ""


class ScanCache:
    """Cache for scan results."""
    
    def __init__(self, cache_path: Path | None = None):
        self.cache_path = cache_path or CACHE_FILE
        self._cache: dict[str, Any] = {}
        self._load()
    
    def _load(self) -> None:
        """Load cache from disk."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path) as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._cache = {}
    
    def _save(self) -> None:
        """Save cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump(self._cache, f, indent=2, ensure_ascii=False)
    
    def get(self, file_path: str) -> dict | None:
        """Get cached result for a file, or None if not cached / changed."""
        file_key = _file_hash(file_path)
        if not file_key:
            return None
        
        cached = self._cache.get(file_path)
        if not cached:
            return None
        
        if cached.get("hash") != file_key:
            return None
        
        return cached.get("result")
    
    def put(self, file_path: str, result: dict, *, save: bool = True) -> None:
        """Cache a scan result for a file.

        `save=False` keeps the entry in memory only, for a caller writing
        many entries in one pass: saving flushes the whole cache file, so a
        repository of four thousand files meant four thousand full rewrites
        of it. Such a caller must call `save()` when it is done - see
        `cli_impl.scanning._store_unchanged`.
        """
        file_key = _file_hash(file_path)
        if not file_key:
            return

        self._cache[file_path] = {
            "hash": file_key,
            "result": result,
        }
        if save:
            self._save()

    def save(self) -> None:
        """Flush the cache to disk. For callers that used `put(save=False)`."""
        self._save()
    
    def invalidate(self, file_path: str) -> None:
        """Remove a file from the cache."""
        self._cache.pop(file_path, None)
        self._save()
    
    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache = {}
        self._save()
    
    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "entries": len(self._cache),
            "size_bytes": self.cache_path.stat().st_size if self.cache_path.exists() else 0,
        }


# Global cache instance
_cache: ScanCache | None = None


def get_cache() -> ScanCache:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        _cache = ScanCache()
    return _cache
