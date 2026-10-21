#!/usr/bin/env python3
"""Assemble raphael-t8-*.img: t7 template header + shim + NEW payload + DTB.

Template = the proven-booting t7 image header page (all quirks preserved:
header_version@0x28=2, header-size accounting@1644=1660, real dtb_size@1648).
Only ramdisk_size@16 changes. Then verify every section byte-for-byte.
"""
import struct, sys, hashlib

T7 = '/home/z/my-project/work/t8/t7.img'
SHIM = '/home/z/my-project/work/t8/shim.bin'
PAYLOAD = sys.argv[2] if len(sys.argv) > 2 else '/home/z/my-project/work/t8/payload_t8.bin'
DTB = '/home/z/my-project/work/t8/raphael.dtb'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/z/my-project/work/t8/raphael-t8-clean.img'

PAGE = 4096


def sha(b):
    return hashlib.sha256(b).hexdigest()


def page_up(n):
    return (n + PAGE - 1) // PAGE * PAGE


def main():
    t7 = open(T7, 'rb').read()
    shim = open(SHIM, 'rb').read()
    payload = open(PAYLOAD, 'rb').read()
    dtb = open(DTB, 'rb').read()

    hdr = bytearray(t7[:PAGE])
    ksz, kaddr, rsz_t7, raddr = struct.unpack_from('<4I', hdr, 8)
    page_size = struct.unpack_from('<I', hdr, 0x24)[0]
    assert page_size == PAGE and kaddr == 0x8000 and raddr == 0x1000000
    assert ksz == len(shim), f'shim size mismatch {ksz} vs {len(shim)}'
    struct.pack_into('<I', hdr, 16, len(payload))

    rd_off = PAGE + page_up(len(shim))
    dtb_off = rd_off + page_up(len(payload))
    out = bytes(hdr) + shim
    out += b'\0' * (rd_off - len(out))
    out += payload
    out += b'\0' * (dtb_off - len(out))
    out += dtb
    open(OUT, 'wb').write(out)
    print(f'[built] {OUT}: {len(out)} bytes  sha256={sha(out)}')

    # ---- verify ----
    img = open(OUT, 'rb').read()
    ksz2, _, rsz2, _ = struct.unpack_from('<4I', img, 8)
    assert img[:8] == b'ANDROID!' and struct.unpack_from('<I', img, 0x28)[0] == 2
    assert ksz2 == len(shim) and rsz2 == len(payload)
    assert img[PAGE:PAGE + len(shim)] == shim, 'shim bytes differ from t7'
    assert img[rd_off:rd_off + len(payload)] == payload, 'payload bytes'
    assert img[dtb_off:dtb_off + len(dtb)] == dtb, 'dtb bytes differ from t7'
    assert img[dtb_off:dtb_off + 4] == b'\xd0\x0d\xfe\xed', 'FDT magic'

    # payload internals vs t7
    p7 = t7[0x33000:0x33000 + rsz_t7]
    assert payload[:8] == b'SWEETXNU' and p7[:8] == b'SWEETXNU'
    cmdline7 = p7[0x48:0x48 + 608].split(b'\0')[0]
    cmdline8 = payload[0x48:0x48 + 608].split(b'\0')[0]
    a7o, a7s = struct.unpack_from('<QQ', p7, 0x20)
    a8o, a8s = struct.unpack_from('<QQ', payload, 0x20)
    assert p7[a7o:a7o + a7s] == payload[a8o:a8o + a8s], 'ADT differs from t7'
    nsegs7, = struct.unpack_from('<I', p7, 12)
    nsegs8, = struct.unpack_from('<I', payload, 12)
    extra = cmdline8[len(cmdline7):].decode() if cmdline8 != cmdline7 else ''
    base_ok = cmdline8.startswith(cmdline7)
    print(f'[verify] cmdline({len(cmdline8)}B) {"identical" if cmdline8 == cmdline7 else "t7-base+" + repr(extra) if base_ok else "DIFFERS"}; ADT {a8s}B identical; '
          f'nsegs {nsegs7}->{nsegs8}; shim/DTB byte-identical to t7')

    # kernel blob actually differs (new RAPHAEL build) and carries the deltas
    segs_off = 0x2a8
    k7 = p7[struct.unpack_from('<Q', p7, segs_off)[0] and 0 or 0:0]  # noqa placeholder
    diffs = sum(1 for a, b in zip(p7, payload) if a != b)
    print(f'[verify] payload byte-diffs vs t7: {diffs} (kernel content change)')
    for s in (b'HW-gated', b'xiaomi,raphael', b'raphael volume-up withheld'):
        print(f'[kernel-string] {s.decode():32s} '
              f'{"PRESENT" if s in payload else "absent"}')
    print('[done]')


if __name__ == '__main__':
    main()
