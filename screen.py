#!/opt/bin/python3
# -*- coding: utf-8 -*-
# screen.py — 高清真实字体渲染（Pillow + 设备 TTF），叠加绘制 + FBIOPAN_DISPLAY 上屏
#
# 安全原则（与之前一致）：完全不杀词典笔主程序、不碰看门狗——不会重启、不会卡死。
# 显示期间每 2 秒防熄屏保活（解除 blank + 背光拉到目标亮度 + wake_lock）；恢复(idle)时释放。
#
# 功能：
#   * 高清真实字体：Pillow(PIL) + 设备自带 TTF，灰阶抗锯齿，支持中文/英文/数字。
#   * 自定义文字：写 screen_text.conf，模式切到 text 即显示（支持换行、自适应字号）。
#   * 颜色：文字 screen_fg.conf、背景 screen_bg.conf（#RRGGBB 或 R,G,B）。
#   * 镜像翻转：screen_flip.conf 取值 none/h/v/hv，默认 "h"（本设备已验证正确）。
#   * 加粗：screen_bold.conf = 0/1（对时钟/文字/日期生效，用膨胀掩膜合成粗体）。
#   * 滚动：screen_scroll.conf = 0/1（仅文字模式；字保持原大，横向循环滚动）。
#   * 滚动速度：screen_scroll_speed.conf = 整数 px/秒（默认 55，网页可调 5~400）。
#   * 垂直微调：screen_voff.conf = 整数像素（正数=上移、负数=下移；复位/默认值为 0）。
#   * 亮度：brightness.conf = 0~max（默认满亮）；keep_awake 写入目标亮度（不再强制满亮）。
#   * 天气：rotate 模式下的 "weather" 项；联网抓 open-meteo，城市由 weather_city.conf 指定。
#   * 日期：rotate 模式下的 "date" 项；显示「年月日 + 星期」。
#   * 轮换：rotate 模式；按 rotate_items.conf 列出的子集（clock/weather/date）循环全屏显示。
#   * 声音：play_beep_local() 通过 aplay 播放 beep.wav（轮换切换提示音）。
import os, time, mmap, struct, glob as _glob, re, subprocess, threading, math, json
try:
    import fcntl
except Exception:
    fcntl = None                      # Windows 测试环境无 fcntl；真实设备(Linux)会有

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    HAVE_PIL = True
except Exception:
    Image = ImageDraw = ImageFont = ImageFilter = None
    HAVE_PIL = False

# 设备系统时区常为 UTC，这里强制东八区，保证时钟显示北京时间
os.environ["TZ"] = "CST-8"
try:
    time.tzset()
except Exception:
    pass

FBDEV     = "/dev/fb0"
MODE_FILE = "/tmp/penweb_mode"        # idle | test | clock | clear | text | rotate
PID_FILE  = "/tmp/penweb_screen.pid"
FLIP_FILE = "/sys_data/penweb/screen_flip.conf"
TEXT_FILE = "/sys_data/penweb/screen_text.conf"
FG_FILE   = "/sys_data/penweb/screen_fg.conf"
BG_FILE   = "/sys_data/penweb/screen_bg.conf"
BOLD_FILE = "/sys_data/penweb/screen_bold.conf"
SCROLL_FILE = "/sys_data/penweb/screen_scroll.conf"
VOFF_FILE = "/sys_data/penweb/screen_voff.conf"
BRIGHT_FILE = "/sys_data/penweb/brightness.conf"
ROTATE_ITEMS_FILE = "/sys_data/penweb/rotate_items.conf"
ROTATE_DUR_FILE = "/sys_data/penweb/rotate_dur.conf"
ROTATE_SOUND_FILE = "/sys_data/penweb/rotate_sound.conf"
ROTATE_SOUND_VOL_FILE = "/sys_data/penweb/rotate_sound_vol.conf"
WEATHER_CITY_FILE = "/sys_data/penweb/weather_city.conf"
WEATHER_CACHE_FILE = "/sys_data/penweb/weather_cache.json"
BEEP_FILE = "/sys_data/penweb/beep.wav"
ALARM_ACTIVE_FILE = "/sys_data/penweb/alarm_active.conf"
OVERLAY_FILE = "/sys_data/penweb/overlay.json"
TIMER_FILE = "/sys_data/penweb/timer_state.json"
LOG       = "/tmp/penweb_screen.log"

DEFAULT_FLIP = "h"
DEFAULT_VOFF = 0                       # 复位/默认值为 0（不再强制补偿，按需用垂直微调上移/下移）
SCROLL_SPEED = 55                      # 滚动速度默认值 px/秒（网页可调 5~400）
SCROLL_GAP   = 70                      # 滚动时两次文字之间的间隔 px
SCROLL_SPEED_FILE = "/sys_data/penweb/screen_scroll_speed.conf"
DEFAULT_CITY = "北京"

def log(msg):
    try:
        with open(LOG, "a") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except Exception:
        pass

