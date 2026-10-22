# Worklog

---
Task ID: 1
Agent: Super Z (main agent)
Task: 研究 ios-sweet 项目并将 iOS 16 (XNU) 移植到 Redmi K20 Pro (raphael / SM8150)

Work Log:
- 深度研究了 dipa-studio/ios-sweet：README、NOTES.md（385 行工程日志）、81 个内核补丁、shim、AGENTS.md
- 评估 raphael 可行性：SM8150 与 SM7150 同代（Kryo 400、ARMv8.2 无 PAC、GICv3 双安全态、GENI/QUP、RPMh、SPMI、DWC3、UFS 2.1）
- 获取硬件事实三重来源：用户提供的 V12.5.6.0.RFKCNXM 官方固件（Range 分片并行下载 2.5GB 前缀，提取 boot.img + 4 个 SoC DTB）、Xiaomi raphael 内核源码 DTS（GitHub API 逐文件抓取）、mainline 参照
- 关键硬件验证（boot.img DTB 实证）：GICD 0x17a00000/GICR 0x17a60000、UFS 0x1d84000、SPMI 0xc440000/0xe600000/0xc40a000、RPMh RSC 0x18220000/TCS 0x18220d00、PSHOLD 0xc264000、帧缓冲 0x9c000000(0x2400000)、MPIDR Aff1=核号、定时器 PPI 18/19、imem 重启寄存器 0x146bf65c
- 触摸：Goodix GT9889 @0x5d SE19(0xc88000, wrap2_s2: 投票 BIT6@0x52014, RCG 0x1e3a8)，供电 TLMM GPIO98(3V3)/GPIO100(1V8)，reset GPIO54/IRQ GPIO122，GTX8 0x824E 协议（8字节/点小端坐标）
- 音量上键：所有 DTS 无 KEY_VOLUMEUP，暂缺（withheld），需真机 live DT 确认
- 下载 xnu-8796.141.3 源码（80MB），按序应用全部 81 个 sweet 补丁（含 libpthread/HFS/BearSSL staging，Linux 下伪造 xcrun/SDK stub）
- 编写 raphael 适配（全部 #if ARM64_BOARD_CONFIG_RAPHAEL 门控，SWEET 构建不变）：
  - 补丁 0082-raphael-machine-config（机器配置注册 + 复用 SWEET 驱动集）
  - 补丁 0083-raphael-input（GT9889 协议 + SE19 时钟/引脚 + TLMM 供电 + keys PON-only）
  - 补丁 0084-raphael-display（1080x2340：early console、start.s panic 行、SweetHID 缩放）
  - mkadt.py --raphael（面板/时钟/Kryo485）、shim RAPHAEL=1（FB 高度、imem、boot header v1 + DTB 追加）
  - tools/build-raphael.sh、tools/raphael-dtb-extract.py、tools/package-raphael.py（python-only 打包）
  - stage 脚本放开 MACHINE_CONFIG 门控；README-RAPHAEL.md、NOTES-RAPHAEL.md
- 补丁自测：重置到 pre-raphael 树重放 0082→0084 全部干净应用
- 用户提供的 GitHub token：fork → Gsjsjzhznsz/ios-sweet；推送 main+raphael 分支；注册并激活 Actions；触发三路构建：xnu(RAPHAEL 内核, run 39246750285)、raphael(shim, run 39246795196)、xnu(SWEET 验证, run 39246201208)

Stage Summary:
- 交付物：Gsjsjzhznsz/ios-sweet fork（main = 完整移植），本地 /home/z/my-project/ios-sweet-raphael/ios-sweet
- raphael ADT 生成验证通过（1080×2340/4320、Kryo485 时钟、MPIDR、UFS 基址）
- 三路 CI 运行中，等待产物：kernel.development.raphael + raphael-shim/Image
- 下一步：CI 产物下载 → 本地组装 shim-boot-raphael.img（package-raphael.py）→ 用户真机 fastboot boot 测试 → 按日志迭代

---
Task ID: 2
Agent: Super Z (main agent)
Task: 完成 raphael 移植的 CI 构建闭环并产出首测镜像

Work Log:
- 用户提供了 GitHub token，fork 到 Gsjsjzhznsz/ios-sweet，推送 main+raphael 分支
- CI 迭代修复链（每轮拉取 Actions 日志定位）：
  1. makedefs arm64e 豁免条件写反（ifneq→ifeq filter）→ SWEET 构建回归，修复后 main 分支 SWEET 构建成功
  2. 缺 config/MASTER.arm64.raphael → nos_arm_pmap/mockfs/sweet_hfs 选项缺失 → vm_last_phys 链接失败 → 创建（复用 sweet 选项集）
  3. bsd/conf/Makefile.template 的 SWEET 门控 → pthread/HFS include 路径 → 放开给 RAPHAEL
  4. libkern/conf/Makefile.template 同样的 BearSSL include 门控 → 放开
  5. MACHINE_FLAGS_ARM64_RAPHAEL 需同时定义 ARM64_BOARD_CONFIG_SWEET（驱动文件首行守卫在 include 前求值）
  6. vendor AOSP mkbootimg.py（LineageOS 镜像，gki 签名桩化）；package-raphael.py 参数前缀修复
- 最终结果：xnu.yml run 39257766195 SUCCESS → kernel.development.raphael (17.2MB)；raphael.yml shim 构建成功
- 本地组装：mkadt --raphael --highmem → mkpayload（16.6MB payload，链式重定位已解）→ package-raphael.py 打包
- 交付物（/home/z/my-project/download/）：shim-boot-raphael.img (17.3MB, 结构校验全过：ANDROID! v1 头/DTB magic/SWEETXNU payload)、payload、ADT、内核、测试说明

Stage Summary:
- RAPHAEL 内核在 GitHub macOS runner 上完整编译链接成功；首测镜像就绪
- SWEET 回归验证通过（main 分支构建成功）
- 用户下一步：fastboot boot shim-boot-raphael.img 冒烟测试 → 构建 iOS rootfs → 完整启动

---
Task ID: 3
Agent: Super Z (main agent)
Task: 更新仓库 README + 利用 K20 Pro 公开资源（mainline DTS/内核源码）关闭移植缺口（音量上键/触摸二供/USB），worklog 入库

Work Log:
- 资源调研（K20 Pro 场景优势兑现）：
  - mainline 补丁系列 "[PATCH v2 0/3] Add Xiaomi Redmi K20 Pro (Raphael)"（patchew 20251104221657, pc1598@mainlining.org）→ 音量上键实锤：pm8150_gpios 6 GPIO_ACTIVE_LOW
  - howtocuddle/xiaomi_raphael（6.18 mainline 状态：显示 ams639rq08/触摸/相机）+ ZakoClubROM/android_kernel_xiaomi_raphael lineage-19.0 分支
  - 内核源码 drivers/input/touchscreen/：goodix_driver_gt9886 + fts_521 → 证实 fts_521 是 ST FingerTipS（I2C 0x49，0xFA+4字节大端地址读 0x20000000 芯片ID，FIFO 0x86 读 8 字节事件 b0>>4=enter/motion/leave），此前"FocalTech 0x38"判断为误读
  - mainline sm8150.dtsi + gcc-sm8150.c：USB30_PRIM 的 DWC3 0xa600000/qscratch 0xa6f8800/QUSB2 0x88e2000/GDSC 0xf004 与 sweet 完全相同；仅 cfg-noc 0x502c→0xf078、aggre 0x8201c→0xf07c、phy-ref=USB3_SEC_CLKREF 0x8c028（0x8c010 在 sm8150 是 gpu_iref）
- 编写补丁（xnu-tree 编辑 → git diff 生成，重放验证干净应用）：
  - 0085-raphael-volumeup.patch：keys GPIO 常量按板分级（PPID 0x0c5/RT 0xc510）+ keys_gpio_census() 一次性只读普查全部 PMIC GPIO 块作为真机证据
  - 0086-raphael-touch-stfts.patch：更正二供为 ST FTS；0x49 只读探测打日志；Goodix 失败且 0x49 应答时走 touch_stfts() 只读事件泵；修复轮询 IRQ 引脚硬编码 9 → TOUCH_GPIO_IRQ(122)
  - 0087-raphael-usb.patch：usb_cbcr 表按板分级（含注释差异表），phy 探测门控改为 phy-ref；ue0/ECM/UDP 日志链路全部激活（boot-arg sweetusb=2）
