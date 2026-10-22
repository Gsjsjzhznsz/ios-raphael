# t20（r30）刷写与判读 · 整幅显示缩放 sweetscale（1125×2436 → 1080×2340）

> **r30 说明（2026-10-22）**：t20 = 0001-0096（t13/r29 底座）+ 新板级补丁 **0097-raphael-display-sweetscale**。
> - **缩放机制**：iOS 按 iPhone X 几何渲染 1125×2436（日志 `swap layer 0 surface 1125x2436`），驱动内置逐列/逐行最近邻映射表（中心对齐）把整幅画面缩到 1080×2340 物理面板——**顶部时间/电量两角不再被居中裁剪切掉**。cmdline 无 `sweetscale` 参数 → 默认 scale=1 开启；补丁保留 `sweetscale=0` 回退居中裁剪路径。
> - **本补丁是历史 0098 的仅缩放子集**（字节级拆分，scripts/t20_make_patch.py）：亮度 DCS / 即时息屏 / externalMethod 调参日志三件 0098 搭车件全部排除，构建校验以 `SWEET FB: brightness` 等 16 项标记强制缺席作为拆分证明。
> - **历史存档**：t14 时代的缩放从未被肉眼验证——历轮 USB 楔死都发生在用户态可见之前（t17 时代结论），**本版是该功能的首次真机视觉测试**。t13/t14 已证"不探测 USB 时系统无限稳定"：t20 沿用 t12 cmdline（`sweetusb=0`），处于该稳定域。
> - 稳定版仍为 **r28/t12**（Latest 不变）；上一测试轮 r29/t13 继续在架。

## t12/t13 时代的问题（本版的出发点）

稳定版 t12 为**居中裁剪**模式：1125×2436 的逻辑画面 1:1 映射到 1080×2340 面板，左右各切 ~22px、上下各切 ~48px——**状态栏时间/电量正好在切口上**（README 实锤）；显示缩放（设置里的标准/放大）两种模式渲染同一画布、裁剪固定，所以"无效"。t14 曾随 USB 轮打包此修复但从未被肉眼验证（见上）。

## 刷写

```
fastboot boot raphael-t20-sweetscale-clean.img   # 日常验证
# 或
fastboot boot raphael-t20-sweetscale-debug.img   # 排障：屏幕控制台常开
```

## 判读树

### A. 显示层（本版主角）

启动判决行（缩放表已建的直接证据）：

```
SWEET FB: AppleCLCD 1080x2340 stride … , presented as 1125x2436 (scaled)
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| 顶部时间/电量**完整显示**、状态栏不再被切 | 缩放生效 | 全胜 |
| 启动行末尾带 `(scaled)` | 缩放表已建 | 对照上一行 `1080x2340 stride …` |
| 画面整体轻微"颗粒感" | 最近邻缩放的正常代价（0.96 倍降采样） | 属预期 |
| 设置里"标准/放大"切换有视觉变化 | 缩放模式下 Display Zoom 真实生效 | 全胜 |
| 顶角仍被切、启动行**无** `(scaled)` | 缩放没生效（罕见：`sweetscale` 被显式置 0？） | 回报启动行 |
| 画面撕裂/局部错位 | 部分更新矩形缩放舍入 | 回报现象+日志，可加边缘对齐 |
| 滑动掉帧加重 | CPU 逐像素缩放的正常代价（无 GPU） | 属预期；回报具体场景可优化映射表 |

### B. 触摸层（回归确认，不应变化）

```
SWEET TOUCH: GT9886 pid err=0 [39 38 38 36] sensor err=0 id=0x1 ...
SWEET TOUCH: cfg send sensor1 784B err=0 flip=0
```

依旧正常即回归通过。若异常回报上述行。

### C. 电池层（继承 t13，不应变化）

```
SWEET BATTERY: probe type=0/0xd sys=0/0x0 msoc=…,…(N%) v=… i=… usb=…
```

fg-gen4 读数与 30s 轮询随 0096 一并继承；本版未动电池路径，判读同 FLASH-T13.md。

### D. 启动层

8 核不变（`8/8 CPUs initialized`）；万一卡 bootstrap（理论不可能：本版只动了显示路径）→ 强制重启回 **t12/r28** 回报。

### E. 日志取证（不变）

```
adb shell dd if=/dev/block/by-name/userdata of=/tmp/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
```

（TWRP 下可用 `tail -c 4198400 /dev/block/sda31` 提取环区。）

### F. 回退

`fastboot boot` 回 **t12 / r28 稳定版**（已知可用：8 核 + 触摸闭环 + 电池探针 + v2 头）；或上一测试轮 **r29/t13**。

## 文件校验

| 文件 | SHA256 |
|---|---|
| `raphael-t20-sweetscale-clean.img` | `e32618b9b94803ca2df80612dec599a9abb3ab6cb7bd058a5ca91b456bee5df8` |
| `raphael-t20-sweetscale-debug.img` | `6c272111370ee41ecf1efe769e74587b41fb7ab44aca9571f5a86acb79523c19` |

内核：`7440577a1feaa6c969ef5a2941484dba51bb8b4334839564ec8ea525fe921577`（补丁 0001-0097，CI run #40 @ a7aed26）；ADT：t8 系 8 核（f50510e0…，12588B）；cmdline：与 t12 逐字节相同（无 `sweetscale` → 缩放默认开启；`sweetusb=0` 保持 USB 休眠）。
