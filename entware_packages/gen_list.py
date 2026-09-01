# -*- coding: utf-8 -*-
"""解析 Entware Packages.gz，生成 penweb 全部依赖的 ipk 下载清单"""
import gzip
import io
import re
import sys
import urllib.request

ARCH = "armv7sf-k3.2"
BASE = f"http://bin.entware.net/{ARCH}/"
PKGS_URL = BASE + "Packages.gz"

# penweb 需要的根包（deploy.sh 实际安装的）
ROOTS = ["python3", "jq", "tesseract", "tesseract-ocr",
         "tesseract-data-eng", "python3-pillow", "python3-PIL", "curl"]


def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def parse_packages(text):
    pkgs = {}
    for block in re.split(r"\n\n+", text):
        d = {}
        key = None
        for line in block.split("\n"):
            if line.startswith((" ", "\t")) and key:  # 续行
                d[key] += " " + line.strip()
                continue
            if ":" in line:
                key, _, v = line.partition(":")
                d[key.strip()] = v.strip()
        name = d.get("Package")
        if name and name not in pkgs:  # 同名取第一个（通常为最新）
            pkgs[name] = d
    return pkgs


def build_provides_map(pkgs):
    """虚拟包名 -> 实际包名列表（opkg 的 Provides 字段）"""
    m = {}
    for name, p in pkgs.items():
        for prov in p.get("Provides", "").split(","):
            prov = prov.strip()
            if prov:
                m.setdefault(prov, []).append(name)
    return m


def resolve_deps(pkgs, roots):
    provides = build_provides_map(pkgs)
    seen, missing = set(), []
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        p = pkgs.get(name)
        if not p:
            # 尝试虚拟包名
            alts = provides.get(name)
            if alts:
                p = pkgs[alts[0]]
            else:
                missing.append(name)
                continue
        seen.add(p["Package"])
        for dep in p.get("Depends", "").split(","):
            dep = dep.strip()
            if not dep:
                continue
            dep = re.split(r"[ (]", dep)[0]  # 剥离版本约束
            stack.append(dep)
    return seen, missing


def main():
    print("下载 Packages 索引 ...")
    raw = fetch(PKGS_URL)
    text = gzip.decompress(raw).decode("utf-8", "replace")
    pkgs = parse_packages(text)
    print(f"索引中共 {len(pkgs)} 个包")

    # 找出 tesseract 的实际包名
    tess_names = [n for n in pkgs if n.lower().startswith("tesseract") and "data" not in n]
    print("tesseract 相关包:", tess_names[:5])

    roots = [r for r in ROOTS if r in pkgs]
    roots += [n for n in tess_names if n in pkgs and n not in roots]
    seen, missing = resolve_deps(pkgs, roots)

    print(f"\n需要下载 {len(seen)} 个包（含依赖）：")
    lines, total = [], 0
    for name in sorted(seen):
        p = pkgs[name]
        fn = p.get("Filename", "")
        size = int(p.get("Size", 0) or 0)
        total += size
        if fn:
            lines.append(BASE + fn)
    for m in missing:
        print(f"  [警告] 索引中不存在: {m}", file=sys.stderr)

    out = r"E:\WorkBuddy\词典笔\entware_packages\download_list.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n清单已写入: {out}")
    print(f"总大小约 {total / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
