# t21（r31）刷写与判读 · 亮度 DCS / 即时息屏 + 充电输入 5s 监视

> **r31 说明（2026-10-22）**：t21 = t20 底座（0001-0097）+ 新板级补丁 **0098-raphael-display-brightness-off** + **0099-raphael-battery-charging**。
> - **亮度/息屏（0098）**：恢复历史 0098 中被 t20 拆分排除的三件搭车件 —— ① DSI ctrl0（0x0ae94000）TPG DMA FIFO 发 DCS：亮度 = 0x51（11 位大端，上限 2047 = qcom,mdss-brightness-max-level），息屏/点亮 = 0x28/0x29；② **即时息屏**：RequestPowerChange(0) 一次 memset 黑帧 + DCS 0x28，替代逐 vsync 渐暗（`sweetfb_fade=1` 恢复旧渐暗）；③ setProperties 亮度钩子 + **user client 转发**（Apple 自家 IOHIDEventServiceUserClient 同款：基类 IOUserClient::setProperties 不会转发给服务，不补这条钩子永远够不到）。DCS 引擎带自证：启动行会打 `SWEET FB: DSI ctrl0 ctrl=…`，控制器关着则自动禁用并注明。
> - **充电状态（0099）**：恢复历史 0097 充电补丁并修复其真 bug —— USBIN 插拔 + CHGR 状态 5s 快速监视（原 30s），插拔发生后 5s 内重新 publish（iOS 充电图标 5s 内出现）；转移瞬间一行打全 SMB5 输入侧寄存器（APSD 类型 / ICL / power path / STATUS5）。原版 inputCheck 抢先缓存导致转移行永远打不出来，本版已修。
> - **亮度滑条的诚实预期**：backboardd 找不到 backlight 节点（日志实锤 `IODeviceTree:/backlight -> none`），本版给出两条可能通路（setProperties / externalMethod 未知 selector）并全部埋好探针 —— externalMethod 日志从"每 selector 首次"升级为"**前 3 次**"且带标量参数值。若滑条本轮仍无效，日志里必有一条新 selector 行给出标量值，下一轮精准挂钩。
> - 稳定版仍为 **r28/t12**（Latest 不变）；t20（缩放）继续在架。

## 刷写

```
fastboot boot raphael-t21-bright-chg-clean.img   # 日常验证
# 或
fastboot boot raphael-t21-bright-chg-debug.img   # 排障：屏幕控制台常开
```

## 判读树

### A. 显示层（0098 主角）

启动判决行（DCS 通路是否可用的一锤定音）：

