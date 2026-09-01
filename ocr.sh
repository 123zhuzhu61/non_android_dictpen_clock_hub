#!/bin/sh
# 自动 OCR 扫描原图，把完整文字写入 store.txt
# 依赖: tesseract  (opkg install tesseract-ocr tesseract-ocr-data-chi-sim tesseract-ocr-data-eng)
STORE=/sys_data/penweb/store.txt
STATE=/sys_data/penweb/.ocr_done
# 可监视的目录（空格分隔）；如需增加扫描落点，改这里即可
WATCH_DIRS="/sys_data/fatfs/answer_word/answerImgs /sys_data/image_cache"
POLL=5
touch "$STORE" "$STATE"

if ! command -v tesseract >/dev/null 2>&1; then
  echo "tesseract 未安装，OCR 功能不可用。请运行 deploy.sh 安装 tesseract-ocr 及中文语言包。"
  exit 0
fi

stamp() {
  # 参数: 毫秒时间戳字符串 -> "YYYY-MM-DD HH:MM:SS"，失败则用当前时间
  python3 -c "import datetime,sys;print(datetime.datetime.fromtimestamp(int(sys.argv[1])/1000).strftime('%Y-%m-%d %H:%M:%S'))" "$1" 2>/dev/null \
    || date +"%Y-%m-%d %H:%M:%S"
}

is_jpeg() {
  [ -f "$1" ] || return 1
  m=$(head -c3 "$1" | od -An -tx1 | tr -d ' \n')
  [ "$m" = "ffd8ff" ]
}

ocr_one() {
  # $1=图片路径  $2=累积文件；把该图 OCR 文本(去空白行)追加到累积文件
  out="/tmp/ocr_$$_$RANDOM"
  tesseract "$1" "$out" -l chi_sim+eng --psm 6 >/dev/null 2>&1
  grep -v '^[[:space:]]*$' "$out.txt" 2>/dev/null >> "$2"
  rm -f "$out" "$out.txt"
}

while true; do
  sleep "$POLL"
  for W in $WATCH_DIRS; do
    [ -d "$W" ] || continue
    # 子文件夹模式（answerImgs：每次扫描一个时间戳文件夹，内含若干 JPEG）
    for d in "$W"/*/ ; do
      [ -d "$d" ] || continue
      bn=$(basename "$d")
      grep -qx "$bn" "$STATE" 2>/dev/null && continue
      acc="/tmp/ocr_acc_$$_$RANDOM"; : > "$acc"
      for img in "$d"*.jpeg "$d"*.jpg "$d"*.JPG "$d"*.png; do
        is_jpeg "$img" || continue
        ocr_one "$img" "$acc"
      done
      if [ -s "$acc" ]; then
        ts=$(stamp "$bn")
        line=$(tr '\n' ' ' < "$acc" | tr -s ' ')
        printf '%s\t[OCR] %s\n' "$ts" "$line" >> "$STORE"
      fi
      rm -f "$acc"
      echo "$bn" >> "$STATE"
    done
    # 直接放 JPEG 的目录（无子文件夹，如未来可解析的 image_cache）
    for img in "$W"/*.jpeg "$W"/*.jpg "$W"*.JPG "$W"*.png; do
      is_jpeg "$img" || continue
      bn=$(basename "$img")
      grep -qx "$bn" "$STATE" 2>/dev/null && continue
      acc="/tmp/ocr_acc_$$_$RANDOM"; : > "$acc"
      ocr_one "$img" "$acc"
      if [ -s "$acc" ]; then
        ts=$(date +"%Y-%m-%d %H:%M:%S")
        line=$(tr '\n' ' ' < "$acc" | tr -s ' ')
        printf '%s\t[OCR] %s\n' "$ts" "$line" >> "$STORE"
      fi
      rm -f "$acc"
      echo "$bn" >> "$STATE"
    done
  done
done
