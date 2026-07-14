"""Targeted tests for bounded temporary cache behavior."""

from __future__ import annotations

from data_viewer.infrastructure.cache import BoundedCache, CacheLimits


def test_cache_put_get_updates_access_time_and_counts(tmp_path) -> None:
    cache_root = tmp_path / "cache"
    cache = BoundedCache(root=cache_root, limits=CacheLimits(1024 * 1024, 10, 3600))

    path = cache.put_bytes("sample", b"abc")
    assert path.exists()
    assert cache.count == 1
    assert cache.current_bytes == 3

    cached = cache.get("sample")
    assert cached == path
    assert cached.exists()


def test_cache_enforces_entry_and_byte_budgets(tmp_path) -> None:
    cache = BoundedCache(
        root=tmp_path / "budget",
        limits=CacheLimits(max_total_bytes=20, max_entry_count=2, max_entry_age_seconds=3600),
    )

    cache.put_bytes("k1", b"11111111")
    cache.put_bytes("k2", b"2222")
    cache.put_bytes("k3", b"3333")

    # k1 should be evicted first by LRU policy to satisfy entry cap.
    assert cache.get("k1") is None
    assert cache.get("k2") is not None
    assert cache.get("k3") is not None
    assert cache.count <= 2
    assert cache.current_bytes <= 20


def test_cache_removes_expired_entries(tmp_path) -> None:
    now = [2000000.0]

    def clock() -> float:
        return now[0]

    cache = BoundedCache(
        root=tmp_path / "age",
        limits=CacheLimits(1024, 10, 1),
        clock=clock,
    )

    cache.put_bytes("a", b"payload")
    assert cache.get("a") is not None

    now[0] += 2
    assert cache.get("a") is None
    assert cache.count == 0


def test_cleanup_reports_and_rewrites_index(tmp_path) -> None:
    cache = BoundedCache(
        root=tmp_path / "persist",
        limits=CacheLimits(1024 * 1024, 10, 3600),
    )
    path = cache.put_bytes("persist", b"data")
    assert path.exists()

    cache.write_tombstone(reason="test")
    tombstone = cache.root / "cache-tombstone.json"
    assert tombstone.exists()

    # Restarted cache should load persisted index and still return the entry.
    reloaded = BoundedCache(root=tmp_path / "persist", limits=CacheLimits(1024 * 1024, 10, 3600))
    assert reloaded.get("persist") == path

    assert reloaded.current_bytes >= 4
