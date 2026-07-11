#!/bin/bash

set -e
time_html=$(timeout 10 curl -s gekiyasutokka.com/popular_page.html --resolve gekiyasutokka.com:80:127.0.0.1 | tail -1 | grep -o '[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} [0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}')
time_html=$(date -d "$time_html" +%s)
time_now=$(date +%s)

if [ $(( time_html + 3600 )) -lt $time_now ]; then
    echo "1"
    exit 1
else
    echo "0"
    exit 0
fi