- 文档：README.md 加 raphael 版块；README-RAPHAEL.md 重写状态/缺口/资源清单；NOTES-RAPHAEL.md 补音量键、ST FTS 更正、USB 对照表、外部来源清单
- 工程卫生：Edit 工具把整文件 tab→空格导致 749 行空白噪声 diff，写 scripts/restore_indent.py 以 HEAD 为基准恢复原始缩进（最终 diff 仅 +177/-24）；语法平衡检查通过
- worklog 同步入库为 docs/WORKLOG.md（用户新要求：防记忆丢失）

Stage Summary:
- 三个移植缺口全部关闭（音量上键/触摸二供/USB 日志通道），补丁已验证可干净重放
- 文档三件套与资源链接更新完毕，rme：mainline 化的硬件事实表可直接支撑后续真机调试
- 下一步：push → CI 重建 RAPHAEL 内核 → 重打包 shim-boot-raphael.img → 用户真机测试

---
Task ID: 4
Agent: Super Z (main agent)
Task: CI 重建 RAPHAEL 内核（fecc50a）并重打包首测镜像，交付物刷新，worklog 入库

Work Log:
- 推送 raphael 分支（fecc50a）→ 触发 xnu workflow（machine_config=RAPHAEL, run 39268242631），~9 分钟构建 SUCCESS，head_sha 确认为 fecc50a
- 下载产物 kernel.development.raphael（17,206,056 字节 Mach-O arm64）
- 本地重打包：mkadt --raphael --highmem → mkpayload（cmdline 与上轮一致）→ package-raphael.py（stock boot.img 提取 SM8150 v2 DTB，header v1）
- 结构校验：ANDROID! v1 头、kernel blob 末尾 DTB magic 0xd00dfeed、SWEETXNU payload 在位
- 交付物刷新（/home/z/my-project/download/）：shim-boot-raphael.img (17,301,504)、payload-raphael.bin、sweet-raphael.adt、kernel.development.raphael、README-RAPHAEL-TEST.txt（含 sweetusb=2 直播日志指引，已修正过时的"已知限制"段）
- worklog 同步 docs/WORKLOG.md 并推送仓库

Stage Summary:
- 含 0085-0087 的首测镜像就绪：真机 fastboot boot 即可验证音量上键/触摸二供/USB 直播日志三条新链路
- 验证顺序建议：sweetusb=1 看时钟/GDSC 报告 → sweetusb=2 + sweet-usbnet.sh 直播日志 → cpus=1→8 → rootfs

---
Task ID: 5
Agent: Super Z (main agent)
Task: README 双语化（默认中文）+ 仓库全面清除 Note 10（sweet/SM7150）内容，仓库定位改为纯 raphael/855

Work Log:
- README.md 全文重写：双语结构（中文默认在上、English 完整镜像在下），内容 100% raphael（K20 Pro / SM8150 / 骁龙 855）
  - 新增：当前状态表（8 子系统）、启动链、三条日志通道说明、真机测试指南（备份/rootfs/CI 内核/打包/fastboot boot/boot-args 速查）、raphael 补丁表 0082-0087、SM8150 硬件事实、K20 Pro 刷机生态资源清单（mainline DTS / howtocuddle 6.18 / pmOS / ZakoClubROM 内核源码 / LineageOS / XDA）、仓库布局、Credits（上游 dipa-studio/ios-sweet 框架署名）
- 删除旧 NOTES.md（433 行，上游 Note 10 工程日志，169 处 sweet 引用）→ git rm
- NOTES-RAPHAEL.md → git mv 为 NOTES.md 并重写净化：删除全部 "identical/mirrors/like sweet" 对照叙述与 sweet(SM7150) 对照列，改为 raphael 单列 + "generic value, no change / generic constant was X" 表述；外部来源列表去掉 sm7150.dtsi/gcc-sm7150.c
- 删除 README-RAPHAEL.md（内容已并入新 README）
- AGENTS.md 重写：指向新文档结构 + "每步完成即 commit+push worklog" 规则（用户要求）
- 交叉引用修正：tools/mkadt.py docstring（SWEET xnu→XNU kernel、sweet live FDT→target device's live FDT、NOTES-RAPHAEL→NOTES）、raphael.yml 注释（README-RAPHAEL→README）
- .gitignore 增加 shim-boot*.img（首测镜像不入库）
- 清除验证：grep note10/SM7150/732G 于 README/NOTES/AGENTS = 0 命中；剩余 sweet 均为代码字面量（fork 仓库名、工具/产物文件名、boot-arg、'xiaomi,sweet' 兼容串、SweetHID 组件名）
- 文档保留范围声明：0001-0081 补丁与工具文件名为上游框架遗产，属代码标识符而非 Note 10 内容，未重命名（避免破坏 CI 补丁序与内核构建）

Stage Summary:
- 仓库文档层已完全定位为 raphael/855 项目；README 双语、中文默认
- 待办不变：真机 fastboot boot 冒烟测试（cpus=1 起步）

---
Task ID: 6
Agent: Super Z (main agent)
Task: 无电脑（手机对手机）测试方案：cpus=1 保守镜像 + 零 PC 逐步指南 + 交付 zip

Work Log:
- 用户环境确认：完全没有电脑，仅有另一台可做 fastboot 主机的安卓手机
- 本地重打包 shim-boot-raphael-safe.img（scripts/repack-raphael-safe.sh）：同一内核（fecc50a，含 0085-0087）+ 同一 ADT，cmdline 改为 cpus=1、去掉 sweetfb_noconsole/sweetfb_hz（屏幕控制台常显）、不启用 sweetusb —— 首测最大可见性
- 结构校验：ANDROID! header v1、ramdisk == payload cmp 一致、payload cmdline 复核（cpus=1，无 fb mute）
- 交付 zip：raphael-p2p-test.zip（12MB）= safe 版 + 8 核版 + 测试指南 txt
- 撰写 docs/TEST-NO-PC.txt（零 PC 指南）：Termux(F-Droid/GitHub) + android-tools + OTG fastboot boot 流程、预期现象与拍照留证、OrangeFox 终端一行 dd 提取 userdata 末尾 4MiB 日志环（备选 Termux adb pull）、结果自查清单、常见问题（OTG 不识别/未解锁 not allowed/黑屏但 Booting OK）、风险边界（boot 不刷分区）
- README.md 中英两区增加"没有电脑？"入口链接 docs/TEST-NO-PC.txt
- 交付物（/home/z/my-project/download/）：shim-boot-raphael-safe.img、raphael-p2p-test.zip、无电脑测试指南-手机对手机.txt

Stage Summary:
- 用户可全程无电脑完成冒烟测试：手机 A(Termux) --OTG--> K20 Pro fastboot boot
- 硬门槛已在指南标注：K20 Pro 必须 BL 已解锁（小米解锁依赖 Windows 工具）
- 等待用户回传：屏幕照片 / sweet-log.bin；后续 rootfs 阶段拟用云 Linux 服务器代跑 mkiosroot

---
Task ID: 7
Agent: Super Z (main agent)
Task: 首轮真机测试结果分析（黑屏+日志空）→ 闪存面包屑诊断镜像（v1+v2）

Work Log:
- 用户回传：fastboot boot OKAY（主机手机 OTG 成功），K20 Pro 全程黑屏无背光，无自动重启；tail -c 4194304 sda31 提取 4MiB
- 日志分析（scripts/analyze-sweetlog.py + decode-log.py）：4MiB 内零 SWEETLOG 头、零 SWEET/Darwin/panic 标记，前 2.1MiB 可打印率 37%（Android 遗留 FS 数据），0x205000 后全零 ⇒ 本次启动未写过任何内核日志；且用户 tail 少了日志头块（区域=[头 4K][环 4M]），sda31=userdata 待 by-name 核实
- 证据推理：shim 首屏动作是 con_clear(RED)（红屏）；异常路径会画蓝屏并 40s 自动重启，用户需长按电源 ⇒ 极早期崩溃（ABLL未交控制权/shim 首 C 调用前）或面板在 ABL 交接时被关闭，证据不足
- shim 面包屑实现（013048e）：ufs.c SCSI 增加方向参数+WRITE(10)；ufs_crumb() 把阶段记录写到 userdata 最后 4KiB（MMU off、Device 内存、复用 test_ufs 的 UTRL 接管流程+GPT 找 userdata 尾块）；shim_main 入口 MAIN、exc_handler EXC(slot/ESR/ELR/FAR)、loader DTB/PLD/SEG/JUMP；SWEET 构建 no-op 不受影响
- CI 异常排队 30+ 分钟后首个 run 39279520451 成功（GCC 15.2），artifact Image 200,704 字节；本地工具链方案（xpack/deb）备而未用
- 打包：payload-raphael-diag.bin（cmdline=safe 版+sweetusb=2）；shim-boot-raphael-diag.img（header v1）+ shim-boot-raphael-diag-v2.img（header v2 兜底实验，DTB 独立段）；双双 ANDROID! 头校验
- 交付：raphael-diag-round2.zip（12MB，双镜像+第二轮指南）；docs/TEST-NO-PC-DIAG.txt（补拉日志头/USB 枚举 sysfs 检查/面包屑判读表）

