# ios-sweet @ Redmi K20 Pro (raphael)

[dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet)（XNU 内核 + iOS 16.7.16 userspace，上游已在 sweet / Redmi Note 10 Pro 点亮 iOS 主屏）向 **raphael / Redmi K20 Pro（SM8150）** 的移植实验分支。

> ⚠️ 【警告】本项目尚未经过全流程实测，仅供极客测试。操作会彻底清空手机数据，严禁在主力机上操作！

**当前状态（2026-10-21, r17/t9）**

- ✅ XNU 早期引导链路实机验证：shim → 内核加载 → VM/zone（diag5 定格至 `bootstrap done` —— 现判读为与 t8 同卡点，待 t9 复核）
- ✅ 显示：raphael 原生 1080x2340 面板点亮（AppleCLCD，shim 直写 ABL splash 帧缓冲）
- ✅ USB：内核枚举 `1209:0001 Sweet iOS`；看门狗已解除（日志定格不重启）
- ✅ rootfs 管线：iOS 16.7.16 → 16G HFS+ 镜像（CI 全自动，见 Releases）
- ✅ **UFS 读路径已实机验证**（社区复现，[Helium-Studio/ios-raphael](https://github.com/Helium-Studio/ios-raphael) 0082d 只读 probe：`BSD root: ufsroot0` + GPT 定位 userdata；F2FS 上 `hfs_mount error=22` 为预期边界）。其 0082e stage2 已刷 boot 分区 + rootfs 刷入 userdata，Apple logo 待回报。
- ✅ **锁屏点亮（原生 4 系内核栈）**：swap-test t2（我们内核 + 修复 ADT：1 CPU + fbcon 0x9a4000 + /product 嫁接）已在实机进入 iOS 锁屏，用户态服务全面跑通（raphael-swaptest-r11 Release）。
- ✅ **8 核 + 按键实证（r15 日志）**：`SWEET CPU: 8/8 CPUs initialized`；按键事件已投递用户态（`SWEET HID: key ... (1 clients)`）
- 🔧 **触摸时钟根因（0089，t6 日志实锤）**：wrap2 s_ahb（0x1e008）是 HWCG 门控分支（健康时 CLK_OFF 常驻 1），Linux 对其跳过检查，旧代码死等清零→静默退出；现按 Linux 语义放行
- 🚨 **t8 回归（r16 实测）**：t8（首个 RAPHAEL 编译内核）卡 `bootstrap done`，t7 正常。复盘实证：历史全部 RAPHAEL 编译内核（diag5/r11-sc/t8）都卡在同一卡点，唯一例外 t2 —— 差异两处且从未隔离：①匹配表 `IONameMatch 'qcom,kryo470'` vs ADT 声明 `kryo485`（t2 只做过二进制就地补丁，未入库）；②t2 ADT 仅 1 个 CPU 节点（逐节点解析实锤：t 系列 ADT 与 t2 的唯一结构差异 = CPU 节点 1→8）。另实证：t5/t6/t7 全部是 SWEET 编译（镜像字符串标记），RAPHAEL 编译从未在 t 系列成功启动过
- 🚧 **t9（r17）已发布待实测**：t2 配方正式入库 —— 补丁 0090（匹配表 kryo470→485）+ ADT 删 cpu1–7（其余与 t 系列逐字节同源）；debug 版屏幕控制台常开（卡住拍最后几行即可定位）；shim/DTB/cmdline 与 t7 逐字节不变
- 🔧 **R14 结论修正**：所谓"面板 180° 倒置"实为拍摄时手机物理倒持（用户确认）；0088 修订为默认不翻转（`sweettouchflip=1` 可强制），触摸方向无需补偿
- 🚧 **熄屏渐慢**：无 GPU、CPU 软渲染的锁屏淡出动画被拉长（display off 路径正常）；待 t9 回报后再评估 `sweetfb_hz` 对照

## 下载（Releases）

| 文件 | 说明 |
|---|---|
| `raphael-t9-bootstrapfix-clean.img` | **当前首刷推荐（r17）**：补丁 0090（匹配表 kryo485 入库）+ 1-CPU ADT（t2 配方）+ 0089；cmdline 与 t7 逐字节一致 |
| `raphael-t9-bootstrapfix-debug.img` | r17 排障版：同 clean 但**屏幕控制台常开**（卡住拍最后几行即可定位） |
| `raphael-t7-touchfix-clean.img` | 回退/对照：t7（SWEET 编译，8 核，触摸死——RAPHAEL 增量未编入） |
| `raphael-t7-touchfix-debug.img` | t7 排障版（控制台已关） |
| `ios16-root.simg.part-00 ~ 05` + `CHECKSUMS.txt` | iOS 16.7.16 rootfs（16G HFS+ 稀疏镜像分卷） |

> 旧发行版（r11–r14、t1–t6/t8、sc 系列）已按需求清理；哈希历史保留在 git 各 Release 提交内。t 系列镜像均为组件级校验重打包（shim/DTB/ADT/cmdline 逐字节比对）：

```
t7-clean: 91abcc1be3bce986606500a8003576d1c01fc31ee9348af9659e75c5583559fe
t8-clean: 1bcdfbb9b0aa524a065cdbfd95a832b1535ac36b3a0686022fd1befbb389c7d7 （已被 t9 取代：卡 bootstrap done）
t9-clean: 371d84e0e934ced88ac549e99b64798d1ff1c86dc14df1ef1ede0fad236d22fe
t9-debug: d9203c0eaa0ee550aefcfc8d1655d1f4ea299ff600bd8eab87b8efbebaf7014e
```

## 📱 K20 Pro 刷入 iOS 极简指南

### 一、准备

- 设备：已解锁 BL 的 K20 Pro，电量 > 80%。
- 环境：电脑或另一台手机（Termux + `android-tools`，OTG 线连接目标机）已装 adb / fastboot。
- 文件：
  - `ios16-root.simg.part-00 ~ 05` 及 `CHECKSUMS.txt`
  - `raphael-t9-bootstrapfix-debug.img`（排障版，首刷；屏幕控制台常开）
  - `raphael-t9-bootstrapfix-clean.img`（正式版）
  - `raphael-t7-touchfix-clean.img`（回退用）
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
fastboot boot raphael-t9-bootstrapfix-debug.img
```

- 屏幕滚动内核日志 → 出现 `SWEET UFS:` 行 → 屏幕被文字"画花" = iOS 用户态接管（正常现象，正式版才有干净画面）。
- 若卡住：**拍下最后几行**发回 —— 那就是精确卡点（判读树见 Release 内 `FLASH-T9.md`）。

2. **正式启动**（确认上一步成功后）：

```bash
fastboot boot raphael-t9-bootstrapfix-clean.img
```

- 此版本无文字叠加：黑屏/定格画面数分钟（无进度反馈）→ 锁屏出现（t9 为 1 核，比 8 核慢，耐心等）。
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
- 补丁链 0001-0090：早期控制台 / 持久日志环 / USB bring-up / raphael 显示适配 / 0090 匹配表（kryo485）等

## 致谢

- [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) — 上游项目与纯 Linux rootfs 管线
- XNU 内核与 iOS userspace 版权归 Apple Inc. 所有，本项目仅用于研究学习

> r17/t9 判读树与取证命令见 Release `raphael-touch-r17` 内 `FLASH-T9.md`（历史判读树 FLASH-T6/T7/T8 保留在 docs/）。
