#!/usr/bin/env bash
set -euo pipefail

cat << USAGE > /dev/null
sudo -u www-data bash /opt/nginx-access/delete_old_article.sh 100
USAGE

DB_NAME="${DB_NAME:-gekiyasutokka_com}"
DB_USER="${DB_USER:-gekiyasutokka_com}"
DB_PASSWORD="${DB_PASSWORD:-gekiyasutokka_com}"

# 記事の DB 削除期限（時間）。cron から引数なしで呼ばれる。
HOURS_AGO="${1:-${HOURS_AGO:-23}}"

if [[ ! "$HOURS_AGO" =~ ^[0-9]+$ ]]; then
  echo "Invalid hours: $HOURS_AGO" >&2
  exit 1
fi

CUTOFF="$(date -d "${HOURS_AGO} hours ago" '+%Y-%m-%d %H:%M:%S')"

if [[ ! "$CUTOFF" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
  echo "Invalid CUTOFF: $CUTOFF" >&2
  exit 1
fi

MYSQL_PWD="$DB_PASSWORD" mysql --user="$DB_USER" "$DB_NAME" <<SQL
delete from wp_posts where post_modified < '$CUTOFF' and
id <> 297955 and
id <> 242735 and
id <> 205000 and
id <> 1      and
id <> 242718 and
id <> 242734 and
id <> 242795 and
id <> 244849 and
id <> 244896 and
id <> 244936 and
id <> 245420 and
id <> 245841 and
id <> 247154 and
id <> 247504 and
id <> 247618 and
id <> 248900 and
id <> 344664 and
id <> 380352 and
id <> 3      and
id <> 2      and
id <> 26     and
id <> 28     and
id <> 30     and
id <> 32     and
id <> 433    and
id <> 539    and
id <> 241907 and
id <> 380793 and
id <> 661180 and
id <> 661177 and
guid not like '%favicon.png%' and
post_name not like '%favicon%' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2023/11/81Ch8zQGAS._AC_SX679.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/webp-express/webp-images/doc-root/wp-content/uploads/2023/11/71qPK6wrmBL._AC_SX679_-374x374.jpg.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/webp-express/webp-images/doc-root/wp-content/uploads/2023/11/71qPK6wrmBL._AC_SX679_-374x374.jpg.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/webp-express/webp-images/doc-root/wp-content/uploads/2023/11/81h95PzQltL._AC_SX679_-374x374.jpg.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2023/11/T40BsqUL.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2023/11/810lqVgPqTL._AC_SX679.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/webp-express/webp-images/doc-root/wp-content/uploads/2023/11/41-gMht0EfL._AC_SX679_-374x374.jpg.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2023/11/B0BW2L198L.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2023/11/51DsMTFWelL._AC_SX679_.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2023/11/81Ch8zQGAS._AC_SX679.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/webp-express/webp-images/doc-root/wp-content/uploads/2023/11/71C7zR6lYbL._AC_SX679.jpg.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2023/11/61lZYRcgUUS._AC_SX679_.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2023/11/51UAva3ateL._AC_SX679_.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2023/11/61k3t7fqO6L._AC_SX679_.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2024/04/516KQ0zlrsL._AC_.webp' and
guid <> 'https://gekiyasutokka.com/wp-content/uploads/2024/07/audible2.webp' and
(
post_type = "page" or
post_type = "post" or
post_type = "attachment" or
post_type = "taxopress_logs"
)
;

-- 記事を直接削除すると wp_term_taxonomy.count が更新されないため、
-- 孤立した term_relationships を削除してから件数を再計算する。
-- link_category 等は object_id が wp_links.link_id を指すため、
-- wp_posts 基準の削除対象に含めない（含めるとリンクのカテゴリーが消える）。
DELETE tr FROM wp_term_relationships tr
INNER JOIN wp_term_taxonomy tt ON tt.term_taxonomy_id = tr.term_taxonomy_id
LEFT JOIN wp_posts p ON p.ID = tr.object_id
WHERE p.ID IS NULL
  AND tt.taxonomy IN ('category', 'post_tag');

UPDATE wp_term_taxonomy tt
SET count = (
  SELECT COUNT(*)
  FROM wp_term_relationships tr
  INNER JOIN wp_posts p ON p.ID = tr.object_id
  WHERE tr.term_taxonomy_id = tt.term_taxonomy_id
    AND p.post_status = 'publish'
    AND p.post_type = 'post'
)
WHERE tt.taxonomy IN ('category', 'post_tag');
SQL
