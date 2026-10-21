# t18（r26）刷写与判读 · RPMh LDO 投票（PHY 模拟供电轨）

## 先回答你上一条消息：不要关 USB

t17 的照片把 USB 案子**破了 90%**：DWC3 控制器、GDSC、8 路时钟、QSCRATCH、软复位、事件缓冲、canary 读、ep0 寄存器读——**全部活着**；死的只有一件事：**femto PHY 的三条模拟供电轨**（ABL 交接时被丢弃）。关掉 USB 等于把一个 90% 工作正常、只差一步上电的栈整个扔掉，还失去 `ping 192.168.7.2` 这个判据。t13/t14 早已证明不开 USB 探测时系统无限稳定——重启从来不是"USB 的错"，是"摸了一个没供电的 PHY"的错。

## t17 实测结果（本版的出发点）

三段裁剪放大逐行转录你拍的照片后，完整时序第一次看清（这次屏幕同时留着**两次启动**的内容——45 秒复位是热复位，帧缓冲没清，early console 从上一个非空行继续写）：

**Boot A（45 秒重启前那次）：**
```
hsphy pre-state COMMON0 0x00000000 CTRL2 0x06666606 CTRL5 0x00000000 CFG0 0x00000000
hsphy up (femto): COMMON0 0x00000000 COMMON1 0x3b3b3b3b CTRL2 0x00000606 REFCLK 0x02020202   ← ★全是重复字节垃圾
QSCRATCH / VBUS override / soft reset 1ms / settle / event buffer —— 全部正常
DEPCMD(0) canary 0x00000000   ← 读通（DWC3 包装层活着）
ep0 DEPSTARTCFG...            ← ★第一条命令写楔死一个 CPU（和 t16 同一个死点）
（其余 CPU 继续启动到锁屏；45 秒倒计时到期 → 触摸线程上电/时钟投票撞上残废总线 → 硬件侧整体复位）
```

**Boot B（你拍照时这次）：** 同样的序列，死得更早——**pre-state 打印输出到一半**（"…CTR"处截断）：总线错误在 printf 途中被异步投递。屏幕上半部行 1-13 是 boot A 的遗留，行 14-72 是 boot B。

**三个决定性证据：**
1. `hsphy up (femto)` 的回读值 `0x3b3b3b3b / 0x02020202 / 0x06666606`——**重复字节模式 = 未供电外设总线的典型假读**。femto 的 15 步写全部写进了黑洞，一步都没粘住。
2. Linux `qcom_snps_hsphy_init()` 的**第一行就是 `regulator_bulk_enable(vdda-pll, vdda33, vdda18)`**——0102 移植时漏掉了这一步，这就是全部差别。
3. ~45 秒重启时刻与 `SWEET TOUCH: starting in 45 s` 倒计时到期**精确吻合**（t16 的"约 40 秒"也是同一事件）——触摸线程在残废系统上做 SE19 时钟投票 + TLMM 上电，触发了 RPM/TZ 侧的最终升级。重启是**症状**，不是独立故障。

## t18 做了什么（补丁 0103）

用移植里现成的 `sweet_rpmh.c`（SWEET 板上验证过 TCS 协议的 RPMh 投票器；raphael 的 apps_rsc 几何完全相同：drv-id 2、ACTIVE 2/SLEEP 3/WAKE 3、RSC 0x18220000、TCS 0x18220d00、cmd-db 定位器 0x0c3f000c——vendor sm8150.dtsi 逐字确认），在 femto 序列**之前**按 mainline raphael DTS 的接法投三根轨（全 HPM）：

| Linux 供电名 | raphael 节点 | RPMh 资源 | 电压 |
|---|---|---|---|
| vdda33 | vdda_usb_hs_3p1 = vreg_l2a_3p1 | `ldoa2` | 3072 mV |
| vdda-pll | vdd_usb_hs_core = vreg_l5a_0p875 | `ldoa5` | 880 mV |
| vdda18 | vdda_usb_hs_1p8 = vreg_l12a_1p8 | `ldoa12` | 1800 mV |

顺序对齐 Linux：**regulators → BCR 复位脉冲 → 15 步 femto 序列**。另加两道防线：

- `hsphy post-LDO ...` 打印：投票后再读一次 COMMON0/CTRL2/CTRL5/CFG0——**值从垃圾变成非重复字节 = 轨真的上来了**（判据眼见为实）
- **任何一票失败 → gadget start 干净中止**（打印 `LDO vote failed ... no ep0 wedge` 后直接返回）：读死 PHY 返回垃圾但能活着，而 ep0 命令写会楔死启动 CPU 把每次失败变成 45 秒重启循环。从这版起，失败模式从"重启循环"变成"稳定锁屏 + 一张 RPMH 打印照片"

其余与 t17 完全一致（8 核、触摸 45 秒、电池、显示、cmdline、ADT、shim、DTB）。

## 刷写

```
fastboot boot raphael-t18-rpmhldo-clean.img
```

**先彻底关机再进 fastboot**（长按电源 10 秒以上）。rootfs 不用重刷，OTG 线保持连接。

## 判读树（一次刷机，逐行对号）

```
SWEET RPMH: ldoa2 addr=0x... slave=4 ...            ← cmd-db 查到三根轨
SWEET RPMH: TCSx ACTIVE 3072 mV mode=7 enable=1 ...
SWEET RPMH: TCSx done=1 ... cmd-status=...          ← 三票都要有
SWEET USB: hsphy post-LDO COMMON0 0x... (ldo err 0)  ← ★值变非重复字节=轨上来了
SWEET USB: hsphy up (femto): COMMON0 ... COMMON1 0x30-ish CTRL2 含 SUSPEND_N   ← ★写进去了
DEPCMD(0) canary 0x00000000
ep0 DEPSTARTCFG/SETEPCONFIG/SETTRANSFRESOURCE
ep0 setup TRB armed                                  ← ★★ 过了这行 = 楔死修复
SWEET USB: running (DSTS ...)
（进锁屏；主机枚举 ECM 网卡；ping 192.168.7.2）
SWEET TOUCH: mapping GCC/TLMM-south/SE7 ...          ← 45 秒时触摸在健康系统上首测
```

**胜负判定：**
- **全胜** = `running` + 锁屏 + 主机出网卡 + `ping 192.168.7.2` 通 + 45 秒时触摸线程正常启动（不再复位）
- **票失败但系统稳定**（`LDO vote failed ... aborted` + 锁屏正常）= 拍 `SWEET RPMH:` 那几行发我：
  - `lookup matches=0; refusing` = cmd-db 里资源名不是 ldoa2/ldoa5/ldoa12（命名约定差异）→ 下轮换拼写或 SPMI 直写
  - `no empty idle ACTIVE TCS` / `conflicting inherited request` = ABL 留了同轨旧投票 → 下轮复用/清槽
  - `timeout; TCS quarantined` = RPM 没应答 → 下轮 SPMI 直写 LDO 寄存器
- **票成功但 post-LDO 仍是重复字节垃圾** = RPM 收了票但轨没真上（AO/TCS 走错、或轨映射不同）→ 下轮 SPMI 直写兜底
- **post-LDO 干净、up (femto) 回读正常、但 ep0 仍楔死** = 时钟域问题 → 下轮全块 BCR + GCTL 重编

## 回退

- `sweetscale`/`sweetfb_fade`/`sweetusb=1` 等 boot-arg 回退沿用
- 整体回退：t7（r15，USB 修复前最后的稳定版）
- 本版只动 USB 路径的供电步骤，其余与 t17 同源
