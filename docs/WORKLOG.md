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
Task ID: 17
Agent: Super Z (main agent)
Task: t13 实测解读（充电状态未识别 + 屏幕缩放/边被挡 + 息屏渐慢 + USB 不可连）→ 逆向研究（EA8076 面板 / DSI 6G v2.2 / SMB5 输入路径 / ios-topaz）→ 0097+0098 → t14/r22 发布 + README 双语重写

Work Log:
- t13 日志判读：电池读数全真（msoc 0xc2=76% 影子校验过、v=4065mV、i=-387mA 放电、probe 全字段 err=0）；`usb=0x26`=UV|VASHDN 无 VBUS（采样时未插线）；充电检测存在**日志盲点**——0096 只在百分比变化时打日志，插拔事件从不落盘；`swap layer 0 surface 1125x2436` 实锤 iOS 全画布渲染 + present() 居中裁剪（fOffX=22/fOffY=48）= 顶部两角被切的根因；`sweetusb=0` 从 t7 继承，CDC-ECM gadget（0073-0077）从未启用
- 逆向研究（本轮新证据全部入库 NOTES.md）：raphael 面板 = **samsung EA8076**（MiCode raphael-p-oss dsi-panel-samsung-fhd-ea8076-*-cmd.dtsi，DSI command 模式、亮度=DCS 0x51 大端 11-bit max 2047、息屏=0x28/0x10、APSD/AOR/ACL 表全量）；DSI 6G v2.2 命令发送三件套（嵌入式包格式 [WC_lo WC_hi data_id flags+payload]、TPG FIFO 路径寄存器 0x15c/0x17c/0x1ec、INT_CTRL 0x110 BIT0 轮询完成）——注意该内核 packet header 顺序是 WC 在前（非主线顺序）；SMB5 输入路径寄存器图（APSD_RESULT 0x1308 单比特类型、ICL 0x1107、POWER_PATH 0x110b、STATUS5 0x100b）；ios-topaz 研究 = dipa-studio/ios-sweet 的 SM6225 兄弟 fork，xnu 补丁同源 0001-0079 无增量，其 shim boot-v4/rootfs 工具暂无可移植项，上游 ios-sweet 新增仅 0080/0081（我们已有）
- 0097（电池充电状态）：5 秒快轮询（USBIN_RT_STS+CHGR_STATUS1 两读，变化即全量 poll）+ 输入切换日志（plugin/APSD 类型名/ICL/POWER_PATH/STATUS5/充电状态机名一行全落）+ probe 行补四个寄存器 + APSD/状态名辅助函数
- 0098（显示）：最近邻缩放表（fColMap/fRowMap，中心对齐）替代裁剪（`sweetscale=0` 回退）；DSI DCS 亮度通道（fbDsiSend：TPG FIFO 嵌入式 LP 命令，0x51 ss 大端，超时即自禁用）；即时息屏（RequestPowerChange(0) 一次清屏 + DCS 0x28，唤醒 0x29+恢复亮度，`sweetfb_fade=1` 回退渐暗）；setProperties("brightness") 钩子；未实现 selector 带参数值落日志（下一轮定位 iOS 滑条入口）
- **流程事故预防**：Edit 工具再次把整文件 tab→空格（比 t13 事故范围更大）；改用 scripts/apply_t14_battery.py / apply_t14_display.py 字节级锚定替换（显式 \t、每处替换断言唯一命中、往返校验 git checkout→apply→diff 全等），补丁 0097（214 行）/0098（476 行）从规范基干净生成
- USB：`sweetusb=2` 进 t14 cmdline（raphael 构建下 gadget 全编译，QSCRATCH 0x0a6f8800 与主线 sm8150 usb@a6f8800 一致、GCC 时钟表 0087 已验证、probe 调用点在 UFS root 初始化尾部不阻塞启动）；文档化 tools/sweet-usbnet.sh 用法
- CI run 39606221999 一次通过（5e53979），内核 9b73a8f1…；t14 打包六重校验全过（ANDROID!v2 / shim/DTB==t7 / ADT 8 核 12588B / cmdline 330B 含 sweetusb=2+sweetbattery=1 / 0090-0098 标记全在含 input plugin 行、(scaled)、brightness、display off (instant)、USB gadget 行 / cfg s0/s1 嵌入）；clean 3374ac69… / debug 51cb98e3…
- 发布 r22（4 资产：clean/debug/FLASH-T14.md/T14-SHA256SUMS.txt）+ 删 r21 → 发行版 = rootfs + t7(r15) + r22；README 全面重写（双语恢复 + 用户提供的完整刷机指南〇-四 + 救砖/回退附录 + 状态表 + 历史哈希）；NOTES.md 存档 EA8076/DSI/SMB5/topaz 研究 + 本轮流程教训

Stage Summary:
- 四项用户诉求全部给出修复或通道：缩放（裁剪→整幅缩放）、息屏（7 步渐暗→即时全黑+DCS 0x28）、亮度（首次打通 DSI DCS 通道，iOS 滑条入口下一轮凭带值 selector 日志定位）、充电状态（5s 响应+全输入路径落盘）；USB（sweetusb=2 网卡+实时日志）
- t14 判决树（FLASH-T14.md）：A 显示（时间/电量完整=缩放胜）、B 息屏/亮度（立即黑=胜；拖滑条后回报带值 selector 日志）、C 充电（插线 ≤5s 闪电=胜；plugin=1 但 DISABLE → 回报完整行，下一步查充电禁用写通道）、D USB（枚举+ping 通=胜）
- 兜底：`sweetscale=0`/`sweetfb_fade=1`/`sweetusb=1` 全部可回退；t13/t7 可随时引导

---
Task ID: 18
Agent: Super Z (main agent)
Task: t14 实测解读（USB 软复位后整机冻结 + 二次启动普查卡死）→ DWC_usb31 根因定位 → 0099/0100 → t15/r23 发布

