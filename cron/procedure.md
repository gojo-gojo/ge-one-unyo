# gekiyasutokka.com 運用手順

## 1. 未使用画像の整理

### 推奨手順

`backup` → `scan` → 一覧確認 → `test-quarantine` → サイト確認 → `quarantine`

### 1. バックアップ

```bash
/opt/nginx-access/cron/orphan-media.sh backup
```

### 2. 未使用画像の一覧作成（削除しない）

```bash
/opt/nginx-access/cron/orphan-media.sh scan
```

進捗ログ: `/var/log/scraping/orphan-media.log`

### 3. `/opt/nginx-access/cron/tmp/orphan_images.txt` の中身確認

```bash
wc -l /opt/nginx-access/cron/tmp/orphan_images.txt
head -20 /opt/nginx-access/cron/tmp/orphan_images.txt
tail -5 /opt/nginx-access/cron/tmp/orphan_images.txt
tr '\n' '\0' < /opt/nginx-access/cron/tmp/orphan_images.txt | du -cb --files0-from=/dev/stdin 2>/dev/null | tail -1
```

### 4. 件数・容量の確認

```bash
/opt/nginx-access/cron/orphan-media.sh status
```

### 5. テスト退避（先頭100件を `cron/tmp/` へ mv・可逆）

```bash
/opt/nginx-access/cron/orphan-media.sh test-quarantine
```

サイトを開いて、記事の画像表示に問題がないか確認してください。

### 6. 全件退避（rm ではなく `cron/tmp/` へ mv）

```bash
/opt/nginx-access/cron/orphan-media.sh quarantine
```

`yes` と入力すると `/opt/nginx-access/cron/tmp/orphan_images_quarantine/` へ退避されます。  
ディレクトリ構造は `wp-content/uploads/...` を維持します。

### 7. 退避状況の確認

```bash
/opt/nginx-access/cron/orphan-media.sh quarantine-status
```

### 問題があった場合: すべて元に戻す

```bash
/opt/nginx-access/cron/orphan-media.sh restore
```

`yes` と入力すると uploads 配下へすべて mv で戻します。

### 問題なければ（任意）

退避済みファイルを完全削除する場合:

```bash
rm -rf /opt/nginx-access/cron/tmp/orphan_images_quarantine
```

### 8. （任意）孤立 postmeta の削除

サイト表示に問題ないことを確認してから実行:

```bash
/opt/nginx-access/cron/orphan-media.sh cleanup-db
```

### コマンド一覧

| コマンド | 説明 |
|---------|------|
| `/opt/nginx-access/cron/orphan-media.sh backup` | バックアップ |
| `/opt/nginx-access/cron/orphan-media.sh scan` | 一覧作成 |
| `/opt/nginx-access/cron/orphan-media.sh status` | 件数確認 |
| `/opt/nginx-access/cron/orphan-media.sh test-quarantine` | 100件テスト退避 |
| `/opt/nginx-access/cron/orphan-media.sh quarantine` | 全件退避（可逆） |
| `/opt/nginx-access/cron/orphan-media.sh restore` | 全件復元 |
| `/opt/nginx-access/cron/orphan-media.sh quarantine-status` | 退避状況確認 |
| `/opt/nginx-access/cron/orphan-media.sh delete` | 全件削除（不可逆） |
| `/opt/nginx-access/cron/orphan-media.sh cleanup-db` | DB整理 |

---

## 2. WebP Express ログ退避（約18GB・可逆）

**触らないもの:** WP Fastest Cache（`wp-content/cache/`）、Cocoon キャッシュ

### 退避

```bash
mv /var/www/nginx/gekiyasutokka.com/wp-content/webp-express/log/conversions \
   /tmp/webp-express-log-conversions-$(date +%Y%m%d)
```

### 戻す場合

`YYYYMMDD` は退避した日付:

```bash
rmdir /var/www/nginx/gekiyasutokka.com/wp-content/webp-express/log/conversions
mv /tmp/webp-express-log-conversions-YYYYMMDD \
   /var/www/nginx/gekiyasutokka.com/wp-content/webp-express/log/conversions
```

### 問題なければ `/tmp` 側を削除

```bash
rm -rf /tmp/webp-express-log-conversions-YYYYMMDD
```

---

## 3. keepa/ 古い画像削除

最終更新から180日以上（約半年）の `.png` を削除。  
※ Linux の `find` は mtime（最終更新日時）で判定。

### 件数確認（削除前）

```bash
find /var/www/nginx/gekiyasutokka.com/keepa -maxdepth 1 -type f -mtime +180 -and -name '*.png' | wc -l
```

### 削除

```bash
find /var/www/nginx/gekiyasutokka.com/keepa -maxdepth 1 -type f -mtime +180 -and -name '*.png' -delete
```