Stage Summary:
- 第二轮测试三证据通道：闪存面包屑（核心）+ sweet-full.bin 日志头 + 主机 sysfs USB 枚举
- 等待用户回传 crumb.bin / sweet-full.bin；JUMP 后无内核日志 ⇒ 内核极早期问题，有 EXC ⇒ shim 可定位

---
Task 8
Agent: Super Z (main agent)
Task: 第二轮证据解读 + shim 阶段码诊断（diag4）交付

Work Log:
- 证据更正：crumb.bin 仅 22 字节 = 提取命令失败（tail -c 4096 必产 4096），"无面包屑"结论未定；sweet-full.bin 乱码 = 内核 UFS 驱动未通（预期，0047 日志线程挂在 UFS probe 后）；18d1/Android = ABL fastboot gadget 残留（XNU 应枚举 1209/Sweet iOS），加 fastboot devices 判别法
- 确认 0084 无 DSI/面板初始化 → fastboot boot 后 ABL 关显示，黑屏是结构性预期，不是崩溃信号
- shim 阶段诊断（6b2b23c + 修复 b5c9e04，CI run 39292316444）：ramoops 区（0xa1dff000/0xa1601000，原厂 DTS pstore 请求 0xc00000 > 区 0x800000 永不绑定）写 STGD 二进制+ASCII 记录（阶段码/面包屑故障码/ESR/ELR/FAR）；shimstage=1 boot 不跳 XNU，按 20+20×阶段 秒自动重启（140s=阶段6→XNU侧问题；40s=异常；200s=校验失败；永不=极早期挂死）
- ufs_crumb_diag()：面包屑失败原因码（host 未就绪/列表接管/TUR/GPT/无 userdata/写失败 rc）
- fdw 修复：fdt_chosen_str 曾覆盖 fdt_chosen_u64 导致 CI 链接失败，已恢复双函数；stage ASCII 96→128
- TEST-NO-PC.txt dd 提取改为 tail -c 4198400（真机实测 TWRP 下 blockdev 负数）；新增 docs/TEST-NO-PC-DIAG3.txt
- 交付 raphael-diag-round3.zip（diag4 v1+v2 + 指南）

Stage Summary:
- 三条零依赖证据链（秒表解码/devmem DDR 记录/闪存面包屑+故障码）+ USB 判别法就绪
- 等用户回传：crumb.bin（wc=4096）、diag4 掐表结果、devmem 四值、fastboot devices 判别输出

---
Task ID: 9
Agent: Super Z (main agent)
Task: 第三轮真机结果解读（diag4-v2 点亮屏幕）+ diag5 XNU 直通镜像交付

Work Log:
- 屏幕输出逐行核对 shim.c/loader.c 源码：SHIM milestone 4 → INITRD/PHYS/VIRT/ENTRY/SEGS/BOOTARG/JUMP 全部来自 loader.c，"RESET now" 是 reset() 的计划内打印（con_str("RESET","now")，shim.c:120）
- 结论：diag4 的 shimstage=1 在跳转前故意拦停（loader.c:162 stage_diag_final()，20+20×6=140 秒后打印 RESET now 并 PSCI 复位）——XNU 从未运行，本轮零崩溃，shim 6 阶段全绿
- v1 死寂/v2 点亮的差异 = boot 头格式：v1 为 header v1（DTB 拼接 kernel），v2 为 header v2 + 独立 DTB section；raphael 小米 ABL 只接受 v2 格式（之前多轮 header-v1 镜像很可能从未执行）
- payload-raphael-diag4.bin 头部实解：phys_base=0x100000000、mem_size=0xFCC00000、virt_base=0xFFFFFE0006000000、entry_pa=0x10148B488——屏幕上 "PHYS base=00000000" 是 con_hex2 的 uint32 截断显示，非真值
- 屏幕点亮证明 ABL 显示管线在 fastboot boot 后持续自刷新，写 splash framebuffer 即可上屏（更正第二轮"结构性黑屏"判断）；fb 0x9c000000 与 RAM 0x100000000 在 16K granule 下同属 V=P L1 index 0 的 64GB 窗口，0010 的 fb bootstrap 映射（L2 idx 78 < RAM idx 128）在 raphael 上无冲突
- XNU 侧诊断资产核查（fecc50a 已含）：start.s stage-0 白条（MMU off 直画）+ sweet_early.c 早期文本控制台 + sweet_early_mark(1..8)（arm_init 七个埋点 + TTBR0 切换）+ sweet_early_panic；0084 已适配 2340 高度
- diag5 打包（scripts/package-raphael-diag5.sh）：同一 shim/内核/ADT，cmdline 去掉 shimstage=1，header v2；cmp 校验 = 与 diag4-v2 仅差 12 字节 shimstage 区 + 20 字节 build id
- 交付 shim-boot-raphael-diag5.img + payload-raphael-diag5.bin + docs/TEST-NO-PC-DIAG5.txt（含白条/SWEET EARLY 1-8 结果对照表、6GB 机型预警、掐表要求）

Stage Summary:
- shim 链路真机验证完毕；下一轮 XNU 首跳，XNU 内置三段早期诊断开箱即用，无需新内核构建
- 关键认知：屏幕 = 第一诊断通道；v2 头 = 唯一被 ABL 接受的格式；18d1/Android = ABL fastboot gadget 残留
- 等 diag5 回传：白条是否出现、SWEET EARLY 走到第几行、定格画面全景、掐表时间线

---
Task ID: 10
Agent: Super Z (main agent)
Task: t7 实测"其他全绿、触摸仍死"日志分析 → CI 级根因（push 构建 SWEET 回退）→ 修复 + t8 交付

Work Log:
- sweet-log.bin（4MiB 环）解码：唯一一次启动，boot-args = t7 r15（cpus=8/sweetfb_noconsole=1/sweetfb_hz=60/sweettouchflip=0）；触摸线：gcc vote=0x4bc0000 rcg=0x80000000、分支 0x18008 HW-gated(0x80000002) ok / 0x18144 still halted(0x80004220) 继续、se7 fw=0x303 proto=3 status=0 tx/rx 32 位 FIFO 全过、"need ABL-loaded I2C firmware and 32-bit FIFOs; probes skipped"
- 寄存器语义（Linux geni-se.h 核对）：0x68=GENI_FW_REVISION_RO、0xe24/0xe28=HW FIFO 参数、0x908=GENI_IOS、0x64=GENI_IF_DISABLE_RO（bit0=接口禁用）→ skip 触发点
- 关键矛盾：日志分支偏移 0x18008/0x18144 ∈ SWEET 列表，而 raphael 列表应为 0x1e004/0x1e008/0x1e3a4
- CI 日志取证（run 39469756410，a4ca660=Head of r15）：event=push；937/937 条 clang 命令仅 -DARM64_BOARD_CONFIG_SWEET。对照 fecc50a（t2-t6 时代内核，run 39268242631）= workflow_dispatch + machine_config=RAPHAEL，962/962 带 -DRAPHAEL —— 0089 commit message 引用的 "0x1e008 halted" 正是 r14（dispatch、RAPHAEL）t6 日志的真实 wrap2 s_ahb 卡点；r15/t7（push）退化成 SWEET，0089 从未被测试
- 根因：xnu.yml push 触发时 inputs 为空 → MACHINE_CONFIG 回退 'SWEET' → 所有 raphael #if 增量（触摸 SE19/GT9889/TLMM 供电/音量上键/USB/0086/0089）预处理剔除；显示/ADT/UFS 因板级无关而幸存，掩盖了问题
- 修复 ea69ad1：push 默认也 RAPHAEL + Build 改 tee build.log + "Verify board macro" 步骤（RAPHAEL 构建下编译命令零 -DRAPHAEL 即 fail）；新内核 run 39517478755 复验 937/937 带 -DRAPHAEL，sweet_touch.c 双宏齐备
- t8 打包：t7.img 提取 shim/ADT/DTB/cmdline（tools 复用 repack-boot-v2 解析）→ mkpayload 新内核（entry 0xfffffe000748b488 与启动谱系一致，nsegs=10）→ 模板头装配（scripts/t8_build.py：仅 ramdisk_size 变化，shim/DTB/ADT/cmdline 逐字节不变）；payload 字符串普查确认 RAPHAEL 触摸打印全在、SWEET 触摸打印全消
- Release raphael-touch-r16：raphael-t8-clean.img（1bcdfbb9…）、raphael-t8-debug.img（f6bcfc9f…，+sweethidtest=15）、FLASH-T8.md、T8-SHA256SUMS.txt；README 状态/下载表更新；t8_extract/t8_build 工具入库
- 新工具：scripts/t8_extract.py（boot v2 组件提取）、scripts/t8_build.py（模板装配+六重校验）；ST FTS 澄清：raphael 二供为 ST FingerTipS（fts_521@0x49），非 FocalTech

