#!/usr/bin/env python3
"""repack-boot-v2.py — raphael shim boot image (Android boot header v2) patcher.

Recovers the lost "v2 repack" step of the raphael pipeline: takes a shim boot
image (header v2 + shim as kernel + SWEETXNU payload as ramdisk + raphael DTB)
and rewrites the payload boot-args in place, keeping every other byte identical.

Usage:
  repack-boot-v2.py SRC.img DST.img [--cmdline "STRING"] [--check]

  --cmdline   Replace the SWEETXNU payload boot-args (max 607 bytes).
              Without it, DST must come out byte-identical to SRC (sanity mode).
  --check     Re-parse DST and verify header fields + section hashes vs SRC.

Payload layout (tools/mkpayload.py, little endian):
  0x000  magic[8] = "SWEETXNU"
  0x008  u32 version, u32 nsegs
  0x010  u64 virt_base, entry_va
  0x020  u64 adt_off, adt_size
  0x030  u64 kernel_end_va
  0x038  u64 phys_base
  0x040  u64 mem_size
  0x048  char cmdline[608]          <- BOOT_LINE_LENGTH
  0x2a8  seg[nsegs] { u64 vmaddr, vmsize, file_off, file_size }

Boot header tail (after the 1632-byte v0 struct, all little endian), as written
by the raphael repack script (empirically reverse-engineered from diag5):
  1632 u32 recovery_dtbo_size = 0
  1636 u64 recovery_dtbo_offset = 0
  1644 u32 header_size = 1660          (custom bookkeeping field)
  1648 u32 dtb_size = 0                (DTB bytes are still appended after the
                                        ramdisk page; ABL hands its own runtime
                                        FDT to the shim, so 0 is harmless)
  1652 u64 dtb_addr = 0x1f00000        (--dtb_offset)
The header_version honored by the raphael ABL is the v0 dt_size slot @0x28.
"""
import argparse, hashlib, struct, sys

BOOT_MAGIC = b'ANDROID!'
SWEET_MAGIC = b'SWEETXNU'
BOOT_LINE_LENGTH = 608
CMDLINE_OFF = 0x48


def align(x, page):
    return (x + page - 1) // page * page