Work Log:
- 用户回报 t14 现场（屏幕控制台）：`ue0 192.168.7.2/24 up (err 0)` → `soft reset done after 1 ms, GCTL 0x00112001 DCFG 0x00480000` 后再无输出、整机冻结重启；第二次 fastboot boot 后按键普查打印到 aplid=297（PM8150B GPIO）停住
- 排除法定位（全部读源码实证）：sweet_keys/sweet_touch/sweet_usb_probe 在同一 UFS 初始化线程顺序执行；IOWatchdog 是"接受签到从不触发"的桩；XNU delay()=微秒 → DEPCMD 超时打印毫秒级就会出，没出 = 总线级挂死而非命令超时；sweet_spmi_read 与普查用不相交 APID 通道
- 决定性证据（拉取上游 ios-sweet NOTES.md + Linux 主线 dwc3/core.c）：
  1) 上游 sweet 真机验证 USB 的控制器是**经典 DWC3 v3.20a**（GSNPSID 0x5533320a，NOTES 原文），0073/0074 在该 IP 上全链跑通；raphael 实测 GSNPSID=0x33313130，Linux `dwc3_core_is_valid()` 按 0x3331xxxx 分类为 **DWC_usb31（USB 3.1 IP，版本号在 VER_NUMBER 寄存器）**
  2) Linux `dwc3_core_soft_reset()` 对 DWC31 的专门规则：CSFTRST 清除后设备/端点时钟域要重新同步，≤1.80a 必须再等 ≥50ms 才能访问 PHY/端点域（SM8150=2018 早期 DWC31）；t14 代码复位后 ~1ms 就发 ep0 DEPCMD → 挂死（config-NoC 全核共享 → 整机冻结）
  3) 普查卡死定性：按键线程(20ms)/普查/电池 5s 轮询三个观察命令源无互斥，而 Linux 对整个 pmic-arbiter 一把锁串行；崩溃后 PMIC 坏状态跨热重启保留 → 二次启动普查"假死机"
- 0099-raphael-usb-dwc31-sync.patch：QSCRATCH VBUS 强制提前到软复位前（Linux dwc3-qcom probe 顺序，wrapper 寄存器不受核复位影响）+ 软复位后 100ms 时钟域同步等待（Linux 50ms 要求×2）+ 每阶段面包屑日志（ue0/QSCRATCH/VBUS/软复位/settle/事件缓冲/ep0 命令/setup TRB/running）——再挂死拍照即定位
- 0100-raphael-spmi-cmdgate-census.patch：sweet_spmi.c 新增全局命令门 sweet_spmi_cmdgate()（keys_read 与 sweet_spmi_read 的观察事务全程持门，Linux 式单锁串行）+ GPIO 普查改 sweetcensus=1 可选（默认跳过并打 census skipped 行，诊断使命已完成）
- 工程流程：work/xnu 重建 t14 规范基（0096 快照+0097+0098，git apply --reverse 验证一致后提交）；apply_t15.py 字节级替换（无缩进漂移）；往返 apply 校验通过；cf75018 push → CI run 39613027135 success（红闸门通过）
- 内核 9640a81c…（15 项标记验证全过：DWC31 settle/settle 面包屑/census skipped/sweetcensus + t13/t14 血统标记 + kryo470 已消）；t15 六重校验全过（ANDROID!v2/shim==t7/DTB==t7/ADT 8 核 12588B/cmdline 330B/entry 0xfffffe000748f488）
- 发布 r23（t15 clean c3abc77e… / debug a4e7f776… + FLASH-T15.md + T15-SHA256SUMS.txt）+ 删 r22；发行版 = rootfs + t7 + r23
- README（中英双语状态区/下载表/引导注意事项：崩溃后先彻底关机再 fastboot）+ NOTES.md 存档 DWC31 差异与 Linux 依据 + FLASH-T15 入库

Stage Summary:
- 双根因闭环：USB 挂死 = DWC_usb31 与经典 DWC3 的复位后同步差异（Linux 依据原文级对齐）；普查卡死 = SPMI 观察命令无全局串行 + 崩溃后 PMIC 跨热重启状态残留
- t15 判决树：面包屑走到 running + 主机枚举 + ping 192.168.7.2 = USB 全胜；停在哪条面包屑之后 = 该步寄存器操作挂死（拍照即可定位）；t14 的显示/息屏/亮度/充电功能随 t15 首测
- 运维规则确立：任何崩溃后先长按电源彻底关机，再进 fastboot（清 PMIC 跨重启状态）

---
Task ID: 19
Agent: Super Z (main agent)
Task: t15 实测解读（USB 面包屑全过后整机冻结+自动重启）→ 环绕控制台取证定位死点 → SUSPHY 根因 → 0101 修复 → t16/r24 发布