Stage Summary:
- 触摸失灵定性：既非 SE19 固件未加载、非 I2C 地址错误、也非二供批次——raphael 触摸代码根本没编进 t7 内核
- t8 为首次"RAPHAEL 编译 + 0089"组合；预期日志：分支 0x1e004/0x1e008(HW-gated ok)/0x1e3a4 + TLMM reset(gpio54) 供电 + probe 0x5d ver-reg / probe ST FTS 0x49
- CI 侧回归防线就位：宏断言防复发；回退 = 任意 t 系列直启

---

Task ID: 11
Agent: Super Z (main agent, post-handover session)
Task: 项目交接（session 更替）——凭据/仓库/CI/Release 全量盘点，本地工作环境恢复，worklog 双写机制重建

Work Log:
- 接收用户指示：GitHub 凭据保留使用（token 已内嵌于 git remote URL，`git remote get-url origin` 可取；用户明确豁免安全顾虑）；裸 token 不入 git（AGENTS.md 卫生规则）
- Clone Gsjsjzhznsz/ios-raphael main @ c1da721（= r16/t8 发布提交），工作树 clean，与 origin/main 同步
- 通读交接材料：README.md（r16/t8 状态表 + 下载表 + 刷机指南）、AGENTS.md（worklog 双写 + 即时 push 协议）、NOTES.md（SM8150 硬件事实 / GT9889 协议 / ST FTS 二供 / USB 表）、docs/WORKLOG.md Task 1-10 全量、docs/FLASH-T8.md（t8 判读树）
- CI 核查（API）：最新 xnu push run 39517478755（ea69ad1）success —— 即 t8 内核（RAPHAEL 宏 937/937 复验通过的那次构建）；build-ios-rootfs 39371434600 success
- Release 核查：共 9 个（ios-rootfs-16.7.16-12 … raphael-touch-r16）；最新 raphael-touch-r16（2026-10-21T00:10Z）= t8-clean/debug + FLASH-T8.md + T8-SHA256SUMS，与 README 下载表哈希一致；无 open issues
- 本地环境恢复：/home/z/my-project/download/ 为空（新会话起点，t 系列镜像按需从 Release 取）；重建 /home/z/my-project/worklog.md 并与 docs/WORKLOG.md 同步
- 交接点确认：t8 已发布未实测 —— 等待用户真机 fastboot boot raphael-t8-clean.img（或 debug 版）回传：触摸现象 + sweet-log.bin；判读路径 = FLASH-T8.md 决胜行（probe 0x5d / ST FTS 0x49 / probes skipped）
- 挂起事项继承：熄屏渐慢（sweetfb_hz 30→60 对照，t7/t8 cmdline 已带 60）待 t8 回报时一并观察

Stage Summary:
- 交接完成，无状态丢失；项目处于 r16/t8 待实测节点
- 下一步：用户刷 t8 → 回传日志/现象 → 按 FLASH-T8.md 判读 → 触摸收尾或转入下一子系统迭代

---

Task ID: 12
Agent: Super Z (main agent)
Task: t8 实测回归（卡 bootstrap done，t7 正常）→ 取证定位 → t9 修复发布 + 发行版清理（保留 t7/ios16）

Work Log:
- 用户回报：t8 卡 bootstrap 而 t7 正常；要求恢复 bootstrap done 之后的启动链；清除发行版只保留 t7 与 ios16
- 取证基建：下载 t8 内核 CI 构建树产物（run 39517478755 xnu-buildtree，含已应用全部 89 补丁的源码）；下载 t2/t6/t7/t8 四代镜像（SHA256 与发布值一致）；趁删除前抢救 R11 交叉定位文档 TEST-MATRIX-R11.md
- 代码侧排查（全链路）：git diff 333512b..ea69ad1 实锤 t6→t8 树差异仅 sweet_touch.c（线程路径，45s 延迟启动，所有等待带上界）；sweet_early/SweetHID/keys/usb 的 raphael 段逐一审计均无害 → 单纯代码差异无法解释 t7/t8 分野
- 决定性实证（镜像字符串标记 + ADT 逐节点解析）：
  1) t2/t8 = RAPHAEL 编译（TLMM reset(gpio/census 在），t6/t7 = SWEET 编译（Yellowstone/L11C 在）—— t5–t7 全是 SWEET 内核，RAPHAEL 编译从未在 t 系列成功启动；纠正 Task 10 "r14=dispatch/RAPHAEL" 的记载（t6 镜像为 SWEET 编译）
  2) t 系列 ADT（t6/t7/t8 逐字节同，f50510e0）与 t2 ADT 唯一结构差异 = CPU 节点 1→8（fbcon 9c000000+0x9a4000、/product、其余全部相同）
  3) R11 矩阵复盘：diag5/r11-sc/t8 三个 RAPHAEL 启动全部卡在同一卡点（UFS probe 之前），唯一例外 t2；t2 差异 = ①匹配表 kryo470→485（只做过二进制就地补丁，从未入库：KernelConfigTables.cpp:47 仍是 kryo470 vs ADT 声明 kryo485）②ADT 仅 1 CPU 节点；两变量从未隔离（t3/t4 未测）
- t9 修复（t2 配方正式入库）：
  - 补丁 0090-raphael-cpu-match：IONameMatch 'qcom,kryo470'→'qcom,kryo485' + cpuName "Kryo 470"→"Kryo 485"（从构建树 git diff 生成，提交 51af6b9，CI run 39557186698 SUCCESS，内核 SHA 32327c91…，字符串验证 kryo485 在/kryo470 消/0089 在）
  - ADT：scripts/mkadt-1cpu.py 对已发布 t8 ADT 外科手术删 cpu1–7（adt.py 解析/序列化，其余节点逐字节保序）= 7044 字节，与 t2 ADT 同尺寸同拓扑；mkadt.py 增加 --cpus=N 入口（再生成路线因 d22ap.adt 缺失不可用，已记录）
  - 打包 scripts/t9_package.py：t7 镜像骨架 + 新内核 + 1-CPU ADT；clean cmdline 与 t7 逐字节一致（330B）；debug = 去 sweetfb_noconsole=1（屏幕控制台常开，r11 取证法）；六重校验全过（ANDROID!v2/shim/DTB==t7/ADT/cmdline/markers/entry 0xfffffe000748b488 与谱系一致）
- 发行版操作：删除 7 个 Release+tag（r16/r14/r11/r12/r13/sc 单核/sc 全核），保留 raphael-touch-r15（t7）与 ios-rootfs-16.7.16-12；发布 raphael-touch-r17（t9 clean/debug + FLASH-T9.md + T9-SHA256SUMS）
- 文档：README 状态区改写（t8 回归实证 + t9 待测）、下载表裁剪（t9 推荐 + t7 回退 + rootfs）、刷机指南改指 t9；docs/FLASH-T9.md 入库；worklog 双写

Stage Summary:
- 根因画像：卡 bootstrap done ⇔ RAPHAEL 编译 ∧（匹配表 kryo470 失配 ∨ 8-CPU ADT）—— t2 是唯一通关组合，两变量随 t9 一并入库，归因可后补隔离
- t9 一次刷机闭环设计：修好 → 直接锁屏（顺带看触摸）；仍卡 → debug 版拍最后几行即得精确卡点
- 若 t9 通关：下一步仅改 ADT（无需重编内核）逐级回加 CPU 节点 2/4/8 找死点，恢复 8 核；触摸判读沿用 FLASH-T8.md 树


---
Task ID: 13
Agent: Super Z (main agent)
Task: t9 实测解读（触摸仍死 + 卡顿）→ 触摸全链路静态审计 + t10（0091 总线诊断 + 8 核回归）发布

