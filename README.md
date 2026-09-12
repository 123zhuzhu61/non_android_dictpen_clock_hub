# 闲置词典笔改造：桌面挂钟 / 信息屏（penweb）

> 把一台吃灰的词典笔，改成摆在桌上的联网挂钟 + 信息屏。
> **本文以「作业帮词典笔 S2 Pro」为例，其他品牌与型号可参照本文思路自行适配。**

>

---

## 这是什么

家里有一台闲置的词典笔——扫描功能早就不怎么用了，但它的屏幕、WiFi、电池都还好好的。
这个项目做的事就是：**在不改动原厂固件的前提下，把它改造成一个联网的桌面挂钟与信息屏**。

- 常亮显示**时钟 / 天气 / 日期**，可勾选轮换，每项单独设显示秒数
- 手机或电脑浏览器远程下发**倒计时、消息、闹钟**，笔的屏幕立即响应
- 息屏状态下，闹钟 / 消息 / 倒计时归零仍会**自动点亮屏幕并响铃**，事件结束后自动熄灭回原生界面
- 原本的扫描功能不受影响，识别出的文字会自动汇总到网页，可一键导出 `.txt`

整套系统跑在设备本地：只有一个 Python 网页服务 + 一个直接写 framebuffer 的渲染进程， 
**不依赖外部服务器，也不上传任何数据**。

### 📌 关于机型（请先看这里）

- **本文的实测机型是「作业帮词典笔 S2 Pro」（固件 1.0.190.450，Lombo N7V5 / GuliteOS）。**
- 但这套方案的本质是「**基于 Linux 的嵌入式设备的网页控制 + 屏幕接管**」，
  **思路并不绑定某个品牌或某个型号**。
- 如果你手里是**其他品牌 / 其他型号的词典笔**（点读笔、扫描笔、翻译笔等），只要满足几个大致前提
  ——设备运行 Linux、**能开启调试通道**、能装上包管理器——就可以**参照本文的思路自行适配**。
  需要你自己确认的差异主要有这些（右侧是本文 S2 Pro 的取值，仅供对照）：

  | 需要自行确认的点 | 本文 S2 Pro 的取值 |
  |---|---|
  | 系统架构（`uname -m`） | `armv7`，对应 entware 目录 `armv7sf-k3.2` |
  | 包管理器的位置与安装方式 | Entware / opkg，位于 `/opt/bin` |
  | 调试通道怎么开 | WebADB 网页（**非 Android**，platform-tools 的 adb 连不上） |
  | 屏幕 framebuffer 节点与分辨率 | `screen.py` 中按 S2 Pro 屏幕参数写死 |
  | 扫描数据的落盘路径 | `/sys_data/fatfs/answer_word/scanWordRecord.json` |
  | 扫描原图目录（OCR 用） | `/sys_data/fatfs/answer_word/answerImgs/` |
  | 部署目录 | `/sys_data/penweb/` |

- ⚠️ **作者只在上述 S2 Pro 上完整实测过，不对其他机型的可用性做任何保证。**
  适配其他机型属于你自己的探索，请自行承担相应风险（见下方免责声明）。
 

---

## ⚠️ 免责声明（使用本项目前请先完整阅读）

> **继续使用本项目，即表示你已完整阅读并同意以下全部条款。**

### 1. 项目性质

- 本项目是**个人出于学习与技术研究的非官方项目**，仅用于闲置词典笔的改造，不对词典笔官方功能进行修改。
- 精确说明改动边界：本项目**不刷写、不替换固件镜像，不修改原厂主程序**；但会在设备可写分区创建部署文件（`/sys_data/penweb/`）、安装第三方软件包（Entware，位于 `/sys_data/opt`）、创建开机自启项（`/data/pre_run.sh`），并在运行期通过 `mount --bind` 挂载 `/opt`、占位 `/sys/power/state` 以阻止深度睡眠。完整改动与还原方法见「完全卸载」一节。
- 文中出现的设备型号、厂商名称、固件版本等，仅用于说明适配对象与操作路径。

### 2. 使用前提（必须全部满足）

- 你**只对本人拥有完全所有权**的设备进行操作，不对他人、单位、机构或公共设备使用。
- 你已充分理解操作内容，并**自愿承担由此产生的一切风险与后果**。

### 3. 风险自担

- 本方案**不修改设备固件二进制**，但仍存在导致设备故障（"变砖"）、系统不稳定、功能异常、数据丢失、续航下降、**失去官方保修与服务资格**的可能。
- 项目按 **"现状"（AS IS）** 提供，**不提供任何明示或默示的担保**，包括但不限于可用性、准确性、稳定性、适用于特定目的及不侵权。
- 作者与贡献者**不对任何直接、间接、附带或衍生的损失承担责任**，也不提供设备维修、数据恢复或技术支持承诺。

### 4. 禁止用途

严禁将本项目用于以下任何行为：

- 绕过、破解任何付费内容、版权保护措施或数字版权管理（DRM）机制；
- 未经授权访问、抓取、存储、传播他人设备、账号或数据；
- 侵犯他人隐私权、商业秘密、著作权等合法权益；
- 任何违反所在地区现行法律法规的行为。

因上述用途产生的一切民事、行政或刑事责任，由使用者自行承担。

### 5. 内容与数据合规

