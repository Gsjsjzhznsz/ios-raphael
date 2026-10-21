# t9（r17）刷写与判读 · bootstrap-done 修复（t2 配方入库）

## 这一版到底修了什么

**t8（首个 RAPHAEL 编译内核）卡死在 `bootstrap done`，t7（SWEET 编译）正常。** 复盘全部历史后根因画像：

- 历史上**每一个 RAPHAEL 编译的内核**（diag5、r11 sc-verbose、t8）无一例外卡在 `bootstrap done`；**唯一例外是 t2**（swap-test，实机进锁屏）。
- t2 与其他 RAPHAEL 启动的差异有两处，从未做过隔离（t3/t4 没测完 t2 就通关了）：
  1. **内核匹配表**：`KernelConfigTables` 里 `SweetCPU` 的 `IONameMatch = 'qcom,kryo470'`，而我们的 ADT 全部声明 `qcom,kryo485`。t2 当时是对内核二进制做**就地字符串补丁**（kryo470→485、Kryo 470→485），从未入库；
  2. **ADT CPU 节点数**：t2 的 ADT 只有 **1 个 CPU 节点**。经逐节点解析比对：t 系列 ADT 与 t2 ADT **唯一结构差异就是 CPU 节点 1→8**（fbcon 9c000000+0x9a4000、/product、其余全部相同）。
- t5–t7 能正常启动是因为它们**实际是 SWEET 编译**（含 t6——本次用镜像字符串标记实证：`Yellowstone`/`L11C` 在、`TLMM reset(gpio` 不在），SWEET 编译对这两项不敏感。**RAPHAEL 编译从未在 t 系列上成功启动过。**

**t9 = 把 t2 配方正式装进现代栈**：

| 部分 | 与 t8 的差异 |
|---|---|
| 内核 | +补丁 0090：`IONameMatch kryo470→kryo485`、`cpuName "Kryo 470"→"Kryo 485"`（t2 二进制补丁的入库版）。0088/0089 保持不变 |
| ADT | t 系列 ADT 删除 cpu1–7（外科手术，其余节点/属性逐字节保序）= t2 的 1-CPU 拓扑，7044 字节 |
| shim / DTB / 头 | 与 t7 逐字节不变 |
| cmdline (clean) | 与 t7 逐字节一致（330B） |
| cmdline (debug) | 同 clean 去掉 `sweetfb_noconsole=1` —— **屏幕控制台常开**（r11 取证法） |

## 刷写

```
fastboot boot raphael-t9-bootstrapfix-clean.img   # 日常验证
# 或
fastboot boot raphael-t9-bootstrapfix-debug.img   # 排障：屏幕显示控制台
```

## 判读树

1. **出锁屏**（可能比 t7 慢——1 核；t2 时代已验证单核可完整跑起用户态）→ bootstrap-done 修复成立。看触摸是否跟着活（RAPHAEL 路径首次真正可执行：拉日志找 `probe 0x5d` / `ST FTS 0x49`，判读沿用 FLASH-T8.md 的触摸树）。
2. **卡住** → 用 **debug 版**：屏幕会滚动内核日志，**拍下最后几行**发回来 —— 那就是精确卡点（r11 方法论）。关键锚：
   - 出现 `SWEET UFS:` 行 → 已越过历史卡点（历史卡点在 UFS probe 之前）；
   - 最后一行是 `VM bootstrap done` 或 IOKit 注册后某行 → 与 r11/t8 同点位，照片直接定位剩余差异。
3. **日志取证**（不变）：
```
adb shell dd if=/dev/block/by-name/userdata of=/tmp/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
```
4. **回退**：`fastboot boot raphael-t7-touchfix-clean.img`（t7 发行版已保留）。

## 若 t9 通关后的路线

- ADT 是纯镜像侧改动（无需重编内核）：下一轮可逐步回加 CPU 节点（2→4→8）找出 RAPHAEL 编译的死点数量，恢复 8 核；
- 触摸判读树见 FLASH-T8.md（0x1e004/0x1e008/0x1e3a4、TLMM reset(gpio54)、probe 0x5d / ST FTS 0x49）。

| 文件 | SHA256 |
|---|---|
| `raphael-t9-bootstrapfix-clean.img` | `371d84e0e934ced88ac549e99b64798d1ff1c86dc14df1ef1ede0fad236d22fe` |
| `raphael-t9-bootstrapfix-debug.img` | `d9203c0eaa0ee550aefcfc8d1655d1f4ea299ff600bd8eab87b8efbebaf7014e` |