Work Log:
- 证据：用户 22:26 回传定格照片（t15，发布后 10 分钟内刷机实测）；upload/sweet-log.bin 与 21:36 截图经时间戳+内容指纹（76%/4065mV/-387mA、census apld=297）确认为上轮 t13/t14 遗留证据，非本轮
- VLM 逐行 OCR 照片：0099 面包屑全过（VBUS override 0x10100000 → soft reset 1ms → settle → 事件缓冲 0x1047dc000 → ep0 DEPSTARTCFG 打印）→ 定格；底部"进度条"经像素级分析证伪（= QSCRATCH 换行残影，全图无 UI 元素）
- 取证方法突破：fbcon 是环绕式控制台（pe_serial.c fbcon_row=(fbcon_row+1)%fbcon_rows，73 行×67 列，FBCON_SCALE=2；QSCRATCH 行恰 67 字符换行指纹互证）→ 屏幕顶部=最新圈层、底部 lap 接缝 → 照片布局证明控制台死在 ud_epcmd 内部（无 timeout/status/"TRB armed" 打印 = DEPCMD 读总线级挂死，非命令超时）
- 日志环盲区确认：sweet_log_append 只挂 _cnputs（printf 路径），kprintf（Skywalk/DLIL/netagent/bsd_autoconf 自检行）直上屏幕不进环 → 环行号≠屏幕行号，环不能用于重建屏幕布局
- 根因（对照 Linux 主线源码）：t15 probe 读到 GUSB2PHYCFG 0x00100240，bit6 SUSPHY=1 = ABL 留下的 PHY 挂起态；Linux dwc3_hs_phy_setup() 显式注释"Ensure SUSPHY is cleared prior to phy init"，完整顺序= phy_setup(SUSPHY 清)→phy_init→CSFTRST→phy_power_on→事件缓冲→gadget/DEPCMD；DWC31 上端点寄存器块（0xc800）被挂起 PHY 时钟门控 → 第一条 DEPCMD 访问挂 AXI → config-NoC 全核共享 → 整机冻结；经典 DWC3（SM7150，0x5533320a）无此门控故上游从未暴露；t14 卡点同源（当时无面包屑误判为复位 settle 问题，0099 治标未治本）
- "自动重启"定性：XNU 侧无看门狗（SweetWatchdog=空壳），复位来自硬件侧路径（RPM/TZ/NoC 错误升级），挂死修掉即消失；若复发需掐表"定格→重启"秒数做指纹（固定=看门狗/可变=错误升级），NOTES 存档为 open question
- 0101 补丁（29 行纯新增，字节级脚本 scripts/apply_0101_susphy.py 生成——MultiEdit 再次把 tab 写成空格，Task 16 规矩生效）：清 GUSB2PHYCFG.SUSPHY（软复位前，+10ms 恢复，保持清零）+ DEPCMD(0) 纯读金丝雀（复发时屏幕自分类：卡 canary=仍被门控→下轮 QUSB2 PHY 完整重初始化；过 canary 卡 DEPSTARTCFG=命令语义→下轮对齐 Linux gadget start 全序列）；往返校验干净应用
- 参照缓存：Linux dwc3（gadget/core/ep0/core.h）+ phy-qcom-qusb2.c + dwc3-qcom.c 入 work/ref/dwc3/（googlesource 拉取，GitHub raw 被限流）
- CI run 39623374559（eba5c47）SUCCESS，内核 ea39593f…；t16 打包六重校验全过（ANDROID!v2/shim/DTB==t7/ADT 8 核 12588B/cmdline 330B==t15/markers 0090-0101 含 SUSPHY+canary/cfg 嵌入/entry 0xfffffe000748f488 谱系一致）；clean 30a978e1… / debug 3584be8e…
- 发布 r24（419713034）：t16 clean/debug + FLASH-T16 + T16-SHA256SUMS；删 r23；发行版=rootfs + t7(r15) + r24
- README 双语状态区/下载表/刷机指南/SHA 全面刷新；NOTES 存档四条（SUSPHY 事实/环绕控制台取证法/kprintf 日志盲区/自动重启 open question）

Stage Summary:
- t15 定性：USB 楔死定位到第一条端点命令的寄存器读（总线级），根因=PHY 挂起时钟门控，0099 settle 属治标
- t16 判决：SUSPHY cleared → canary → ep0 armed → running(DSTS) → 锁屏 → 主机枚举 ECM + ping 192.168.7.2 = USB 全胜；判读树与两级兜底路径就绪
- 证据链方法沉淀：环绕控制台几何、照片像素级证伪、环日志 kprintf 盲区——后续轮次取证基建

---
Task ID: 20
Agent: Super Z (main agent)
Task: 用户报告"t16 发行版文件异常" → r24 资产修复

Work Log:
- 现象确认（GitHub API）：r24 全部 4 个资产为 46-56 字节（应为 17,342,575 / 17,342,575 / 5,527 / 283），下载计数全 0（无人中招）
- 根因（下载坏资产取证 + 对照 release_r24.py）：资产内容 = 本地文件路径字符串本身——curl `--data-binary` 缺 `@` 前缀，把路径文本当请求体上传；API 返回 state=uploaded，脚本仅校验 state 故静默放行；r22 脚本用 `@{path}` 正确，属 r24 脚本笔误
- 修复（scripts/fix_r24_assets.py）：预检本地哈希（与 T16-SHA256SUMS 逐字节一致）→ 删除 4 个坏资产 → `--data-binary @file` 重传 → API 响应 size 字段与本地尺寸逐一相等
- 验证双通道：资产 API 端点（按 id，Accept: octet-stream）回读 4 文件 sha256 与本地全等；浏览器下载 URL 初测两个文本文件仍返回 CDN 缓存的旧坏对象 → 75 秒后复测全部刷新为正确内容（镜像哈希 30a978e1…/3584be8e…，ANDROID! 魔数正确）
- 预防：release_r24.py 两处 `--data-binary` 补 `@` + 注释（防模板继承）；NOTES.md 存档三条规则（@ 必须、size 必校验、CDN 陈旧缓存与资产 API 端点验证法）

Stage Summary:
- r24 发行版完全修复：4 资产正确在位，公开 URL 可下载，哈希与 README/T16-SHA256SUMS 一致
- 用户可直接 fastboot boot raphael-t16-susphy-clean.img（或 debug 版）继续 t16 判读树（SUSPHY cleared → canary → ep0 armed → running → 锁屏 → 主机枚举 ECM + ping 192.168.7.2）
- 流程防线：发布脚本上传后必须校验 size 字段；CDN 缓存陈旧用资产 API 端点辨别
---
Task ID: 21
Agent: Super Z (main agent)
Task: t16 实测解读（ue0 up 后首条端点命令写楔死 + 40s 硬件侧重启）→ K20 Pro 逆向项目研究（用户点名）→ 0102 femto PHY 完整启动 → t17/r25 发布

