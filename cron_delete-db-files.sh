#!/bin/bash
# cron 用まとめスクリプト: 古いファイル・記事・未使用メディアの一括削除
#
# 実行内容（上から順に実行し、失敗した時点で停止）:
#   1. /opt/nginx-access/response_*.html の最新3個以外を削除
#   2. delete_old_article.sh 24  … 24時間より前に更新された記事を DB から削除
#   3. orphan-media.sh scan / delete --yes / cleanup-db --yes
#      … 未使用メディアの一覧作成 → ファイル削除 → 孤立 postmeta 削除
#   4. popular_page.py … 直近10時間の投稿から人気記事HTMLを再生成
#
# ログは syslog (/var/log/syslog) に出力される。確認方法:
#   grep cron_delete-db-files /var/log/syslog
#   journalctl -t cron_delete-db-files
#
# 二重起動防止: flock により前回実行中は即終了（exit 0）
#
# crontab 登録例（リダイレクト不要）:
#   0 3 * * * /opt/nginx-access/cron_delete-db-files.sh

set -euo pipefail

# 二重起動防止（cron の重複実行・前回未完了時はスキップ）
LOCK_FILE="/opt/nginx-access/.cron_delete-db-files.lock"
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    logger -t cron_delete-db-files "Already running, skip."
    exit 0
fi

BASE_DIR="/opt/nginx-access"
CRON_DIR="$BASE_DIR/cron"
KEEP_RESPONSES=3

# 全出力を syslog へ送る（タグ: cron_delete-db-files）
exec > >(logger -t cron_delete-db-files) 2>&1

log() {
    echo "$*"
}

log "=== cron_delete-db-files start ==="

# 1. response_*.html の最新3個以外を削除
log "[1/4] cleanup old response_*.html (keep latest $KEEP_RESPONSES)"
ls -1t "$BASE_DIR"/response_*.html 2>/dev/null | tail -n +$((KEEP_RESPONSES + 1)) | xargs -d '\n' -r rm -f
log "remaining: $(ls -1 "$BASE_DIR"/response_*.html 2>/dev/null | wc -l) files"

# 2. 古い記事の削除（24時間より前）
log "[2/4] delete_old_article.sh 24"
bash "$BASE_DIR/delete_old_article.sh" 24

# 3. 未使用メディアの整理
# scan が失敗したら delete は実行しない（set -e により停止）
log "[3/4] orphan-media scan / delete / cleanup-db"
"$CRON_DIR/orphan-media.sh" scan
"$CRON_DIR/orphan-media.sh" delete --yes
"$CRON_DIR/orphan-media.sh" cleanup-db --yes

# 4. 人気記事HTMLの再生成（記事削除後に実行し、削除済み記事が載らないようにする）
# テンプレート popular_page.j2 をカレントから読むため cd が必要
log "[4/4] popular_page.py"
cd "$BASE_DIR"
python3 "$BASE_DIR/popular_page.py"

log "=== cron_delete-db-files done ==="

