#!/usr/bin/env python3
import os, subprocess, re, glob, time, wave, struct as _struct, math, threading, json, base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

STORE = "/sys_data/penweb/store.txt"
PORT = 8080
DIR = "/sys_data/penweb"
BEEP_FILE = DIR + "/beep.wav"
BRIGHT_FILE = DIR + "/brightness.conf"
ROTATE_ITEMS_FILE = DIR + "/rotate_items.conf"
ROTATE_DUR_FILE = DIR + "/rotate_dur.conf"
ROTATE_SOUND_FILE = DIR + "/rotate_sound.conf"
ROTATE_SOUND_VOL_FILE = DIR + "/rotate_sound_vol.conf"
WEATHER_CITY_FILE = DIR + "/weather_city.conf"
WEATHER_CACHE_FILE = DIR + "/weather_cache.json"
ALARM_FILE = DIR + "/alarm_list.conf"
ALARM_ACTIVE_FILE = DIR + "/alarm_active.conf"
TOUCH_DEV_FILE = DIR + "/touch_dev.txt"
OVERLAY_FILE = DIR + "/overlay.json"          # 当前在屏幕上覆盖显示的内容（计时/消息），优先级高于轮换
TIMER_FILE = DIR + "/timer_state.json"        # 后台计时状态（含“继续轮换”时仍运行，手机端可查看）


PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>词典笔控制台</title>
<style>
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#f5f6f8;color:#222}
 header{background:#2b6cff;color:#fff;padding:14px 16px;font-size:17px;font-weight:600;display:flex;align-items:center;justify-content:space-between}
 #status{font-size:12px;font-weight:400;opacity:.92}
 #dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#7CFFB2;margin-right:5px;vertical-align:middle}
 .wrap{max-width:720px;margin:0 auto;padding:14px}
 .card{background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:12px 14px;margin-top:12px}
 .card h3{margin:0 0 8px;font-size:15px;color:#2b6cff}
 .row{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;align-items:center}
 button{border:0;border-radius:10px;padding:10px 14px;font-size:14px;background:#2b6cff;color:#fff;cursor:pointer}
 .btnw{background:#fff;color:#2b6cff;border:1px solid #2b6cff}
 .btnr{background:#ff5b5b}
 a.btn{display:inline-block;text-decoration:none;background:#fff;color:#2b6cff;border:1px solid #2b6cff;border-radius:10px;padding:10px 14px;font-size:14px}
 .item{background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:10px 12px;margin-top:10px}
 .ts{color:#8a93a2;font-size:12px;margin-bottom:4px}
 pre{white-space:pre-wrap;word-break:break-word;margin:0;font-size:15px;font-family:inherit}
 .empty{color:#8a93a2;text-align:center;margin-top:30px}
 .msg{color:#0a9d6e;font-size:13px;min-height:18px;margin-top:6px}
 .sub{font-size:12px;color:#6b7585;font-weight:600;margin-top:12px;padding-left:8px;border-left:3px solid #cdd6e6}
 .section{border:1px solid #c9d6ff}
</style></head>
<body>
<header>词典笔控制台 <span id="status"><span id="dot"></span><span id="ts">连接中…</span></span></header>
<div class="wrap">
 <div class="card">
  <h3>设备状态</h3>
  <div id="dev">加载中…</div>
 </div>
 <div class="card">
  <h3>天气 <button class="btnw" style="float:right;padding:4px 10px;font-size:12px" onclick="refreshWeather(true)">刷新</button></h3>
  <div id="wx">加载中…</div>
 </div>
 <div class="card section">
  <h3>轮换显示</h3>
  <div class="row">
   <a class="btn" href="/rotate">轮换显示页面 →</a>
  </div>
  <div style="font-size:12px;color:#8a93a2;margin-top:6px">勾选要轮换的内容（时间/天气/日期），每项单独设显示秒数，可设切换提示音。点上面进入设置页。</div>
 </div>
 <div class="card section">
  <h3>屏幕控制（接管显示）</h3>

  <div class="sub">显示模式</div>
  <div class="row">
   <button onclick="sact('clock')">全屏时钟</button>
   <button class="btnw" onclick="sact('clear')">清屏</button>
   <button class="btnw" onclick="sactq('flip_h')">左右镜像</button>
   <button class="btnw" onclick="sactq('flip_v')">上下镜像</button>
   <button class="btnr" onclick="sact('restore')">恢复词典笔</button>
  </div>

  <div class="sub">文字与颜色</div>
  <div class="row" style="margin-top:8px">
   <input id="txt" placeholder="输入要显示的文字（支持中英文/数字，可换行）" style="flex:1;padding:9px;border:1px solid #ccd;border-radius:8px">
   <button onclick="showText()">显示文字</button>
  </div>
  <div class="row" style="align-items:center;margin-top:8px">
   <label style="font-size:13px">文字颜色 <input type="color" id="fg" value="#ffffff"></label>
   <label style="font-size:13px;margin-left:12px">背景颜色 <input type="color" id="bg" value="#000000"></label>
   <button class="btnw" id="btnBold" onclick="toggleBold()" style="margin-left:12px">加粗：关</button>
  </div>


  <div class="sub">滚动（长文字）</div>
  <div class="row" style="margin-top:8px;align-items:center">
   <button class="btnw" id="btnScroll" onclick="toggleScroll()">滚动显示：关</button>
   <label style="font-size:13px;margin-left:12px">滚动速度 px/秒
     <input type="number" id="sspeed" value="55" min="5" max="400" style="width:62px;padding:5px;border:1px solid #ccd;border-radius:6px">
   </label>
   <button class="btnw" onclick="setScrollSpeed(document.getElementById('sspeed').value)">应用速度</button>
  </div>

  <div class="sub">位置与亮度</div>
  <div class="row" style="align-items:center;margin-top:8px">
   <label style="font-size:13px">垂直微调（正数上移/负数下移）
     <input type="number" id="voff" value="0" style="width:62px;padding:5px;border:1px solid #ccd;border-radius:6px">
   </label>
   <button class="btnw" onclick="setVoff(document.getElementById('voff').value)">应用微调</button>
   <button class="btnw" onclick="setVoff(0)">复位</button>
  </div>
  <div class="row" style="align-items:center;margin-top:8px">
   <label style="font-size:13px">屏幕亮度(0~10)
     <input type="number" id="bright" value="10" min="0" max="10" style="width:54px;padding:5px;border:1px solid #ccd;border-radius:6px">
   </label>
   <button class="btnw" onclick="setBright(document.getElementById('bright').value)">应用亮度</button>
  </div>

  <div class="sub">声音测试</div>
  <div class="row" style="margin-top:8px">
   <button onclick="sact('sound')">测试声音</button>
  </div>

  <div id="smsg" class="msg"></div>
  <div style="font-size:12px;color:#8a93a2;margin-top:6px">说明：叠加绘制+PAN上屏，不动主程序、不碰看门狗。方向不对点“左右/上下镜像”实时调正。改颜色后需重新点“显示文字”或“全屏时钟”生效。亮度立即生效并保持。</div>
 </div>

 <div class="card section">
  <h3>闹钟</h3>
  <div class="row">
   <a class="btn" href="/alarm">闹钟设置 →</a>
  </div>
  <div style="font-size:12px;color:#8a93a2;margin-top:6px">设置闹钟后，到点循环响“嘚儿”声并在屏幕提示，点屏幕任意处即可关闭。</div>
 </div>

 <div class="card section">
  <h3>倒计时 &amp; 消息投送</h3>
  <div class="row">
   <a class="btn" href="/timer">倒计时 →</a>
   <a class="btn" href="/message">手机消息投送到屏 →</a>
  </div>
  <div style="font-size:12px;color:#8a93a2;margin-top:6px">倒计时结束时循环“嘚儿”声提醒，点屏或网页可关闭；消息可设显示秒数（0=手动关闭），点屏即关。</div>
 </div>

 <div class="card">
  <h3>设备操作</h3>
  <div class="row">
   <button onclick="act('restart')">重启服务</button>
   <button class="btnw" onclick="act('clear')">清空文字台</button>
   <button class="btnw" onclick="act('export_dict')">导出到生词本</button>
   <button class="btnr" onclick="act('reboot')">重启设备</button>
   <button class="btnr" onclick="act('poweroff')">关机</button>
  </div>
  <div id="msg" class="msg"></div>
 </div>
 <div class="card">
  <h3>扫描文字台</h3>
  <div id="list"></div>
 </div>
</div>
<script>
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function fmt(d){return d.toLocaleTimeString('zh-CN',{hour12:false});}
async function refresh(){try{var r=await fetch('/content?_='+Date.now(),{cache:'no-store'});document.getElementById('list').innerHTML=await r.text();var d=document.getElementById('dot');if(d)d.style.background='#7CFFB2';var t=document.getElementById('ts');if(t)t.textContent='已更新 '+fmt(new Date());}catch(e){var d=document.getElementById('dot');if(d)d.style.background='#ff6b6b';var t=document.getElementById('ts');if(t)t.textContent='连接中断，重试中…';}}
async function refreshStatus(){try{var r=await fetch('/status?_='+Date.now(),{cache:'no-store'});document.getElementById('dev').innerHTML=await r.text();}catch(e){}}
async function refreshWeather(force){
  if(force){
    try{await fetch('/weather_refresh',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'weather_refresh=1'});}catch(e){}
  }
  try{
    var r=await fetch('/weather_api?_='+Date.now(),{cache:'no-store'});
    var j=await r.json();
    var d=j.data||{};
    var el=document.getElementById('wx');
    if(d.error){el.innerHTML='<span style="color:#ff5b5b">天气获取失败：'+esc(String(d.error))+'</span>';return;}
    if(d.loading){el.textContent='天气加载中…';return;}
    var ts=j.t?new Date(j.t*1000).toLocaleTimeString('zh-CN',{hour12:false}):'';
    el.innerHTML='<div style="font-size:30px;font-weight:700">'+esc(d.temp!=null?Math.round(d.temp)+'°':'--')+' <span style="font-size:16px;font-weight:400;color:#555">'+esc(d.desc||'')+'</span></div>'+
      '<div style="font-size:13px;color:#8a93a2;margin-top:4px">'+esc(j.city||'')+(ts?' · 更新于 '+ts:'')+'</div>';
  }catch(e){document.getElementById('wx').textContent='连接中断';}
}
async function act(cmd){if(cmd!=='clear'&&!confirm('确定执行：'+cmd+'？'))return;try{var r=await fetch('/action',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'cmd='+encodeURIComponent(cmd)});var t=await r.text();var m=document.getElementById('msg');if(m){m.textContent=t;setTimeout(function(){m.textContent='';},4000);}}catch(e){}}
async function sact(a){var fg=document.getElementById('fg').value;var bg=document.getElementById('bg').value;var body='screen='+encodeURIComponent(a)+'&fg='+encodeURIComponent(fg)+'&bg='+encodeURIComponent(bg);if(!confirm('屏幕操作：'+a+'？'))return;sactpost(body);}
async function sactq(a){var fg=document.getElementById('fg').value;var bg=document.getElementById('bg').value;var body='screen='+encodeURIComponent(a)+'&fg='+encodeURIComponent(fg)+'&bg='+encodeURIComponent(bg);sactpost(body);}
async function showText(){var t=document.getElementById('txt').value;var fg=document.getElementById('fg').value;var bg=document.getElementById('bg').value;var body='screen=text&text='+encodeURIComponent(t)+'&fg='+encodeURIComponent(fg)+'&bg='+encodeURIComponent(bg);sactpost(body);}
async function sactpost(body){try{var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:body});var x=await r.text();var m=document.getElementById('smsg');if(m){m.textContent=x;setTimeout(function(){m.textContent='';},5000);}}catch(e){}}
var _pen_bold=false,_pen_scroll=false;
function toggleBold(){_pen_bold=!_pen_bold;var b=document.getElementById('btnBold');b.textContent='加粗：'+(_pen_bold?'开':'关');screenAdj('bold',_pen_bold?1:0);}
function toggleScroll(){_pen_scroll=!_pen_scroll;var b=document.getElementById('btnScroll');b.textContent='滚动显示：'+(_pen_scroll?'开':'关');screenAdj('scroll',_pen_scroll?1:0);}
async function setVoff(v){var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'screen=voff&voff='+encodeURIComponent(v)});var m=document.getElementById('smsg');if(m){m.textContent=await r.text();setTimeout(function(){m.textContent='';},5000);}}
async function setScrollSpeed(v){var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'screen=scroll_speed&scroll_speed='+encodeURIComponent(v)});var m=document.getElementById('smsg');if(m){m.textContent=await r.text();setTimeout(function(){m.textContent='';},5000);}}
async function setBright(v){var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'screen=brightness&brightness='+encodeURIComponent(v)});var m=document.getElementById('smsg');if(m){m.textContent=await r.text();setTimeout(function(){m.textContent='';},5000);}}
async function screenAdj(k,v){var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'screen='+k+'&'+k+'='+encodeURIComponent(v)});var m=document.getElementById('smsg');if(m){m.textContent=await r.text();setTimeout(function(){m.textContent='';},5000);}}
refresh();refreshStatus();refreshWeather();setInterval(refresh,3000);setInterval(refreshStatus,5000);setInterval(refreshWeather,15000);
</script>
</body></html>
"""

ROTATE_PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>轮换显示</title>
<style>
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#f5f6f8;color:#222}
 header{background:#2b6cff;color:#fff;padding:14px 16px;font-size:17px;font-weight:600;display:flex;align-items:center;justify-content:space-between}
 header a{color:#fff;text-decoration:none;font-size:13px;opacity:.92}
 .wrap{max-width:720px;margin:0 auto;padding:14px}
 .card{background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:12px 14px;margin-top:12px}
 .card h3{margin:0 0 8px;font-size:15px;color:#2b6cff}
 .row{display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;align-items:center}
 label.chk{display:flex;align-items:center;gap:6px;font-size:15px;background:#f2f5ff;border:1px solid #d6e0ff;border-radius:10px;padding:8px 12px;cursor:pointer}
 input[type=checkbox]{width:18px;height:18px}
 button{border:0;border-radius:10px;padding:10px 16px;font-size:14px;background:#2b6cff;color:#fff;cursor:pointer}
 .btnw{background:#fff;color:#2b6cff;border:1px solid #2b6cff}
 .btnr{background:#ff5b5b}
 input[type=number],input[type=text]{padding:9px;border:1px solid #ccd;border-radius:8px;font-size:14px}
 .msg{color:#0a9d6e;font-size:13px;min-height:18px;margin-top:8px}
 .tip{font-size:12px;color:#8a93a2;margin-top:6px}
</style></head>
<body onload="init()">
<header>轮换显示 <a href="/">← 返回控制台</a></header>
<div class="wrap">
 <div class="card">
  <h3>选择要轮换显示的内容（每项单独设置显示时长）</h3>
  <div class="row" style="align-items:center">
   <label class="chk" style="min-width:210px"><input type="checkbox" id="c_clock" checked> 时间（时钟）</label>
   <span style="font-size:14px">显示</span>
   <input type="number" id="d_clock" value="10" min="1" max="600" style="width:64px"> 秒
  </div>
  <div class="row" style="align-items:center">
   <label class="chk" style="min-width:210px"><input type="checkbox" id="c_weather" checked> 天气</label>
   <span style="font-size:14px">显示</span>
   <input type="number" id="d_weather" value="2" min="1" max="600" style="width:64px"> 秒
  </div>
  <div class="row" style="align-items:center">
   <label class="chk" style="min-width:210px"><input type="checkbox" id="c_date"> 日期（年月日+星期）</label>
   <span style="font-size:14px">显示</span>
   <input type="number" id="d_date" value="2" min="1" max="600" style="width:64px"> 秒
  </div>
  <div class="row" style="align-items:center">
   <span style="font-size:14px">天气城市</span>
   <input type="text" id="city" value="北京" style="width:140px">
  </div>
  <div class="row" style="align-items:center">
   <label class="chk"><input type="checkbox" id="c_sound"> 切换时播放提示音</label>
   <span style="font-size:14px;margin-left:12px">提示音音量</span>
   <input type="number" id="vol" value="80" min="0" max="100" style="width:64px"> %
  </div>
  <div class="row">
   <button onclick="startRotate()">开始轮换</button>
   <button class="btnw" onclick="resetCfg()">恢复默认</button>
   <button class="btnr" onclick="stopRotate()">停止并显示词典笔</button>
  </div>
  <div id="rmsg" class="msg"></div>
  <div class="tip">勾选哪些项就轮换哪些项（勾 1 项则固定显示该项）。每项可单独设置“显示多少秒”：时间默认 10 秒、天气/日期默认 2 秒，均可调。天气需设备联网（已验证可出网）。提示音音量 0~100 可调。配置会自动保存，下次进入本页显示上次设置。</div>
 </div>
</div>
<script>
function setMsg(s){var m=document.getElementById('rmsg');m.textContent=s;setTimeout(function(){m.textContent='';},5000);}
async function startRotate(){
  var items=[], durs=[];
  function add(cid,did,key){
    if(document.getElementById(cid).checked){
      items.push(key);
      var v=parseInt(document.getElementById(did).value,10);
      if(!v||v<1) v=(key==='clock'?10:2);
      durs.push(v);
    }
  }
  add('c_clock','d_clock','clock');
  add('c_weather','d_weather','weather');
  add('c_date','d_date','date');
  if(items.length===0){setMsg('请至少勾选一项');return;}
  var body='screen=rotate'
    +'&rotate_items='+encodeURIComponent(items.join(','))
    +'&rotate_dur='+encodeURIComponent(durs.join(','))
    +'&rotate_sound='+encodeURIComponent(document.getElementById('c_sound').checked?'1':'0')
    +'&rotate_sound_vol='+encodeURIComponent(document.getElementById('vol').value)
    +'&weather_city='+encodeURIComponent(document.getElementById('city').value);
  try{
    var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:body});
    setMsg(await r.text());
  }catch(e){setMsg('请求失败');}
}
async function stopRotate(){
  try{
    var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'screen=restore'});
    setMsg(await r.text());
  }catch(e){setMsg('请求失败');}
}
function resetCfg(){
  document.getElementById('c_clock').checked=true;
  document.getElementById('c_weather').checked=true;
  document.getElementById('c_date').checked=false;
  document.getElementById('d_clock').value=10;
  document.getElementById('d_weather').value=2;
  document.getElementById('d_date').value=2;
  document.getElementById('city').value='北京';
  document.getElementById('c_sound').checked=false;
  document.getElementById('vol').value=80;
  setMsg('已恢复默认（点“开始轮换”才会保存）');
}
async function init(){
  try{
    var r=await fetch('/rotate_config',{cache:'no-store'});
    var c=await r.json();
    if(c.clock!==undefined) document.getElementById('c_clock').checked=!!c.clock;
    if(c.weather!==undefined) document.getElementById('c_weather').checked=!!c.weather;
    if(c.date!==undefined) document.getElementById('c_date').checked=!!c.date;
    if(c.d_clock) document.getElementById('d_clock').value=c.d_clock;
    if(c.d_weather) document.getElementById('d_weather').value=c.d_weather;
    if(c.d_date) document.getElementById('d_date').value=c.d_date;
    if(c.city) document.getElementById('city').value=c.city;
    if(c.sound!==undefined) document.getElementById('c_sound').checked=!!c.sound;
    if(c.vol!==undefined) document.getElementById('vol').value=c.vol;
  }catch(e){ /* 用页面默认值 */ }
}
</script>
</body></html>
"""

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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

