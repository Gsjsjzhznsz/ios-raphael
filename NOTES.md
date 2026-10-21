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

## USB IP version is DWC_usb31, not classic DWC3 (patch 0099, t14 post-mortem)

t14 enabled `sweetusb=2` and froze the whole system right after
`soft reset done after 1 ms` (no timeout print even reached the console; the
second `fastboot boot` then stalled the SPMI GPIO census at PM8150B). Both
facts pinned against the Linux kernel source:

- **GSNPSID on raphael reads `0x33313130`** — Linux `dwc3_core_is_valid()`
  classifies `0x3331xxxx` as **DWC_usb31** (the USB 3.1 IP; the version then
  comes from DWC3_VER_NUMBER, not GSNPSID). The upstream sweet phone's
  controller is the **classic DWC3 v3.20a** (`0x5533320a`, documented in the
  upstream NOTES) — the USB gadget code was only ever proven on that IP.
- **Linux `dwc3_core_soft_reset()` has a DWC31-only rule**: after
  `DCTL.CSFTRST` clears, the device/endpoint clock domains must
  re-synchronize before any endpoint access — "for DWC_usb31 1.80a and
  prior, once DCTL.CSFRST bit is cleared, we must wait at least 50ms before
  accessing the PHY domain" (SM8150 is 2018 silicon = early DWC31). The
  t14 code issued ep0 DEPCMDs ~1 ms after the reset → bus wedge → whole
  system freeze (the config-NoC path is shared by all CPU clusters).
- Fix in 0099: QSCRATCH VBUS override moved **before** the reset (Linux
  dwc3-qcom does the override at probe; the wrapper registers survive the
  core reset), a **100 ms post-reset settle** (2× the Linux requirement),
  and a breadcrumb print between every init phase (ue0 → QSCRATCH → VBUS
  override → soft reset → settle → event buffer → ep0 commands → setup TRB
  → running) so any future wedge is localizable from a photo of the screen.
- The SPMI stall: keys thread (20 ms), GPIO census and the t14 5 s battery
  poll all issued observer commands with no mutual exclusion, while Linux
  serializes **every** pmic-arb command with one spinlock. After a crash the
  PMIC keeps its state across warm reboots (no power cycle), so the census
  could grind against a wedged SID 2 (PM8150B). Patch 0100 adds one global
  command gate for all users and makes the census opt-in (`sweetcensus=1`).
  **Operational rule: after any crash, power the phone fully off before the
  next `fastboot boot`.**

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

## Battery: PM8150B fg-gen4 (t13 / 0096 research, 2026-10-21)

The PM8150B fuel gauge is fg-gen4, NOT a QG (QG is the sm8250+ PMIC gauge).
Split peripherals, all on SPMI SID 2 (vendor pm8150b.dtsi):

- `fg-batt-soc@0x4000`: PERPH_TYPE +0x04 = 0xd, monotonic SOC +0x09
  (0-255, shadow copy +0x0A; vendor fg_get_msoc() percent mapping:
  255->100, 0->0, else round((raw-1)*98/253)+1)
- `fg-batt-info@0x4100`: SYS_BATT +0x07 (battery-missing bits 0-2),
  VBATT +0xA0 / shadow +0xA6 (uV = raw*122070/1000, 0x8000 ~= 4000 mV),
  IBATT +0xA2 / shadow +0xA8 (uA = sign16(raw)*488281/1000, discharge > 0)
- SMB5 charger: CHGR@0x1000 BATTERY_CHARGER_STATUS_1 +0x06 state machine
  (0 INHIBIT, 1 TRICKLE, 2 PRE, 3 FULLON, 4 TAPER = charging, 5 TERMINATE
  = full, 7 DISABLE), USBIN@0x1300 INT_RT_STS +0x10 BIT(4) = plugged.
- Key sources: qpnp-fg-gen4.c, fg-util.c (getters + shadow-check pattern),
  fg-reg.h, smb5-reg.h, pm8150b.dtsi (LineageOS android_kernel_xiaomi_sm8150,
  branch lineage-19.1, drivers/power/supply/qcom/). Cached under work/ref/fg.
