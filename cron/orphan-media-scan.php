<?php
/**
 * WordPress 未使用メディア検出スクリプト
 * DB上に存在する記事・メディアから参照されている画像以外を一覧化する
 *
 * 使い方:
 *   php /opt/nginx-access/cron/orphan-media-scan.php
 */

if (php_sapi_name() !== 'cli') {
    fwrite(STDERR, "CLI only\n");
    exit(1);
}

$wp_root = getenv('WP_ROOT') ?: '/var/www/nginx/gekiyasutokka.com';
$output  = getenv('OUTPUT') ?: '/opt/nginx-access/cron/tmp/orphan_images.txt';
$log     = getenv('LOG') ?: '/var/log/scraping/orphan-media.log';

require $wp_root . '/wp-load.php';

$exclude_dirs = [
    'cocoon-resources',
    'rank-math',
    'slider2',
    'slider3',
    'wpcf7_uploads',
    'wpforms',
    'wp-import-export-lite',
    'wpallexport',
];

$image_exts = ['jpg', 'jpeg', 'png', 'gif', 'webp'];

function log_line(string $message, string $log): void
{
    $line = date('Y-m-d H:i:s') . ' ' . $message . PHP_EOL;
    echo $line;
    @file_put_contents($log, $line, FILE_APPEND | LOCK_EX);
}

function mark_used(string $path, array &$used, array $image_exts): void
{
    $path = wp_normalize_path($path);
    if ($path === '') {
        return;
    }

    $used[$path] = true;

    $dir  = dirname($path);
    $base = pathinfo($path, PATHINFO_FILENAME);
    foreach ($image_exts as $ext) {
        $used[wp_normalize_path($dir . '/' . $base . '.' . $ext)] = true;
    }
}

function add_attachment_files(int $id, array &$used, array $image_exts): void
{
    $file = get_attached_file($id);
    if ($file) {
        mark_used($file, $used, $image_exts);
    }

    $meta = wp_get_attachment_metadata($id);
    if (empty($meta['file'])) {
        return;
    }

    $dir = dirname($meta['file']);
    mark_used(WP_CONTENT_DIR . '/uploads/' . $meta['file'], $used, $image_exts);

    foreach ($meta['sizes'] ?? [] as $size) {
        if (!empty($size['file'])) {
            mark_used(WP_CONTENT_DIR . '/uploads/' . $dir . '/' . $size['file'], $used, $image_exts);
        }
    }
}

log_line('scan start', $log);
$used = [];

log_line('collecting attachments...', $log);
$attachments = get_posts([
    'post_type'      => 'attachment',
    'post_status'    => 'inherit',
    'posts_per_page' => -1,
    'fields'         => 'ids',
]);

foreach ($attachments as $id) {
    add_attachment_files((int) $id, $used, $image_exts);
}
log_line('attachments: ' . count($attachments), $log);

global $wpdb;

log_line('collecting featured images...', $log);
$thumb_ids = $wpdb->get_col("
    SELECT pm.meta_value
    FROM {$wpdb->postmeta} pm
    INNER JOIN {$wpdb->posts} p ON p.ID = pm.post_id
    WHERE pm.meta_key = '_thumbnail_id'
      AND pm.meta_value != ''
      AND p.post_status IN ('publish', 'private', 'draft', 'future', 'pending')
");
foreach ($thumb_ids as $thumb_id) {
    add_attachment_files((int) $thumb_id, $used, $image_exts);
}
log_line('featured images: ' . count($thumb_ids), $log);

log_line('collecting post/page content references...', $log);
$rows = $wpdb->get_col("
    SELECT post_content
    FROM {$wpdb->posts}
    WHERE post_status IN ('publish', 'private', 'draft', 'future', 'pending')
      AND post_type IN ('post', 'page')
");

$content_refs = 0;
foreach ($rows as $content) {
    if (preg_match_all('#/wp-content/uploads/([^\"\'\\s>]+)#', $content, $matches)) {
        foreach ($matches[1] as $rel) {
            mark_used(WP_CONTENT_DIR . '/uploads/' . urldecode($rel), $used, $image_exts);
            $content_refs++;
        }
    }

    if (preg_match_all('#wp-image-(\d+)#', $content, $ids)) {
        foreach ($ids[1] as $id) {
            add_attachment_files((int) $id, $used, $image_exts);
        }
    }
}
log_line('content url refs: ' . $content_refs, $log);

log_line('scanning uploads directory...', $log);
$uploads = WP_CONTENT_DIR . '/uploads';
$orphans = [];
$checked = 0;

$iterator = new RecursiveIteratorIterator(
    new RecursiveDirectoryIterator($uploads, FilesystemIterator::SKIP_DOTS)
);

foreach ($iterator as $file) {
    if (!$file->isFile()) {
        continue;
    }

    $path = wp_normalize_path($file->getPathname());
    foreach ($exclude_dirs as $exclude) {
        if (strpos($path, '/uploads/' . $exclude . '/') !== false) {
            continue 2;
        }
    }

    if (!preg_match('/\.(jpe?g|png|gif|webp)$/i', $path)) {
        continue;
    }

    $checked++;
    if ($checked % 50000 === 0) {
        log_line('checked files: ' . $checked, $log);
    }

    if (!isset($used[$path])) {
        $orphans[] = $path;
    }
}

// 書き込み失敗時は必ず異常終了させる（古い一覧のまま delete が走るのを防ぐ）
$written = file_put_contents($output, implode(PHP_EOL, $orphans) . (count($orphans) ? PHP_EOL : ''));
if ($written === false) {
    log_line("ERROR: failed to write $output", $log);
    exit(1);
}

$summary = sprintf(
    'scan done: checked=%d used=%d orphans=%d output=%s',
    $checked,
    count($used),
    count($orphans),
    $output
);
log_line($summary, $log);
