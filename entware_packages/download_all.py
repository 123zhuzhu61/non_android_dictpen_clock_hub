# -*- coding: utf-8 -*-
"""批量下载 Entware ipk 到本地，供设备离线安装"""
import os
import sys
import time
import urllib.request

BASE_DIR = r"E:\WorkBuddy\词典笔\entware_packages"
OUT = os.path.join(BASE_DIR, "ipk")
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(BASE_DIR, "download_list.txt"), encoding="utf-8") as f:
    urls = [u.strip() for u in f if u.strip()]

print(f"共 {len(urls)} 个文件", flush=True)
fail = []
for i, url in enumerate(urls, 1):
    fn = url.rsplit("/", 1)[-1]
    dest = os.path.join(OUT, fn)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"[{i}/{len(urls)}] 已存在，跳过 {fn}", flush=True)
        continue
    ok = False
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
            data = urllib.request.urlopen(req, timeout=300).read()
            with open(dest, "wb") as f:
                f.write(data)
            print(f"[{i}/{len(urls)}] {fn} ({len(data)//1024} KB)", flush=True)
            ok = True
            break
        except Exception as e:
            print(f"[{i}/{len(urls)}] 第{attempt+1}次失败 {fn}: {e}", flush=True)
            time.sleep(3)
    if not ok:
        fail.append(url)

if fail:
    print(f"\n失败 {len(fail)} 个：", file=sys.stderr, flush=True)
    for u in fail:
        print(u, file=sys.stderr, flush=True)
    sys.exit(1)
print("\n全部下载完成", flush=True)
