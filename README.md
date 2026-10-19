# iOS 16 · Redmi K20 Pro（raphael / 骁龙 855）

**Apple XNU 内核 + iOS 16 用户空间，运行在 Redmi K20 Pro 上。**

[中文](#中文) · [English](#english)

---

## 中文

### 这是什么

本项目把 Apple 开源的 XNU 内核（xnu-8796，iOS 16 同代）移植到小米 Redmi K20 Pro（代号 `raphael`，高通 SM8150 / 骁龙 855），其上运行 **iPhone X 的原版 iOS 16.7.16（20H392）用户空间**：launchd、系统守护进程、backboardd、SpringBoard 与系统应用均为原装文件。

启动方式为 `fastboot boot` 临时引导：解锁引导加载器后，从内存引导打包好的 shim 镜像 → XNU → 自研 UFS 驱动 → `userdata` 分区内日志式 HFS+ 根文件系统 → iOS。**不向 boot 分区写入任何内容。**

> 实验性项目，不是可日常使用的手机系统。Apple 的安全模型（AMFI 代码签名、沙盒）处于宽松模式，AppleKeyStore 为桩实现。安装会**清空 Android 用户数据**（占用 userdata 分区）。引导加载器、recovery、modem、persist 分区永不触碰。

### 当前状态（2026-10-19）

- 移植适配完成：机器配置、按键、触摸、显示、USB 日志通道（补丁 0082-0087，全部由 `ARM64_BOARD_CONFIG_RAPHAEL` 门控）
- 内核在 GitHub Actions（macOS runner）编译链接通过；shim 亦可 CI 构建
- 首测镜像 `shim-boot-raphael.img` 已打包
- **尚未在真机上启动过** —— 下一步就是真机 `fastboot boot` 冒烟测试

| 子系统 | 状态 |
| --- | --- |
| 启动链 | ABL → shim（裸金属 C/汇编）→ XNU + 生成的 Apple Device Tree |
| CPU | 8 核（1×Kryo 485 Prime 2.84G + 3×Gold 2.42G + 4×Silver 1.80G），PSCI 启动副核，16K 页，GICv3 |
| 内存 | 上 DDR bank 约 3.95 GiB（`--highmem`，位于高通 carve-out 之上）；6/8 GB 机型均适用 |
| 存储 | 自研 UFS 主机驱动；iOS 根 = userdata 内日志式 HFS+，可读写 |
| 显示 | 1080×2340 三星 AMOLED；内核控制台直接画进 ABL 留下的 splash framebuffer；以 iPhone X 1125×2436 呈现给 iOS |
| 触摸 | Goodix GT9889 @I2C 0x5d（主路径，GENI SE19）；ST FingerTipS 0x49 二供只读探测（补丁 0086） |
| 按键 | 电源 / 音量减（PM8150 PON 块）；音量加 = PM8150 GPIO6（mainline DTS 实锤，补丁 0085） |
| USB | DWC3 设备模式 + CDC-ECM 网卡 `ue0` + UDP 内核日志直播（补丁 0087） |
| iOS 用户空间 | iPhone X iOS 16.7.16 rootfs（构建流程见下） |

### 启动链

```
ABL（原装小米 bootloader，已解锁）
  -> fastboot boot shim-boot-raphael.img      （临时引导；不写 boot 分区）
     -> shim：自建 MMU，读取 live FDT，从 ramdisk 载入 payload
        -> XNU Mach-O + 生成的 Apple Device Tree (ADT) + boot-args
           -> XNU -> UFS 驱动 -> userdata 内 HFS+ 根
              -> dyld + shared cache -> launchd -> 守护进程 -> backboardd + SpringBoard
```

无串口（该板的调试 UART 被复用为 SPI）。三条日志通道：

1. **framebuffer 内核控制台** —— ABL 留下的 `0x9c000000` splash buffer，开机即见；
2. **持久日志环** —— userdata 末尾 4 MiB；临时引导 OrangeFox 后用 `tools/sweet-log-pull.sh` 拉取（panic 后必用此通道）；
3. **USB 直播日志**（补丁 0087）—— 加 `sweetusb=2` 后手机枚举为 CDC-ECM 网卡（手机 192.168.7.2/24，PC .1），内核 printf 每 100 ms 以 UDP 推流到 `192.168.7.1:5140`；PC 端运行 `tools/sweet-usbnet.sh`（自动等接口、配 IP）并用 `tools/sweet-log.py` 查看。

### 真机测试指南

前置：Redmi K20 Pro（任意版本，**已解锁 bootloader**）、Linux PC（`adb`/`fastboot`、`python3`）、GitHub 账号（fork 本仓库以获得免费的 macOS CI 分钟数）。

**0. 先备份。** 临时引导 OrangeFox（或任意带 adb root 的 recovery），至少拉取 `persist`、`modemst1`、`modemst2`、`fsg`、`fsc`、`boot`、`dtbo`、`vbmeta`。shim 需要你原厂 boot.img 里的 SoC DTB：

```sh
python3 tools/unpack_bootv2.py backup/boot.img dtb/boot_unpacked   # -> dtb/boot_unpacked/dtb
```

**1. 构建 iOS 根镜像。** 从 Apple 下载 iPhone X（iPhone10,3）iOS 16.7.16（20H392）IPSW。Linux 上需 `apfs-fuse`、`hfsprogs` 与 sudo：

```sh
# OS / SystemOS / AppOS 磁盘镜像（名字见 BuildManifest.plist）
tools/mkiosroot.sh OS.dmg SystemOS.dmg AppOS.dmg ios16-root.img 16G
sudo fsck.hfsplus -fy ios16-root.img
sudo mount -t hfsplus -o loop,force ios16-root.img /mnt/iosroot
sudo python3 tools/sweet-root-tweaks.py /mnt/iosroot
sudo umount /mnt/iosroot
img2simg ios16-root.img ios16-root.simg
```

`mkiosroot.sh` 把 OS 卷与两个 cryptex 合并进一个区分大小写的日志式 HFS+ 卷；`sweet-root-tweaks.py` 应用 bring-up 修改（跳过 Setup、播种激活态、移除基线带守护进程、关闭杀死慢应用的看门狗等），脚本头部有逐项说明。

**2. 构建内核（CI）与引导镜像。** 内核在 GitHub Actions 的 macOS runner 上构建：

```sh
gh workflow run xnu.yml -R YOU/ios-sweet -f machine_config=RAPHAEL -f kernel_config=DEVELOPMENT
gh run download RUN_ID -R YOU/ios-sweet -n xnu-kernel -D xnu/out
# -> xnu/out/kernel.development.raphael
```

打包（纯 python；shim 可用 CI 产物 `raphael-shim/Image` 或本地 `cd shim && RAPHAEL=1 ./build.sh` 构建）：

```sh
python3 tools/mkadt.py shim/out/sweet-raphael.adt --raphael --highmem
python3 tools/mkpayload.py xnu/out/kernel.development.raphael \
    shim/out/sweet-raphael.adt shim/out/payload-raphael.bin \
    --cmdline 'debug=0xc serial=3 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30'

python3 tools/package-raphael.py shim-dir payload-raphael.bin backup/boot.img shim-boot-raphael.img
```

`package-raphael.py` 从你的原厂 boot.img 提取 SM8150 v2 SoC DTB，按原厂 layout（header v1、DTB 追加在内核 blob 尾部）打包。**首次测试建议 `cpus=1`**；要隔离驱动可加 `sweettouch=0 sweetkeys=0`。

**3. 刷入 root 并启动：**

```sh
fastboot -S 512M flash userdata ios16-root.simg    # ~7 分钟，勿拔线
# 小米 fastboot 大写入后常假死：电源键+音量减 重新进入 fastboot
fastboot boot shim-boot-raphael.img                # 临时引导，不动 boot 分区
```

**4. 读日志：**

```sh
fastboot boot recovery/recovery.img                # OrangeFox 临时引导
tools/sweet-log-pull.sh logs/raphael-1.txt         # userdata 末尾 4 MiB 日志环
adb reboot bootloader
```

日志含带 backtrace 的崩溃报告（`CRASH name ...`）、backboardd/SpringBoard 的 IOKit trace、各驱动 `SWEET ...` 行；`tools/sweet-crash.py` 可对 shared cache 符号化。

### boot-args 速查

| 参数 | 作用 |
| --- | --- |
| `rd=ufsroot0 ufsrw=1 rootrw=1` | 根在 userdata 分区，可写 |
| `cpus=8`（首测建议 `cpus=1`） | PSCI 启动副核 |
| `sweetusb=2` | 启动 DWC3 设备控制器 + CDC-ECM + UDP 日志（默认 `sweetusb=1` 只报时钟/GDSC 状态） |
| `launchd_unsecure_cache=1` | launchd 接受无 AMFI 的 job cache |
| `wdt=-1 wdt_test=no_user_checkin` | 关硬件看门狗 |
| `sweetfb_noconsole=1` | GUI 出现后停止屏上叠印内核文本（日志仍进持久环，panic 仍会画） |
| `sweetfb_hz=30` | CPU 拷贝帧率 |
| `sweettouch=0` / `sweetkeys=0` | 禁用触摸 / 按键驱动（隔离用） |

### 内核补丁（raphael 部分）

| 补丁 | 内容 |
| --- | --- |
| 0082 | 机器配置注册：SM8150 布局 + 复用通用驱动集 |
| 0083 | 输入：GT9889 触摸协议 + SE19 时钟/引脚 + TLMM 供电 + PON 按键 |
| 0084 | 显示：1080×2340 早期控制台 / panic 行 / SweetHID 缩放 |
| 0085 | 音量加 = PM8150 GPIO6（mainline DTS 实锤）+ PMIC GPIO 一次性普查日志 |
| 0086 | 触摸二供更正为 ST FingerTipS：0x49 只读探测 + 事件 FIFO 泵；IRQ 引脚修正（GPIO122） |
| 0087 | USB：DWC3/qscratch/QUSB2/GDSC 地址按 SM8150 核对（仅 2 处 GCC 分支迁移 + phy ref 更正），ue0/ECM/UDP 全链路激活 |

0001-0081 为通用基础补丁系列（工具链兼容、UFS 驱动、HFS+、HID 事件服务、USB 设备模式、SMP/PSCI 等），CI 按序应用。寄存器级证据、GT9889/ST FTS 协议细节与 bring-up 顺序见 [NOTES.md](NOTES.md)。

### 硬件事实（SM8150 / raphael）

- GICD/GICR `0x17a00000`/`0x17a60000`（GICR stride 0x20000）；定时器 PPI：物理 INTID 18 / 虚拟 INTID 19，19.2 MHz
- UFS 主机 `ufshc@1d84000`（ABL 留下已初始化）；SPMI arbiter `0xc440000`；RPMh apps RSC `0x18220000`
- ABL framebuffer `0x9c000000`（cont_splash 0x2400000）；imem restart_reason `0x146bf65c`
- 触摸 GENI SE19 @ `0xc88000`（wrap2 S2）；TLMM 单块 `0x03000000`
- 触摸供电：纯 TLMM GPIO——vdd 3v3 = GPIO98、avdd 1v8 = GPIO100（无需 RPMh LDO vote）
- 触摸引脚：reset GPIO54 / IRQ GPIO122 / SDA-SCL GPIO57-58（qup19 func 2）
- 触摸 IC：Goodix GT9889 @0x5d（MIUI DTB 与 mainline DTS 一致）；内核源码另带 ST FingerTipS `fts_521`（0x49，二供可能性）
- CPU 时钟：Prime 2.8416G / Gold 2.4192G / Silver 1.8048G；ARMv8.2、无 PAC、16K granule、crypto 扩展
- 原厂 boot.img（V12.5.6.0.RFKCNXM）：header v1，内核 blob 内 4 个 SoC DTB（sm8150/sm8150p × v1/v2），K20 Pro = SM8150 v2；cmdline 含 `androidboot.usbcontroller=a600000.dwc3`

### 参考资源（K20 Pro 刷机生态）

K20 Pro 是刷机/逆向资源最丰富的骁龙 855 机型之一，本项目大量受益于：

- **Mainline Linux DTS**：`sm8150-xiaomi-raphael.dts` —— 补丁系列 [PATCH v2 0/3] Add Xiaomi Redmi K20 Pro (Raphael)（patchew.org/linux/20251104221657.51580-1-pc1598@mainlining.org）：音量加键（pm8150_gpios 6）、goodix@5d on i2c19、面板 `samsung,ams639rq08`
- **howtocuddle/xiaomi_raphael**：6.18 mainline 状态跟踪（显示 ams639rq08 / 触摸 / 相机）
- **postmarketOS**：wiki 页 xiaomi-raphael，包 `linux-xiaomi-raphael`
- **原厂内核源码**：github.com/ZakoClubROM/android_kernel_xiaomi_raphael（lineage-19.0 分支：`goodix_driver_gt9886`、`fts_521` 驱动源码、`raphael-*` dtsi —— 触摸/面板/按键的 ground truth）
- LineageOS raphael 设备树；XDA raphael 内核/recovery 版块；OrangeFox/TWRP 官方支持（recovery 拉日志用）

### 仓库布局

| 路径 | 内容 |
| --- | --- |
| `shim/` | 裸金属引导 shim（C + 汇编），打成 Android boot.img |
| `xnu/patches/` | XNU 补丁系列（CI 按序应用）+ libpthread/HFS/BearSSL staging 脚本 |
| `.github/workflows/xnu.yml` | 内核 CI（machine_config=RAPHAEL） |
| `.github/workflows/raphael.yml` | shim CI 构建 |
| `tools/mkadt.py --raphael` | 从 SM8150 MMIO 布局生成 Apple Device Tree |
| `tools/mkpayload.py` | 内核 + ADT + boot-args → shim payload |
| `tools/package-raphael.py` | 原厂 boot.img DTB + payload → shim-boot-raphael.img |
| `tools/mkiosroot.sh` + `sweet-root-tweaks.py` | IPSW → HFS+ iOS root |
| `tools/sweet-log-pull.sh` / `sweet-log.py` / `sweet-usbnet.sh` | 持久日志拉取 / UDP 直播日志 |
| `tools/qemu-sweet.py` | QEMU virt 冒烟测试（framebuffer 文本解码） |
| `tools/sweet-crash.py` / `xnu-cc.py` / `remotezip.py` / `unpack_bootv2.py` | 崩溃符号化 / 本地单文件编译检查 / IPSW 按需提取 / boot 解包 |
| `NOTES.md` | raphael 工程笔记：寄存器级证据、协议、bring-up 顺序 |
| `docs/WORKLOG.md` | 工作日志（每完成一步即更新并推送） |

不在 git 里：分区备份、live DT、recovery 镜像、Apple 固件与 root 镜像、下载/生成的构建树（含设备序列号与校准数据，或 Apple 版权文件）。

---

## English

### What is this

This project ports Apple's open-source XNU kernel (xnu-8796, the iOS 16 generation) to the **Redmi K20 Pro / Mi 9T Pro** (`raphael`, Qualcomm SM8150 / Snapdragon 855). On top of it runs the **unmodified iOS 16.7.16 (20H392) userland of the iPhone X**: launchd, the system daemons, backboardd, SpringBoard and the stock apps.

It boots via `fastboot boot`: with an unlocked bootloader, our shim is loaded from RAM → XNU → own UFS host driver → journaled HFS+ root inside the `userdata` partition → iOS. **Nothing is ever flashed to the boot partition.**

> Experimental bring-up, not a usable phone OS. Apple's security model (AMFI, sandbox) is permissive and AppleKeyStore is a stub. Installing **erases Android's user data** (it occupies `userdata`). Bootloaders, recovery, modem and persist partitions are never touched.

### Status (2026-10-19)

- Adaptation complete: machine config, keys, touch, display and the USB log path (patches 0082-0087, all guarded by `ARM64_BOARD_CONFIG_RAPHAEL`).
- The kernel compiles in CI (GitHub Actions macOS runner); the shim builds in CI too.
- A first test image `shim-boot-raphael.img` is packaged.
- **It has not yet been booted on hardware** — the next step is a real-device `fastboot boot` smoke test.

| Area | State |
| --- | --- |
| Boot chain | ABL → bare-metal shim (C + asm) → XNU + generated Apple Device Tree |
| CPU | 8 cores (1×Kryo 485 Prime 2.84G + 3×Gold 2.42G + 4×Silver 1.80G) via PSCI, 16K pages, GICv3 |
| Memory | ~3.95 GiB of the upper DDR bank (`--highmem`, above Qualcomm's carve-outs); works on 6/8 GB units |
| Storage | Own UFS host driver; iOS root = journaled HFS+ in `userdata`, read/write |
| Display | 1080×2340 Samsung AMOLED; kernel console in the ABL splash framebuffer; presented to iOS as an iPhone X 1125×2436 panel |
| Touch | Goodix GT9889 @I2C 0x5d (primary, GENI SE19); ST FingerTipS 0x49 second-source read-only probe (patch 0086) |
| Buttons | Power / volume-down (PM8150 PON); volume-up = PM8150 GPIO6 (settled by the mainline DTS, patch 0085) |
| USB | DWC3 device mode + CDC-ECM ethernet `ue0` + live UDP kernel log (patch 0087) |
| iOS userland | iPhone X iOS 16.7.16 rootfs (build steps below) |

### Boot chain

```
ABL (stock Xiaomi bootloader, unlocked)
  -> fastboot boot shim-boot-raphael.img      (temporary; nothing is flashed to boot)
     -> shim: own MMU setup, reads the live FDT, loads the payload from the ramdisk
        -> XNU Mach-O + generated Apple Device Tree (ADT) + boot-args
           -> XNU -> UFS driver -> HFS+ root in userdata
              -> dyld + shared cache -> launchd -> daemons -> backboardd + SpringBoard
```

No serial port (the debug UART is wired as SPI on this board). Three log channels:

1. **Framebuffer kernel console** — the ABL splash buffer at `0x9c000000`, visible immediately;
2. **Persistent log ring** — 4 MiB at the end of `userdata`; pull with `tools/sweet-log-pull.sh` after temporarily booting OrangeFox (mandatory after a panic);
3. **Live USB log** (patch 0087) — with `sweetusb=2` the phone enumerates as a CDC-ECM ethernet adapter (phone 192.168.7.2/24, PC .1) and streams kernel printf over UDP to `192.168.7.1:5140` every 100 ms; run `tools/sweet-usbnet.sh` on the PC and watch with `tools/sweet-log.py`.

### Testing on the device

Prerequisites: a Redmi K20 Pro (any variant, **unlocked bootloader**), a Linux PC (`adb`/`fastboot`, `python3`), a GitHub account (fork this repo for free macOS CI minutes).

**0. Back up first.** Temporarily boot OrangeFox and pull at least `persist`, `modemst1`, `modemst2`, `fsg`, `fsc`, `boot`, `dtbo`, `vbmeta`. The shim needs the SoC DTB from your stock boot.img:

```sh
python3 tools/unpack_bootv2.py backup/boot.img dtb/boot_unpacked   # -> dtb/boot_unpacked/dtb
```

**1. Build the iOS root image.** Download the iPhone X (iPhone10,3) iOS 16.7.16 (20H392) IPSW from Apple. On Linux you need `apfs-fuse`, `hfsprogs` and sudo:

```sh
tools/mkiosroot.sh OS.dmg SystemOS.dmg AppOS.dmg ios16-root.img 16G
sudo fsck.hfsplus -fy ios16-root.img
sudo mount -t hfsplus -o loop,force ios16-root.img /mnt/iosroot
sudo python3 tools/sweet-root-tweaks.py /mnt/iosroot
sudo umount /mnt/iosroot
img2simg ios16-root.img ios16-root.simg
```

`mkiosroot.sh` merges the OS volume and both cryptexes into one case-sensitive journaled HFS+ volume; `sweet-root-tweaks.py` applies the bring-up changes (Setup skip, activation seeding, baseband daemon removal, watchdog disables) — its header explains each change.

**2. Build the kernel (CI) and the boot image.** The kernel builds on GitHub's macOS runners:

```sh
gh workflow run xnu.yml -R YOU/ios-sweet -f machine_config=RAPHAEL -f kernel_config=DEVELOPMENT
gh run download RUN_ID -R YOU/ios-sweet -n xnu-kernel -D xnu/out
# -> xnu/out/kernel.development.raphael
```

Packaging (python only; the shim comes from the CI artifact `raphael-shim/Image`, or build locally with `cd shim && RAPHAEL=1 ./build.sh`):

```sh
python3 tools/mkadt.py shim/out/sweet-raphael.adt --raphael --highmem
python3 tools/mkpayload.py xnu/out/kernel.development.raphael \
    shim/out/sweet-raphael.adt shim/out/payload-raphael.bin \
    --cmdline 'debug=0xc serial=3 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30'

python3 tools/package-raphael.py shim-dir payload-raphael.bin backup/boot.img shim-boot-raphael.img
```

`package-raphael.py` extracts the SM8150 v2 SoC DTB from your stock boot.img and packs a **header v1** image exactly like the stock layout (DTB appended to the kernel blob). **Use `cpus=1` for the first boot**; add `sweettouch=0 sweetkeys=0` to isolate drivers.

**3. Flash the root and boot:**

```sh
fastboot -S 512M flash userdata ios16-root.simg    # ~7 min, do not unplug
# Xiaomi's fastboot often hangs after a large flash: re-enter with Power + Volume down
fastboot boot shim-boot-raphael.img                # temporary, boot partition untouched
```

**4. Read the kernel log:**

```sh
fastboot boot recovery/recovery.img                # OrangeFox, temporary
tools/sweet-log-pull.sh logs/raphael-1.txt         # 4 MiB ring at the end of userdata
adb reboot bootloader
```

The log contains crash reports with backtraces (`CRASH name ...`), IOKit traces of backboardd/SpringBoard and the drivers' `SWEET ...` lines; `tools/sweet-crash.py` symbolicates against the shared cache.

### Boot-args cheat sheet

| Arg | Effect |
| --- | --- |
| `rd=ufsroot0 ufsrw=1 rootrw=1` | Root on the `userdata` partition, writable |
| `cpus=8` (`cpus=1` for the first boot) | Start secondary cores via PSCI |
| `sweetusb=2` | Start the DWC3 device controller + CDC-ECM + UDP log (default `sweetusb=1` only reports clock/GDSC state) |
| `launchd_unsecure_cache=1` | launchd accepts its job cache without AMFI |
| `wdt=-1 wdt_test=no_user_checkin` | No hardware watchdog |
| `sweetfb_noconsole=1` | Stop drawing kernel text over the GUI (the log still goes to the ring; panics are drawn) |
| `sweetfb_hz=30` | Panel refresh rate of the CPU copy |
| `sweettouch=0` / `sweetkeys=0` | Disable the touch / button drivers |

### Kernel patches (raphael)

| Patch | What |
| --- | --- |
| 0082 | Machine config registration: SM8150 layout, reuses the generic driver set |
| 0083 | Input: GT9889 touch protocol + SE19 clocks/pins + TLMM supplies + PON keys |
| 0084 | Display: 1080×2340 early console / panic line / SweetHID scaling |
| 0085 | Volume-up = PM8150 GPIO6 (settled by the mainline DTS) + one-shot PMIC GPIO census log |
| 0086 | Touch second source corrected to ST FingerTipS: read-only 0x49 probe + event FIFO pump; IRQ pin fix (GPIO122) |
| 0087 | USB: DWC3/qscratch/QUSB2/GDSC addresses verified for SM8150 (only two GCC branches moved + phy ref correction); ue0/ECM/UDP path activated |

0001-0081 are the generic foundation series (toolchain compatibility, UFS driver, HFS+, HID event services, USB device mode, SMP/PSCI, ...), applied in order by CI. Register-level evidence, the GT9889/ST FTS protocol details and the bring-up order are in [NOTES.md](NOTES.md).

### Key hardware facts (SM8150 / raphael)

- GICD/GICR `0x17a00000`/`0x17a60000` (GICR stride 0x20000); timer PPIs: phys INTID 18 / virt INTID 19, 19.2 MHz
- UFS host `ufshc@1d84000` (left initialized by ABL); SPMI arbiter `0xc440000`; RPMh apps RSC `0x18220000`
- ABL framebuffer `0x9c000000` (cont_splash 0x2400000); imem restart_reason `0x146bf65c`
- Touch GENI SE19 @ `0xc88000` (wrap2 S2); one TLMM block at `0x03000000`
- Touch supplies are plain TLMM GPIOs: vdd 3v3 = GPIO98, avdd 1v8 = GPIO100 (no RPMh LDO vote needed)
- Touch pins: reset GPIO54 / IRQ GPIO122 / SDA-SCL GPIO57-58 (qup19 func 2)
- Touch IC: Goodix GT9889 @0x5d (MIUI DTB and mainline DTS agree); the kernel source also carries an ST FingerTipS `fts_521` (0x49, second-source possibility)
- CPU clocks: Prime 2.8416G / Gold 2.4192G / Silver 1.8048G; ARMv8.2, no PAC, 16K granule, crypto extensions
- Stock boot.img (V12.5.6.0.RFKCNXM): header v1, four SoC DTBs inside the kernel blob (sm8150/sm8150p × v1/v2), K20 Pro = SM8150 v2; cmdline has `androidboot.usbcontroller=a600000.dwc3`

### Resources (the K20 Pro scene)

The K20 Pro has one of the richest flashing/reverse-engineering scenes among SD855 devices; this port leans on:

- **Mainline Linux DTS**: `sm8150-xiaomi-raphael.dts` — series [PATCH v2 0/3] Add Xiaomi Redmi K20 Pro (Raphael) (patchew.org/linux/20251104221657.51580-1-pc1598@mainlining.org): volume-up key (pm8150_gpios 6), goodix@5d on i2c19, panel `samsung,ams639rq08`
- **howtocuddle/xiaomi_raphael**: 6.18 mainline status (display ams639rq08 / touch / cameras)
- **postmarketOS**: wiki page xiaomi-raphael, package `linux-xiaomi-raphael`
- **Stock kernel sources**: github.com/ZakoClubROM/android_kernel_xiaomi_raphael (lineage-19.0: `goodix_driver_gt9886`, `fts_521` driver sources, `raphael-*` dtsi — ground truth for touch/panel/keys)
- LineageOS raphael device tree; XDA raphael kernel/recovery threads; official OrangeFox/TWRP support (for log pulls)

### Repository layout

| Path | What |
| --- | --- |
| `shim/` | Bare-metal boot shim (C + asm), packed as an Android boot.img |
| `xnu/patches/` | The XNU patch series (applied in order by CI) + libpthread/HFS/BearSSL staging scripts |
| `.github/workflows/xnu.yml` | Kernel CI (machine_config=RAPHAEL) |
| `.github/workflows/raphael.yml` | Shim CI build |
| `tools/mkadt.py --raphael` | Generates the Apple Device Tree from the SM8150 MMIO layout |
| `tools/mkpayload.py` | Packs kernel + ADT + boot-args into the shim payload |
| `tools/package-raphael.py` | Stock-boot.img DTB + payload → shim-boot-raphael.img |
| `tools/mkiosroot.sh` + `sweet-root-tweaks.py` | IPSW → HFS+ iOS root |
| `tools/sweet-log-pull.sh` / `sweet-log.py` / `sweet-usbnet.sh` | Persistent log pull / live UDP log |
| `tools/qemu-sweet.py` | QEMU `virt` smoke test with framebuffer text decoding |
| `tools/sweet-crash.py` / `xnu-cc.py` / `remotezip.py` / `unpack_bootv2.py` | Crash symbolication / local single-file compile check / partial IPSW fetch / boot unpack |
| `NOTES.md` | raphael engineering notes: register-level evidence, protocols, bring-up order |
| `docs/WORKLOG.md` | Work log (updated and pushed after every step) |

Not in git: partition backups, live device trees, recovery images, Apple firmware and root images, downloaded/generated build trees (device serials and calibration data, or Apple's copyrighted files).

## Credits

Built on the generic porting framework of the upstream [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) project (patch series, UFS driver, HFS+ root flow). Thanks to Apple's open-source releases (xnu, IOHIDFamily, libpthread, hfs), [BearSSL](https://bearssl.org), [blacktop/darwin-xnu-build](https://github.com/blacktop/darwin-xnu-build), [ipsw](https://github.com/blacktop/ipsw), Qualcomm/Xiaomi's published Linux kernel sources, the mainline Linux and postmarketOS communities, and [OrangeFox Recovery](https://orangefox.download). iOS itself is Apple's and is not distributed here.
