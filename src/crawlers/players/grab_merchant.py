"""Grab Merchant Vietnam blog (companion to Grab Passenger blog)."""
from __future__ import annotations

import re

from src.crawlers.players._spa import PlayerBlogCrawler


class GrabMerchantVNBlog(PlayerBlogCrawler):
    name = "grab_merchant_vn"
    base_url = "https://merchant.grab.com/vn-vn/blog"
    domain_prefix = "https://merchant.grab.com"
    url_substring = "/vn-vn/blog/"
    article_url_re = re.compile(r"/vn-vn/blog/[a-z0-9\-]{6,}")
    block_paths = {"/vn-vn/blog"}
    player = "Grab"