- 词典笔扫描、OCR 得到的文字与图片，可能包含他人隐私信息或受著作权保护的内容。如何采集、保存、导出、共享这些内容，**由使用者自行负责并确保合规**。
- 本项目**不收集、不上传、不传播任何用户数据**，全部处理均在本地设备与局域网内完成。

### 6. 第三方依赖与外部链接

- 项目依赖的 Entware / opkg、Python、jq、tesseract 及其语言包、WebADB 等均为第三方项目，各自遵循其许可证；其可用性、安全性与合规性由相应提供方负责。
- 文档中引用的外部博客与链接仅作技术参考，其内容不由本项目控制，本项目不对其准确性、时效性与合法性负责。

### 7. 权利保护

- 本项目**不含、不分发任何设备原厂固件、官方二进制、字体或受版权保护的资源文件**。
- 若任何权利方认为本项目内容侵犯其合法权益，请通过 issue 或邮件联系，核实后将及时移除相关内容。

---

## 目录

- [实机轮播画面（效果实拍）](#实机轮播画面效果实拍)
- [一、安装与使用说明](#一安装与使用说明)
- [二、文件说明](#二文件说明)
- [三、补充：关于 `ocr.sh`](#三补充关于-ocrsh)

---

## 实机轮播画面（效果实拍）

以下三张是 penweb 接管屏幕后，**轮换显示**功能在词典笔上的真实运行画面，分别对应三类可轮换内容：**全屏时钟 / 天气 / 日期**。

这些画面由 `screen.py` 直接写 framebuffer（`FBIOPAN_DISPLAY`）渲染，**不是设备原生界面**；轮换哪些项、每项显示多少秒、是否开启切换提示音，均可在网页「轮换显示」页配置（详见后文 [5.2 屏幕显示](#52-屏幕显示screenpy-接管)）。

<table>
<tr>
<td align="center">
<img src="screenshots/01-clock.jpg" width="250" alt="全屏时钟"><br>
<sub><b>全屏时钟</b></sub>
</td>
<td align="center">
<img src="screenshots/02-weather.jpg" width="250" alt="天气显示"><br>
<sub><b>天气</b>（25° 阵雨 + 城市）</sub>
</td>
<td align="center">
<img src="screenshots/03-date.jpg" width="250" alt="日期显示"><br>
<sub><b>日期</b>（2026年09月01日 星期一）</sub>
</td>
</tr>
</table>

> 📷 说明：照片为手机实拍，屏幕上的划痕、反光与塑料外壳纹理属于设备本身的使用痕迹与拍摄条件所致，**不是显示缺陷**。

配合轮换显示，本版还支持：

- **倒计时**：时/分/秒输入，归零时抢屏 + 循环"嘚儿"声，点一下屏幕即关
- **消息投送**：网页发文字到笔屏幕，可设显示秒数
- **闹钟**：到点自动点亮屏幕并循环响铃
- **息屏响应**：即使屏幕熄灭，上述三类事件仍会自动点亮屏幕并响铃，事件结束后自动熄灭回原生界面

---

## 一、安装与使用说明

> 以下为本目录 `安装与使用说明.md` 的完整内容。

# 作业帮词典笔「文字台 + 屏幕接管」(penweb) 安装与使用说明

> 适配机型：作业帮词典笔 S2 Pro，固件版本1.0.190.450（Lombo N7V5 / GuliteOS，`guliteos_test` 主程序）
> 调试工具：WebADB 网站（https://app.webadb.com/ ）
> 本说明包含**从零开始**的完整流程。前置的 ADB / Entware 准备步骤参考博客：
> https://onimai0306.wksite.cn/Blog/blogs/20260301.html

---

## 一、这是什么 / 能做什么

`penweb` 是在词典笔上跑的一个**零依赖网页应用**，做两件事：
1. **文字台**：把词典笔扫描识别出的文字自动汇总到网页，也支持手动粘贴，可查看 / 导出 `.txt`。
   - 自动抓词：扫描的词每隔约 5 秒自动出现在网页。
2. **屏幕接管显示（核心功能）**：`screen.py` 接管设备的 framebuffer（显示屏），可显示天气、时钟、轮换内容，以及网页下发的**倒计时**和**消息投送**；还能在笔上"测试声音"（嘚儿声）。

**已删除的功能**（本版不含）：图片投送、正计时、测试图案。\
**声音**：目前只有合成音 `beep.wav`（880Hz 短音，即"嘚儿"），面板无其他声音。

---

## 二、从零开始：前置准备

> 本节只做三件事：**打开设备的调试开关 → 用网页工具连上它 → 给它装一个包管理器**。
> 这几个前置环节的做法参考自公开资料，出处见文末 [致谢与引用来源](#致谢与引用来源)。
> 下面按「**为什么要做 → 怎么做 → 怎么确认成功**」重新组织，并补上了适配其他机型时的注意点。

### 2.1 打开设备的调试开关（ADB）（以下步骤在 S2 Pro 固件 1.0.190.450 上实测，同型号其他固件版本未必相同）

设备出厂默认不开放调试，得先在系统设置里把这个开关翻出来：

1. 进入 **设置 → 关于设备**
2. 连续点击 **SN 码** 若干次，会弹出密码输入框，输入 `123443211`
3. 进入后打开 **ADB** 开关

**注意**：ADB后尽量保证设备处于亮屏状态，否则设备有可能断开连接。若不慎断开连接，ADB网页版有几率连接不上，这时重启电脑即可。

> ⚠️ **这台设备跑的是 Linux，不是 Android。** 这一点直接决定了工具该怎么选——
> platform-tools 里的 `adb` 连不上它（会报 `no devices/emulators found`，严重时还会把设备连死机）。
> 所以我们改用 **WebADB**：一个纯网页的调试客户端，不用装驱动，也不用配环境。

> 📺 原博客附了两个视频教程（B 站，非本人制作）：
> [开启 ADB](https://www.bilibili.com/video/BV1we6SByEuU/) ｜ [安装软件包管理器](https://www.bilibili.com/video/BV1YoQcB9Enw/)

### 2.2 用 WebADB 连上设备

1. 用 **USB 数据线**把词典笔接到电脑
2. 浏览器打开 **https://app.webadb.com/** ，点 **Add** 添加设备
3. 在词典笔屏幕上点**允许**授权，连上后页面会显示设备信息

**怎么确认成功**：页面出现设备信息，且 **Shell** 标签里敲命令有回显。
**常见问题**：若不慎断开词典笔与电脑的连接，再次连接有可能会连接不上，此时只需重启电脑即可。
连上之后主要用这两个标签页：

| 标签 | 用途 |
|---|---|
| **Shell** | 敲命令，等价于设备上的 sh 终端——后面绝大部分操作都在这里 |
| **Files** | 上传 / 下载文件——部署脚本走这个通道 |

### 2.3 给它装一个包管理器（Entware / opkg）

**为什么要做**：设备自带的系统极其精简——没有 `python3`（网页服务要它）、没有 `jq`（抓词要它），
更没有包管理器。Entware 是一套面向嵌入式设备的软件源，装上它就有了 `opkg`，
缺什么直接 `opkg install`，不用自己交叉编译。

#### 第一步：给 `/opt` 找一个能长期存放的位置

`/opt` 是 Entware 的默认安装位置，但设备原来的 `/opt` 是**只读文件系统**（实测 `mkdir` 会报 `Read-only file system`），所以必须先在持久分区建一个可写目录，再把它挂载到 `/opt`：

```sh
mkdir -p /sys_data/opt
mount --bind /sys_data/opt /opt
```

⚠️ **这两行最容易出错，务必注意：**

- 第一行建的目录名，必须和第二行挂载的**源路径**完全一致（都是 `/sys_data/opt`）。写成 `mkdir /sys_data/opkg` 再挂 `/sys_data/opt`，是实测踩过的坑——挂载静默失败，后面全盘皆输。
- `mount --bind` 后面必须有**两个**参数（源 + 目标）。只写一个会报 `can't find ... in /etc/fstab`。

**挂载后立刻验证，不要跳过：**

```sh
touch /opt/_test && rm /opt/_test && echo "OK: /opt 可写"
```

必须看到 `OK: /opt 可写` 才继续；若报 `Read-only file system`，说明挂载没生效，回头检查上面两行。

> 💡 **适配其他机型时注意**：持久分区的路径每台设备都不一样——有的是 `/userdisk`，有的是 `/sys_data`，
> 有的还需要先把根分区改成可写（`mount -o remount,rw /`）。
> 用 `df -h` 看一眼哪个分区容量大、重启不丢，就把它挂到 `/opt`。
> 不想动挂载的话，社区里也有人用软链接 `ln -s` 达到同样效果。

#### 第二步：按架构安装 Entware

先确认 CPU 架构：

```sh
uname -m
```

本文的作业帮 S2 Pro 是 **armv7**，对应 entware 目录 `armv7sf-k3.2`，安装命令：

```sh
wget -O - http://bin.entware.net/armv7sf-k3.2/installer/generic.sh | sh
```

> ⚠️ **架构必须对上**，装错架构的包根本跑不起来。
> 另外国内镜像源基本都因为 SSL 的问题连不上，官方源服务器在国外，慢一点但能装成功，耐心等。

#### 第三步：更新索引并试装一个包

opkg 装好后在 `/opt/bin`，先把它加进 PATH：

```sh
export PATH=/opt/bin:/opt/sbin:$PATH
opkg update
opkg install jq
```

**怎么确认成功**：`jq --version` 能输出版本号。

以后装任何包都是 `opkg install <包名>`。

> 这里 export 的 PATH **只在当前 Shell 会话有效**，重开 Shell 或重启设备后要重新设置。
> `deploy.sh` 内部已经处理了这件事，正常跟着流程走不用管。

#### 下载太慢怎么办

官方源服务器在国外，`python3`、`tesseract` 这类大包要等较长时间，中途断了就得重来。
国内镜像（清华 TUNA、中科大 USTC）的 Entware 目录**实测已全部下线（404）**，换镜像这条路走不通。

两个可行办法：

1. **耐心装一次**：所有包装完会持久保存在 `/sys_data/opt`，以后重启都不用重装。
2. **离线安装（推荐）**：在电脑上把全部 ipk 一次性下载好，传到设备安装，全程不依赖设备网速——见下一节 [2.5 离线安装](#25-离线安装彻底解决下载慢)。

### 2.4 连 WiFi、查 IP

- 在词典笔上连好 WiFi（设置里操作）。
- 在 WebADB **Shell** 查 IP：

```sh
ifconfig
```

找 `wlan0`（或 `eth0`）下的 `inet addr:`，比如 `192.168.1.100`。手机/电脑要和词典笔在**同一 WiFi** 下才能访问网页。

### 2.5 离线安装：彻底解决下载慢

**背景**：Entware 官方源服务器在国外，装 `python3`（含依赖约 20MB+）、`tesseract` 这类包可能要等很久，中途断了还得重来；国内镜像（清华 TUNA、中科大）的 Entware 目录实测已全部下线，换镜像走不通。

最可靠的办法是**离线安装**：在电脑上把全部 ipk 一次性下载好（电脑网速快、可用下载工具），传到设备安装，全程不依赖设备网速。

本教程配套的 `entware_packages/` 目录就是为此准备的：

```
entware_packages/
├── ipk/                  ← 全部 ipk 包（约 28.6 MB，含 python3 / jq / tesseract / pillow 及全部依赖，共 57 个）
├── install_offline.sh    ← 设备端离线安装脚本
├── chi_sim.traineddata   ← 中文 OCR 训练数据（Entware 源里没有，需单独放）
└── download_list.txt     ← ipk 来源清单（供核对，或自行重新下载）
```

**操作步骤：**

1. **先建目录**：⚠️ WebADB 网页版的 **Files** 标签**不能创建文件夹**，所以先切到 **Shell**，手动把目录建好：

```sh
mkdir -p /sys_data/offline
```

2. **再上传**：切回 **Files**，进入 `/sys_data/offline/`，把以下文件全部上传进去：

   - `install_offline.sh`
   - `chi_sim.traineddata`
   - `ipk/` 文件夹里的**全部 57 个 ipk 文件**

   文件较多，上传需要几分钟，属正常现象；中途个别失败，重传那一个即可。

   > 💡 **嫌进子目录麻烦？** 把上面这些文件**直接传到 `/sys_data/` 根目录**也完全可以——
   > `install_offline.sh` 会自动在脚本所在目录找 ipk，不要求目录必须叫 `offline`。
   > 只是 57 个文件会和原厂文件混在一起，装完记得按后文的说明清理。

3. **安装**（切回 **Shell**）：（该过程需要一定的时间，注意不要让词典笔熄屏）

```sh
mkdir -p /sys_data/opt
mount --bind /sys_data/opt /opt
export PATH=/opt/bin:/opt/sbin:$PATH
sh /sys_data/offline/install_offline.sh
```

> 上面两条路径写的是"传到 `/sys_data/offline/`"的情况；如果你传到了根目录，
> 最后一行改为 `sh /sys_data/install_offline.sh`。
>
> ⚠️ 前提是 Entware 本体已按 [2.3](#23-给它装一个包管理器entware--opkg) 装好（`/opt/bin/opkg` 存在）。
> Entware 本体只有一个脚本加一个 opkg 二进制，文件很小，在线装一般不至于慢。

脚本会 `opkg install` 目录下全部 ipk：已安装的自动跳过，依赖顺序自动处理，重复执行无副作用。

4. **放中文 OCR 数据**（Entware 源里没有这个包，只能手动放）：

```sh
mkdir -p /opt/share/tessdata
cp /sys_data/offline/chi_sim.traineddata /opt/share/tessdata/
```

（传到根目录的话，源路径改为 `/sys_data/chi_sim.traineddata`。放好之后，`deploy.sh` 检测到该文件存在就会跳过联网下载。）

5. **验证**（三个都有版本号输出才算就绪）：

```sh
python3 --version && jq --version && tesseract --version
```

之后跑 `deploy.sh` 就基本不碰网络了，所有依赖都已就位。

---

## 三、部署 penweb（上传 7 个文件 + 跑一次 deploy.sh）

程序文件已从 `deploy.sh` 中分离出来，发布包里**不再有内嵌代码**。部署时需要把 6 个程序文件上传到设备的 `/sys_data/penweb/`（固定目录），`deploy.sh` 本身位置不限：

- **需要上传的 6 个程序文件**：`server.py`、`screen.py`、`start.sh`、`stop.sh`、`ingest.sh`、`ocr.sh` → 全部传到 `/sys_data/penweb/`
- **另加 `deploy.sh`**（位置不限，习惯上也放在 `/sys_data/penweb/`）

`deploy.sh` 现在是**纯部署器**：只负责装依赖（jq / python3 / tesseract / 中文语言包，中文训练数据走 `curl` 下载，避开设备自带 `wget` 不支持 TLS 的问题）、配置开机自启、校验程序文件齐全，**不再内嵌任何代码**。

### 方法 A（推荐）：WebADB Files 上传

1. WebADB 切到 **Shell**，先建目录（Files 标签建不了文件夹）：

```sh
mkdir -p /sys_data/penweb
```

2. 切到 **Files** 标签，进入 `/sys_data/penweb/`，把 **7 个文件全部上传**：`server.py`、`screen.py`、`start.sh`、`stop.sh`、`ingest.sh`、`ocr.sh`、`deploy.sh`。
3. 切到 **Shell** 标签，执行：

```sh
sh /sys_data/penweb/deploy.sh
```

### 方法 B（备用）：分步粘贴

文件较多不适合全部粘贴，优先用方法 A；实在需要粘贴时，逐个文件用 `cat > 文件名 <<'EOF'` … `EOF` 写入 `/sys_data/penweb/` 后，再执行 `deploy.sh`。

### 看到完成提示

执行后会看到 `正在安装 jq` 或 `jq 已存在`，以及末尾的 `==== 部署完成 ====`。若提示缺少程序文件，说明还没传齐，补传后重跑即可。部署会自动配置**开机自启**。

---

## 四、启动 / 停止 / 访问

### 启动(必须执行以下命令才可启动)

```sh
sh /sys_data/penweb/start.sh
```

正常会打印：

```
penweb 已启动（Python 版 + 自动抓取扫描词）
浏览器打开: http://<词典笔IP>:8080/
```

### 浏览器访问

手机或电脑（与笔同一 WiFi）打开：

```
http://<你查到的IP>:8080/
```

例如 `http://192.168.1.100:8080/` 。注意是根路径 `/`。

### 停止

```sh
sh /sys_data/penweb/stop.sh
```

### 重启后失效怎么办（一般来说不会失效，所以这一栏目作者没有试过）

`/sys_data/penweb/` 下的文件会保留，但 opkg 的 `/opt` 绑定可能丢失。先重新绑定再启动：

```sh
mount --bind /sys_data/opt /opt
sh /sys_data/penweb/start.sh
```

### 完全卸载（回到部署前状态）

想彻底清掉 penweb 和所有第三方包（比如换一种方式重装、或出问题想推倒重来），按顺序执行：

```sh
# 1. 停止服务
sh /sys_data/penweb/stop.sh

# 2. 解除运行期挂载
umount /sys/power/state 2>/dev/null
umount /opt 2>/dev/null

# 3. 删除部署目录与全部第三方包（Entware、python3、jq、tesseract 一并清除）
rm -rf /sys_data/penweb
rm -rf /sys_data/opt
```

> ⚠️ 第 4 步执行前先 `cat /data/pre_run.sh` 看一眼内容：本机型实测该文件由 `deploy.sh`
> 创建（原厂无此文件），整删安全；若你的设备上该文件还包含其他内容，
> 只删除 `# >>> PENWEB_AUTOSTART >>>` 到 `# <<< PENWEB_AUTOSTART <<<` 之间的段落。

卸载后原厂功能不受影响；重新部署按本文流程从头再来即可。

---

## 五、功能使用详解

### 5.1 文字台

- **自动抓词**：在笔上扫描一个英文/中文词（建议扫完点一下收藏/保存，确保落盘），回到网页刷新，约 5 秒后词会自动出现。
- **查看 / 导出**：「导出 .txt」下载全部；「清空」重置。
- 也可以直接在 Shell 看抓取结果：`cat /sys_data/penweb/store.txt`

### 5.2 屏幕显示（screen.py 接管）

主页板块自上而下：


1. **设备状态**：可查看内存、CPU、负载、运行时长、温度、IP地址、屏幕亮度。
1. **天气**：配置城市后显示天气。（在轮换显示页面中配置城市）
2. **轮换显示**（独立卡片，在"天气"和"屏幕控制"之间）：勾选要轮换的内容（天气 / 时钟 / 日期），点「轮换显示页面 →」进入设置。
3. **屏幕控制**：可以显示全屏时钟，可以显示自定义文字内容，还可以设置文字滚动，滚动速度可调。可设置文字和背景颜色，以及亮度。
3. **闹钟**：可以设置闹钟。 
5. **倒计时 & 消息投送**：见下。

### 5.3 倒计时

- 在「倒计时 & 消息投送」板块点 **倒计时 →** 进入 `/timer`。
- 时长用 **时 / 分 / 秒** 三个输入框。
- 点「开始倒计时」→ 屏幕显示剩余时间。
- 归零后循环响"嘚儿"声；**点一下屏幕**即可关闭声音与显示（不杀后台，关闭后该倒计时槽位清空）。
- 在**轮换 / 时钟**模式下，点屏幕会**临时看一眼倒计时**，再点一下回到轮换。

### 5.4 消息投送

- 在「倒计时 & 消息投送」板块点 **消息投送 →** 进入 `/message`。
- 纯文字 + 显示时长（秒，默认 3，0 = 手动关闭）。
- 点「发送」→ 屏幕显示该文字，到点自动消失（0 则手动点屏关闭）。
- 注意，如果在息屏状态下投送文字，建议把时长适当延长5~10秒。

### 5.5 息屏（待机）时的响应

即使你主动熄屏、笔显示原生界面，penweb 仍在后台运行并响应事件：

- **闹钟到点**：自动点亮屏幕 + 显示闹钟画面 + **循环响铃**（点屏关闭）。
- **消息投送**：自动点亮屏幕 + 显示文字 + **只响一声**。
- **倒计时归零**：自动点亮屏幕 + 显示"时间到" + 响铃。

事件结束后屏幕**自动熄灭**回原生界面。强制防深度睡眠始终生效，息屏时设备依旧保持唤醒、能收投送并响铃；只有"无事件且你主动熄屏"时屏幕才保持黑屏。

### 5.6 声音测试

- 主页「屏幕控制」→「声音测试」→「测试声音」：笔播放合成音 `beep.wav`（"嘚儿"）。
- 目前**只有这一种声音**，面板无其他音效可选。

---

## 六、常见问题 / 排错

| 现象 | 处理 |
|---|---|
| `mkdir: can't create directory '/opt/...': Read-only file system` | `/opt` 没挂载成功：源目录没建，或 `mount --bind` 漏了目标参数。先 `mkdir -p /sys_data/opt`，再 `mount --bind /sys_data/opt /opt`，并用 `touch /opt/_test` 验证可写后再装 Entware |
| `mount: can't find ... in /etc/fstab` | `mount --bind` 只写了一个参数。它需要**两个**参数：`mount --bind 源 目标` |
| 看到 `Congratulations!` 但其实没装上 | Entware 安装脚本**不检查错误**，无论成败末尾都打印祝贺。以 `ls /opt/bin/opkg` 是否存在、`opkg update` 是否成功为准 |
| `Warning: Folder /opt exists!`（装 Entware 时） | 设备原厂 `/opt` 本身非空，此警告可忽略；仅当后续安装报错时，按提示清空 `/opt` 重试 |
| 启动报 `python3: not found` | Entware/依赖没装好。按上一条排查 `/opt` 挂载，或走 [2.5 离线安装](#25-离线安装彻底解决下载慢) 后重跑 `deploy.sh` |
| 网页打不开 | 确认 IP 正确、手机/电脑与笔同一 WiFi；`ps \| grep server.py` 看进程在不在；可在笔上自测 `wget -qO- http://127.0.0.1:8080/` 看是否返回 HTML |
| 词没自动出现 | Shell 里 `cat /sys_data/fatfs/answer_word/scanWordRecord.json` 看文件是否存在、有无新词；手动跑 `sh /sys_data/penweb/ingest.sh` 看报错（多半是 jq 缺） |
| `jq: not found` | 重跑 `sh /sys_data/penweb/deploy.sh` 装 jq；或 `/opt/bin/opkg install jq`；下载慢就走 [2.5 离线安装](#25-离线安装彻底解决下载慢) |
| 重启后失效 | `/sys_data/penweb/` 文件保留，但 `/opt` 绑定可能丢失，先 `mount --bind /sys_data/opt /opt` 再 `start.sh`；开机自启（`/data/pre_run.sh`）正常情况下会自动完成这一步 |

---

## 七、二次开发 & 编译校验

- 程序文件已独立（不再内嵌在 `deploy.sh` 里）：直接改发布包里的 `server.py` / `screen.py` / 各 `.sh`，然后把改动的文件重传到设备 `/sys_data/penweb/` 覆盖，重启服务即可：

```sh
sh /sys_data/penweb/stop.sh
sh /sys_data/penweb/start.sh
```

- `deploy.sh` 只负责装依赖和开机自启，改程序逻辑后**不需要重跑**（除非要新装依赖）。
- **校验 Python 能否编译**（强烈建议每次改完跑一遍，避免设备上语法错误）：

```sh
python3 test/check_compile.py
```

它会对发布包根目录的 `server.py` 和 `screen.py` 直接做 `py_compile` 校验。

- 自定义扫描源：编辑 `ingest.sh` 里的 `REC`（例如改用生词本 `word_book/scanWordCollection.json`）。

---

## 八、发布包文件清单

| 文件 | 说明 |
|---|---|
| `deploy.sh` | **部署器**（不内嵌代码）。装依赖（jq/python3/tesseract/中文语言包）、配置开机自启、校验程序文件齐全；位置不限 |
| `server.py` | 网页后端源码，**需上传到设备** `/sys_data/penweb/` |
| `screen.py` | 屏幕接管渲染器源码，**需上传到设备** |
| `start.sh` | 启动脚本源码，**需上传到设备** |
| `stop.sh` | 停止脚本源码，**需上传到设备** |
| `ingest.sh` | 自动抓词脚本源码，**需上传到设备** |
| `ocr.sh` | 自动 OCR 扫描原图脚本源码，**需上传到设备** |
| `deploy.verygood.sh` | 旧的自包含版 `deploy.sh` 备份（仍内嵌全部代码），仅作历史回退参考，**不要用于新部署** |
| `README.md` | 历史版本文档（功能描述偏旧，以本说明为准） |
| `test/check_compile.py` | Python 编译校验工具（直接校验 `server.py` / `screen.py`） |

> 部署时需上传 **6 个程序文件 + deploy.sh** 到 `/sys_data/penweb/`；改哪个文件重传哪个即可，不用重跑 deploy.sh。

---

## 九、最简部署速查

```sh
# 1) 笔上开 ADB（设置→关于→连点SN→密码123443211→开ADB），USB 连电脑，WebADB(app.webadb.com) 连上
# 2) Shell 装好 opkg：
mkdir -p /sys_data/opt
mount --bind /sys_data/opt /opt
touch /opt/_test && rm /opt/_test && echo "OK: /opt 可写"   # 必须输出 OK 再继续
wget -O - http://bin.entware.net/armv7sf-k3.2/installer/generic.sh | sh
export PATH=/opt/bin:/opt/sbin:$PATH
opkg update
# 3) 建目录，Files 上传 7 个文件（server.py / screen.py / start.sh / stop.sh / ingest.sh / ocr.sh / deploy.sh），然后：
mkdir -p /sys_data/penweb
sh /sys_data/penweb/deploy.sh
# 4) 启动 + 浏览器访问：
sh /sys_data/penweb/start.sh
#    打开 http://<IP>:8080/
```

---

## 二、文件说明

> 以下为本目录 `文件说明.md` 的完整内容。

# 文件说明（每个文件的作用）

> 配套 `安装与使用说明.md` 使用。本文把"发布包里的文件"和"部署后词典笔上生成的文件"分开说明，方便你对照。
> 部署动作：把发布包里 6 个程序文件 + `deploy.sh` 上传到设备 `/sys_data/penweb/`，然后执行 `sh /sys_data/penweb/deploy.sh`（装依赖 + 配置开机自启 + 校验文件齐全）。

---

## 一、发布包里的文件（电脑侧，随你保管）

| 文件 | 作用 |
|---|---|
| `deploy.sh` | **部署器**（不内嵌代码）。装依赖（jq/python3/tesseract/中英文语言包）、配置开机自启、校验程序文件齐全。 |
| `server.py` | **网页后端源码**（基于 `http.server`）。提供主页、各功能页（轮换/倒计时/消息/天气等）、接收手机/网页下发的计时与消息、驱动自动抓词的结果汇总、提供导出 `.txt`、管理屏幕显示状态（`overlay.json`/`timer_state.json`）。上传后直接在设备上运行。 |
| `screen.py` | **屏幕接管渲染器源码**。直接写 framebuffer（`FBIOPAN_DISPLAY`），按当前模式绘制天气/时钟/轮换/倒计时/消息；常驻主循环与触摸监听（点屏关闹钟/倒计时、轮换中点屏看一眼倒计时）。 |
| `start.sh` | **启动脚本源码**。内容：`pkill` 掉旧进程 → `python3 server.py &` 拉起网页服务 → `sh ingest.sh &` 拉起自动抓词 → 防深度睡眠处理 → 打印访问地址。 |
| `stop.sh` | **停止脚本源码**。`pkill` 掉 `server.py`/`ingest.sh`/`ocr.sh`/`screen.py`，解除防睡眠绑定。 |
| `ingest.sh` | **自动抓词脚本源码**。监听词典笔扫描记录 `scanWordRecord.json`，按时间**增量**提取新词去重写入 `store.txt`。 |
| `ocr.sh` | **自动 OCR 脚本源码**。监听扫描原图目录，用 tesseract 识别完整文字，以 `[OCR]` 标记写入 `store.txt`（绕开屏幕显示被截断的限制）。 |
| `deploy.verygood.sh` | 旧的自包含版 `deploy.sh` 备份（仍内嵌全部代码），**仅作回退参考**，不要用于新部署。 |
| `README.md` | 历史版本文档，功能描述偏旧（仍含图片投送/正计时）。以本发布包的 `安装与使用说明.md` 和 `文件说明.md` 为准。 |
| `test/check_compile.py` | 编译校验工具。对发布包根目录的 `server.py` / `screen.py` 直接做 `py_compile`，改完源码跑一遍可提前发现语法错误。用法：`python3 test/check_compile.py` |

> 上述前 7 个文件（6 个程序文件 + deploy.sh）都是**需要上传到设备的**；其余文件供查看、校验和回退使用。

---

## 二、设备端生成文件（部署后在 `/sys_data/penweb/` 下）

这些是部署时上传的程序文件（与发布包根目录同名文件一致）加上运行时生成的数据。

### 2.1 程序

| 文件 | 作用 |
|---|---|
| `server.py` | **网页后端**（基于 `http.server`）。提供主页、各功能页（轮换/倒计时/消息/天气等）、接收手机/网页下发的计时与消息、驱动自动抓词的结果汇总、提供导出 `.txt`、管理屏幕显示状态（`overlay.json`/`timer_state.json`）。 |
| `screen.py` | **屏幕接管渲染器**。直接写 framebuffer（`FBIOPAN_DISPLAY`），按当前模式绘制天气/时钟/轮换/倒计时/消息；常驻主循环与触摸监听（点屏关闹钟/倒计时、轮换中点屏看一眼倒计时）。 |
| `start.sh` / `stop.sh` / `ingest.sh` / `ocr.sh` | 设备启停 / 抓词 / OCR 脚本。 |

### 2.2 数据 / 状态文件（运行时生成）

| 文件 | 作用 |
|---|---|
| `store.txt` | **文字台主数据**：所有扫描词，按追加去重写入；网页读取它展示，也可导出为 `.txt`。 |
| `.lastscan` | 自动抓词的水位线状态：记录上次处理到的扫描时间戳，保证增量、不重复。 |
| `overlay.json` | **当前屏幕覆盖层**：倒计时/消息投送时写入，优先级高于轮换显示；屏显内容以此为准，关闭后清空。 |
| `timer_state.json` | **倒计时状态**：当前仅存 `{"down": 槽位|null}`（已删除正计时）。后台倒计时状态持久化，重启/轮换时仍可续显。 |
| `beep.wav` | 合成提示音（880Hz 短音，即"嘚儿"），屏幕测试声音 / 倒计时归零提示用。 |

### 2.3 配置 / 缓存文件（由网页或脚本读写）

| 文件 | 作用 |
|---|---|
| `screen_flip.conf` | 屏幕翻转开关（横/竖、上下翻转）。 |
| `screen_text.conf` | 文字显示模式下的文本内容。 |
| `screen_fg.conf` / `screen_bg.conf` | 屏幕前景色 / 背景色。 |
| `screen_bold.conf` | 文字加粗开关。 |
| `screen_scroll.conf` / `screen_scroll_speed.conf` | 文字滚动开关 / 滚动速度。 |
| `screen_voff.conf` | 垂直偏移（微调显示位置）。 |
| `brightness.conf` | 屏幕亮度。 |
| `rotate_items.conf` | 轮换显示勾选的内容项（天气/时钟等）。 |
| `rotate_dur.conf` | 轮换间隔时长。 |
| `rotate_sound.conf` / `rotate_sound_vol.conf` | 轮换切页音效开关 / 音量。 |
| `weather_city.conf` | 天气查询城市。 |
| `weather_cache.json` | 天气数据缓存（减少请求）。 |
| `alarm_active.conf` | 闹钟激活标志；存在时屏显闹钟、点屏关闭。 |
| `nowake.conf` | 防挂起开关：`0`/`off`/`false` 时允许设备正常睡眠（否则 `start.sh`/`server` 用 `mount --bind` 占位 `/sys/power/state` 阻止深度睡眠）。 |

---

## 三、一句话记忆

- **要部署／要带走**：带上整个发布包（至少 6 个程序文件 + `deploy.sh`）。
- **部署动作**：全部传到 `/sys_data/penweb/` → 跑一次 `deploy.sh`（装依赖 + 自启）。
- **要改逻辑**：改哪个文件重传哪个 → `stop.sh` + `start.sh` 重启服务，不用重跑 deploy.sh。
- **改完先校验**：`python3 test/check_compile.py`。
- **设备上跑的**：`server.py` + `screen.py` + 四个 `.sh`；数据在 `store.txt`／`overlay.json`／`timer_state.json`；配置是那一堆 `.conf`。

---

## 三、补充：关于 `ocr.sh`

`ocr.sh` 是发布包里的正式源码文件之一，与其他程序文件一同上传到 `/sys_data/penweb/`：

- **作用**：监听 `/sys_data/fatfs/answer_word/answerImgs/<毫秒时间戳>/` 下的新目录，对该目录内的标准 JPEG 跑 `tesseract`（`chi_sim+eng`），把识别出的完整文字以 `[OCR]` 标记写入 `store.txt`。
- **目的**：设备主程序用 LVGL 的 `lv_textarea_set_max_length` 截断屏幕显示的长文，但扫描**原图是完整保存**的。通过 OCR 原图，可在**不修改固件**的前提下拿到完整全文。
- **注意点**：同目录的 `image_cache/` 中也有扫描图，但为**自定义封装格式**（文件头 `04 40 01 0a`），tesseract 无法读取，因此 OCR 以 `answerImgs` 下的 JPEG 为准。
- **更详细的原理与排错**，参见上级目录 `penweb/README.md`（历史文档中 OCR 部分仍有效）。
- **部署**：`deploy.sh` 的依赖安装流程中包含 `tesseract` 及中英文语言包；语言包走 `curl` 下载，以避开设备自带 `wget` 不支持 TLS 的问题。

> OCR 识别结果可能包含受著作权保护或涉及隐私的内容，其采集与使用由操作者自行负责，详见文首免责声明第 5 条。该功能尚在测试阶段，如有Bug请见谅。

---

## 致谢与引用来源

**前置环境的准备方法（开启调试通道、安装 opkg / Entware）并非本人原创**，参考自以下公开资料。在此向原作者致谢：

| 来源 | 作者 | 贡献内容 | 链接 |
|---|---|---|---|
| PenUniverse Discussion #302《YDP031 词典笔 OS 2.8.0 一种全新的安装软件方法》 | **Fritillaly** | 在词典笔上安装 opkg / Entware 的思路（原帖机型为有道 YDP031，架构 `aarch64`） | https://github.com/orgs/PenUniverse/discussions/302 |
| 博客《作业帮 Linux 词典笔安装软件包》（2026/03/01） | **onimai0306** | 将上述思路适配到作业帮词典笔（`armv7`），并给出开启 ADB、挂载 `/opt` 的具体步骤 | https://onimai0306.wksite.cn/Blog/blogs/20260301.html |
| 线上帮助 | **RobinNotBad** | 调试过程中的协助 | — |

### 引用方式说明

- 上表资料均为**公开发表的技术分享**。本文档仅引用其中的**事实性操作步骤**（命令、路径、架构目录、调试通道的开启方式等），并已注明出处与原作者。
- 命令行、文件路径、参数属于功能性信息；但**原文的遣词与组织结构**仍归原作者所有。
- 若你是上述任一内容的作者，且不希望被本文档引用，请通过 issue 联系，核实后将**立即移除相关内容**。
- 本文档中由本人编写的部分（`deploy.sh`、`server.py`、`screen.py`、`ingest.sh`、`ocr.sh` 等），转载请注明出处。
- 如果你要转载本文档，请**一并保留上表的来源署名**，不要只摘抄步骤而删去出处。

### 给想适配其他机型的你

如果你的词典笔不是作业帮 S2 Pro，建议先去 [PenUniverse](https://github.com/PenUniverse) 社区看看有没有同型号的讨论，
再从本文挑选**适用部分**参考——前置环节（调试通道、包管理器）往往已有现成结论，
真正需要自己动手的通常是 framebuffer 参数、屏幕分辨率与扫描数据的落盘路径。

---

