#!/bin/sh
# 从作业帮扫描记录 JSON 自动提取识别文字，写入 store.txt
# 依赖: jq  (opkg install jq)
export PATH=/opt/bin:/opt/sbin:$PATH 2>/dev/null
STORE=/sys_data/penweb/store.txt
STATE=/sys_data/penweb/.lastscan
REC=/sys_data/fatfs/answer_word/scanWordRecord.json
POLL=5
touch "$STORE" "$STATE"
LAST=$(cat "$STATE" 2>/dev/null)
case "$LAST" in ''|*[^0-9]*) LAST=0;; esac
while true; do
  sleep "$POLL"
  [ -f "$REC" ] || continue
  jq -r --argjson last "$LAST" '
    ( (.en // [])[]? , (.cn // [])[]? )
    | select((.time // 0) > $last)
    | [ ((.time/1000) | strftime("%Y-%m-%d %H:%M:%S")), (.word // "") ] | @tsv
  ' "$REC" 2>/dev/null >> "$STORE"
  MAX=$(jq -r '[ (.en // [])[]?.time//0 , (.cn // [])[]?.time//0 ] | max' "$REC" 2>/dev/null)
  case "$MAX" in
    ''|*[^0-9]*) ;;
    *) [ "$MAX" -gt "$LAST" ] 2>/dev/null && LAST=$MAX && echo "$MAX" > "$STATE" ;;
  esac
done
