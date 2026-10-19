# iOS 16 on Redmi K20 Pro ("raphael", SM8150) — port guide

Same idea as the sweet port: Apple's open-source XNU kernel (xnu-8796) on
Qualcomm hardware, running the **unmodified iPhone X iOS 16.7.16 userland**.
Read the main README.md and NOTES.md first; this file only covers what
differs on raphael. Hardware facts and register-level evidence live in
NOTES-RAPHAEL.md.

Status: adaptation complete, kernel + shim build in CI, first test image
packaged — not yet booted on hardware. Three follow-up patches (0085-0087,
2026-10-19) closed the last bring-up gaps using public raphael resources:
**volume-up** (mainline DTS), **ST FingerTipS touch** as the second-IC path
(the old "FocalTech" assumption was wrong — see NOTES-RAPHAEL.md), and the
**USB device/Ethernet port** of patches 0072-0077. Everything is
`#if defined(ARM64_BOARD_CONFIG_RAPHAEL)`-guarded — building SWEET is
unaffected.

## Prerequisites

- Redmi K20 Pro (raphael, global/cn/india), **unlocked bootloader**. 6 or 8 GB.
- A Linux PC with `adb`/`fastboot`, `python3`, `pip3 install mkbootimg`.
- A GitHub account (fork this repo; public repos get free macOS runner minutes).
- The iOS 16.7.16 (20H392) iPhone X IPSW from Apple (same as sweet; not
  distributed here).
- Your stock raphael boot.img (MIUI V12.5.6.0 tested): extract it from the
  fastboot ROM tgz (`images/boot.img`) or pull it from the device. Only its
  embedded SoC DTB is used; never upload it anywhere.

## 1. Kernel (GitHub Actions, macOS runner)

Fork the repo, then run the `xnu` workflow **with machine_config = RAPHAEL**:

```sh
gh workflow run xnu.yml -R YOU/ios-sweet -f machine_config=RAPHAEL -f kernel_config=DEVELOPMENT
gh run watch          # ~8-10 min
gh run download RUN_ID -R YOU/ios-sweet -n xnu-kernel -D xnu/out
# -> xnu/out/kernel.development.raphael
```

Optionally also run the `raphael` workflow (ubuntu) to get the prebuilt shim
blob (artifact `raphael-shim`, contains `Image`); otherwise build it locally:

```sh
cd shim && RAPHAEL=1 ./build.sh        # needs aarch64-linux-gnu-gcc + mkbootimg
```

## 2. iOS rootfs (identical to sweet)

Follow README.md steps 0-2 unchanged: backup partitions, build the 16 GB
HFS+ root image from the IPSW (`tools/mkiosroot.sh` + `sweet-root-tweaks.py`),
flash to userdata. Nothing here is raphael-specific.

## 3. Boot image (python only)

```sh
python3 tools/mkadt.py shim/out/sweet-raphael.adt --raphael --highmem
python3 tools/mkpayload.py xnu/out/kernel.development.raphael \
    shim/out/sweet-raphael.adt shim/out/payload-raphael.bin \
    --cmdline 'debug=0xc serial=3 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30'

# shim blob: CI artifact (raphael-shim/Image) or local shim/out/Image
python3 tools/package-raphael.py shim-dir payload-raphael.bin stock/boot.img shim-boot-raphael.img
```

`package-raphael.py` extracts the SM8150 v2 SoC DTB from your stock boot.img
and packs a **header v1** image exactly like the stock layout (v2 is not
verified on raphael ABL). `cpus=1` is the safe fallback for a first boot; add
`sweettouch=0 sweetkeys=0` to isolate drivers.

## 4. Boot and read logs

```sh
fastboot -S 512M flash userdata ios16-root.simg    # ~7 min, do not unplug
fastboot boot shim-boot-raphael.img                # nothing is flashed to boot
# after a test: Power+VolDown -> fastboot, then:
fastboot boot recovery/recovery.img                # OrangeFox
tools/sweet-log-pull.sh logs/raphael-1.txt         # 4 MiB persistent log ring
adb reboot bootloader
```

Two log channels are available on raphael:

