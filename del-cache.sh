#!/bin/bash

agents=("mozilla/5.0 (linux; android 10; k) applewebkit/537.36 (khtml, like gecko) chrome/120.0.0.0 mobile safari/537.36" "curl")

function create () {
  local kaeri=""
  for agent in "${agents[@]}" ; do
    local url="https://gekiyasutokka.com$1"
    local start=$(date +%s)
    local body=$(curl -Ls "$url" -A "$agent" 2> /dev/null)
    local end=$(date +%s)
    local elapsed=$((end - start))
    echo "$elapsed $url" >&2
    kaeri="$kaeri $body"
  done
  echo "$kaeri"
}

echo rm
rm -f /var/www/nginx/gekiyasutokka.com/wp-content/cache/all/index.html
rm -f /var/www/nginx/gekiyasutokka.com/wp-content/cache/wpfc-mobile-cache/index.html


page_all=""
for path in '/' /page/{2,3,4,5,6,7,8,9}/ ; do
  page_all="$page_all $(create "$path")" &
done
wait

echo "${#page_all}"
exit 0

y0=$(date +%Y --date '0 days ago')
m0=$(date +%m --date '0 days ago')
d0=$(date +%d --date '0 days ago')
y1=$(date +%Y --date '1 days ago')
m1=$(date +%m --date '1 days ago')
d1=$(date +%d --date '1 days ago')
y2=$(date +%Y --date '2 days ago')
m2=$(date +%m --date '2 days ago')
d2=$(date +%d --date '2 days ago')
urls1=$(echo "$page_all" | grep -o "https://gekiyasutokka.com/$y0/$m0/$d0/[A-z0-9%/-]\+" )
urls2=$(echo "$page_all" | grep -o "https://gekiyasutokka.com/$y1/$m1/$d1/[A-z0-9%/-]\+" )
urls2=$(echo "$page_all" | grep -o "https://gekiyasutokka.com/$y2/$m2/$d2/[A-z0-9%/-]\+" )

for url in  $urls1 $urls2 $urls3 ; do
  echo "$url"
done
