# t16（r24）刷写与判读 · SUSPHY 根因修复（USB 端点域时钟门控）

## t15 实测结果（本版的出发点）

t15 开机：**全部 USB 面包屑通过**（VBUS override → soft reset 1ms → 100ms settle → 事件缓冲区 → `ep0 DEPSTARTCFG/SETEPCONFIG/SETTRANSFRESOURCE`）——然后就**整机冻结，过了一会儿自动重启**。你拍的照片就是最后定格画面。

## 取证：这次终于看清了死点

上轮会话换了个视角分析你的照片，有两个此前不知道的事实帮了忙：

1. **屏幕控制台是"环绕式"的，不是滚动的**（写满 73 行就回到第 0 行继续覆盖）。用环绕几何重排照片上的文字后，屏幕顶部那 5 行 USB 输出其实是**最新**的内容——也就是说：控制台死在 `ep0 DEPSTARTCFG...` 这行打印**之后、下一条打印（"ep0 setup TRB armed"）之前**，即死在 `ud_epcmd()` 端点命令序列**内部**。没有 timeout 打印、没有 status 打印 → 不是命令超时，是 **DEPCMD 寄存器读永远不返回 = 总线级挂死**。
2. t15 的软复位、事件缓冲区、DCFG/DEVTEN 全部成功——**全局寄存器块活着，只有端点寄存器块（0xc800 DEPCMD 区）死了**。

顺带说明"自动重启"：内核挂死在总线上后，复位来自硬件侧机制（RPM/TZ/NoC 错误路径，内核不控制），所以表现是"冻结→过一会儿自己重启进 MIUI"。**挂死修掉，重启自然消失。**如果哪次还冻结，请掐一下"定格→重启"的秒数告诉我（固定值=看门狗，随机值=NoC 错误升级，指纹不同）。

## 根因（已实锤，对照 Linux 源码）

你照片里 probe 打过一行 `GUSB2PHYCFG 0x00100240` —— **bit 6 = SUSPHY = 1，ABL 留下的 PHY 处于挂起省电状态**。

Linux `dwc3_hs_phy_setup()` 里有一行显式注释：

```c
/* Ensure the GUSB2PHYCFG.SUSPHY is cleared prior to phy init. */
reg &= ~DWC3_GUSB2PHYCFG_SUSPHY;
```

在 DWC_usb31 上，**PHY 挂起时端点寄存器块的时钟是被门控的**——第一条 DEPCMD 访问就挂在 AXI 总线上，拖死 config-NoC（全核共享）→ 整机冻结。t14/t15 楔死在同一点，t14 只是没面包屑看不见。上游 sweet 的 SM7150 是经典 DWC3，这条捷径无害，所以从未暴露。Linux-on-raphael 的 USB 能用，正是因为它走了"清 SUSPHY → phy init → 软复位"的完整序列。

## t16 做了什么（补丁 0101）

| 项 | 内容 |
|---|---|
| **清 SUSPHY** | `sweet_usb_gadget_start` 里、设备软复位**之前**：读 GUSB2PHYCFG → 清 bit 6 → 等 10ms（PHY 从挂起恢复）→ 打印 `GUSB2PHYCFG 0x00100240 -> 0x00000240 (SUSPHY cleared)`。之后**保持清零**（我们是轮询式驱动，不需要 Linux 那套"跑起来后再开自动挂起"） |
| **金丝雀探针** | 第一条端点命令**之前**先做一次纯读：`DEPCMD(0) canary 0x00000000`。万一还挂死，屏幕最后一行直接分辨：卡在 canary = 端点块仍被时钟门控（下轮上 QUSB2 PHY 完整重初始化）；过了 canary 卡在 `ep0 DEPSTARTCFG` = 命令语义问题（下轮对齐 Linux gadget start 全序列） |

其余一切（8 核、触摸、电池、显示缩放/息屏/亮度、充电轮询、SPMI 命令门）与 t15 完全一致。

## 刷写

```
fastboot boot raphael-t16-susphy-clean.img
```

**先彻底关机再进 fastboot**（长按电源 10 秒以上）——PMIC 的崩溃状态会跨温重启保留。rootfs 不用重刷。

## 判读树（一次刷机，逐行对号）

屏幕 USB 段按顺序应打：

```
SWEET USB: ue0 192.168.7.2/24 up (err 0)              ← 接口创建（老）
SWEET USB: GUSB2PHYCFG 0x00100240 -> 0x00000240 (SUSPHY cleared)   ← 新：根因修复
SWEET USB: QSCRATCH HS_PHY_CTRL 0x00000000 ...        ← 初始 dump（老）
SWEET USB: VBUS override on: HS_PHY_CTRL 0x10100000 ...
SWEET USB: soft reset done after 1 ms ...
SWEET USB: DWC31 post-reset settle done
SWEET USB: event buffer armed at ...
SWEET USB: DEPCMD(0) canary 0x00000000                ← 新：端点块活了
SWEET USB: ep0 DEPSTARTCFG/SETEPCONFIG/SETTRANSFRESOURCE
SWEET USB: ep0 setup TRB armed                        ← ★ 过了这条 = 卡点打通
SWEET USB: running (DSTS 0x... after N ms)            ← ★ 控制器跑起来
SWEET USB: QUSB2 PLL_STATUS ...                        ← probe 收尾
```

之后正常进锁屏。然后验证 USB 里程碑（主机 = 你那台Termux 手机，保持 OTG 连着）：

1. **主机侧枚举**：Termux 里 `lsusb` 或看 `/sys/bus/usb/devices`——应出现新设备（Sweet ECM 网卡，不再是 fastboot 的 18d1:4ee7）；
2. **拿到地址**：`ping 192.168.7.2`；
3. （可选）`nc -ukl 5140` 收 UDP 直播日志。

### 如果又冻结了

| 最后定格行 | 含义 | 下一步 |
|---|---|---|
| `event buffer armed` | canary 楔死 = 端点块仍被门控 | 下轮：QUSB2 PHY 完整重初始化（Linux phy-qcom-qusb2 序列，源码已备好） |
| `DEPCMD(0) canary 0x...` | canary 过了、DEPSTARTCFG 楔死 = 命令语义 | 下轮：对齐 Linux `__dwc3_gadget_start` 全序列（GCTL 重写等） |
| 其他行 | 新卡点 | 拍照回传 |

同时掐表记录**定格→自动重启的秒数**，回传时附上。可选：照旧用 OrangeFox 提取 `sweet-log.bin`（注意：kprintf 行不进日志环，屏幕照片才是全量证据；ring 里最后一行应该是 `ep0 DEPSTARTCFG...`）。

### 回退

t7（r15）/ t13 直接 fastboot boot 即可。rootfs 不动。
