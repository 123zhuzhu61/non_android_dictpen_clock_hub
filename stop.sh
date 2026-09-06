#!/bin/sh
# 停止 penweb 网页服务。screen.py 现已不碰看门狗、不杀主程序，直接停掉即可，安全。
pkill -f 'server.py' 2>/dev/null
pkill -f 'ingest.sh' 2>/dev/null
pkill -f 'ocr.sh' 2>/dev/null
echo idle > /tmp/penweb_mode 2>/dev/null
pkill -f 'screen.py' 2>/dev/null
# 恢复睡眠能力：解除对 /sys/power/state 的占位绑定（若已绑定）
umount /sys/power/state 2>/dev/null
echo "penweb 已停止（触摸屏幕即可回到词典笔界面）"
