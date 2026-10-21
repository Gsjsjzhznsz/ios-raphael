# t15（r23）刷写与判读 · USB 挂死修复（DWC31）+ SPMI 串行化

## t14 实测结果（本版的出发点）

t14 开机后**卡死并重启**，现场日志（屏幕控制台）：

```
SWEET USB: ue0 192.168.7.2/24 up (err 0)
SWEET USB: soft reset done after 1 ms, GCTL 0x00112001 DCFG 0x00480000
[此后再无任何输出 → 整机冻结 → 重启]
```

第二次 `fastboot boot` 后卡得更早：按键普查（census）打印到 `aplid=297`（PM8150B 的 GPIO）就停住。

## 根因（已实锤）

1. **USB 挂死 = IP 版本差异**。上游 ios-sweet 真机验证 USB 用的控制器是**经典 DWC3 v3.20a**（sweet，GSNPSID `0x5533320a`）；raphael 读到的 GSNPSID 是 **`0x33313130` = DWC_usb31（USB 3.1 IP）**（Linux `dwc3_core_is_valid()` 按 `0x3331xxxx` 分类）。Linux 内核 `dwc3_core_soft_reset()` 对 DWC31 有专门注释：**DCTL.CSFTRST 清除后，设备/端点时钟域要重新同步，1.80a 及更早版本必须再等 ≥50ms 才能访问端点域**。我们的代码软复位"done after 1 ms"后立刻发 ep0 命令 → 总线挂死（连 DEPCMD 的超时打印都没来得及出）。**这就是卡在 `soft reset done` 后面的原因。**
2. **普查卡住 = SPMI 命令从未全局串行化**。按键线程（每 20ms）、普查（一次性）、电池轮询（t14 起每 5s）各自独立向同一个 SPMI 仲裁器发观察命令；Linux 对整个 pmic-arbiter 用**一把全局锁**串行所有命令。崩溃重启后 PMIC 状态未清（warm reboot 不断 PMIC 电），叠加并发命令，普查就"看起来死机"了。

## t15 做了什么

| 项 | 补丁 | 内容 |
|---|---|---|
| USB DWC31 修复 | 0099 | ① QSCRATCH VBUS 强制**提前到软复位之前**（Linux dwc3-qcom 顺序，wrapper 寄存器不受核复位影响）；② 软复位后 **100ms 时钟域同步等待**（Linux 对 DWC31 的 50ms 要求 ×2 裕量）；③ **每个阶段一条面包屑日志**——再挂死也能从屏幕看出死在哪条指令 |
| SPMI 串行化 | 0100 | 按键/普查/电池**所有**观察命令过同一把全局命令门（Linux 式单锁串行） |
| 普查改可选 | 0100 | GPIO 普查默认**跳过**（日志会打 `census skipped`），`sweetcensus=1` 可选开——诊断使命已完成，不再让它有机会"假死机" |

显示缩放 / 即时息屏 / 亮度通道 / 充电快轮询（0097/0098）原样保留——t14 死在 USB 阶段，这些功能**从未被真正测过**，本轮一并验证。

## 刷写

```
fastboot boot raphael-t15-usbfix-clean.img   # 日常验证
# 或
fastboot boot raphael-t15-usbfix-debug.img   # 排障：屏幕控制台常开
```

> ⚠️ **刷之前先彻底关机一次**（长按电源 10 秒以上再进 fastboot）。t14 崩溃后 PMIC 的坏状态会跨热重启保留，导致第二次启动"假死机"；冷启动可清掉。

## 判读树

### A. USB（本版主角）——面包屑顺序

