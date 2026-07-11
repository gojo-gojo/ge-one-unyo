#!/bin/bash
# WordPress 未使用メディア整理スクリプト
#
# 使い方:
#   /opt/nginx-access/cron/orphan-media.sh scan              # 未使用画像一覧を作成
#   /opt/nginx-access/cron/orphan-media.sh status            # 件数・容量を確認
#   /opt/nginx-access/cron/orphan-media.sh test-quarantine   # 先頭100件を tmp/ へ退避
#   /opt/nginx-access/cron/orphan-media.sh quarantine        # 一覧の全件を tmp/ へ退避
#   /opt/nginx-access/cron/orphan-media.sh restore           # 退避ファイルをすべて元に戻す
#   /opt/nginx-access/cron/orphan-media.sh delete            # 一覧の全件削除（不可逆）
#   /opt/nginx-access/cron/orphan-media.sh cleanup-db        # 孤立 postmeta 削除
#   /opt/nginx-access/cron/orphan-media.sh backup            # DB/uploads バックアップ
#
# cron 等の非対話実行では --yes (-y) を付けると確認プロンプトをスキップする:
#   /opt/nginx-access/cron/orphan-media.sh delete --yes
#   （環境変数 AUTO_YES=1 でも同じ）

set -euo pipefail

WP_ROOT="/var/www/nginx/gekiyasutokka.com"
SCRIPT_DIR="/opt/nginx-access/cron"
TMP_DIR="$SCRIPT_DIR/tmp"
LIST="$TMP_DIR/orphan_images.txt"
QUARANTINE="$TMP_DIR/orphan_images_quarantine"
LOG="$TMP_DIR/orphan-media.log"

mkdir -p "$TMP_DIR"
DB_USER="gekiyasutokka_com"
DB_PASS="gekiyasutokka_com"
DB_NAME="gekiyasutokka_com"

export WP_ROOT OUTPUT="$LIST" LOG

# --yes / -y または環境変数 AUTO_YES=1 で確認プロンプトをスキップ（cron 用）
AUTO_YES="${AUTO_YES:-0}"

# delete で「直近 N 時間以内に更新されたファイル」を除外する（画像歯抜け防止）
MIN_AGE_HOURS="${MIN_AGE_HOURS:-24}"

usage() {
    cat <<'EOF'
WordPress 未使用メディア整理

  /opt/nginx-access/cron/orphan-media.sh backup            DB と uploads をバックアップ
  /opt/nginx-access/cron/orphan-media.sh scan              未使用画像一覧を作成
  /opt/nginx-access/cron/orphan-media.sh status            件数・容量を確認
  /opt/nginx-access/cron/orphan-media.sh test-quarantine   先頭100件を tmp/ へ退避（可逆）
  /opt/nginx-access/cron/orphan-media.sh quarantine        一覧の全件を tmp/ へ退避（可逆）
  /opt/nginx-access/cron/orphan-media.sh restore           退避ファイルをすべて元に戻す
  /opt/nginx-access/cron/orphan-media.sh quarantine-status 退避中の件数・容量を確認
  /opt/nginx-access/cron/orphan-media.sh delete            一覧の全件削除（不可逆）
  /opt/nginx-access/cron/orphan-media.sh cleanup-db        孤立 postmeta 削除

オプション:
  --yes, -y        確認プロンプトをスキップ（cron 等の非対話実行用）
                   環境変数 AUTO_YES=1 でも同じ

cron 実行例:
  /opt/nginx-access/cron/orphan-media.sh scan
  /opt/nginx-access/cron/orphan-media.sh delete --yes
  /opt/nginx-access/cron/orphan-media.sh cleanup-db --yes

推奨手順（初回・安全）:
  1. backup
  2. scan
  3. status
  4. test-quarantine
  5. サイト表示確認
  6. quarantine
  7. 問題あれば restore / 問題なければそのまま or delete
EOF
}

log_line() {
    # ログファイルに書けなくても処理は止めない
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$LOG" 2>/dev/null || true
}

