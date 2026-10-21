# ios-sweet @ Redmi K20 Pro (raphael)

[dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet)（XNU 内核 + iOS 16.7.16 userspace，上游已在 sweet / Redmi Note 10 Pro 点亮 iOS 主屏）向 **raphael / Redmi K20 Pro（SM8150）** 的移植实验分支。

> ⚠️ 【警告】本项目尚未经过全流程实测，仅供极客测试。操作会彻底清空手机数据，严禁在主力机上操作！

**当前状态（2026-10-21, r20/t12）**

- ✅ XNU 早期引导链路实机验证：shim → 内核加载 → VM/zone → 实机完整启动进锁屏
- ✅ **8 核实机确认（t10/t11 日志）**：`8/8 CPUs initialized`；bootstrap 卡死（根因 kryo470 失配，0090 已修）与卡顿（单核副作用）双双关闭
- ✅ **触摸总线已通（t11 日志）**：TLMM-south 修复后供电轨 vdd=3/avdd=3、SDA/SCL 拉高、IC 应答（probe err=0）
- ✅ 显示：raphael 原生 1080x2340 面板点亮（AppleCLCD，shim 直写 ABL splash 帧缓冲）
- ✅ USB：内核枚举 `1209:0001 Sweet iOS`；看门狗已解除（日志定格不重启）
- ✅ rootfs 管线：iOS 16.7.16 → 16G HFS+ 镜像（CI 全自动，见 Releases）
- 🔧 **触摸真根因已定位（爬透 LineageOS raphael 内核 + vendor 固件 blob，0094 修复）**：① GT9886 "normandy" 寄存器图来自配置 blob（pid@0x4535、配置窗口@0x6f78、**触摸帧@0x4100**），t8 以来读的 0x8240/0x824E 只是碰巧 ACK 的地址；② 这颗 IC 每次开机**必须下发 784 字节面板配置**（双供应商配置已从 vendor blob 原样嵌入内核，按 IC sensor-id 选择），不下发就没有触摸帧；③ t11 探针成功后轮询全灭的元凶 = 0x49 ST FTS 探针 NACK 后 TX FIFO 残留字节投毒 → 已删除 + TX 改水位驱动流式写入（单条写 786B）
- 🔧 **电池真根因已定位（0095 修复）**：SPMI 观察者命令漏了 `sid<<20` 位域（Linux pmic_arb_fmt_cmd_v2 对照）—— SWEET（PM6150=SID0）无害，raphael PM8150B（**SID 2**）每次都读错 PMIC → 静默 static fallback；已修复 + 启动探针逐字段记录
- 🚧 **t12（r20）已发布待实测**：一次刷机双验证（触摸配置下发链 + 电池真实读数）；判读树见 docs/FLASH-T12.md

## 下载（Releases）

| 文件 | 说明 |
|---|---|
| `raphael-t12-gt9886-clean.img` | **当前首刷推荐（r20）**：**0094 GT9886 厂商级 bring-up**（真寄存器图 + 784 字节配置下发 + doze 控制 + TX 流式写入）+ **0095 电池 sid 根因修复**（SPMI 命令补 sid 位域 + 逐字段探针）+ 8 核；判读树 docs/FLASH-T12.md |
| `raphael-t12-gt9886-debug.img` | r20 排障版：同 clean 但**屏幕控制台常开**（卡住拍最后几行即可定位） |
| `raphael-t7-touchfix-clean.img` | 回退/对照：t7（SWEET 编译，8 核可启动，触摸死） |
| `ios16-root.simg.part-00 ~ 05` + `CHECKSUMS.txt` | iOS 16.7.16 rootfs（16G HFS+ 稀疏镜像分卷） |

> 旧发行版（r11–r14、t1–t11、sc 系列）已按需求清理；哈希历史保留在 git 各 Release 提交内。t 系列镜像均为组件级校验重打包（shim/DTB/ADT/cmdline 逐字节比对）：

```
t7-clean: 91abcc1be3bce986606500a8003576d1c01fc31ee9348af9659e75c5583559fe （回退用，已知可启动）
t10-clean: e8cd3bc126670fdb2cb3bcd5cf4ee1a3f3b572a1ab53d49234dde0c378a2f857 （诊断版，已完成使命）
t11-clean: bd75bc2d0a0db479f4295bfe80ecab85276a80b3258ac27ff746723fe902cf12 （总线已通，已被 t12 取代）
t12-clean: 3725736f0773ede73b59a35d1cabddc92decbc58aaa37f8a375fa09d46459c6b
t12-debug: 8dc5b5a98155949f552f8b8caa35bf772311560dff81bc63c47a7f89f639ba8b
```

## 📱 K20 Pro 刷入 iOS 极简指南

### 一、准备

- 设备：已解锁 BL 的 K20 Pro，电量 > 80%。
- 环境：电脑或另一台手机（Termux + `android-tools`，OTG 线连接目标机）已装 adb / fastboot。
- 文件：
  - `ios16-root.simg.part-00 ~ 05` 及 `CHECKSUMS.txt`
  - `raphael-t12-gt9886-debug.img`（排障版，首刷；屏幕控制台常开）
  - `raphael-t12-gt9886-clean.img`（正式版）
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
fastboot boot raphael-t12-gt9886-debug.img
```

- 屏幕滚动内核日志 → 出现 `SWEET UFS:` 行 → 屏幕被文字"画花" = iOS 用户态接管（正常现象，正式版才有干净画面）。
- 若卡住：**拍下最后几行**发回 —— 那就是精确卡点（判读树见 Release 内 `FLASH-T11.md`）。

2. **正式启动**（确认上一步成功后）：

```bash
fastboot boot raphael-t12-gt9886-clean.img
```

- 此版本无文字叠加：黑屏/定格画面数分钟（无进度反馈）→ 锁屏出现（8 核，应与 t10 同样流畅）。
- 重点观察：①**上手滑触摸**（`cfg send … err=0` 即配置入 IC，触摸应直接工作；方向不对回报 `sensor id=`/`flip=` 值）；②**锁屏电池**（不再恒定 100% 即活）；③拉日志看 `GT9886 pid`/`cfg send`/`SWEET BATTERY: probe` 判读行。
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
- 补丁链 0001-0095：早期控制台 / 持久日志环 / USB bring-up / raphael 显示适配 / 0090 匹配表（kryo485）/ 0091 触摸总线诊断 / 0092 电池（PM8150B QG）/ 0093 触摸 TLMM-south / 0094 GT9886 配置下发（触摸真根因）/ 0095 电池 SPMI sid 等

## 致谢

- [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) — 上游项目与纯 Linux rootfs 管线
- XNU 内核与 iOS userspace 版权归 Apple Inc. 所有，本项目仅用于研究学习

> r20/t12 判读树与取证命令见 Release `raphael-touch-r20` 内 `FLASH-T12.md`（历史判读树 FLASH-T6~T11 保留在 docs/）。
