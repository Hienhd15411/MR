"""Zalo / Zalopay / Zalo OA player crawlers."""
from __future__ import annotations

import re

from src.crawlers.players._spa import PlayerBlogCrawler


class ZaloPayNews(PlayerBlogCrawler):
    name = "zalopay_news"
    base_url = "https://zalopay.vn/tin-tuc"
    domain_prefix = "https://zalopay.vn"
    url_substring = "/tin-tuc/"
    # Article URLs: /tin-tuc/<slug>; section landing is /tin-tuc itself
    article_url_re = re.compile(r"/tin-tuc/[a-z0-9\-]{6,}")
    block_paths = {"/tin-tuc"}
    player = "Zalo"


class ZaloPayPromo(PlayerBlogCrawler):
    name = "zalopay_promo"
    base_url = "https://zalopay.vn/khuyen-mai"
    domain_prefix = "https://zalopay.vn"
    url_substring = "/khuyen-mai/"
    article_url_re = re.compile(r"/khuyen-mai/[a-z0-9\-]{6,}")
    block_paths = {"/khuyen-mai"}
    player = "Zalo"


class ZaloOANews(PlayerBlogCrawler):
    name = "zalo_oa_news"
    base_url = "https://oa.zalo.me/home/resources/news"
    domain_prefix = "https://oa.zalo.me"
    url_substring = "/news/"
    article_url_re = re.compile(r"/news/[a-z0-9\-]{6,}")
    block_paths = {"/home/resources/news", "/news"}
    player = "Zalo"
