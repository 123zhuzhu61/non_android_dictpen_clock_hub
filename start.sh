#!/bin/sh
DIR=/sys_data/penweb
pkill -f 'server.py' 2>/dev/null
pkill -f 'ingest.sh' 2>/dev/null
pkill -f 'ocr.sh' 2>/dev/null
pkill -f 'httpd -p 8080' 2>/dev/null
sleep 1
# Entware 的 python3/jq 都在 /opt/bin；只要该目录存在就加入 PATH（不再依赖 opkg 是否可用来决定是否加）
[ -d /opt/bin ] && export PATH=/opt/bin:/opt/sbin:$PATH
# python3 优先用 /opt/bin 绝对路径，避免 PATH 未生效时找不到
PY=python3; [ -x /opt/bin/python3 ] && PY=/opt/bin/python3
# 防深度睡眠：用 mount --bind 把 /sys/power/state 盖成占位文件，
# 原厂 guliteos_test 再写 mem 也会落空，设备不再挂起。nowake.conf=0/off 时跳过（恢复睡眠）。
if [ ! -f "$DIR/nowake.conf" ] || ! grep -qiE '^(0|off|false)$' "$DIR/nowake.conf"; then
    echo blocked > /tmp/no_suspend
    mount --bind /tmp/no_suspend /sys/power/state 2>/dev/null
fi
"$PY" "$DIR/server.py" &
sh "$DIR/ingest.sh" &
# 屏幕显示回 idle（screen.py 若在跑会自行退出；它不碰主程序和看门狗，安全）
echo idle > /tmp/penweb_mode 2>/dev/null
echo "penweb 已启动（Python 版 + 自动抓取扫描词）"
echo "浏览器打开: http://<词典笔IP>:8080/"