- If the monotonic SOC ever freezes while voltage keeps moving, the FG
  algorithm needs the battery profile via fg-memif SRAM DMA (fg-memif@0x4300,
  MEM_IF_* registers in fg-reg.h) - next research item.

## Pop-up selfie camera motor (t13 research, archived for a future round)

raphael's pop-up camera is driven by a TI DRV8846 dual H-bridge stepper
(vendor drivers/misc/drv8846.c, cached work/ref/motor/):

- TLMM GPIOs (all SOUTH tile, the 0093 driver already reaches them):
  mode0=21, mode1=33, sleep=35, dir=9, pwren=130; step-mode = 2
  (mode1=1/mode0=0) per raphael-sm8150.dtsi.
- PWM: PM8150L LPG channel 1 (`&pm8150l_pwm`, pwms = <... 1 1000000>);
  motion profile: ramp 625000 ns (1.6 kHz) 50 ms -> high 52083 ns
  (~19.2 kHz, the LRA resonance) 720 ms -> ramp down. sleep=1 during
  motion, dir pin picks up/down, hrtimer drives the state machine.
- Missing piece: PM8150L LPG register map (pm8150l.dtsi + pwm-qcom-lpg
  driver, PM8150L SID unknown - fetch before attempting).

## Vibration motor (open lead)

No vibrator node in raphael-sm8150.dtsi / overlay. Candidate driver:
leds-qpnp-vibrator-ldo.c (present in the vendor kernel) - an LDO-driven
eccentric motor on PM8150L. Needs pm8150l.dtsi + the LDO regulator mapping
to confirm. The drv8846 node above is the CAMERA motor, not haptics.

## Process lesson (0096 CI round)

The local work/xnu tree drifted from the repo patch lineage (Edit-tool
tab->space pollution in regions old patches never touched). Patch hunks
generated against the drifted tree fail on CI with
"patch failed: ...:55" and darwin-xnu-build SKIPS failed patches with only
a warning - producing a green build missing the change (run 39593077146).
Countermeasures now in place: regenerate board patches against the CI
buildtree (canonical) base; xnu.yml fails the run if any NNNN-(raphael|
sweet)-*.patch is skipped. Also: C++ default arguments live in the
declaration only, but the out-of-line definition must still list ALL
parameters (publish() lost its 10th param -> IOPMPowerSource::timeRemaining
getter shadowed the name).

## Raphael display panel: samsung EA8076 (t14 research)

The panel is NOT "sofef00" - that was a wrong lead. MiCode
Xiaomi_Kernel_OpenSource raphael-p-oss has the panel in DTS
(arch/arm64/boot/dts/qcom/dsi-panel-samsung-fhd-ea8076-*-cmd.dtsi,
5 variants: plain / f1 / f1mp / f1p2 / f1p2-2 + a secondary-supplier
dsi-panel-ss-fhd-ea8076-cmd.dtsi; all share the brightness scheme):

- DSI **command mode**, 1080x2340, 4 lanes, burst traffic,
  dma-trigger=trigger_sw / mdp-trigger=none, dsi_lp_mode commands
- Brightness: DCS 0x51 with a **big-endian** 11-bit level (the "_ss"
  variant, mipi_dsi_dcs_set_display_brightness_ss in the vendor's
  drm_mipi_dsi.c), max 2047 (qcom,mdss-brightness-max-level).
  0x53 is only sent for HBM/dimming events (hbm-on=E8, dimmingon=28,
  dimmingoff=20), NOT per brightness level. 0x55 = ACL levels.
- Display off: DCS 0x28 then 0x10 (sleep, 120ms); on sequence ends with
  0x29. The on-command includes panel-specific unlock (F0/FC 5A 5A) and
  Gamma/CRC blobs - brightness does NOT need the unlock.
- Off-command state at boot: ABL programs the whole pipeline and leaves
  it streaming the splash; our kernel only injects commands.

## DSI 6G v2.2 command TX (SM8150, dsi ctrl0 @ 0x0ae94000)

