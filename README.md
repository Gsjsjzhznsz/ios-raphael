# ios-sweet @ Redmi K20 Pro (raphael)

[dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet)（XNU 内核 + iOS 16.7.16 userspace，上游已在 sweet / Redmi Note 10 Pro 点亮 iOS 主屏）向 **raphael / Redmi K20 Pro（SM8150）** 的移植实验分支。

> ⚠️ 【警告】本项目尚未经过全流程实测，仅供极客测试。操作会彻底清空手机数据，严禁在主力机上操作！

**当前状态（2026-10-21, r19/t11）**

- ✅ XNU 早期引导链路实机验证：shim → 内核加载 → VM/zone → 实机完整启动进锁屏
- ✅ **8 核实机确认（t10 日志）**：`SWEET CPU: requested=8 selected=8` → `8/8 CPUs initialized`；bootstrap 卡死（根因 kryo470 失配，0090 已修）与卡顿（单核副作用）双双关闭
- ✅ 显示：raphael 原生 1080x2340 面板点亮（AppleCLCD，shim 直写 ABL splash 帧缓冲）
- ✅ USB：内核枚举 `1209:0001 Sweet iOS`；看门狗已解除（日志定格不重启）
- ✅ rootfs 管线：iOS 16.7.16 → 16G HFS+ 镜像（CI 全自动，见 Releases）
- 🔧 **触摸根因已定位（t10 日志实锤，0093 修复）**：`bus idle`/`bus live` 六个电平读数全 0 —— SM8150 TLMM 不是平坦一块，GPIO 寄存器在 `0x03000000 + tile偏移 + 0x1000×编号`（SOUTH=0x00D00000，pinctrl-sm8150.c 实锤）；触摸 6 个 GPIO（54/57/58/98/100/122）全在 SOUTH tile，真窗口 = **0x03D00000**。驱动从 0083 起映射 TLMM 基址本身（未实现空洞）→ 触摸 IC 从未上电、SDA/SCL 从未复用到 qup19 → 探针必然超时。0093 改映射 SOUTH tile，启动行带 `TLMM-south` 正向标记
- 🔧 **电池真相（t10 日志实锤，0092 修复）**：`sweetbattery=0` → `static fallback`（恒 100%/4200mV/假外接电源）。0092 = PM8150B fg-gen4 QG（SPMI SID 2）真实电压/电流/电量 + SMB5 充电器状态；t11 cmdline 已开 `sweetbattery=1`
- 🚧 **t11（r19）已发布待实测**：触摸根因修复 + 电池真实读数一次刷机双验证；判读树见 docs/FLASH-T11.md

## 下载（Releases）

| 文件 | 说明 |
|---|---|
| `raphael-t11-battery-clean.img` | **当前首刷推荐（r19）**：**0093 触摸根因修复**（TLMM SOUTH tile 窗口 0x03D00000）+ **0092 电池真实读数**（PM8150B QG + SMB5，`sweetbattery=1`）+ 8 核；判读树 docs/FLASH-T11.md |
| `raphael-t11-battery-debug.img` | r19 排障版：同 clean 但**屏幕控制台常开**（卡住拍最后几行即可定位） |
| `raphael-t7-touchfix-clean.img` | 回退/对照：t7（SWEET 编译，8 核可启动，触摸死） |
| `ios16-root.simg.part-00 ~ 05` + `CHECKSUMS.txt` | iOS 16.7.16 rootfs（16G HFS+ 稀疏镜像分卷） |

> 旧发行版（r11–r14、t1–t10、sc 系列）已按需求清理；哈希历史保留在 git 各 Release 提交内。t 系列镜像均为组件级校验重打包（shim/DTB/ADT/cmdline 逐字节比对）：

```
t7-clean: 91abcc1be3bce986606500a8003576d1c01fc31ee9348af9659e75c5583559fe （回退用，已知可启动）
t9-clean: 371d84e0e934ced88ac549e99b64798d1ff1c86dc14df1ef1ede0fad236d22fe （单核，已被 t11 取代）
t10-clean: e8cd3bc126670fdb2cb3bcd5cf4ee1a3f3b572a1ab53d49234dde0c378a2f857 （诊断版，已完成使命）
t11-clean: bd75bc2d0a0db479f4295bfe80ecab85276a80b3258ac27ff746723fe902cf12
t11-debug: df4690b644df0699bb917841b9dda1eadf3292558e93f4ec8d5283a90e705aab
```

## 📱 K20 Pro 刷入 iOS 极简指南

### 一、准备

