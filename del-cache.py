#!/usr/bin/python3

import requests
import re
import os
import sys
import shutil
import datetime
import time
from pprint import pprint
import time

# 対象ホストの切り替え（優先順）:
#   1. 環境変数 POPULAR_PAGE_DOMAIN（/etc/cron.d/scraping で設定・popular_page.py と共通）
#   2. 引数 test                    -> test.gekiyasutokka.com
#   3. デフォルト                   -> gekiyasutokka.com
if os.environ.get("POPULAR_PAGE_DOMAIN"):
    HOST = os.environ["POPULAR_PAGE_DOMAIN"]
elif "test" in sys.argv[1:]:
    HOST = "test.gekiyasutokka.com"
else:
    HOST = "gekiyasutokka.com"
BASE_URL = f"https://{HOST}"


class CurlMain:
    def __init__(self) -> None:
        # 共通処理
        self.initial()

        # ファイル削除の有無
        self.del_file = True

        # 最初の10ページのbodyを取得し、
        self.np("■■■トップのページ")
        body_all = self.main_pager()

        # カテゴリごとのページ
        cates = [
            {"n": "fashion", "j": "ファッション"},
            {"n": "food-drink", "j": "食品・飲料"},
            {"n": "zakka", "j": "生活雑貨"},
        ]
        for cate in cates:
            self.np(f"■■■{cate['j']}のページ")
            body_tmp = self.food_pages(cate["n"])
            self.np(f'{cate["j"]}の配列数={len(body_tmp)}')
            body_all += body_tmp

        # 記事のリンクをcurl
        # print(len(body_all))
        self.main_pages(body_all)

        # 24時間を過ぎた個別記事のキャッシュを削除
        self.np("■■■古い個別記事キャッシュの削除")
        self.delete_old_article_cache()

    def initial(self) -> None:
        self.day_ago0 = (datetime.datetime.now() - datetime.timedelta(days=0)).strftime(
            "%Y/%m/%d"
        )
        self.day_ago1 = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime(
            "%Y/%m/%d"
        )
        self.day_ago2 = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime(
            "%Y/%m/%d"
        )

    def np(
        self,
        msg: str,
    ):
        current_time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        print(f"【del-cache {current_time}】 {msg}")

    def file_mod_time_diff(self, file_path: str, thresh=15 * 60) -> int:
        """
        ファイルが無い： 0
        ファイルが有る： intで秒
        Args:
            file_path (str): ファイルのパス

        Returns:
            int: 最終更新時刻と現在時刻の差（秒）。
                ファイルが存在しない、またはアクセスできない場合はNoneを返す。
        """
        try:
            # ファイルの最終更新時刻をタイムスタンプ（秒）で取得
            file_modified_timestamp = os.path.getmtime(file_path)

            # ファイルの最終更新時刻をdatetimeオブジェクトに変換
            file_modified_datetime = datetime.datetime.fromtimestamp(
                file_modified_timestamp
            )

            # 現在時刻を取得
            current_datetime = datetime.datetime.now()

            # 時刻の差を計算（秒単位）
            time_difference = (
                current_datetime - file_modified_datetime
            ).total_seconds()

            time_difference = round(time_difference, 3)
            if time_difference > thresh:
                os.remove(file_path)
                self.np(f"file-remove: {time_difference} {file_path}")
            else:
                self.np(f"file-keep: {time_difference} {file_path}")

            return int(time_difference)  # 秒単位の差を整数で返す

        except FileNotFoundError:
            self.np(f"file-nofile: {file_path}")
            return 0
        except PermissionError:
            self.np(f"エラー: ファイルへのアクセス権がありません: {file_path}")
            return 9999
        except Exception as e:
            self.np(f"予期せぬエラーが発生しました: {e}")
            return 9999

    def main_pager(self) -> list[str]:
        base_url: str = BASE_URL

        delfiles: list[str] = [
            "/var/www/nginx/gekiyasutokka.com/wp-content/cache/all/index.html",
            "/var/www/nginx/gekiyasutokka.com/wp-content/cache/wpfc-mobile-cache/index.html",
        ]
        for file in delfiles:
            self.file_mod_time_diff(file)

        paths = [
            "/",
            "/page/2/",
            "/page/3/",
            "/page/4/",
            "/page/5/",
            "/page/6/",
            "/page/7/",
            "/page/8/",
            "/page/9/",
        ]

        # pageを1~9まで取得

        body_all = []

        def fetch_and_print(url):
            start_time = time.time()
            r = requests.get(url)
            elapsed_time = time.time() - start_time
            if elapsed_time >= 0.5:
                elapsed_time = "{:.3f}".format(elapsed_time)
                self.np(f"{elapsed_time} {url}")
            body_all.append(r.text)

        for path in paths:
            fetch_and_print(f"{base_url}{path}")

        return body_all

    def main_pages(self, body_all: list[str]):
        self.np(f"対象日 {self.day_ago0} {self.day_ago1} {self.day_ago2}")
        i = 0
        urls_to_curls = []
        for body in body_all:
            urls = re.findall(
                rf"https://{re.escape(HOST)}/[0-9]{{4}}/[0-9]{{2}}/[0-9]{{2}}/[A-z0-9%/-]+",
                body,
            )
            for url in urls:
                if self.day_ago0 in url or self.day_ago1 in url or self.day_ago2 in url:
                    urls_to_curls.append(url)
                i += 1

        # 重複を削除
        urls_to_curls = list(set(urls_to_curls))

        req_result = []

        def fetch_status_code(url):
            start_time = time.time()
            r = requests.get(url)
            elapsed_time = time.time() - start_time
            return [r.status_code, elapsed_time, url]

        req_result = [fetch_status_code(url) for url in urls_to_curls]

        slow_num = 0
        for line in req_result:
            if line[1] >= 0.5:
                slow_num += 1
                elapsed_time = "{:.3f}".format(line[1])
                self.np(f"{line[0]} {elapsed_time} {line[2]}")
        self.np(f"slow_num: {slow_num}/{len(req_result)}")

    def delete_old_article_cache(self, max_age_hours: int = 24) -> None:
        """
        個別記事キャッシュ (cache/*/YYYY/MM/DD/記事スラッグ/) のうち、
        最終更新から max_age_hours を過ぎたものを削除する。
        記事本体は delete_old_article.sh により24時間で消えるため、
        それより古いキャッシュは参照されない。
        万一生きている記事のキャッシュを消しても、次のアクセスで再生成される。
        """
        # cache/all, cache/wpfc-mobile-cache に加え、
        # cache/<ホスト名>/all などホスト別キャッシュも対象にする
        cache_base = "/var/www/nginx/gekiyasutokka.com/wp-content/cache"
        cache_roots = []
        for sub in ("all", "wpfc-mobile-cache"):
            cache_roots.append(os.path.join(cache_base, sub))
            for host_dir in os.listdir(cache_base):
                cache_roots.append(os.path.join(cache_base, host_dir, sub))
        cutoff = time.time() - max_age_hours * 3600
        date_dir = re.compile(r"/[0-9]{4}/[0-9]{2}/[0-9]{2}$")

        deleted = 0
        kept = 0
        for root in cache_roots:
            if not os.path.isdir(root):
                continue
            for dirpath, dirnames, _filenames in os.walk(root):
                if not date_dir.search(dirpath):
                    continue
                # dirpath = .../YYYY/MM/DD 直下の各ディレクトリが記事キャッシュ
                for name in list(dirnames):
                    article_dir = os.path.join(dirpath, name)
                    try:
                        if os.path.getmtime(article_dir) < cutoff:
                            shutil.rmtree(article_dir)
                            deleted += 1
                        else:
                            kept += 1
                    except OSError as e:
                        self.np(f"cache-del-error: {e}")
                dirnames.clear()  # 記事ディレクトリ内は走査しない

        # 空になった日付ディレクトリを掃除
        for root in cache_roots:
            if not os.path.isdir(root):
                continue
            for dirpath, dirnames, filenames in os.walk(root, topdown=False):
                if re.search(r"/[0-9]{4}(/[0-9]{2}){0,2}$", dirpath) and not dirnames and not filenames:
                    try:
                        os.rmdir(dirpath)
                    except OSError:
                        pass

        self.np(f"article-cache: deleted={deleted} kept={kept} (>{max_age_hours}h)")

    def food_pages(self, cate_name: str):
        baseopath: str = (
            f"/var/www/nginx/gekiyasutokka.com/wp-content/cache/all/category/{cate_name}"
        )
        baseurl: str = f"{BASE_URL}/category/{cate_name}"

        body_all = []
        for num in range(1, 10):
            if num == 1:
                ospath = f"{baseopath}/index.html"
                url = f"{baseurl}/"
            else:
                ospath = f"{baseopath}/page/{num}/index.html"
                url = f"{baseurl}/page/{num}/"

            # delete file

            start_time = time.time()
            self.file_mod_time_diff(ospath)

            # create cache
            r = requests.get(url)
            body_all.append(r.text)
            end_time = time.time()
            elapsed_time = end_time - start_time
            if elapsed_time >= 0.5:
                elapsed_time = "{:.3f}".format(elapsed_time)
                self.np(f"{elapsed_time} {url}")
        return body_all


if __name__ == "__main__":
    CurlMain()
