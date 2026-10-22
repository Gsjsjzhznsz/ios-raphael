# ios-raphael — iOS 16 on Redmi K20 Pro (raphael)

[English version below](#english)

把 Apple 的 XNU 内核 + iOS 16.7.16 用户态跑在红米 K20 Pro（代号 **raphael**，高通 SM8150 / 骁龙 855）上的移植实验。基于上游 [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet)（已在 sweet / Redmi Note 10 Pro 点亮 iOS 主屏），本项目为 raphael 做全套硬件适配：触摸、电池、显示、USB、八核。

> ⚠️ **警告 / Warning**
> 本项目为实验性质，操作会**彻底清空手机全部数据**，严禁在主力机上操作！
> This project is experimental. Flashing **erases all phone data**. Never use your daily driver.

## 📊 当前状态（2026-10-22）· 稳定版 r28/t12（t14~t19 实验轮已废弃回退）

| 子系统 | 状态 | 说明 |
|---|---|---|
| 引导链 | ✅ 实测可用 | shim → XNU → iOS 锁屏完整启动（`fastboot boot` 免落盘，重启即回安卓引导） |
| CPU | ✅ 8 核实测 | `8/8 CPUs initialized`（kryo485 匹配表 + PSCI 二次核拉起） |
| 显示 | ✅ 点亮（稳定版 t12 为居中裁剪；t20 缩放 / t21 / t22 测试轮在架） | 原生 1080×2340 面板；整幅缩放修复已作为 **t20/r30 测试轮** 发布（sweetscale 最近邻映射表，历史 0098 的仅缩放子集，1125×2436 整幅缩到 1080×2340，顶部时间/电量不再被切）；**t21/r31 测试轮**上 0098 的亮度 DCS + 即时息屏子集；**t22/r32 测试轮**实锤亮度真通路 = IOMFB **sel 50 setBrightnessCorrection**（t21 日志捕获 backboardd 调用 `sel 50 (10000)`，0..10000 满刻度），感知表映射到面板 DCS 0x51 电平 4..2047；DSI 存活改双控制器（ctrl0/ctrl1）真实命令自证，不再信 ctrl 使能位 |
| 触摸 | ✅ 实测可用（t22 出现概率性冷启动竞速：PID 垃圾值→驱动自杀；**t23/r33** 冷启动重试阶梯在架） | GT9886 厂商级 bring-up：真寄存器图 + 784 字节面板配置下发（双供应商）+ doze 控制；t23 = PID 不匹配时冷断电重试（×2 加长时序 + INT strap），三次全败才停 |
| 电池 | 🔶 探针读通（稳定版 t12）；充电监视 t21 / AppleSmartBattery 注册 t22 测试轮在架 | PM8150B 读通（probe type=0xd）；fg-gen4 真实读数（SOC/电压/电流）为 t13 系（稳定版不含）；**t21/r31 测试轮**上 5s 充电输入监视（USBIN 插拔 + CHGR 状态，插拔 5s 内 publish 到 iOS 状态栏）+ 插拔瞬间 SMB5 输入侧一行全dump（APSD/ICL/power-path/STATUS5）；**t22/r32**：服务以 iOS 状态栏查找的名字注册（personality name = AppleSmartBattery，类名仍 SweetBattery）——t21 日志实锤内核侧插拔/APSD/ICL/FULLON 全通，本轮赌名字匹配；t22 实机日志确认 `registering as AppleSmartBattery` 判决行在场、用户本轮未再报充电缺失 |
| 亮度 / 息屏 | ❌ 稳定版未含 | DSI DCS 亮度通道与息屏立即全黑系 t14 实验功能（已随回退移除），稳定版为多步渐暗 |
| USB | ⛔ 已废弃（t14~t19 回退，稳定版无 USB） | 实验轮推进至 t19 三项硬件级修复即全线回退（历史细节：源码深挖+官方源裁决推翻 t18 判读——①"字节复制×4"读值（REFCLK 写 0x2 读回 0x02020202）是 **AHB2PHY 桥（0x6a004）访问降级**特征，非轨未上电（0103 三票经 raphael 官方板级 dtsi 验证对象/电压/编码全对）；②**QUSB2PHY_PRIM_BCR 真偏移 0x26000**（raphael 官方 GCC 复位表；主线 0x12000 在此硅片不存在，t17/t18 一直在脉冲空气）；③**GUSB3PIPECTL.SUSPHY(0xc2c0 bit17) 从未清除**（Qualcomm 9bdbd5286ea5：遗留=寄存器写失败→整机崩溃；t16 无 femto 也楔死吻合）。控制台几何定案（fbcon 环绕+清屏）：所有照片都是单次启动单次 probe，光标冻在 ep0 print，其后两行空白=从未写过；t16 重读证明 ep0 后系统继续跑完启动——**只楔死 CPU0**，45s 触摸线程撞毒化 NoC → RPM/TZ 热复位 = 40-50s 重启完整因果链。t19：ahb2phy 桥使能 + 双 BCR 脉冲 + U3 SUSPHY 清除 + 20ms settle + **降级中止**（失败=稳定锁屏+照片，45s 重启循环机制性终结）+ `SWEET RST:` PON 复位分类器（SPMI 只读） |
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
| `raphael-t12-gt9886-clean.img` | **当前首刷推荐（r28 稳定版）**：8 核（cmdline cpus=8 + ADT 8×kryo485）· GT9886 触摸闭环（784B 面板配置下发，实测可用）· 电池探针 · v2 头正确打包 · 逐字节复用实测可用的原 r20 资产（零改动） |
| `raphael-t12-gt9886-debug.img` | r28 排障版：同 clean 但**屏幕控制台常开**（仅改 1 字节 sweetfb_noconsole=0） |
| `raphael-t13-fggen4-clean.img` | **上一测试轮（r29）**：t13 fg-gen4 硬件电量计重建版——稳定版底座上真电池读数（monotonic SOC / 实测电压电流 + SMB5 充电语义 + 30s 轮询）；内核由回退树 CI 重建（标记集验证），v2 头工具链字节级验证 |
| `raphael-t13-fggen4-debug.img` | r29 排障版：同 clean 但**屏幕控制台常开**（仅改 1 字节 sweetfb_noconsole 1→0） |
| `raphael-t20-sweetscale-clean.img` | **当前测试轮（r30）**：整幅显示缩放——1125×2436 最近邻缩到 1080×2340（逐列/逐行映射表，中心对齐），顶部时间/电量两角不再被居中裁剪切掉；历史 0098 的仅缩放子集（亮度/息屏/日志搭车件全部排除）；首次真机视觉测试（t14 时代该功能从未被肉眼验证） |
| `raphael-t23-touchfix-clean.img` | **当前测试轮（r33）**：触摸冷启动重试阶梯 —— t22 日志破案：IC 在 0x5d 完全活着（全部 xfer err=0）但 PID `[22 50 96 ba]`（正常 "9886"）+ 版本块和 0x8a（应为 0）→ 固件没跑起来，reset 后 300ms 探测抢跑 flash 引导（概率性，t12→t21 十余次全胜、t22 输了一次）。0102：PID 不匹配时不再自杀，冷断电重试两档（200/300ms 断电 + 50/100ms 稳定 + 10ms reset 低 + 500ms 引导窗），第三档加 INT 上升沿 strap；每档打 `retry N cold cycle` + `GT9886 tryN pid` 判决行；三败才停留全证据 |
| `raphael-t23-touchfix-debug.img` | r33 排障版：同 clean 但**屏幕控制台常开**（仅改 1 字节 sweetfb_noconsole 1→0） |
| `raphael-t22-bright-chg-clean.img` | **上一测试轮（r32）**：亮度真通路 + 电池服务名 —— ① IOMFB **sel 50 setBrightnessCorrection**（0..10000 → DCS 0x51 电平 4..2047 感知映射；sel 50 每次调用必记日志）；② DSI 存活探测重构：ctrl0→ctrl1 各试 DCS 0x29，谁完成 command DMA 谁是宿主（t21 实锤 ctrl 使能位不可信）；③ DSI 未通时亮度请求记忆 pending、亮屏自动补发；④ setProperties dump 全部键名；⑤ 电池以 **AppleSmartBattery** 名字注册（判决行 `registering as AppleSmartBattery`） |
| `raphael-t22-bright-chg-debug.img` | r32 排障版：同 clean 但**屏幕控制台常开**（仅改 1 字节 sweetfb_noconsole 1→0，位 @0x33160） |
| `raphael-t21-bright-chg-clean.img` | **上一测试轮（r31）**：亮度/息屏 + 充电监视 —— ① DSI ctrl0 DCS 通路：亮度 0x51（11 位大端 ≤2047）、息屏/点亮 0x28/0x29；② **即时息屏**（一次黑帧 + 面板真睡眠，`sweetfb_fade=1` 回旧渐暗）；③ setProperties 亮度钩子 + user client 转发（Apple IOHIDEventServiceUserClient 同款）；externalMethod 日志升级为每 selector 前 3 次并带标量值（亮度通路猎取）；④ 电池 5s 充电输入监视 + 插拔转移一行全dump（inputCheck 抢先缓存 bug 已修） |
| `raphael-t20-sweetscale-debug.img` | r30 排障版：同 clean 但**屏幕控制台常开**（仅改 1 字节 sweetfb_noconsole 1→0） |
| `raphael-t21-bright-chg-debug.img` | r31 排障版：同 clean 但**屏幕控制台常开**（仅改 1 字节 sweetfb_noconsole 1→0） |
| ~~`raphael-t19-ahb2phy-bcr-clean.img`~~ | ⚠️ **勿刷（r27）**：v1 头打包错误（本机 ABL 只接受 v2 头），实测黑屏；USB 供电轮 t14~t19 已全线废弃回退 |
| `ios16-root.simg.part-00 ~ 05` + `CHECKSUMS.txt` | iOS 16.7.16 rootfs（16G HFS+ 稀疏镜像分卷，**rootfs 无需重刷**，与 t 系列内核通用） |

> 项目内核迭代极快，**每次刷机请务必下载最新版本**。
> 历史镜像哈希（回退参考）：

```
t7-clean:  91abcc1be3bce986606500a8003576d1c01fc31ee9348af9659e75c5583559fe （r15 已删除，稳定位由 t12 接替）
t12-clean: 3725736f0773ede73b59a35d1cabddc92decbc58aaa37f8a375fa09d46459c6b （r28 稳定版，当前推荐）
t12-debug: 73f1d0ff7656b2e9ce5b52c7d2f274c33fb811a15142910442a410c4da45f46e
t13-orig-clean: 3d31006ca3c318779e5a0c21e4d6dee2ed65c7a1125b50acc26c2c8f8aa8c23f （原版 r21，资产已失传，仅供历史对照）
t13-clean: 82c71576bb58b9279e71ddcc03335a1e66a858679abb4d3abac9d65fe88044e4 （r29 重建版，v2 头正确打包，当前测试轮）
t13-debug: 4f1f5f65cd96463030729ffdba8787ad8c880dd4aff5a4641bd8fa0c1430770d （同上）
t20-clean: e32618b9b94803ca2df80612dec599a9abb3ab6cb7bd058a5ca91b456bee5df8 （r30 整幅缩放，v2 头正确打包，当前测试轮）
t20-debug: 6c272111370ee41ecf1efe769e74587b41fb7ab44aca9571f5a86acb79523c19 （同上）
t23-clean: d3af5724cc1189614e55b6915e4d6287cfbe7cc391b84842930e0293c7698938 （r33 触摸冷启动重试阶梯（GT9886 PID 垃圾值破案），当前测试轮）
t23-debug: 014f2d2d4bb170c958bbd9673ffbafb4c758a2859f82010d7aa1d6e1c337c9ca （同上）
t22-debug: 0b4fa757aef9a568e8412cba4b80226b1289403d0f427cd380962866ab13326f （同上）
t21-clean: 312259a106a89c2cbfa2f534123576ef5e409948a2f9c7001cd055ed88d02bcb （r31 亮度DCS+即时息屏+充电5s监视，上一测试轮）
t21-debug: e7f19586cbcb641dbe7efe0f21db69fd8a68ff21ef032ceec27ad8144a28bc09 （同上）
t14-clean: 3374ac69efb17155de6a61792e5753053c25669317bb5464aa5fa284e8da3a3c （USB 挂死，勿刷）
t18-clean: a16e17250b16f6b253085175922e196ec626f898d2165b7b811a996f69fa29ee
t18-debug: 6f165dca80db7e34021f3f3b6cb020f5127ee108475cb5a5efe76f2c241dcd91
t19-clean: 593691d1a168069967581ce8ed62bef3cf39ffeb97f8a3cc802a3589514c1fce （v1 头打包错误，黑屏，勿刷）
t19-debug: 6097c99aa6a800d82f3a2ec639d8624557501a3c660ce72755b818c012a99557 （同上，勿刷）
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
- t19 预期：开机第一行 `SWEET RST:`（分类上一次复位——t18 的 45s 之谜当庭宣判）→ `ahb2phy CBCR ... (on)` → `pre-state` **不再是重复字节** → 三票 → `post-LDO` → `hsphy up (femto)` 回读正常 → `U3 SUSPHY cleared` → `canary` → `ep0 setup TRB armed` → `running`；进锁屏后主机（Termux 手机）枚举 USB 网卡，`ping 192.168.7.2` 通 = **USB 全胜**（45 秒重启应随之消失）。若仍失败：`register file degraded ... aborted` 后**稳定锁屏不再重启**，拍 `ahb2phy`/`pre-state`/`up (femto)` 三行照片即可自分类（判读树见 FLASH-T19）。
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

## Status (2026-10-22) — stable r28/t12 (t14–t19 experimental rounds reverted)

- ✅ Boot chain proven on device: shim → XNU → iOS lock screen (`fastboot boot`, nothing permanent)
- ✅ All 8 cores (`8/8 CPUs initialized`)
- ✅ Display lit (stable t12 center-crops: the 1125×2436 frame is cropped, cutting the top clock/battery corners; the whole-frame scaling fix is now published as the t20/r30 test round — sweetscale nearest-neighbour maps, see Downloads)
- ✅ Touch (GT9886 vendor-grade bring-up, confirmed working; t22 hit a probabilistic cold-boot race — garbage PID killed the driver; **t23/r33** adds a cold-boot retry ladder, test round available)
- 🔶 Battery probe reads the PM8150B (type=0xd); the fg-gen4 real gauge (SOC/voltage/current) and charger polling are t13 features — kept out of the stable image, but the t13 rebuild is now published as the current test round (r29); the stable image still reports static values
- ❌ Not in the stable image: brightness DCS channel and instant screen-off were t14 experimental features (reverted); the stable image keeps the old multi-step fade
- ⛔ USB: abandoned (t14–t19 reverted; the stable image has no USB gadget). History — the experimental line reached t19's three hardware-level fixes: the t18 reading was overturned by source verification — the byte-replicated x4 readbacks (REFCLK written 0x2, read back 0x02020202) are a degraded AHB2PHY-bridge signature, not unpowered rails (the 0103 votes were verified correct against raphael's own board dtsi: pm8150 l5/l12/l2); the real QUSB2PHY_PRIM_BCR is at 0x26000 (raphael's gcc table; mainline's 0x12000 does not exist on this silicon — t17/t18 pulsed a no-op); GUSB3PIPECTL.SUSPHY (0xc2c0 bit 17) was never cleared (Qualcomm 9bdbd5286ea5). Console geometry settled (ring fbcon, cleared at boot): every photo is one boot, one probe; only CPU0 wedges at the first ep0 command and the 45 s touch thread escalates it to a warm reset. t19: enable the ahb2phy branch, dual BCR pulse, clear U3 SUSPHY, 20 ms settle, degraded-readback abort (failure = stable lock screen, never the 45 s reboot loop), plus a `SWEET RST:` PON reset classifier (read-only SPMI)
- SPMI command gate and GPIO census were t15 experimental features (reverted); the stable image keeps the pre-gate observer paths
- ❌ No GPU driver (CPU software rendering, UI is slow), no Wi-Fi/BT/camera/audio/modem yet

## Downloads (Releases)

| File | Purpose |
|---|---|
| `raphael-t12-gt9886-clean.img` | **Recommended (r28 stable)**: 8-core (cpus=8 + 8×kryo485 ADT nodes) · GT9886 touch closed-loop (784-byte panel config, verified on device) · battery probe · byte-identical reuse of the verified r20 asset (zero modification) |
| `raphael-t12-gt9886-debug.img` | Same, with the on-screen console always on (1-byte cmdline patch) |
| `raphael-t13-fggen4-clean.img` | **Previous test round (r29)**: the t13 fg-gen4 hardware fuel gauge, rebuilt — real battery readings on top of the stable base (monotonic SOC / measured V-I + SMB5 charger semantics + 30 s polling); kernel rebuilt by CI on the rolled-back tree (marker-verified), packaged on the byte-proven v2 chain |
| `raphael-t13-fggen4-debug.img` | r29 troubleshooting build: same clean, on-screen console always on (1-byte patch) |
| `raphael-t20-sweetscale-clean.img` | **Current test round (r30)**: whole-frame display scaling — 1125×2436 nearest-neighbour-scaled to 1080×2340 (per-column/per-row maps, centres aligned), so the top clock/battery corners are no longer cropped; the scale-only subset of the historical 0098 (brightness/instant-off/logging all excluded); the first on-device visual test of this feature |
| `raphael-t23-touchfix-clean.img` | **Current test round (r33)**: touch cold-boot retry ladder — the t22 log cracked it: the IC is fully alive at 0x5d (every xfer err=0) but PID read `[22 50 96 ba]` (expected "9886") with the 72-byte version block summing to 0x8a (vendor guarantees 0x00) -> the flash firmware had not started when the driver probed 300 ms after reset release (probabilistic race; t12..t21 all won it, t22 lost). 0102: on a PID mismatch no more instant surrender — redo the cold power cycle twice with longer settle windows (200/300 ms rails-off, 50/100 ms settle, 10 ms reset-low, 500 ms boot window), the third attempt also straps INT high across the reset rising edge; every attempt logs `retry N cold cycle` + `GT9886 tryN pid` verdict lines; stop only after 3 failed cold boots |
| `raphael-t23-touchfix-debug.img` | r33 troubleshooting build: same clean, on-screen console always on (1-byte patch) |
| `raphael-t22-bright-chg-clean.img` | **Previous test round (r32)**: the real brightness channel + battery service name — ① IOMFB **sel 50 setBrightnessCorrection** (0..10000 -> panel DCS 0x51 level 4..2047 via a perceptual table; sel 50 logged on every call); ② DSI liveness probe reworked: ctrl0 then ctrl1 each get one DCS 0x29, the first host completing a command DMA wins (t21 proved the ctrl enable bit lies); ③ brightness requests remembered while the DSI path is down, applied at the next display-on; ④ setProperties dumps every key; ⑤ battery registers under the name **AppleSmartBattery** (verdict line `registering as AppleSmartBattery`) |
| `raphael-t22-bright-chg-debug.img` | r32 troubleshooting build: same clean, on-screen console always on (1-byte patch @0x33160) |
| `raphael-t21-bright-chg-clean.img` | **Previous test round (r31)**: brightness/instant-off + charging watch — ① DSI ctrl0 DCS path: brightness 0x51 (11-bit big-endian ≤2047), display off/on 0x28/0x29; ② **instant display off** (one black memset + real panel sleep, `sweetfb_fade=1` restores the legacy fade); ③ setProperties brightness hook + user-client forwarding (same pattern as Apple's IOHIDEventServiceUserClient); externalMethod logging upgraded to the first 3 uses per selector with scalar values (brightness-path hunt); ④ battery 5 s charger-input watch + one-line SMB5 input dump on plug transitions (inputCheck ahead-caching bug fixed) |
| `raphael-t20-sweetscale-debug.img` | r30 troubleshooting build: same clean, on-screen console always on (1-byte patch) |
| `raphael-t21-bright-chg-debug.img` | r31 troubleshooting build: same clean, on-screen console always on (1-byte patch) |
| ~~`raphael-t19-ahb2phy-bcr-clean.img`~~ | ⚠️ **Do NOT flash (r27)**: v1-header packaging bug (this ABL only accepts v2 headers) — black screen; the t14–t19 USB line is fully reverted |
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
4. **Boot**: `fastboot boot raphael-t19-ahb2phy-bcr-clean.img`, wait **4–8 minutes** for the lock screen. The body staying warm is normal; do not force-reboot early. Touch works; expect software-rendering lag. **Power the phone fully off before fastboot** after any crash/abnormal boot — PMIC state survives warm reboots.

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
- Patch series 0001–0096 (repo tree): early console, persistent log ring, USB bring-up, raphael display/touch/battery (0090 kryo485 match, 0093 TLMM-south, 0094 GT9886 config download, 0096 fg-gen4 gauge); experimental 0097–0104 (charger polling, display scaling, USB gadget rounds) were reverted — see git history. The r28 stable image is the t12-era kernel (0001–0095)

## Credits

- [dipa-studio/ios-sweet](https://github.com/dipa-studio/ios-sweet) — upstream project and rootfs pipeline
- [MakrSas/ios-topaz](https://github.com/MakrSas/ios-topaz) — sibling port (Redmi Note 12 4G) used for cross-checking
- The XNU kernel and iOS userspace are © Apple Inc. This project is for research only.

> 判读树与取证命令：Release `raphael-touch-r26` 内 `FLASH-T18.md`（历史判读树 FLASH-T6~T17 保留在 docs/）。
