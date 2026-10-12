"""Content identity and concurrent persistence across all cache stores."""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from browser_cache import BrowserCache
from judgment_cache import JudgmentCache
from scan_cache import ScanCache


def test_same_size_and_timestamp_do_not_reuse_old_verdict(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("before")
    stamp = source.stat()
    cache = ScanCache(tmp_path / "cache.json")
    cache.put(str(source), {"verdict": "old"})
    source.write_text("after!")
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert cache.get(str(source)) is None


def test_result_is_bound_to_analyzed_snapshot(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("new text")
    cache = ScanCache(tmp_path / "cache.json")
    cache.put(str(source), {"verdict": "old"}, content="old text")
    assert cache.get(str(source)) is None
    assert cache.get(str(source), content="old text") == {"verdict": "old"}


def test_pipeline_invalidates_configuration_and_uses_snapshot(tmp_path, monkeypatch):
    import config
    import scan_cache
    from cli_impl.scanning import _split_unchanged, _store_unchanged
    from models import FileResult
    monkeypatch.setattr(scan_cache, "_cache", ScanCache(tmp_path / "cache.json"))
    args = SimpleNamespace(detector="none", categories=None, no_typography=False,
                           no_unicode=False, no_ignore=True, scope="content")
    result = FileResult(path=str(tmp_path / "source.txt"), blocks=[], raw_text="snapshot")
    _store_unchanged([result], [], args)
    assert _split_unchanged([result], args)[2] == 1
    args.no_unicode = True
    assert _split_unchanged([result], args)[2] == 0
    args.no_unicode = False
    monkeypatch.setattr(config, "APP_VERSION", "different-version")
    assert _split_unchanged([result], args)[2] == 0


@pytest.mark.parametrize("kind", ["scan", "browser", "judgment"])
def test_parallel_processes_merge_their_own_updates(tmp_path, kind):
    script = '''
import sys
from pathlib import Path
from types import SimpleNamespace
from scan_cache import ScanCache
from browser_cache import BrowserCache
from judgment_cache import JudgmentCache
root, kind, key = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
if kind == "scan":
    cache = ScanCache(root / "scan.json")
elif kind == "browser":
    cache = BrowserCache(SimpleNamespace(), [], directory=root)
else:
    cache = JudgmentCache("test", directory=root)
print("ready", flush=True)
sys.stdin.readline()
if kind == "scan":
    cache.put(key, {"value": key}, content=key)
elif kind == "browser":
    cache.put(key, SimpleNamespace(issues=[], html=key))
    cache.save()
else:
    cache.put(key, [{"value": key}])
    cache.save()
'''
    keys = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]
    processes = [subprocess.Popen([sys.executable, "-c", script, str(tmp_path), kind, key],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True) for key in keys]
    try:
        for process in processes:
            assert process.stdout.readline().strip() == "ready"
        for process in processes:
            process.stdin.write("go\n")
            process.stdin.flush()
        for process in processes:
            _, error = process.communicate(timeout=15)
            assert process.returncode == 0, error
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    assert len(json.loads(files[0].read_text())) == len(keys)
    assert not list(tmp_path.glob(".cache-*"))


def test_stale_writer_does_not_resurrect_cleared_entries(tmp_path):
    first = JudgmentCache("test", directory=tmp_path)
    first.put("old passage", [])
    first.save()
    stale = JudgmentCache("test", directory=tmp_path)
    first.clear()
    stale.put("new passage", [])
    stale.save()
    reread = JudgmentCache("test", directory=tmp_path)
    assert reread.get("old passage") is None
    assert reread.get("new passage") == []


def test_stale_save_does_not_overwrite_a_newer_verdict(tmp_path):
    first = JudgmentCache("test", directory=tmp_path)
    first.put("same passage", [{"score": 1}])
    first.save()
    stale = JudgmentCache("test", directory=tmp_path)
    first.put("same passage", [{"score": 2}])
    first.save()
    stale.put("other passage", [])
    stale.save()
    assert JudgmentCache("test", directory=tmp_path).get("same passage") == [{"score": 2}]


def test_browser_expiry_and_limit_apply_after_merge(tmp_path, monkeypatch):
    import browser_cache
    monkeypatch.setattr(browser_cache, "MAX_ENTRIES", 2)
    first = BrowserCache(SimpleNamespace(), [], directory=tmp_path)
    stale = BrowserCache(SimpleNamespace(), [], directory=tmp_path)
    for key in ("a", "b"):
        first.put(key, SimpleNamespace(issues=[]))
    first.save()
    stale.put("c", SimpleNamespace(issues=[]))
    stale.save()
    assert len(json.loads(first.path.read_text())) == 2
