#!/bin/bash
# One-shot raphael (Redmi K20 Pro) payload + boot image build.
# Prereqs: aarch64-linux-gnu-gcc, mkbootimg, python3, and a raphael boot.img
# for DTB extraction.
#   tools/build-raphael.sh KERNEL_DIRECTORY BOOT_IMG [OUT_PREFIX]
# KERNEL_DIRECTORY is the CI artifact (xnu-kernel) containing
# kernel.development.raphael; BOOT_IMG is the stock raphael boot.img (for the
# SoC DTB); OUT_PREFIX defaults to shim/out/shim-boot-raphael.
set -euo pipefail
cd "$(dirname "$0")/.."

KERNEL_DIR=${1:?usage: build-raphael.sh KERNEL_DIR BOOT_IMG [OUT_PREFIX]}
BOOT_IMG=${2:?usage: build-raphael.sh KERNEL_DIR BOOT_IMG [OUT_PREFIX]}
PREFIX=${3:-shim/out/shim-boot-raphael}
KERN=$(ls "$KERNEL_DIR"/kernel.development.raphael "$KERNEL_DIR"/*.development.raphael 2>/dev/null | head -1)
[ -n "$KERN" ] || { echo "no kernel.development.raphael in $KERNEL_DIR" >&2; exit 1; }

# 1. SoC DTB from the stock boot image (header v1: DTB inside the kernel blob)
python3 tools/raphael-dtb-extract.py "$BOOT_IMG" dtb/boot_unpacked

# 2. Apple Device Tree (raphael panel geometry + Kryo 485 clocks)
python3 tools/mkadt.py shim/out/sweet-raphael.adt --raphael --highmem

# 3. Payload: kernel + ADT + boot-args
python3 tools/mkpayload.py "$KERN" shim/out/sweet-raphael.adt shim/out/payload-raphael.bin \
    --cmdline 'debug=0xc serial=3 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30'

# 4. Shim (RAPHAEL=1: 1080x2340 console, imem restart reason, header v1)
(cd shim && RAPHAEL=1 DTB_IN=../dtb/boot_unpacked/raphael_0.dtb ./build.sh ../shim/out/payload-raphael.bin)
cp shim/out/shim-boot.img "$PREFIX.img"
ls -l "$PREFIX.img"
echo 'ready: fastboot boot '"$PREFIX.img"