def render_items():
    items = list(reversed(read_items()))
    if not items:
        return '<p class="empty">还没有内容。扫描或粘贴文字后会出现在这里。</p>'
    html = ""
    for i, (ts, txt) in enumerate(items, 1):
        ocr = txt.startswith('[OCR] ')
        if ocr:
            txt = txt[len('[OCR] '):]
        badge = ' <span style="background:#0a9d6e;color:#fff;border-radius:6px;padding:1px 6px;font-size:11px;vertical-align:middle">原图OCR</span>' if ocr else ''
        html += '<div class="item"><div class="ts">#%d · %s%s</div><pre>%s</pre></div>' % (i, esc(ts), badge, esc(txt))
    return html

# ---------- 闹钟 ----------
def read_alarms():
    try:
        with open(ALARM_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, list):
            return d
    except Exception:
        pass
    return []

def write_alarms(lst):
    try:
        with open(ALARM_FILE, "w", encoding="utf-8") as f:
            json.dump(lst, f, ensure_ascii=False)
    except Exception:
        pass

_alarm_fired = {}   # id -> "YYYY-MM-DD HH:MM"，避免同一分钟内重复触发

def _dismiss_alarm():
    try:
        os.remove(ALARM_ACTIVE_FILE)
    except Exception:
        pass
    try:
        os.system("pkill -f 'aplay.*beep.wav' 2>/dev/null")
    except Exception:
        pass

def _alarm_beep_loop():
    """循环播放提示音（der 声），直到闹钟被关闭。"""
    while os.path.exists(ALARM_ACTIVE_FILE):
        try:
            play_beep()
        except Exception:
            pass
        for _ in range(6):   # 每 ~0.6s 响一声，期间随时可因关闭而退出
            if not os.path.exists(ALARM_ACTIVE_FILE):
                break
            time.sleep(0.1)

def _alarm_touch_listener():
    """监听触摸设备，任意触摸即关闭闹钟（设备已验证 /dev/input/event2 = axs_ts）。"""
    dev = "/dev/input/event2"
    try:
        with open(TOUCH_DEV_FILE) as f:
            d = f.read().strip()
            if d:
                dev = d
    except Exception:
        pass
    try:
        fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
    except Exception:
        return
    fmt, size = "iiHHi", 16
    buf = b""
    while os.path.exists(ALARM_ACTIVE_FILE):
        try:
            data = os.read(fd, 4096)
        except (BlockingIOError, OSError):
            time.sleep(0.05)
            continue
        if not data:
            time.sleep(0.02)
            continue
        buf += data
        while len(buf) >= size:
            ev = buf[:size]; buf = buf[size:]
            try:
                _, _, et, ec, val = _struct.unpack(fmt, ev)
            except Exception:
                buf = b""; break
            if et == 3 and ec == 0x35:                 # ABS_MT_X 出现 = 触摸中
                _dismiss_alarm(); break
            if et == 1 and ec == 0x14A and val == 1:  # BTN_TOUCH 按下
                _dismiss_alarm(); break
            if et == 3 and ec == 0x39 and val != -1:   # ABS_MT_TRACKING_ID 新触点
                _dismiss_alarm(); break
    try:
        os.close(fd)
    except Exception:
        pass

def _fire_alarm(a):
    try:
        with open(ALARM_ACTIVE_FILE, "w", encoding="utf-8") as f:
            json.dump({"label": a.get("label", ""), "time": a.get("time", "")}, f, ensure_ascii=False)
    except Exception:
        pass
    threading.Thread(target=_alarm_beep_loop, daemon=True).start()
    _enter_event_display()   # idle 态下点亮屏并显示闹钟
    # 触摸关闭由常驻 _touch_listener 统一处理（见 __main__ 启动），此处不再单独拉起

def _alarm_checker():
    """每秒比对一次当前时间，命中启用的闹钟则触发（循环响 + 屏幕覆盖 + 点屏关闭）。"""
    while True:
        try:
            if not os.path.exists(ALARM_ACTIVE_FILE):
                now = time.localtime()
                minute_key = time.strftime("%Y-%m-%d %H:%M", now)
                cur = time.strftime("%H:%M", now)
                wd = now.tm_wday
                for a in read_alarms():
                    if not a.get("enabled"):
                        continue
                    if a.get("time") != cur:
                        continue
                    rep = a.get("repeat") or []
                    if rep and (wd not in rep):
                        continue
                    aid = a.get("id")
                    if _alarm_fired.get(aid) == minute_key:
                        continue
                    _alarm_fired[aid] = minute_key
                    _fire_alarm(a)
        except Exception:
            pass
        time.sleep(1)

def alarm_status():
    active = os.path.exists(ALARM_ACTIVE_FILE)
    label = ""; t = ""
    if active:
        try:
            with open(ALARM_ACTIVE_FILE, encoding="utf-8") as f:
                d = json.load(f); label = d.get("label", ""); t = d.get("time", "")
        except Exception:
            pass
    return {"active": active, "label": label, "time": t}

