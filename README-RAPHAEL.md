# iOS 16 on Redmi K20 Pro ("raphael", SM8150) — port guide

Same idea as the sweet port: Apple's open-source XNU kernel (xnu-8796) on
Qualcomm hardware, running the **unmodified iPhone X iOS 16.7.16 userland**.
Read the main README.md and NOTES.md first; this file only covers what
differs on raphael. Hardware facts and register-level evidence live in
NOTES-RAPHAEL.md.

Status: adaptation complete, not yet booted on hardware. Everything is
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

First-boot expectations, in order (see NOTES-RAPHAEL.md for the hardware
evidence behind each): shim console on the 1080x2340 panel -> GIC probe ->
PSCI version -> XNU -> UFS probe (same host controller as sweet) -> HFS+
root -> launchd -> backboardd/SpringBoard (~4 min on the Apple logo).

## Known gaps / TODO (see NOTES-RAPHAEL.md)

- **Volume-up source unknown** on raphael (no KEY_VOLUMEUP in any DTS);
  power + volume-down work via PON. Identify from a live DT before relying
  on it.
- **FocalTech fts_521 variant**: some K20 Pro units ship a FocalTech touch
  controller instead of the Goodix GT9889. v1 only supports Goodix; the
  probe log prints both attempts (`probe 0x5d ver-reg ...` /
  `probe 0x38 ... chip-id=..:..`).
- USB (ue0, patches 0072-0077) not yet ported: raphael DWC3 is at
  0xa600000 with a QUSB2/QMP PHY pair; the sweet constants need a per-SoC
  pass. Same for Wi-Fi/BT/audio/SEP — none are expected to work.
- `fastboot boot` on raphael ABL with header v1 is the stock-supported
  path; if the ABL rejects our image, try `--header_version 2` (sweet
  style) as a fallback experiment.

## Safety

Installing erases Android's userdata. Security (AMFI/sandbox) is permissive,
AppleKeyStore is a stub: do not put anything personal on it. Bootloaders,
recovery, modem and persist partitions are never touched, and nothing is
flashed to the boot partition — `fastboot boot` is temporary by design.
