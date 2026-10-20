# tools/repack-boot-v2.py — raphael shim boot 镜像重打包工具

恢复旧工作区丢失的 "v2 重打包" 环节：对 shim boot 镜像（Android boot header v2 +
shim 作 kernel + SWEETXNU payload 作 ramdisk + raphael DTB 追加段）做 **原位
cmdline 补丁**，除 payload boot-args 外保持逐字节一致。

## 用法

```bash
# 完整性自检（不改 cmdline，输出必须与输入逐字节一致）
python3 tools/repack-boot-v2.py diag5.img sanity.img --check

# 生产版 full（build-raphael.sh 原版 cmdline，无控制台叠加）
python3 tools/repack-boot-v2.py diag5.img shim-boot-raphael-full.img \
  --cmdline 'debug=0xc serial=3 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetfb_noconsole=1 sweetfb_hz=30' \
  --check

# 排障版 verbose（diag5 cmdline 仅改 cpus=8，保留屏上日志 + sweetusb=2 UDP）
python3 tools/repack-boot-v2.py diag5.img shim-boot-raphael-full-verbose.img \
  --cmdline 'debug=0xc serial=3 cpus=8 keepsyms=1 -enable_kprintf_spam -noprogress rd=ufsroot0 unentitled_ios_sim_launch=1 ignition_level=1 wdt_test=no_user_checkin ufsrw=1 rootrw=1 launchd_unsecure_cache=1 wdt=-1 sweetusb=2' \
  --check
```

## 镜像布局（实证逆向自 diag5，全部 little endian）

Android boot header v2（mkbootimg --header_version 2，pagesize 4096）：

| 段 | 偏移 | 内容 |
|----|------|------|
| header | 0x0 | 1660B 有效字段；header_version 在 **v0 dt_size 槽位 @0x28**（raphael ABL 实际读取点） |
| kernel | 0x1000 | shim（200KB，ARM64 freestanding） |
| ramdisk | 0x33000 | **SWEETXNU payload**（XNU kernelcache + ADT，ramdisk_addr=0x1000000） |
| dtb | ramdisk 对齐页后 | raphael FDT（d00dfeed，self-describing totalsize） |

header 尾部（1632B v0 结构之后）：

| 偏移 | 字段 | diag5 实测值 |
|------|------|-------------|
| 1632 | u32 recovery_dtbo_size | 0 |
| 1636 | u64 recovery_dtbo_offset | 0 |
| 1644 | u32 header_size（fork 自定义记账） | 1660 |
| 1648 | u32 dtb_size | 0（DTB 实体仍在文件尾追加；ABL 运行时交给 shim 的是自己的 FDT，此字段不影响启动） |
| 1652 | u64 dtb_addr | 0x1f00000（= --dtb_offset） |

SWEETXNU payload v1 头（与上游 tools/mkpayload.py 一致）：

```
0x000 magic[8]="SWEETXNU"  0x008 u32 version=1, nsegs
0x010 u64 virt_base, entry_va          0x020 u64 adt_off, adt_size
0x030 u64 kernel_end_va                0x038 u64 phys_base
0x040 u64 mem_size                     0x048 char cmdline[608]
0x2a8 seg[nsegs] { u64 vmaddr, vmsize, file_off, file_size }
```

## 已知限制

- header `id[]`（20B build id）由原构建管线对重打包前输入计算，本地无法复现；
  重打包后保持原值。该字段纯记录用途，ABL/shim 均不校验（diag5 实测证明）。
- 本工具只改 payload cmdline 缓冲区（608B，NUL 填充），绝不动 kernel/ADT/DTB 字节。