```
SWEET USB: ue0 192.168.7.2/24 up (err 0)        ← ue0 网卡已建
SWEET USB: QSCRATCH HS_PHY_CTRL 0x… SS_PHY_CTRL 0x… GENERAL_CFG 0x…
SWEET USB: VBUS override on: …                  ← VBUS 会话已强制（提前）
SWEET USB: soft reset done after N ms, …        ← 设备软复位
SWEET USB: DWC31 post-reset settle done         ← ★100ms 同步等待（新增）
SWEET USB: event buffer armed at 0x…            ← 事件缓冲
SWEET USB: ep0 DEPSTARTCFG/SETEPCONFIG/SETTRANSFRESOURCE
SWEET USB: ep0 setup TRB armed                  ← ep0 就绪
SWEET USB: running (DSTS 0x… after N ms), DMA at 0x…   ← ★设备态运行
SWEET USB: connected, speed 0                   ← 主机侧看到连接（speed 0=高速）
SWEET USB: setup … / address N / configured (1)
SWEET USB: ECM endpoints configured             ← 网卡端点激活
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| 全部面包屑走到 `running`，电脑枚举出网卡、`ping 192.168.7.2` 通 | **全胜**，以后日志可走 `tools/sweet-usbnet.sh` 实时看 | 顺手验证 B/C/D |
| 停在某条面包屑之后 | 该条后面的操作挂死 | **拍照回报最后几行**（每条面包屑对应一步寄存器操作，可直接定位） |
| `ep0 cmd status N` 或 `ep0 … timeout` | 端点命令失败（不再挂死） | 回报数值 |
| `soft reset STUCK` | 复位不自清 | 回报 |
| 卡在 `settle done` 与 `event buffer` 之间 | 100ms 不够（IP 版本更早） | 回报，下轮加长 |

### B. 电脑端（USB 全通后的玩法）

```bash
sudo tools/sweet-usbnet.sh     # 配置 192.168.7.1 + 起 nc -ukl 5140 收实时日志
ping 192.168.7.2
```

### C. 显示 / 息屏 / 亮度 / 充电（t14 的功能，本轮才真正开始测）

判读树与 t14 相同，摘录关键行：

| 现象 | 结论 |
|---|---|
| 顶部时间/电量**完整显示**，不再被切 | 缩放生效（0098） |
| 按电源键**立即全黑**（无渐暗） | 即时息屏生效（0098） |
| `SWEET FB: brightness N` 出现且亮度变 | DCS 0x51 通道生效（`sweetfb_bright=1000` 可试） |
| 插线后 ≤5 秒锁屏闪电 + `input plugin=1 apsd=…` | 充电状态闭环（0097） |

### D. 回归确认（不应变化）

- 触摸：`GT9886 pid err=0 [39 38 38 36]` + `cfg send 784B err=0`
- 八核：`8/8 CPUs initialized`
- 电量：`msoc=…(NN%)` 真百分比
- **按键普查默认消失**：看到 `SWEET KEYS: census skipped (sweetcensus=1 to run)` 是**预期行为**，不是故障（需要普查证据时再加 boot-arg）

### E. 日志取证

USB 通了以后直接 `tools/sweet-usbnet.sh` 实时看；还不通则老路径：

```
adb shell -T "tail -c 4194304 /dev/block/by-name/userdata > /tmp/sweet-log.bin"
adb pull /tmp/sweet-log.bin
```

### F. 回退

`fastboot boot` 回 **t13**（电池读数版）或 **t7**（最终回退点）。t 系列不落盘，重启即回安卓。

## 风险提示

- USB 初始化若再挂死，面包屑会指明位置；不会再出现"无声无息死在半路"的盲区。
- 冷启动建议（见刷写注意事项）是为了清 PMIC 的跨重启状态，属于已知的高通平台行为，不是本移植的缺陷。

## 文件校验

| 文件 | SHA256 |
|---|---|
| `raphael-t15-usbfix-clean.img` | 见 r23 Release 的 `T15-SHA256SUMS.txt` |
| `raphael-t15-usbfix-debug.img` | 见 r23 Release 的 `T15-SHA256SUMS.txt` |

内核：0099-0100（CI run 见 r23）；ADT：t8 系 8 核（f50510e0…，12588B）；shim/DTB 与 t7 逐字节一致；rootfs 无需重刷。
