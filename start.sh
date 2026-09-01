#!/bin/sh
DIR=/sys_data/penweb
pkill -f 'server.py' 2>/dev/null
pkill -f 'ingest.sh' 2>/dev/null
pkill -f 'ocr.sh' 2>/dev/null
pkill -f 'httpd -p 8080' 2>/dev/null
sleep 1
[ -x /opt/bin/opkg ] && export PATH=/opt/bin:/opt/sbin:$PATH
python3 "$DIR/server.py" &
sh "$DIR/ingest.sh" &
sh "$DIR/ocr.sh" &
echo "penweb 已启动（Python 版 + 自动抓取扫描词）"
echo "浏览器打开: http://<词典笔IP>:8080/"
