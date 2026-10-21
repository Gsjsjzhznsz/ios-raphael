# ios-sweet @ Redmi K20 Pro (raphael)

[dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet)（XNU 内核 + iOS 16.7.16 userspace，上游已在 sweet / Redmi Note 10 Pro 点亮 iOS 主屏）向 **raphael / Redmi K20 Pro（SM8150）** 的移植实验分支。

> ⚠️ 【警告】本项目尚未经过全流程实测，仅供极客测试。操作会彻底清空手机数据，严禁在主力机上操作！

**当前状态（2026-10-21, r16/t8）**

- ✅ XNU 早期引导全链路实机通过：shim → 内核加载 → VM/zone → `bootstrap done`（diag5 定格验证，12/12 shim 服务注册）
- ✅ 显示：raphael 原生 1080x2340 面板点亮（AppleCLCD，shim 直写 ABL splash 帧缓冲）
- ✅ USB：内核枚举 `1209:0001 Sweet iOS`；看门狗已解除（日志定格不重启）
- ✅ rootfs 管线：iOS 16.7.16 → 16G HFS+ 镜像（CI 全自动，见 Releases）
- ✅ **UFS 读路径已实机验证**（社区复现，[Helium-Studio/ios-raphael](https://github.com/Helium-Studio/ios-raphael) 0082d 只读 probe：`BSD root: ufsroot0` + GPT 定位 userdata；F2FS 上 `hfs_mount error=22` 为预期边界）。其 0082e stage2 已刷 boot 分区 + rootfs 刷入 userdata，Apple logo 待回报。
- ✅ **锁屏点亮（原生 4 系内核栈）**：swap-test t2（我们内核 + 修复 ADT：1 CPU + fbcon 0x9a4000 + /product 嫁接）已在实机进入 iOS 锁屏，用户态服务全面跑通（raphael-swaptest-r11 Release）。
- ✅ **8 核 + 按键实证（r15 日志）**：`SWEET CPU: 8/8 CPUs initialized`；按键事件已投递用户态（`SWEET HID: key ... (1 clients)`）
- ✅ **触摸真修复上车（r16/t8）**：t7 测试暴露 CI 级根因——`xnu.yml` push 触发回退 `MACHINE_CONFIG=SWEET`，r12-r15 全部 push 内核里 raphael 触摸/按键/USB 增量被预处理成死代码（t7 CI 日志 937/937 条编译命令无 `-DARM64_BOARD_CONFIG_RAPHAEL`）。已修：push 默认 RAPHAEL + CI 宏断言；t8 = 首个 RAPHAEL 编译 + 0089 内核（SE19@0xc88000 / GT9889@0x5d / TLMM 供电路径首次上车）
- ✅ **触摸时钟根因（0089，t6 日志实锤）**：wrap2 s_ahb（0x1e008）是 HWCG 门控分支（健康时 CLK_OFF 常驻 1），Linux 对其跳过检查，旧代码死等清零→静默退出；现按 Linux 语义放行
- 🔧 **R14 结论修正**：所谓"面板 180° 倒置"实为拍摄时手机物理倒持（用户确认）；0088 修订为默认不翻转（`sweettouchflip=1` 可强制），触摸方向无需补偿
- 🚧 **熄屏渐慢**：无 GPU、CPU 软渲染的锁屏淡出动画被拉长（display off 路径正常）；本轮 `sweetfb_hz` 30→60 对照实验

## 下载（Releases）

| 文件 | 说明 |
|---|---|
| `raphael-t8-clean.img` | **当前首刷推荐（r16）**：首个 RAPHAEL 编译内核（0089 已含）+ 8 核 + 无叠加，cmdline 与 t7 逐字节一致 |
| `raphael-t8-debug.img` | r16 排障版：clean + `sweethidtest=15`（控制台同样已关） |
| `raphael-t7-touchfix-clean.img` | r15：内核实为 SWEET 编译（CI 回退 bug），仅供对照/回退 |
| `raphael-t7-touchfix-debug.img` | r15 排障版：clean + `sweethidtest=15`（控制台同样已关） |
| `raphael-t6-touchflip-clean.img` | r14：触摸 180° 翻转（**前提有误，已被 r15 撤销**，勿用） |
| `raphael-t6-touchflip-debug.img` | r14 排障版：同上 + 屏上日志 + `sweethidtest=15` |
| `raphael-t5-8core-clean.img` | r13 日常版（8 核 + 触摸开，内核无翻转——触摸异常时用它对照） |
| `raphael-hid-clean.img` | r12 单核对照（cpus=1，触摸已开、无翻转） |
| `raphael-t2-native-fullfix.img` | 锁屏里程碑版（但 keys/touch 关闭，仅供对照） |
| `raphael-t1/t3/t4-*.img` | R11 交叉定位组（已完成使命） |
| `ios16-root.simg.part-00 ~ 05` + `CHECKSUMS.txt` | iOS 16.7.16 rootfs（16G HFS+ 稀疏镜像分卷） |
| `shim-boot-raphael-sc-verbose.img` / `sc-full.img` | 早期单核排障/生产版 |
| `shim-boot-raphael-full(-verbose).img` | 旧 8 核版（实验性） |

boot 镜像 = diag5 实测内核**原样提取重打包**，仅 cmdline 不同（复验脚本 `tools/repack-boot-v2.py`，内核/ADT/DTB 三段 SHA256 逐字节一致；sc 版 cmdline 对齐社区实机验证过的 stage2 配方）：

```
sc-full:     b8b3e47ab6907ba666437d94b4a70cbc41f12e8cf7443dd3b294f7ade6c0dd25
sc-verbose:  6db479ab0c610241ffe5f273aae5cc81863eb8a2bd24896a8d4a913442acc7ab
full(8核):    a85b9a07813ec143dc0b910a0e73f7e45fe62b0f3405e9aa6cba9a30b0d16ff2
verbose(8核): 720b903360caace991fd43878a18ab807861fd278b84f82f8d1ca10f578343e4
t2-native:   1bc5396e04ae29447e1445968d40a72a9a987bdde95fb6f24ce49390738d4748
hid-debug:   103215da2e6d80f55097523259f609c06bfd52e0fd0ddc323ca09a3c0358daf1
hid-clean:   0a98df3b1545a1c50dab81ef770f048ea9c0e37d29804f523728e1772fb87b52
t5-8core-clean: a634a6c02d32535bf55ef6476c2cde6bf5f400e6a15664a4af70db1436322129
t5-8core-debug: 72d1b75854d1b326c213738976a97d4e828a0d590e9a7dfd5c83f11a3f19eb25
t6-flip-clean:  1d39aa012d754f246d7423d774765ae7254f2c25822d8f493241a5972de9b18e
t6-flip-debug:  31e5a8725340d68564c97e9cfdadff360f298ec8421cc171b6d9f1233df4c43b
t7-touchfix-clean: 91abcc1be3bce986606500a8003576d1c01fc31ee9348af9659e75c5583559fe
t7-touchfix-debug: 70ca59669a99e6f6e3abeded879369c5f884d0c0aee36608758015f798dbc5c8
t8-clean: 1bcdfbb9b0aa524a065cdbfd95a832b1535ac36b3a0686022fd1befbb389c7d7
t8-debug: f6bcfc9f56741124975ce7f717b6623573549ed3f78f9ad663a2bab4f03f6a59
```

> t8 与 t7 的差异：内核全量重编译（RAPHAEL 宏恢复）；shim/ADT/DTB 逐字节不变。判读树见 Release 内 `FLASH-T8.md`。

> HID 版与 t2 的差异仅 36/18 字节（608B cmdline 区内）：内核/ADT/DTB/shim 逐字节不变。判读树与日志取证见 Release 内 `FLASH-HID.md`。

## 📱 K20 Pro 刷入 iOS 极简指南

### 一、准备

- 设备：已解锁 BL 的 K20 Pro，电量 > 80%。
- 环境：电脑或另一台手机（Termux + `android-tools`，OTG 线连接目标机）已装 adb / fastboot。
- 文件：
  - `ios16-root.simg.part-00 ~ 05` 及 `CHECKSUMS.txt`
  - `shim-boot-raphael-sc-verbose.img`（排障版，首刷）
  - `shim-boot-raphael-sc-full.img`（正式版）
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

1. **首刷排障版**（cpus=1 安全版）：

```bash
fastboot boot shim-boot-raphael-sc-verbose.img
```

- 现象：屏幕滚动内核日志，随后出现 UFS/GPT 挂载信息。
- 成功标志：4-8 分钟内屏幕被大量白色文字"画花"——说明 iOS 用户态已接管（verbose 版正常现象，正式版才有干净画面）。
- 注意：只要机身微热就说明在干活，绝对不要提前断电重启。

2. **正式启动**（确认上一步成功后）：

```bash
fastboot boot shim-boot-raphael-sc-full.img
```

- 此版本无文字叠加：黑屏/定格画面数分钟（无进度反馈）→ 锁屏出现。
- 超过 10 分钟无变化 → 转下方「救砖与取证」。

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
- 补丁链 0001-0087：早期控制台 / 持久日志环 / USB bring-up / raphael 显示适配等

## 致谢

- [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) — 上游项目与纯 Linux rootfs 管线
- XNU 内核与 iOS userspace 版权归 Apple Inc. 所有，本项目仅用于研究学习

> r16 判读树与取证命令见 Release `raphael-touch-r16` 内 `FLASH-T8.md`。
