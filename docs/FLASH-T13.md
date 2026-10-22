# t13（r29）刷写与判读 · fg-gen4 硬件电量计（真 SOC / 电压 / 电流）+ SMB5 充电语义 · v2 头重建版

> **r29 重建说明（2026-10-22）**：原版 t13（r21）资产失传——被 v1 头重建版误替换导致黑屏。
> - **内核**：由回退树 a7a925e（补丁 0001-0096，与原版 t13 完全同一补丁集）经 CI run 39730368579 重新构建；runner 工具链漂移致字节级哈希与原版不同（`bd6ad8be…`，已对 CI manifest 清单验证），内容判定以标记集校验为准——t12 身份标记（GT9886 / cfg send / DWC3 GSNPSID）+ 0096 fg-gen4 标记三项全部在场、已回退的 0097-0104（t14~t19 轮）标记 17 项全部缺席，双镜像六重校验全过。
> - **打包**：字节级验证过的 v2 工具链（`scripts/t13_prove_v2_toolchain.py` 对黄金 t12 往返复现，除 20B id 记账字段外逐字节一致）——**v1 头 = 黑屏**（三次事故同源：本机 ABL 只接受 v2 头 + DTB 独立段 @0x1f00000）。
> - 稳定版仍为 **r28/t12**（Latest 不变）；本版为当前测试轮。

## t12 实测结果（本版的出发点）

触摸已闭环（`pid [39 38 38 36]` = ASCII "9886"、`cfg send 784B err=0`，上手滑即有效）。电池侧 0095 的 sid 修复生效了——探针第一次读通了 PM8150B：

```
SWEET BATTERY: probe type=0/0xd sub=0/0x10 st1=0/0 st2=0/0xce v=0/0 i=0/0 usb=0/0x26 ...
```

（字段格式是 `err/值`。）`type=0xd` 读通，但电压/电流全 0、随后仍 static fallback。深挖 vendor 源码后真相大白：

## 根因：PM8150B 上根本没有"QG"，它是 fg-gen4 双外设集合

| t12 以为的 | 实际（vendor pm8150b.dtsi + fg-util.c 实锤） |
|---|---|
| 0x4000 = QG 外设 | 0x4000 = **fg-batt-soc**（SOC 算法外设）；QG 是 sm8250+ 的 PMIC 才有的 |
| 0x4008 = QG_STATUS（bit0 电池存在） | 0x4008 = BATT_SOC_SLEEP_SHUTDOWN_STS，恒 0 → t12 每次都判"无电池"直接 fallback |
| 0x40c0 = QG_LAST_ADC_V | fg-batt-soc 外设内根本没有 0xC0 数据寄存器 → 读回 0 |
| 0x4009 读到 0xce | **这就是 BATT_SOC_FG_MONOTONIC_SOC = 206（0-255 标度）≈ 80% 电量**——数值一直都在，只是被当成了 status2 |

真寄存器图（全部 PM8150B / SPMI SID 2）：

- **电量百分比**：`fg-batt-soc+0x09`（monotonic SOC，0-255，+0x0A 影子副本校验），换算用 vendor 原公式：255→100、0→0、其余 `round((raw-1)*98/253)+1`
- **电压**：`fg-batt-info+0xA0`（+0xA6 影子），`uV = raw × 122070 / 1000`（raw 0x8000 ≈ 4000mV）
- **电流**：`fg-batt-info+0xA2`（+0xA8 影子），符号扩展 15 位，`uA = raw × 488281 / 1000`，放电为正
- **电池在位**：`fg-batt-info+0x07`（SYS_BATT，bit0-2 = HW/ALG/CMP 缺电池标志）
- **充电状态**：SMB5 `0x1006` BATTERY_CHARGER_STATUS_1 状态机（1-4=涓流/预充/满充/收尾=充电中，5=TERMINATE=满）+ `0x1310` USBIN_PLUGIN bit4 = 外接电源

此外 0096 还带来：时间剩余估算（用实测电流对 4000mAh 标称容量）、真低电警告（≤20% 或 ≤3450mV）与临界（≤10% 或 ≤3350mV，仅在实测有效时上报）、百分比变化日志。

