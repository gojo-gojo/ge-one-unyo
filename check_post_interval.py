#!/usr/bin/env python3
"""gekiyasutokka.com の最新記事投稿からの経過秒数を出力する。"""

import re
import socket
import sys
import urllib.request
from datetime import datetime

DOMAIN = 'gekiyasutokka.com'
URL = f'https://{DOMAIN}/'
ENTRY_DATE_PATTERN = re.compile(
    r'<span class="entry-date">\s*'
    r'(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2})時(\d{1,2})分'
)


def fetch_homepage() -> str:
    original_getaddrinfo = socket.getaddrinfo

    def local_getaddrinfo(host, *args, **kwargs):
        if host == DOMAIN:
            return original_getaddrinfo('127.0.0.1', *args, **kwargs)
        return original_getaddrinfo(host, *args, **kwargs)

    socket.getaddrinfo = local_getaddrinfo
    try:
        req = urllib.request.Request(
            URL,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/137.0.0.0 Safari/537.36'
                ),
            },
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8', errors='replace')
    finally:
        socket.getaddrinfo = original_getaddrinfo


def get_latest_post_time(html: str) -> datetime:
    match = ENTRY_DATE_PATTERN.search(html)
    if not match:
        raise RuntimeError('entry-date が見つかりません')
    year, month, day, hour, minute = map(int, match.groups())
    return datetime(year, month, day, hour, minute)


def main() -> int:
    html = fetch_homepage()
    latest = get_latest_post_time(html)
    return int((datetime.now() - latest).total_seconds())


if __name__ == '__main__':
    try:
        print(main())
    except Exception as exc:
        print(f'エラー: {exc}', file=sys.stderr)
        sys.exit(1)