def parse(img):
    """Parse a shim boot image v2 and return a dict of everything that matters."""
    d = open(img, 'rb').read()
    assert d[:8] == BOOT_MAGIC, 'not an Android boot image'
    (kernel_size, kernel_addr, rd_size, rd_addr, second_size, _second_addr,
     tags_addr, page, header_version, os_version) = struct.unpack_from('<10I', d, 8)
    header_size, = struct.unpack_from('<I', d, 1644)
    dtb_size_field, = struct.unpack_from('<I', d, 1648)
    dtb_addr, = struct.unpack_from('<Q', d, 1652)
    assert header_version == 2, f'header_version@0x28={header_version}, want 2'
    assert second_size == 0, 'unexpected second stage'

    kernel_off = page
    rd_off = kernel_off + align(kernel_size, page)
    dtb_off = rd_off + align(rd_size, page)
    # DTB blob is self-describing: big-endian FDT totalsize right after the magic
    assert d[dtb_off:dtb_off + 4] == b'\xd0\x0d\xfe\xed', 'no FDT magic after ramdisk page'
    dtb_size, = struct.unpack_from('>I', d, dtb_off + 4)

    assert d[rd_off:rd_off + 8] == SWEET_MAGIC, 'ramdisk section is not a SWEETXNU payload'
    version, nsegs = struct.unpack_from('<II', d, rd_off + 8)
    virt_base, entry_va, adt_off, adt_size, kernel_end_va, phys_base, mem_size = \
        struct.unpack_from('<7Q', d, rd_off + 0x10)
    cmdline_start = rd_off + CMDLINE_OFF
    cmdline_raw = d[cmdline_start:cmdline_start + BOOT_LINE_LENGTH]
    cmdline = cmdline_raw.split(b'\x00')[0].decode(errors='replace')

    dtb = d[dtb_off:dtb_off + dtb_size]
    assert dtb[:4] == b'\xd0\x0d\xfe\xed', 'dtb section lacks FDT magic'

    return dict(data=d, page=page, kernel_off=kernel_off, kernel_size=kernel_size,
                kernel_addr=kernel_addr, rd_off=rd_off, rd_size=rd_size,
                rd_addr=rd_addr, tags_addr=tags_addr, dtb_off=dtb_off,
                dtb_size=dtb_size, dtb_size_field=dtb_size_field,
                header_size=header_size, dtb_addr=dtb_addr, os_version=os_version,
                payload_version=version, nsegs=nsegs, virt_base=virt_base,
                entry_va=entry_va, adt_off=adt_off, adt_size=adt_size,
                kernel_end_va=kernel_end_va, phys_base=phys_base,
                mem_size=mem_size, cmdline=cmdline,
                cmdline_start=cmdline_start)


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--cmdline', help='replacement payload boot-args (max 607 bytes)')
    ap.add_argument('--check', action='store_true', help='verify DST against SRC after write')
    args = ap.parse_args()

    s = parse(args.src)
    print(f'[src] {args.src} ({len(s["data"])} bytes)')
    print(f'  kernel  @{s["kernel_off"]:#x} size {s["kernel_size"]}  addr {s["kernel_addr"]:#x}')
    print(f'  payload @{s["rd_off"]:#x} size {s["rd_size"]}  addr {s["rd_addr"]:#x}'
          f'  (SWEETXNU v{s["payload_version"]}, {s["nsegs"]} segs)')
    print(f'  adt     @{s["rd_off"] + s["adt_off"]:#x} size {s["adt_size"]}')
    print(f'  dtb     @{s["dtb_off"]:#x} size {s["dtb_size"]}  (header field: {s["dtb_size_field"]})  addr {s["dtb_addr"]:#x}')
    print(f'  phys_base {s["phys_base"]:#x}  mem_size {s["mem_size"]:#x}  entry_va {s["entry_va"]:#x}')
    print(f'  cmdline({len(s["cmdline"])}): {s["cmdline"]}')

    out = bytearray(s['data'])
    if args.cmdline is not None:
        new = args.cmdline.encode()
        assert len(new) < BOOT_LINE_LENGTH, f'cmdline {len(new)}B >= {BOOT_LINE_LENGTH}B buffer'
        out[s['cmdline_start']:s['cmdline_start'] + BOOT_LINE_LENGTH] = \
            new + b'\x00' * (BOOT_LINE_LENGTH - len(new))
        print(f'\n[patch] cmdline ({len(s["cmdline"])} -> {len(new)} bytes):')
        print(f'  old: {s["cmdline"]}')
        print(f'  new: {args.cmdline}')
    else:
        print('\n[patch] none — sanity mode, output must be byte-identical')

    open(args.dst, 'wb').write(out)
    print(f'[dst] {args.dst} ({len(out)} bytes)')

    if args.cmdline is None and bytes(out) != s['data']:
        sys.exit('FATAL: sanity mode produced a diff — repacker is not faithful')

    if args.check:
        t = parse(args.dst)
        changed = []
        for k in ('kernel_size', 'rd_size', 'dtb_size', 'dtb_addr', 'nsegs',
                  'entry_va', 'phys_base', 'mem_size', 'header_size',
                  'dtb_size_field', 'os_version'):
            if t[k] != s[k]:
                changed.append(k)
        same_kernel = sha256(s['data'][s['kernel_off']:s['kernel_off'] + s['kernel_size']]) == \
            sha256(t['data'][t['kernel_off']:t['kernel_off'] + t['kernel_size']])
        same_adt = sha256(s['data'][s['rd_off'] + s['adt_off']:
                                    s['rd_off'] + s['adt_off'] + s['adt_size']]) == \
            sha256(t['data'][t['rd_off'] + t['adt_off']:
                             t['rd_off'] + t['adt_off'] + t['adt_size']])
        same_dtb = sha256(s['data'][s['dtb_off']:s['dtb_off'] + s['dtb_size']]) == \
            sha256(t['data'][t['dtb_off']:t['dtb_off'] + t['dtb_size']])
        n_diff = sum(a != b for a, b in zip(s['data'], t['data']))
        print(f'\n[check] kernel/ADT/DTB sha256 identical: {same_kernel}/{same_adt}/{same_dtb}')
        print(f'[check] byte-diffs vs src: {n_diff} (expect {abs(len(t["cmdline"]) - len(s["cmdline"]))} when patching)'
              if args.cmdline else f'[check] byte-diffs vs src: {n_diff} (expect 0)')
        if changed:
            sys.exit(f'FATAL: unexpected field changes: {changed}')
        print('[check] OK')


if __name__ == '__main__':
    main()
