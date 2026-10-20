#!/usr/bin/env python3
"""img2simg.py — 纯 Python 的 raw→Android sparse 转换 + 定长分卷。
用法: python3 img2simg.py RAW.img OUT.simg PART_MB
生成 OUT.simg 和 OUT.simg.part-00..NN（每卷 PART_MB MiB），并打印 total_chunks/blks。
4096 字节块；全零 16MB 段 → FILL 块；末尾附加 CRC32 块（与 AOSP img2simg 一致）。
"""
import os, struct, sys, zlib

BLK = 4096
SEG_BLKS = 1024              # 4 MiB 段（零块检测粒度）
RAW, FILL, DONT_CARE, CRC = 0xCAC1, 0xCAC2, 0xCAC3, 0xCAC4


def convert(src, dst):
    size = os.path.getsize(src)
    assert size % BLK == 0, "image size must be multiple of 4096"
    total_blks = size // BLK
    f = open(src, "rb")
    out = open(dst, "wb")
    out.write(struct.pack("<IHHHHIIII", 0xED26FF3A, 1, 0, 28, 12, BLK, 0, 0, 0))
    nchunks = 0
    crc = 0
    for seg in range(total_blks // SEG_BLKS):
        data = f.read(BLK * SEG_BLKS)
        assert len(data) == BLK * SEG_BLKS
        crc = zlib.crc32(data, crc)
        first4 = data[:4]
        if data == b"\x00" * len(data):
            out.write(struct.pack("<HHII", FILL, 0, SEG_BLKS, 16) + struct.pack("<I", 0))
        elif first4 * SEG_BLKS == data:
            out.write(struct.pack("<HHII", FILL, 0, SEG_BLKS, 16) + first4)
        else:
            out.write(struct.pack("<HHII", RAW, 0, SEG_BLKS, 12 + len(data)) + data)
        nchunks += 1
    rem = total_blks % SEG_BLKS
    if rem:
        data = f.read(BLK * rem)
        crc = zlib.crc32(data, crc)
        out.write(struct.pack("<HHII", RAW, 0, rem, 12 + len(data)) + data)
        nchunks += 1
    out.write(struct.pack("<HHII", CRC, 0, 0, 16) + struct.pack("<I", crc))
    nchunks += 1
    out.seek(0)
    out.write(struct.pack("<IHHHHIIII", 0xED26FF3A, 1, 0, 28, 12, BLK,
                          total_blks, nchunks, 0))
    out.close(); f.close()
    return total_blks, nchunks


def split(path, mb):
    part = mb * 1024 * 1024
    n = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(part)
            if not b:
                break
            open(f"{path}.part-{n:02d}", "wb").write(b)
            n += 1
    return n


if __name__ == "__main__":
    src, dst, mb = sys.argv[1], sys.argv[2], int(sys.argv[3])
    blks, ch = convert(src, dst)
    parts = split(dst, mb)
    print(f"sparse: {blks} blocks, {ch} chunks, {parts} parts, "
          f"{os.path.getsize(dst)/1e9:.2f} GB (raw {os.path.getsize(src)/1e9:.2f} GB)")
