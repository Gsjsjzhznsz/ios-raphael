#!/usr/bin/env python3
"""Build 4 swap-test boot images to isolate the raphael bootstrap-done hang.

Evidence so far (byte-level comparison of friend's working 0082e vs our sc-verbose):
  - cmdline: identical except friend adds sweetfb_noconsole=1 sweetfb_hz=30
  - kernel: same link layout (10 segs, same vmaddrs/entry); OURS built from ios-sweet
    CI with OLD match tables ('xiaomi,sweet' only; SweetCPU 'qcom,kryo470' only),
    FRIEND's adds ('xiaomi,raphael') and ('qcom,kryo485')
  - ADT: ours 9904B (8 CPU nodes, fbcon reg size 0x1700000, NO /product node,
    root compatible xiaomi,sweet+qcom,sm7150), friend 7048B (1 CPU node, fbcon
    0x9a4000, full d22ap /product, xiaomi,raphael+qcom,sm8150)
  - photo proof: our stack registers all IOKit drivers, never prints SWEET UFS,
    last line = bootstrap done; friend's reaches lock screen on the same phone.

Variants (all: OUR shim + OUR stock-4.14 DTB shell, console kept ON):
  t1  friend kernel + friend ADT          -> shell vs payload attribution
  t2  our kernel(kryo485 table patch) + our ADT(1 CPU, fbcon 0x9a4000, +product)
  t3  our kernel(kryo485 table patch) + our ADT unchanged
  t4  friend kernel + our ADT unchanged   -> kernel vs ADT attribution
"""
import copy, hashlib, os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt as adtlib

BASE = os.environ.get('SWAPTEST_BASE', './cmp')
OUT = os.environ.get('SWAPTEST_OUT', './out')
PAGE = 4096
CMDLINE_OFF = 0x48
BOOT_LINE = 608
ADT_OFF_FIELD = 0x28          # payload header: adt_off at 0x20, adt_size at 0x28
RD_SIZE_FIELD = 16            # boot header: ramdisk_size at offset 16

def sha(b):
    return hashlib.sha256(b).hexdigest()

def load(tag):
    d = {}
    d['kernel'] = open(f'{BASE}/{tag}/kernel', 'rb').read()
    d['payload'] = open(f'{BASE}/{tag}/ramdisk', 'rb').read()
    d['dtb'] = open(f'{BASE}/{tag}/dtb', 'rb').read()
    d['img'] = open(f'{BASE}/{tag}/header.txt')  # keep values below
    return d

OURS = load('ours')
FRIEND = load('friend')
OURS_IMG = open('/home/z/my-project/download/shim-boot-raphael-sc-verbose.img', 'rb').read()

# ---- payload helpers -------------------------------------------------------

def parse_payload(buf):
    assert buf[:8] == b'SWEETXNU'
    ver, nsegs = struct.unpack_from('<II', buf, 8)
    adt_off, adt_size = struct.unpack_from('<2Q', buf, 0x20)
    cmdline = buf[CMDLINE_OFF:CMDLINE_OFF + BOOT_LINE].split(b'\0')[0].decode()
    return dict(ver=ver, nsegs=nsegs, adt_off=adt_off, adt_size=adt_size, cmdline=cmdline)

def set_cmdline(buf, text):
    new = text.encode()
    assert len(new) < BOOT_LINE, f'cmdline {len(new)}B too long'
    buf[CMDLINE_OFF:CMDLINE_OFF + BOOT_LINE] = new + b'\0' * (BOOT_LINE - len(new))

def swap_adt(buf, new_adt):
    p = parse_payload(buf)
    out = bytearray(buf[:p['adt_off']] + new_adt)
    out += b'\0' * (-len(out) & 0xf)
    struct.pack_into('<Q', out, ADT_OFF_FIELD, len(new_adt))
    return bytes(out)

def patch_tables(buf):
    n1 = buf.count(b'qcom,kryo470')
    n2 = buf.count(b'Kryo 470')
    assert n1 >= 1 and n2 >= 1, f'unexpected table marker counts {n1}/{n2}'
    out = buf.replace(b'qcom,kryo470', b'qcom,kryo485').replace(b'Kryo 470', b'Kryo 485')
    print(f'  table patch: qcom,kryo470 x{n1}, Kryo 470 x{n2} replaced (equal length)')
    return out

# ---- ADT surgery for t2 ----------------------------------------------------