Work Log:
- t16 照片环绕控制台解码（指针恰在环绕点，72 行完美时序窗口重建）：probe 头（GDSC/时钟/GSNPSID/DCFG/GEVNT，DALEPENA=0xf=ABL 残留）→ ue0 attach/addr/up(err 0) → SUSPHY 0x00102400→0x00102400（冷启动本来就清）→ QSCRATCH HS/SS_PHY_CTRL=0x00000000（★全零=ABL 交接时 USB 块被重置）→ VBUS override 0x10100000/0x61000000 → 软复位 1ms → settle → 事件缓冲 → canary 0x00000000（★读通过）→ ep0 打印 → 楔死（无 timeout=总线级）；顶部 "^NRL_CFG 0x4" = QSCRATCH 行 GENERAL_CFG 的环绕尾巴
- 根因定级：端点命令状态机用 PHY 的 UTMI 时钟——canary 纯读走 AHB 无需该时钟，命令写要跨时钟域启动状态机 → PHY 断电（冷启动）/挂起（t15 热）都死 → ABL 残局永远不够，必须像 Linux 每次开机从头启动 PHY；40s 重启 = RPM/TZ/NoC 硬件侧升级（t13/t14 稳定运行从不重启=无全局看门狗，vendor 充电 wd-bark 16s 是另一子系统）
- 逆向研究（用户要求"搜寻 K20 Pro 逆向项目"）：**重大更正——sm8150 HS PHY = 7nm Synopsys femto（drivers/phy/qualcomm/phy-qcom-snps-femto-v2.c，compatible qcom,sm8150-usb-hs-phy），Task 19 的 qusb2-v2 参照是错代驱动**（代码搜索实证 compatible 只在 DTS，驱动匹配主 compatible）；旧 probe 尾打印读的 0x1a0/0x210/0x240 偏移在 femto 上不存在。howtocuddle/xiaomi_raphael（真实日用级 mainline Gentoo 6.18 项目）sm8150.dtsi 佐证：ref 时钟直取 RPMH_CXO + GCC_QUSB2PHY_PRIM_BCR 复位；pmOS raphael = 6.5 vendor fork 另一谱系
- 双 DTS 实锤 raphael USB = HS-only 单 PHY（vendor: maximum-speed="high-speed" + usb_nop_phy，QMP DP 禁用；mainline patchew: phys 只留 usb_1_hsphy）→ 无需 QMP USB3；vendor 板级调优 param-override-seq（OVERRIDE_X1=0x83/X2=0x2c，(value,offset) 序列，0x70/0x74 正是 femto OVERRIDE_X1/X2）
- femto 驱动全文研读（拉取到 work/ref/dwc3/phy-qcom-snps-femto-v2.c）：15 步序列（CFG0 CMN_OVERRIDE_EN → POR=1 → FSEL=000 → PLLBTUNE → REFCLK_SEL=10b → VBUSVLDEXTSEL0/VBUSVLDEXT0 → 板级覆盖 → VREGBYPASS → SUSPEND_N_SEL|SUSPEND_N → SLEEPM → SIDDQ=0 上电 → POR=0 释放 → SEL=0 → 覆盖关）+ GCC_QUSB2PHY_PRIM_BCR=0x12000 脉冲（gcc-sm8150.c 复核，时钟偏移全对）；Linux 顺序 phy_setup→phy_init→软复位（Linux 之后回设 SUSPHY=1 供 phy ops，我们保持 0=永 P0，轮询式不需要）
- 0102 补丁（scripts/apply_0102_hsphy.py 字节级锚定，无缩进漂移）：femto 全序列插在 SUSPHY 清除与 QSCRATCH 之间 + pre-state/up 两行诊断 + usb_phy_wr_mask 助手（写后读回）+ probe 尾打印改 femto 偏移；往返校验干净通过
- CI run 39630226729（2ec9adc）success，内核 243a5496…；二进制标记验证全过（hsphy pre-state/up/femto dump 在、QUSB2 PLL_STATUS/PORT_TUNE1 消）
- t17 打包六重校验全过（ANDROID!v2/shim/DTB==t7/ADT 8 核 12588B/cmdline 330B==t16/markers 0090-0102/cfg s0s1/entry 0xfffffe000748f488 谱系一致）；clean 80b148a3… / debug 2db77b0a…
- 发布 r25（419772788，4 资产 size+state 双校验全过）+ 删 r24 → 发行版 = rootfs + t7(r15) + r25(t17)；README 双语状态/下载表/哈希/刷机指南全面刷新；NOTES.md 存档六节（femto 更正/序列/HS-only/屏幕解码/RE 项目调查/LDO 兜底清单）；download/ 刷新 t17 五件套
- 沿用流程防线：发布脚本 @+size 双校验（r24 事故防复发）；补丁对规范基生成；fetch 脚本 SHA 匹配陷阱（HEAD 前移导致轮询空转）已用 run ID 直下绕过

Stage Summary:
- t16 死点精确到"端点命令写跨时钟域"级别，根因从"SUSPHY 位"升级为"PHY 从未被启动"；0102 是 Linux 序列的寄存器级移植
- t17 判决树（FLASH-T17.md）：ep0 TRB armed + running + 主机枚举 ECM + ping 通 = USB 全胜（40s 重启应消失）；卡 hsphy pre-state = PHY 供电轨（下轮 RPMh LDO）；过 hsphy up 仍卡 canary/ep0 = 时钟域（下轮全块 BCR + GCTL）
- 触摸/电池/显示等 t14 功能随 t17 一并首测（历轮 USB 楔死都发生在它们用户态可见之前，但内核路径已验证）
- 流程防线：发布脚本上传后必须校验 size 字段；CDN 缓存陈旧用资产 API 端点辨别

---
Task ID: 21
Agent: Super Z (main agent)
Task: t16 实测解读（ue0 up 后首条端点命令写楔死 + 40s 硬件侧重启）→ K20 Pro 逆向项目研究（用户点名）→ 0102 femto PHY 完整启动 → t17/r25 发布

