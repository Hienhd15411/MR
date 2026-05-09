"""Shopee / TikTok Shop seller-blog crawlers."""
from __future__ import annotations

import re

from src.crawlers.players._spa import PlayerBlogCrawler


class ShopeeSellerBlog(PlayerBlogCrawler):
    name = "shopee_seller_blog"
    base_url = "https://banhang.shopee.vn/edu/category?sub_cat_id=1006"
    domain_prefix = "https://banhang.shopee.vn"
    url_substring = "banhang.shopee.vn/"
    article_url_re = re.compile(r"banhang\.shopee\.vn/edu/article/\d+")
    block_paths: set[str] = set()
    player = "Shopee"


class TikTokShopSellerBlog(PlayerBlogCrawler):
    name = "tiktokshop_seller_blog"
    base_url = "https://seller-vn.tiktok.com/university/essay?knowledge_id=8858869405370113"
    domain_prefix = "https://seller-vn.tiktok.com"
    url_substring = "seller-vn.tiktok.com/"
    article_url_re = re.compile(r"seller-vn\.tiktok\.com/university/essay/\d+|"
                                r"seller-vn\.tiktok\.com/university/article/\d+")
    block_paths: set[str] = set()
    player = "TikTokShop"
