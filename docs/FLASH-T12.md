# t12（r20）刷写与判读 · GT9886 厂商级 bring-up（配置下发）+ 电池 sid 修复

## t11 实测结果（本版的出发点）

t11 的 TLMM-south 修复让总线**完全活了**：供电轨上电（vdd=3 avdd=3）、SDA/SCL 拉高、`probe 0x5d err=0`（IC 应答！）—— 然后暴露出下一层的两个真问题：

```
SWEET TOUCH: probe raw 0x8240: 00 00 02 d2 ff ff f9 ad ...   ← 不是 ASCII "9886"：寄存器图根本不对
SWEET TOUCH: report err=5 irq=0x40000001                     ← 每次轮询都失败（DONE、零 RX、无 NACK）
SWEET BATTERY: SPMI arb=0x50000000 APIDs=512 ...             ← arbiter 活着
SWEET BATTERY: static fallback, 100% 4200mV ...              ← 但读数仍然失败
```

## 根因（爬透 LineageOS raphael 内核 + vendor 固件 blob 后定位）

1. **GT9886 "normandy" 的寄存器图来自配置 blob，不是任何 GT9xx 通用图**。真图：pid@0x4535（ASCII "9886"）、sensor-id@0x4541、版本块@0x452c（72 字节、和为零）、命令通道@0x6f68、配置窗口@**0x6f78**、**触摸帧@0x4100**。我们从 t8 起读的 0x8240/0x824E 只是碰巧会 ACK 的地址。
2. **这颗 IC 每次开机都必须经 I2C 下发 784 字节面板配置**（vendor `goodix_send_config` 握手：命令寄存器 0xff → START 0x80 → 等 0x82 → 写 784B → END 0x83 → 等 0xff，全程关 doze）。不下发配置，固件永远不产出触摸帧。两份面板供应商配置已从 vendor blob 原样嵌入内核（sensor0 双轴翻转 / sensor1 不翻转，运行时按 IC 的 sensor-id 选择）。
3. **0x49 ST FTS 探针是投毒者**：NACK 后 TX FIFO 残留 5 字节，此后每次传输都在发送陈旧字节（DONE 提前到、sent!=nt → err=5）—— 正是 t11 "探针成功、轮询全灭" 的签名。该探针已删除；TX 路径改为水位驱动的流式写入（单条写可达 786 字节）。
4. **电池读数失败的根因在 SPMI 观察者命令**：Linux 格式是 `opcode<<27 | sid<<20 | addr<<4 | len-1`，我们漏了 **sid 字段** —— SWEET（PM6150=SID0）从没暴露，raphael 的 PM8150B 在 **SID 2**，于是每次都在读 SID 0 → QG type 校验失败 → 静默 fallback。已修复，并加了一次性寄存器探针（逐字段带错误码）。

## t12 改了什么

| 部分 | 与 t11 的差异 |
|---|---|
| 内核 0094（触摸）| GT9886 真寄存器图；**784 字节配置下发**（双供应商配置嵌入）；doze 控制（0xAA→0x30F0，读 0x3100==0xBB，下发后保持唤醒）；帧解析移到 0x4100（事件位7 + 计数 + 8字节点 + 整帧校验和为零 + 清帧写 0）；0x49 探针删除；TX 流式传输 |
| 内核 0095（电池）| SPMI 观察者命令补 sid 位域（根因修复）；启动时一次性探针：`SWEET BATTERY: probe type=… sub=… st1=… v=… i=… usb=… path=… chg=… err=… temp=…`（每个字段带错误码）|
| ADT / shim / DTB / cmdline | 与 t11 逐字节不变（8 核、sweetbattery=1）|

## 刷写

```
fastboot boot raphael-t12-gt9886-clean.img   # 日常验证
# 或
fastboot boot raphael-t12-gt9886-debug.img   # 排障：屏幕控制台常开
```

## 判读树

### A. 启动层

1. 出锁屏且流畅（8 核不变）→ 正常。
2. 万一卡 bootstrap → 长按电源强制重启回 t7 回报（理论上不可能：改动仅触摸/电池路径）。

### B. 触摸层（一次刷机看全链）

```
SWEET TOUCH: GT9886 pid err=0 [39 38 38 36] sensor err=0 id=? ver err=? sum=?
SWEET TOUCH: doze disable err=0 (staying awake for polling)
SWEET TOUCH: cfg send sensor? 784B err=0 flip=?
SWEET TOUCH: selected GT9886 normandy, 1080x2340, poll=10ms irq-hint=0
```

| 现象 | 含义 | 结论/下一步 |
|---|---|---|
| `pid err=0 [39 38 38 36]`（ASCII "9886"）| IC 身份确认 | 看 cfg 行 |
| `cfg send … err=0` | **配置已进入 IC** | **上手滑！触摸应当工作** |
| 触摸工作但方向不对 | sensor0/1 翻转选择错 | 回报 `sensor id=` 与 `flip=` 值，一行修正 |
| `pid err=0` 但字节非 "9886" | IC 固件态异常（需固件下发路径）| 回报 pid 字节，下轮做 gtx8 固件更新 |
| `pid err=6`（NACK）| 总线活了但 IC 无应答 | 回报 bus idle/live 行 |
| `cfg send: no 0x82 prepare` | IC 拒绝配置握手 | 回报该行 + pid 行 |
| `report err=5` 仍持续出现 | 帧读取仍有问题 | 回报 report 行频率 |

### C. 电池层

锁屏电池**不再是恒定 100%** 即成功。日志双保险：

| 日志行 | 含义 |
|---|---|
| `SWEET BATTERY: probe type=0/0xd sub=0/? st1=0/? v=0/? i=…` | **读通了**（type 应为 0xd=QG；错误码全 0）|
| `probe type=-1/…` | 读路径仍断（APID/observer）| 
| `SWEET BATTERY: PM8150B QG / estimated SOC, XX% XXXXmV …` | **真实读数上车**（百分比随实际变化）|
| `static fallback` 仍出现 | 数据校验失败（非读路径）| 回报 probe 行 |

### D. 日志取证（不变）

```
adb shell dd if=/dev/block/by-name/userdata of=/tmp/sweet-full.bin bs=4096 skip=$(( $(blockdev --getsize64 /dev/block/by-name/userdata) / 4096 - 1026 )) count=1026
```

（TWRP 下可用 `tail -c 4198400 /dev/block/sda31` 提取环区。）

### E. 回退

`fastboot boot` 回 **t7**（已知可用：8 核 + 按键）。

## 文件校验

| 文件 | SHA256 |
|---|---|
| `raphael-t12-gt9886-clean.img` | `3725736f0773ede73b59a35d1cabddc92decbc58aaa37f8a375fa09d46459c6b` |
| `raphael-t12-gt9886-debug.img` | `8dc5b5a98155949f552f8b8caa35bf772311560dff81bc63c47a7f89f639ba8b` |

内核：`78cbcaaf009a124366485d92c55db199e8ca7bd5e6602fbce50eb73350c59a59`（0094+0095，CI run 39588429883）；ADT：t8 系 8 核（f50510e0…，12588B）。
