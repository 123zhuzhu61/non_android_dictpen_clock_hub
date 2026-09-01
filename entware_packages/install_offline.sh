#!/bin/sh
# ============================================================
# install_offline.sh — penweb 依赖离线安装脚本
#
# 用法：把本脚本和 ipk/ 文件夹一起上传到设备（如 /sys_data/offline/），
# 然后执行：
#   mkdir -p /sys_data/opt
#   mount --bind /sys_data/opt /opt
#   export PATH=/opt/bin:/opt/sbin:$PATH
#   sh /sys_data/offline/install_offline.sh
#
# 前提：Entware 本体已装好（/opt/bin/opkg 存在）。
# 特性：已安装的包自动跳过，依赖顺序由 opkg 自动处理，可重复执行。
# ============================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
IPK_DIR="$DIR/ipk"
[ -d "$IPK_DIR" ] || IPK_DIR="$DIR"

OPKG=/opt/bin/opkg
[ -x "$OPKG" ] || OPKG="$(command -v opkg 2>/dev/null)"
if [ -z "$OPKG" ]; then
  echo "错误: 找不到 opkg。请先按教程装好 Entware（/opt/bin/opkg），再运行本脚本。"
  exit 1
fi

if ! ls "$IPK_DIR"/*.ipk >/dev/null 2>&1; then
  echo "错误: $IPK_DIR 下没有 .ipk 文件。请确认 ipk 文件夹已完整上传。"
  exit 1
fi

count=$(ls "$IPK_DIR"/*.ipk | wc -l)
echo "ipk 目录: $IPK_DIR（共 $count 个包）"
echo "开始安装，已安装的包会自动跳过 ..."
echo "------------------------------------------------"

cd "$IPK_DIR" || exit 1
fail=0
for f in *.ipk; do
  out=$("$OPKG" install "$f" 2>&1)
  if echo "$out" | grep -qiE 'is up to date|installed|Configuring'; then
    echo "  [OK] $f"
  else
    echo "  [失败] $f"
    echo "$out" | tail -3 | sed 's/^/         /'
    fail=$((fail+1))
  fi
done

echo "------------------------------------------------"
if [ "$fail" -eq 0 ]; then
  echo "全部安装完成。开始验证："
  echo ""
  python3 --version 2>&1
  jq --version 2>&1
  tesseract --version 2>&1 | head -1
  echo ""
  echo "三个命令都有版本号输出即就绪。接下来可执行: sh /sys_data/deploy.sh"
else
  echo "有 $fail 个包安装失败，请把上面的输出发给作者排查。"
fi
