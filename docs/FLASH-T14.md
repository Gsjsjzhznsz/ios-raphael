# t14（r22）刷写与判读 · 显示缩放 + 即时息屏 + 亮度通道 + 充电状态快轮询 + USB 网卡

## t13 实测结果（本版的出发点）

电池读数路径全通：`msoc=0/0xc2,0xc2(76%) v=0/0x821a(4065mV) i=0/0x319(-387mA)` —— 锁屏百分比已是真数据。但三件事没有闭环：

1. **充电状态识别不到**：probe 采样时未插线（`usb=0x26` = UV|VASHDN，无 VBUS），且 0096 只在百分比变化时打日志——插拔电源这种关键事件**根本不落日志**（盲区）。
2. **屏幕缩放无效 + 顶部两角被挡**：实锤于代码——iOS 按 iPhone X 的 **1125×2436** 渲染（日志 `swap layer 0 surface 1125x2436`），驱动只取**居中裁剪**的 1080 宽窗口（左右各切 ~22px、上下各切 ~48px），状态栏时间/电量正好在切口上；显示缩放（标准/放大）两种模式渲染同一画布，裁剪固定，所以"无效"。
3. **息屏慢慢变暗 + 无亮度调节**：息屏走的是 7 步逐 vsync 减半渐暗 + iOS 用户态自身的软渲染淡出动画；亮度则完全没有通道。

USB 一侧：t 系列 cmdline 一直带着 `sweetusb=0`（从 t7 继承，从未开过）——CDC-ECM USB 网卡 + UDP 实时日志这套东西**早就实现**（补丁 0073-0077 + 0087），只是没启用。

## t14 做了什么

| 项 | 补丁 | 内容 |
|---|---|---|
| 显示缩放 | 0098 | 1125×2436 → 1080×2340 **最近邻缩放**（逐列/逐行映射表，中心对齐），不再裁剪；`sweetscale=0` 回退裁剪 |
| 即时息屏 | 0098 | RequestPowerChange(0) 时**一次性清屏 + DCS 0x28**（面板断显，AMOLED 黑=像素灭），替代 7 步渐暗；`sweetfb_fade=1` 回退渐暗 |
| 亮度通道 | 0098 | DSI ctrl0（0x0ae94000）命令 DMA（vendor TPG FIFO 路径）发 **DCS 0x51 大端 11-bit**（vendor `mipi_dsi_dcs_set_display_brightness_ss` 同款，max 2047）；入口：`sweetfb_bright=<4-2047>` 启动亮度 + `setProperties("brightness")` 钩子；未识别的 UC selector 现在带**参数值**落日志（下一轮定位 iOS 滑条到底调哪个 selector） |
| 充电状态 | 0097 | 5 秒快轮询（USBIN_RT_STS + CHGR_STATUS1 两读），插拔 5 秒内响应；**输入路径切换日志**：APSD 充电器类型（SDP/DCP/CDP/QC…）+ ICL 输入限流 + 电源路径 + 充电状态机名一次全落盘；probe 行也补齐这四个寄存器 |
| USB | cmdline | `sweetusb=2`：DWC3 设备模式软复位 + ep0 + CDC-ECM 网卡 `ue0`（192.168.7.2）+ 控制台日志每 100ms UDP 发往 192.168.7.1:5140 |

> 工程注：本轮差点重演"缩进漂移假补丁"事故——Edit 工具把整文件 tab 转成了空格，生成的补丁上下文与规范树不符。已改为**脚本字节级替换**（scripts/apply_t14_battery.py / apply_t14_display.py）从规范基直接生成，往返校验通过。

## 刷写

```
fastboot boot raphael-t14-display-clean.img   # 日常验证
# 或
fastboot boot raphael-t14-display-debug.img   # 排障：屏幕控制台常开
```

## 判读树

### A. 显示层（本版主角）

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| 顶部时间/电量**完整显示**、状态栏不再被切 | 缩放生效 | 全胜 |
| `SWEET FB: AppleCLCD … presented as 1125x2436 (scaled)` | 缩放表已建 | 对照上一行 `1080x2340 stride …` |
| 画面整体轻微"颗粒感" | 最近邻缩放的正常代价（0.96 倍降采样） | 属预期 |
| 设置里"标准/放大"切换有视觉变化 | 缩放模式下 Display Zoom 真实生效 | 全胜 |
| 顶角仍被切 | 缩放没生效（`sweetscale=0`?） | 回报启动行 |
| 画面撕裂/局部错位 | 部分更新矩形缩放舍入 | 回报现象+日志，可加边缘对齐 |

