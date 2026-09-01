# penweb 离线依赖包（Entware armv7sf-k3.2）

## 这是什么

`deploy.sh` 运行时需要从 Entware 官方源（国外服务器）在线安装 `python3`、`jq`、`tesseract`
等包，网络不好时经常中途失败（而且 Entware 安装脚本不检查错误，失败了也会打印
`Congratulations!`，非常坑）。本目录把这些包**全部提前下载好了**，在设备上离线安装，
全程不依赖设备网速。

## 目录内容

| 文件 | 说明 |
|---|---|
| `ipk/` | 全部 57 个 ipk（约 28.6 MB）：python3 3.13.9 / jq 1.8.1 / tesseract 5.4.1 / pillow 12.0.0 及全部依赖 |
| `install_offline.sh` | 设备端离线安装脚本（自动跳过已装包，可重复执行） |
| `chi_sim.traineddata` | tesseract 中文 OCR 训练数据（Entware 源里没有，取自 tesseract-ocr/tessdata_fast） |
| `download_list.txt` | 每个 ipk 的来源 URL 清单（供核对，或自行重新下载） |
| `gen_list.py` / `download_all.py` | 生成清单与批量下载的脚本（想更新版本时用） |

## 使用方法

**前提**：Entware 本体已按教程 2.3 节装好（`/opt/bin/opkg` 存在且 `opkg update` 可用）。
Entware 本体只有一个小脚本加一个 opkg 二进制，在线装很快，一般不需要离线。

1. **上传**：通过 WebADB 的 **Files** 标签，把 `ipk/` 文件夹、`install_offline.sh`、
   `chi_sim.traineddata` 上传到设备的 `/sys_data/offline/`（目录名可自定义）。
   文件较多，上传需要几分钟，属正常现象。

2. **安装**（WebADB 的 **Shell** 里执行）：

   ```sh
   mkdir -p /sys_data/opt
   mount --bind /sys_data/opt /opt
   export PATH=/opt/bin:/opt/sbin:$PATH
   sh /sys_data/offline/install_offline.sh
   ```

3. **装中文 OCR 数据**：

   ```sh
   mkdir -p /opt/share/tessdata
   cp /sys_data/offline/chi_sim.traineddata /opt/share/tessdata/
   ```

4. **验证**（三个都有版本号输出即就绪）：

   ```sh
   python3 --version && jq --version && tesseract --version
   ```

5. 之后正常执行 `sh /sys_data/deploy.sh` 即可，**不再依赖设备网速**
   （chi_sim 已手动放好，deploy.sh 检测到文件存在会跳过下载）。

## 适配其他架构

本包按 **armv7**（entware 目录 `armv7sf-k3.2`）下载。其他机型请修改
`gen_list.py` 顶部的 `ARCH` 变量后重新生成清单并下载（纯 Python 标准库，无需装依赖）。
