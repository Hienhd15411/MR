"""Shopee / TikTok Shop seller-blog crawlers."""
from __future__ import annotations

import re

from src.crawlers.players._spa import PlayerBlogCrawler


class ShopeeSellerBlog(PlayerBlogCrawler):
    name = "shopee_seller_blog"
    base_url = "https://banhang.shopee.vn/edu/category?sub_cat_id=1006"
    # Other Seller-Education sub-categories also carry recent posts
    # (ids confirmed from the live category nav).
    list_urls = [
        "https://banhang.shopee.vn/edu/category?sub_cat_id=1109",
        "https://banhang.shopee.vn/edu/category?sub_cat_id=1110",
        "https://banhang.shopee.vn/edu/category?sub_cat_id=1206",
        "https://banhang.shopee.vn/edu/category?sub_cat_id=1209",
        "https://banhang.shopee.vn/edu/category?sub_cat_id=1278",
        "https://banhang.shopee.vn/edu/category?sub_cat_id=1404",
    ]
    domain_prefix = "https://banhang.shopee.vn"
    # Links are root-relative ("/edu/article/16440"); match on the path,
    # not the absolute domain, or every article gets rejected.
    url_substring = "/edu/"
    article_url_re = re.compile(r"/edu/article/\d+")
    block_paths: set[str] = set()
    force_playwright = True
    needs_scroll = True
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
