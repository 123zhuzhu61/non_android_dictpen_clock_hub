#!/usr/bin/env python3
# 从 deploy.sh 提取两段 heredoc 的 Python 内容并 py_compile 校验。
import re, sys, py_compile, tempfile, os, traceback
src = open(r"E:\WorkBuddy\词典笔\penweb\deploy.sh", encoding="utf-8").read()
parts = re.findall(r"<<'([A-Z_]+)'\n(.*?)\n[A-Z_]+\n", src, flags=re.DOTALL)
ok = True
for tag, body in parts:
    if tag not in ("PENWEB_SERVER_EOF", "PENWEB_SCREEN_EOF"):
        continue
    fd, p = tempfile.mkstemp(suffix=".py", prefix=tag+"_")
    os.close(fd)
    open(p, "w", encoding="utf-8").write(body)
    try:
        py_compile.compile(p, doraise=True)
        print("[OK] %s: %d bytes" % (tag, len(body)))
    except py_compile.PyCompileError as e:
        ok = False
        print("[FAIL] %s: %s" % (tag, e))
        traceback.print_exc()
    finally:
        os.unlink(p)
sys.exit(0 if ok else 1)