Work Log:
- t16 照片环绕控制台解码（指针恰在环绕点，72 行完美时序窗口重建）：probe 头（GDSC/时钟/GSNPSID/DCFG/GEVNT，DALEPENA=0xf=ABL 残留）→ ue0 attach/addr/up(err 0) → SUSPHY 0x00102400→0x00102400（冷启动本来就清）→ QSCRATCH HS/SS_PHY_CTRL=0x00000000（★全零=ABL 交接时 USB 块被重置）→ VBUS override 0x10100000/0x61000000 → 软复位 1ms → settle → 事件缓冲 → canary 0x00000000（★读通过）→ ep0 打印 → 楔死（无 timeout=总线级）；顶部 "^NRL_CFG 0x4" = QSCRATCH 行 GENERAL_CFG 的环绕尾巴
- 根因定级：端点命令状态机用 PHY 的 UTMI 时钟——canary 纯读走 AHB 无需该时钟，命令写要跨时钟域启动状态机 → PHY 断电（冷启动）/挂起（t15 热）都死 → ABL 残局永远不够，必须像 Linux 每次开机从头启动 PHY；40s 重启 = RPM/TZ/NoC 硬件侧升级（t13/t14 稳定运行从不重启=无全局看门狗，vendor 充电 wd-bark 16s 是另一子系统）
- 逆向研究（用户要求"搜寻 K20 Pro 逆向项目"）：**重大更正——sm8150 HS PHY = 7nm Synopsys femto（drivers/phy/qualcomm/phy-qcom-snps-femto-v2.c，compatible qcom,sm8150-usb-hs-phy），Task 19 的 qusb2-v2 参照是错代驱动**（代码搜索实证 compatible 只在 DTS，驱动匹配主 compatible）；旧 probe 尾打印读的 0x1a0/0x210/0x240 偏移在 femto 上不存在。howtocuddle/xiaomi_raphael（真实日用级 mainline Gentoo 6.18 项目）sm8150.dtsi 佐证：ref 时钟直取 RPMH_CXO + GCC_QUSB2PHY_PRIM_BCR 复位；pmOS raphael = 6.5 vendor fork 另一谱系
- 双 DTS 实锤 raphael USB = HS-only 单 PHY（vendor: maximum-speed="high-speed" + usb_nop_phy，QMP DP 禁用；mainline patchew: phys 只留 usb_1_hsphy）→ 无需 QMP USB3；vendor 板级调优 param-override-seq（OVERRIDE_X1=0x83/X2=0x2c，(value,offset) 序列，0x70/0x74 正是 femto OVERRIDE_X1/X2）
- femto 驱动全文研读（拉取到 work/ref/dwc3/phy-qcom-snps-femto-v2.c）：15 步序列（CFG0 CMN_OVERRIDE_EN → POR=1 → FSEL=000 → PLLBTUNE → REFCLK_SEL=10b → VBUSVLDEXTSEL0/VBUSVLDEXT0 → 板级覆盖 → VREGBYPASS → SUSPEND_N_SEL|SUSPEND_N → SLEEPM → SIDDQ=0 上电 → POR=0 释放 → SEL=0 → 覆盖关）+ GCC_QUSB2PHY_PRIM_BCR=0x12000 脉冲（gcc-sm8150.c 复核，时钟偏移全对）；Linux 顺序 phy_setup→phy_init→软复位（Linux 之后回设 SUSPHY=1 供 phy ops，我们保持 0=永 P0，轮询式不需要）
- 0102 补丁（scripts/apply_0102_hsphy.py 字节级锚定，无缩进漂移）：femto 全序列插在 SUSPHY 清除与 QSCRATCH 之间 + pre-state/up 两行诊断 + usb_phy_wr_mask 助手（写后读回）+ probe 尾打印改 femto 偏移；往返校验干净通过
- CI run 39630226729（2ec9adc）success，内核 243a5496…；二进制标记验证全过（hsphy pre-state/up/femto dump 在、QUSB2 PLL_STATUS/PORT_TUNE1 消）
- t17 打包六重校验全过（ANDROID!v2/shim/DTB==t7/ADT 8 核 12588B/cmdline 330B==t16/markers 0090-0102/cfg s0s1/entry 0xfffffe000748f488 谱系一致）；clean 80b148a3… / debug 2db77b0a…
- 发布 r25（419772788，4 资产 size+state 双校验全过）+ 删 r24 → 发行版 = rootfs + t7(r15) + r25(t17)；README 双语状态/下载表/哈希/刷机指南全面刷新；NOTES.md 存档六节（femto 更正/序列/HS-only/屏幕解码/RE 项目调查/LDO 兜底清单）；download/ 刷新 t17 五件套
- 沿用流程防线：发布脚本 @+size 双校验（r24 事故防复发）；补丁对规范基生成；fetch 脚本 SHA 匹配陷阱（HEAD 前移导致轮询空转）已用 run ID 直下绕过

Stage Summary:
- t16 死点精确到"端点命令写跨时钟域"级别，根因从"SUSPHY 位"升级为"PHY 从未被启动"；0102 是 Linux 序列的寄存器级移植
- t17 判决树（FLASH-T17.md）：ep0 TRB armed + running + 主机枚举 ECM + ping 通 = USB 全胜（40s 重启应消失）；卡 hsphy pre-state = PHY 供电轨（下轮 RPMh LDO）；过 hsphy up 仍卡 canary/ep0 = 时钟域（下轮全块 BCR + GCTL）
- 触摸/电池/显示等 t14 功能随 t17 一并首测（历轮 USB 楔死都发生在它们用户态可见之前，但内核路径已验证）

---
Task ID: 22
Agent: Super Z (main agent)
Task: t17 实测解读（用户报告 ~45s 重启 + 询问是否临时关闭 USB）→ 三段裁剪 VLM 逐字转录 → 根因闭环到 PHY 模拟供电轨 → 0103 RPMh LDO 投票 → t18/r26 发布

