#!/bin/sh
# ingest.sh - 从作业帮扫描记录 JSON 自动提取识别文字，写入 penweb store.txt
# 依赖: jq  (opkg install jq)
# 原理: 每次扫描识别出的词会写入
#   /sys_data/fatfs/answer_word/scanWordRecord.json
#   结构: {"en":[{"word":"strive","time":1762777846934}], "cn":[{"word":"...","time":...}]}
#   其中 time 为毫秒时间戳。本脚本按 time 增量提取新词，避免重复。

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

  # 取出 time>LAST 的词，输出 "可读时间<TAB>词"
  jq -r --argjson last "$LAST" '
    ( (.en // [])[]? , (.cn // [])[]? )
    | select((.time // 0) > $last)
    | [ ((.time/1000) | strftime("%Y-%m-%d %H:%M:%S")), (.word // "") ] | @tsv
  ' "$REC" 2>/dev/null >> "$STORE"

  # 更新已处理的最大时间戳
  MAX=$(jq -r '[ (.en // [])[]?.time//0 , (.cn // [])[]?.time//0 ] | max' "$REC" 2>/dev/null)
  case "$MAX" in
    ''|*[^0-9]*) ;;
    *) [ "$MAX" -gt "$LAST" ] 2>/dev/null && LAST=$MAX && echo "$MAX" > "$STATE" ;;
  esac
done
