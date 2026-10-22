# t23（r33）刷写与判读 · 触摸冷启动重试阶梯（GT9886 PID 垃圾值破案）

> **r33 说明（2026-10-22）**：t23 = t22 底座（0001-0101 全保留）+ **0102-raphael-touch-coldboot-retry**。
> 本轮依据 = **你的 t22 实机日志的一锤定音判决**：
> - 触摸 IC 完全活着：`probe xfer addr=0x5d` 全部 `err=0`（ACK + 时钟拉伸都在，72 字节配置块都读得回来）。
> - 但 PID 读出 `[22 50 96 ba]`（正常应为 ASCII `"9886"` = `39 38 38 36`），且 72 字节版本块校验和 `sum=0x8a`（厂商固件保证为 0）。
> - 这两组寄存器都活在 **IC 的 RAM 镜像**里 → 固件根本没跑起来：驱动 reset 释放后只等 **300ms** 就去探测，芯片从 flash 引导固件输掉了这次竞速。
> - 这是**概率性**问题：t12→t21 十几次开机全部成功，t22 这一次输了。不是驱动退化、不是 t22 的显示/电池补丁波及（0100/0101 不碰 I2C/QUP/TLMM），纯粹是那 1/10 概率砸中了。
> - **0102（触摸）**：PID 不匹配时不再直接自杀，走**冷启动重试阶梯**——
>   - 第 1 次重试： rails 断电 200ms → 上电 → 稳定 50ms → reset 低 10ms → 释放 → 等 500ms（t22 是 100/20/2/300）；
>   - 第 2 次重试：再加长（300/100/10/500），并在 reset 上升沿把 **INT 拉高 strap**（经典 Goodix 引导选择带，释放回输入前只保持 1ms）；
>   - 每次重试都打 `retry N cold cycle …` + `GT9886 tryN pid …` 判决行；三次全败才停（日志留全证据）。
> - **亮度/充电本轮零改动**：你 t22 日志里 `sel 50 in (10000)` → `brightness 2047` 亮度和 `registering as AppleSmartBattery` 充电链路都在正常工作，保持原样。
> - 稳定版仍为 **r28/t12**（Latest 不变）。

## 刷写

```
fastboot boot raphael-t23-touchfix-clean.img   # 日常验证
# 或
fastboot boot raphael-t23-touchfix-debug.img   # 排障：屏幕控制台常开
```

## 判读树

### A. 触摸（本轮主角，一锤定音）

启动约 45-50 秒后（触摸驱动启动），看日志：

```
SWEET TOUCH: GT9886 try0 pid err=0 [39 38 38 36] sensor err=0 id=… ver err=0 sum=0x0   ← 首次即成（正常路径）
SWEET TOUCH: retry 1 cold cycle off=200 settle=50 low=10 boot=500 ms                    ← 重试阶梯介入
SWEET TOUCH: GT9886 try1 pid err=0 [39 38 38 36] … sum=0x0                              ← 重试成功！
SWEET TOUCH: doze disable err=… (staying awake for polling)
SWEET TOUCH: cfg send sensorN 784B err=0 flip=N
SWEET TOUCH: selected GT9886 normandy, 1080x2340, poll=10ms irq-hint=…
```

| 现象 | 含义 | 结论 |
|---|---|---|
| try0 就是 `[39 38 38 36]` sum=0x0 | 芯片这次正常引导（竞速赢了） | 触摸应直接可用 ✅ |
| try0 垃圾值 → retry 1 → **try1 变 `[39 38 38 36]` sum=0x0** | 冷循环加长时序治好了引导竞速 | **0102 生效，触摸恢复** ✅ 拍视频记录 |
| try0/try1 都败 → retry 2（带 INT strap）→ **try2 成功** | 更 stubborn 的状态也被第三档拉回 | 仍算全胜，回报两行 retry 判决行 |
| 三次全败：`pid is not 9886 after 3 cold boots (fw update path not built); stopping` | 芯片固件真的引导不起来（flash 层面问题） | 回报完整 try0-2 三行 → 下轮上固件升级路径（从 MIUI 提取 goodix 固件） |
| **实机判定**：锁屏界面用手指划动，能解锁/能点图标 | 用户态确认 | 无论日志走的是哪一档，触摸闭环 ✅ |

> 判定核心：**只要三次里任何一次 PID 变对，触摸就应该回来**——因为后续 bring-up（doze disable → 配置下载 → 0x4100 轮询）与 t12→t21 完全一致。

### B. 亮度（t22 已通，回归确认即可）

拖亮度滑条：`SWEET FB: backboardd sel 50 in 2/0 (NNNN 0 0 0)` → `SWEET FB: brightness NNN`，屏幕实时跟随 = 依旧全胜。本轮显示代码零改动，理论上与 t22 完全一致。

### C. 充电状态（t22 已通，回归确认即可）

插充电器 ≤5s 状态栏闪电 + `SWEET BATTERY: input plugin=1 … charging=1`。本轮电池代码零改动。

### D. 回归确认（不应变化）

- 按键：`SWEET HID: key 0x30 down/up`（你 t22 日志里按键本就正常）。
- 8 核：`8/8 CPUs initialized, SGI1 verified`。
- 息屏瞬时全黑 + 亮屏恢复（0100 的 instant-off + pending 亮度补发）。
- 缩放：启动行末尾 `(scaled)` 依旧。

### E. 风险与回退

本轮改动面 = 只在触摸探测块（新增两次冷循环 + INT strap）。INT strap 在 reset 上升沿保持 1ms 后立即交还输入态，与厂商 dev_confirm 时序兼容；重试路径完全复用 t22 验证过的 rail/GPIO/SE 代码。任何异常：

```
fastboot boot raphael-t22-bright-chg-clean.img    # 回上一测试轮（触摸差但亮度/充电好的版本）
fastboot boot <r28/t12 镜像>                       # 回稳定版
```

### F. 日志取证（不变）

```
adb shell dd if=/dev/block/by-name/userdata of=/tmp/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
```

（TWRP/OrangeFox 下可用 `tail -c 4198400 /dev/block/sda31 > /tmp/sweet-log.bin`，再 `adb pull`。）

### G. 本轮日志重点抓取清单（发我这些就够）

1. `SWEET TOUCH:` 开头的**全部行**（A 节判决——特别是 try0/try1/try2 三行 PID + sum）
2. 锁屏实际划一下的时段（让我们对上"触摸恢复"的时间戳）
3. 若三次全败：try0-2 的完整三行 + `bus idle/bus live` 两行