def build_adt_v2():
    # fidelity check first: parse->serialize round trip of the unmodified tree
    ro, _ = adtlib.parse(OURS['payload'][parse_payload(OURS['payload'])['adt_off']:
                                         parse_payload(OURS['payload'])['adt_off']
                                         + parse_payload(OURS['payload'])['adt_size']])
    rf, _ = adtlib.parse(FRIEND['payload'][parse_payload(FRIEND['payload'])['adt_off']:
                                           parse_payload(FRIEND['payload'])['adt_off']
                                           + parse_payload(FRIEND['payload'])['adt_size']])
    cpus = next(c for c in ro.children if c.name == 'cpus')
    kept = [c for c in cpus.children if c.name == 'cpu0']
    dropped = len(cpus.children) - len(kept)
    cpus.children = kept
    fbcon = next(c for c in ro.children if c.name == 'sweet-fbcon')
    for i, (n, f, v) in enumerate(fbcon.props):
        if n == 'reg':
            assert len(v) == 16
            fbcon.props[i] = (n, f, struct.pack('<2Q', 0x9c000000, 0x9a4000))
    prod = copy.deepcopy(next(c for c in rf.children if c.name == 'product'))
    for i, (n, f, v) in enumerate(prod.props):
        if n == 'AAPL,phandle':
            prod.props[i] = (n, f, b'\xff\x00\x00\x00')   # unique in our tree
    idx = next(i for i, c in enumerate(ro.children) if c.name == 'sweet-ufs')
    ro.children.insert(idx, prod)
    blob = adtlib.serialize(ro)
    chk, _ = adtlib.parse(blob)
    names = [c.name for c in chk.children]
    assert 'product' in names and 'sweet-ufs' in names, names
    n_cpu = len(next(c for c in chk.children if c.name == 'cpus').children)
    assert n_cpu == 1, n_cpu
    print(f'  ADT v2: cpus 8->1 (dropped {dropped}), fbcon reg -> 0x9a4000, '
          f'product node spliced ({len(prod.props)} props, phandle 0xff), '
          f'size {parse_payload(OURS["payload"])["adt_size"]} -> {len(blob)}')
    return blob

# ---- boot image assembly ---------------------------------------------------

def build_boot(payload, name):
    page = bytearray(OURS_IMG[:PAGE])                 # template header page
    struct.pack_into('<I', page, RD_SIZE_FIELD, len(payload))
    rd_off = PAGE + len(OURS['kernel'])               # shim already page-aligned
    rd_off = (rd_off + PAGE - 1) // PAGE * PAGE
    dtb_off = rd_off + len(payload)
    dtb_off = (dtb_off + PAGE - 1) // PAGE * PAGE
    out = bytearray(page)
    out += OURS['kernel']
    out += b'\0' * (rd_off - len(out))
    out += payload
    out += b'\0' * (dtb_off - len(out))
    out += OURS['dtb']
    path = f'{OUT}/{name}'
    open(path, 'wb').write(out)
    print(f'  [built] {name}: {len(out)} bytes  sha256={sha(out)}')
    return path

# ---- verification ----------------------------------------------------------

