# ge-one-unyo

[gekiyasutokka.com](https://gekiyasutokka.com/) の運用自動化スクリプト群。

WP キャッシュの生成・削除、人気記事 HTML の生成、相互リンクランキングの集計、古い記事・未使用メディアの整理などを担う。

## リポジトリ

```
git@github.com:gojo-gojo/ge-one-unyo.git
```

## 全体像

```
nginx アクセスログ
    └─ rank.py ── rank.json ── rank.html（相互リンクランキング）

del-cache.py（5分ごと）
    └─ WP キャッシュの削除・再生成

cron_delete-db-files.sh（20分ごと）
    ├─ 古い response_*.html 削除
    ├─ delete_old_article.sh（24時間超の記事削除）
    ├─ orphan-media.sh（未使用メディア削除）
    └─ popular_page.py（人気記事 HTML 再生成）

kanshi.sh
    └─ Zabbix エージェント ninki（popular_page.html の更新監視）

check_post_interval.py
    └─ Zabbix エージェント arttime（最新記事投稿からの経過秒数）
        └─ Zabbix サーバー側で Discord 通知
```

## cron 設定

本番の cron 定義は `/etc/cron.d/scraping` に登録されている。リポジトリにはその控えとして `cron-scraping.txt` を置いている（`cp -p /etc/cron.d/scraping cron-scraping.txt` で更新）。

cron を変更したときは、本番ファイルと `cron-scraping.txt` の両方を揃えておく。

### 有効なジョブ

| スケジュール | ユーザー | スクリプト | 内容 |
|---|---|---|---|
| `*/5 * * * *` | www-data | `del-cache.py` | WP キャッシュの削除・再生成 |
| `10,30,50 * * * *` | www-data | `cron_delete-db-files.sh` | 記事削除・メディア整理・人気記事 HTML 生成 |
| `5 */2 * * *` | www-data | `rank.py` | 相互リンクランキング更新 |

ファイル先頭の `POPULAR_PAGE_DOMAIN='gekiyasutokka.com'` は、`del-cache.py` と `popular_page.py` が参照する環境変数。

### 無効化済み（コメントアウト）

`cron-scraping.txt` 内で `#` により停止している旧ジョブ。

| スケジュール | スクリプト | 備考 |
|---|---|---|
| `47 16 * * *` | `rank.py` | 旧ランキング更新（`logger nginx-access` 付き） |
| `15,45 * * * *` | `wp_post_check.py` | 旧メール通知監視（Zabbix + Discord に移行） |
| `55 18 * * *` | `delete-wp-cache.sh` | 旧 WP キャッシュ削除 |
| `35 * * * *` | `popular_page.py` | 旧・毎時人気記事生成（`cron_delete-db-files.sh` 内に統合） |
| `*/15 * * * *` | `del-cache.py` | 旧・15分間隔キャッシュ処理（5分間隔に変更） |

### 本番への反映

```bash
# 編集後に反映（root 権限が必要）
sudo cp /opt/nginx-access/cron-scraping.txt /etc/cron.d/scraping
sudo chmod 644 /etc/cron.d/scraping
```

## 主要スクリプト

### rank.py — 相互リンクランキング

nginx のアクセスログからリファラを集計し、相互リンク先ブログのランキング HTML を生成する。

- **入力ログ**: `/var/log/nginx/gekiyasutokka.com-access.log`（と `.1`）
- **対象サイト**: `rank.json` に登録されたドメインのみ
- **集計ルール**: 同一 IP・同一日・同一リファラは 1 件としてカウント
- **同票処理**: 同じ件数のサイト同士はランダムに並べ替え
- **出力**: `/var/www/nginx/gekiyasutokka.com/simaccess/rank.html`
- **デバッグ用**: `natural.log`（全リファラの集計結果）

`rank.html` の各行直前に HTML コメントで実リファラ件数が出力される（ダミー補完分は `0`）。5 件に満たない場合は `rank.json` からランダムに補完する。

```bash
python3 /opt/nginx-access/rank.py
```

### popular_page.py — 人気記事 HTML

直近 10 時間以内の投稿から人気記事一覧 HTML を生成する。

- **出力**: `/var/www/nginx/gekiyasutokka.com/popular_page.html`
- **テンプレート**: `popular_page.j2`
- **ドメイン**: 環境変数 `POPULAR_PAGE_DOMAIN`（デフォルト: `test.gekiyasutokka.com`）

```bash
cd /opt/nginx-access
POPULAR_PAGE_DOMAIN=gekiyasutokka.com python3 popular_page.py
```

### del-cache.py — WP キャッシュ管理

トップページ・カテゴリページのキャッシュを削除して再生成する。古い個別記事キャッシュ（24 時間超）も削除する。

- **対象ホスト**: 環境変数 `POPULAR_PAGE_DOMAIN`、または引数 `test`、デフォルト `gekiyasutokka.com`
- **キャッシュ先**: `/var/www/nginx/gekiyasutokka.com/wp-content/cache/`

```bash
python3 /opt/nginx-access/del-cache.py
python3 /opt/nginx-access/del-cache.py test   # test.gekiyasutokka.com 向け
```

### cron_delete-db-files.sh — 定期メンテナンス

以下を順に実行する（`flock` による二重起動防止あり）。ログは syslog（タグ: `cron_delete-db-files`）。

1. `response_*.html` の最新 3 個以外を削除
2. `delete_old_article.sh 24` — 24 時間より前の記事を DB から削除
3. `cron/orphan-media.sh` — 未使用メディアの scan → delete → cleanup-db
4. `popular_page.py` — 人気記事 HTML の再生成

```bash
grep cron_delete-db-files /var/log/syslog
```

### delete_old_article.sh — 古い記事の DB 削除

指定時間より前に更新された `wp_posts` を削除する。固定ページ・特定 ID は除外。

```bash
sudo -u www-data bash /opt/nginx-access/delete_old_article.sh 24
```

DB 接続は環境変数 `DB_NAME` / `DB_USER` / `DB_PASSWORD` で上書き可能。

### check_post_interval.py — 記事投稿間隔（Zabbix）

[gekiyasutokka.com](https://gekiyasutokka.com/) のトップページから最新記事の `entry-date` を取得し、投稿からの経過秒数（int）を出力する。旧 `wp_post_check.py` の記事間隔チェックを置き換える。

- **取得方法**: `127.0.0.1` 経由でトップページを取得（外部からの 403 を回避）
- **出力**: 経過秒数のみ（例: `915`）
- **依存**: Python 標準ライブラリのみ

```bash
python3 /opt/nginx-access/check_post_interval.py
# 915
```

Zabbix からの確認:

```bash
zabbix_get -s 127.0.0.1 -k arttime
```

### kanshi.sh — 更新監視（Zabbix）

`popular_page.html` の生成日時を確認し、1 時間以上更新がなければ異常（exit 1）を返す。

Zabbix エージェントの `UserParameter=ninki` として登録されており、Zabbix サーバー側で Discord 通知が行われる。

```bash
/opt/nginx-access/kanshi.sh
# 正常: exit 0 / 出力 "0"
# 異常: exit 1 / 出力 "1"
```

設定: `/etc/zabbix/zabbix_agent2.d/plugins.d/gekiyasutokka.conf`

## Zabbix エージェント設定

Zabbix エージェントの UserParameter は `/etc/zabbix/zabbix_agent2.d/plugins.d/` に配置する。

| ファイル | キー | コマンド | 内容 |
|---|---|---|---|
| `wordpress.conf` | `arttime` | `check_post_interval.py` | 最新記事投稿からの経過秒数 |
| `gekiyasutokka.conf` | `ninki` | `kanshi.sh` | `popular_page.html` が 1 時間以内に更新されているか（0/1） |

### wordpress.conf

```ini
UserParameter=arttime,/usr/bin/python3 /opt/nginx-access/check_post_interval.py
```

Zabbix サーバー側で `arttime` を定期取得し、閾値（例: 10800 秒 = 3 時間）を超えたらアラート（Discord 等）を送る想定。

動作確認:

```bash
zabbix_get -s 127.0.0.1 -k arttime
# 915
```

設定変更後は Zabbix エージェントの再起動が必要:

```bash
sudo systemctl restart zabbix-agent2
```

### cron/orphan-media.sh — 未使用メディア整理

WordPress の uploads 内で記事・メタから参照されていない画像を検出・削除する。

詳細な手順は [cron/procedure.md](cron/procedure.md) を参照。

```bash
/opt/nginx-access/cron/orphan-media.sh scan      # 一覧作成
/opt/nginx-access/cron/orphan-media.sh status    # 件数・容量確認
/opt/nginx-access/cron/orphan-media.sh delete --yes  # 削除（不可逆）
```

## 設定ファイル

| ファイル | 用途 |
|---|---|
| `rank.json` | ランキング対象の相互リンク先（ドメイン → 表示名・URL） |
| `rank.html.j2` | ランキング HTML テンプレート（Jinja2） |
| `popular_page.j2` | 人気記事 HTML テンプレート（Jinja2） |
| `siteall.json` | サイト情報マスタ |
| `cron-scraping.txt` | `/etc/cron.d/scraping` の控え（cron 定義） |

## 廃止済み

### wp_post_check.py

記事更新間隔の監視と Brevo（メール）によるアラート送信を行っていた旧スクリプト。cron はコメントアウト済み。監視は `check_post_interval.py`（`arttime`）+ Zabbix + Discord に移行済み。削除予定。

## 依存パッケージ（Python）

```
jinja2
requests
beautifulsoup4
lxml
python-dateutil
mysql-connector-python
```

## ディレクトリ構成

```
/opt/nginx-access/
├── rank.py                  # 相互リンクランキング
├── rank.json                # ランキング対象サイト
├── rank.html.j2             # ランキングテンプレート
├── popular_page.py          # 人気記事 HTML 生成
├── popular_page.j2          # 人気記事テンプレート
├── del-cache.py             # WP キャッシュ管理
├── cron_delete-db-files.sh  # 定期メンテナンス（cron 用）
├── delete_old_article.sh    # 古い記事の DB 削除
├── check_post_interval.py   # 最新記事の経過秒数（Zabbix arttime）
├── kanshi.sh                # popular_page 更新監視（Zabbix ninki）
├── cron-scraping.txt        # /etc/cron.d/scraping の控え
├── cron/
│   ├── orphan-media.sh      # 未使用メディア整理
│   ├── orphan-media-scan.php
│   └── procedure.md         # メディア整理の手順書
└── wp_post_check.py         # 廃止済み（メール通知）
```
