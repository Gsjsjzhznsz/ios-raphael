# t22（r32）刷写与判读 · 亮度真通路 sel 50 / DSI 双控制器探测 + 电池 AppleSmartBattery

> **r32 说明（2026-10-22）**：t22 = t21 底座（0001-0099）+ **0100-raphael-display-brightness-sel50** + **0101-raphael-battery-smartname**。
> 本轮依据 = **t21 实机日志的两大判决**：
> ① 亮度通路找到了：Apple Wiki IOMFB selector 表与实机日志完全互证（sel 6/12/8/3/5 的形状全部吻合），**sel 50 = setBrightnessCorrection**，日志里 backboardd 两次调用 `sel 50 in (10000 0)` —— 10000 正是 iOS 亮度内部满刻度。t21 没实现它所以滑条无效；t22 直接挂上。
> ② DCS 引擎门禁误杀：t21 启动行 `DSI ctrl0 ctrl=0x20030000 (engine off; DCS disabled)` —— 但屏幕明明亮着，bit0 不是可靠的存活信号。t22 改用**真实命令自证**：ctrl0 → ctrl1 各试一条 DCS 0x29，谁完成 command DMA 谁是面板宿主。
> - **0100（显示/亮度）**：IOMFB sel 50 处理器 —— 0..10000 → 面板 DCS 0x51 电平（4..2047）感知曲线映射（低端可用、顶端 2047 满亮）；sel 50 **每次调用都记日志**（拖滑条会有连续 `brightness NNN` 行）；DSI 存活探测重构（bit0 门禁移除 + 双控制器）；亮度请求在 DSI 未通时**记 pending，亮屏时自动补发**；setProperties 改为**dump 全部键名**（t21 两个猜名钩子从未命中，其它属性通道不再隐身）；其余 selector 日志上限 3→8 次。
> - **0101（电池）**：iOS 状态栏按服务名找电池 —— personality 加 `'name' = AppleSmartBattery`（类名仍 SweetBattery），并打判决行 `registering as AppleSmartBattery`。内核侧数据链 t21 已实锤全通（插拔/APSD/ICL/FULLON/百分比全对），本轮赌的是**名字匹配**。
> - **自动亮度（诚实说明）**：自动亮度 = 光感(ALS) → CoreBrightness → **同一条 sel 50**。手动亮度修通后，sel 50 通路即自动亮度的执行端；但**没有 ALS 传感器数据 CoreBrightness 不会主动调** —— ALS 驱动（I2C 光感 + AppleALS HID 事件）是下一轮任务，本轮不塞进来（一次一个变量，回报质量优先）。
> - 稳定版仍为 **r28/t12**（Latest 不变）。

## 刷写

```
fastboot boot raphael-t22-bright-chg-clean.img   # 日常验证
# 或
fastboot boot raphael-t22-bright-chg-debug.img   # 排障：屏幕控制台常开
```

## 判读树

### A. DSI 探测（新启动判决行，一锤定音）

