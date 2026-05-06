import os
import time

import pytest

from src.utils import cache as html_cache


@pytest.fixture
def cache_on(monkeypatch):
    monkeypatch.setenv("CRAWL_CACHE", "1")
    yield
    # cleanup
    html_cache.clear()


def test_cache_round_trip(cache_on):
    url = "https://example.com/test-cache"
    assert html_cache.read(url) is None
    html_cache.write(url, "<html>hello</html>")
    assert html_cache.read(url) == "<html>hello</html>"


def test_cache_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("CRAWL_CACHE", "0")
    url = "https://example.com/disabled"
    html_cache.write(url, "<html>x</html>")
    assert html_cache.read(url) is None


def test_cache_expires_after_ttl(cache_on, monkeypatch):
    url = "https://example.com/ttl"
    html_cache.write(url, "<html>old</html>")
    # Pretend the file was written 25h ago
    p = html_cache._path_for(url)
    old = time.time() - (25 * 3600)
    os.utime(p, (old, old))
    assert html_cache.read(url) is None
