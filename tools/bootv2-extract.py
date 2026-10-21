#!/usr/bin/env python3
"""Extract boot-v2 image components (shim / payload / DTB / cmdline) for t8 repack.

Reuses the layout parser from tools/repack-boot-v2.py so the offsets are
guaranteed identical to the ones used to assemble the t-series images.
"""
import struct, sys

sys.path.insert(0, '/home/z/my-project/work/t8fix/tools')
import importlib.util

spec = importlib.util.spec_from_file_location(
    'repack', '/home/z/my-project/work/t8fix/tools/repack-boot-v2.py')
repack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repack)


def main(src, outdir):
    try:
        img = repack.parse(src)
        print('parsed with tools/repack-boot-v2.py')
    except Exception as e:
        raise SystemExit(f'repack parser failed: {e}; falling back')

    d = img['data']
    page = img['page']
    kernel_off = img['kernel_off']
    kernel_size = img['kernel_size']
    rd_off = img['rd_off']
    rd_size = img['rd_size']
    dtb_off = img['dtb_off']
    dtb_size = img['dtb_size']

    shim = d[kernel_off:kernel_off + kernel_size]
    payload = d[rd_off:rd_off + rd_size]
    dtb = d[dtb_off:dtb_off + dtb_size]

    # payload header: magic(8) ver+segs(8) virt_base(8) entry(8) adt_off+size(16)
    #                 kernel_end(8) phys_base(8) mem_size(8) cmdline[608]
    magic = payload[0:8]
    assert magic == b'SWEETXNU', f'bad payload magic {magic!r}'
    version, nsegs = struct.unpack_from('<II', payload, 8)
    adt_off, adt_size = struct.unpack_from('<QQ', payload, 0x20)
    cmdline = payload[0x48:0x48 + 608].split(b'\0')[0].decode()

    adt = payload[adt_off:adt_off + adt_size]

    import os
    os.makedirs(outdir, exist_ok=True)
    open(f'{outdir}/shim.bin', 'wb').write(shim)
    open(f'{outdir}/adt.bin', 'wb').write(adt)
    open(f'{outdir}/raphael.dtb', 'wb').write(dtb)
    open(f'{outdir}/payload_t7.bin', 'wb').write(payload)
    open(f'{outdir}/cmdline.txt', 'w').write(cmdline)

    print(f'payload version={version} nsegs={nsegs}')
    print(f'shim   : {kernel_off:#x} +{kernel_size} ({len(shim)} bytes)')
    print(f'payload: {rd_off:#x} +{rd_size} ({len(payload)} bytes)')
    print(f'dtb    : {dtb_off:#x} +{dtb_size} ({len(dtb)} bytes)')
    print(f'adt    : payload+{adt_off:#x} +{adt_size} ({adt_size} bytes)')
    print(f'cmdline({len(cmdline)}): {cmdline}')


def parse_image(src):
    """Parse header-v2 boot image exactly like repack-boot-v2.py does."""
    with open(src, 'rb') as f:
        d = f.read()
    assert d[:8] == b'ANDROID!', 'not a boot image'
    header_version = struct.unpack_from('<I', d, 0x28)[0]
    page = struct.unpack_from('<I', d, 0x24)[0]
    kernel_size = struct.unpack_from('<I', d, 8)[0]
    rd_size = struct.unpack_from('<I', d, 0x10)[0]
    kernel_addr = struct.unpack_from('<I', d, 0xc)[0]
    rd_addr = struct.unpack_from('<I', d, 0x14)[0]
    dtb_size_field = struct.unpack_from('<I', d, 0x28 - 0x28)[0]  # placeholder
    # v2 layout: 0x28 = header_version when read via mkbootimg; per R7 notes the
    # fork sets dtb_size at 1648 and header_version is read from v0 dt_size slot.
    kernel_off = page
    rd_off = kernel_off + (kernel_size + page - 1) // page * page
    second_size = struct.unpack_from('<I', d, 0x18)[0]
    after_rd = rd_off + (rd_size + page - 1) // page * page
    dtb_off = after_rd
    assert d[rd_off:rd_off + 8] == b'SWEETXNU', 'ramdisk is not SWEETXNU payload'
    # dtb: scan forward for FDT magic (R7: header dtb_size slot may be 0)
    dtb_size = struct.unpack_from('<I', d, 1648)[0]
    if dtb_size == 0:
        assert d[dtb_off:dtb_off + 4] == b'\xd0\x0d\xfe\xed', 'no FDT magic after ramdisk'
        totalsize = struct.unpack_from('>I', d, dtb_off + 4)[0]
        dtb_size = totalsize
    return dict(data=d, page=page, kernel_off=kernel_off, kernel_size=kernel_size,
                rd_off=rd_off, rd_size=rd_size, dtb_off=dtb_off, dtb_size=dtb_size,
                kernel_addr=kernel_addr, rd_addr=rd_addr)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