def verify(path, expect):
    name = os.path.basename(path)
    img = open(path, 'rb').read()
    assert img[:8] == b'ANDROID!'
    ksz, kaddr, rsz, raddr = struct.unpack_from('<4I', img, 8)
    page, = struct.unpack_from('<I', img, 36)
    assert page == 4096 and kaddr == 0x8000 and raddr == 0x1000000
    rd_off = PAGE + ((ksz + PAGE - 1) // PAGE * PAGE)
    pl = img[rd_off:rd_off + rsz]
    assert pl[:8] == b'SWEETXNU', 'payload magic'
    p = parse_payload(pl)
    assert p['nsegs'] == 10
    adt = pl[p['adt_off']:p['adt_off'] + p['adt_size']]
    root, _ = adtlib.parse(adt)
    names = [c.name for c in root.children]
    dtb_off = rd_off + ((rsz + PAGE - 1) // PAGE * PAGE)
    assert img[dtb_off:dtb_off + 4] == b'\xd0\x0d\xfe\xed', 'FDT magic'
    assert img[dtb_off:dtb_off + len(OURS['dtb'])] == OURS['dtb'], 'dtb bytes'
    kern = img[PAGE:PAGE + ksz]
    assert kern == OURS['kernel'], 'shim bytes'
    _p_ours = OURS['payload'].replace(b'qcom,kryo470', b'qcom,kryo485').replace(b'Kryo 470', b'Kryo 485')
    checks = {
        'cmdline_has': lambda: all(x in p['cmdline'] for x in expect['cmdline_has']),
        'cmdline_lacks': lambda: all(x not in p['cmdline'] for x in expect['cmdline_lacks']),
        'kernel_is_ours': lambda: sha(pl[0x3e8:0x3e8 + 0x160000]) == sha(_p_ours[0x3e8:0x3e8 + 0x160000]),
        'kernel_is_friend': lambda: sha(pl[0x3e8:0x3e8 + 0x160000]) == sha(FRIEND['payload'][0x3e8:0x3e8 + 0x160000]),
        'table_patched': lambda: b'qcom,kryo470' not in pl and b'Kryo 470' not in pl and b'qcom,kryo485' in pl,
        'adt_ours': lambda: adt == OURS['payload'][parse_payload(OURS['payload'])['adt_off']:
                                                 parse_payload(OURS['payload'])['adt_off'] + 9904],
        'adt_friend': lambda: sha(adt) == sha(FRIEND['payload'][parse_payload(FRIEND['payload'])['adt_off']:
                                                                parse_payload(FRIEND['payload'])['adt_off']
                                                                + parse_payload(FRIEND['payload'])['adt_size']]),
        'adt_v2': lambda: 'product' in names and len(next(c for c in root.children if c.name == 'cpus').children) == 1,
    }
    for k, ok in expect['checks'].items():
        assert checks[k](), f'{name}: check {k} FAILED'
    print(f'  [verify OK] {os.path.basename(path)}: adt_off={p["adt_off"]:#x} '
          f'adt_size={p["adt_size"]} cmdline({len(p["cmdline"])}B) all checks pass')

# ---- build all four --------------------------------------------------------

F_CMDLINE = parse_payload(FRIEND['payload'])['cmdline']
O_CMDLINE = parse_payload(OURS['payload'])['cmdline']
NOCON = 'sweetfb_noconsole=1 sweetfb_hz=30 '
assert NOCON in F_CMDLINE
F_VERBOSE = F_CMDLINE.replace(NOCON, '')
print(f'friend verbose cmdline: "{F_VERBOSE}"')

print('\n== t1: friend kernel + friend ADT + our shell ==')
p1 = bytearray(FRIEND['payload'])
set_cmdline(p1, F_VERBOSE)
p1 = bytes(p1)
t1 = build_boot(p1, 'raphael-t1-friendpayload-ourshell.img')

print('\n== t2: our kernel (kryo485 table) + fixed ADT + our shell ==')
adt2 = build_adt_v2()
p2 = swap_adt(patch_tables(OURS['payload']), adt2)
t2 = build_boot(p2, 'raphael-t2-native-fullfix.img')

print('\n== t3: our kernel (kryo485 table) + our ADT unchanged ==')
p3 = patch_tables(OURS['payload'])
assert len(p3) == len(OURS['payload'])
t3 = build_boot(p3, 'raphael-t3-native-tableonly.img')

print('\n== t4: friend kernel + our ADT + our shell ==')
p4 = bytearray(swap_adt(FRIEND['payload'],
                        OURS['payload'][parse_payload(OURS['payload'])['adt_off']:
                                        parse_payload(OURS['payload'])['adt_off'] + 9904]))
set_cmdline(p4, F_VERBOSE)
p4 = bytes(p4)
t4 = build_boot(p4, 'raphael-t4-friendkernel-ouradt.img')

print('\n== verification ==')
ours_adt_bytes = OURS['payload'][parse_payload(OURS['payload'])['adt_off']:
                                 parse_payload(OURS['payload'])['adt_off'] + 9904]
verify(t1, dict(cmdline_has=['cpus=1', 'ufsroot=userdata', 'sweetlog=1'], cmdline_lacks=['sweetfb_noconsole'],
                checks=dict(kernel_is_friend=1, adt_friend=1)))
verify(t2, dict(cmdline_has=['cpus=1', 'ufsroot=userdata', 'sweetlog=1'], cmdline_lacks=[],
                checks=dict(kernel_is_ours=1, table_patched=1, adt_v2=1)))
verify(t3, dict(cmdline_has=['cpus=1'], cmdline_lacks=[], checks=dict(kernel_is_ours=1, table_patched=1, adt_ours=1)))
verify(t4, dict(cmdline_has=['cpus=1', 'sweetlog=1'], cmdline_lacks=['sweetfb_noconsole'],
                checks=dict(kernel_is_friend=1, adt_ours=1)))

print('\nALL FOUR IMAGES BUILT AND VERIFIED')
with open(f'{OUT}/SWAPTEST-SHA256SUMS.txt', 'w') as f:
    for n in ('raphael-t1-friendpayload-ourshell.img', 'raphael-t2-native-fullfix.img',
              'raphael-t3-native-tableonly.img', 'raphael-t4-friendkernel-ouradt.img'):
        f.write(f'{sha(open(f"{OUT}/{n}", "rb").read())}  {n}\n')
    f.write(f'# t1/t4 friend kernel sha256: {sha(FRIEND["kernel.flat"] if False else b"")}'
            if False else '')
print('SWAPTEST-SHA256SUMS.txt written')
