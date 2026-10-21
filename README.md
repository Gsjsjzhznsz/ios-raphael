# ios-raphael — iOS 16 on Redmi K20 Pro (raphael)

[English version below](#english)

把 Apple 的 XNU 内核 + iOS 16.7.16 用户态跑在红米 K20 Pro（代号 **raphael**，高通 SM8150 / 骁龙 855）上的移植实验。基于上游 [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet)（已在 sweet / Redmi Note 10 Pro 点亮 iOS 主屏），本项目为 raphael 做全套硬件适配：触摸、电池、显示、USB、八核。

> ⚠️ **警告 / Warning**
> 本项目为实验性质，操作会**彻底清空手机全部数据**，严禁在主力机上操作！
> This project is experimental. Flashing **erases all phone data**. Never use your daily driver.

## 📊 当前状态（2026-10-21, r24/t16）

| 子系统 | 状态 | 说明 |
|---|---|---|
| 引导链 | ✅ 实测可用 | shim → XNU → iOS 锁屏完整启动（`fastboot boot` 免落盘，重启即回安卓引导） |
| CPU | ✅ 8 核实测 | `8/8 CPUs initialized`（kryo485 匹配表 + PSCI 二次核拉起） |
| 显示 | ✅ 点亮 + 缩放修复（t14 引入，t16 起随整机验证） | 原生 1080×2340 面板；iOS 的 1125×2436 画面**整幅缩放**到面板（此前居中裁剪会切掉顶部两角的时间/电量）；`sweetscale=0` 可回退旧行为 |
| 触摸 | ✅ 实测可用 | GT9886 厂商级 bring-up：真寄存器图 + 784 字节面板配置下发（双供应商）+ doze 控制 |
| 电池 | ✅ 真实读数 | fg-gen4 硬件电量计：真 SOC/电压/电流（影子校验）+ 低电警告 + 时间剩余；**t14 新增充电状态 5 秒快轮询 + 插拔即日志**（APSD 充电器类型 / 输入限流 / 电源路径全落盘） |
| 亮度 / 息屏 | 🔧 t14 引入（待实测） | DSI DCS 亮度通道（`sweetfb_bright=` 初始亮度，iOS 滑条联动下一轮接入）+ **息屏立即全黑**（面板清屏 + DCS 0x28，替代旧的多步渐暗，`sweetfb_fade=1` 可回退）；t14/t15 都死在 USB 阶段，这些功能随 t16 首测 |
| USB | 🔧 t16 根因修复（待实测） | t15 实测：面包屑全过（VBUS/软复位/settle/事件缓冲）但**第一条端点命令（DEPCMD）总线级挂死**（环绕控制台取证定位，无超时打印 = 读永不清零）→ 根因：**ABL 留下的 PHY 处于挂起态**（GUSB2PHYCFG 0x00100240，bit6 SUSPHY=1），DWC31 上端点寄存器块被挂起 PHY 时钟门控，Linux `dwc3_hs_phy_setup()` 要求 phy init 前显式清 SUSPHY。t16：软复位前清 SUSPHY + DEPCMD 金丝雀探针。冻结后的“自动重启”是硬件侧路径（RPM/TZ/NoC）反应，挂死修掉即消失 |
| GPU | ❌ 无驱动 | 界面为 CPU 软渲染，滑动卡顿属正常 |
| Wi-Fi / 蓝牙 / 相机 / 音频 / 传感器 / 基带 | ❌ 未开始 | — |

<details>
<summary>📁 历史里程碑（t2–t13 归档）</summary>

- t2：首次进锁屏（1 核 + kryo485 二进制补丁） · t7：触摸修复系列起点 · t9：bootstrap 卡死根因（kryo470 失配）
- t10：八核回归 + 总线电平判读 · t11：TLMM SOUTH tile 根因定位（触摸供电）
- t12：触摸闭环（GT9886 配置下发，**实测可用**） · t13：fg-gen4 硬件电量计（SOC/电压/电流实测全真）
</details>

## 📥 下载（Releases）

| 文件 | 说明 |
|---|---|
| `raphael-t16-susphy-clean.img` | **当前首刷推荐（r24）**：USB SUSPHY 根因修复（清 GUSB2PHYCFG.SUSPHY + DEPCMD 金丝雀）+ t15 全部（SPMI 串行化/显示缩放/即时息屏/亮度通道/充电快轮询/USB 网卡） |
| `raphael-t16-susphy-debug.img` | r24 排障版：同 clean 但**屏幕控制台常开**（卡住拍最后几行即可定位） |
| `raphael-t7-touchfix-clean.img` | 回退/对照（SWEET 编译，已知可启动，触摸死） |
| `ios16-root.simg.part-00 ~ 05` + `CHECKSUMS.txt` | iOS 16.7.16 rootfs（16G HFS+ 稀疏镜像分卷，**rootfs 无需重刷**，与 t 系列内核通用） |

> 项目内核迭代极快，**每次刷机请务必下载最新版本**。
> 历史镜像哈希（回退参考）：

```
t7-clean:  91abcc1be3bce986606500a8003576d1c01fc31ee9348af9659e75c5583559fe （回退用，已知可启动）
t12-clean: 3725736f0773ede73b59a35d1cabddc92decbc58aaa37f8a375fa09d46459c6b （触摸闭环）
t13-clean: 3d31006ca3c318779e5a0c21e4d6dee2ed65c7a1125b50acc26c2c8f8aa8c23f
t14-clean: 3374ac69efb17155de6a61792e5753053c25669317bb5464aa5fa284e8da3a3c （USB 挂死，勿刷）
t16-clean: 30a978e156594979e1e03535a54aad6771ff6fac6ec20aa10ce416913fe4e721
t16-debug: 3584be8e0f744b3eba12b335a8170626e88fbb1b29235490b96a2f7e5dd59129
```

---

# 使用方法

## 〇、 新手如何从 GitHub 下载文件？

项目内核迭代极快，每次刷机请务必下载最新版本。

1. 打开项目发布页：https://github.com/Gsjsjzhznsz/ios-raphael/releases
2. 找到最上方带有 **Latest** 标签的最新版本。
3. 点击底部的 **Assets** 展开文件列表。
4. 你需要下载：
   - 所有的 `ios16-root.simg.part-xx` 分卷文件（**必须全部下载**）。
   - `CHECKSUMS.txt`（校验文件）。
   - 最新的 **clean** 镜像（用于启动，注意**不要下错成 debug 版**）。

> 注：国内访问 GitHub 慢的话，请使用 Watt Toolkit 等加速工具或科学上网。

---

## 一、 合并与校验镜像

将下载的所有 `ios16-root.simg.part-*` 分卷放在电脑同一目录，执行合并：

```bash
# Mac/Linux:
cat ios16-root.simg.part-* > ios16-root.simg
# Windows:
copy /b ios16-root.simg.part-* ios16-root.simg
```

校验生成的 `ios16-root.simg` 的 SHA256，**必须与 `CHECKSUMS.txt` 完全一致，否则绝不能刷入**。

```bash
# Mac/Linux:
sha256sum ios16-root.simg
# Windows:
certutil -hashfile ios16-root.simg SHA256
```

---

## 二、 备份关键分区（保命必做）

1. 手机进 Fastboot：关机，按住 **电源 + 音量下**。
2. 电脑执行 `fastboot boot 你的recovery.img` 进临时 Recovery。
3. 在电脑本地新建 `backup` 文件夹，执行以下命令备份 8 个底包分区：

```bash
for p in persist modemst1 modemst2 fsg fsc boot dtbo vbmeta; do
    adb exec-out cat /dev/block/by-name/$p > backup/$p.img
done
```

> - 请将 `backup` 文件夹妥善保存到电脑以外的地方，**一旦丢失可能无法救砖**。
> - Windows 用户请在 **CMD**（勿用 PowerShell，`>` 会按文本编码重写、损坏二进制流）或 WSL 下执行。

---

## 三、 刷入 iOS 系统

1. 执行 `adb reboot bootloader` 回到 Fastboot 模式。
2. 执行刷写（约 10-20 分钟，中途断电或断线会报错，重新连好重刷即可，不会变砖）：

```bash
fastboot -S 512M flash userdata ios16-root.simg
```

> 刷完后小米 Fastboot 常假死黑屏，长按 **电源 + 音量下** 强行重进 Fastboot 即可，数据不丢。

---

## 四、 引导启动

在 Fastboot 模式下，执行引导（请替换为你刚在 Releases 下载的最新 clean 镜像的实际文件名）：

```bash
fastboot boot 最新版的-clean镜像.img
```

- 注意：引导后需等待 **4-8 分钟**，屏幕会出现 iOS 锁屏界面。只要机身微热，绝对不要提前强制重启。
- 由于无 GPU 驱动，界面基于 CPU 软渲染，滑动会卡顿（正常现象）。触摸已适配（如个别批次失灵请回报日志）。
- t16 预期：屏幕依次打出 `SUSPHY cleared` → `DEPCMD(0) canary` → `ep0 setup TRB armed` → `running (DSTS...)`；息屏应**立即全黑**；顶部时间/电量完整显示；主机（Termux 手机）枚举出 USB 网卡后 `ping 192.168.7.2`（`tools/sweet-usbnet.sh` 实时看日志）。**刷前先彻底关机一次**（长按电源 10 秒以上再进 fastboot）——崩溃后 PMIC 坏状态会跨热重启保留，冷启动清除。若再冻结：记录定格行 + 掐表“定格→自动重启”秒数（判读树见 FLASH-T16）。
- **USB 实时日志（新）**：电脑端 `sudo tools/sweet-usbnet.sh`（Linux/Mac），脚本会配置 192.168.7.1 并用 `nc -ukl 5140` 接收实时内核日志——以后排查问题不用再进 Recovery。

---

## 🚑 附：触摸失灵/卡死如何提日志？

若无法滑动解锁或卡死，请引导进 Recovery 提取日志发给开发者：

```bash
fastboot boot 你的recovery.img
# 等待进 Recovery 后执行：
adb shell -T "tail -c 4194304 /dev/block/by-name/userdata > /tmp/sweet-log.bin"
adb pull /tmp/sweet-log.bin
```

> 存放路径必须是 `/tmp`（内存盘）——`/sdcard` 现在是 HFS+，Recovery 挂不上。

## 🔙 附：如何退回安卓？

本项目仅覆盖了 `userdata`，未改动底层分区。如需回退，直接使用小米官方 **MiFlash** 工具配合 K20 Pro 官方线刷包（TGZ 格式）进行线刷恢复即可。

---

# English

**ios-raphael** brings Apple's XNU kernel + iOS 16.7.16 userspace to the Redmi K20 Pro (codename **raphael**, Qualcomm SM8150 / Snapdragon 855). It is a port of [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet), adding full hardware bring-up for raphael: touch, battery, display, USB and all 8 CPU cores.

> ⚠️ Experimental. Flashing **erases all data** — never on a daily driver. The project only overwrites `userdata`; you can return to Android anytime with MiFlash + the official K20 Pro fastboot package.

## Status (2026-10-21, r24/t16)

- ✅ Boot chain proven on device: shim → XNU → iOS lock screen (`fastboot boot`, nothing permanent)
- ✅ All 8 cores (`8/8 CPUs initialized`)
- ✅ Display: native 1080×2340 panel; the 1125×2436 iPhone-X frame is **scaled** to the panel instead of center-cropped (t14; first real test in t16 — t14/t15 both died in USB init before userspace)
- ✅ Touch (GT9886 vendor-grade bring-up, confirmed working)
- ✅ Battery: real fg-gen4 hardware gauge (SOC/voltage/current, shadow-verified) + 5-second charger-input polling with APSD/ICL/power-path transition logging
- 🔧 Brightness DCS channel (`sweetfb_bright=`) and **instant screen-off** (panel clear + DCS 0x28; `sweetfb_fade=1` restores the old fade) — landed in t14; t14/t15 both died in USB init, first real test in t16
- 🔧 USB (t16 root-cause fix, pending test): t15 passed every breadcrumb but **wedged on the first endpoint command** (wrap-console forensics; a bus-level wedge, no timeout print). Root cause: **ABL leaves the PHY suspended** (GUSB2PHYCFG 0x00100240, bit 6 SUSPHY=1); on DWC_usb31 the endpoint register block is clock-gated while the PHY is suspended, and Linux `dwc3_hs_phy_setup()` explicitly clears SUSPHY before phy init. t16 clears SUSPHY before the soft reset and adds a DEPCMD(0) canary read. The post-freeze "auto-reboot" is a hardware-side path (RPM/TZ/NoC) reacting to the wedged kernel
- 🔧 SPMI: all observer commands (keys/census/battery) now go through one global gate, Linux-style; GPIO census is opt-in (`sweetcensus=1`)
- ❌ No GPU driver (CPU software rendering, UI is slow), no Wi-Fi/BT/camera/audio/modem yet

## Downloads (Releases)

| File | Purpose |
|---|---|
| `raphael-t16-susphy-clean.img` | **Recommended (r24)**: USB SUSPHY root-cause fix + all t15/t14 features (SPMI gate, display scaling, instant off, brightness, charger polling, USB network) |
| `raphael-t16-susphy-debug.img` | Same, with the on-screen console always on (photograph the last lines if it hangs) |
| `raphael-t7-touchfix-clean.img` | Known-good fallback |
| `ios16-root.simg.part-00~05` + `CHECKSUMS.txt` | iOS 16.7.16 rootfs (16G HFS+ sparse image; no need to re-flash when kernels update) |

## Flashing Guide

0. **Download** from the [releases page](https://github.com/Gsjsjzhznsz/ios-raphael/releases) (pick the **Latest** release): every `ios16-root.simg.part-xx` volume, `CHECKSUMS.txt`, and the newest **clean** image.
1. **Merge & verify**: `cat ios16-root.simg.part-* > ios16-root.simg` (Windows: `copy /b`), then check the SHA256 against `CHECKSUMS.txt`. Never flash on mismatch.
2. **Back up 8 critical partitions** (in a temporary recovery via `fastboot boot recovery.img`):
   ```bash
   for p in persist modemst1 modemst2 fsg fsc boot dtbo vbmeta; do
       adb exec-out cat /dev/block/by-name/$p > backup/$p.img
   done
   ```
   Keep these somewhere safe — they can unbrick the phone.
3. **Flash the rootfs** (~10–20 min): `fastboot -S 512M flash userdata ios16-root.simg`. If Xiaomi fastboot appears frozen afterwards, force-restart into fastboot with **Power + Vol-**; the data is intact.
4. **Boot**: `fastboot boot raphael-t16-susphy-clean.img`, wait **4–8 minutes** for the lock screen. The body staying warm is normal; do not force-reboot early. Touch works; expect software-rendering lag. **Power the phone fully off before fastboot** after any crash/abnormal boot — PMIC state survives warm reboots.

## Troubleshooting

- **Pull the log** (touch dead / hung): boot a recovery, then
  `adb shell -T "tail -c 4194304 /dev/block/by-name/userdata > /tmp/sweet-log.bin" && adb pull /tmp/sweet-log.bin`
- **Live log over USB (new)**: `sudo tools/sweet-usbnet.sh` on the PC shows the kernel log in real time.
- **Return to Android**: MiFlash + official K20 Pro fastboot package. Only `userdata` was touched.

## Build & Tools

- `.github/workflows/xnu.yml` — kernel CI (board-macro and patch-skip red gates)
- `.github/workflows/build-rootfs.yml` — one-shot iOS rootfs build + release
- `tools/build-raphael.sh` / `repack-boot-v2.py` / `mkadt.py` / `mkpayload.py` — full packaging chain
- `tools/sweet-usbnet.sh` — host side of the USB Ethernet gadget + live log
- Patch series 0001–0098: early console, persistent log ring, USB bring-up, raphael display/touch/battery (0090 kryo485 match, 0093 TLMM-south, 0094 GT9886 config download, 0096 fg-gen4 gauge, 0097 charger input polling, 0098 display scaling + brightness + instant off)

## Credits

- [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) — upstream project and rootfs pipeline
- [MakrSas/ios-topaz](https://github.com/MakrSas/ios-topaz) — sibling port (Redmi Note 12 4G) used for cross-checking
- The XNU kernel and iOS userspace are © Apple Inc. This project is for research only.

> 判读树与取证命令：Release `raphael-touch-r24` 内 `FLASH-T16.md`（历史判读树 FLASH-T6~T15 保留在 docs/）。
