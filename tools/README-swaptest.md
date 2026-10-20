# build-swaptest.py — R11 bootstrap-done bisection images

Builds four cross-swap boot images from two unpacked boot images (ours = the
sc-verbose image that stalls at `bootstrap done`, friend = the 0082e image that
reaches the lock screen). Each output keeps OUR shim + OUR stock DTB and a
console-on cmdline; only the payload parts listed below change:

- `t1` friend kernel + friend ADT — shell vs payload attribution
- `t2` our kernel with the match-table patch (`qcom,kryo470` -> `qcom,kryo485`,
  `Kryo 470` -> `Kryo 485`, equal length, in place) + fixed ADT (1 CPU node,
  fbcon reg 0x9a4000, /product spliced from friend's ADT with phandle 0xff)
- `t3` our kernel with the table patch only
- `t4` friend kernel + our unchanged ADT

Usage:

    python3 tools/unpack_bootv2.py ours.img   cmp/ours
    python3 tools/unpack_bootv2.py friend.img cmp/friend
    # place the sc-verbose source image next to the script input:
    SWAPTEST_BASE=cmp SWAPTEST_OUT=out python3 tools/build-swaptest.py

The script re-parses every output (payload header, seg table, ADT tree, DTB
magic, shim bytes, cmdline) and asserts the expected combination before
printing the sha256 lines that go into SWAPTEST-SHA256SUMS.txt.

Rationale and test procedure: Release `raphael-swaptest-r11` / TEST-MATRIX-R11.md.
