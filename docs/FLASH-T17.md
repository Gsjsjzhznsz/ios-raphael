# t17（r25）刷写与判读 · 7nm HS PHY 完整启动（femto bring-up）

## t16 实测结果（本版的出发点）

t16 开机：**0099/0101 面包屑全部通过，走得比 t15 更远**——DLIL/Skywalk 全过、UFS 挂载 userdata、`ue0 192.168.7.2/24 up (err 0)` 都出来了，然后**整机冻结、约 40 秒后自动重启**。你拍的照片经环绕控制台几何重排（这次指针正好在环绕点上，整屏 72 行完美时序重建），死点看得一清二楚：

```
[SUSPHY] 0x00102400 -> 0x00102400（冷启动本来就清）      ← 0101 生效
[QSCRATCH] HS_PHY_CTRL 0x00000000 SS_PHY_CTRL 0x00000000  ← ★ USB 块被重置过！
[VBUS override] 写入 0x10100000/0x61000000 成功
[软复位] 1ms 完成 → [settle] → [事件缓冲] → [canary 0x00000000 ← 读通了！]
[ep0 DEPSTARTCFG...]                                        ← ★ 冻死在这
```

**关键证据链**：
1. **canary 纯读通过**（0x00000000 正常值）——端点寄存器块的 AHB 读通道活着
2. **第一条命令写楔死**（无 timeout 打印 = 总线级）——写操作要启动端点命令状态机，那个状态机**用 PHY 提供的 UTMI 时钟**
3. QSCRATCH 全零 = 你这次彻底关机后冷启动，**ABL 交接时把 USB 块重置了、PHY 处于断电状态**（上次 t15 是热启动，PHY 是"挂起"状态——两种状态，同一个死法）

结论：**ABL 留下的残局永远不够用，PHY 必须像 Linux 那样每次开机从头启动**。这正是 Linux 在 raphael 上 USB 能用的根本原因。

## 本轮逆向研究（你要求的 K20 Pro 项目调查）

- **找到并确认了正确的 PHY 驱动**：sm8150 的 HS PHY 是 7nm Synopsys "femto"（`phy-qcom-snps-femto-v2.c`）。**上一轮我参考的 qusb2-v2 驱动是错的**（那是老一代 10nm PHY 的），旧诊断打印读的偏移在这代 PHY 上根本不存在——本轮已修正
- **howtocuddle/xiaomi_raphael**：真实日用级 K20 Pro mainline 项目（真机跑 Gentoo + 6.18 内核），其 sm8150.dtsi 证实 PHY 节点 = `ref` 时钟直取 CXO + `GCC_QUSB2PHY_PRIM_BCR` 复位
- **vendor 与 mainline DTS 双重证实**：raphael 的 USB 就是 **high-speed 单 PHY 方案**（QMP USB3 PHY 显式禁用/移除）——不用碰 QMP，femto HS PHY 就是全部
- **vendor 板级调优参数拿到**：`param-override-seq`（OVERRIDE_X1=0x83、X2=0x2c）已按字节嵌入

## t17 做了什么（补丁 0102）

**寄存器级 1:1 移植 Linux `qcom_snps_hsphy_init()`**，插在 SUSPHY 清除之后、QSCRATCH/软复位之前（与 Linux `dwc3_core_init` 的 phy_setup → phy_init → soft reset 顺序完全一致）：

| 步骤 | 内容 |
|---|---|
| PHY 复位脉冲 | `GCC_QUSB2PHY_PRIM_BCR`(0x12000) 拉高 150µs 再释放 |
| 15 步 femto 序列 | CFG0 覆盖使能 → POR=1 → FSEL=000 → PLLBTUNE → REFCLK_SEL=10b → VBUSVLDEXTSEL0/VBUSVLDEXT0 → 板级调优 X1/X2 → VREGBYPASS → SUSPEND_N → SLEEPM → **SIDDQ=0 上电** → **POR=0 释放** → 收尾 |
| 诊断打印 | 启动前一行 `hsphy pre-state`（看交接时 PHY 原始状态）、启动后一行 `hsphy up (femto)`（看 COMMON0/1/CTRL2/REFCLK 回读值） |
| 修正 | probe 尾部的 PHY 状态打印改用 femto 偏移（旧的 qusb2-v2 偏移读的是不存在的寄存器） |

其余一切与 t16 完全一致（8 核、触摸、电池、显示、充电、SPMI 门、canary、QSCRATCH、settle）。

## 刷写

```
fastboot boot raphael-t17-hsphy-clean.img
```

**先彻底关机再进 fastboot**（长按电源 10 秒以上）。rootfs 不用重刷。OTG 线保持连接（fastboot 那根就是）。

## 判读树（一次刷机，逐行对号）

```
hsphy pre-state COMMON0 ... CTRL2 ...      ← 新：交接时的 PHY 原始状态
hsphy up (femto): COMMON0 ... CTRL2 0x...  ← 新：回读值（CTRL2 应含 0x4 = SUSPEND_N）
SWEET USB: QSCRATCH ... VBUS override on   ← 既有
soft reset done after 1 ms
DWC31 post-reset settle done
event buffer armed ...
DEPCMD(0) canary 0x00000000
ep0 DEPSTARTCFG/SETEPCONFIG/SETTRANSFRESOURCE
ep0 setup TRB armed                        ← ★ 过了这一行 = 楔死修复！
SWEET USB: running (DSTS ...)              ← gadget 跑起来
（进锁屏；此时主机手机应枚举出 ECM 网卡）
```

**胜负判定**：
- **全胜** = 看到 `running` + 进锁屏 + 主机手机枚举到网卡（设置里看 USB 设备，或 Termux 里 `ifconfig`/`ip a` 出现新网卡）+ `ping 192.168.7.2` 通。40 秒重启现象应随楔死一起消失
- **冻结点变化** = 巨大信息量：
  - 卡在 `hsphy pre-state` 打印 = PHY 寄存器空间本身死了（供电轨没上）→ 下轮做 RPMh LDO 投票
  - `hsphy up (femto)` 的回读值不对（写不进去）= 同上，PHY 供电问题
  - 过了 `hsphy up` 但卡在 canary/ep0 = PHY 活了但时钟域还有问题 → 下轮加全块 BCR + GCTL 重编
- **屏幕正常进锁屏但 USB 没枚举** = 拍屏幕 USB 段 + 主机手机 Termux 里 `lsusb` 或 `dmesg | tail` 结果发我

## 回退

- `sweetscale`/`sweetfb_fade`/`sweetusb=1` 等 boot-arg 回退全部沿用
- 整体回退：t7（r15，USB 修复前最后的稳定版）
- 本版 USB 修复只动了 USB 路径，触摸/电池/显示与 t16 同源，理论上互相独立
