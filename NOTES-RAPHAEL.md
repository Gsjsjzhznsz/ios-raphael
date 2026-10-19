# raphael port (Redmi K20 Pro, SM8150) — working notes

Status: adaptation complete, awaiting first on-device boot. Everything below
was extracted from the stock V12.5.6.0.RFKCNXM firmware (boot.img SoC DTBs +
the `android_kernel_xiaomi_raphael` DTS sources) and cross-checked; the bring-up
method mirrors sweet exactly.

## Why raphael is a near drop-in

SM8150 and SM7150 are the same Qualcomm generation. These are IDENTICAL to
sweet and needed zero changes:

| Item | Value (both SoCs) | Evidence |
| --- | --- | --- |
| GICD / GICR | 0x17a00000 / 0x17a60000 (stride 0x20000) | sm8150.dtsi intc; raphael_0.dtb |
| Timer PPIs | phys INTID 18 (PPI 2), virt INTID 19 (PPI 3), 19.2 MHz | sm8150.dtsi timer node |
| UFS host | ufshc@1d84000, left initialized by ABL | sm8150.dtsi; raphael_0.dtb |
| SPMI arbiter | core 0xc440000, obsrvr 0xe600000, cnfg 0xc40a000 | sm8150.dtsi spmi@c440000 |
| RPMh apps RSC | 0x18220000, TCS 0x18220d00 | sm8150.dtsi mailbox@18220000 |
| PSHOLD | 0x0c264000 | sm8150.dtsi restart@c264000 |
| ABL framebuffer | 0x9c000000 (cont_splash_region, 0x2400000) | sm8150.dtsi reserved-memory |
| CPU topology | 8 cores, MPIDR Aff1 = core (0x000..0x700) | raphael_0.dtb cpu@0/100/.../700 |
| ARMv8.2, no PAC, 16K granule, crypto ext | same Kryo 400 family | |

Differences (all handled behind `#if defined(ARM64_BOARD_CONFIG_RAPHAEL)`):

| Item | sweet (SM7150) | raphael (SM8150) |
| --- | --- | --- |
| Panel | 1080x2400 AMOLED | 1080x2340 AMOLED (presented as iPhone X 1125x2436, same as sweet) |
| imem restart_reason | 0x146aa65c | 0x146bf65c (imem@146bf000 + 0x65c) |
| Touch SE | SE7 @ 0xa84000 (wrap1, vote BIT(23)@0x5200c, RCG 0x18148) | SE19 @ 0xc88000 = GCC_QUPV3_WRAP2_S2 (vote BIT(6)@0x52014, RCG 0x1e3a8, CBCRs 0x1e004/0x1e008/0x1e3a4) |
| TLMM | north block 0x03900000 | one block 0x03000000 |
| Touch IC | Goodix GT9896 "Yellowstone" (0x4180 protocol, 8-byte head) | Goodix GT9889 @0x5d, GTX8 "0x824E" protocol (see below) |
| Touch power | RPMh vote "ldoc11" 3200 mV + GPIO90 | TLMM GPIOs only: vdd 3v3 = GPIO98, avdd 1v8 = GPIO100 (no RPMh vote needed) |
| Touch pins | reset GPIO8, IRQ GPIO9, SDA/SCL GPIO6/7 (qup11 func 1) | reset GPIO54, IRQ GPIO122, SDA/SCL GPIO57/58 (qup19 func 2) |
| Volume-up | PM6150L SID4 GPIO2 @ 0xc110 | NOT mapped yet (withheld; see TODO) |
| CPU clocks | A76 2.304G / A55 1.8048G | cpu0 Prime 2.8416G, cpu1-3 Gold 2.4192G, cpu4-7 Silver 1.8048G |
| Boot image | header v2, DTB via --dtb | stock is header v1, DTB appended to kernel blob |

## GT9889 event protocol (from goodix_driver_gt9886 in raphael-r-oss)

- Version block at 0x8240 (probe: 8-byte read at 0x5d, non-zero = alive).
- Event frame at 0x824E: byte[1] = status (bit4 have_key, bits3:0 touch count);
  points start at 0x8250, 8 bytes each: `id, x_lo, x_hi, y_lo, y_hi, w, pressure, area`
  (little-endian x/y, pen marks bit7 of the id byte).
- Ack: write one zero byte to 0x824E after reading.
- Touch panel range 1080x2340 (`panel-max-x 1079`, `panel-max-y 2339`), scaled to
  the presented 1125x2436 canvas by SweetHID like sweet does.

## Memory plan (same trick as sweet)

- Fixed reserved-memory carve-outs all sit in the low bank (0x86200000 removed
  regions through 0xa4c00000 cdsp_sec; cont_splash 0x9c000000-0x9e400000).
- `--highmem` kernel RAM = upper bank 0x100000000 + 0xfcc00000 (~3.95 GiB),
  exactly like sweet; works on 6 GB and 8 GB units alike.
- Low-bank fallback (PHYS_BASE 0xb0000000) unchanged from sweet.

## Keys

- Power = PON KPDPWR (PPID 0x008 bit0), volume-down = PON RESIN (bit2), via the
  same SPMI observer EXT_READL flow as sweet. pm8150.dtsi confirms resin -> KEY_VOLUMEDOWN.
- Volume-up is NOT in any raphael DTS (no gpio-keys node, no KEY_VOLUMEUP).
  Withheld in 0083 until the real source is identified from a live device:
  check `/proc/device-tree` under Android, or dump the live FDT from fastboot
  boot of the shim (the shim prints the DTB pointer; sweet-log tooling reads it).

## What still needs device validation (bring-up order)

1. `fastboot boot` of the shim image (header v1 + appended SM8150 v2 DTB).
   Watch: GIC probe line, PSCI version, framebuffer console at 1080x2340.
2. cpus=8: PSCI CPU_ON should just work (identical MPIDR layout + PSCI in
   sm8150 XBL). Fallback boot-arg cpus=1.
3. UFS root: same driver, same host controller address; verify with the
   persistent log (tools/sweet-log-pull.sh) reading the userdata log ring.
4. Display: ABL hands off the splash framebuffer at 0x9c000000; the ADT fbcon
   carries 1080x2340/stride 4320.
5. Touch: SE19 clock vote + GT9889 probe (0x8240). If the IC does not answer,
   check TLMM GPIO98/100 latch state in the log first.
6. iOS 16.7.16 rootfs: identical image + tweaks as sweet (mkiosroot.sh),
   flashed to userdata.

## Firmware facts (V12.5.6.0.RFKCNXM, Android 11, cn)

- boot.img: header v1, page 4096, kernel 43958745 bytes (Image.gz + 4 SoC DTBs),
  cmdline `... androidboot.usbcontroller=a600000.dwc3 ...` (USB DWC3 @ 0xa600000
  — relevant for the later ue0/USB-Ethernet port of patches 0072-0077).
- Four SoC DTBs in the kernel blob: sm8150 v2 (raphael_0), sm8150p v2 (raphael_1),
  sm8150p v1 (raphael_2), sm8150 v1 (raphael_3). K20 Pro = SM8150 v2.
- Board-level nodes (touch, panel, keys) live in dtbo.img overlays; the DTS
  sources in `android_kernel_xiaomi_raphael` (branch lineage-19.0) document them:
  raphael-sm8150.dtsi, raphael-pinctrl.dtsi, sm8150-qupv3.dtsi.
- Not in git: the extracted DTBs, firmware images, Apple artifacts.