Work Log:
- t9 日志解码（sweet-log.bin 4MiB 环）：t9 完整启动进锁屏（bootstrap-done 修复成立）；`SWEET CPU: requested=8 selected=1` = 单核 → "很卡"定性为 t2 配方副作用；按键 HID 全通
- 触摸判决行：probe 0x5d err=60（ETIMEDOUT）seen=0x40000000（TX 水位触发、2 字节入 FIFO）tx=2 rx=0 status=0（无活动命令）+ abort 干净（无 abort failed、dead=0）→ 序列器活着但总线上零活动；probe ST FTS 0x49 err=5 tx=0 seen=0 → 命令根本没发出
- Bug 实锤（0086 遗留）：touch_msg_run 的 `nt > 3 → EIO(5)` 硬上限拒绝 5 字节 ST FTS 命令（0xFA+4 地址字节）；touch_stfts 运行时 nt=1+nr=8 同样撞 `(nt && nr)` 拒绝 —— ST FTS 探针与轮询全是结构性死代码
- 全链路静态审计（对齐 Linux torvalds 源码 + Lineage raphael vendor 源码 + 原厂 DTB）：SLV_ADDR_SHFT=9/STOP_STRETCH=BIT(2)/I2C 长度寄存器 0x26c/0x270/打包值 0x7f8fe,0xffefe（=geni_se_config_packing(8,4,msb_to_lsb=TRUE) 正是 Linux I2C 取值）/初始化序列（CGC/OUTPUT_CTRL/FIFO 模式/水位/SER_CLK_EN/SCL 计数）逐项等价 —— 驱动配置无错
- 硬件事实三级验证：原厂 DTB pinctrl（qupv3_se19_i2c_active 绑 i2c@0xc88000）、vendor sm8150-qupv3.dtsi（SE19@0xc88000 = wrap2_s2）、vendor sm8150-pinctrl.dtsi（qup19 i2c = gpio57+gpio58）、pinctrl-sm8150.c PINGROUP(57/58) func2=qup19、vendor raphael-sm8150.dtsi goodix@5d（reset=54 irq=122 vdd=98 avdd=100 power-on-delay=300ms）—— 全部与 SWEET 驱动一致；板级触摸节点在 dtbo（基础 DTB 无触摸节点）
- 结论：嫌疑收敛物理层 —— ① avdd（GPIO100）上拉轨没真正起来（ios=0 但采自配置前，无证据力）② 总线被拖死。需要配置后电平证据
- 0091 补丁（a99dc24，CI run 39572579833 success，内核 c8fdc459）：冷上电循环（拉住 reset，98/100 双轨 off 100ms → on）；`bus idle`（vdd/avdd/sda/scl/reset/ios，复位拉住时）+ `bus live`（复位释放+300ms 后）两条判读行；TX 上限 3→6 + 双字 FIFO 打包；touch_stfts 拆写+读两条消息（burst 上限 10 事件保 nr≤90）；停止行带 ios 终值；往返 apply 自检通过
- t10 打包（scripts/t10_package.py）：t7 骨架 + 0091 内核 + t8 的 8 核 ADT（f50510e0，12588B，从 t8 镜像提取并解析验证 8 CPU 节点）；六重校验全过（ANDROID!v2/shim/DTB==t7/ADT 8 核/cmdline 330B==t7/markers/entry 0xfffffe000748b488）；clean e8cd3bc1… debug 4cc1e957…
- 8 核回归的安全性论证：t7（SWEET 编译）用同一个 8 核 ADT 正常启动 → ADT 的 8 核拓扑本身无害；t8 卡死根因 = kryo470 失配（0090 已入库）而非 CPU 数
- 发布 raphael-touch-r18（419348086）：t10 clean/debug + FLASH-T10.md + T10-SHA256SUMS；README 状态区/下载表/刷机指南全面更新；发行版现为 rootfs + r15/t7 + r17/t9 + r18/t10

Stage Summary:
- t9 两定性：触摸 0x5d 超时=总线零活动（软件全对→物理层）；卡=单核
- t10 一次刷机三信息：8 核回归成败 + 总线电平判读（idle/live 分离上拉轨 vs 引擎时钟两大理论）+ ST FTS 真探针
- 判读树：bus idle sda/scl=1 → 嫌疑转串行时钟（DFS/RCG）；=0 → avdd 供电轨问题；probe 0x5d err=0 → 触摸活
- 若 t10 卡 bootstrap → 8 核 ADT 是第二变量 → 退 t9，下轮 2/4 核折半

---
Task ID: 14
Agent: Super Z (main agent)
Task: t10 实测解读（触摸仍死 + 电池识别错误）→ 触摸根因定位（TLMM SOUTH tile）+ t11（0093 触摸根因 + 0092 电池）发布 + 发行版清理

Work Log:
- t10 日志解码（sweet-log.bin 4MiB，本次上传）：8/8 CPUs initialized（8 核回归成功，bootstrap 卡死与卡顿双双关闭）；`bus idle vdd=0 avdd=0 sda=0 scl=0 reset=0 ios=0` + `bus live sda=0 scl=0 irq=0 ios=0`（六个电平读数全零）；probe 0x5d err=60（TX 已发但总线无应答）；probe ST FTS 0x49 err=60（0091 的 5 字节修复生效，命令真的发出去了，同样超时）→ 两个地址完全一致的超时 = 总线物理层死
- 电池问题命中：`SWEET BATTERY: static fallback, 100% 4200mV external=1 charging=0` + boot-args `sweetbattery=0` —— 电池驱动从未开启，iOS 里恒定 100% 是写死的假数据，不是"识别错误"
- 触摸根因定位（0093，f5d231a）：SM8150 TLMM 不是平坦一块 —— GPIO 寄存器 = TLMM 基址 + tile 偏移 + 0x1000×编号（WEST 0x00100000 / EAST 0x00500000 / NORTH 0x00900000 / SOUTH 0x00D00000，pinctrl-sm8150.c 实锤）；触摸 6 GPIO（54/57/58/98/100/122）全在 SOUTH tile（PINGROUP 逐条验证；102-104=NORTH、105=WEST 交错排布，证实必须逐 GPIO 查表）→ 真窗口 = 0x03D00000；驱动从 0083 起映射 0x03000000（整个 TLMM 区开头 0x100000 的未实现空洞，读全零写无效）→ 触摸 IC 从未上电、SDA/SCL 从未复用到 qup19 —— 与 t10 全零判决行完美互证
- 上轮遗留问题修正：work/ 里遗留的 0093 补丁草稿是针对 pre-0091 树生成的（内含已入库的 0091 内容，直接用会冲突）→ 在 work/t11/0093base 重建 post-0091 基准（baseline 构建树 + 应用 in-repo 0091），从 work/xnu 工作树重新提取纯 diff；追加 `TLMM-south` 运行时正向标记（启动行 printing mapping GCC/TLMM-south/SE7），往返 apply 校验通过
- 0092 复核（fa957b0 已在上轮提交并 CI 成功）：PM8150B fg-gen4 QG（SPMI SID 2，peripheral 0x40）真实电压/电流/电量 + SMB5 充电器状态；SweetBattery IOLog 判读行 = `SWEET BATTERY: PM8150B QG / estimated SOC, XX% XXXXmV external=? charging=?`（真实）vs `static fallback`（假数据）
- t11 打包（scripts/t11_package.py 更新）：t7 骨架 + 0092+0093 内核（CI run 39582204279，内核 SHA 63dba04e…，二进制标记逐项验证：TLMM-south 在/旧串消/PM8150B QG 在/PM6150 消/kryo485 在）+ t8 8 核 ADT + cmdline sweetbattery=0→1；六重校验全过（ANDROID!v2/shim/DTB==t7/ADT 8 核/cmdline battery ON/markers 0090-0093/entry 谱系一致）；clean bd75bc2d… debug df4690b6…
- 发布 raphael-touch-r19（419415295）：t11 clean/debug + FLASH-T11.md + T11-SHA256SUMS；同时删除被取代的 r17/t9（单核）与 r18/t10（诊断使命完成）—— 发行版现为 rootfs + r15/t7 + r19/t11（落实用户"只保留 t7 和 ios16 + 当前版"指令）
- 文档：README 状态区（8 核实机确认/触摸根因/电池真相）、下载表（t11 推荐 + t7 回退）、刷机指南改指 t11、docs/FLASH-T11.md 入库；worklog 双写

