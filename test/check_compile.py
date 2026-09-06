#!/usr/bin/env python3
# 对发布包里的 server.py / screen.py 直接做 py_compile 校验。
# （旧版从 deploy.sh 的 heredoc 抽取内嵌段校验；内嵌方式已废弃，程序文件已独立。）
import os, sys, py_compile, tempfile, traceback

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = ["server.py", "screen.py"]

ok = True
for name in TARGETS:
    p = os.path.join(BASE, name)
    if not os.path.isfile(p):
        ok = False
        print("[FAIL] %s: 文件不存在（应在发布包根目录）" % name)
        continue
    fd, tmp = tempfile.mkstemp(suffix=".pyc", prefix=name + "_")
    os.close(fd)
    try:
        py_compile.compile(p, doraise=True, cfile=tmp)
        print("[OK] %s: %d bytes" % (name, os.path.getsize(p)))
    except py_compile.PyCompileError as e:
        ok = False
        print("[FAIL] %s: %s" % (name, e))
        traceback.print_exc()
    finally:
        try: os.unlink(tmp)
        except OSError: pass

sys.exit(0 if ok else 1)
