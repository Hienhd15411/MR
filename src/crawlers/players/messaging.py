"""WhatsApp / Telegram blog crawlers — international messaging players."""
from __future__ import annotations

import re

from src.crawlers.players._spa import PlayerBlogCrawler


class WhatsAppBlog(PlayerBlogCrawler):
    name = "whatsapp_blog"
    base_url = "https://blog.whatsapp.com/"
    domain_prefix = "https://blog.whatsapp.com"
    url_substring = "blog.whatsapp.com/"
    # WhatsApp blog post URLs: /<slug-or-id>
    article_url_re = re.compile(r"blog\.whatsapp\.com/[a-z0-9\-]{8,}")
    block_paths = {"/", "/feed", "/feed/"}
    scope = "international"
    player = "WhatsApp"


class TelegramBlog(PlayerBlogCrawler):
    name = "telegram_blog"
    base_url = "https://telegram.org/blog"
    domain_prefix = "https://telegram.org"
    url_substring = "/blog/"
    # Telegram blog post URLs: /blog/<slug>
    article_url_re = re.compile(r"/blog/[a-z0-9\-]{4,}")
    block_paths = {"/blog"}
    scope = "international"
    player = "Telegram"