### B. 息屏 / 亮度（本版主角）

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| 按电源键**立即全黑**（无渐暗） | 即时息屏生效 | 全胜 |
| `SWEET FB: display off (instant)` | 清屏 + DCS 0x28 已发 | 对照 `display on` |
| 息屏瞬间黑一下但随即又亮 | DCS 0x28 后用户态又画了帧 | 回报，可加 power-off 期间丢弃 present |
| 亮度：主机日志看到 `SWEET FB: brightness N` | DCS 0x51 通道工作 | `sweetfb_bright=1000` 试不同值 |
| 息屏后唤不亮 | DCS 0x29 唤醒失败 | 强制重启回报（可 `sweetfb_fade=1` 绕过 DCS 息屏） |
| 拖动 iOS 亮度滑条无反应 | 滑条 selector 未接（预期） | **回报日志**：新版 selector 日志带参数值，拖滑条时哪个 selector 在反复调用+数值变化即可定位 |

### C. 电池充电状态（本版主角）

启动 probe 行新增四个字段（`err/值` 格式）：`apsd=… icl=… pp=… s5=…`。运行期**插拔电源**看切换行：

```
SWEET BATTERY: input plugin=1 apsd=DCP(0x8) icl=0x1e(1500mA) path=0x11 st5=0x1 usbsts=0x30 chg=FULLON(0x43) charging=1
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| 插线后 ≤5 秒锁屏出现闪电/插头图标 | 全链闭环 | 全胜 |
| `plugin=1` 但 `chg=DISABLE` | VBUS 在但充电器没启动 | 回报完整行；若 `st5=0`（充电级全关）→ 下一步查 ABL 是否留了充电禁用，需要 SPMI 写通道 |
| `plugin=1 apsd=SDP` + PC 口 | PC 口限流 500mA，系统功耗 > 充电 | 用充电头（DCP）复测 |
| `plugin=0` 但实际已插线 | VBUS 没到 USBIN | 回报行；查线材/充电头，或 type-c 路径 |
| `apsd=none` 且 icl=0 | APSD 未跑 | 回报行 |

### D. USB 网卡 + 实时日志（新能力）

插线到电脑后：

```bash
# 电脑端（Linux/Mac，仓库 tools/ 目录）：
sudo tools/sweet-usbnet.sh     # 配置 192.168.7.1 + 起 nc -ukl 5140 收实时日志
ping 192.168.7.2               # 手机应答即 USB 网络通
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| 主机枚举出 USB 网卡（cdc_ether）+ ping 通 | gadget 全通 | 以后日志实时看 |
| `SWEET USB: running (DSTS 0x… after N ms)` | DWC3 设备态运行 | 对照 `soft reset done` |
| 枚举出 `18d1:…` fastboot 残留 | gadget 没起来（GDSC/时钟没开） | 回报 `SWEET USB:` 全部行 |
| `soft reset STUCK` | ABL 残留态异常 | 回报；`sweetusb=1`（只探测）可对照 |

### E. 回归确认（不应变化）

- 触摸：`GT9886 pid err=0 [39 38 38 36]` + `cfg send 784B err=0`
- 八核：`8/8 CPUs initialized`
- 电量：`msoc=…(NN%)` 真百分比

### F. 日志取证（新捷径：USB 实时日志，见 D；老路径不变）

```
adb shell -T "tail -c 4194304 /dev/block/by-name/userdata > /tmp/sweet-log.bin"
adb pull /tmp/sweet-log.bin
```

### G. 回退

`fastboot boot` 回 **t13**（电池读数版）或 **t7**（最终回退点）。t 系列不落盘，重启即回。

## 风险提示

- **DCS 亮度/息屏是对显示管线的首次写操作**：若面板对 0x28/0x51 响应异常，最坏情况息屏唤不亮（重启即恢复）。debug 镜像可 `sweetfb_fade=1` 完全绕过 DCS 息屏。
- 缩放路径每帧多做一次 2.5M 像素采样，帧率理论略降（8 核下应无感）。

## 文件校验

| 文件 | SHA256 |
|---|---|
| `raphael-t14-display-clean.img` | 见 r22 Release 的 `T14-SHA256SUMS.txt` |
| `raphael-t14-display-debug.img` | 见 r22 Release 的 `T14-SHA256SUMS.txt` |

内核：0097-0098（CI run 见 r22）；ADT：t8 系 8 核（f50510e0…，12588B）；shim/DTB 与 t7 逐字节一致。
