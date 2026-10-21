# t10（r18）刷写与判读 · 触摸总线上电诊断 + 8 核恢复

## t9 实测结果（本版的出发点）

t9 **已成功越过 bootstrap**（kryo485 + 1-CPU ADT 修复成立），触摸探针**首次真正上车**：

```
SWEET TOUCH: probe 0x5d ver-reg err=60 id=a5a5a5a5 ...    ← 超时（ETIMEDOUT）
SWEET TOUCH: probe ST FTS 0x49 err=5 id=00:00 ...          ← EIO，且 tx=0
SWEET TOUCH: no supported IC (goodix=0 st-fts=0 dead=0); stopping
```

实锤两层结论：

1. **0x5d（GT9889）超时**：TX 水位中断触发（2 字节已入 FIFO）、abort 干净完成（序列器活着）、但**无 DONE/NACK = 总线上没有产生任何活动**。全链路静态审计（SE19@0xc88000、qup19=GPIO57/58 func2、vdd=GPIO98/avdd=GPIO100、reset=54/irq=122、寄存器/打包/命令编码 = Linux i2c-qcom-geni 逐项对齐）**全部正确**——问题在物理层：要么上拉轨（avdd）没真正起来、要么 IC/总线粘死。
2. **0x49（ST FTS）是纯软件 bug**：`touch_msg_run` 的 3 字节 TX 上限把 5 字节命令（0xFA+4 字节地址）直接拒了（err=5=EIO，tx=0 证明根本没上总线）。

另外：**卡 = 单核**。t9 为修 bootstrap 砍到 1 核，iOS 单核必然卡。

## t10 改了什么

| 部分 | 与 t9 的差异 |
|---|---|
| 内核 | +补丁 0091：① raphael 触摸上电改为**冷循环**（拉住 reset，98/100 双轨完整 off→on 一次，前一个 OS 留下的 IC 状态不可能存活）；② 新增两条**总线电平判读行**（`bus idle` / `bus live`）；③ ST FTS 5 字节传输修复（TX 上限 3→6、双字 FIFO 打包、轮询拆成写+读两条消息） |
| ADT | **恢复 t8 的 8-CPU ADT**（12588B，f50510e0）——8 核回归，卡顿应消失。安全性依据：t7 用同一个 8 核 ADT 正常跑，t8 卡死根因是 kryo470 失配（0090 已入库）而非 CPU 数量 |
| shim / DTB / 头 / cmdline | 与 t7/t9 逐字节不变（clean = t7 330B） |

## 刷写

```
fastboot boot raphael-t10-touchbus-clean.img   # 日常验证
# 或
fastboot boot raphael-t10-touchbus-debug.img   # 排障：屏幕控制台常开
```

## 判读树

### A. 启动层

1. **出锁屏且流畅**（日志应出现 `SWEET CPU: requested=8 selected=8`）→ 8 核恢复成功，卡顿问题关闭。
2. **卡 bootstrap** → 8 核 ADT 触发（kryo485 之外的第二个变量）→ 长按电源强制重启，`fastboot boot` 回 t9，回报即可（下一轮 2/4 核折半定位）。t 系列不落盘，无变砖风险。

### B. 触摸层（拉日志，重点看两条新行）

```
SWEET TOUCH: bus idle vdd=? avdd=? sda=? scl=? reset=? ios=?   ← 复位拉住时
SWEET TOUCH: bus live sda=? scl=? irq=? ios=?                  ← 复位释放+300ms 后
```

| 现象 | 含义 | 下一步 |
|---|---|---|
| `bus idle` 的 **sda=1 且 scl=1**（bit0=1）| 上拉轨活着、总线健康 | 若 probe 0x5d 仍 err=60 → 嫌疑转向串行时钟侧（DFS/RCG），下轮做时钟实验 |
| `bus idle` 的 sda 或 scl = **0** | **avdd（GPIO100）上拉轨没起来**或总线被拖死 → 供电路径问题 | 核对 98/100 读回值与极性、找真实供电轨 |
| `bus live` 的 sda=**0** 而 idle 时 =1 | IC 释放复位后主动拖死 SDA（从机卡事务） | 下轮加 I2C bus-clear（9 个 SCL 脉冲）序列 |
| `probe 0x5d` **err=0 且 id≠a5a5a5a5** | **GT9889 活了** | 触摸应直接工作，回报体验 |
| `probe ST FTS 0x49` **err=6（ENXIO/NACK）** | 0x49 无应答——goodix 机型正常现象 | — |
| `probe ST FTS 0x49` **err=0 且 id≠00:00** | 这台是 ST 二供屏 | 触摸走 ST FTS 只读链路 |

### C. 日志取证（不变）

```
adb shell dd if=/dev/block/by-name/userdata of=/tmp/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
```

（TWRP 下可用 `tail -c 4198400 /dev/block/sda31` 提取环区。）

### D. 回退

`fastboot boot` 回 **t9**（1 核、已知可启动）或 **t7**。

## 文件校验

| 文件 | SHA256 |
|---|---|
| `raphael-t10-touchbus-clean.img` | `e8cd3bc126670fdb2cb3bcd5cf4ee1a3f3b572a1ab53d49234dde0c378a2f857` |
| `raphael-t10-touchbus-debug.img` | `4cc1e957d9b84be1a2eb70af669e39d798e189c6aa7a7d630bbe5a2f1cd97a43` |

内核：`c8fdc4591494f5643d987aeb721a4083eb75aae5100d34ca1a3546d7c51497c8`（0091，CI run 39572579833）；ADT：t8 系 8 核（f50510e0…，12588B）。