> 工程注：本轮 CI 曾两次失败——第一次是本地树的 tab/空格缩进漂移导致补丁上下文不匹配被 dxb **静默跳过**（绿灯假内核），已重建补丁并在 workflow 加了"板级补丁被跳过即报错"闸门；第二次是 publish 定义漏列默认参数（C++ 出参定义必须列全参数）。都已在 0096 v3 修复。

## 刷写

```
fastboot boot raphael-t13-fggen4-clean.img   # 日常验证
# 或
fastboot boot raphael-t13-fggen4-debug.img   # 排障：屏幕控制台常开
```

## 判读树

### A. 电池层（本版主角）

锁屏电量**不再是恒定 100%**、插线出现充电闪电即全胜。日志判决行（启动时一条看全）：

```
SWEET BATTERY: probe type=0/0xd sys=0/0x0 msoc=0/0xce,0xce(80%) v=0/0x7eXX,0x7eXX(4000mV左右) i=… usb=… chg=…
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| `type=0/0xd sys=0/0x0` | fg-gen4 在位、电池存在 | 看 msoc/v |
| `msoc=0/0xce,0xce(80%)`（两值相等=影子校验过） | **真电量上车** | 锁屏百分比应随实际变化 |
| `v=…(3900-4200mV 区间)` | 实测电压 | 数值应随负载/充电小幅波动 |
| 运行期 `SWEET BATTERY: PM8150B fg-gen4, XX% XXXXmV … charging=1` | 每 30s 轮询 | 插拔 USB 应翻转 external/charging |
| `msoc` 两值长期不相等 | 影子校验失败（读路径撕裂）| 回报该行 |
| 仍 `static fallback` | 数据校验没过（非读路径）| 回报 probe 行全部字段 |
| 百分比长期冻结不动但 v 在变 | FG 算法未跑（无 profile 时可能停更）| 下一步研究 fg-memif 电池 profile 下发 |

### B. 触摸层（回归确认，不应变化）

```
SWEET TOUCH: GT9886 pid err=0 [39 38 38 36] sensor err=0 id=0x1 ...
SWEET TOUCH: cfg send sensor1 784B err=0 flip=0
```

依旧正常即回归通过。若异常回报上述行。

### C. 启动层

8 核不变（`8/8 CPUs initialized`）；万一卡 bootstrap（理论不可能：本轮只动了电池路径）→ 强制重启回 **t12（r28）** 回报。

### D. 日志取证（不变）

```
adb shell dd if=/dev/block/by-name/userdata of=/tmp/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
```

（TWRP 下可用 `tail -c 4198400 /dev/block/sda31` 提取环区。）

### E. 回退

`fastboot boot` 回 **t12 / r28 稳定版**（已知可用：8 核 + 触摸闭环 + 电池探针 + v2 头）。

## 下一步研究已在案（见仓库 NOTES.md 新增章节）

- **升降前置摄像头**：DRV8846 步进马达驱动已逆向完毕（TLMM GPIO 21/33/35/9/130 + PM8150L LPG PWM，ramp 1.6kHz / 谐振 19.2kHz 序列），差 PM8150L LPG 寄存器图考证
- **振动马达**：板级 DTS 无节点，疑走 leds-qpnp-vibrator-ldo（PM8150L），待 pm8150l.dtsi 考证
- **电池 profile**：若 FG 算法停更，研究 fg-memif SRAM DMA 下发 vendor 电池特征文件
- **亮度**：AMOLED DCS 0x51 命令通道（需 DSI 主控写路径）

## 文件校验

| 文件 | SHA256 |
|---|---|
| `raphael-t13-fggen4-clean.img` | `82c71576bb58b9279e71ddcc03335a1e66a858679abb4d3abac9d65fe88044e4` |
| `raphael-t13-fggen4-debug.img` | `4f1f5f65cd96463030729ffdba8787ad8c880dd4aff5a4641bd8fa0c1430770d` |

内核：`bd6ad8bee6ea239b8d703b89c98ba15eedae9ab8080ae3502a525b02b3354eed`（补丁 0001-0096，CI run 39730368579；原版 r21 内核为 `c094d9ed…`，CI run 39596471069——runner 工具链漂移，功能同一补丁集，以标记集校验判定）；ADT：t8 系 8 核（f50510e0…，12588B）。
