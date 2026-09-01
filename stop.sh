#!/bin/sh
pkill -f 'server.py' 2>/dev/null
pkill -f 'ingest.sh' 2>/dev/null
pkill -f 'ocr.sh' 2>/dev/null
echo "penweb 已停止"
