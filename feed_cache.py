#!/usr/bin/env python3
"""
直近の記事 URL を取得し、WP キャッシュを生成する。

WordPress REST API から記事リンクを取得する（RSS feed は10件上限のため使用しない）。
"""

import datetime
import os
import re
import socket
import sys
import time

import requests

if os.environ.get("POPULAR_PAGE_DOMAIN"):
    HOST = os.environ["POPULAR_PAGE_DOMAIN"]
elif "test" in sys.argv[1:]:
    HOST = "test.gekiyasutokka.com"
else:
    HOST = "gekiyasutokka.com"
BASE_URL = f"https://{HOST}"
POST_LIMIT = 50
POSTS_API_URL = f"{BASE_URL}/wp-json/wp/v2/posts"
ARTICLE_URL_PATTERN = re.compile(rf"^https://{re.escape(HOST)}/\d{{4}}/\d{{2}}/\d{{2}}/")
SLOW_THRESHOLD = 0.5


def log(msg: str) -> None:
    now = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    print(f"【feed-cache {now}】 {msg}")


def enable_local_resolve() -> socket.getaddrinfo:
    original_getaddrinfo = socket.getaddrinfo

    def local_getaddrinfo(host, *args, **kwargs):
        if host == HOST:
            return original_getaddrinfo("127.0.0.1", *args, **kwargs)
        return original_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = local_getaddrinfo
    return original_getaddrinfo


def fetch_article_urls(session: requests.Session, limit: int = POST_LIMIT) -> list[str]:
    response = session.get(
        POSTS_API_URL,
        params={"per_page": limit, "_fields": "link"},
        timeout=15,
    )
    response.raise_for_status()
    posts = response.json()
    urls = []
    for post in posts:
        url = post.get("link", "").strip()
        if ARTICLE_URL_PATTERN.match(url):
            urls.append(url)
    return list(dict.fromkeys(urls))


def warm_cache(session: requests.Session, urls: list[str]) -> None:
    slow_num = 0
    for url in urls:
        start = time.time()
        response = session.get(url, timeout=30)
        elapsed = time.time() - start
        if elapsed >= SLOW_THRESHOLD:
            slow_num += 1
            log(f"{response.status_code} {elapsed:.3f} {url}")
    log(f"done: {len(urls)} urls, slow={slow_num}")


def main() -> None:
    original_getaddrinfo = enable_local_resolve()
    try:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                ),
            }
        )

        log(f"fetch posts: {POSTS_API_URL} (limit={POST_LIMIT})")
        urls = fetch_article_urls(session)
        log(f"article urls: {len(urls)}")
        warm_cache(session, urls)
    finally:
        socket.getaddrinfo = original_getaddrinfo


if __name__ == "__main__":
    main()
