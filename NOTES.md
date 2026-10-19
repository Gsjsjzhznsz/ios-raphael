# raphael port (Redmi K20 Pro, SM8150) — working notes

Status: adaptation complete, awaiting first on-device boot. Everything below
was extracted from the stock V12.5.6.0.RFKCNXM firmware (boot.img SoC DTBs +
the `android_kernel_xiaomi_raphael` DTS sources) and cross-checked against
mainline Linux. Updates 2026-10-19: volume-up settled from the mainline DTS,
touch second source corrected to ST FingerTipS, USB constants verified
per-SoC (patches 0085-0087).

## SM8150 platform facts (as used by the port)

| Item | Value | Evidence |
| --- | --- | --- |
| GICD / GICR | 0x17a00000 / 0x17a60000 (stride 0x20000) | sm8150.dtsi intc; raphael_0.dtb |
| Timer PPIs | phys INTID 18 (PPI 2), virt INTID 19 (PPI 3), 19.2 MHz | sm8150.dtsi timer node |
| UFS host | ufshc@1d84000, left initialized by ABL | sm8150.dtsi; raphael_0.dtb |
| SPMI arbiter | core 0xc440000, obsrvr 0xe600000, cnfg 0xc40a000 | sm8150.dtsi spmi@c440000 |
| RPMh apps RSC | 0x18220000, TCS 0x18220d00 | sm8150.dtsi mailbox@18220000 |
| PSHOLD | 0x0c264000 | sm8150.dtsi restart@c264000 |
| ABL framebuffer | 0x9c000000 (cont_splash_region, 0x2400000) | sm8150.dtsi reserved-memory |
| CPU topology | 8 cores, MPIDR Aff1 = core (0x000..0x700) | raphael_0.dtb cpu@0/100/.../700 |
| ISA | ARMv8.2, no PAC, 16K granule, crypto extensions (Kryo 485) | |

Board-specific values, all handled behind `#if defined(ARM64_BOARD_CONFIG_RAPHAEL)`:

| Item | raphael (SM8150) |
| --- | --- |
| Panel | 1080x2340 AMOLED (`samsung,ams639rq08` per mainline; presented to iOS as an iPhone X 1125x2436 canvas) |
| imem restart_reason | 0x146bf65c (imem@146bf000 + 0x65c) |
| Touch SE | SE19 @ 0xc88000 = GCC_QUPV3_WRAP2_S2 (vote BIT(6)@0x52014, RCG 0x1e3a8, CBCRs 0x1e004/0x1e008/0x1e3a4) |
| TLMM | one block 0x03000000 |
| Touch IC | Goodix GT9889 @0x5d, GTX8 "0x824E" protocol (see below) |
| Touch power | TLMM GPIOs only: vdd 3v3 = GPIO98, avdd 1v8 = GPIO100 (no RPMh LDO vote needed) |
| Touch pins | reset GPIO54, IRQ GPIO122, SDA/SCL GPIO57/58 (qup19 func 2) |
| Volume-up | PM8150 (SID0) GPIO6 @ 0xc500: RT_STS 0xc510, MODE 0xc540, EN 0xc546, PPID 0x0c5, active-low (mainline raphael dts `gpio-keys`) |
| CPU clocks | cpu0 Prime 2.8416G, cpu1-3 Gold 2.4192G, cpu4-7 Silver 1.8048G |
| Boot image | stock is header v1, DTB appended to the kernel blob |

## GT9889 event protocol (from goodix_driver_gt9886 in raphael-r-oss)

- Version block at 0x8240 (probe: 8-byte read at 0x5d, non-zero = alive).
- Event frame at 0x824E: byte[1] = status (bit4 have_key, bits3:0 touch count);
  points start at 0x8250, 8 bytes each: `id, x_lo, x_hi, y_lo, y_hi, w, pressure, area`
  (little-endian x/y, pen marks bit7 of the id byte).
- Ack: write one zero byte to 0x824E after reading.
- Touch panel range 1080x2340 (`panel-max-x 1079`, `panel-max-y 2339`), scaled
  to the presented 1125x2436 canvas by SweetHID.

## Memory plan

- Fixed reserved-memory carve-outs all sit in the low bank (0x86200000 removed
  regions through 0xa4c00000 cdsp_sec; cont_splash 0x9c000000-0x9e400000).