Work Log:
- 用户反馈：问题依旧，~45s 重启，问"要不要先临时关闭 USB"。回答：**不关**——t17 照片证明 USB 栈 90% 活着（GDSC/8 时钟/GSNPSID/DCFG/GEVNT/QSCRATCH/VBUS/软复位/事件缓冲/canary 读全部通过），关 USB 会丢掉 ping 判据；t13/t14 已证不探测 USB 时系统无限稳定
- 取证升级：照片裁 3 段（0-40%/30-72%/62-100%）2x 放大灰度增强，逐段 VLM 逐字转录（vlm-t17-shot1/band1/band2/band3.json），72 行完整时序重建
- **几何发现**：屏幕同时含两次启动——行 1-13 是 boot A 尾巴（up→QSCRATCH→VBUS→复位→settle→事件→canary→ep0），行 14-72 是 boot B（SK/Skywalk/kainit/lo0/UFS/LOG/KEYS/TOUCH→GDSC→…→pre-state 戛然而止"…CTR"处+绿色光标）；45 秒复位是热复位、帧缓冲不清、early console 从最后非空行续写；"一行两次 pre-state"非双调用（全树只有 sweet_ufs_rootdev 一个调用点，且 su.ready 在 usb_probe 前置位）——是跨启动残留
- **Boot A 定性**：femto 序列跑完但 `hsphy up (femto)` 回读全是重复字节垃圾（COMMON1 0x3b3b3b3b / REFCLK 0x02020202 / CTRL2 0x00000606）= PHY 寄存器堆未供电、15 步写全部没粘住；ep0 命令写仍楔死 CPU（无 UTMI 时钟，同 t16 死点）；其余 CPU 继续启动；**~45s 复位时刻与 `SWEET TOUCH: starting in 45 s` 倒计时到期精确吻合**（t16 的"~40s"也是它）——触摸线程在残废系统上的 SE19/TLMM/I2C 总线活动触发 RPM/TZ 侧升级，重启是症状不是独立故障
- **Boot B 定性**：死得更早——pre-state printf 输出中途截断（"…CTR"）：C 语义下 4 个读实参先于调用求值完毕（文字已上屏即证明），CPU 是在控制台输出途中被异步总线错误打断
- **根因闭环**：Linux `qcom_snps_hsphy_init()` 第一行 = `regulator_bulk_enable(vdda-pll/vdda33/vdda18)`（先于时钟、BCR、寄存器序列）——0102 移植恰好漏了这步，其余寄存器序列全部正确
- 轨映射（mainline raphael patchew v2 DTS + 本地 work/ref 复核）：vdda33=vreg_l2a_3p1=**ldoa2@3072mV**、vdda-pll=vreg_l5a_0p875=**ldoa5@880mV**、vdda18=vreg_l12a_1p8=**ldoa12@1800mV**（全 PM8150/a 片，全 HPM）
- 复用审计：`sweet_rpmh.c`（SWEET 板 TCS 投票器）**本来就在 raphael 编译**（RAPHAEL 构建同时定义 ARM64_BOARD_CONFIG_SWEET）；vendor sm8150.dtsi 逐字证实 apps_rsc 几何全同（drv-id 2、ACTIVE 2/SLEEP 3/WAKE 3、RSC 0x18220000、TCS 0x18220d00、cmd-db 定位器 0x0c3f000c reg 8 字节）——TCS 纪律零改动
- 0103 补丁（scripts/apply_0103_rpmh_ldo.py，幂等+byte 锚定）：sweet_rpmh.c 守卫板感知化（raphael 三轨紧电压窗，SWEET 保留 ldoc11）+ 两处 L11C 打印泛化；sweet_usb.c 在 pre-state 与 BCR 之间插三票 + `hsphy post-LDO` 回读打印 + **投票失败干净中止**（读死 PHY 返回垃圾但可存活，ep0 写才楔死——失败模式从 45 秒重启循环变成稳定锁屏+拍照定位）；往返校验干净
- CI run 39638829687（b66adc3）success，内核 ea2b69ab…；t18 六重校验全过（ANDROID!v2/shim/DTB==t7/ADT 8 核 12588B/cmdline 330B==t17/markers 0090-0103 含 RPMH+post-LDO+ldoa 三轨、ldoc11 正确被预处理掉/entry 0xfffffe000748f488 谱系一致）；clean a16e1725… / debug 6f165dca…
- 发布 r26（419823957，4 资产 @+size 双校验 + 公开 URL 回读 sha 全等）+ 删 r25 → 发行版 = rootfs + t7(r15) + r26(t18)；README 双语状态/下载表/哈希/判读树/指南全面刷新；NOTES.md 存档（两启动屏幕几何课/垃圾回读判据/45s 触摸触发闭环/轨映射/0103 事实/投票失败分类法）；download/ 刷新 t18 五件套（清掉 t13/t14/t17 旧件）

Stage Summary:
- t17 案子破了 90%：死因不是寄存器序列（0102 全对）而是漏了 Linux 的第一步——PHY 三条模拟供电轨从未上电（重复字节垃圾回读是铁证）；45 秒重启 = 触摸倒计时触发，症状而已
- t18 判决树（FLASH-T18）：三票成功 + post-LDO 值离开垃圾 → up 回读正常 → ep0 TRB armed → running → 主机枚举 ECM + ping 通 = USB 全胜；票失败则干净中止锁屏，RPMH 打印自分类下一轮（命名/继承冲突/超时→SPMI 直写兜底）
- 方法沉淀：跨启动屏幕残留的识别法（顶行时序不可能属同一启动即断双启动）；printf 中途截断 = 异步异常打断而非实参读挂死

