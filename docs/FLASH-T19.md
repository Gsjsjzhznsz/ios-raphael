# t19（r27）刷写与判读 · 修复 femto 寄存器堆的三个硬件级死因

## 这一轮破了什么案（源码深挖 + 官方源裁决）

t18 照片五带逐行转录 + 源码逐行对照后，之前几轮的三个误判被推翻：

1. **"环绕控制台"几何定案**（读了 `pe_serial.c` 的 fbcon 实现：`fbcon_row = (fbcon_row + 1) % fbcon_rows`，行后留空行，每次开机清屏）：**照片上所有内容都来自同一次启动、同一次 probe**，没有"上一次启动残留"。光标冻在 `ep0 DEPSTARTCFG...` 行（其后两行空白 = 从未写过）。
2. **t16 照片重读**：同样是一次启动一次 probe——ep0 print 之后系统**继续跑完** DLIL/Skywalk/UFS 挂载/KEYS/触摸倒计时才定格。**楔死的只是 CPU0**（8 核里 1 个）；45 秒后触摸线程在残废总线上做时钟投票 → RPM/TZ 热复位。**40→45→50 秒"自动重启"的完整因果链就此闭合**，它是症状，不是独立故障。
3. **"字节复制 ×4"读值的真相**：t18 里 REFCLK **写 0x2 读回 0x02020202**、COMMON1 写 PLLBTUNE 读回 0x3b3b3b3b——这不是"轨没上电"（0103 的三票经查**对象、电压、编码全部正确**：raphael 官方板级 dtsi 明写 pm8150_l5@880 / l12@1800 / l2@3072，与我们的投票逐一吻合），而是 **AHB→PHY 桥访问降级**的特征。

## 三个硬件级死因与修复（0104）

| # | 死因 | 证据 | 修复 |
|---|------|------|------|
| 1 | **AHB2PHY 桥时钟（GCC 0x6a004）被门控** | raphael 官方内核 GCC（raphael-p-oss `gcc-sdmmagpie.c`）里有 `gcc_usb_phy_cfg_ahb2phy_clk`；字节复制读值 = 桥降级 | femto 序列前显式使能该分支并打印 `ahb2phy CBCR` |
| 2 | **QUSB2PHY_PRIM_BCR 脉冲打错了地址** | 主线 `gcc-sm8150.c` 写 0x12000，但 raphael 官方复位表是 **0x26000**（两表其余 USB/PCIe/UFS 复位全部一致，唯此项不同=主线错）；t17/t18 脉冲了一个不存在的寄存器，**PHY 从未真正复位** | 先脉冲 0x26000（权威），保留 0x12000 为次（已验证无害） |
| 3 | **GUSB3PIPECTL.SUSPHY（0xc2c0 bit17）从未清除** | Qualcomm commit 9bdbd5286ea5：遗留置 1 → 寄存器写失败 → 整机崩溃；主线对 sm8150 两个 dwc3 都挂 `dis_u3_susphy_quirk`；t16 没有 femto 代码也照样楔死在第一条 DEPCMD 写 | 与 GUSB2PHYCFG.SUSPHY 一并清除，打印前后值 |

另加两道防线与一件取证工具：

- **+20ms settle + 降级中止**：femto 序列后若回读仍是"字节复制/全零" → 打印 `register file degraded ... aborted` 干净返回，**不进 ep0**。从这版起任何失败 = 稳定锁屏 + 一张照片，**45 秒重启循环在机制上不可能再发生**。
- **`SWEET RST:` 复位原因分类器**：开机经 SPMI 只读 PM8150 PON 寄存器组（sid0 periph 0x8），自动分类**上一次**复位（PS_HOLD/SOFT = EL3/AOP 发起；PMIC_WD；FAULT；S3）。t18 那次 45 秒复位到底是谁拉的，这版开机第一行就告诉你。

## 刷写

```
fastboot boot raphael-t19-ahb2phy-bcr-clean.img
```

**先彻底关机再进 fastboot**（长按电源 10 秒以上）。rootfs 不用重刷，OTG 线保持连接。卡住想拍最后几行用 `-debug` 变体（屏幕控制台常开）。

## 判读树（一次刷机，逐行对号）

```
SWEET RST: subtype=... poff1=... -> <分类>         ← 上一次复位是谁拉的（t18 的 45s 之谜）
SWEET USB: ahb2phy CBCR 0x........ (on)            ← 桥时钟状态（on = 好消息；STUCK OFF = 桥死，下轮 SPMI 直查）
SWEET USB: hsphy pre-state COMMON0 0x....          ← ★若不再是 0x88888888 类重复字节 = 桥修好了
SWEET RPMH: (三票, 与 t18 相同)                     ← cmd-db 查址/投票/完成
SWEET USB: hsphy post-LDO COMMON0 ... (ldo err 0)
SWEET USB: hsphy up (femto): COMMON0 ... COMMON1 0x.... REFCLK 0x....   ← ★★决胜行
DEPCMD(0) canary 0x....
SWEET USB: GUSB3PIPECTL 0x.... -> 0x.... (U3 SUSPHY cleared)
ep0 DEPSTARTCFG/SETEPCONFIG/SETTRANSFRESOURCE
ep0 setup TRB armed                                 ← ★★★ 过了这行 = 五轮楔死正式终结
SWEET USB: running (DSTS ...)
（锁屏；主机枚举 ECM 网卡；ping 192.168.7.2）
```

**胜负判定：**

- **全胜** = `running` + 锁屏 + 主机出网卡 + `ping 192.168.7.2` 通 + 45 秒时触摸正常启动
- **`hsphy up (femto)` 回读正常但 ep0 后无下文**（GUSB3PIPECTL 行已打印、canary 后冻住）→ 剩余嫌疑 = DEPCMD 写路径本身，拍 `GUSB3PIPECTL` 那行发我
- **`register file degraded ... aborted` + 稳定锁屏**（不再重启！）→ 拍 `ahb2phy CBCR` + `pre-state` + `up (femto)` 三行发我：
  - `ahb2phy ... STUCK OFF` = 桥时钟开不起来 → 下轮从 SPMI/GCC 深查桥域
  - `ahb2phy on` 但读值仍重复字节 = 桥活着但 PHY 数字域没电/没复位 → 下轮 SPMI 直读 LDOA2/5/12 实际电压裁决
- **`SWEET RST:` 显示 PMIC watchdog / FAULT** = 45 秒复位另有元凶（PMIC 侧），与 USB 案并案处理
- **`SWEET RPMH` 某票失败**（`lookup matches=0` / `no empty idle ACTIVE TCS` / `timeout`）→ 拍那几行，taxonomy 同 FLASH-T18

## 回退

- `sweetusb=1`（探测但不启 gadget）、`sweettouch=0`（关 45 秒触摸线程）、`sweetusb=0`（全关）等 boot-arg 回退沿用；`sweetscale`/`sweetfb_fade` 等不变。
- 上一版：`raphael-t18-rpmhldo-clean.img`（r26）。