Stage Summary:
- 本轮双根因：触摸 = TLMM SOUTH tile 基址错误（0083 起所有 GPIO 写入落空）；电池 = sweetbattery=0 静态假数据
- t11 一次刷机双判决：触摸看 `TLMM-south` 标记 + bus idle/live 电平 + probe 0x5d（err=0 即活）；电池看锁屏百分比（不再恒 100% 即活）+ `SWEET BATTERY: PM8150B QG / estimated SOC` 行
- 若触摸仍超时且 sda/scl=0 → GPIO 使能≠电源轨真起来，下轮查供电轨真身（RPMh/LDO 投票）；若 err=6/NACK → 总线活了但器件地址或 IC 异常
- 电池若仍 static fallback → 回报 SPMI 判读行（mapping failed / unsupported arb / timeout），下轮排查 SPMI arbiter 配置

---
Task ID: 15
Agent: Super Z (main agent)
Task: t11 实测解读（触摸总线已通但帧不动 + 电池仍 fallback）→ 爬透 raphael 逆向资源 → 0094 GT9886 配置下发 + 0095 电池 sid 修复 → t12 发布

Work Log:
- t11 日志解码（sweet-log.bin 4MiB）：8/8 CPUs（延续）；`mapping GCC/TLMM-south/SE7` 0093 生效；`bus idle vdd=0x3 avdd=0x3 sda=0x1 scl=0x1`（供电轨+总线全通）；`probe 0x5d ver-reg err=0`（IC 应答！32 字节真实读回）但 `probe raw 0x8240: 00 00 02 d2 ff ff f9 ad...` 非 ASCII；`selected GT9889` 后每次轮询 `report err=5 irq=0x40000001`（DONE+TX_WM、无 RX、无 NACK）；电池 `SPMI arb=0x50000000 APIDs=512` 但仍 `static fallback`（无 timeout 行 = 静默失败）
- 逆向研究（用户点名要求）：爬 LineageOS/android_kernel_xiaomi_sm8150（raphael 内核）—— drivers/input/touchscreen/xiaomi/goodix_driver_gt9886 全套（core/i2c/cfg_bin/gtx8_update）+ raphael-sm8150.dtsi 触摸节点 + firmware/goodix_gt9886_cfg_f11.bin.ihex（vendor 配置 blob 就在内核仓库）+ drivers/power/supply/qcom/qg-reg.h + pm8150b.dtsi + Linux 主线 spmi-pmic-arb.c + i2c-qcom-geni.c，全部下载到 work/ref/ 供后续轮次引用
- 触摸三大发现：① GT9886 "normandy" 寄存器图来自 cfg bin reg 表（vendor 直接使用）：pid@0x4535=ASCII "9886"、sensor-id@0x4541(mask 0x0f)、版本块@0x452c(72B 和零)、命令@0x6f68、配置窗口@0x6f78、**触摸帧@0x4100**（bit7=触摸事件、b[1]&15=点数、8字节点、整帧 4+8n 字节和为零、清帧=写 0）—— t8 以来读的 0x8240/0x824E 只是碰巧 ACK 的地址；② IC 每次开机必须下发 784 字节面板配置（0xff→0x80→0x82→写 784B→0x83→0xff 命令握手 + doze 0xAA/0xBB 协议），不下发就没有触摸帧；解析 vendor blob（ihex→bin→2×905B 包=const(56B)+reg表(65B)+784B 配置，双供应商 sensor0/sensor1，44 bag 校验全零）→ 生成 bsd/dev/gt9886_cfg.h 嵌入内核；③ t11 轮询全灭元凶 = 0x49 ST FTS 探针 NACK 后 TX FIFO 残留 5 字节投毒（每次后续传输先发陈旧字节→DONE 提前→sent!=nt→err=5，与 t11 日志完美互证）→ 探针删除 + touch_msg_run TX 改水位驱动流式写入（单条写上限 6→800 字节，配置写 786B 单条完成）
- 电池根因：SPMI 观察者命令对照 Linux pmic_arb_fmt_cmd_v2 = `opcode<<27 | sid<<20 | addr<<4 | len-1`，我们漏了 sid 位域 —— SWEET（PM6150=SID0）无害，raphael PM8150B=SID2（pm8150b.dtsi fg-batt-soc@4000 + 中断声明双重确认）每次都读错 PMIC → type!=0x0D → 静默 fallback；修复 + SweetBattery::start 加一次性 11 字段探针（type/sub/st1/st2/v/i/usb/path/chg/err/temp 逐字段带错误码）
- 0094 补丁（834b776）：GT9886 全套 bring-up（pid 校验非"9886"则带证据停止——固件更新路径未建；sensor-id 选配置；sensor0=x2x+y2y 翻转 per DT；doze 禁用后保持唤醒适配轮询模式；request 事件记一次+清帧）；0095 补丁（130937a）：sid 位域 + 探针；CI run 39588429883 一次通过，内核 78cbcaaf…，标记逐项验证（GT9886 新行全在/0x49 与 GT9889 旧串全消/两份 784B 配置字节级嵌入验证）
- t12 打包（scripts/t12_package.py）：t7 骨架 + 0094+0095 内核 + 8 核 ADT + cmdline 同 t11；六重校验 + 配置嵌入断言全过；clean 3725736f… debug 8dc5b5a9…
- 发布 raphael-touch-r20（419459117）+ 删除 r19 → 发行版现为 rootfs + r15/t7 + r20/t12；README 状态区/下载表/刷机指南/docs/FLASH-T12.md 全面更新；worklog 双写

Stage Summary:
- 本轮双根因均来自对 vendor 实现的忠实对照（不再猜测）：触摸 = 寄存器图错 + 缺配置下发 + 0x49 投毒三重叠加；电池 = SPMI 命令缺 sid 位域
- t12 判决：`GT9886 pid err=0 [39 38 38 36]` → 身份确认；`cfg send … err=0` → 配置入 IC 上手滑；`SWEET BATTERY: probe type=0/0xd` → 电池读通；方向不对回报 sensor id/flip 值
- 兜底：pid 非 9886 → 固件下发路径（gtx8_update.c 已在 work/ref 备好）；cfg send 卡 0x82 → 回报握手行；电池 probe 有 -1 → APID/observer 层问题（dump APID 表）

---
Task ID: 16
Agent: Super Z (main agent)
Task: t12 实测解读（触摸闭环 + 电池仍 fallback）→ fg-gen4 真根因 → 0096 电池重写 → t13 发布（含 CI 假内核事故修复）

Work Log:
- t12 日志解码：触摸判决行全绿（pid [39 38 38 36]=ASCII "9886"、sensor id=0x1、cfg send sensor1 784B err=0 → 用户确认触摸正常）；电池探针 `type=0/0xd sub=0/0x10 st1=0/0 st2=0/0xce v=0/0 i=0/0 usb=0/0x26 path=0/0x2 chg=0/0x47`（格式 err/值）→ sid 修复生效、读路径通，但 V/I 全零仍 fallback
- 真根因研究（fetch LineageOS sm8150 fg 全家桶到 work/ref/fg/：qpnp-fg-gen4.c 213KB + fg-util.c + fg-reg.h + smb5-reg.h + smb5-lib.h）：PM8150B 无 QG（那是 sm8250+），是 fg-gen4 双外设：fg-batt-soc@0x4000（monotonic SOC +0x09/+0x0A 影子、0-255、vendor 百分比公式）+ fg-batt-info@0x4100（SYS_BATT +0x07、VBATT +0xA0/+0xA6、IBATT +0xA2/+0xA8；换算 uV=raw×122070/1000、uA=sign16×488281/1000）；t12 的 `st2=0xce` 就是 SOC 206/255≈80%，数值一直都在被误读；0x4008=SLEEP_SHUTDOWN_STS 恒 0 → t12 "无电池"判定直接 fallback
- 0096 编写：SweetBattery raphael 段全面重写（影子校验读 fgReadShadowByte/Word、fgMonotonicPercent、SMB5 语义 external=USBIN_PLUGIN bit4、charging=状态机 1-4、full=TERMINATE、时间剩余估算、真低电警告/临界仅实测有效、百分比变化日志、publish 增加 timeRemaining 参数）+ sweet_spmi.c 白名单补 0x41
- CI 事故一（假内核）：v1 补丁在本地树（历史 Edit 工具 tab→空格污染）上生成，CI 规范树 tab 缩进 → `patch failed: SweetBattery.cpp:55` 被 dxb 静默跳过 → run 39593077146 绿灯但内核无 0096（靠 t13_package 的标记校验抓到）；修复：下载该 run 的 xnu-buildtree 作为规范基，脚本化重建（scripts/rebuild_0096.py，to_tabs 转换 + token 级等价校验 + 往返验证）
- CI 事故二（我方 YAML）：防呆闸步骤名含冒号破坏 YAML → run 39594849054 无 job 即败 + dispatch 422；修复：引号包名 + 防呆闸限定 NNNN-(raphael|sweet)- 模式（blacktop 上游补丁 TrustCache/skywalk_sonoma 等每次都良性跳过）
- CI 事故三（真编译错）：publish 声明带默认参数 `int timeRemaining = -1` 但定义漏列第 10 参数 → 函数体 timeRemaining 解析为基类 getter（IOPMPowerSource::timeRemaining）两个报错；修复：定义补全参数（v3）
- v3 构建（run 39596471069 SUCCESS，内核 c094d9ed…）14 项标记逐项验证全过；t13 打包六重校验全过（clean 3d31006c… / debug 8a5fe04f…）
- 发布 raphael-touch-r21（419516832，4 资产）+ 删 r20 → 发行版 = rootfs + t7 + t13；download/ 刷新为 t13 件；README 状态区/下载表/刷机指南/补丁链更新；NOTES.md 存档 fg-gen4 全套研究 + DRV8846 升降摄像头马达（TLMM 21/33/35/9/130 + PM8150L LPG ch1，ramp 1.6kHz/谐振 19.2kHz，差 pm8150l.dtsi 考证）+ 振动马达线索（leds-qpnp-vibrator-ldo，PM8150L）+ 流程教训