- the persistent 4 MiB userdata log ring (always), and
- **live USB logs** (patch 0087, same as sweet): while the kernel is up, the
  phone enumerates as a CDC-ECM ethernet adapter (192.168.7.2/24, host .1) and
  streams kernel printf over UDP — run `tools/sweet-usbnet.sh` on the PC and
  `tools/sweet-log.py`. Requires the `sweetusb=2` boot-arg to start the
  device controller (default `sweetusb=1` only reports clock/GDSC state).
  `fastboot boot` hands over a running USB controller, so no PHY setup is
  needed.

First-boot expectations, in order (see NOTES-RAPHAEL.md for the hardware
evidence behind each): shim console on the 1080x2340 panel -> GIC probe ->
PSCI version -> XNU -> UFS probe (same host controller as sweet) -> HFS+
root -> launchd -> backboardd/SpringBoard (~4 min on the Apple logo).

## Known gaps / TODO

- **Touch second source**: raphael units carry a Goodix GT9889/GT9886 @0x5d
  (both the MIUI DTB and the mainline DTS agree) — that is the primary path.
  The kernel source also carries an ST FingerTipS driver (`fts_521`, I2C
  0x49); patch 0086 probes it and, if the Goodix is absent and the ST chip
  answers, polls its event FIFO read-only (sensing must be inherited from
  the previous OS — we never panel-init the IC). The first boot log prints
  both probes (`probe 0x5d ver-reg ...` / `probe ST FTS 0x49 id=..:..`).
- `fastboot boot` on raphael ABL with header v1 is the stock-supported
  path; if the ABL rejects our image, try `--header_version 2` (sweet
  style) as a fallback experiment.
- Wi-Fi/BT/audio/camera/SEP remain unsupported, as on sweet. Modem is not
  touched.

Closed by public resources (2026-10-19):

- **Volume-up = PM8150 GPIO6, active-low** — settled by the mainline
  `sm8150-xiaomi-raphael.dts` (`gpio-keys`: `gpios = <&pm8150_gpios 6
  GPIO_ACTIVE_LOW>`). Patch 0085 polls it through the same read-only SPMI
  observer channel as the other keys (PPID 0x0c5, RT_STS 0xc510) and also
  runs a one-shot census of every PMIC GPIO block so the first boot log
  confirms the mapping on real hardware.
- **USB (ue0, patches 0072-0077) ported in 0087.** The DWC3 (0xa600000),
  the wrapper qscratch (0xa6f8800), the QUSB2 HS PHY (0x88e2000) and the
  GDSC (0xf004) are all identical to sweet; only two GCC clock branches
  moved (cfg-noc 0xf078, aggre 0xf07c) and the phy ref is USB3_SEC_CLKREF
  (0x8c028) — see NOTES-RAPHAEL.md for the table.

## Resources worth knowing (K20 Pro has a big scene)

- Mainline DTS: `sm8150-xiaomi-raphael.dts` — [PATCH v2 0/3] Add Xiaomi
  Redmi K20 Pro (Raphael), patchew.org/linux/20251104221657.51580-1-pc1598@mainlining.org
- Mainline driver/fixed tree: github.com/howtocuddle/xiaomi_raphael
  (6.18-based, display ams639rq08 + touch + cameras working)
- postmarketOS: wiki postmarketos.org xiaomi-raphael, package
  `linux-xiaomi-raphael` (6.5 kernel fork)
- Stock kernel sources (touch/panel/keys ground truth):
  github.com/ZakoClubROM/android_kernel_xiaomi_raphael (branch lineage-19.0:
  `drivers/input/touchscreen/goodix_driver_gt9886`, `fts_521`; dtsi under
  `arch/arm64/boot/dts/qcom/raphael-*`)
- Device trees: LineageOS wiki/device tree for raphael; XDA raphael
  kernel/recovery threads (OrangeFox/TWRP are used for log pulls)

## Safety

Installing erases Android's userdata. Security (AMFI/sandbox) is permissive,
AppleKeyStore is a stub: do not put anything personal on it. Bootloaders,
recovery, modem and persist partitions are never touched, and nothing is
flashed to the boot partition — `fastboot boot` is temporary by design.