---
Task ID: 23
Agent: Super Z (main agent)
Task: t18 实测深度排查（用户报告 ~50s 重启 + 要求"深度搜索彻底排查"）→ 照片逐行取证 + 双路深度检索 + 全链路代码审计 → 根因定级与 t19 方案

Work Log:
- 照片逐字转录（scripts/t18_photo_bands.py 三段 + t18_photo_strips.py 三窄条，2-3x 灰度增强，VLM 逐行）：
  - 判读重大修正：屏幕不是"USB 全绿后重启"，而是环绕控制台一圈 lap 的切片——底部 22 行（clk dump/GSNPSID/DCFG/GEVNTADR/ifnet/fsw/NET/usb up/SUSPHY/pre-state 0x88888888）是 lap-1 残留（旧），顶部 46 行（votes/post-LDO/femto/QSCRATCH/VBUS/软复位/settle/事件缓冲/canary/ep0 print）是 lap-2（新）。全屏 = 同一次 probe，无二次启动、无二次 probe（sweet_ufs_rootdev 有 su.ready 守卫 + 单调用链，代码排除重入）
  - 死点不变：最后输出 = "ep0 DEPSTARTCFG/SETEPCONFIG/SETTRANSFRESOURCE"，其后两行纯空白（strip-mid 证实无 timeout/failed/TRB armed/running 行）→ 机器仍楔死在第一条 ep0 命令写（AXI 级，ud_epcmd 的 dwc_rd 本身挂死所以 1000 次有界循环救不了）；"running" 从未到达、RUN/STOP 从未置位 → 主机从未枚举过任何 USB 设备
  - 0103 的 LDO 投票"完成"但 PHY 寄存器堆仍没真正上电：post-LDO 读回 CTRL2 0x06060606、femto up 读回 COMMON1 0x3b3b3b3b / REFCLK 0x02020202 —— 全是"单字节复制×4"的半崩坏模式，且与 pre-state（0x88888888/0x66666666）不同 = 投票确实改变了 PHY 状态（轨在动），但寄存器堆供电仍不稳定
  - VLM 8→0 误读规律：所有 '8' 被读成 '0'（rsc 0x18220000→0x10220000、880mV→800mV、1800mV→1000mV、3072mV 无 8 不变）→ 日志实际值与代码完全一致（3072/880/1800 + 正确 RSC 地址），投票数值无错
- 代码审计：sweet_rpmh.c（RSC/TCS 地址 ✓ 0x18220000/0x18220d00、投票序列 电压+8→模式+0→使能+4 ✓、TCS 完成判定 ISSUED|COMPLETE ✓、与 sm7150 上游真机验证过的实现一致）；cmd-db 查址返回 ldoa2=0x40f00/ldoa5=0x40b00/ldoa12=0x42000 —— 非线性（+0x100 应为 0x41200/0x41900），存疑待 SPMI 实测裁决；femto 偏移逐一比对 phy-qcom-snps-femto-v2.c 全对；Linux 的 femto write_mask 是读-改-写 = 真机寄存器必须可干净读回 → 字节复制垃圾 = 供电真没到位，不是"本来就读不回"
- 深度检索 A（复位机制取证）：imem 0x146bf65c 由 Linux 重启路径写入且 ABL 每次开机清除 = 对意外复位无取证价值；权威分类器 = PM8150 PON 寄存器组（SPMI sid0 基址 0x800：PON_REASON1 GEN2 0xC0 / WARM_RESET_REASON1 0xC2 / POFF_REASON1 0xC5 / OFF_REASON 0xC7 / FAULT_REASON1/2 0xC8-0xC9 / S3_RESET_REASON 0xCA / SOFT_RB_SPARE 0x8F，分类矩阵：PS_HOLD/SOFT=EL3 软复位、PMIC_WD=PMIC 看门狗、FAULT_*=PBS/热/UVLO、S3_*=硬复位链）；APSS 看门狗（0x17c10000，bark 11s）由内核驱动而非 ABL 使能 = 与 t13/t14 稳定运行互证排除；TZ 侧复位指纹 = POFF PS_HOLD/SOFT + imem 0x65c==0；DRAM 温复位保内容 → 心跳页取证法可行；标定手段 = XNU 直写 0x0C264000 PS_HOLD 制造已知类别复位
- 深度检索 B（USB 主机侧）：Android 主机息屏→系统 suspend→root hub 停发 SOF→几毫秒内设备自动进 L2（global suspend，hub.c 原文）；30s 息屏+Doze ≈ 40-50s 窗口 = USB 真正跑通后的下一颗雷，届时需轮询 DSTS.USBLNKST + L2 期间禁发 Start Transfer；高通主线 sm8150.dtsi 对两个 dwc3 永久禁用 SUSPHY/ENBLSLPM/U1/U2（dis_u2_susphy_quirk 等，与我们"SUSPHY 永清零"一致，官方背书）；GUSB3PIPECTL.SUSPHY（bit17）置 1 时寄存器写失败→SMMU fault→整机崩溃（commit 9bdbd5286ea5，高通实测一年无副作用）= 我们未清的遗留嫌疑位；DEPCMD 前 ENBLSLPM+SUSPHY 必清（DWC31 编程指南 3.2.2）；L1 由 BOS LPM 位+DCFG.LPM_CAP 双重门控，我们天然免疫；cdc_ether 支持 autosuspend 但需 remote-wakeup 配合
- 根因链定级（与 40→45→50s 漂移吻合）：probe 每轮变长（0102 femto +0103 投票）→ ep0 楔死点后移；楔死后 45s 触摸线程倒计时到期在残废系统上触发 RPM/TZ 升级 → 温复位。重启仍是症状，不是独立故障；UTMI 时钟缺失的元凶从"SUSPHY 位"→"PHY 未上电"→本轮收敛到"LDO 投票未真正落到轨"（或 cmd-db 地址错、或缺 settle 延时——PMIC5 LDO 电压阶跃用 stepper 爬升可达数 ms，我们的 post-LDO 读回恰在爬升窗口）
- t19 方案（0104）：① 开机读 PON/WDT0/imem/TCSR 打印"SWEET RST:"行分类上次复位；② 三票后 +20ms settle 再读 femto，若仍是单字节复制垃圾 → 干净中止（不进 ep0，锁屏存活拍照定位，彻底终结 50s 重启循环）；③ SPMI 读 LDOA2/A5/A12 实际电压状态寄存器裁决 cmd-db 地址疑点；④ 清 GUSB3PIPECTL.SUSPHY（高通 sm8150 实锤位）；⑤ sweettouchdelay= 调节旋钮做 45s 相关性 A/B
- 证据请求（零构建）：t18 sweet-log.bin（OrangeFox tail -c 4198400）；掐表"屏幕定格时刻 vs 重启时刻"差值（若恒 ≈35-40s = 触摸升级链实锤）；主机侧确认枚举从未发生