- 设备：已解锁 BL 的 K20 Pro，电量 > 80%。
- 环境：电脑或另一台手机（Termux + `android-tools`，OTG 线连接目标机）已装 adb / fastboot。
- 文件：
  - `ios16-root.simg.part-00 ~ 05` 及 `CHECKSUMS.txt`
  - `raphael-t11-battery-debug.img`（排障版，首刷；屏幕控制台常开）
  - `raphael-t11-battery-clean.img`（正式版）
  - `raphael-t7-touchfix-clean.img`（回退用，已知可启动）
  - K20 Pro 的 `recovery.img`（OrangeFox，用于备份与取证）

### 二、合并与校验镜像

```bash
# 1. 合并分卷
#    Windows: copy /b ios16-root.simg.part-* ios16-root.simg
#    Mac/Linux: cat ios16-root.simg.part-* > ios16-root.simg

# 2. 校验（确保哈希与 CHECKSUMS.txt 一致）
#    Windows: certutil -hashfile ios16-root.simg SHA256
#    Mac/Linux: sha256sum ios16-root.simg
```

### 三、备份关键分区（保命必做）

1. 手机关机，**电源 + 音量下** 进 Fastboot。
2. `fastboot boot recovery.img` 进临时 Recovery。
3. 新建 `backup` 文件夹并备份：

```bash
for p in persist modemst1 modemst2 fsg fsc boot dtbo vbmeta; do
    adb exec-out cat /dev/block/by-name/$p > backup/$p.img
done
```

> Windows 用户请在 **CMD**（勿用 PowerShell，`>` 会按文本编码重写、损坏二进制流）或 WSL 下执行。

### 四、刷入 Rootfs

```bash
adb reboot bootloader
# 耗时约 10-20 分钟
fastboot -S 512M flash userdata ios16-root.simg
```

> 刷完后若卡死黑屏（小米 fastboot 假死）：长按 **电源 + 音量下** 强行重进 Fastboot，已写入数据不会丢。

### 五、启动与验证

1. **首刷排障版**（屏幕控制台常开）：

```bash
fastboot boot raphael-t11-battery-debug.img
```

- 屏幕滚动内核日志 → 出现 `SWEET UFS:` 行 → 屏幕被文字"画花" = iOS 用户态接管（正常现象，正式版才有干净画面）。
- 若卡住：**拍下最后几行**发回 —— 那就是精确卡点（判读树见 Release 内 `FLASH-T11.md`）。

2. **正式启动**（确认上一步成功后）：

```bash
fastboot boot raphael-t11-battery-clean.img
```

- 此版本无文字叠加：黑屏/定格画面数分钟（无进度反馈）→ 锁屏出现（8 核，应与 t10 同样流畅）。
- 重点观察：①**上手滑触摸**（`probe 0x5d` err=0 即活）；②**锁屏电池**（不再是恒定 100% 即活）；③拉日志看 `TLMM-south`/`bus idle`/`bus live` 判读行。
- 超过 15 分钟无变化 → 转下方「救砖与取证」。

## 🚑 救砖与取证

- **提取内核日志**（持久日志环 = userdata 末 4MiB，在 HFS+ 卷之外，不怕踩数据）：

```bash
fastboot boot recovery.img
adb shell -T "tail -c 4194304 /dev/block/by-name/userdata > /tmp/log.bin"
adb pull /tmp/log.bin
```

> 存放路径必须是 `/tmp`（内存盘）——`/sdcard` 现在是 HFS+，Recovery 挂不上。

- **USB 判别法（5 秒）**：主机 `fastboot devices` 仍列出设备 = 小米 ABL fastboot 残留；枚举出 `1209:0001 Sweet iOS` 才是内核 USB 活着。

- **回退安卓**：小米官方 MiFlash 刷入官方线刷包（需 PC；无 PC 可用 Termux fastboot + OTG 逐分区刷线刷包）。重刷 userdata 会同时抹掉 iOS rootfs。

## 构建与工具

- `.github/workflows/build-rootfs.yml` — 一键产出 iOS rootfs 并发 Release（macOS runner）
- `tools/build-raphael.sh` — 全链路打包：DTB 提取 → ADT → mkpayload → shim → boot.img v2
- `tools/repack-boot-v2.py` — 对实测 boot 镜像原位补丁 cmdline（sanity 模式逐字节复验），布局逆向文档见 `tools/README-repack.md`
- 补丁链 0001-0093：早期控制台 / 持久日志环 / USB bring-up / raphael 显示适配 / 0090 匹配表（kryo485）/ 0091 触摸总线诊断 / 0092 电池（PM8150B QG）/ 0093 触摸根因（TLMM SOUTH tile）等

## 致谢

- [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) — 上游项目与纯 Linux rootfs 管线
- XNU 内核与 iOS userspace 版权归 Apple Inc. 所有，本项目仅用于研究学习

> r19/t11 判读树与取证命令见 Release `raphael-touch-r19` 内 `FLASH-T11.md`（历史判读树 FLASH-T6~T10 保留在 docs/）。