From vendor dsi-staging (dsi_ctrl.c / dsi_ctrl_hw_cmn.c /
dsi_ctrl_reg.h), the embedded-mode FIFO path used by 0098:

- Packet dword 0 = [WC_lo WC_hi data_id flags]: data_id = dtype | vc<<6;
  flags bit7 = LASTCOMMAND, bit6 = payload present, bit5 = embedded BTA
  (read). Payload follows, 0xff-padded to a dword. NOTE: this kernel's
  mipi_dsi_create_packet puts WC first (bytes 0/1) - NOT the mainline
  order (data_id first).
- DSI_COMMAND_MODE_DMA_CTRL (0x3c): bit28 embedded, bit26 LP, bits
  31/30/29/24 clear. FIFO path also programs DSI_TEST_PATTERN_GEN_CTRL
  (0x15c) = BIT(1)|BIT(2)|0x3<<16 and pushes dwords through
  DSI_TEST_PATTERN_GEN_CMD_DMA_INIT_VAL (0x17c);
  DSI_TPG_DMA_FIFO_RESET (0x1ec) pulse 1us between transfers.
- DSI_DMA_CMD_LENGTH (0x4c) = padded byte count; trigger =
  DSI_CMD_MODE_DMA_SW_TRIGGER (0x90) = 1; completion =
  DSI_INT_CTRL (0x110) bit 0, write-1-to-clear (pollable).
- Memory path (kickoff_command): same trigger, DMA address in
  DSI_DMA_CMD_OFFSET (0x48, 32-bit - buffer must live under 4GB),
  DSI_DMA_FIFO_CTRL (0x50) bits 16+20 disable watermarks.

## SMB5 charging input path (PM8150B, SPMI SID 2)

Peripheral bases (pm8150b.dtsi): chgr 0x1000, dcdc 0x1100, batif
0x1200, usb 0x1300, dc 0x1400, typec 0x1500, misc 0x1600. Registers
0097 reads on input transitions: USBIN_RT_STS 0x1310 (BIT4 = plugin),
APSD_RESULT 0x1308 (single bit: SDP 01/DCP 08/CDP 04/FLOAT 10/QC2 20/
QC3 40), ICL_STATUS 0x1107 (input current limit, ~50mA units),
POWER_PATH_STATUS 0x110b (BIT4 use-USBIN, BIT0 valid input),
CHGR_STATUS_5 0x100b (charge stage enables - all zero means charging
disabled at the command level), CHGR_STATUS_1 0x1006 state machine
(0 INHIBIT .. 5 TERMINATE, 7 DISABLE).
t13 blind spot: poll() only logged on percent change, so plug/unplug
events never reached the log. t14: 5s quick poll + transition line.

## ios-topaz / upstream study (t14)

- topaz (MakrSas/ios-topaz) = sibling fork of dipa-studio/ios-sweet for
  Redmi Note 12 4G (SM6225). xnu/patches = the SAME 0001-0079 lineage,
  no device patches yet; its own work is the shim (boot image v4,
  "Gold hand-off", GIC setup) + tools (mkiosroot, root-tweaks). Nothing
  directly portable to raphael this round (our boot v2 works; our
  packaging tools match upstream). Worth re-checking when their device
  patches (0080+) land.
- Upstream ios-sweet after 0079: only 0080 (IPv4 route change logging)
  and 0081 (ue0 reports active link) - both already in our tree as
  0080-sweet-net-trace / 0081-sweet-usb-link-state. Plus
  tools/sweet-usbnet.sh (we have it), QEMU tooling and a docs site.

## Process lesson (t14 round)

Edit-tool whitespace normalization converted WHOLE FILES tab->space
(the t13 lesson was region-local). Any patch generated from such a tree
carries space context against the canonical tab tree. Fix: generate ALL
board-patch content via scripts (scripts/apply_t14_battery.py,
scripts/apply_t14_display.py) that do byte-exact anchored replacements
with explicit \t on the git-committed canonical base, then roundtrip
(git checkout HEAD -- file; git apply patch; diff saved==applied).