Stage Summary:
- t18 破案：表面"50s 重启"之下，USB 链路仍死在 t16 同一点（第一条 ep0 命令写楔死）；0103 投票完成了 TCS 握手但 PHY 寄存器堆仍半崩坏（字节复制读回），轨没有真正上稳
- 双路深度检索产出三条硬资产：PON 复位分类矩阵（0104 取证）、GUSB3PIPECTL.SUSPHY 嫌疑位、Android 主机 L2 息屏挂起时序（USB 跑通后的下一防线）
- t19 = 取证 + 自保 + 裁决三合一：复位原因打印、垃圾读中止、SPMI 轨实测；sweet-log.bin 是当前最缺的一块拼图

---
Task ID: 24
Agent: Super Z (main agent)
Task: 用户指令"深度搜索源码，深度研究"+ t18 死亡屏幕照片 → 源码级深挖 + 官方源裁决 → t19/0104 三项硬件级修复

Work Log:
- 会话恢复: 用户提供的分享页(agent-browser 渲染抓取全文) + GitHub token → 找回 Gsjsjzhznsz/ios-raphael 仓库并克隆; 本地重建规范基线树(xnu-8796.141.3 + staging×3 + 0001-0103, scripts/rebuild-baseline.sh)
- VLM 五带逐行转录 IMG_20261022_010547.jpg(t18 死亡屏幕) + 逐行对照 sweet_usb.c 打印序: 照片 = 同一次启动、同一次 probe 的完整环绕一圈(50行×67列), 光标冻在 ep0 print, 其后两行空白; Task 23 的"双启动残留"判读被推翻
- 控制台几何定案(读了 pe_serial.c fbcon 实现, 0003 补丁以来未变): 环绕式 + 行后留空 + 每次开机清屏 → 照片内容永远来自单次启动
- t16_screen.jpg 重转录: ep0 print 后系统继续跑完 DLIL/Skywalk/UFS/KEYS/TOUCH-45s → 只有 CPU0 楔死在第一条 ud_epcmd 写(store/dsb 永不完成); 45 秒触摸线程撞毒化 NoC → RPM/TZ 热复位 = 40-50s"重启"完整因果链闭合
- cmd-db 解析器审计(对照 Linux cmd-db.c 逐字节): rh_lookup 完全正确, 非线性 VRM 地址是固件真值 → "投错轨"嫌疑排除
- 官方源裁决链: realme X2 Pro(sm8150) vendor USB dtsi + Xiaomi raphael-p-oss 板级链(raphael-sm8150.dtsi → xiaomi-sm8150-common → sm8150-usb.dtsi) → 硅片 = femto v2, 供电轨 = pm8150_l5/l12/l2@880/1800/3072(0103 投票对象全对), sdmmagpie-usb.dtsi 的 qusb2phy-v2 是死代码; 主线 femto 驱动与 vendor 驱动逐行一致, 0102 移植无误
- 真死因×3 定位: ①字节复制×4 读值(REFCLK 写 0x2 读回 0x02020202) = AHB2PHY 桥降级特征, raphael 官方 GCC 有 gcc_usb_phy_cfg_ahb2phy_clk@0x6a004 ②QUSB2PHY_PRIM_BCR 真偏移 0x26000(raphael 官方) vs 主线错值 0x12000, 两表其余复位全一致唯此项不同, t17/t18 一直在脉冲不存在的寄存器 ③GUSB3PIPECTL.SUSPHY(0xc2c0 bit17)从未清除(Qualcomm 9bdbd5286ea5, t16 无 femto 也楔死吻合)
- 0104 补丁(apply_0104_usb_ahb2phy_bcr.py, byte 锚定×8 全过 + 往返校验干净): ahb2phy 桥使能 + 双 BCR 脉冲 + GUSB3PIPECTL 清除 + 20ms settle + 降级中止(终结 45s 重启循环) + SWEET RST: PON 复位分类器(SPMI 只读, sid0 periph 0x8)
- 提交 a312db4 推送, CI run 39701306108 构建中; t19-materials 从 t17 上传镜像提取(shim/DTB/ADT/cmdline, shim 自 r25 未变), scripts/t19_package.py 后台轮询打包+六重校验
- 文档: FLASH-T19.md(判读树) / NOTES.md 追加 t18 verdict CORRECTED 全证据链

Stage Summary:
- t19 修复集: 三项硬件死因(桥时钟/BCR 偏移/U3 SUSPHY) + 防护(降级中止) + 取证(PON 分类器); 任何失败模式从"45 秒重启循环"变为"稳定锁屏+照片"
- 判读树决胜行: ahb2phy CBCR (on) → pre-state 非重复字节 → hsphy up (femto) 回读正常 → ep0 TRB armed → running → 枚举 + ping 192.168.7.2
- 证据资产: t19-bands 五带转录 / t16-bands 重转录 / ref-raphael-{gcc,usb,board,sm8150-usb} 官方源存档 / ref-vendor-{gcc,femto,usb} / ref-femto-v2.c 主线驱动
