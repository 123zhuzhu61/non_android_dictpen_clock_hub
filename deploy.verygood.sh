#!/bin/sh
# deploy.sh - 在作业帮词典笔 S2 部署 penweb（整段粘贴/上传到设备执行一次即可）
# 自包含：运行后会自己创建 /sys_data/penweb/ 下全部文件。
set -e
DIR=/sys_data/penweb
mkdir -p "$DIR"
touch "$DIR/store.txt" "$DIR/.lastscan"

# ---------- ingest.sh：从扫描记录自动提取识别文字 ----------
cat > "$DIR/ingest.sh" <<'PENWEB_INGEST_EOF'
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
PENWEB_INGEST_EOF
chmod +x "$DIR/ingest.sh"

# ---------- ocr.sh：监听扫描原图，自动 OCR 出完整文字 ----------
# 目标目录 /sys_data/fatfs/answer_word/answerImgs 下，每次扫描会新建一个
# 以毫秒时间戳命名的文件夹，里面是若干标准 JPEG 裁剪图（img_*.jpeg）。
# 我们按文件夹为单位，对其内全部 JPEG 做 tesseract 识别，结果写入 store.txt，
# 从而绕开屏幕显示被 lv_textarea 截断的限制，拿到完整长文。
cat > "$DIR/ocr.sh" <<'PENWEB_OCR_EOF'
#!/bin/sh
# 自动 OCR 扫描原图，把完整文字写入 store.txt
# 依赖: tesseract + tesseract-data-eng (opkg) + chi_sim.traineddata (curl 从 GitHub 拉，源里无中文包)
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
  # 注意：该设备的 tesseract 把 tessdata 解析为当前目录("./")，必须从
  # /opt/share/tessdata 目录下运行才能找到 chi_sim/eng，故用子shell cd 进去。
  out="/tmp/ocr_$$_$RANDOM"
  ( [ -d /opt/share/tessdata ] && cd /opt/share/tessdata; tesseract "$1" "$out" -l chi_sim+eng --psm 6 >/dev/null 2>&1 )
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
PENWEB_OCR_EOF
chmod +x "$DIR/ocr.sh"

# ---------- server.py：纯 Python HTTP 服务（不依赖 busybox CGI） ----------
cat > "$DIR/server.py" <<'PENWEB_SERVER_EOF'
#!/usr/bin/env python3
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime

STORE = "/sys_data/penweb/store.txt"
PORT = 8080

PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>词典笔文字台</title>
<style>
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#f5f6f8;color:#222}
 header{background:#2b6cff;color:#fff;padding:14px 16px;font-size:17px;font-weight:600}
 .wrap{max-width:720px;margin:0 auto;padding:14px}
 textarea{width:100%;height:120px;border:1px solid #ccd;border-radius:10px;padding:10px;font-size:15px;resize:vertical}
 .row{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
 button{border:0;border-radius:10px;padding:10px 14px;font-size:15px;background:#2b6cff;color:#fff;cursor:pointer}
 .btn2{background:#eef;color:#2b6cff}
 .item{background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:10px 12px;margin-top:10px}
 .ts{color:#8a93a2;font-size:12px;margin-bottom:4px}
 pre{white-space:pre-wrap;word-break:break-word;margin:0;font-size:15px;font-family:inherit}
 .empty{color:#8a93a2;text-align:center;margin-top:30px}
</style></head>
<body>
<header>词典笔文字台</header>
<div class="wrap">
 <form method="post" action="/">
  <textarea name="text" placeholder="把扫描或复制的文字粘贴到这里..."></textarea>
  <div class="row">
   <button type="submit">上传文字</button>
   <a class="btn2" style="text-decoration:none" href="/export"><button type="button" class="btn2">导出 .txt</button></a>
   <a class="btn2" style="text-decoration:none" href="/clear" onclick="return confirm('清空全部？')"><button type="button" class="btn2">清空</button></a>
  </div>
 </form>
"""

def esc(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def read_items():
    items = []
    try:
        with open(STORE, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                if "\t" in line:
                    ts, txt = line.split("\t", 1)
                else:
                    ts, txt = "", line
                items.append((ts, txt))
    except FileNotFoundError:
        pass
    return items

def render():
    items = list(reversed(read_items()))
    html = PAGE
    if items:
        html += '<div style="margin-top:16px">'
        for i, (ts, txt) in enumerate(items, 1):
            badge = ''
            if txt.startswith('[OCR] '):
                badge = ' <span style="background:#0a9d6e;color:#fff;border-radius:6px;padding:1px 6px;font-size:11px;vertical-align:middle">原图OCR</span>'
                txt = txt[len('[OCR] '):]
            html += '<div class="item"><div class="ts">#%d · %s%s</div><pre>%s</pre></div>' % (i, esc(ts), badge, esc(txt))
        html += '</div>'
    else:
        html += '<p class="empty">还没有内容。扫描或粘贴文字后会出现在这里。</p>'
    html += '</div></body></html>'
    return html.encode("utf-8")

class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # 客户端在响应发送前/中途断开连接（刷新、关闭标签页、预连接取消等），属正常，静默忽略
            pass
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/export":
            try:
                with open(STORE, "rb") as f: data = f.read()
            except FileNotFoundError: data = b""
            return self._send(data, "text/plain; charset=utf-8")
        if u.path == "/clear":
            open(STORE, "w").close()
            self.send_response(302); self.send_header("Location", "/"); self.end_headers(); return
        self._send(render())
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8", "replace")
        data = parse_qs(raw)
        text = data.get("text", [""])[0]
        if text:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(STORE, "a", encoding="utf-8") as f:
                f.write("%s\t%s\n" % (ts, text))
        self.send_response(302); self.send_header("Location", "/"); self.end_headers()
    def log_message(self, *a): pass

if __name__ == "__main__":
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    open(STORE, "a").close()
    ThreadingHTTPServer.allow_reuse_address = True
    print("penweb listening on http://0.0.0.0:%d/" % PORT)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
PENWEB_SERVER_EOF
chmod +x "$DIR/server.py"

# ---------- start.sh ----------
cat > "$DIR/start.sh" <<'PENWEB_START_EOF'
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
"$PY" "$DIR/server.py" &
sh "$DIR/ingest.sh" &
echo "penweb 已启动（Python 版 + 自动抓取扫描词；已关闭原图OCR以省CPU）"
echo "浏览器打开: http://<词典笔IP>:8080/"
PENWEB_START_EOF
chmod +x "$DIR/start.sh"

# ---------- stop.sh ----------
cat > "$DIR/stop.sh" <<'PENWEB_STOP_EOF'
#!/bin/sh
pkill -f 'server.py' 2>/dev/null
pkill -f 'ingest.sh' 2>/dev/null
pkill -f 'ocr.sh' 2>/dev/null
echo "penweb 已停止"
PENWEB_STOP_EOF
chmod +x "$DIR/stop.sh"

# ---------- 配置国内镜像（清华 TUNA，http 协议，避开设备 wget 不支持 TLS 的问题）----------
export PATH=/opt/bin:/opt/sbin:$PATH 2>/dev/null

if [ -x /opt/bin/opkg ]; then
  if [ -f /opt/etc/opkg.conf ]; then
    # 取出架构（如 armv7sf-k3.2），把每条 src 行【整条 URL 重写】为官方源。
    # 说明：清华/中科大的 Entware 镜像实际路径是 404（不镜像该架构目录），
    # 而设备自带 wget 不支持 TLS（无法走 https）。官方 bin.entware.net 同时支持
    # 纯 http 且索引完整（含 tesseract），设备 wget 可直接下载，最稳。
    ARCH=$(grep -oE 'armv7[a-z0-9.-]+|aarch64[a-z0-9.-]+|mipsel[a-z0-9.-]+' /opt/etc/opkg.conf | head -1)
    [ -z "$ARCH" ] && ARCH=armv7sf-k3.2
    sed -i -E "s#(src/gz[[:space:]]+[^[:space:]]+[[:space:]]+)https?://[^[:space:]]+#\1http://bin.entware.net/$ARCH#g" /opt/etc/opkg.conf
    echo "已将 opkg 源切换为官方源（http，设备可直接下载）: http://bin.entware.net/$ARCH"
    grep 'src/gz' /opt/etc/opkg.conf
    # 清掉上次可能缓存的错误索引，强制重新拉取
    rm -f /opt/var/opkg-lists/* 2>/dev/null
  fi
  echo "更新软件列表 (opkg update)..."
  /opt/bin/opkg update 2>&1 | tail -5

  # jq
  command -v jq >/dev/null 2>&1 || { echo "正在安装 jq..."; /opt/bin/opkg install jq 2>&1 | tail -3; }
  # python3
  command -v python3 >/dev/null 2>&1 || { echo "正在安装 python3..."; /opt/bin/opkg install python3 2>&1 | tail -3; }
  # tesseract 主程序（动态发现包名，兼容不同架构/版本）
  if command -v tesseract >/dev/null 2>&1; then
    echo "tesseract 已存在，跳过主程序安装"
  else
    echo "正在从官方源安装 tesseract 主程序..."
    TESS_PKG=$(/opt/bin/opkg list 2>/dev/null | grep -iE '^tesseract ' | awk '{print $1}' | head -1)
    [ -z "$TESS_PKG" ] && TESS_PKG=$(/opt/bin/opkg list 2>/dev/null | grep -iE '^tesseract-ocr ' | awk '{print $1}' | head -1)
    if [ -z "$TESS_PKG" ]; then
      echo "镜像中未找到 tesseract 主包。当前架构可用的 tesseract 相关包："
      /opt/bin/opkg list 2>/dev/null | grep -i tesseract | head
      echo "（若上面为空，请贴出 cat /opt/etc/opkg.conf 和 opkg print-architecture 的输出）"
    else
      echo "发现 tesseract 包: $TESS_PKG"
      /opt/bin/opkg install "$TESS_PKG" 2>&1 | tail -5
    fi
  fi
  # 英文语言包：官方源提供 tesseract-data-eng（中文源里没有，单独用 curl 拉，见下）
  /opt/bin/opkg install tesseract-data-eng 2>&1 | tail -2
  command -v tesseract >/dev/null 2>&1 && echo "tesseract 安装成功: $(tesseract --version 2>&1 | head -1)" || echo "tesseract 仍未安装，请检查上面 opkg update/install 的输出"
  # 中文训练数据兜底：用 curl（支持 TLS）从 GitHub 拉取
  TESS=/opt/share/tessdata
  if ! [ -f "$TESS/chi_sim.traineddata" ]; then
    echo "尝试用 curl 从 GitHub 下载 chi_sim 训练数据..."
    command -v curl >/dev/null 2>&1 || /opt/bin/opkg install curl 2>&1 | tail -2
    mkdir -p "$TESS"
    curl -fsSL -o "$TESS/chi_sim.traineddata" https://github.com/tesseract-ocr/tessdata_fast/raw/main/chi_sim.traineddata \
      && echo "chi_sim.traineddata 已下载" || echo "警告: 无法下载中文训练数据，OCR 中文将不可用（英文仍可）。"
  fi
else
  echo "警告: 未找到 /opt/bin/opkg。依赖安装跳过。请先按博客绑定 /opt 后重跑本脚本。"
fi

echo "==== 部署完成 ===="
echo "启动: sh $DIR/start.sh"
echo "停止: sh $DIR/stop.sh"
echo "浏览器打开: http://<词典笔IP>:8080/"
