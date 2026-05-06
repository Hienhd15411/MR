"""Pytest config — disable HTTP cache so test fixtures are deterministic."""
import os

os.environ.setdefault("CRAWL_CACHE", "0")