```
SWEET FB: DSI ctrl0 @0x… ctrl=0x… int=0x… dma=0x… tpg=0x…
SWEET FB: DSI ctrl0 probe ok; panel DCS enabled     ← 命中 ctrl0
SWEET FB: DSI ctrl1 @0x… ctrl=0x… …                 ← ctrl0 超时后才出现
SWEET FB: DSI ctrl1 probe ok; panel DCS enabled     ← 命中 ctrl1（面板挂 DSI1！）
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| ctrl0 probe ok | ABL 留下的宿主就是 ctrl0，t21 的 bit0 门禁确实误杀 | DCS 全链解锁 |
| ctrl0 timeout + ctrl1 probe ok | 面板挂在 DSI1 | 同样全胜，且回答了一个悬案 |
| 两个都 timeout | DMA FIFO 方案本身不成立 | 回报两行完整日志，改走别路（MDP/PSEQ） |

### B. 亮度滑条（本轮主角）

控制中心/设置拖亮度滑条，看日志：

```
SWEET FB: backboardd sel 50 in 2/0 (NNNN 0 0 0) …     ← 每次都记（不再只前3次）
SWEET FB: brightness NNN                              ← DCS 0x51 已发出（NNN=面板电平 4..2047）
SWEET FB: brightness DCS failed; panel DCS disabled   ← 只有 DMA 失败才会出现
```

| 现象 | 含义 | 结论 |
|---|---|---|
| 拖滑条屏幕亮度**实时跟随** + 日志连续 `sel 50 (NNNN)` → `brightness NNN` | 亮度全胜 ✅ | 拍视频记录 |
| 拖滑条有 `sel 50` 行 + `brightness NNN` 行，但屏幕不亮/不变 | DCS 发出但面板没执行（0x51 编码或 LP 模式问题） | 回报 NNN 值 + A 节探测行 |
| 拖滑条有 `sel 50` 行但无 `brightness` 行 | fDsiOk 没建立（看 A 节两行） | 回报 A 节日志 |
| 拖滑条**完全没有 sel 50 行** | 亮度走的是另一条通路 | 回报 `setProperties key …` 行（本轮会 dump 全部键名）+ 任意新 sel 行 |
| 亮屏后亮度与息屏前一致 | pending 亮度恢复生效 ✅ | — |

### C. 充电状态（名字匹配验证）

```
SWEET BATTERY: registering as AppleSmartBattery       ← t22 新增判决行
SWEET BATTERY: input plugin=1 apsd=DCP(0x8) icl=0xa(500mA) … chg=FULLON(0x3) charging=1
```

| 现象 | 含义 | 结论 |
|---|---|---|
| 插充电器 ≤5s 状态栏闪电出现 | AppleSmartBattery 名字就是钥匙 ✅ | 充电闭环 |
| 仍无闪电（插拔日志行照旧出现） | UI 不按名找/还要别的（BatteryData 等） | 回报插拔时刻日志；下一轮逆向 rootfs 的状态栏数据源 |
| 电量百分比显示（若之前显示假 100%）变真 | 同名注册让 UI 读到了真数据 | 额外全胜 |

### D. 息屏（回归确认，不应变化）

电源键/自动锁屏 → **瞬间全黑**（t21 已生效）；亮屏恢复正常。若退回渐暗 → 回报 A 节行。

### E. 回归确认（不应变化）

- 缩放：启动行末尾 `(scaled)` 依旧。
- 触摸：`SWEET TOUCH: selected GT9886 normandy …` 依旧。
- 8 核：`8/8 CPUs initialized`。
- 显示本身：UI 渲染、swap 流正常（本轮只动 sel 50 + DSI 探测，swap 路径零改动）。

### F. 风险与回退

本轮改动面 = ①sel 50 处理器（新分支，此前走 default 直通）②DSI 探测（多了对 ctrl1 的映射+一条 0x29 探测命令；0x29 对已亮面板是无害 no-op）③电池名字串。理论回归风险极低。任何异常：

```
fastboot boot raphael-t21-bright-chg-clean.img    # 回上一测试轮
fastboot boot <r28/t12 镜像>                       # 回稳定版
```

### G. 日志取证（不变）

```
adb shell dd if=/dev/block/by-name/userdata of=/tmp/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
```

（TWRP 下可用 `tail -c 4198400 /dev/block/sda31`。）

### H. 本轮日志重点抓取清单（发我这些就够）

1. `SWEET FB: DSI` 开头的全部行（A 节判决）
2. 拖亮度滑条前后 30 秒内所有 `SWEET FB:` 行（B 节判决）
3. `SWEET BATTERY: registering` + 插拔充电器前后所有 `SWEET BATTERY:` 行（C 节判决）
4. 若滑条无 sel 50 行：全部 `setProperties key …` 行 + 所有 sel ≥ 60 的行
