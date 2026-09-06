#!/bin/sh
# deploy.sh - 在作业帮词典笔 S2 部署 penweb（依赖安装 + 文件校验 + 开机自启）
#
# 用法：把本文件与下面 6 个程序文件一起上传到设备的 /sys_data/penweb/ 后执行：
#   server.py / screen.py / start.sh / stop.sh / ingest.sh / ocr.sh
#（deploy.sh 自身位置不限，但 6 个程序文件必须在 /sys_data/penweb/ 下）
#
# 本脚本不再内嵌任何程序代码；程序文件以发布包里的源文件为准，改完重传即可。
set -e
DIR=/sys_data/penweb
mkdir -p "$DIR"
touch "$DIR/store.txt" "$DIR/.lastscan"

# ---------- 校验 6 个程序文件是否齐全 ----------
MISSING=""
for f in server.py screen.py start.sh stop.sh ingest.sh ocr.sh; do
  [ -f "$DIR/$f" ] || MISSING="$MISSING $f"
done
if [ -n "$MISSING" ]; then
  echo "错误: 以下程序文件不在 $DIR/ 下，请先上传后重试:$MISSING"
  echo "上传方法见 README「三、部署 penweb」一节。"
  exit 1
fi
chmod +x "$DIR"/*.sh "$DIR"/*.py

# ---------- 高清渲染依赖 Pillow(PIL)，本设备已自带(12.0.0)；若缺失则尝试安装一次 ----------
if ! /opt/bin/python3 -c "import PIL" >/dev/null 2>&1; then
  echo "[penweb] 未检测到 Pillow，尝试安装（失败则屏幕功能不可用）"
  opkg install python3-pillow >/dev/null 2>&1 || opkg install python3-PIL >/dev/null 2>&1 || true
fi

# ---------- 配置软件源并安装依赖（jq / python3 / tesseract / 中文语言包）----------
# 说明：清华/中科大的 Entware 镜像实际路径是 404（不镜像该架构目录），
# 而设备自带 wget 不支持 TLS（无法走 https）。官方 bin.entware.net 同时支持
# 纯 http 且索引完整，设备 wget 可直接下载，最稳。
export PATH=/opt/bin:/opt/sbin:$PATH 2>/dev/null

if [ -x /opt/bin/opkg ]; then
  if [ -f /opt/etc/opkg.conf ]; then
    # 取出架构（如 armv7sf-k3.2），把每条 src 行【整条 URL 重写】为官方源。
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
  /opt/bin/opkg install python3-pillow 2>&1 | tail -2 || true
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

# ---------- 开机自启：写入 /data/pre_run.sh（重启后自动恢复 /opt 绑定并启动 penweb）----------
PR=/data/pre_run.sh
MARK=PENWEB_AUTOSTART
if [ -f "$PR" ] && grep -q "$MARK" "$PR"; then
  echo "开机自启已配置，跳过（标记 $MARK 已存在）"
else
  if [ -f "$PR" ]; then
    cat >> "$PR" <<PENWEB_PR_EOF

# >>> $MARK >>>
[ -x /opt/bin/opkg ] || { [ -d /sys_data/opt ] && mount --bind /sys_data/opt /opt 2>/dev/null; }
( sleep 6; sh /sys_data/penweb/start.sh >/dev/null 2>&1 ) &
# <<< $MARK <<<
PENWEB_PR_EOF
  else
    cat > "$PR" <<PENWEB_PR_EOF
#!/bin/sh
# >>> $MARK >>>
[ -x /opt/bin/opkg ] || { [ -d /sys_data/opt ] && mount --bind /sys_data/opt /opt 2>/dev/null; }
( sleep 6; sh /sys_data/penweb/start.sh >/dev/null 2>&1 ) &
exit 0
# <<< $MARK <<<
PENWEB_PR_EOF
    chmod +x "$PR"
  fi
  echo "已配置开机自启: $PR"
fi

echo "==== 部署完成 ===="
echo "启动: sh $DIR/start.sh"
echo "停止: sh $DIR/stop.sh"
echo "浏览器打开: http://<词典笔IP>:8080/"
