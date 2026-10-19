#!/usr/bin/env python3
"""Extract the SoC DTBs from a raphael (K20 Pro) stock boot.img kernel blob.

The stock raphael boot image is header v1 with the DTBs appended to the
gzipped kernel (Image.gz-dtb style). The shim boot image needs one of these
appended to its own kernel so ABL has a device tree to patch and hand to the
shim (raphael_0 = SM8150 v2, the K20 Pro silicon).

  python3 tools/raphael-dtb-extract.py boot.img out_dir
"""
import os, struct, sys


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    boot, out = sys.argv[1], sys.argv[2]
    data = open(boot, 'rb').read()
    os.makedirs(out, exist_ok=True)
    magic, pos, n = b'\xd0\x0d\xfe\xed', 0, 0
    found = []
    while True:
        i = data.find(magic, pos)
        if i < 0:
            break
        ts = struct.unpack('>I', data[i + 4:i + 8])[0]
        if 0x1000 < ts < 0x400000 and i + ts <= len(data):
            found.append((i, ts))
        pos = i + 4
    for n, (off, ts) in enumerate(found):
        blob = data[off:off + ts]
        open(os.path.join(out, f'raphael_{n}.dtb'), 'wb').write(blob)
        try:
            import fdt
            d = fdt.parse_dtb(blob)
            model = d.get_property('model', '/')
            model = model.value if model else '?'
        except Exception:
            model = '?'
        print(f'raphael_{n}.dtb  offset={off:#x} size={ts}  {model}')
    if not found:
        raise SystemExit('no DTB found — is this a raphael boot.img?')
    print(f'\n{len(found)} DTBs written to {out}; use raphael_0.dtb (SM8150 v2) for the shim: DTB_IN=<dir>/raphael_0.dtb')


if __name__ == '__main__':
    main()