def read_overlay():
    try:
        with open(OVERLAY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
def clear_overlay():
    try:
        os.remove(OVERLAY_FILE)
    except Exception:
        pass
def fmt_timer(secs):
    secs = int(secs)
    if secs < 0:
        secs = 0
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h > 0:
        return "%d:%02d:%02d" % (h, m, s)
    return "%02d:%02d" % (m, s)

# ---------- 帧缓冲 ioctl ----------
FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602
FBIOPAN_DISPLAY     = 0x4606

def read_geometry():
    """读取 /dev/fb0 真实参数（横屏：显存 170(宽) x 560(高/页)，逻辑 560 x 170）。"""
    fd = os.open(FBDEV, os.O_RDWR)
    try:
        vb = bytearray(160)
        fcntl.ioctl(fd, FBIOGET_VSCREENINFO, vb)
        xs  = struct.unpack_from("<I", vb, 0)[0]
        ys  = struct.unpack_from("<I", vb, 4)[0]
        xsv = struct.unpack_from("<I", vb, 8)[0]
        ysv = struct.unpack_from("<I", vb, 12)[0]
        bpp = struct.unpack_from("<I", vb, 20)[0]
        fb = bytearray(80)
        fcntl.ioctl(fd, FBIOGET_FSCREENINFO, fb)
        smem = struct.unpack_from("<I", fb, 20)[0]
        line = struct.unpack_from("<I", fb, 44)[0]
    finally:
        os.close(fd)
    if line == 0:
        line = xs * (bpp // 8)
    if xsv == 0: xsv = xs
    if ysv == 0: ysv = ys
    if smem == 0:
        smem = xsv * ysv * bpp // 8
    return dict(xs=xs, ys=ys, xsv=xsv, ysv=ysv, bpp=bpp, line=line, smem=smem)

# ---------- 颜色 / 配置读取 ----------
def read_file(path, default=""):
    try:
        return open(path, encoding="utf-8").read().strip()
    except Exception:
        return default

def read_int(path, default):
    s = read_file(path)
    try:
        return int(s)
    except Exception:
        return default

def read_bool(path, default=False):
    s = read_file(path)
    if s == "":
        return default
    return s in ("1", "true", "on", "yes")

def parse_color(s, default):
    s = (s or "").strip()
    if not s:
        return default
    s = s.lstrip("#")
    try:
        if len(s) == 6:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        if "," in s:
            parts = s.split(",")
            if len(parts) >= 3:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
    except Exception:
        pass
    return default

def rgb565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

# ---------- 字体 ----------
FONT_CANDIDATES = [
    "/mnt/userapp/lfs/font.ttf",
    "/mnt/userdict/DroidSansFallback.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/NotoSansSC-VF.ttf",
]

_font_cache = None
def find_font():
    global _font_cache
    if _font_cache is not None:
        return _font_cache
    if not HAVE_PIL:
        log("PIL 不可用，无法渲染真实字体"); _font_cache = False; return False
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            _font_cache = f; log("font found: %s" % f); return f
    for base in ["/usr/share/fonts", "/system/fonts", "/opt/share/fonts",
                 "/mnt/userdict", "/mnt/userapp", "/data/fonts"]:
        if not os.path.isdir(base):
            continue
        for pat in ("*.ttf", "*.ttc", "*.otf"):
            for f in _glob.glob(base + "/**/" + pat, recursive=True):
                low = f.lower()
                if any(k in low for k in ("cjk", "hei", "song", "wqy", "droid",
                                          "noto", "fallback", "sc", "cn", "gothic",
                                          "ming", "sans")):
                    _font_cache = f; log("font fallback: %s" % f); return f
    _font_cache = False
    log("no font found (中文将不可用，仅能渲染英文/数字)")
    return False

# 真实字体对象缓存（按 path+size），避免每帧重新加载 10MB 字体导致滚动卡顿
_TT_CACHE = {}
def get_tt(path, size):
    key = (path, int(size))
    f = _TT_CACHE.get(key)
    if f is None:
        f = ImageFont.truetype(path, int(size))
        if len(_TT_CACHE) < 32:
            _TT_CACHE[key] = f
    return f

def _wrap_text(text, d, f, max_w):
    """按字符折行（遇 \n 强制换行），返回行列表。"""
    lines = []
    for para in text.split("\n"):
        if para == "":
            lines.append(""); continue
        cur = ""
        for ch in para:
            t = cur + ch
            try:
                w = d.textlength(t, font=f)
            except Exception:
                w = len(t) * f.size * 0.6
            if w <= max_w or not cur:
                cur = t
            else:
                lines.append(cur); cur = ch
        lines.append(cur)
    return lines

def _fit_size(text, font_path, max_w, max_h, wrap):
    """二分搜索能放下文字的最大字号（wrap=True 同时受宽高约束；否则仅按单行长宽）。"""
    lo, hi, best = 6, 400, 6
    while lo <= hi:
        mid = (lo + hi) // 2
        try:
            f = get_tt(font_path, mid)
        except Exception:
            return best
        d = ImageDraw.Draw(Image.new("RGB", (16, 16)))
        if wrap:
            lines = _wrap_text(text, d, f, max_w)
            lh = int(mid * 1.3)
            maxw = max((d.textlength(ln, font=f) for ln in lines), default=0)
            ok = (maxw <= max_w) and (lh * len(lines) <= max_h)
        else:
            bb = d.textbbox((0, 0), text, font=f)
            ok = ((bb[2] - bb[0]) <= max_w) and ((bb[3] - bb[1]) <= max_h)
        if ok:
            best = mid; lo = mid + 1
        else:
            hi = mid - 1
    return best

# ---------- 方向（镜像翻转，兼容其他设备） ----------
ORIENT = {
    "none": [],
    "h":    [Image.FLIP_LEFT_RIGHT],        # 水平镜像（本设备已验证正确）
    "v":    [Image.FLIP_TOP_BOTTOM],        # 垂直镜像
    "hv":   [Image.FLIP_LEFT_RIGHT, Image.FLIP_TOP_BOTTOM],
}
DEFAULT_FLIP = "h"

def read_flip():
    s = read_file(FLIP_FILE)
    if s not in ORIENT:
        s = DEFAULT_FLIP
    return s

def apply_orient(img, flip):
    for op in ORIENT.get(flip, ORIENT[DEFAULT_FLIP]):
        img = img.transpose(op)
    return img

# ---------- 帧缓冲写屏 ----------
class FB:
    def __init__(self, geo):
        self.geo = geo
        self.fd = os.open(FBDEV, os.O_RDWR)
        self.mm = mmap.mmap(self.fd, geo["smem"])
    def show(self, M):
        n = len(M)
        self.mm[0:n] = M
        # 复制到所有缓冲页：显示引擎无论取哪一页都是同一画面
        off = n
        smem = len(self.mm)
        while off + n <= smem:
            self.mm[off:off + n] = M
            off += n
        vb = bytearray(160)
        fcntl.ioctl(self.fd, FBIOGET_VSCREENINFO, vb)
        struct.pack_into("<I", vb, 16, 0)        # yoffset=0
        fcntl.ioctl(self.fd, FBIOPAN_DISPLAY, vb)
    def close(self):
        try: self.mm.close()
        except Exception: pass
        try: os.close(self.fd)
        except Exception: pass

# ---------- 防熄屏保活 ----------
_last_awake = [0.0]
def keep_awake():
    now = time.time()
    if now - _last_awake[0] < 2.0:
        return
    _last_awake[0] = now
    try:
        open("/sys/class/graphics/fb0/blank", "w").write("0")
    except Exception:
        pass
    # 写入用户设定的目标亮度（默认满亮）；不再强制 max，从而支持调暗
    target = read_int(BRIGHT_FILE, -1)
    for p in _glob.glob("/sys/class/backlight/*/brightness"):
        try:
            mx = open(os.path.join(os.path.dirname(p), "max_brightness")).read().strip() or "255"
            mx = int(mx)
            if target < 0:
                val = mx
            else:
                val = max(0, min(target, mx))
            open(p, "w").write(str(val))
        except Exception:
            pass
    try:
        open("/sys/power/wake_lock", "w").write("penweb_screen")
    except Exception:
        pass
    try:
        open("/sys/power/autosleep", "w").write("off")
    except Exception:
        pass
    # 注：本设备无 /sys/power/wake_lock 与 /sys/power/autosleep 节点，以上两行是空操作；
    # 真正的防挂起由 start.sh / server._wake_guard 用 mount --bind /sys/power/state 实现。

def release_awake():
    # nowake.conf=0/off 时，解除占位绑定让设备可正常睡眠（由 stop.sh 或本调用触发）
    try:
        os.system("umount /sys/power/state 2>/dev/null")
    except Exception:
        pass

# ---------- 声音（aplay 播放提示音） ----------
def ensure_beep():
    """生成短促提示音 beep.wav（音量按 rotate_sound_vol.conf 缩放，每次重生成以保证最新）。返回文件是否可用。"""
    try:
        import wave, struct as _struct
        vol = read_int(ROTATE_SOUND_VOL_FILE, 80)   # 0~100，默认 80
        if vol < 0: vol = 0
        if vol > 100: vol = 100
        amp = max(0.02, 0.4 * (vol / 100.0))        # 基准振幅0.4，按音量线性缩放
        rate = 22050; dur = 0.18; freq = 880
        n = int(rate * dur)
        w = wave.open(BEEP_FILE, "w")
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        for i in range(n):
            v = int(32767 * amp * math.sin(2 * math.pi * freq * i / rate))
            w.writeframes(_struct.pack("<h", v))
        w.close()
        return True
    except Exception as e:
        log("beep gen fail: %s" % e)
        return False

def play_beep_local():
    if not ensure_beep():
        return
    try:
        subprocess.Popen("aplay %s >/dev/null 2>&1 &" % BEEP_FILE, shell=True)
    except Exception as e:
        log("beep play fail: %s" % e)

# ---------- 渲染 ----------
def _blit(img, text, f, x, y, fg, bold):
    """在 img 上以 (x,y) 为锚点绘制文字；bold 时用膨胀掩膜合成粗体。"""
    if not bold:
        ImageDraw.Draw(img).text((x, y), text, fill=fg, font=f)
        return
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        md.text((x + dx, y + dy), text, fill=255, font=f)
    mask = mask.filter(ImageFilter.MaxFilter(3))
    img.paste(Image.new("RGB", img.size, fg), (0, 0), mask)

def _apply_voff(img, voff, bg):
    """把内容在画面内整体上下平移 voff 像素（正数=上移）以补偿设备显示偏移。"""
    if not voff:
        return img
    base = bg if bg is not None else img.getpixel((0, 0))
    res = Image.new("RGB", img.size, base)
    res.paste(img, (0, -int(voff)))
    return res

def _centered_xy(bb, W, H, slot_top=0, slot_h=None):
    """按文字真实 ink 包围盒计算居中绘制坐标（slot 内垂直居中）。"""
    iw = bb[2] - bb[0]; ih = bb[3] - bb[1]
    x = (W - iw) / 2 - bb[0]
    if slot_h is None:
        y = (H - ih) / 2 - bb[1]
    else:
        y = slot_top + (slot_h - ih) / 2 - bb[1]
    return x, y

def render_text_frame(text, W, H, fg, bg, font, bold, voff):
    """静态文字：居中、自适应字号、自动换行、可选加粗、可垂直微调。"""
    size = _fit_size(text, font, W - 20, H - 10, wrap=True)
    f = get_tt(font, size)
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines = _wrap_text(text, d, f, W - 20)
    lh = int(size * 1.3)
    img = Image.new("RGB", (W, H), bg)
    start_y = (H - lh * len(lines)) // 2
    for i, ln in enumerate(lines):
        bb = d.textbbox((0, 0), ln, font=f)
        x, y = _centered_xy(bb, W, H, slot_top=start_y + i * lh, slot_h=lh)
        _blit(img, ln, f, x, y, fg, bold)
    return _apply_voff(img, voff, bg)

def render_clock_frame(t, W, H, fg, bg, font, bold, voff):
    """时钟：单行、按宽高自适应、居中、可选加粗、可垂直微调。"""
    size = _fit_size(t, font, W - 20, H - 10, wrap=False)
    f = get_tt(font, size)
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bb = d.textbbox((0, 0), t, font=f)
    x, y = _centered_xy(bb, W, H)
    img = Image.new("RGB", (W, H), bg)
    _blit(img, t, f, x, y, fg, bold)
    return _apply_voff(img, voff, bg)

def render_scroll_frame(text, W, H, fg, bg, font, bold, voff, offset):
    """滚动文字：字保持原大（按高度取最大），横向循环滚动。"""
    size = min(H - 10, 150)
    f = get_tt(font, size)
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bb = d.textbbox((0, 0), text, font=f)
    iw = bb[2] - bb[0]; ih = bb[3] - bb[1]
    tw = iw + SCROLL_GAP
    tile = Image.new("RGB", (tw, H), bg)
    x, y = _centered_xy(bb, tw, H)
    _blit(tile, text, f, x, y, fg, bold)
    tile = _apply_voff(tile, voff, bg)
    frame = Image.new("RGB", (W, H), bg)
    base = -(int(offset) % tw)
    x = base
    while x < W:
        frame.paste(tile, (x, 0))
        x += tw
    return frame

def render_date_frame(W, H, fg, bg, font, bold, voff):
    """日期：年月日(上一行) + 星期(下一行)，均居中。"""
    now = time.localtime()
    wd = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][now.tm_wday]
    d1 = "%04d年%02d月%02d日" % (now.tm_year, now.tm_mon, now.tm_mday)
    d2 = wd
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    f1 = get_tt(font, 64)
    bb1 = d.textbbox((0, 0), d1, font=f1)
    x1, y1 = _centered_xy(bb1, W, H, slot_top=int(H * 0.16), slot_h=int(H * 0.42))
    _blit(img, d1, f1, x1, y1, fg, bold)
    f2 = get_tt(font, 50)
    bb2 = d.textbbox((0, 0), d2, font=f2)
    x2, y2 = _centered_xy(bb2, W, H, slot_top=int(H * 0.60), slot_h=int(H * 0.30))
    _blit(img, d2, f2, x2, y2, fg, bold)
    return _apply_voff(img, voff, bg)

def render_info_frame(big, label, W, H, fg, bg, font, bold, voff):
    """通用信息画面（与闹钟同一套 UI）：上方大字号显示 big，下方左对齐显示 label，
    label 过长自右向左跑马灯滚动；底部右对齐『点击屏幕关闭』。计时/闹钟共用。"""
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    LX = 14  # 左对齐基准（时间/标签共用，形成一体块）
    # 上方：大字号（当前时间 / 计时值）
    f1 = get_tt(font, 100)
    bb1 = d.textbbox((0, 0), big, font=f1)
    y1 = _centered_xy(bb1, W, H, slot_top=2, slot_h=int(H * 0.48))[1]
    _blit(img, big, f1, LX, y1, fg, bold)
    # 下方：标签（左对齐于 LX，过长滚动）
    if label:
        f2 = get_tt(font, 34)
        bb2 = d.textbbox((0, 0), label, font=f2)
        tw = bb2[2] - bb2[0]
        th = bb2[3] - bb2[1]
        slot_top = int(H * 0.52)
        slot_h = int(H * 0.32)
        y2 = slot_top + (slot_h - th) / 2 - bb2[1]
        avail_w = W - LX - 14
        if tw <= avail_w:
            _blit(img, label, f2, LX, y2, fg, bold)
        else:
            speed = 70  # px/s
            pad = 60
            period = tw + pad
            off = (time.time() * speed) % period
            x0 = LX - off
            _blit(img, label, f2, x0, y2, fg, bold)
            _blit(img, label, f2, x0 + period, y2, fg, bold)
    # 底部提示
    f3 = get_tt(font, 24)
    tip = "点击屏幕关闭"
    bb3 = d.textbbox((0, 0), tip, font=f3)
    x3 = W - 14 - (bb3[2] - bb3[0])
    y3 = _centered_xy(bb3, W, H, slot_top=int(H * 0.86), slot_h=int(H * 0.14))[1]
    _blit(img, tip, f3, x3, y3, fg, bold)
    return _apply_voff(img, voff, bg)

def render_alarm_frame(label, W, H, fg, bg, font, bold, voff):
    """闹钟响铃画面：上方显示当前时间，下方标签，UI 同计时。"""
    now = time.strftime("%H:%M", time.localtime())
    return render_info_frame(now, label, W, H, fg, bg, font, bold, voff)

def render_timer_frame(ov, W, H, fg, bg, font, bold, voff):
    """倒计时画面：上方大字剩余时间，下方标签；到点显示“时间到”。"""
    if ov.get("finished"):
        big = "时间到"
    else:
        start = ov.get("start_ts", time.time())
        dur = ov.get("duration", 0)
        big = fmt_timer(max(0, dur - (time.time() - start)))
    return render_info_frame(big, ov.get("label", ""), W, H, fg, bg, font, bold, voff)

def render_message_frame(ov, W, H, fg, bg, font, bold, voff):
    """消息投送文字画面：居中显示文字（过长横向跑马灯）+ 底部点击关闭提示。"""
    text = ov.get("label", "") or " "
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    LX = 14
    f = get_tt(font, 40)
    bb = d.textbbox((0, 0), text, font=f)
    tw = bb[2] - bb[0]
    th = bb[3] - bb[1]
    avail_w = W - LX * 2
    y = (H - th) / 2 - bb[1]
    if tw <= avail_w:
        _blit(img, text, f, LX, y, fg, bold)
    else:
        speed = 70
        pad = 50
        period = tw + pad
        off = (time.time() * speed) % period
        _blit(img, text, f, LX - off, y, fg, bold)
        _blit(img, text, f, LX - off + period, y, fg, bold)
    f3 = get_tt(font, 22)
    tip = "点击屏幕关闭"
    bb3 = d.textbbox((0, 0), tip, font=f3)
    x3 = W - 14 - (bb3[2] - bb3[0])
    y3 = H - 26
    _blit(img, tip, f3, x3, y3, fg, bold)
    return _apply_voff(img, voff, bg)

# ---------- 天气 ----------
WMO_DESC = {
    0: "晴", 1: "大致晴朗", 2: "局部多云", 3: "阴",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "阵雨", 81: "阵雨", 82: "强阵雨",
    85: "阵雪", 86: "阵雪",
    95: "雷阵雨", 96: "雷阵雨伴冰雹", 99: "雷阵雨伴冰雹",
}
CITY_ALIAS = {
    "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou", "深圳": "Shenzhen",
    "杭州": "Hangzhou", "成都": "Chengdu", "武汉": "Wuhan", "南京": "Nanjing",
    "西安": "Xi'an", "重庆": "Chongqing", "天津": "Tianjin", "苏州": "Suzhou",
    "香港": "Hong Kong", "台北": "Taipei", "青岛": "Qingdao", "厦门": "Xiamen",
    "长沙": "Changsha", "郑州": "Zhengzhou", "济南": "Jinan", "合肥": "Hefei",
    "昆明": "Kunming", "贵阳": "Guiyang", "兰州": "Lanzhou", "沈阳": "Shenyang",
    "哈尔滨": "Harbin", "大连": "Dalian", "宁波": "Ningbo", "无锡": "Wuxi",
}

def _resolve_city(city):
    """城市名 -> (lat, lon, 显示名)。失败回退北京。"""
    city = (city or DEFAULT_CITY).strip() or DEFAULT_CITY
    q = CITY_ALIAS.get(city, city)
    try:
        import urllib.request, urllib.parse, json
        gurl = "https://geocoding-api.open-meteo.com/v1/search?name=%s&count=1&language=zh" % urllib.parse.quote(q)
        req = urllib.request.Request(gurl, headers={"User-Agent": "penweb"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.load(r)
        res = (d.get("results") or [])
        if res:
            g = res[0]
            return float(g["latitude"]), float(g["longitude"]), g.get("name", q)
    except Exception as e:
        log("geocode fail(%s): %s" % (q, e))
    return 39.9042, 116.4074, city

def fetch_weather(city):
    """抓 open-meteo 当前天气。返回 dict（含 temp/desc/name 或 error）。"""
    try:
        import urllib.request, json
        lat, lon, name = _resolve_city(city)
        url = ("https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f"
               "&current=temperature_2m,weather_code") % (lat, lon)
        req = urllib.request.Request(url, headers={"User-Agent": "penweb"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.load(r)
        cur = d.get("current", {})
        temp = cur.get("temperature_2m")
        code = cur.get("weather_code")
        if temp is None and "temperature" in cur:
            temp = cur.get("temperature")
        return {"temp": temp, "code": code, "name": name,
                "desc": WMO_DESC.get(code, "未知")}
    except Exception as e:
        return {"error": str(e)}

_WX = {"data": {"loading": True}, "t": 0.0, "city": None}
def _wx_refresh(city):
    _WX["data"] = fetch_weather(city)
    _WX["t"] = time.time()
    _WX["city"] = city

def wx_ensure(city, force=False):
    """后台刷新天气（避免阻塞主循环）；loading、超时(300s)、或城市变更 才刷新。"""
    if city != _WX.get("city"):
        force = True
    if force or _WX["data"].get("loading") or (time.time() - _WX["t"] > 300):
        threading.Thread(target=_wx_refresh, args=(city,), daemon=True).start()

def screen_weather(city):
    """优先读 server 写入的共享天气缓存（与网页完全一致）；缺失/损坏时回退本机抓取。"""
    try:
        with open(WEATHER_CACHE_FILE, encoding="utf-8") as f:
            c = json.load(f)
        d = c.get("data")
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    # 回退：本机抓取一次（server 尚未写入缓存时）
    wx_ensure(city, force=True)
    return _WX["data"]

def render_weather_frame(info, W, H, fg, bg, font, bold, voff):
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    if not isinstance(info, dict) or info.get("loading"):
        _blit(img, "天气加载中…", get_tt(font, 50), *_centered_xy(
            d.textbbox((0, 0), "天气加载中…", font=get_tt(font, 50)), W, H), fg, bold)
        return _apply_voff(img, voff, bg)
    if "error" in info:
        msg = "天气获取失败"
        _blit(img, msg, get_tt(font, 50), *_centered_xy(
            d.textbbox((0, 0), msg, font=get_tt(font, 50)), W, H), fg, bold)
        return _apply_voff(img, voff, bg)
    name = info.get("name", "")
    temp = info.get("temp")
    desc = info.get("desc", "")
    # 布局：温度在左栏（大字，垂直居中）；城市+气象在右栏（右对齐）。
    # 在本设备实测下，最终屏显≈L-space，故 L-space 左=屏左、右=屏右。
    # 温度（左栏，垂直居中）
    tstr = ("%.0f°" % temp) if temp is not None else "--°"
    ft = get_tt(font, 132)
    bt = d.textbbox((0, 0), tstr, font=ft)
    tw = bt[2] - bt[0]
    lx = int(W * 0.28)                       # 左栏中心
    tx = lx - tw / 2 - bt[0]
    ty = (H - (bt[3] - bt[1])) / 2 - bt[1]
    _blit(img, tstr, ft, tx, ty, fg, bold)
    # 右栏右边缘
    rx_edge = W - 14
    # 城市名（右栏顶部，右对齐）
    f1 = get_tt(font, 30)
    cb = d.textbbox((0, 0), name, font=f1)
    cx = rx_edge - (cb[2] - cb[0]) - cb[0]
    d.text((cx, 12), name, fill=fg, font=f1)
    # 气象描述（右栏下半，垂直居中于该槽，右对齐）
    f3 = get_tt(font, 54)
    maxw = int(W * 0.42)
    while d.textbbox((0, 0), desc, font=f3)[2] > maxw and f3.size > 18:
        f3 = get_tt(font, f3.size - 2)
    bb3 = d.textbbox((0, 0), desc, font=f3)
    dx = rx_edge - (bb3[2] - bb3[0]) - bb3[0]
    dy = _centered_xy(bb3, W, H, slot_top=int(H * 0.42), slot_h=int(H * 0.50))[1]
    _blit(img, desc, f3, dx, dy, fg, bold)
    return _apply_voff(img, voff, bg)

def landscape_to_memory(L, xs, ys, W, H, flip):
    """横屏图 L(W x H) -> 显存 M(xs x ys) 的 bytes（RGB565）。"""
    D = apply_orient(L, flip)              # W x H
    M = D.transpose(Image.TRANSPOSE)       # H x W = xs x ys（与显存一致）
    data = M.tobytes()                     # 行主序 RGB
    out = bytearray(len(data) // 3 * 2)
    o = 0
    for i in range(0, len(data), 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        v = rgb565(r, g, b)
        out[o] = v & 0xff
        out[o + 1] = (v >> 8) & 0xff
        o += 2
    return bytes(out)

# ---------- 模式循环 ----------
def get_mode():
    try:
        return open(MODE_FILE).read().strip()
    except Exception:
        return "idle"

def read_rotate_items():
    s = read_file(ROTATE_ITEMS_FILE)
    if not s:
        return ["clock"]
    items = []
    for part in re.split(r"[,\s]+", s):
        part = part.strip()
        if part in ("clock", "weather", "date"):
            items.append(part)
    return items or ["clock"]

DEFAULT_DUR = {"clock": 10, "weather": 2, "date": 2}
def read_rotate_durs(items):
    """读取每项显示时长（秒），与 items 顺序对应；缺省/非法项回退默认值（clock=10/weather=2/date=2）。"""
    s = read_file(ROTATE_DUR_FILE)
    nums = []
    if s:
        for part in re.split(r"[,\s]+", s):
            part = part.strip()
            if part:
                try:
                    v = int(float(part))
                    nums.append(max(1, v))
                except Exception:
                    nums.append(5)
    out = []
    for i in range(len(items)):
        out.append(nums[i] if i < len(nums) else DEFAULT_DUR.get(items[i], 5))
    return out

# ---------- 时间自动校准（网络校时） ----------
def _set_clock(epoch):
    """设置系统时钟（root 有 CAP_SYS_TIME）；优先用 Python 直接调用 clock_settime，再 hwclock 持久化到 RTC。"""
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        class _ts(ctypes.Structure):
            _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]
        v = _ts(int(epoch), 0)
        libc.clock_settime(0, ctypes.byref(v))   # CLOCK_REALTIME = 0
    except Exception:
        try:
            subprocess.run("date -s @%d >/dev/null 2>&1" % int(epoch), shell=True)
        except Exception:
            pass
    try:
        subprocess.run("hwclock -w >/dev/null 2>&1", shell=True)
    except Exception:
        pass

def sync_time_once():
    """用 HTTP Date 头取准确 UTC 时间校正系统时钟（设备已验证可出网）。偏差>2s 才写。"""
    try:
        import urllib.request, email.utils, calendar
        url = "https://api.open-meteo.com/v1/forecast?latitude=39.9&longitude=116.4&current=temperature_2m"
        req = urllib.request.Request(url, headers={"User-Agent": "penweb"})
        with urllib.request.urlopen(req, timeout=8) as r:
            date_hdr = r.headers.get("Date")
        if not date_hdr:
            return False
        dt = email.utils.parsedate_to_datetime(date_hdr)
        if dt is None:
            return False
        correct = calendar.timegm(dt.utctimetuple())
        off = correct - time.time()
        if abs(off) < 2:
            return True
        _set_clock(correct)
        log("time synced, offset=%.1fs" % off)
        return True
    except Exception as e:
        log("time sync fail: %s" % e)
        return False

def time_sync_thread():
    while True:
        try:
            sync_time_once()
        except Exception:
            pass
        time.sleep(1800)   # 每 30 分钟校时一次

def main():
    try:
        open(PID_FILE, "w").write(str(os.getpid()))
    except Exception:
        pass
    log("screen.py start")
    if not HAVE_PIL:
        log("PIL 不可用 -> 退出（请用真实字体版或先安装 Pillow）"); return
    try:
        geo = read_geometry()
    except Exception as e:
        log("read_geometry failed: %s" % e); return
    xs = geo["xs"]; ys = geo["ys"]; line = geo["line"]
    W = ys; H = xs                          # 横屏宽=显存高, 横屏高=显存宽
    log("fb xs=%d ys=%d line=%d  landscape W=%d H=%d" % (xs, ys, line, W, H))
    font = find_font()
    if not font:
        log("无可用字体 -> 退出"); return
    ensure_beep()                           # 提前生成提示音，供轮换切换使用
    # 时间自动校准：开机立即校时 + 后台每 30 分钟校时（基于 HTTP Date 头，设备已验证可出网）
    try: sync_time_once()
    except Exception: pass
    threading.Thread(target=time_sync_thread, daemon=True).start()
    fb = FB(geo)
    _last_key = object()
    _last_flip = None
    scroll_off = 0.0
    last_t = time.time()
    rot = {"idx": 0, "last": time.time()}
    try:
        while True:
            now = time.time()
            dt = now - last_t
            last_t = now
            if dt > 0.5:
                dt = 0.5                       # 切换模式时避免一次性跳变
            mode = get_mode()
            if mode not in ("test", "clock", "clear", "text", "rotate", "event"):
                break                       # idle / 未知 -> 退出（不动主程序）
            flip = read_flip()
            fg = parse_color(read_file(FG_FILE), (255, 255, 255))
            bg = parse_color(read_file(BG_FILE), (0, 0, 0))
            bold = read_bool(BOLD_FILE, False)
            voff = read_int(VOFF_FILE, DEFAULT_VOFF)
            scroll = read_bool(SCROLL_FILE, False)
            speed = read_int(SCROLL_SPEED_FILE, SCROLL_SPEED)
            keep_awake()
            # 闹钟响铃：覆盖显示闹钟画面（点屏关闭由 server 端触摸监听处理）
            if os.path.exists(ALARM_ACTIVE_FILE):
                try:
                    with open(ALARM_ACTIVE_FILE, encoding="utf-8") as f:
                        _ad = json.load(f)
                    _alabel = _ad.get("label", "")
                except Exception:
                    _alabel = ""
                L = render_alarm_frame(_alabel, W, H, fg, bg, font, bold, voff)
                fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                _last_key = object()
                continue
            # 覆盖层（计时/消息）：优先级高于屏幕轮换；闹钟优先于覆盖层
            ov = read_overlay()
            if ov:
                typ = ov.get("type")
                if typ == "timer":
                    L = render_timer_frame(ov, W, H, fg, bg, font, bold, voff)
                    fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                    _last_key = object()
                    continue
                elif typ == "message":
                    if ov.get("expire_ts") and time.time() >= ov["expire_ts"]:
                        clear_overlay()
                    else:
                        L = render_message_frame(ov, W, H, fg, bg, font, bold, voff)
                        fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                        _last_key = object()
                        continue
            if flip != _last_flip:
                _last_key = object()        # 方向变了，缓存失效
                _last_flip = flip
                log("flip -> %s" % flip)
            if mode == "clock":
                os.environ["TZ"] = "CST-8"
                try: time.tzset()
                except Exception: pass
                t = time.strftime("%H:%M:%S", time.localtime())
                key = (t, fg, bg, flip, bold, voff)
                if key != _last_key:
                    L = render_clock_frame(t, W, H, fg, bg, font, bold, voff)
                    fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                    _last_key = key
            elif mode == "text":
                text = read_file(TEXT_FILE)
                if scroll:
                    scroll_off += speed * dt
                    L = render_scroll_frame(text, W, H, fg, bg, font, bold, voff, scroll_off)
                    fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                    _last_key = object()
                else:
                    key = (text, fg, bg, flip, bold, voff)
                    if key != _last_key:
                        L = render_text_frame(text, W, H, fg, bg, font, bold, voff)
                        fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                        _last_key = key
            elif mode == "rotate":
                items = read_rotate_items()
                durs = read_rotate_durs(items)
                sound_on = read_bool(ROTATE_SOUND_FILE, False)
                city = read_file(WEATHER_CITY_FILE, DEFAULT_CITY)
                if rot["idx"] >= len(items):
                    rot["idx"] = 0
                dur = durs[rot["idx"]] if rot["idx"] < len(durs) else DEFAULT_DUR.get(items[rot["idx"]], 5)
                if now - rot["last"] >= dur:
                    rot["idx"] = (rot["idx"] + 1) % len(items)
                    rot["last"] = now
                    if sound_on:
                        play_beep_local()
                item = items[rot["idx"]]
                if item == "clock":
                    os.environ["TZ"] = "CST-8"
                    try: time.tzset()
                    except Exception: pass
                    t = time.strftime("%H:%M:%S", time.localtime())
                    key = ("clock", t, fg, bg, flip, bold, voff)
                    if key != _last_key:
                        L = render_clock_frame(t, W, H, fg, bg, font, bold, voff)
                        fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                        _last_key = key
                elif item == "weather":
                    info = screen_weather(city)
                    key = ("weather", json.dumps(info, ensure_ascii=False), fg, bg, flip, bold, voff)
                    if key != _last_key:
                        L = render_weather_frame(info, W, H, fg, bg, font, bold, voff)
                        fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                        _last_key = key
                elif item == "date":
                    key = ("date", time.strftime("%Y%m%d%H%M", time.localtime()),
                           fg, bg, flip, bold, voff)
                    if key != _last_key:
                        L = render_date_frame(W, H, fg, bg, font, bold, voff)
                        fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                        _last_key = key
            elif mode in ("clear", "test"):  # clear/test：画黑底
                L = Image.new("RGB", (W, H), (0, 0, 0))
                fb.show(landscape_to_memory(L, xs, ys, W, H, flip))
                _last_key = object()
            else:  # event：无覆盖层时不动屏，保留词典笔原生界面（事件结束退回 idle 即熄屏）
                time.sleep(0.03)
                continue
            time.sleep(0.03)
    except KeyboardInterrupt:
        log("interrupted")
    finally:
        fb.close()
        # 不再 release_awake()：server.py 的 wake_guard 持续持有，避免屏幕一退就睡。
        # 仅在 nowake.conf=0/off 时才释放，便于恢复原厂睡眠行为。
        try:
            if open("/sys_data/penweb/nowake.conf").read().strip() in ("0", "off", "false"):
                release_awake()
        except Exception:
            pass
        log("screen.py exit (idle)")

if __name__ == "__main__":
    main()
