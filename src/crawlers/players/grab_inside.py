"""Grab 'Inside Grab' blog (https://www.grab.com/inside-grab/)."""
from __future__ import annotations

import re

from src.crawlers.players._spa import PlayerBlogCrawler


class GrabInsideBlog(PlayerBlogCrawler):
    name = "grab_inside"
    base_url = "https://www.grab.com/inside-grab/"
    domain_prefix = "https://www.grab.com"
    url_substring = "/inside-grab/"
    article_url_re = re.compile(r"/inside-grab/[a-z0-9\-]{6,}")
    block_paths = {"/inside-grab"}
    scope = "international"
    player = "Grab"