# ---------- 覆盖层（计时/消息）：优先级高于屏幕轮换 ----------
def read_overlay():
    try:
        with open(OVERLAY_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
def set_overlay(obj):
    try:
        with open(OVERLAY_FILE, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
    except Exception:
        pass
def clear_overlay():
    try:
        os.remove(OVERLAY_FILE)
    except Exception:
        pass
def _dismiss_overlay():
    """点屏关闭覆盖层：只清显示，不杀后台计时；若关闭的是“已到时”的倒计时，则顺手清掉该槽位。"""
    ov = read_overlay()
    if ov and ov.get("type") == "timer" and ov.get("mode") == "down" and ov.get("finished"):
        tj = read_timer()
        if tj.get("down"):
            tj["down"] = None
            write_timer(tj)
    clear_overlay()
    try: os.system("pkill -f 'aplay.*beep.wav' 2>/dev/null")
    except Exception: pass

# 常驻触摸监听：任意触摸关闭 闹钟 或 覆盖层（计时/消息），与显示模式无关。
def _touch_listener():
    dev = "/dev/input/event2"
    try:
        with open(TOUCH_DEV_FILE) as f:
            d = f.read().strip()
            if d: dev = d
    except Exception:
        pass
    try:
        fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
    except Exception:
        return
    fmt, size = "iiHHi", 16
    buf = b""
    while True:
        try:
            data = os.read(fd, 4096)
        except (BlockingIOError, OSError):
            time.sleep(0.05); continue
        if not data:
            time.sleep(0.02); continue
        buf += data
        while len(buf) >= size:
            ev = buf[:size]; buf = buf[size:]
            try:
                _, _, et, ec, val = _struct.unpack(fmt, ev)
            except Exception:
                buf = b""; break
            touch = False
            if et == 3 and ec == 0x35:                 # ABS_MT_X 出现 = 触摸中
                touch = True
            elif et == 1 and ec == 0x14A and val == 1:  # BTN_TOUCH 按下
                touch = True
            elif et == 3 and ec == 0x39 and val != -1:  # ABS_MT_TRACKING_ID 新触点
                touch = True
            if touch:
                if os.path.exists(ALARM_ACTIVE_FILE):
                    _dismiss_alarm()
                elif read_overlay():
                    _dismiss_overlay()
                else:
                    # 轮换/时钟模式下点屏：临时看一眼倒计时，再点回轮换
                    tj = read_timer()
                    if tj.get("down"):
                        set_overlay(_slot_overlay("down", tj["down"]))

# ---------- 倒计时（单槽） ----------
def read_timer():
    """读取倒计时状态：{"down": slot|None}。"""
    try:
        with open(TIMER_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            d.setdefault("down", None)
            return d
    except Exception:
        pass
    return {"down": None}

def write_timer(obj):
    try:
        with open(TIMER_FILE, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
    except Exception:
        pass

def _slot_overlay(mode, slot):
    return {"type": "timer", "mode": mode, "label": slot.get("label", ""),
            "start_ts": slot.get("start_ts", time.time()),
            "duration": slot.get("duration", 0),
            "expire_ts": slot.get("expire_ts", 0),
            "finished": slot.get("finished", False)}

def start_timer(label, duration, allow_rotate, sound):
    """开始倒计时。不勾选“继续轮换”则立即覆盖屏幕；勾选则后台运行，屏幕继续轮换。
    倒计时结束会自动抢屏 + 循环嘚儿声。时长为 0（00:00:00）：直接响铃，不进入运行态。"""
    tj = read_timer()
    now = time.time()
    label = label or ""
    try:
        dur = int(duration) if duration not in (None, "") else 0
    except Exception:
        dur = 0
    if dur <= 0:
        # 时长 0：立即响铃提示（一次性），不占用倒计时槽；息屏态也能听到
        _beep_burst(3)
        return "已响铃（时长 0，可重新设置时长后再开始）"
    slot = {"active": True, "mode": "down", "label": label, "start_ts": now,
            "duration": dur, "expire_ts": (now + dur) if dur > 0 else 0,
            "allow_rotate": bool(allow_rotate), "sound": bool(sound), "finished": False}
    tj["down"] = slot
    write_timer(tj)
    if not allow_rotate:
        set_overlay(_slot_overlay("down", slot))
    msg = "已开始倒计时（%s）" % ("继续轮换，手机可查看" if allow_rotate else "已覆盖屏幕显示")
    return msg

def stop_timer(mode=""):
    """停止倒计时（mode 保留兼容参数，忽略其值）。"""
    tj = read_timer()
    if tj.get("down"):
        tj["down"] = None
        write_timer(tj)
    ov = read_overlay()
    if ov and ov.get("type") == "timer":
        clear_overlay()
    try: os.system("pkill -f 'aplay.*beep.wav' 2>/dev/null")
    except Exception: pass
    return "已停止"

def convert_timer(mode=""):
    """把正在进行的倒计时切到屏幕优先显示。"""
    tj = read_timer()
    slot = tj.get("down")
    if not slot or not slot.get("active"):
        return "当前没有正在进行的倒计时"
    set_overlay(_slot_overlay("down", slot))
    return "已切换到倒计时优先显示"

def timer_status():
    tj = read_timer()
    out = {"down": None}
    now = time.time()
    slot = tj.get("down")
    if slot and slot.get("active"):
        out["down"] = {"active": True, "label": slot.get("label", ""),
                       "remain": int(max(0, slot.get("expire_ts", 0) - now)),
                       "finished": slot.get("finished", False),
                       "allow_rotate": slot.get("allow_rotate", False)}
    out["active"] = bool(out["down"])
    return out

_beep_on = False
_beep_lock = threading.Lock()
def _beep_burst(n=3):
    """播放 n 声短促提示音（一次性，不循环）；用于时长0的倒计时、消息投送等即时提醒。"""
    def _run():
        for i in range(n):
            try:
                play_beep()
            except Exception:
                pass
            if i < n - 1:
                time.sleep(0.6)
    threading.Thread(target=_run, daemon=True).start()
def _start_overlay_beep():
    global _beep_on
    with _beep_lock:
        if _beep_on:
            return
        _beep_on = True
    threading.Thread(target=_overlay_beep_loop, daemon=True).start()
def _overlay_beep_loop():
    global _beep_on
    try:
        while True:
            ov = read_overlay()
            if not ov or ov.get("type") != "timer" or not ov.get("finished"):
                break
            try:
                play_beep()
            except Exception:
                pass
            stop = False
            for _ in range(6):
                ov = read_overlay()
                if not ov or ov.get("type") != "timer":
                    stop = True; break
                time.sleep(0.1)
            if stop:
                break
    finally:
        with _beep_lock:
            _beep_on = False

def _timer_watcher():
    """检测倒计时归零：强制覆盖显示 + 循环嘚儿声。"""
    while True:
        try:
            tj = read_timer()
            now = time.time()
            slot = tj.get("down")
            if slot and slot.get("active") and not slot.get("finished") and slot.get("expire_ts") and now >= slot["expire_ts"]:
                slot["finished"] = True
                write_timer(tj)
                ov = read_overlay()
                if not ov or ov.get("type") != "timer" or ov.get("mode") != "down":
                    set_overlay(_slot_overlay("down", slot))
                else:
                    ov["finished"] = True
                    set_overlay(ov)
                if slot.get("sound"):
                    _start_overlay_beep()
                _enter_event_display()   # idle 态下点亮屏并显示倒计时归零
        except Exception:
            pass
        time.sleep(0.3)

# ---------- 消息投送（文字） ----------
def push_message(text, duration):
    """duration: 0=手动关闭（点屏/网页）；其余为秒数。息屏态也会响铃提醒。"""
    now = time.time()
    try:
        d = int(duration) if duration not in (None, "") else 3
    except Exception:
        d = 3
    expire = 0 if d == 0 else (now + d)
    set_overlay({"type": "message", "label": text or "", "expire_ts": expire})
    _beep_burst(1)   # 消息投送：响一声提示
    _enter_event_display()   # idle 态下点亮屏并显示消息
    return "已推送（%s）" % ("手动关闭" if d == 0 else ("%d 秒后自动关闭" % d))

def message_status():
    ov = read_overlay()
    if not ov:
        return {"active": False}
    if ov.get("type") == "message":
        return {"active": True, "type": ov["type"], "label": ov.get("label", ""),
                "expire_ts": ov.get("expire_ts", 0)}
    return {"active": False}


ALARM_PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>闹钟</title>
<style>
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#f5f6f8;color:#222}
 header{background:#2b6cff;color:#fff;padding:14px 16px;font-size:17px;font-weight:600}
 .wrap{max-width:720px;margin:0 auto;padding:14px}
 .card{background:#fff;border:1px solid #e6e8ec;border-radius:12px;padding:12px 14px;margin-top:12px}
 h3{margin:0 0 8px;font-size:15px;color:#2b6cff}
 .row{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;align-items:center}
 button{border:0;border-radius:10px;padding:9px 13px;font-size:14px;background:#2b6cff;color:#fff;cursor:pointer}
 .btnw{background:#fff;color:#2b6cff;border:1px solid #2b6cff}
 .btnr{background:#ff5b5b}
 a.btn{display:inline-block;text-decoration:none;background:#fff;color:#2b6cff;border:1px solid #2b6cff;border-radius:10px;padding:9px 13px;font-size:14px}
 .ar{display:flex;gap:8px;align-items:center;padding:10px;margin-top:8px;border:1px solid #e6e8ec;border-radius:10px;flex-wrap:wrap}
 .ar input[type=time]{padding:6px;border:1px solid #ccd;border-radius:6px;font-size:15px}
 .ar input[type=text]{flex:1;min-width:120px;padding:6px;border:1px solid #ccd;border-radius:6px;font-size:14px}
 .wd{font-size:12px;color:#555}
 .msg{color:#0a9d6e;font-size:13px;min-height:18px;margin-top:6px}
</style></head>
<body>
<header>闹钟 <a class="btn" style="float:right;font-size:13px" href="/">← 返回控制台</a></header>
<div class="wrap">
 <div class="card" id="ringCard" style="display:none">
  <h3 style="color:#e0392b">闹钟响铃中</h3>
  <div id="ringLabel" style="font-size:18px;font-weight:600"></div>
  <div class="row"><button class="btnr" onclick="dismiss()">停止（也可点击屏幕关闭）</button></div>
 </div>
 <div class="card">
  <h3>闹钟列表</h3>
  <div id="list"></div>
  <div class="row" style="margin-top:10px">
   <button class="btnw" onclick="addRow()">+ 添加闹钟</button>
   <button onclick="save()">保存</button>
  </div>
  <div id="msg" class="msg"></div>
 </div>
</div>
<script>
var WD=['一','二','三','四','五','六','日'];
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function rowHTML(a,idx){
  var rep=a.repeat||[];
  var wd='';
  for(var i=0;i<7;i++){wd+='<label class="wd"><input type="checkbox" data-k="rep" data-i="'+i+'"'+(rep.indexOf(i)>=0?' checked':'')+'>'+WD[i]+'</label>';}
  return '<div class="ar" data-idx="'+idx+'">'
    +'<input type="time" data-k="time" value="'+esc(a.time)+'">'
    +'<input type="text" data-k="label" placeholder="标签(可选)" value="'+esc(a.label)+'">'
    +'<label class="wd"><input type="checkbox" data-k="enabled"'+(a.enabled?' checked':'')+'>启用</label>'
    +'<span class="wd">重复:'+wd+'</span>'
    +'<button class="btnr" onclick="delRow('+idx+')">删除</button>'
    +'</div>';
}
var ALARMS=[];
function render(){var h='';for(var i=0;i<ALARMS.length;i++){h+=rowHTML(ALARMS[i],i);}if(!ALARMS.length)h='<p style="color:#8a93a2">还没有闹钟，点“添加闹钟”。</p>';document.getElementById('list').innerHTML=h;}
function addRow(){ALARMS.push({id:Date.now(),time:'08:00',enabled:true,label:'',repeat:[]});render();}
function delRow(i){ALARMS.splice(i,1);render();}
function collect(){var rows=document.querySelectorAll('#list .ar');var out=[];rows.forEach(function(r){var o={};var t=r.querySelector('[data-k=time]');o.time=t?t.value:'08:00';var l=r.querySelector('[data-k=label]');o.label=l?l.value:'';var e=r.querySelector('[data-k=enabled]');o.enabled=!!(e&&e.checked);var reps=[];r.querySelectorAll('[data-k=rep]').forEach(function(c){if(c.checked)reps.push(parseInt(c.getAttribute('data-i'),10));});o.repeat=reps;var id=r.getAttribute('data-idx');o.id=ALARMS[parseInt(id,10)]?ALARMS[parseInt(id,10)].id:Date.now();out.push(o);});return out;}
async function load(){try{var r=await fetch('/alarm_api',{cache:'no-store'});ALARMS=await r.json();render();}catch(e){ALARMS=[];render();}}
async function save(){var data=collect();try{var r=await fetch('/alarm_api',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'alarms='+encodeURIComponent(JSON.stringify(data))});msg(await r.text());}catch(e){msg('保存失败');}}
function msg(t){var m=document.getElementById('msg');m.textContent=t;setTimeout(function(){m.textContent='';},4000);}
async function status(){try{var r=await fetch('/alarm_status',{cache:'no-store'});var s=await r.json();var c=document.getElementById('ringCard');if(s.active){c.style.display='block';document.getElementById('ringLabel').textContent=(s.label||'闹钟')+'  '+s.time;}else{c.style.display='none';}}catch(e){}}
async function dismiss(){try{await fetch('/alarm_dismiss',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'alarm_dismiss=1'});}catch(e){}}
load();status();setInterval(status,2000);
</script>
</body></html>
"""

TIMER_PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>计时器</title>
<style>
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#f5f6f8;color:#222}
 header{background:#2b6cff;color:#fff;padding:14px 16px;font-size:17px;font-weight:600}
 .wrap{max-width:560px;margin:14px auto;padding:0 12px}
 .card{background:#fff;border-radius:12px;padding:14px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
 h3{margin:0 0 10px;font-size:16px}
 .row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px}
 input[type=text],input[type=number],textarea,select{padding:9px;border:1px solid #ccd;border-radius:8px;font-size:14px}
 input[type=text],textarea{flex:1;min-width:160px}
 textarea{min-height:64px;resize:vertical}
 button{background:#2b6cff;color:#fff;border:0;border-radius:8px;padding:9px 14px;font-size:14px;cursor:pointer}
 button.btnw{background:#eef2ff;color:#2b6cff}
 button.btnr{background:#e0392b;color:#fff}
 .btn{display:inline-block;background:#eef2ff;color:#2b6cff;text-decoration:none;padding:9px 14px;border-radius:8px;font-size:14px}
 label{font-size:14px}
 .big{font-size:40px;font-weight:700;text-align:center;margin:8px 0;font-variant-numeric:tabular-nums}
 .msg{color:#0a9d6e;font-size:13px;min-height:18px;margin-top:6px}
</style></head>
<body>
<header>计时器 <a class="btn" style="float:right;font-size:13px" href="/">← 返回控制台</a></header>
<div class="wrap">

 <div class="card">
  <h3>倒计时</h3>
  <div class="row"><input type="text" id="down_label" placeholder="标签（如：煮面），可留空"></div>
  <div class="row">
   <span>时长</span>
   <input type="number" id="down_h" value="0" min="0" max="99" placeholder="时" style="width:54px;padding:6px;border:1px solid #ccd;border-radius:6px;font-size:15px;text-align:center">
   <span>:</span>
   <input type="number" id="down_m" value="0" min="0" max="59" placeholder="分" style="width:54px;padding:6px;border:1px solid #ccd;border-radius:6px;font-size:15px;text-align:center">
   <span>:</span>
   <input type="number" id="down_s" value="0" min="0" max="59" placeholder="秒" style="width:54px;padding:6px;border:1px solid #ccd;border-radius:6px;font-size:15px;text-align:center">
  </div>
  <div class="row">
   <label><input type="checkbox" id="down_rotate"> 继续轮换（后台运行）</label>
   <label><input type="checkbox" id="down_sound" checked> 结束时响铃（嘚儿声，点屏关闭）</label>
  </div>
  <div class="row">
   <button onclick="startDown()">开始倒计时</button>
   <button class="btnr" onclick="stopDown()">停止</button>
  </div>
  <div class="row"><span id="down_status" style="color:#8a93a2">未开始</span></div>
 </div>

 <div class="card">
  <h3>屏幕显示</h3>
  <div class="row">
   <button class="btnw" onclick="convertTo('down')">倒计时切到屏幕</button>
  </div>
  <div style="font-size:12px;color:#8a93a2;margin-top:6px">倒计时在后台运行时，点此切到屏幕优先显示；轮换中点屏也可看一眼倒计时（再点回轮换）。</div>
 </div>
</div>
<script>
function pad(n){n=parseInt(n||0,10);return (n<10?'0':'')+n;}
function fmt(sec){sec=Math.max(0,parseInt(sec||0,10));var h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60),x=sec%60;if(h>0)return h+':'+pad(m)+':'+pad(x);return pad(m)+':'+pad(x);}
function toSec(h,m,s){return (parseInt(document.getElementById(h).value||0,10)*3600)+(parseInt(document.getElementById(m).value||0,10)*60)+(parseInt(document.getElementById(s).value||0,10));}
function setStatus(id,t){document.getElementById(id).textContent=t;}
async function startDown(){
  var label=document.getElementById('down_label').value;
  var dur=toSec('down_h','down_m','down_s');
  var rotate=document.getElementById('down_rotate').checked?'1':'0';
  var sound=document.getElementById('down_sound').checked?'1':'0';
  var body='timer_start=1&timer_label='+encodeURIComponent(label)+'&timer_duration='+dur+'&timer_rotate='+rotate+'&timer_sound='+sound;
  try{var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:body});setStatus('down_status',await r.text());}catch(e){setStatus('down_status','失败');}
}
async function postStop(mode,id){try{var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'timer_stop=1&timer_mode='+mode});setStatus(id,await r.text());}catch(e){setStatus(id,'停止失败');}}
function stopDown(){postStop('down','down_status');}
async function convertTo(mode){try{await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'timer_convert=1&timer_mode='+mode});}catch(e){}}
async function status(){
  try{
    var r=await fetch('/timer_api',{cache:'no-store'});var s=await r.json();
    var dn=s.down;
    if(dn&&dn.active){var t2='倒计时 · '+(dn.label||'');if(dn.finished)t2+='（已到时）';setStatus('down_status',t2+'  '+fmt(dn.remain));}
    else setStatus('down_status','未开始');
  }catch(e){}
}
status();setInterval(status,1000);
</script>
</body></html>
"""

MESSAGE_PAGE = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>消息投送</title>
<style>
 *{box-sizing:border-box} body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#f5f6f8;color:#222}
 header{background:#2b6cff;color:#fff;padding:14px 16px;font-size:17px;font-weight:600}
 .wrap{max-width:560px;margin:14px auto;padding:0 12px}
 .card{background:#fff;border-radius:12px;padding:14px;margin-bottom:14px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
 h3{margin:0 0 10px;font-size:16px}
 .row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:8px}
 input[type=text],input[type=number],textarea{padding:9px;border:1px solid #ccd;border-radius:8px;font-size:14px}
 textarea{flex:1;min-width:160px;min-height:64px;resize:vertical}
 button{background:#2b6cff;color:#fff;border:0;border-radius:8px;padding:9px 14px;font-size:14px;cursor:pointer}
 button.btnw{background:#eef2ff;color:#2b6cff}
 button.btnr{background:#e0392b;color:#fff}
 .btn{display:inline-block;background:#eef2ff;color:#2b6cff;text-decoration:none;padding:9px 14px;border-radius:8px;font-size:14px}
 .msg{color:#0a9d6e;font-size:13px;min-height:18px;margin-top:6px}
</style></head>
<body>
<header>消息投送 <a class="btn" style="float:right;font-size:13px" href="/">← 返回控制台</a></header>
<div class="wrap">
 <div class="card">
  <h3>发送消息到词典笔</h3>
  <div class="row"><textarea id="text" placeholder="输入要投送到屏幕的文字"></textarea></div>
  <div class="row">
   <label>显示秒数 <input type="number" id="dur" value="3" min="0" style="width:70px"></label>
   <span style="font-size:12px;color:#8a93a2">（0=手动关闭，点屏或下方按钮关闭）</span>
  </div>
  <div class="row"><button onclick="send()">发送</button></div>
  <div id="msg" class="msg"></div>
 </div>
 <div class="card">
  <h3>当前投送</h3>
  <div id="status" style="color:#8a93a2">屏幕暂无投送内容</div>
  <div class="row"><button class="btnr" onclick="closeMsg()">关闭屏幕内容</button></div>
 </div>
</div>
<script>
function msg(t){var m=document.getElementById('msg');m.textContent=t;setTimeout(function(){m.textContent='';},4000);}
async function send(){
  var text=document.getElementById('text').value;
  var dur=document.getElementById('dur').value||'3';
  if(!text){msg('请填写要投送的文字');return;}
  var body='message_push=1&message_text='+encodeURIComponent(text)+'&message_duration='+encodeURIComponent(dur);
  post(body);
}
async function post(body){try{var r=await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:body});msg(await r.text());}catch(e){msg('发送失败');}}
async function closeMsg(){try{await fetch('/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'overlay_dismiss=1'});}catch(e){}}
async function status(){
  try{
    var r=await fetch('/message_api',{cache:'no-store'});var s=await r.json();
    var st=document.getElementById('status');
    if(!s.active){st.textContent='屏幕暂无投送内容';st.style.color='#8a93a2';return;}
    st.textContent='正在显示：'+(s.label||'');st.style.color='#222';
  }catch(e){}
}
status();setInterval(status,2000);
</script>
</body></html>
"""

def render():
    # 亮度回填：把已保存的亮度值写回输入框，避免返回主页面时又显示成默认 10
    try:
        _bv = int(float(open(BRIGHT_FILE).read().strip()))
    except Exception:
        _bv = 10
    html = PAGE.replace('id="bright" value="10"', 'id="bright" value="%d"' % _bv)
    return html.encode("utf-8")

def run(cmd, default="未知"):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors="replace", timeout=6)
        s = (out.stdout or "").strip()
        return s if s else default
    except Exception:
        return default

def get_ip():
    """从 ip addr / ifconfig 解析非回环 IPv4（修掉 hostname -I 在本设备为空导致“未知”）。"""
    for cmd in ("ip addr 2>/dev/null", "ifconfig 2>/dev/null", "ip -4 addr 2>/dev/null"):
        s = run(cmd, "")
        for line in s.splitlines():
            line = line.strip()
            if line.startswith("inet ") and "127.0.0.1" not in line:
                parts = line.split()
                ip = parts[1].split("/")[0]
                if ip and ip != "127.0.0.1":
                    return ip
            if line.startswith("inet addr:") and "127.0.0.1" not in line:
                ip = line.split("inet addr:")[1].split()[0]
                if ip and ip != "127.0.0.1":
                    return ip
    return "未知"

def get_brightness():
    for p in glob.glob("/sys/class/backlight/*/brightness"):
        try:
            return open(p).read().strip()
        except Exception:
            pass
    return "未知"

def device_status():
    info = []
    try:
        mi = open("/proc/meminfo").read()
        def gi(k):
            m = re.search(k + r"\s*:\s*(\d+)\s*kB", mi)
            return int(m.group(1)) if m else None
        mt, ma = gi("MemTotal"), (gi("MemAvailable") or gi("MemFree"))
        if mt:
            used = mt / 1024 - (ma / 1024 if ma else 0)
            info.append(("内存", "已用 %d / %d MB" % (used, mt / 1024)))
        else:
            info.append(("内存", "未知"))
    except Exception:
        info.append(("内存", "未知"))
    try:
        info.append(("CPU 负载", open("/proc/loadavg").read().split()[0]))
    except Exception:
        info.append(("CPU 负载", "未知"))
    try:
        s = float(open("/proc/uptime").read().split()[0])
        info.append(("运行时长", "%d天%d时%d分" % (s // 86400, (s % 86400) // 3600, (s % 3600) // 60)))
    except Exception:
        info.append(("运行时长", "未知"))
    info.append(("存储(/sys_data)", run("df -h /sys_data 2>/dev/null | awk 'NR==2{print $3\" / \"$2\" 可用\"$4}'", "未知")))
    info.append(("电量", "未知"))   # 本设备无标准电源节点，暂显示未知（待后续定位）
    temp = "未知"
    try:
        for f in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
            v = int(open(f).read().strip()) / 1000.0
            if v > 0:
                temp = "%.1f°C" % v; break
    except Exception:
        pass
    info.append(("温度", temp))
    info.append(("IP 地址", get_ip()))
    info.append(("屏幕亮度", get_brightness()))
    h = '<table style="width:100%;border-collapse:collapse;font-size:14px">'
    for k, v in info:
        h += '<tr><td style="padding:6px 8px;color:#8a93a2;width:92px">%s</td><td style="padding:6px 8px">%s</td></tr>' % (esc(k), esc(v))
    h += '</table>'
    return h

def export_dict():
    try:
        words = []
        for ts, txt in read_items():
            t = txt
            if t.startswith('[OCR] '):
                t = t[len('[OCR] '):]
            t = t.strip()
            if t:
                words.append(t)
        if not words:
            return "没有可导出的文字"
        os.makedirs("/mnt/userdict", exist_ok=True)
        with open("/mnt/userdict/penweb_export.txt", "a", encoding="utf-8") as f:
            for w in words:
                f.write(w + "\n")
        return "已导出 %d 条到 /mnt/userdict/penweb_export.txt（独立导出文件，未改动原生生词本格式）" % len(words)
    except Exception as e:
        return "导出失败: " + str(e)

def rd(p, d=""):
    """模块级配置读取（server.py 各函数共用，避免 NameError）。"""
    try: return open(p).read().strip()
    except Exception: return d

def rotate_config_json():
    """返回当前轮换配置 JSON（供 /rotate 页面回填），与 screen.py 的读取逻辑保持一致。"""
    import json
    def rd(p, d=""):
        try: return open(p).read().strip()
        except Exception: return d
    items_raw = rd(ROTATE_ITEMS_FILE, "clock")
    items = []
    for p in re.split(r"[,\s]+", items_raw):
        p = p.strip()
        if p in ("clock", "weather", "date"):
            items.append(p)
    if not items: items = ["clock"]
    durs_raw = rd(ROTATE_DUR_FILE, "")
    nums = []
    if durs_raw:
        for p in re.split(r"[,\s]+", durs_raw):
            p = p.strip()
            if p:
                try: nums.append(max(1, int(float(p))))
                except Exception: nums.append(5)
    def default_dur(it): return {"clock":10,"weather":2,"date":2}.get(it,5)
    durs = [nums[i] if i < len(nums) else default_dur(items[i]) for i in range(len(items))]
    d = {"clock": False, "weather": False, "date": False,
         "d_clock": 10, "d_weather": 2, "d_date": 2,
         "city": rd(WEATHER_CITY_FILE, "北京"),
         "sound": rd(ROTATE_SOUND_FILE, "0") in ("1","true","on","yes"),
         "vol": 80}
    try:
        v = int(rd(ROTATE_SOUND_VOL_FILE, "80")); d["vol"] = max(0, min(100, v))
    except Exception: pass
    for it, du in zip(items, durs):
        if it == "clock": d["clock"] = True; d["d_clock"] = du
        elif it == "weather": d["weather"] = True; d["d_weather"] = du
        elif it == "date": d["date"] = True; d["d_date"] = du
    return json.dumps(d)

# ---------- 声音 ----------
def ensure_beep():
    try:
        try:
            vol = int(open(ROTATE_SOUND_VOL_FILE).read().strip())
        except Exception:
            vol = 80
        vol = max(0, min(100, vol))
        amp = max(0.02, 0.4 * (vol / 100.0))   # 基准振幅0.4，按音量线性缩放
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
        return False

def play_beep():
    if not ensure_beep():
        return "提示音生成失败"
    try:
        subprocess.Popen("aplay %s >/dev/null 2>&1 &" % BEEP_FILE, shell=True)
        return "已播放测试音"
    except Exception as e:
        return "播放失败: " + str(e)

# ---------- 亮度 ----------
def set_brightness(val):
    try:
        v = int(float(val))
    except Exception:
        return "亮度值无效"
    for p in glob.glob("/sys/class/backlight/*/brightness"):
        try:
            mx = open(os.path.join(os.path.dirname(p), "max_brightness")).read().strip() or "255"
            mx = int(mx)
            vv = max(0, min(v, mx))
            open(p, "w").write(str(vv))
        except Exception:
            pass
    try:
        open(BRIGHT_FILE, "w").write(str(v))
    except Exception:
        pass
    return "屏幕亮度已设为 %d（立即生效；显示期间将保持此亮度）" % v

def handle_action(cmd):
    if cmd == "restart":
        try:
            subprocess.Popen("sh /sys_data/penweb/stop.sh; sh /sys_data/penweb/start.sh", shell=True)
        except Exception:
            pass
        return "正在重启 penweb 服务…"
    if cmd == "clear":
        try:
            open(STORE, "w").close()
        except Exception:
            pass
        return "文字台已清空"
    if cmd == "export_dict":
        return export_dict()
    if cmd in ("reboot", "poweroff"):
        try:
            subprocess.Popen("sync; %s 2>/dev/null || /sbin/%s 2>/dev/null || busybox %s 2>/dev/null" % (cmd, cmd, cmd), shell=True)
        except Exception:
            pass
        return "正在" + ("重启设备" if cmd == "reboot" else "关机") + "…"
    return "未知操作: " + str(cmd)

def screen_action(a, text=None, fg=None, bg=None, bold=None, scroll=None, voff=None,
                  scroll_speed=None, brightness=None, sound=None,
                  rotate_items=None, rotate_dur=None, rotate_sound=None, weather_city=None,
                  rotate_sound_vol=None):
    # 屏幕显示（最终方案：叠加绘制 + PAN 上屏）：不杀主程序、不碰看门狗，不会重启/卡死。
    #   模式经 /tmp/penweb_mode 切换（idle/test/clock/clear/text/rotate）；
    #   idle 时 screen.py 自行退出，触摸屏幕主程序重绘即恢复原生界面。
    PY = "/opt/bin/python3"
    if not os.path.exists(PY):
        PY = "python3"
    MODE = "/tmp/penweb_mode"
    PIDF = "/tmp/penweb_screen.pid"
    FLIP = DIR + "/screen_flip.conf"

    def _screen_running():
        try:
            pid = open(PIDF).read().strip()
            return pid.isdigit() and os.path.exists("/proc/%s" % pid)
        except Exception:
            return False

    def _spawn():
        if not _screen_running():
            subprocess.Popen("%s %s/screen.py >/dev/null 2>&1 &" % (PY, DIR), shell=True)

    # 颜色：任何显示操作都可附带文字色/背景色
    if fg is not None:
        try: open(DIR + "/screen_fg.conf", "w").write(fg)
        except Exception: pass
    if bg is not None:
        try: open(DIR + "/screen_bg.conf", "w").write(bg)
        except Exception: pass

    if a == "brightness" and brightness is not None:
        return set_brightness(brightness)
    if a == "sound":
        return play_beep()
    if a == "rotate":
        if rotate_items is not None:
            try: open(ROTATE_ITEMS_FILE, "w").write(str(rotate_items))
            except Exception: pass
        if rotate_dur is not None:
            try: open(ROTATE_DUR_FILE, "w").write(str(rotate_dur))
            except Exception: pass
        if rotate_sound is not None:
            try: open(ROTATE_SOUND_FILE, "w").write("1" if str(rotate_sound) in ("1","true","on","yes") else "0")
            except Exception: pass
        if weather_city is not None:
            try: open(WEATHER_CITY_FILE, "w").write(str(weather_city))
            except Exception: pass
        if rotate_sound_vol is not None:
            try:
                v = int(float(rotate_sound_vol))
                open(ROTATE_SOUND_VOL_FILE, "w").write(str(max(0, min(100, int(v)))))
            except Exception: pass
        try: open(MODE, "w").write("rotate")
        except Exception: pass
        _spawn()
        return "已开始轮换显示（按勾选项循环；天气首次显示需联网获取，约 1~2 秒）。点“停止”可恢复词典笔。"
    if a == "text":
        if text is not None:
            try: open(DIR + "/screen_text.conf", "w").write(text)
            except Exception: pass
        try: open(MODE, "w").write("text")
        except Exception: pass
        _spawn()
        t = (text or "").replace("\n", " ")
        return "已显示自定义文字“%s”（不动主程序，不会重启；显示期间自动防熄屏）" % (t[:20] + ("…" if len(t) > 20 else ""))
    if a in ("clock", "clear"):
        try:
            open(MODE, "w").write(a)
        except Exception:
            pass
        _spawn()
        label = {"clock": "全屏时钟", "clear": "清屏(黑屏)"}.get(a, a)
        extra = "（首次启动需渲染高清字形，几秒后出画面，之后走缓存瞬开）" if a == "clock" else ""
        return "已显示%s%s（不动主程序，不会重启；显示期间自动防熄屏）" % (label, extra)
    if a in ("flip_h", "flip_v"):
        s = "h"
        try:
            s = open(FLIP).read().strip() or "h"
        except Exception:
            pass
        if s not in ("none", "h", "v", "hv"):
            s = "h"
        if a == "flip_h":
            s = {"none": "h", "h": "none", "v": "hv", "hv": "v"}[s]
        else:
            s = {"none": "v", "h": "hv", "v": "none", "hv": "h"}[s]
        try:
            open(FLIP, "w").write(s)
        except Exception as e:
            return "方向切换失败: " + str(e)
        return "显示方向已切换为 %s（h=水平镜像 v=垂直镜像 hv=两者 none=原样），1~2秒后生效；不对就再点一次" % s
    if a == "restore":
        try:
            open(MODE, "w").write("idle")
        except Exception:
            pass
        return "已停止屏幕显示（防熄屏已解除）；触摸词典笔屏幕即可回到原生界面"
    # 加粗 / 滚动 / 垂直微调：写配置，当前显示立即生效（screen.py 每帧读取）
    if a in ("bold", "scroll", "voff"):
        def _yn(v): return str(v) in ("1", "true", "on", "yes")
        if a == "bold" and bold is not None:
            try: open(DIR + "/screen_bold.conf", "w").write("1" if _yn(bold) else "0")
            except Exception: pass
            return "加粗已%s（时钟与文字立即生效）" % ("开启" if _yn(bold) else "关闭")
        if a == "scroll" and scroll is not None:
            try: open(DIR + "/screen_scroll.conf", "w").write("1" if _yn(scroll) else "0")
            except Exception: pass
            return "滚动显示已%s（仅文字模式；字保持原大、横向循环滚动）" % ("开启" if _yn(scroll) else "关闭")
        if a == "voff" and voff is not None:
            try: open(DIR + "/screen_voff.conf", "w").write(str(int(float(voff))))
            except Exception: pass
            return "垂直微调已设为 %s（正数上移、负数下移，用于把内容移到可见屏中央）" % int(float(voff))
    if a == "scroll_speed" and scroll_speed is not None:
        try: open(DIR + "/screen_scroll_speed.conf", "w").write(str(int(float(scroll_speed))))
        except Exception: pass
        return "滚动速度已设为 %s px/秒（约 5~400，越大越快；文字滚动立即生效）" % int(float(scroll_speed))
    return "未知屏幕操作: " + str(a)

# ---------- 天气（网页展示 + 手动刷新，server 端独立抓取，与 screen.py 互不耦合） ----------
WMO_DESC = {0:"晴",1:"大致晴",2:"局部多云",3:"阴",45:"雾",48:"雾凇",51:"小毛毛雨",53:"毛毛雨",55:"大毛毛雨",56:"冻毛毛雨",57:"冻毛毛雨",61:"小雨",63:"中雨",65:"大雨",66:"冻雨",67:"冻雨",71:"小雪",73:"中雪",75:"大雪",77:"雪粒",80:"阵雨",81:"强阵雨",82:"暴雨",85:"阵雪",86:"强阵雪",95:"雷阵雨",96:"雷阵雨伴冰雹",99:"强雷阵雨伴冰雹"}
def _wx_resolve(city):
    city = (city or "北京").strip() or "北京"
    try:
        import urllib.request, urllib.parse, json as _j
        g = "https://geocoding-api.open-meteo.com/v1/search?name=%s&count=1&language=zh" % urllib.parse.quote(city)
        req = urllib.request.Request(g, headers={"User-Agent": "penweb"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = _j.load(r)
        res = (d.get("results") or [])
        if res:
            g0 = res[0]
            return float(g0["latitude"]), float(g0["longitude"]), g0.get("name", city)
    except Exception:
        pass
    return 39.9042, 116.4074, city
def fetch_weather_server(city):
    try:
        import urllib.request, json as _j
        lat, lon, name = _wx_resolve(city)
        url = "https://api.open-meteo.com/v1/forecast?latitude=%.4f&longitude=%.4f&current=temperature_2m,weather_code" % (lat, lon)
        req = urllib.request.Request(url, headers={"User-Agent": "penweb"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = _j.load(r)
        cur = d.get("current", {})
        temp = cur.get("temperature_2m")
        code = cur.get("weather_code")
        return {"temp": temp, "code": code, "name": name, "desc": WMO_DESC.get(code, "未知")}
    except Exception as e:
        return {"error": str(e)}
_WX = {"data": {"loading": True}, "t": 0.0, "city": None}
def _wx_save_cache():
    """把天气（与网页一致）写入共享文件，供屏幕端读取，保证两端同步。"""
    try:
        with open(WEATHER_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"data": _WX["data"], "t": _WX["t"], "city": _WX["city"]}, f)
    except Exception:
        pass
def _wx_guard():
    # 每 5 分钟自动刷新（与屏幕天气一致）；手动刷新由 /weather_refresh 立即触发
    while True:
        try:
            city = rd(WEATHER_CITY_FILE, "北京")
            _WX["data"] = fetch_weather_server(city)
            _WX["t"] = time.time()
            _WX["city"] = city
            _wx_save_cache()
        except Exception:
            pass
        time.sleep(300)

class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="text/html; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
    def do_GET(self):
        u = path = urlparse(self.path)
        if u.path == "/rotate":
            return self._send(ROTATE_PAGE.encode("utf-8"))
        if u.path == "/rotate_config":
            try:
                return self._send(rotate_config_json().encode("utf-8"), "application/json; charset=utf-8")
            except Exception:
                return self._send(b"{}", "application/json; charset=utf-8")
        if u.path == "/export":
            try:
                with open(STORE, "rb") as f: data = f.read()
            except FileNotFoundError: data = b""
            return self._send(data, "text/plain; charset=utf-8")
        if u.path == "/clear":
            open(STORE, "w").close()
            self.send_response(302); self.send_header("Location", "/"); self.end_headers(); return
        if u.path == "/status":
            return self._send(device_status().encode("utf-8"), "text/html; charset=utf-8")
        if u.path == "/content":
            return self._send(render_items().encode("utf-8"), "text/html; charset=utf-8")
        if u.path == "/alarm":
            return self._send(ALARM_PAGE.encode("utf-8"))
        if u.path == "/alarm_api":
            return self._send(json.dumps(read_alarms()).encode("utf-8"), "application/json; charset=utf-8")
        if u.path == "/alarm_status":
            return self._send(json.dumps(alarm_status()).encode("utf-8"), "application/json; charset=utf-8")
        if u.path == "/weather_api":
            return self._send(json.dumps({"data": _WX["data"], "t": _WX["t"], "city": _WX["city"]}).encode("utf-8"), "application/json; charset=utf-8")
        if u.path == "/timer":
            return self._send(TIMER_PAGE.encode("utf-8"))
        if u.path == "/timer_api":
            return self._send(json.dumps(timer_status()).encode("utf-8"), "application/json; charset=utf-8")
        if u.path == "/message":
            return self._send(MESSAGE_PAGE.encode("utf-8"))
        if u.path == "/message_api":
            return self._send(json.dumps(message_status()).encode("utf-8"), "application/json; charset=utf-8")
        self._send(render())
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8", "replace")
        data = parse_qs(raw)
        if data.get("alarm_dismiss"):
            _dismiss_alarm()
            return self._send("已停止".encode("utf-8"), "text/plain; charset=utf-8")
        if data.get("weather_refresh"):
            try:
                city = rd(WEATHER_CITY_FILE, "北京")
                _WX["data"] = fetch_weather_server(city)
                _WX["t"] = time.time()
                _WX["city"] = city
            except Exception as e:
                _WX["data"] = {"error": str(e)}
            _wx_save_cache()
            return self._send(json.dumps({"data": _WX["data"], "t": _WX["t"], "city": _WX["city"]}).encode("utf-8"), "application/json; charset=utf-8")
        if data.get("alarms"):
            try:
                lst = json.loads(data.get("alarms")[0])
                if isinstance(lst, list):
                    write_alarms(lst)
                    return self._send("已保存".encode("utf-8"), "text/plain; charset=utf-8")
            except Exception as e:
                return self._send(("保存失败: " + str(e)).encode("utf-8"), "text/plain; charset=utf-8")
        if data.get("timer_start"):
            try:
                label = data.get("timer_label", [""])[0]
                dur = data.get("timer_duration", ["0"])[0]
                rotate = data.get("timer_rotate", ["0"])[0] in ("1", "on", "true", "yes")
                sound = data.get("timer_sound", ["1"])[0] in ("1", "on", "true", "yes")
                self._send(start_timer(label, dur, rotate, sound).encode("utf-8"), "text/plain; charset=utf-8")
            except Exception as e:
                self._send(("操作失败: " + str(e)).encode("utf-8"), "text/plain; charset=utf-8")
            return
        if data.get("timer_stop"):
            mode = data.get("timer_mode", [""])[0]
            self._send(stop_timer(mode).encode("utf-8"), "text/plain; charset=utf-8"); return
        if data.get("timer_convert"):
            mode = data.get("timer_mode", [""])[0]
            self._send(convert_timer(mode).encode("utf-8"), "text/plain; charset=utf-8"); return
        if data.get("message_push"):
            try:
                text = data.get("message_text", [""])[0]
                dur = data.get("message_duration", ["3"])[0]
                self._send(push_message(text, dur).encode("utf-8"), "text/plain; charset=utf-8")
            except Exception as e:
                self._send(("推送失败: " + str(e)).encode("utf-8"), "text/plain; charset=utf-8")
            return
        if data.get("overlay_dismiss"):
            _dismiss_overlay()
            self._send("已关闭".encode("utf-8"), "text/plain; charset=utf-8"); return
        screen = data.get("screen", [""])[0]
        if screen:
            self._send(screen_action(screen,
                        data.get("text", [""])[0] or None,
                        data.get("fg", [""])[0] or None,
                        data.get("bg", [""])[0] or None,
                        data.get("bold", [""])[0] or None,
                        data.get("scroll", [""])[0] or None,
                        data.get("voff", [""])[0] or None,
                        data.get("scroll_speed", [""])[0] or None,
                        data.get("brightness", [""])[0] or None,
                        data.get("sound", [""])[0] or None,
                        data.get("rotate_items", [""])[0] or None,
                        data.get("rotate_dur", [""])[0] or None,
                        data.get("rotate_sound", [""])[0] or None,
                        data.get("weather_city", [""])[0] or None,
                        data.get("rotate_sound_vol", [""])[0] or None).encode("utf-8"), "text/plain; charset=utf-8")
            return
        cmd = data.get("cmd", [""])[0]
        self._send(handle_action(cmd).encode("utf-8"), "text/plain; charset=utf-8")

    def log_message(self, *a): pass

if __name__ == "__main__":
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    open(STORE, "a").close()
    ThreadingHTTPServer.allow_reuse_address = True
    print("penweb listening on http://0.0.0.0:%d/" % PORT)

    # 防深度睡眠：本设备是裸 Linux，挂起来源是原厂 guliteos_test 往 /sys/power/state 写 mem。
    # 没有 wake_lock / autosleep 节点，故用 mount --bind 把该节点盖成占位文件，
    # 任何进程（含 guliteos_test）写 mem 都会落空，设备不再挂起。start.sh 已绑定，
    # 这里每 2s 复查，被 umount 时自动重新绑定；nowake.conf=0/off 则解除绑定恢复原厂睡眠。
    def _ensure_no_suspend():
        try:
            if open(DIR + "/nowake.conf").read().strip() in ("0", "off", "false"):
                os.system("umount /sys/power/state 2>/dev/null")
                return
        except Exception:
            pass
        try:
            open("/tmp/no_suspend", "w").write("blocked")
        except Exception:
            pass
        try:
            cur = open("/sys/power/state").read()
            if "standby" in cur:   # 仍是真节点（内容 "freeze standby mem"），需 (重新) 绑定
                os.system("mount --bind /tmp/no_suspend /sys/power/state 2>/dev/null")
        except Exception:
            pass

    def _wake_guard():
        """防深度睡眠始终生效（见 _ensure_no_suspend）；仅在 penweb 接管显示
        （mode 非 idle，含事件态 event）时才强制点亮屏幕。idle 时不动 fb0/blank 与
        背光，让词典笔原生界面正常熄屏；但闹钟/消息投送/倒计时等事件会经
        _enter_event_display 临时接管（mode=event）点亮并显示，结束后退回 idle 熄屏。"""
        while True:
            _ensure_no_suspend()
            try:
                m = open("/tmp/penweb_mode").read().strip()
            except Exception:
                m = "idle"
            if m and m != "idle":
                try:
                    open("/sys/class/graphics/fb0/blank", "w").write("0")
                except Exception:
                    pass
                try:
                    tgt = -1
                    try:
                        tgt = int(open(BRIGHT_FILE).read().strip())
                    except Exception:
                        pass
                    for p in glob.glob("/sys/class/backlight/*/brightness"):
                        try:
                            mx = open(os.path.join(os.path.dirname(p), "max_brightness")).read().strip() or "255"
                            mx = int(mx); v = mx if tgt < 0 else max(0, min(tgt, mx))
                            open(p, "w").write(str(v))
                        except Exception:
                            pass
                except Exception:
                    pass
            time.sleep(2)

    # ---------- 息屏（idle）态事件点亮屏幕并显示 ----------
    # 闹钟/消息投送/倒计时在 idle（息屏、显示原生界面）发生时，临时接管（mode=event）
    # 点亮屏幕并展示；事件结束后自动退回 idle，屏幕重新熄灭。仅在当前确为 idle 时才
    # 接管，不打扰用户已主动开启的显示（全屏时钟/轮换等）。
    EVENT_MODE_FLAG = DIR + "/event_mode.flag"

    def _spawn_screen_if_needed():
        """若 screen.py 未运行则拉起（与 screen_action._spawn 逻辑一致）。"""
        PIDF = "/tmp/penweb_screen.pid"
        try:
            pid = open(PIDF).read().strip()
            if pid.isdigit() and os.path.exists("/proc/%s" % pid):
                return
        except Exception:
            pass
        PY = "/opt/bin/python3"
        if not os.path.exists(PY):
            PY = "python3"
        try:
            subprocess.Popen("%s %s/screen.py >/dev/null 2>&1 &" % (PY, DIR), shell=True)
        except Exception:
            pass

    def _enter_event_display():
        """idle 态下发生事件（闹钟/消息/倒计时）时点亮屏并显示。
        仅当当前确为 idle 才切换模式并打标记；用户已在显示别的内容则不插手。"""
        try:
            if os.path.exists(EVENT_MODE_FLAG):
                return
            try:
                m = open("/tmp/penweb_mode").read().strip()
            except Exception:
                m = "idle"
            if m and m != "idle":
                return
            open(EVENT_MODE_FLAG, "w").write("1")
            open("/tmp/penweb_mode", "w").write("event")
            _spawn_screen_if_needed()
        except Exception:
            pass

    def _event_active():
        """当前是否有需要展示的事件（闹钟/未过期消息/倒计时覆盖）。"""
        if os.path.exists(ALARM_ACTIVE_FILE):
            return True
        ov = read_overlay()
        if ov:
            if ov.get("type") == "message":
                exp = ov.get("expire_ts", 0)
                if exp == 0 or time.time() < exp:
                    return True
            elif ov.get("type") == "timer":
                return True
        return False

    def _event_display_guard():
        """事件结束后把模式退回 idle（屏幕熄灭、原生界面恢复）并清除标记。
        仅当我们自己切到 event 态时才退回；用户期间手动切走则不打扰。"""
        while True:
            try:
                if os.path.exists(EVENT_MODE_FLAG) and not _event_active():
                    try:
                        m = open("/tmp/penweb_mode").read().strip()
                    except Exception:
                        m = "idle"
                    if m == "event":
                        try:
                            open("/tmp/penweb_mode", "w").write("idle")
                        except Exception:
                            pass
                    try:
                        os.remove(EVENT_MODE_FLAG)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(0.5)

    threading.Thread(target=_event_display_guard, daemon=True).start()
    threading.Thread(target=_wake_guard, daemon=True).start()
    threading.Thread(target=_alarm_checker, daemon=True).start()
    threading.Thread(target=_wx_guard, daemon=True).start()
    threading.Thread(target=_touch_listener, daemon=True).start()
    threading.Thread(target=_timer_watcher, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