- `--highmem` kernel RAM = upper bank 0x100000000 + 0xfcc00000 (~3.95 GiB),
  above every Qualcomm XPU carve-out; works on 6 GB and 8 GB units alike.
- Low-bank fallback: PHYS_BASE 0xb0000000.

## Keys

- Power = PON KPDPWR (PPID 0x008 bit0), volume-down = PON RESIN (bit2), via
  the generic SPMI observer EXT_READL flow. pm8150.dtsi confirms
  resin -> KEY_VOLUMEDOWN.
- **Volume-up = PM8150 GPIO6 (closed 2026-10-19).** No raphael DTS in the
  Xiaomi tree declares a gpio-keys node, but the mainline
  `sm8150-xiaomi-raphael.dts` does: `key-vol-up { gpios = <&pm8150_gpios 6
  GPIO_ACTIVE_LOW>; linux,code = <KEY_VOLUMEUP>; }` with `vol_up_n` on
  `pm8150_gpios` gpio6, input + bias-pull-up. Mapping to our SPMI observer
  scheme: PPID = (SID0 << 8) | (0xc500 >> 8) = 0x0c5; poll RT_STS (0xc510)
  bit0, active-low — the generic `!(gpio & 1)` polarity logic. ABL reads the
  same key for its fastboot menu, so it is configured as input by firmware
  before we run. Patch 0085 additionally logs a one-shot census of every PMIC
  GPIO block (type 0x10-0x13: mode/en/rt) so the first boot confirms the
  mapping live.

## Touch second source: ST FingerTipS, NOT FocalTech (correction 2026-10-19)

The raphael kernel source carries two touch stacks:
`drivers/input/touchscreen/goodix_driver_gt9886` (the one the MIUI DTS
enables, GT9889 @0x5d) and `drivers/input/touchscreen/fts_521`. Earlier notes
read "fts" as FocalTech (addr 0x38, regs 0xa3/0x9f) — **wrong**:
`fts_521` is STMicroelectronics FingerTipS (fts.h: `FTS Capacitive touch
screen controller (FingerTipS)`, `marco.cali@st.com`):

- I2C slave 0x49 (`I2C_SAD`); hw-register access = write `0xFA` + 4
  big-endian address bytes, then read (fts_lib/ftsIO.c `fts_writeReadU8UX`,
  I2C build has no dummy byte).
- Chip id at 0x20000000 (`ADDR_DCHIP_ID`), fw version at 0x20000004.
- Event FIFO: write `0x86` (`FIFO_CMD_READALL`, I2C), read 8 bytes; byte7
  bits4:0 = remaining events, drain them the same way; each event is 8
  bytes, id = b[0]>>4 (0x1 enter / 0x2 motion / 0x3 leave / 0x4 status /
  0x5 user / 0xf error), touch id = b[1]>>4, type = b[1]&0xf (1 = finger),
  x = ((b[3]&0xf)<<8)|b[2], y = (b[4]<<4)|(b[3]>>4) (fts.c
  `fts_enter_pointer_event_handler` etc.).

Both the MIUI DTB and the mainline DTS enable only the Goodix, so ST FTS is
likely carried dead code from another Xiaomi device — but howtocuddle's
mainline tree uses an ftsIO-based touch fix, so the possibility is real.
Patch 0086 therefore: probes 0x49 read-only and logs the chip id; if the
Goodix probe fails and 0x49 answers, it polls the FIFO (still read-only —
no panel-init/sense-on writes, so sensing must be inherited from the
previous OS boot; after a fresh power-up the FIFO stays silent).

## USB (patch 0087, generic USB device/Ethernet path on SM8150)

Generic driver constants from the shared USB bring-up series (patches
0072-0077), verified against SM8150 via mainline sm8150.dtsi +
gcc-sm8150.c:

| Item | raphael (SM8150) |
| --- | --- |
| DWC3 core | 0x0a600000 (usb_1_dwc3) — generic value, no change |
| wrapper qscratch | 0x0a6f8800 (usb@a6f8800) — generic value, no change |
| QUSB2 HS PHY | 0x088e2000 (usb_1_hsphy; 7nm snps hs phy, ref = CXO directly) — generic value, no change |
| GDSC USB30_PRIM | 0x0f004 — generic value, no change |
| USB30 master/sleep/utmi CBCR | 0x0f010/14/18 — generic value, no change |
| CFG_NOC_USB3_PRIM_AXI | **0x0f078** (generic constant was 0x0502c) |
| AGGRE_USB3_PRIM_AXI | **0x0f07c** (generic constant was 0x8201c) |
| phy ref branch | none for the HS PHY (CXO direct); wrapper ref = USB3_SEC_CLKREF **0x8c028** (note: 0x8c010 on this SoC is gpu_iref — do not use) |

As with any Qualcomm ABL, `fastboot boot` hands over a powered, clocked
controller (the fastboot menu itself is USB30_PRIM), so the driver only
restarts the device controller; boot-arg `sweetusb=2` starts it, `sweetusb=1`
(default) reports state only. The stock boot.img cmdline confirms the
controller: `androidboot.usbcontroller=a600000.dwc3`.

## What still needs device validation (bring-up order)

1. `fastboot boot` of the shim image (header v1 + appended SM8150 v2 DTB).
   Watch: GIC probe line, PSCI version, framebuffer console at 1080x2340.
2. cpus=8: PSCI CPU_ON should just work (MPIDR layout + PSCI in sm8150 XBL).
   Fallback boot-arg cpus=1.
3. UFS root: verify with the persistent log (tools/sweet-log-pull.sh) reading
   the userdata log ring.
4. Display: ABL hands off the splash framebuffer at 0x9c000000; the ADT fbcon
   carries 1080x2340/stride 4320.
5. Touch: SE19 clock vote + GT9889 probe (0x8240). If the IC does not answer,
   check TLMM GPIO98/100 latch state in the log first, then the `probe ST FTS
   0x49` line (patch 0086) for the second-source possibility.
6. Keys: log lines `SWEET KEYS: census ...` (patch 0085) and vol-up press
   events; power/volume-down are plain PON reads.
7. USB: with `sweetusb=2`, `lsusb` on the host should show the CDC-ECM
   device; then `tools/sweet-usbnet.sh` + `tools/sweet-log.py` for live logs.
8. iOS 16.7.16 rootfs: built with mkiosroot.sh + sweet-root-tweaks.py,
   flashed to userdata.

## Firmware facts (V12.5.6.0.RFKCNXM, Android 11, cn)

- boot.img: header v1, page 4096, kernel 43958745 bytes (Image.gz + 4 SoC DTBs),
  cmdline `... androidboot.usbcontroller=a600000.dwc3 ...` (USB DWC3 @ 0xa600000
  — confirmed by the USB port in patch 0087).
- Four SoC DTBs in the kernel blob: sm8150 v2 (raphael_0), sm8150p v2 (raphael_1),
  sm8150p v1 (raphael_2), sm8150 v1 (raphael_3). K20 Pro = SM8150 v2.
- Board-level nodes (touch, panel, keys) live in dtbo.img overlays; the DTS
  sources in `android_kernel_xiaomi_raphael` (branch lineage-19.0) document them:
  raphael-sm8150.dtsi, raphael-pinctrl.dtsi, sm8150-qupv3.dtsi.
- Not in git: the extracted DTBs, firmware images, Apple artifacts.

## External sources used (beyond the firmware)

- Mainline DTS: `[PATCH v2 0/3] Add Xiaomi Redmi K20 Pro (Raphael)`
  (patchew.org/linux/20251104221657.51580-1-pc1598@mainlining.org) —
  volume-up key, goodix@5d on i2c19, panel `samsung,ams639rq08`,
  pm8150_gpios vol_up_n.
- github.com/howtocuddle/xiaomi_raphael — 6.18 mainline status: display
  (ams639rq08), touch, cameras; confirms the raphael mainline story.
- github.com/ZakoClubROM/android_kernel_xiaomi_raphael (lineage-19.0) —
  `goodix_driver_gt9886/` and `fts_521/` (ST FingerTipS) driver sources,
  fts protocol facts above.
- mainline sm8150.dtsi / gcc-sm8150.c — USB address and clock table above.
- postmarketOS wiki (xiaomi-raphael) and the LineageOS raphael device tree —
  recovery, kernel-fork and bring-up pointers.