Stage Summary:
- 电池根因三连击闭环：0092 假数据 → 0095 sid → 0096 fg-gen4 真寄存器图（vendor 逐字节对齐）
- t13 判决：`probe type=0/0xd sys=0/0x0 msoc=0/0xXX,0xXX(NN%)`（两值相等=影子过）+ 锁屏不再恒 100% + 插线闪电 → 全胜；百分比冻结但电压动 → 下轮 fg-memif 电池 profile
- 工程加固：补丁必须对 CI buildtree 规范基生成；CI 对板级补丁跳过即红
- 彩蛋已备料：升降摄像头马达全协议在案（NOTES.md）

---
Task ID: 27
Agent: Z.ai (main)
Task: t13 重建版真机不亮屏 → 根因定位（v1 头打包错误）→ 用户已知良好 t12 接替 t7（r15）稳定发行版地位（r28）

Work Log:
- t13 重建版/ t19 双双黑屏的根因（镜像解剖三重对照）：用户正常 t12 与 t17 上传镜像均为 **boot header v2**（DTB 独立段，dtb_addr=0x1F00000），而我用 package-raphael.py 打包的 t19/t13 均为 **v1**（DTB 拼进 kernel 段）——diag 轮早已实证"v2 头 = 唯一被 ABL 接受的格式"（v1 下 shim 拿不到独立加载的 DTB，直接黑屏）。教训：打包工具必须与历史可用镜像同构，改打包链前先解剖已知良好样本。
- 用户 t12 上传件 sha256 3725736f… 与 r20 原版 release 资产逐字节一致；用户亦将该文件直接上传至仓库根（commit ee4d2d1）。
- "改成 8 核"经三重验证为无需修改：cmdline cpus=8 + ADT 8×kryo485 CPU 节点（cpu0-7）+ t11 真机日志 8/8 CPUs。对已知良好资产零改动 = 最大安全。
- r28 稳定版构建：clean = 用户 t12 逐字节拷贝（零改动）；debug = 仅 1 字节补丁（payload cmdline sweetfb_noconsole 1→0，v2 结构/shim/DTB/内核全不动），构建脚本断言：源哈希 == r20 记录、全文件恰 1 字节差异、payload 魔数与 t12 身份标记（GT9886/cfg send/DWC3 GSNPSID 在位；fg-gen4/SUSPHY cleared 不在）。
- 发布 raphael-touch-r28（Latest）：4 资产 api_size 与公网回读 sha256 全等（Task 20 纪律）；删除 r15 release+tag（t7 稳定位由 t12 接替）；发行版 = r28(t12 稳定) + r27(t19, 标注勿刷) + rootfs。
- README 双语更新：状态表降级 t14~t19 实验功能（显示缩放/亮度/息屏/充电轮询/SPMI 门/USB 全部标注已回退，稳定版不含；电池降为探针读通——fg-gen4 系 t13），下载表 t12 升为当前首刷推荐、t19 标注勿刷（v1 头）、t7 行移除，哈希块补 t12-debug 与勿刷标注。
- 注：t14~t19 各轮详情见 git 历史（0f84efc..1999311）；仓库树已回退至 t13 基线（a7a925e），稳定镜像为 t12 时代内核（补丁 0001-0095）。

Stage Summary:
- 稳定发行版 = r28/t12：8 核 + GT9886 触摸闭环 + 电池探针 + v2 头正确打包；clean 与当年实测可用文件逐字节一致
- v1 头黑屏根因已归档（t13 重建失败、t19 黑屏、乃至 t8 时代"v1 不被接受"三次事故同源）
- 后续若重启 USB 线：先用 v2 工具链（repack-boot-v2）重打包再谈内核功能

---
Task ID: 28
Agent: Z.ai (main)
Task: 用户指令"t12 不要加 USB 了" —— 冻结 t12 稳定线，禁止任何 USB 添加

Work Log:
- 核实 r28 双资产（clean/debug）cmdline 均 sweetusb=0：USB 探测/gadget 在 boot-arg 层面彻底关闭；内核中的基线 USB 代码（0072/0073/0087，0085 轮产物）保持休眠，与实测可用的原 t12 行为逐字节一致
- 文档扫描：FLASH-T12.md 仅废弃说明 + 电池探针 usb= 遥测字段（PMIC 充电类型，非 USB gadget）；README 无任何 USB 计划，USB 行已标 ⛔ 已废弃
- 决策记录：t12 稳定线（r28 及后续 t12 系资产）**永久不做 USB**——不启用 sweetusb、不打包 v2 USB 镜像实验、不在稳定资产上做任何 USB 变体；仓库树 0001-0096（含休眠 USB 基线补丁）保持不动（与稳定内核血缘一致，删除反而制造分叉）

Stage Summary:
- t12 稳定线冻结于无 USB 状态；任何未来 USB 尝试（如有）必须走独立实验分支，绝不触碰 r28 稳定资产

---
Task ID: 29
Agent: Z.ai (main)
Task: 用户指令"好了开始出t13" —— 从回退树（a7a925e，补丁 0001-0096）重建失传的 t13（fg-gen4 硬件电量计）镜像，v2 工具链正确打包

Work Log:
- 环境再次重置（GH_TOKEN 丢失、.git/config token 被 REDACTED）；仓库树仍在 e20ac84（= a7a925e 回退树 + 用户 t12 上传 + r28 文档），xnu/patches 99 文件（0001-0096 完整，0097-0104 已随回退移除）。
- 确认 CI 已替我们建好内核：xnu run #36（run id 39730368579，a7a925e，2026-10-22 06m16s success）产物 xnu-kernel（artifact id 12404184990，60MB，未过期，约 10-29 失效）；r21（原 t13）release 已删除只剩 tag，原版镜像/内核在公网不可恢复。
- 根因考古（t19_package.py 源码实锤）：v1 黑屏事故 = package-raphael.py 用 --header_version 1 且把 DTB 拼进 kernel 段；正确 v2 链 = mkpayload.py + mkbootimg.py --header_version 2（kernel=shim、ramdisk=payload、DTB 独立段 @0x1f00000、文件在 DTB 末端截断）。
- v2 工具链字节级证明（scripts/t13_prove_v2_toolchain.py）：从黄金 t12（3725736f…）抽取 shim/payload/DTB → mkbootimg（--base 0 --pagesize 4096 --cmdline 'console=null' --os_version 11.0.0 --os_patch_level 2021-10）+ 截断规则 → 复现 t12 除 20B id[] 记账字段（原管线对重打包前输入计算、ABL/shim 均不读，README-repack 有档）外逐字节一致；材料与 Task 27 的 t12-materials 三重交叉全等（shim 9fbe8fb8 / DTB 2a1ec87b / ADT f50510e0=12588B 8 核）。
- 标记判别集审计（scripts/t13_marker_audit.py，对照 t12 内核区(0095) 与本地 t19 内核(0104)）：'SWEET FB: AppleCLCD'/'QSCRATCH HS_PHY_CTRL'/'SWEET RPMH:'/'VBUS override'/'ACTIVE vote complete' 在 t12 休眠基线里早已存在，不是 t14+ 判别子；已剔除。终版：PRESENT = t12 身份（GT9886/cfg send/DWC3 GSNPSID）+ 0096 fg-gen4（PM8150B fg-gen4 / probe sys= / msoc=）三项；ABSENT = 0097-0104 每补丁至少一串共 17 项。
- 生产线就绪（scripts/t13_build.py）：mkpayload(t13 内核, t12 ADT, t12 cmdline 逐字) → mkbootimg + 截断 → debug=1 字节（sweetfb_noconsole 1→0）；六重校验（v2 头律/shim+DTB 逐字节/payload 魔数+cmdline/ADT 逐字节+内存几何/标记在场+缺席/sha256）。负向冒烟（t19 内核喂入）：机械链全过、标记门以全 17 项泄漏正确拒绝 —— 管线双向验证。
- 阻塞项：GH_TOKEN（拉 CI artifact、push、发 r29 均需）。fetch/release 脚本已备好（scripts/t13_fetch_kernel.py / scripts/t13_release.py，后者 make_latest=false 保 r28 稳定位）。

