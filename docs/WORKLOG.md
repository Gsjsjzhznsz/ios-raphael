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