```
SWEET FB: DSI ctrl0 ctrl=0x… int=0x… dma=0x…            ← ctrl&1=1 即引擎在（ABL 留下）
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| 按电源键/自动锁屏：屏幕**瞬间全黑**（不再渐暗） | 即时息屏生效（memset+DCS 0x28） | 全胜 |
| 息屏后 AMOLED 严格黑（无微亮残影） | 面板真睡眠（DCS 0x28 生效） | 全胜+ |
| 亮屏恢复画面正常、亮度与息屏前一致 | DCS 0x29 + 亮度恢复生效 | 全胜 |
| 启动行显示 `(engine off; DCS disabled)` | DSI 引擎没被 ABL 留下 | DCS 不可用；息屏退化为黑帧覆盖，回报该行 |
| 日志出现 `brightness DCS failed; panel DCS disabled` | DMA 收不到 CMD_MODE_DMA_DONE | 回报该行 + 前后 10 行 |
| 息屏仍走渐暗（数秒变黑） | fInstantOff 没建立（异常） | 回报启动行 |
| 想回旧渐暗 | cmdline 加 `sweetfb_fade=1` | 需重打包，回报即可 |

### B. 亮度滑条（本轮目标：通路识别）

控制中心拖亮度滑条后提取日志，找这些行：

```
SWEET FB: setProperties brightness NNN     ← backboardd 走 connect-set-properties 通路
SWEET FB: backboardd sel NN in …/… (V1 V2 V3 V4) out …/…   ← 某未知 selector 首次/前三使用
SWEET FB: brightness NNN                   ← DCS 0x51 已发送（若前两者之一挂钩成功）
```

| 现象 | 结论 |
|---|---|
| 出现 `setProperties brightness` 且屏幕亮度跟随变化 | 亮度全胜（通路 = setProperties） |
| 出现 `setProperties brightness` 但亮度不变、且无 `brightness NNN` | 钩子被调用了但 DCS 失败（看 `brightness DCS failed`） |
| 出现新的 `backboardd sel NN … (V1…)` 行（拖动时） | 把这行发我：sel 号 + 标量值就是亮度通路真身，下一轮挂钩 |
| 滑条完全无新日志行 | 本轮两条通路都不对，等 DCS 自证行另寻他路 |

### C. 电池/充电层（0099 主角）

```
SWEET BATTERY: probe … apsd=… icl=… pp=… s5=…           ← 启动探针行新增 4 个字段
SWEET BATTERY: input plugin=1 apsd=DCP(0x8) icl=0x…(NNNmA) path=0x… st5=0x… … chg=FULLON(0x…) charging=1
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| 插充电器 ≤5s 内状态栏出现闪电 | 5s 监视 + publish 生效 | 全胜 |
| 插充电器无反应，但日志有 `input plugin=1 …` 行 | 内核已看到插拔、publish 已发——看 iOS 侧（把行发我） | 半胜，回报行内容 |
| 插充电器完全无新日志行 | USBIN plugin 位没动（PMIC 输入路径问题） | 回报 probe 行 + 任意 `SWEET BATTERY` 行 |
| `input plugin=1 … charging=0` 且 `chg=DISABLE(0x…)` | PMIC 看到输入但充电被禁 | 把整行发我：path/apsd/icl 值决定下一步投票 |
| 电量数字与 t20 一致平滑变化 | fg-gen4 无回归 | 通过 |

### D. 显示缩放（回归确认，不应变化）

启动行末尾 `(scaled)` 依旧；顶角时间/电量完整依旧。异常回报启动行。

### E. 触摸层（回归确认，不应变化）

```
SWEET TOUCH: selected GT9886 normandy, 1080x2340, poll=10ms irq-hint=0
```

### F. 启动层

8 核不变（`8/8 CPUs initialized`）；本版只动显示/电池观测路径，若卡 bootstrap（理论不可能）→ 强制重启回 **t12/r28** 回报。

### G. 日志取证（不变）

```
adb shell dd if=/dev/block/by-name/userdata of=/tmp/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
```

（TWRP 下可用 `tail -c 4198400 /dev/block/sda31` 提取环区。）

### H. 回退

`fastboot boot` 回 **t12 / r28 稳定版**；或上一测试轮 **r30/t20**（缩放版）。

## 文件校验

| 文件 | SHA256 |
|---|---|
| `raphael-t21-bright-chg-clean.img` | `312259a106a89c2cbfa2f534123576ef5e409948a2f9c7001cd055ed88d02bcb` |
| `raphael-t21-bright-chg-debug.img` | `e7f19586cbcb641dbe7efe0f21db69fd8a68ff21ef032ceec27ad8144a28bc09` |

内核：CI run 39788229692 @ d13299c（补丁 0001-0099；kernel.development.raphael cdd15b5b972522a78f85175db67989e4d2c0f8ac33eecec0f9acbb3f40ea2896）；ADT：t12 系 8 核（f50510e0…，12588B，逐字节复用）；cmdline：与 t12/t20 逐字节相同（无 `sweetfb_bright` → 亮度由 ABL 遗留档位起步；`sweetusb=0` 保持 USB 休眠）；debug 版与 clean 恰 1 字节差（`sweetfb_noconsole` 1→0，位 @0x33172）。