confirm() {
    local prompt="$1"
    if [[ "$AUTO_YES" == "1" ]]; then
        echo "$prompt -> auto-yes"
        return 0
    fi
    local ans
    read -r -p "$prompt [yes/no]: " ans
    if [[ "$ans" != "yes" ]]; then
        echo "cancelled"
        exit 1
    fi
}

cmd_backup() {
    local stamp
    stamp="$(date +%Y%m%d)"
    echo "DB backup..."
    mysqldump -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" > "$TMP_DIR/gekiyasutokka_backup_${stamp}.sql"
    echo "uploads backup..."
    tar czf "$TMP_DIR/uploads_backup_${stamp}.tar.gz" -C "$WP_ROOT/wp-content" uploads
    echo "done:"
    ls -lh "$TMP_DIR/gekiyasutokka_backup_${stamp}.sql" "$TMP_DIR/uploads_backup_${stamp}.tar.gz"
}

cmd_scan() {
    echo "scan start (時間がかかることがあります)"
    php "$SCRIPT_DIR/orphan-media-scan.php"
    echo "scan done: $LIST"
}

cmd_status() {
    if [[ ! -f "$LIST" ]]; then
        echo "一覧がありません。先に scan を実行してください。"
        exit 1
    fi
    echo "orphan files: $(wc -l < "$LIST")"
    echo "sample:"
    head -10 "$LIST"
    echo "..."
    echo "estimated size:"
    tr '\n' '\0' < "$LIST" | du -cb --files0-from=/dev/stdin 2>/dev/null | tail -1 | awk '{printf "%.1f GB (%d bytes)\n", $1/1024/1024/1024, $1}'
}

cmd_quarantine_status() {
    if [[ ! -d "$QUARANTINE" ]]; then
        echo "退避ディレクトリがありません: $QUARANTINE"
        exit 1
    fi
    local count
    count="$(find "$QUARANTINE" -type f | wc -l)"
    echo "quarantined files: $count"
    echo "quarantine dir: $QUARANTINE"
    echo "sample:"
    find "$QUARANTINE" -type f | head -10
    echo "..."
    echo "estimated size:"
    du -sh "$QUARANTINE"
}

