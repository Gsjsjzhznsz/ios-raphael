# t11（r19）刷写与判读 · 触摸根因修复（TLMM SOUTH tile）+ 电池真实读数

## t10 实测结果（本版的出发点）

t10 **8 核全部复活**（`SWEET CPU: requested=8 selected=8` → `8/8 CPUs initialized`），bootstrap 问题关闭、卡顿问题关闭。电池与触摸判决行全部到位：

```
SWEET TOUCH: bus idle vdd=0 avdd=0 sda=0 scl=0 reset=0 ios=0   ← 六个读数全是 0
SWEET TOUCH: bus live sda=0 scl=0 irq=0 ios=0                  ← 仍然全 0
SWEET TOUCH: probe 0x5d ver-reg err=60 ...                      ← 超时
SWEET TOUCH: probe ST FTS 0x49 err=60 id=00:00                  ← 也超时（0091 修复后命令真的发出去了）
SWEET BATTERY: static fallback, 100% 4200mV external=1 charging=0   ← 电池是假数据
```

两层定论：

1. **触摸根因找到了——不是供电、不是总线、是 GPIO 寄存器基址错了**。SM8150 的 TLMM 不是 0x03000000 处的一整块平坦空间：每个 GPIO 的寄存器在 `TLMM基址 + tile偏移 + 0x1000×GPIO编号`，其中 WEST=0x00100000 / EAST=0x00500000 / NORTH=0x00900000 / **SOUTH=0x00D00000**（pinctrl-sm8150.c 实锤）。触摸用的 6 个 GPIO（54/57/58/98/100/122）**全部在 SOUTH tile**，即真正的 GPIO 窗口在 **0x03D00000**。驱动从 0083 起一直映射 0x03000000 本身——那是整个 TLMM 区开头 0x100000 的**未实现空洞**，读全零、写无效。所以：触摸 IC 从未上电、SDA/SCL 从未复用到 qup19、所有探针必然超时。t10 的"全零"判决行就是为这一刻准备的。
2. **电池"识别错误"的真相**：内核一直走 `static fallback`（boot-args `sweetbattery=0`，电池驱动关闭，上报写死的 100%/4200mV/外接电源）。所以 iOS 里电池永远 100%——不是识别错，是根本没读。

## t11 改了什么

| 部分 | 与 t10 的差异 |
|---|---|
| 内核 0093（根因修复）| GPIO 窗口改为 **SOUTH tile 0x03D00000**（0x80000 覆盖 GPIO 0–127，gpio122 的 IN_OUT 止于 0x7a004）。此后 mux / 供电轨 / 复位 / 中断读回全部落在真实寄存器上。启动行改为 `mapping GCC/TLMM-south/SE7`（正向标记，证明 0093 生效）|
| 内核 0092（电池）| PM8150B fuel gauge（fg-gen4 QG，SPMI **SID 2**，peripheral 0x40）真实电压/电流/电量读数 + SMB5 充电器状态（USB 插入/充电态/过温）；容量按 raphael 原厂 4000mAh F11 电池。锁屏/状态栏电池 = 真实值 |
| cmdline | `sweetbattery=0` → **`sweetbattery=1`**（电池驱动上车）。其余与 t10 逐字节一致 |
| ADT / shim / DTB / 头 | 与 t10 逐字节不变（8 核 ADT f50510e0）|

## 刷写

```
fastboot boot raphael-t11-battery-clean.img   # 日常验证
# 或
fastboot boot raphael-t11-battery-debug.img   # 排障：屏幕控制台常开
```

## 判读树

### A. 启动层

1. **出锁屏且流畅**（`SWEET CPU: requested=8 selected=8`）→ 与 t10 一致即正常（0093 不触碰启动路径）。
2. 万一卡 bootstrap → 长按电源强制重启回 t7，回报（理论上不可能：改动只有 GPIO 基址与电池）。

### B. 触摸层（先确认标记，再看电平，再看探针）

```
SWEET TOUCH: mapping GCC/TLMM-south/SE7        ← 有"TLMM-south"字样 = 0093 内核在跑
SWEET TOUCH: bus idle vdd=? avdd=? sda=? scl=? reset=? ios=?
SWEET TOUCH: bus live sda=? scl=? irq=? ios=?
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| `bus idle` vdd≥2 avdd≥2（bit1=输出已写 1）| 供电轨 GPIO 指令真正落到了寄存器 | 供电路径打通 |
| `bus idle`/`bus live` **sda=1 且 scl=1** | 上拉活着、总线健康 | 看探针行 |
| `probe 0x5d` **err=0 且 id≠a5a5a5a5** | **GT9889 应答** | **触摸应当直接工作，上手滑** |
| `probe 0x5d` err=6（ENXIO/NACK）| 总线活着但 0x5d 无应答 | GT9889 可能在备用地址或 IC 异常，回报日志 |
| `probe ST FTS 0x49` err=6 | goodix 机型正常（0x49 无器件）| — |
| `probe 0x5d` 仍 err=60 **且** sda/scl=0 | 寄存器对了但 avdd 轨仍没电（GPIO 使能≠电源轨真起来）| 回报 `bus idle/live` 全行，下轮查供电轨真身（RPMh/LDO）|
| `bus live` sda 从 1 变 0 | IC 释放复位后拖死总线 | 下轮加 bus-clear（9 个 SCL 脉冲）|

### C. 电池层（iOS UI + 日志双重判读）

锁屏/设置里看电池：**不再是恒定 100%**，显示真实电量；插线后出现充电态即全面成功。日志侧：

| 日志行 | 含义 |
|---|---|
| `SWEET BATTERY: PM8150B QG / estimated SOC, XX% XXXXmV external=? charging=?` | **真实读数上车**（百分比/电压随实际变化）|
| `SWEET BATTERY: static fallback, ...` | QG 读取失败，仍在走假数据 → 回报 |
| `SWEET BATTERY: SPMI mapping failed` / `unsupported SPMI arb=...` / `SPMI timeout ...` | SPMI 通道问题 → 回报具体行 |

### D. 日志取证（不变）

```
adb shell dd if=/dev/block/by-name/userdata of=/tmp/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
```

（TWRP 下可用 `tail -c 4198400 /dev/block/sda31` 提取环区。）

### E. 回退

`fastboot boot` 回 **t7**（已知可用：8 核 + 按键，无触摸/电池修复）。

## 文件校验

| 文件 | SHA256 |
|---|---|
| `raphael-t11-battery-clean.img` | `bd75bc2d0a0db479f4295bfe80ecab85276a80b3258ac27ff746723fe902cf12` |
| `raphael-t11-battery-debug.img` | `df4690b644df0699bb917841b9dda1eadf3292558e93f4ec8d5283a90e705aab` |

内核：`63dba04e678c2db0c2d1308708e9f5d698a3f204fb4d836123adde41573e58f4`（0092+0093，CI run 39582204279）；ADT：t8 系 8 核（f50510e0…，12588B）。
