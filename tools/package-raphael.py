#!/usr/bin/env python3
"""Package the final raphael shim boot image — python only, no cross toolchain.

Inputs (download from the fork's Actions artifacts):
  raphael-shim/Image          shim kernel blob (CI-built with RAPHAEL=1)
  payload-raphael.bin         xnu payload from tools/mkpayload.py
  your stock raphael boot.img (only its embedded SoC DTB is used; it is
                              never uploaded anywhere)

  pip3 install mkbootimg
  python3 tools/package-raphael.py SHIM_DIR PAYLOAD STOCK_BOOT.img OUT.img
"""
import os, struct, subprocess, sys, tempfile

MKBOOTIMG_ARGS = dict(base=0, kernel_offset=0x8000, ramdisk_offset=0x1000000,
                      tags_offset=0x100, pagesize=4096,
                      os_version="11.0.0", os_patch_level="2021-10",
                      cmdline="console=null")


def find_dtbs(data):
    magic, pos, found = b"\xd0\x0d\xfe\xed", 0, []
    while True:
        i = data.find(magic, pos)
        if i < 0:
            break
        ts = struct.unpack(">I", data[i + 4:i + 8])[0]
        if 0x1000 < ts < 0x400000 and i + ts <= len(data):
            found.append((i, ts))
        pos = i + 4
    return found


def main():
    if len(sys.argv) != 5:
        raise SystemExit(__doc__)
    shim_dir, payload, stock_boot, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    boot = open(stock_boot, "rb").read()
    dtbs = find_dtbs(boot)
    if not dtbs:
        raise SystemExit("no DTB found in the stock boot.img")
    off, ts = dtbs[0]  # raphael_0 = SM8150 v2, first in stock Image.gz-dtb order
    print(f"SoC DTB: offset={off:#x} size={ts}")
    kernel = open(os.path.join(shim_dir, "Image"), "rb").read() + boot[off:off + ts]
    with tempfile.NamedTemporaryFile(suffix=".Image.dtb", delete=False) as f:
        f.write(kernel)
        kpath = f.name
    argv = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "mkbootimg.py"), "--header_version", "1", "--kernel", kpath,
            "--ramdisk", payload, *sum(([k, str(v)] for k, v in MKBOOTIMG_ARGS.items()), []),
            "-o", out]
    subprocess.run(argv, check=True)
    os.unlink(kpath)
    print(f"wrote {out} ({os.path.getsize(out)} bytes)")
    print("next: fastboot boot " + out)


if __name__ == "__main__":
    main()
