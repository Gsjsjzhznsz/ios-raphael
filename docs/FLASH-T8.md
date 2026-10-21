# t8（r16）刷写与判读 · 触摸"真修复"首次上车

## 这一版到底修了什么

**t7 的"触摸修复"从未真正上车。** 根因在 CI 而非内核补丁：

- `xnu.yml` 的 push 触发走 `${{ inputs.machine_config || 'SWEET' }}`，push 构建没有 inputs → **回退 SWEET**。
- r15/t7 内核（run 39469756410，a4ca660）由 push 触发：CI 日志 937/937 条编译命令只有 `-DARM64_BOARD_CONFIG_SWEET`，**没有 `-DARM64_BOARD_CONFIG_RAPHAEL`**。
- 于是全部 raphael 专用代码（触摸 SE19@0xc88000 / GT9889@0x5d / TLMM 供电 / 音量上键 / USB 表 / 0086 ST FTS / 0089 HWCG）被预处理剔除成死代码。
- t7 日志因此是 SM7150 路径：wrap0 分支 0x18008/0x18144、错误引擎 0xa84000（SM8150 wrap1_s1，其 GENI_IF_DISABLE_RO bit0=1 → "probes skipped"）。触摸 IC 从未被触碰。
- 0089 的 HWCG 规则本身正确——它来自 t6 日志（r14 内核是 dispatch 构建、带 RAPHAEL，真实卡点 = wrap2 s_ahb 0x1e008），只是 t7 没跑到那里。

**t8 = 首个"RAPHAEL 编译 + 0089 已含"的内核。** 修复：push 默认也用 RAPHAEL + CI 硬断言（编译命令缺宏直接 fail）。

## 与 t7 的字节差异

| 部分 | 差异 |
|---|---|
| shim / DTB / ADT | **逐字节不变** |
| cmdline (clean) | 逐字节不变（330B） |
| cmdline (debug) | + ` sweethidtest=15`（346B） |
| 内核 | 全量重编译（RAPHAEL 宏恢复）；payload 内核段变化 |

| 文件 | SHA256 |
|---|---|
| `raphael-t8-clean.img` | `1bcdfbb9b0aa524a065cdbfd95a832b1535ac36b3a0686022fd1befbb389c7d7` |
| `raphael-t8-debug.img` | `f6bcfc9f56741124975ce7f717b6623573549ed3f78f9ad663a2bab4f03f6a59` |
| 新内核 `kernel.development.raphael` | 见 T8-SHA256SUMS.txt |

## 刷写

与 t7 完全一致（OrangeFox adb / 手机对手机 fastboot boot，boot 不刷分区、可随时回退 t7）：

```
fastboot boot raphael-t8-clean.img          # 日常验证
# 或
fastboot boot raphael-t8-debug.img          # 排障（假 Home 键每 15s 自打，验证 HID 下游）
```

## 日志判读树（sweet-log.bin）

t8 起，触摸走 raphael 真路径。关键锚点变化：

1. `SWEET TOUCH: gcc vote=… rcg=… cfg=… dfs=…` —— 投票寄存器 0x52014、RCG 0x1e3a8（wrap2_s2）。
2. 分支行现在是 **0x1e004 / 0x1e008 / 0x1e3a4**（不再是 0x18008/0x18144！）。预期 `0x1e008 HW-gated (…); ok`（0089 规则）。
3. `se7 fw=… proto=…` —— 标签仍叫 se7（历史打印），**这次读的是 SE19（0xc88000）**。qupfw 由 ABL 整体加载，预期 proto=3（I2C）。
4. 新增 `SWEET TOUCH: TLMM reset(gpio54)=… irq(gpio122)=…; GPIO rail power` —— raphael 供电路径首次运行（GPIO98 3v3 / GPIO100 1v8 / reset 54）。
5. 决胜行：
   - `probe 0x5d ver-reg err=0 …` → **GT9889 在线**，`selected GT9889` → 触摸应可用；
   - `probe 0x5d err≠0` 但 `probe ST FTS 0x49 err=0` → 二供批次（ST FingerTipS），`selected ST FTS`（只读事件泵）；
   - 两者都 err≠0 → 供电/复位时序问题，回传日志；
   - `probes skipped`（packing mismatch / inherited FIFO / IF_DISABLE）→ SE19 状态异常，回传日志。

触摸仍不动但 `selected GT9889` 且无 `report err` → IC 在线但事件链问题，用 debug 版（假 Home 每 15s）区分"IC→内核"与"内核→iOS"两段。

## 取证

```
adb shell dd if=/dev/block/by-name/userdata of=/sdcard/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
# 或 OrangeFox 终端： tail -c 4198400 /dev/block/sda31 > /sdcard/sweet-log.bin
```

回退：`fastboot boot raphael-t7-touchfix-clean.img`（任意 t 系列直启即可）。