Stage Summary:
- t13 重建万事俱备：内核在 CI run 39730368579（未过期）、v2 打包链已字节级证明、构建/校验/发布脚本三件套就绪、t12 材料交叉验证一致
- 一旦 GH_TOKEN 到位：fetch → build（六重校验）→ 文档（FLASH-T13/README/WORKLOG）→ push → r29（make_latest=false）→ download/ 刷新
- 教训归档：mkpayload 非幂等（chained fixups 原地改写、payload 内核区不可回喂）；t14+ 判别标记必须双内核对照审计后使用

---
Task ID: 30
Agent: Z.ai (main)
Task: 用户送达 GH_TOKEN（"以后要保留凭据"）→ t13 重建流水线全程执行：fetch → build → 文档 → push → r29 发布 → download/ 刷新

Work Log:
- 凭据持久化：GH_TOKEN 写入 .env（.gitignore 补 .env 防泄漏）+ work/ios-raphael/.git/config remote URL；token 三重验证通过（api /user → Gsjsjzhznsz；repo 访问 200；fetch 后远程 main = 本地 = e20ac84 零漂移）。
- fetch（run 39730368579 / artifact 12404184990，60MB zip）：内核选型事故与修复——原"取最大 kernel.*"策略选中 .link/ 下 134MB ar 归档（kernel.development.raphael.a）而非顶层 17.2MB 真 Mach-O，t13_build 魔数断言正确拦截；t13_fetch_kernel.py 已改为 SHA256SUMS manifest 优先 + Mach-O 魔数（cf fa ed fe）校验 + 排除 .link/.dSYM/.a。内核 = kernel.development.raphael 17,206,304B，sha256 bd6ad8be…（与 CI manifest 全等；与原版 r21 内核 c094d9ed… 不同 = runner 工具链漂移，按预案以标记集判定，功能同一补丁集 0001-0096）。
- build（t13_build.py）：六重校验全过（v2 头律 / shim+DTB 逐字节=t12 / payload 魔数+cmdline / ADT 逐字节+内存几何 / 标记 t12 身份+0096 fg-gen4 全在场、0097-0104 全 17 项缺席 / sha256）；双镜像均 17,326,191B；debug 恰 1 字节 @0x33172（sweetfb_noconsole 1→0，与 t12 debug 同位）。clean = 82c71576…，debug = 4f1f5f65…。
- 文档：FLASH-T13.md 升级为 r29 版（重建说明块 + 原版判读树全保留；回退点 t7 → t12/r28；内核哈希行更新）；README 双语五处（状态表电池行 ×2、下载表 t13 两行 ×2、哈希块 t13-orig/r29 三行）；WORKLOG 补档 Task 28/29/30。
- 发布：raphael-touch-r29（make_latest=false，r28/t12 保持 Latest）；4 资产（clean/debug/FLASH-T13.md/T13-SHA256SUMS.txt）api_size + 公网回读 sha256 双通道全等（Task 20 纪律）。
- download/ 刷新为 t13 四件套（t12 四件套移除；t12 仍可从 r28 release 获取）。

Stage Summary:
- t13 以 r29 重回测试轮：功能与失传的原版完全同一补丁集（0001-0096），打包首次用字节级验证的 v2 链
- 凭据新常态：GH_TOKEN 常驻 .env + git config（.env 已进 .gitignore），后续会话免再索要
- 教训：CI artifact 内可能混有链接中间产物（.link/*.a 134MB > 真 Mach-O 17MB），选核必须走 manifest + 魔数双验证，"取最大"不可靠

---
Task ID: 31
Agent: Z.ai (main)
Task: 用户指令"好了把屏幕缩放搞一下" —— 重建 t14 时代被回退的整幅缩放（sweetscale），仅缩放子集，发布为 t20/r30

Work Log:
- 考古（a7a925e^ 树）：恢复 0097-raphael-battery-charging（不取）与 0098-raphael-display-scale-brightness（四合一：缩放/亮度 DCS/即时息屏/externalMethod 调参日志）+ FLASH-T14.md；实锤"历轮 USB 楔死都发生在 t14 功能用户态可见之前"——**缩放从未被肉眼验证，t20 是首次真机视觉测试**；t12 cmdline 无 sweetscale → 补丁默认 scale=1 即缩放开。
- 拆分（scripts/t20_make_patch.py）：规范基 = work/xnu 文件反向应用 0098（零 fuzz）→ 0001-0096 基线；KEEP 缩放 hunks（74 注释/104 成员/176 映射表构建/359 present 重构）+ presented-as 日志行（混合 hunk 197 切片）；hunk 359 捎带的 setPanelBrightness 函数块经"s->release() 尾段恢复"手术剔除；diff -u 生成新补丁 0097-raphael-display-sweetscale.patch（5 hunks，200 行），往返+纯度+排除指纹三重验证。纯度误报两例修正：`scalarInput[0]` 撞基线合法用法（改指纹 `(%llx %llx %llx %llx)`）；补丁生成中 diff 退出码 1 语义修正。
- CI 三折：push a7aed26（0097 补丁）→ dispatch 误杀在跑的 push run #37（并发组 cancel-in-progress）；dispatch #38/#39 两连死（runner 秒分配即取消、零步骤=池故障）；重派 #40 success（内核 7440577a…，run id 39761972114）。**"push 触发已死"被证伪**：`branches: [main]` 一直在文件里，"ain]" 是显示管道吞 "[m" 的 ANSI 伪影（od 实锤）；一次据错误认知的"修复"提交因 sed 空操作+git nothing-to-commit 被拦，未污染仓库。
- 判别标记定版：PRESENT = t12 身份 3 + 0096 fg-gen4 3 + `sweetscale`/` (scaled)`（对 r29 内核原始扫描验证纯净）；ABSENT 16 项（0097-charging + `SWEET FB: brightness`=拆分证明 + 0099-0104）。原始扫描 PASS；负向冒烟：r29 内核喂入 t20 管线被标记门正确拒绝（missing: sweetscale pair）——管线双向验证。
- 构建（t20_build.py，v2 链）：双镜像 17,326,191B；六重校验全过（v2 头/shim/DTB 逐字节=t12/payload 魔数+cmdline 与 t12 全等/ADT+几何/标记/sha256）；debug 恰 1 字节 @0x33172（与 t12/t13 debug 同位）。clean e32618b9… / debug 6c272111…。
- 文档：FLASH-T20.md（判读树 A 显示层全表：顶角完整=全胜、`(scaled)` 判决行、颗粒感=预期、Display Zoom 真实生效、撕裂回报；回退 t12/r28）；README 双语 7 锚点（显示行 ×2、t13 降上一轮 ×2、t20 双行 ×2、哈希块）；NOTES 存档（设计/拆分/判别/CI 教训）；本 WORKLOG。
- 发布：raphael-touch-r30（make_latest=false，r28 保持 Latest）；download/ 刷新为 t20 四件套。

Stage Summary:
- t20 = 0001-0096 + 0097-sweetscale；功能首次上真机，判决 = 锁屏顶角时间/电量完整 + 启动行 `(scaled)` + Display Zoom 有视觉变化
- 教训双档：①CI"沉默跳过"防闸继续救命（本轮是 runner 池故障三连，第 4 次尝试通过）；②终端显示会吞 "[m"（ANSI 伪影），字节级判断必须 od -c，勿凭 grep/cat 改工作流
