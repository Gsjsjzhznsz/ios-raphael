#!/bin/bash
# Build the shim and wrap it in a boot.img v2 that mirrors the stock PixelOS header.
set -euo pipefail
cd "$(dirname "$0")"
CC=aarch64-linux-gnu-gcc
OBJCOPY=aarch64-linux-gnu-objcopy
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
# RAPHAEL=1 ./build.sh: build for the Redmi K20 Pro (SM8150) console geometry
# (same FB base, 1080x2340 panel) and imem restart-reason address.
if [ "${RAPHAEL:-0}" = 1 ]; then CFLAGS="$CFLAGS -DRAPHAEL"; fi
mkdir -p out
for f in start.S shim.c console.c mmu.c fdt.c loader.c ufs.c; do
        $CC $CFLAGS -c $f -o out/${f%.*}.o
done
# The image runs wherever ABL puts it with no relocation pass: only the
# header's image_size (start.o, linked at 0) may be an absolute address.
abs=$(aarch64-linux-gnu-readelf -r out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }
$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
        out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o -o out/shim.elf
$OBJCOPY -O binary out/shim.elf out/Image
# ABL copies the file; pad to image_size so .bss/stacks exist as zeroed bytes.
size=$(aarch64-linux-gnu-nm out/shim.elf | awk '$3=="_end"{print strtonum("0x"$1)}')
truncate -s "$size" out/Image
# Ramdisk: an xnu payload (tools/mkpayload.py) if given as $1, else an empty
# newc cpio (ABL dislikes a zero-size ramdisk on some builds) -> diagnostics.
if [ -n "${1:-}" ]; then
        cp "$1" out/ramdisk.bin
else
        (cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
fi
if [ "${RAPHAEL:-0}" = 1 ]; then
        # Redmi K20 Pro stock flow: boot header v1, DTB appended to the kernel
        # blob (Image.gz-dtb style). Extract a SoC DTB from the stock boot.img
        # (tools/raphael-dtb-extract.py) and point DTB_IN at it. Without a DTB
        # (CI shim-only builds) only out/Image is produced; package it with
        # tools/package-raphael.py.
        DTB_IN=${DTB_IN:-../dtb/boot_unpacked/raphael_0.dtb}
        if [ ! -f "$DTB_IN" ]; then
                echo "shim: no DTB_IN ($DTB_IN); built out/Image only (package with tools/package-raphael.py)"
                ls -l out/Image out/shim.elf
                exit 0
        fi
        cat out/Image "$DTB_IN" > out/Image.dtb
        python3 ../tools/mkbootimg.py --header_version 1 --kernel out/Image.dtb --ramdisk out/ramdisk.bin \
                --base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 \
                --tags_offset 0x100 --pagesize 4096 \
                --os_version 11.0.0 --os_patch_level 2021-10 \
                --cmdline "console=null" -o out/shim-boot.img
else
        python3 ../tools/mkbootimg.py --header_version 2 --kernel out/Image --ramdisk out/ramdisk.bin \
                --dtb ../dtb/boot_unpacked/dtb --base 0 --kernel_offset 0x8000 --ramdisk_offset 0x1000000 \
                --tags_offset 0x100 --dtb_offset 0x1f00000 --pagesize 4096 \
                --os_version 17.0.0 --os_patch_level 2035-06 \
                --cmdline "console=null" -o out/shim-boot.img
fi
# Host render of the console layout.
gcc -O1 -Wall -o out/host_test console.c host_test.c && ./out/host_test
ls -l out/Image out/shim-boot.img