move_to_quarantine() {
    local input_file="$1"
    local moved=0
    local skipped=0

    mkdir -p "$QUARANTINE"
    log_line "quarantine start: $input_file -> $QUARANTINE"

    while IFS= read -r path; do
        [[ -z "$path" ]] && continue

        if [[ "$path" != "$WP_ROOT"/* ]]; then
            log_line "skip (outside WP_ROOT): $path"
            skipped=$((skipped + 1))
            continue
        fi

        if [[ ! -f "$path" ]]; then
            skipped=$((skipped + 1))
            continue
        fi

        # scan 後に再アップロードされた同名ファイルは退避しない
        if [[ -f "$LIST" && "$path" -nt "$LIST" ]]; then
            log_line "skip (newer than list): $path"
            skipped=$((skipped + 1))
            continue
        fi

        rel="${path#$WP_ROOT/}"
        dest="$QUARANTINE/$rel"
        mkdir -p "$(dirname "$dest")"
        mv "$path" "$dest"
        moved=$((moved + 1))

        if (( moved % 50000 == 0 )); then
            log_line "quarantine progress: moved=$moved skipped=$skipped"
        fi
    done < "$input_file"

    log_line "quarantine done: moved=$moved skipped=$skipped"
    echo "moved: $moved, skipped: $skipped"
    echo "quarantine dir: $QUARANTINE"
}

cmd_test_quarantine() {
    if [[ ! -f "$LIST" ]]; then
        echo "一覧がありません。先に scan を実行してください。"
        exit 1
    fi
    local tmp_list
    tmp_list="$(mktemp)"
    head -100 "$LIST" > "$tmp_list"
    move_to_quarantine "$tmp_list"
    rm -f "$tmp_list"
}

cmd_quarantine() {
    if [[ ! -f "$LIST" ]]; then
        echo "一覧がありません。先に scan を実行してください。"
        exit 1
    fi
    echo "move all files listed in $LIST to $QUARANTINE"
    confirm "本当に退避しますか?"
    move_to_quarantine "$LIST"
}

cmd_restore() {
    if [[ ! -d "$QUARANTINE" ]]; then
        echo "退避ディレクトリがありません: $QUARANTINE"
        exit 1
    fi
    local count
    count="$(find "$QUARANTINE" -type f | wc -l)"
    if [[ "$count" -eq 0 ]]; then
        echo "退避ファイルがありません。"
        exit 1
    fi
    echo "restore $count files from $QUARANTINE to $WP_ROOT"
    confirm "本当にすべて元に戻しますか?"

    local restored=0
    local failed=0

    log_line "restore start: $QUARANTINE -> $WP_ROOT"

    while IFS= read -r file; do
        rel="${file#$QUARANTINE/}"
        orig="$WP_ROOT/$rel"
        mkdir -p "$(dirname "$orig")"
        if mv "$file" "$orig"; then
            restored=$((restored + 1))
        else
            failed=$((failed + 1))
            log_line "restore failed: $file"
        fi

        if (( restored % 50000 == 0 )); then
            log_line "restore progress: restored=$restored failed=$failed"
        fi
    done < <(find "$QUARANTINE" -type f)

    find "$QUARANTINE" -type d -empty -delete 2>/dev/null || true

    log_line "restore done: restored=$restored failed=$failed"
    echo "restored: $restored, failed: $failed"
}

cmd_test_delete() {
    if [[ ! -f "$LIST" ]]; then
        echo "一覧がありません。先に scan を実行してください。"
        exit 1
    fi
    head -100 "$LIST" | xargs -d '\n' -r rm -f
    echo "deleted first 100 files"
}

cmd_delete() {
    if [[ ! -f "$LIST" ]]; then
        echo "一覧がありません。先に scan を実行してください。"
        exit 1
    fi
    echo "delete all files listed in $LIST"
    confirm "本当に削除しますか?"

    # 直近 MIN_AGE_HOURS 時間以内に更新されたファイルは削除しない。
    # ファイル名を使い回す投稿システムのため、scan 中〜delete までの間に
    # 再アップロードされた画像を巻き添えにしないための保険。
    # 記事の寿命は24時間 (delete_old_article.sh 24) なので、
    # それより古い孤立ファイルだけ消せば取りこぼしても次回消える。
    local age_ref
    age_ref="$(mktemp)"
    touch -d "$MIN_AGE_HOURS hours ago" "$age_ref"

    local deleted=0
    local skipped_new=0
    while IFS= read -r path; do
        [[ -z "$path" || ! -f "$path" ]] && continue
        if [[ "$path" -nt "$age_ref" || "$path" -nt "$LIST" ]]; then
            skipped_new=$((skipped_new + 1))
            continue
        fi
        rm -f "$path"
        deleted=$((deleted + 1))
    done < "$LIST"
    rm -f "$age_ref"
    echo "delete done: deleted=$deleted skipped_new=$skipped_new (skip = ${MIN_AGE_HOURS}h以内に更新)"
}

cmd_cleanup_db() {
    echo "delete orphan postmeta"
    confirm "本当に実行しますか?"
    mysql -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "
        DELETE pm FROM wp_postmeta pm
        LEFT JOIN wp_posts p ON p.ID = pm.post_id
        WHERE p.ID IS NULL;
    "
    echo "cleanup-db done"
}

# 引数のどこにあっても --yes / -y を受け付ける
ARGS=()
for arg in "$@"; do
    case "$arg" in
        --yes|-y) AUTO_YES=1 ;;
        *) ARGS+=("$arg") ;;
    esac
done
set -- "${ARGS[@]:-}"

case "${1:-}" in
    backup) cmd_backup ;;
    scan) cmd_scan ;;
    status) cmd_status ;;
    test-quarantine) cmd_test_quarantine ;;
    quarantine) cmd_quarantine ;;
    restore) cmd_restore ;;
    quarantine-status) cmd_quarantine_status ;;
    test-delete) cmd_test_delete ;;
    delete) cmd_delete ;;
    cleanup-db) cmd_cleanup_db ;;
    *) usage ;;
esac
