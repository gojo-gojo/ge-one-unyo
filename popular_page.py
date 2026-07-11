import requests
from pprint import pprint
import re
import json
from os.path import exists
import os
import hashlib
import sys
from lxml import html
import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
from lxml import etree
import inspect
import mysql.connector
import datetime
from shutil import copyfile
import urllib3

# 自ホストへ verify=False でアクセスする仕様のため、証明書警告は抑制する
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


"""
⬛使い方
python ./popular_page.py
/var/www/nginx/gekiyasutokka.com/popular_page.html が生成される。
"""

# 対象ドメイン。環境変数 POPULAR_PAGE_DOMAIN で上書き可能。
#   本番:   gekiyasutokka.com
#   テスト: test.gekiyasutokka.com
DOMAIN = os.environ.get('POPULAR_PAGE_DOMAIN', 'test.gekiyasutokka.com')


class Create_html:

    def __init__(self, debug=False):
        self.debug = debug
        self.baseurl = f'https://{DOMAIN}/?p='
        self.all_str = {}
        # カスタムリゾルバーを設定
        self.session = requests.Session()
        self.session.mount('https://', requests.adapters.HTTPAdapter(
            pool_connections=1,
            pool_maxsize=1
        ))
        # カスタムリゾルバーを設定
        self.session.trust_env = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
        })
        # カスタムリゾルバーを設定
        import socket
        original_getaddrinfo = socket.getaddrinfo
        def custom_getaddrinfo(*args, **kwargs):
            if args[0] == DOMAIN:
                return original_getaddrinfo('127.0.0.1', *args[1:], **kwargs)
            return original_getaddrinfo(*args, **kwargs)
        socket.getaddrinfo = custom_getaddrinfo

        ids = self.recent_post_ranking(hours=10, limit=5)

        for i, id in enumerate(ids):
            if debug:
                print(id)
            self.rtf(id, i)

        self.assing()

    def rtf(self, id: str, i: int):
        """
        メイン処理。
        """
        # url = "http://buy.livedoor.biz/index.rdf"
        # url = "https://blog.tokka.shop/?xml"

        # rtfを取得
        response = self.session.get(self.baseurl + str(id), verify=False)
        

        # print(response.text)
        # 無駄文字を削除
        # response_text = c.remove_ignore(response.text)

        ###################################
        # soupオブジェクトに変換
        soup = BeautifulSoup(response.text, 'html.parser')
        
        lxml_coverted_data = html.fromstring(response.text)
        eye_catch_figure = lxml_coverted_data.xpath('//meta[@property="og:image"]/@content')
        # print(f'{self.baseurl}{str(id)}')
        eye_catch_figure = f'<img src="{eye_catch_figure[0]}">'
        with open(f"response_{str(id)}.html", "w") as f:
            f.write(response.text)
            
        # if eye_catch_figure:
        #     eye_catch_figure = eye_catch_figure[0].replace('gekiyasutokka.com', '127.0.0.1')
        # else:
        #     eye_catch_figure = None

        ###########################
        soup = BeautifulSoup(response.text, 'html.parser')
        xml = etree.HTML(str(soup))

        lxml_coverted_data = html.fromstring(response.text)
        titles = lxml_coverted_data.xpath(
            '//*[@id="post-' + str(id) + '"]/header/h1/text()')

        titles = "".join(titles)
        titles = (re.sub(r'\n|\t|\s', '', titles))

        ###########################
        # リダイレクト後の正規URL(?p=id → パーマリンク)は最初のレスポンスから取得
        self.all_str.update(
            {
                f'no{str(i+1)}_pic': eye_catch_figure,
                f'no{str(i+1)}_url': response.url,
                f'no{str(i+1)}_title': titles,
                f'no{str(i+1)}_id': str(id),
            }
        )
        if self.debug:
            pprint(self.all_str)

    def assing(self):
        """
        create html string from j2
        """
        ########################
        # jinja2
        env = Environment(loader=FileSystemLoader('.'))
        template = env.get_template('popular_page.j2')

        rendered = str(template.render(self.all_str))

        # for inprint update time
        now = datetime.datetime.now()
        now_date = now.strftime("%Y-%m-%d %H:%M:%S")
        now_date = '<!--'+now_date+'-->'


        copyfile("/var/www/nginx/gekiyasutokka.com/popular_page.html", "/var/www/nginx/gekiyasutokka.com/popular_page.html.bak")

        # print(str(rendered))
        with open("/var/www/nginx/gekiyasutokka.com/popular_page.html", "w") as f:
            f.write(rendered+now_date)

    def recent_post_ranking(self, hours: int = 10, limit: int = 5):
        """
        直近{hours}時間に投稿された記事を対象に、
        PV(wp_cocoon_accesses)の多い順に{limit}件のpost_idを返す。
        投稿から{hours}時間以内の記事なので総PV≒直近PVとみなせる。
        """
        mydb = mysql.connector.connect(
            host="localhost",
            user="gekiyasutokka_com",
            password="gekiyasutokka_com",
            database="gekiyasutokka_com"
        )
        mycursor = mydb.cursor()
        sql = (
            "SELECT pos.ID, COALESCE(SUM(acc.count), 0) AS pv "
            "FROM wp_posts pos "
            "LEFT JOIN wp_cocoon_accesses acc ON acc.post_id = pos.ID "
            "WHERE pos.post_type = 'post' "
            "  AND pos.post_status = 'publish' "
            "  AND pos.post_date >= DATE_SUB(NOW(), INTERVAL %s HOUR) "
            "GROUP BY pos.ID "
            "ORDER BY pv DESC, pos.ID DESC "
            "LIMIT %s"
        )
        mycursor.execute(sql, (hours, limit))
        post_ids = [row[0] for row in mycursor.fetchall()]
        mydb.close()

        # 直近の投稿がlimit件に満たない場合は当日PVランキングで補完
        if len(post_ids) < limit:
            for pid in self.database():
                if pid not in post_ids:
                    post_ids.append(pid)
                if len(post_ids) >= limit:
                    break

        pprint(post_ids)
        return post_ids

    def database(self):
        """
        obtain populpr page from database
        - within 24h
        - rop 5
        [int,int,int,int,int]
        """
        # honban
        # mydb = mysql.connector.connect(
        #     host="localhost",
        #     user="gekiyasutokka_com",
        #     password="gekiyasutokka_com",
        #     database="gekiyasutokka_com"
        # )
        # test
        mydb = mysql.connector.connect(
            host="localhost",
            user="gekiyasutokka_com",
            password="gekiyasutokka_com",
            database="gekiyasutokka_com"
        )

        mycursor = mydb.cursor()

        # sql = 'SELECT   *  FROM (  SELECT    post_id   ,post_name   ,post_title   ,SUM(     CASE      WHEN date = curdate() THEN count      ELSE 0  END) AS today_pv   ,SUM(     CASE      WHEN date > DATE_SUB(NOW(), INTERVAL 1 WEEK) THEN count      ELSE 0     END) AS week_pv   ,SUM(     CASE      WHEN LEFT(REPLACE(date,'-',''),6) = DATE_FORMAT(now(),'%Y%m') THEN count      ELSE 0     END) AS month_pv   ,SUM(count) AS total_pv    FROM (   SELECT      acc.post_id    ,pos.post_name    ,pos.post_title    ,acc.date    ,acc.count   FROM wp_cocoon_accesses acc   INNER JOIN wp_posts pos   ON acc.post_id = pos.id  ) blog_info  GROUP BY post_id ,post_name ,post_title ) blog_pv_info ORDER BY today_pv DESC limit 10 ;'
        sql = "SELECT  post_id , today_pv  FROM (  SELECT    post_id   ,post_name   ,post_title   ,SUM(     CASE      WHEN date = curdate() THEN count      ELSE 0  END) AS today_pv   ,SUM(     CASE      WHEN date > DATE_SUB(NOW(), INTERVAL 1 WEEK) THEN count      ELSE 0     END) AS week_pv   ,SUM(     CASE      WHEN LEFT(REPLACE(date,'-',''),6) = DATE_FORMAT(now(),'%Y%m') THEN count      ELSE 0     END) AS month_pv   ,SUM(count) AS total_pv    FROM (   SELECT      acc.post_id    ,pos.post_name    ,pos.post_title    ,acc.date    ,acc.count   FROM wp_cocoon_accesses acc   INNER JOIN wp_posts pos   ON acc.post_id = pos.id  ) blog_info  GROUP BY post_id ,post_name ,post_title ) blog_pv_info ORDER BY today_pv DESC limit 5;"
        mycursor.execute(sql)
        myresult = mycursor.fetchall()

        post_ids = []
        for row in myresult:
            # print(type(row[0]))
            post_ids.append(row[0])
        mydb.close()
        pprint(post_ids)
        return post_ids


if __name__ == '__main__':
    # インスタンス生成
    ch = Create_html(debug=False)
    # ch.rtf('287786', 0)
