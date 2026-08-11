# BUG 跟踪记录

本文件只用于提交、处理和关闭项目 BUG，不用于存放开发规范、需求或功能计划。

当前状态唯一索引：`docs/product/当前开发状态.md`。本文件各条目的首个“状态”行须与索引一致；其后测试、退回和复测状态均为历史证据。

## 状态流转

`待处理` → `修复中` → `待测试` → `待稽查` → `已关闭`

### BUG-20260812-064：新增Stage登记门禁未覆盖启动恢复与业务投影

- 状态：已关闭（最终只读稽查通过）
- 关联任务：M9.198 / 架构v2.2阶段登记门禁，不扩展处理用户并行前端改动或BUG057设备阻塞。
- 正式复现：现有`test_frontend_and_pipeline_use_one_canonical_stage_contract`只核对pipeline、前端类型和前端流程顺序；启动恢复器`_recover_production_workflows.stage_storage`仅登记outline/script/storyboard/assets/image/video/composition/review_export，缺requirements/audio/subtitle，也没有独立的项目存储投影/继续入口完整集合供CI与11阶段做相等性校验。
- 首个事实：当前CI证明“阶段名出现在三个文件”，不能证明新增Stage同步登记于启动恢复器、LangGraph阶段映射、项目存储投影和前端继续入口；已有11阶段甚至在恢复映射中只覆盖8项。
- 风险：新增或现有阶段可在运行期进入权威图，却在服务重启后无法按业务持久事实恢复，或前端没有继续入口；静态测试仍会错误放行。
- 整改标准：建立四个显式可枚举登记表并由同一契约测试与`CANONICAL_STAGES`精确相等校验；每个阶段的恢复存储、图映射、项目投影和前端继续行为必须有明确策略，禁止用隐式fallback掩盖缺登记。
- 主线实现：新增版本化`stage.registrations.json`，11阶段逐项登记启动恢复策略、LangGraph规范名、项目存储键及真实前端继续函数。后端启动时失败关闭顺序/字段/图名不一致并由恢复器直接消费项目存储映射；前端流程模块编译时校验该表与pipeline顺序精确一致并导出登记事实。requirements/audio/subtitle不再缺席恢复映射。
- 开发验证：四处登记契约、生产控制面、文档状态与架构关联`109 passed`，无失败无跳过；显式Node运行时Vue类型检查通过。首次从插件子目录执行pnpm因无package失败、随后仓库frontend的pnpm前置检查因既有esbuild脚本未获批准停止，改用已安装`vue-tsc`直接验证通过，未改变依赖授权。
- 独立软件测试：通过。冻结提交`2522e17`复跑四处登记门禁、生产控制面、文档状态与架构关联`109 passed`，无失败无跳过；显式Node运行时Vue类型检查通过。首次误在frontend目录调用仓库根`.venv`导致命令路径不存在，纠正工作目录后同一测试集合通过，未把环境调用错误计作产品失败。
- 最终只读稽查：通过。版本化登记表与11个`CANONICAL_STAGES`顺序、集合精确一致，四字段均非空且LangGraph名只能使用规范名；后端导入时失败关闭并由启动恢复器直接索引项目存储映射，前端模块校验同一登记表与pipeline并导出继续入口。CI还逐项验证登记的继续函数真实存在，requirements/audio/subtitle不再依赖隐式fallback。
- 关闭时间：2026-08-12（Asia/Shanghai）。下一状态：已关闭；按当前状态索引进入BUG039根因分析。
- 补充关联修正：扩大恢复测试仍硬编码旧局部`stage_storage`源码片段，架构迁移后产生1项静态假失败；测试改为解析版本化登记表并核对image/video项目存储值，同时确认恢复器消费`PROJECT_STAGE_STORAGE`。新旧门禁组合`4 passed`，不改变BUG064关闭结论。

### BUG-20260812-063：顶层架构文档停留v2.1并反向陈述生产内核状态

- 状态：已关闭（最终只读稽查通过）
- 关联任务：用户提交的架构文档v2.2事实修正清单；BUG057保持环境阻塞，不改模型路线。
- 正式复现：`docs/technical/系统架构设计.md`仍标记版本2.1，且第10节声称M5进行中、LangGraph M7.5尚未完成；代码和已关闭里程碑已存在11阶段契约、SQLite checkpoint、跨实例租约、ProductionLedger权威证据、拒绝事件快照、资源池/契约门禁及RecordExporter。
- 首个事实：顶层总纲没有随M9.169/172/183/195/197闭环更新，仍把已落地生产内核描述为未完成；权威台账、晚到隔离、持久等待、导出脱敏、provider inflight保护和新增Stage登记门禁也未形成顶层章节。
- 风险：后续开发会依据最高优先级架构文档重复建设或绕过已落地围栏，并遗漏提供方热插拔及阶段恢复登记约束。
- 整改标准：升级为v2.2，按用户确认事实替换第10节并补齐六项架构/运行约束；实现状态与目标约束必须分开表达，未交付的通用Skill机器人和多租户商业化不得伪装完成。
- 主线实现：顶层架构升级为v2.2并按截至2026-08-11的权威事实重写当前状态；新增ProductionLedger、晚到响应隔离、`waiting_memory`、`RecordExporter`四个章节，以及provider inflight热插拔保护和四处Stage登记CI门禁。新增架构契约测试，防止版本、里程碑及关键约束再次倒退。
- 开发验证：架构v2.2契约、生产控制面、权威台账、阶段一致性、可观测性与文档状态关联`92 passed`，文档状态门禁通过；未启动模型、未修改正式任务或运行数据。
- 独立软件测试：通过。冻结提交`1aaf7a9`上以显式仓库模块路径复跑架构契约、生产控制面、权威台账、阶段一致性、可观测性与文档状态`112 passed`；无失败、无跳过，未启动模型或修改正式数据。首轮遗漏模块路径导致15项导入失败，同时索引状态少了规范前缀导致2项文档门禁失败；修正测试环境和状态口径后全部通过，不掩盖失败证据。
- 最终只读稽查：通过。代码中`CANONICAL_STAGES`精确为11阶段；ProductionLedger持久字段、代际/revision CAS与指纹/审核批次唯一边界存在；`waiting_memory`持久且投影queued；RecordExporter、JSONL/Prometheus导出和provider inflight原子保护均与文档一致。新增Stage四处登记被明确为演进强制约束，未将通用Skill机器人、多租户商业化或本机不可执行H3伪装完成。
- 关闭时间：2026-08-12（Asia/Shanghai）。下一状态：已关闭；继续稽查Stage四处登记CI门禁的实现完整性，缺口独立登记，不回退本次文档事实同步结论。

### BUG-20260812-062：H3 INT8在MPS静默回退单核CPU且无进度门禁

- 状态：已关闭（补充只读复稽查通过）
- 关联任务：M9.198 / BUG057真实静音H3，不扩展处理排队BUG039—041。
- 正式复现：BUG061修复后的正式job`e6c8d306-6644-47ad-88bb-e7ff0c01e2c6`成功完成Context IR并提交H3 prompt`a11500f0-ca73-4e9b-a4dc-9eed014e15d3`；模型和文本编码器均完整加载，但采样连续70分钟保持`0/20`。进程持续约100% CPU、24%内存，Comfy无错误且业务心跳持续，用户界面无法区分有效推理与不可交付硬件回退。
- 首个事实：进程栈稳定落在`at::_ops::_int_mm`→`_int_mm_cpu`，当前`minimax_h3_ref2va_pruned_int8_convrot`依赖的量化矩阵算子在Darwin/MPS没有设备内核；Comfy启动还明确报告AIMDO不支持Darwin。现有能力选择只检查模型文件和可用内存，没有硬件/算子兼容门禁或首步进度截止。
- 风险：单镜头可能占用加速器数小时至数十小时而没有产出，资源租约、后续镜头和全链永久被占；4小时总超时也不能证明模型在本机可交付。
- 当前处置：已通过正式停止入口写`cancel_pending`，在量化CPU核不可中断时重启本地Comfy，任务最终`cancelled`且队列归零，无伪成功产物。
- 整改标准：提供方准入必须声明并动态验证设备/量化算子兼容性；已知不兼容组合在提交重模型前持久为`model_blocked`，禁止静默回退、禁止自动改用其他模型。补充状态投影、恢复、取消、接口和前端显示回归；只有受支持执行节点或显式安装兼容提供方后才允许真实H3。
- 主线实现：固定H3制品声明受支持设备集合`cuda`；提交Context IR前读取实际Comfy`system_stats.devices`，设备未知或存在非白名单设备均失败关闭。专用`ModelBlockedError`原子提交job`model_blocked/model_blocked`及模型/提供方证据，持久任务投影为`paused`；服务端阶段编排识别该终态并把LangGraph报告为`paused`、HTTP返回409`model_blocked`。恢复可在提供方变更后显式重放原请求，停止、看门狗和重启均把该状态视为无活动执行体；禁止Wan静默回退。
- 正式验证：同一正式项目以新代际运行video，job`b92ede69-7963-4a9f-af20-6f16e23f89ae`在约2秒内持久`model_blocked`，错误明确当前设备`mps`及禁止CPU回退；`context_ir_prompt_id`和`comfy_prompt_id`均为空，证明任何32B/H3重模型都未提交。阶段接口返回HTTP409`model_blocked`，LangGraph video为`paused`，Comfy队列0/0。
- 开发验证：MPS阻断、CUDA准入、未知设备失败关闭、job终态、paused投影和服务端编排直接关联`159 passed`。完整unit除用户并行修改中的4项前端断言外`617 passed, 4 deselected, 9 subtests passed`；不排除时精确为`4 failed, 617 passed, 9 subtests passed`，四项均指向当前未提交的前端界面改动，与H3后端调用链无关。Python编译和文档门禁通过。
- 开发阶段边界（历史）：本机没有受支持H3执行节点或兼容制品，BUG057真实静音成品仍不得宣称通过；当时BUG062代码尚待独立软件测试和只读稽查。
- 独立软件测试：通过。冻结提交`f061cbb`的H3设备准入、未知设备失败关闭、job终态、paused持久投影、服务端阶段编排、取消/恢复及原Context IR/Ref2VA关联`159 passed`，无失败无跳过；Python编译、文档状态与正式job/Graph/Comfy终态一致。当前工作树完整unit为`4 failed, 617 passed, 9 subtests passed`，四项失败均逐项定位到用户并行未提交的前端界面改动；排除该四项后`617 passed, 4 deselected, 9 subtests passed`，未把其计作本BUG通过证据。
- 最终只读稽查：通过。兼容性判断基于固定模型制品的显式设备白名单与运行提供方实际设备声明，未知设备失败关闭；门禁在Context IR和H3提交前，不能产生模型、prompt或媒体副作用。`model_blocked`是持久终态并投影paused，显式重放只在新job中发生，未改用Wan、未绕过生产门禁。正式旧任务取消核销和新任务秒级阻断证据一致。
- 关闭时间：2026-08-12（Asia/Shanghai）。下一状态：已关闭；BUG057继续阻塞于缺少CUDA兼容H3执行提供方，不属于代码静默回退缺陷。
- 补充只读复稽查：不通过（P1）。job提交入口虽然秒级阻断MPS，但公共`/api/production/capabilities`仍把`video.shot.h3_ref2va / comfy-minimax-h3-ref2va`发布为`healthy=true`且metadata只有`builtin`。调度器和客户端会在任务前把已知不可执行提供方展示为健康，违反“能力注册状态与运行门禁同一事实”并可能反复准入。
- 复稽查整改：固定H3注册项在安装能力时读取同一Comfy设备契约；MPS/CPU/未知或健康检查失败均注册`healthy=false`，metadata同步公开`supported_device_types=["cuda"]`和`availability_error`。其他内置能力健康状态不受影响；健康查询只读现有Comfy状态，不启动模型或服务。
- 整改正式验证：服务重载后`/api/production/capabilities`返回H3 provider `enabled=true, healthy=false`，支持设备为CUDA，错误与正式job的MPS阻断事实一致；不再对外发布伪健康。
- 整改开发验证：能力注册健康隔离、MPS/CUDA/未知设备、job/Graph状态及原H3关联`160 passed`，Python编译通过。下一状态：待独立软件复测与只读复稽查。
- 整改独立软件复测：通过。在提交`2a94278`上只读复跑H3能力健康、设备白名单、未知设备、job/Graph状态和原Context IR/Ref2VA关联`160 passed`，无失败无跳过；正式能力接口精确断言provider unhealthy、CUDA白名单和MPS原因通过。
- 补充最终只读复稽查：通过。能力目录与执行门禁共用同一固定制品设备契约；注册失败只降低H3 provider健康，不污染其他能力。健康查询不启动Comfy/模型，正式任务准入才允许确保服务启动；不可用provider既不会被注册表选择，也不会在业务入口静默回退。BUG062重新关闭。

### BUG-20260812-061：嵌套结果媒体URL被错误截断为末级目录

- 状态：已关闭（最终只读稽查通过）
- 关联任务：M9.198 / BUG057正式静音H3，不扩展处理排队BUG039—041。
- 正式复现：BUG060修复后，正式job`4e7e8e8c-e443-48f9-b4d7-bbc8a09d9922`的Context IR成功完成并持久化优化提示词，随后H3启动前以`分镜图片不存在`失败。分镜图和身份图均存在且HTTP 200；失败输入是`subfolder=assets3d/<project>/scene/空房间`的Blender源视频。
- 首个事实：`_local_media_path`对`subfolder`执行`Path(...).name`，把合法受控嵌套目录截断为`空房间`，再错误查找`output/空房间/blender_source.mp4`；正式资产URL实际指向`output/assets3d/<project>/scene/空房间/blender_source.mp4`。
- 风险：所有3D资产生成的嵌套源视频均能通过媒体接口播放，却不能作为H3输入；Context IR完成后视频阶段确定性失败。
- 整改标准：在`OUTPUT_ROOT`内按解码后的相对目录安全解析嵌套`subfolder`，拒绝绝对路径、`..`和越界；文件名保持单一叶子名。补充合法多级目录、编码中文、穿越及绝对路径动态测试后，重跑同一正式H3。
- 主线实现：结果媒体解析保留受控根内完整相对`subfolder`，文件名必须为单一叶子；绝对目录、目录穿越、文件名穿越及解析后越界统一失败关闭，既有一级`images/videos`URL保持兼容。
- 正式验证：同一请求重跑为job`e6c8d306-6644-47ad-88bb-e7ff0c01e2c6`；Context IR完成后成功解析并装载嵌套Blender源视频与身份图，持久阶段进入`h3_rv2v`且Comfy prompt实际运行，原`分镜图片不存在`不再出现。随后量化算子性能问题独立登记BUG062。
- 独立软件测试：合法多级中文目录、绝对目录、`..`目录和文件名穿越动态矩阵通过；H3直接关联`31 passed`，绑定Node后完整unit`599 passed, 9 subtests passed`，无失败无跳过；Python编译和文档门禁通过。
- 最终只读稽查：通过。`resolve()`后的根目录包含校验同时覆盖符号链接逃逸，文件名不可携带路径，嵌套目录只在`OUTPUT_ROOT`内放行；正式H3已越过原失败点，无静默复制或当前项目特判。
- 关闭时间：2026-08-12（Asia/Shanghai）。下一状态：已关闭；M9.198串行处理BUG062。

### BUG-20260812-060：H3 Ref2VA Context IR主Skill工具未注册

- 状态：已关闭（最终只读稽查通过）
- 关联任务：M9.198 / BUG057真实静音H3，不扩展处理排队BUG039—041。
- 正式复现：隔离正式项目`6b2a7774-5543-405d-b4c5-e07420677701`已按用户范围确认大纲、剧本、3镜分镜、资产和image权威台账；通过正式`/api/videos/generate`提交3秒H3 job`d72dfc6f-bdb7-406a-8e51-97b7702f3b4b`。Context IR两次均在节点`MiniMaxH3Ref2VAPromptAgentOpenAIAPI`失败，Comfy历史prompt`d6b3a781-57ba-4c00-8154-31f74d1bfde1`原始错误为`Tool h3-prompt-writing not found in agent MiniMax H3 Ref2VA Prompt Agent`。
- 首个事实：节点把`h3-prompt-writing`正文内联到system instructions并要求输出selected_skills，但Agent只注册`list_style_skills`和`load_style_skill`。本地Qwen3-VL在Ref2VA多模态请求中合法产生名为`h3-prompt-writing`的工具调用，OpenAI Agents SDK因Agent工具表缺失该名称而在模型结果解析阶段失败；有限重试无法改变确定性契约错误。
- 风险：FL2VA简单冒烟可以偶然直接输出JSON，但正式Ref2VA一旦选择主Skill工具就必然失败；Context IR无法落盘，H3按失败关闭禁止启动，BUG057和后续视频阶段永久阻塞。
- 整改标准：供应链固定补丁必须把只读主Skill注册为精确名称`h3-prompt-writing`的工具，返回与内联材料同源的Skill和当前guide；禁止网络加载、路径越界或回退原提示词。更新补丁SHA、安装验证和动态测试，重启Comfy后重跑同一正式H3。
- 主线实现：固定兼容补丁新增`_make_h3_material_tool`，以`function_tool(name_override="h3-prompt-writing")`注册零参数只读工具，只闭包返回已由固定skills目录加载的主Skill正文和当前base/ref guide；两个style工具保持原白名单。安装器同步锁定新补丁SHA，并在安装/验收时解析已应用`nodes.py`，强制校验精确模型可见工具名。
- 开发验证：补丁在固定上游提交`771cb3cb01af9543b4f424518bb19b7fa0cf31d8`的隔离worktree中实际apply、Comfy Python编译和AST精确工具注册验证通过；H3安装/Context IR/Ref2VA/取消关联`48 passed`，完整unit`595 passed, 9 subtests passed`无失败无跳过，shell/Python编译通过。
- 正式复测：用户明确授权外部节点目录后，补丁已应用并由安装器固定校验，Comfy 8194完成重启。首次复测暴露补丁helper遗漏局部`function_tool`导入，修正供应链补丁及应用态双SHA后再次重启；正式job`4e7e8e8c-e443-48f9-b4d7-bbc8a09d9922`一次完成Context IR，模型实际调用`h3-prompt-writing`并输出`selected_skills=["h3-prompt-writing"]`、优化提示词及原始JSON持久快照。
- 独立软件测试：H3 Context IR/Ref2VA直接关联`33 passed`；绑定显式Node运行时后完整unit`595 passed, 9 subtests passed`，无失败无跳过。安装器`--verify`、固定上游补丁应用态、Comfy Python编译和精确工具AST门禁通过。
- 最终只读稽查：通过。模型可见工具名、闭包材料来源、零参数/无网络边界、补丁文件SHA与已应用diff SHA分别锁定；正式Ref2VA已越过原工具缺失点并持久完成Context IR。随后媒体路径失败属于独立BUG061，不回退BUG060结论。
- 关闭时间：2026-08-12（Asia/Shanghai）。下一状态：已关闭；M9.198串行处理BUG061。


### BUG-20260811-059：人物角度后验收脱离原图片任务生命周期

- 状态：已关闭（最终只读稽查通过）
- 关联任务：M9.198 / BUG057正式image前序，不扩展处理BUG039—041。
- 正式复现：人物固定角度job`93185ea7-6266-4b04-9118-cbeb1e3593b4`的Qwen产图完成后，持久job停在`processing/qwen_variant`且心跳停止；资源池却排队随机job`character-angle-audit-a116c49b-affd-4abc-8983-e26b6e66868e`。同时下一图片job`134a62ce-0124-4e2d-97dd-6ffc5dcfdaa3`在不可观测的后验收占用期内等待内存并超时失败。
- 首个事实：`_validate_character_variant`两次LLava审核均以随机UUID申请资源，调用方又直接同步执行验收，没有经过已有`_run_image_validation`的原job心跳、180秒超时、停止取消和晚到隔离边界。
- 风险：原图片job可在没有自身资源票据与心跳的情况下长时间占用审核模型；停止、超时或服务回收无法精确取消排队票据，终态后仍可晚到启动模型，并阻塞后续重任务。
- 下一状态：将人物baseline/固定角度验收统一纳入原图片job的后验收监督器，两次审核共用原job资源所有权与同一有限截止，然后重跑正式前序。
- 框架整改：人物baseline与固定角度共用`_run_image_validation`，持久阶段统一为`character_validation`；角度、服装与画幅三类审核全部使用原`job_id`票据。后验收工作线程从持久job恢复完整tenant/user/project身份，每次排队、模型调用前后均复核job可运行性，所有审核共用外层180秒deadline。停止或超时取消原job排队票据并终止LLava，禁止终态后新启审核。
- 正式验证：服务在资源空闲后重载，同一项目林婉清左45°正式job`ef558c27-c3b3-4bef-ad8d-f662fd6a8579`完成两次Qwen产图与后验收。产图后持久phase明确转为`character_validation`，heartbeat从`15:31:23Z`持续推进至`15:39:48Z`，最终因方向、身份、脚部和比例质量门禁正常failed；Comfy队列回到0/0、资源池回到空闲，无随机audit票据、无无心跳卡死和模型残留。
- 开发回归：绑定显式Node运行时后验收、图片恢复、生产门禁、取消及H3直接关联`175 passed, 3 subtests passed`；完整unit`586 passed, 9 subtests passed`，均0失败0跳过。Python编译、文档状态与diff门禁通过。
- 下一状态：待独立软件测试。
- 独立软件测试：通过。在开发提交`430397b`的干净工作树上，重跑人物后验收、图片恢复、生产投影/取消、阶段覆盖、H3静音图及Context IR直接关联`175 passed, 3 subtests passed`；完整unit`586 passed, 9 subtests passed`，均0失败0跳过。Python编译、文档门禁、diff-check与干净工作树通过。正式job的持续心跳、真实质量失败终态、Comfy与资源归零证据与实现一致；测试身份未修改代码、配置或正式数据。
- 下一状态：待只读稽查。
- 首轮只读稽查：不通过（P1）。LLava三类审核已归原job，但其后`_face_pose_angles`、`_face_embedding_similarity`、`_pose_proportion_metrics`和`_head_body_ratio`仍未接收job/deadline。其中`_pose_proportion_metrics`会提交一个未写入图片job的Comfy prompt，最长自行轮询300秒；外层180秒超时只取消资源票据并终止LLava，不知道该prompt ID，验收线程仍可在原job终态后继续Comfy/子进程工作。此缺口违反同一后验收的取消、超时、晚到隔离和资源释放验收；原证据不足以关闭BUG059。
- 稽查整改标准：确定性子步骤全部复用原job可运行性与同一deadline；OpenPose prompt ID必须持久到原job，停止/超时精确核销且确认离开Comfy running/pending后才收敛；补充超时、停止和终态晚到不启动下一子步骤的动态测试，重新经过独立软件测试。
- 稽查整改：新增原job所有的确定性验收子进程监督器；InsightFace姿态、身份向量与头身比子进程均登记到`ACTIVE_IMAGE_PROCESSES`，每200ms复核原job可运行性和共享deadline，停止/超时终止自身进程组。OpenPose的Comfy prompt ID原子写入`validation_prompt_id`，历史轮询同样受job/deadline约束，失败时精确核销；统一停止、超时、服务恢复与关闭核销集合已纳入该prompt字段。外层后验收在收敛前同时取消原job票据、确定性子进程、所属Comfy prompt和LLava。
- 整改动态验证：原job在确定性子进程运行时转failed，子进程在2秒内终止且活动映射清空；OpenPose在截止时间到达后精确取消已持久`prompt-timeout`，并清空job的活动prompt字段；统一取消入口只核销原job持有的`prompt-owned`。直接关联`178 passed, 3 subtests passed`，完整unit`589 passed, 9 subtests passed`，均0失败0跳过；Python编译、文档状态和diff门禁通过。
- 下一状态：待独立软件测试复测。
- 稽查整改独立软件复测：通过。在提交`9685d38`的干净工作树上，重跑人物后验收子进程终止、OpenPose prompt持久/超时精确取消、图片恢复、生产取消及H3直接关联`178 passed, 3 subtests passed`；完整unit`589 passed, 9 subtests passed`，均0失败0跳过。Python编译、文档状态、diff-check与干净工作树门禁通过；测试身份未修改代码、配置或正式数据。
- 下一状态：待只读复稽查。
- 二轮只读复稽查：不通过（P1）。确定性子进程取消已成立，但`_pose_proportion_metrics`向Comfy提交OpenPose prompt时仍没有取得原job的`audit/accelerator`资源票据，正式证据中已实际出现Comfy pending/running而资源池`active=null`。此外，`_cancel_image_validation_work`忽略`_cancel_job_comfy_prompts`的布尔结果；若Comfy prompt在10秒内未确认离开队列，外层仍抛错并由HTTP入口写`failed`终态，看门狗、服务关闭也同样忽略核销失败。这与规范要求的“prompt确认离开running/pending后才收敛”相反，可产生failed但仍占用Comfy/加速器的矛盾终态。
- 二轮稽查整改标准：OpenPose提交与轮询必须在原job、完整身份和共享deadline的`audit`资源claim内；停止/超时先持久取消请求，核销未确认时保持非终态`cancel_pending`并由看门狗继续精确核销，禁止写failed/completed或释放任务所有权；补充核销失败不进终态、看门狗复核和资源身份动态测试。
- 二轮稽查整改：OpenPose提交、持久prompt与历史轮询进入原图片job完整身份的`audit`资源claim，并共享外层deadline。取消入口返回Comfy与LLava双确认；超时、用户停止、启动恢复、无owner清理、看门狗和服务关闭在任一prompt未确认离队时统一持久`processing/cancel_pending`及预定终态，不释放subject所有权。看门狗每轮继续精确核销；确认离队后才原样恢复completed或提交failed，服务恢复同样纠正历史“终态但prompt仍活动”的矛盾记录。
- 二轮整改开发验证：动态覆盖后验收取消未确认保持非终态、停止与恢复拒绝提前终态、既有completed记录在prompt未离队时转`cancel_pending`并在确认后恢复completed、OpenPose使用原job资源claim与超时精确取消；直接关联`110 passed, 3 subtests passed`，完整unit`593 passed, 9 subtests passed`，均0失败0跳过。Python编译与diff门禁通过。
- 下一状态：待独立软件测试复测。
- 二轮整改独立软件复测：通过。在冻结提交`ec12a1c`和干净工作树上，重跑OpenPose原job资源claim、后验收取消未确认、用户停止、无owner清理、服务恢复及终态恢复关联`110 passed, 3 subtests passed`；完整unit`593 passed, 9 subtests passed`，均0失败0跳过。Python编译、文档状态、diff-check和工作树门禁通过；未启动模型、未修改正式数据。
- 下一状态：待只读复稽查。
- 三轮只读复稽查：不通过（P1）。第一，`_cleanup_invalid_image_tasks`把所有无owner的`cancel_pending`走通用“旧任务回收”分支；核销确认后以新错误调用`_finish_image_cancel_pending`，会把原本预定恢复的completed写成“completed但有回收错误”，破坏已持久的预定终态语义。第二，`_confirm_image_job_cancellation`在看门狗/恢复/清理持有图片锁时直接全局停止`llava:latest`，没有重新取得原job的accelerator票据；原验收claim释放后若下一审核已准入，持续对账可能误停后续job的模型。现有测试分别覆盖终态恢复与资源claim，但未覆盖通用清理介入及“下一job已占资源”竞态。
- 三轮稽查整改标准：`cancel_pending`必须优先按其持久`pending_terminal_*`原样对账，所有清理入口不得覆盖预定终态或错误；LLava重试核销必须先以原job完整身份重新取得有限`audit`claim，资源被其他job占用时保持pending而非全局停模。补充通用清理恢复completed无错误和资源忙时不调用停模的动态测试，重新独立复测。
- 三轮稽查整改：通用无owner清理先识别`cancel_pending`，确认资源离队后只调用无覆盖参数的预定终态恢复，未确认则仅更新心跳。LLava持续核销从持久job恢复tenant/user/project身份，以原job申请250ms有限`audit`claim；资源忙或租约不可得时保持pending且绝不调用全局停模，取得独占accelerator后才重试终止并确认模型退出。
- 三轮整改开发验证：动态覆盖通用清理把预定completed、空error及原finished_at无损恢复；资源claim忙时停模调用为0，原job完整身份成功取得claim后才精确停止LLava。直接关联`112 passed, 3 subtests passed`、完整unit`595 passed, 9 subtests passed`，均0失败0跳过；Python编译通过。
- 下一状态：待独立软件测试复测。
- 三轮整改独立软件复测：通过。在冻结提交`490d2a0`和干净工作树上，重跑通用清理预定终态恢复、资源忙停模隔离、原job身份claim、OpenPose及图片生命周期关联`112 passed, 3 subtests passed`；完整unit`595 passed, 9 subtests passed`，均0失败0跳过。Python编译、文档状态、diff-check和工作树门禁通过；未启动模型、未修改正式数据。
- 下一状态：待只读复稽查。
- 最终只读复稽查：通过。OpenPose提交/轮询处于原job完整身份的有限`audit`claim；取消请求、Comfy prompt、LLava、确定性子进程、subject所有权及预定终态形成同一持久生命周期。核销未确认不进入终态，通用清理/恢复/看门狗/关闭持续对账且无损恢复预定结果；LLava重试先重新取得原job accelerator所有权，资源忙时不触碰后续任务。软件复测无skip，代码、状态和证据一致，无阻断项。
- 关闭时间：2026-08-12（Asia/Shanghai）。
- 下一状态：已关闭；M9.198恢复BUG057正式静音H3及2—3镜头、总时长不超过15秒的全链验收。

### BUG-20260811-058：人物固定角度串行批次误判为并发内存超限

- 状态：已关闭（最终只读稽查通过）
- 关联任务：M9.198正式全链的image前序恢复，不扩展处理BUG039—041。
- 正式复现：用户在正式资产页确认“林婉清”0°基准图后，左45°Qwen任务被拒绝为预计60GB且必须保留99GB；随后右45°、90°、180°和半身依次以90GB/81GB保留量失败，Comfy队列最终为空。
- 首个事实：人物Qwen共用入口在取得串行image资源后仍直接调用`_require_memory(60GB)`；上一张Comfy任务结束后的`/free`是异步释放，该入口没有使用BUG052已建立的有限、可取消`waiting_memory`握手，于是把同一串行批次的前一模型驻留误算成新的非AI工作集。
- 风险：任意连续人物固定角度或Qwen修复任务都会在上一Comfy权重释放窗口内确定性失败；资源池虽无并发超卖，业务批次仍无法完成。
- 框架整改：人物Qwen固定角度与独立修复两个60GB公共入口统一改用`_wait_for_post_comfy_memory(..., job_id)`；保持空闲队列才允许主动`/free`、最长60秒、持续心跳、停止可取消、超时失败关闭的既有协议。
- 下一状态：完成专项与关联回归，并在正式页面重试固定角度，确认每张任务串行、权重释放且人物图片链可继续后提交独立软件测试。
- 主线正式验证：128GB Mac资源门禁满足后，正式项目`83eaa695-0a31-4119-aa94-060c232053fd`的林婉清左45° job `444f4db8-1388-4a74-803e-e7543bda2fca`越过原60GB误拒绝，进入Comfy Qwen prompt `7abdd0f7-45de-4f4a-ba1b-35ffc70494d1`并成功产图；其最终失败仅来自独立视觉质量门禁（错误为方向/身份/脚部等验收项，不含内存保护）。随后另一项目苏璃左45° job `b38fa97a-608f-47d8-960c-f82368a43291`同样在上一模型释放后自然准入，资源快照始终仅一个accelerator active、Comfy仅一个running且无并发超卖。
- 主线回归：显式Node环境完整单元`584 passed, 9 subtests passed`，无失败无跳过；BUG058直接内存等待/取消/超时/服务重启空闲释放与两个Qwen入口关联均包含在冻结快照。文档状态与diff门禁通过。
- 下一状态：待独立软件测试。
- 独立软件测试：通过。绑定显式Node运行时复跑内存释放窗口、取消、超时、服务重启空闲释放、图片job恢复、生产资源投影及Qwen两入口关联`168 passed`，完整unit`584 passed, 9 subtests passed`，均0失败0跳过。正式林婉清job已由原60GB立即拒绝变为Qwen成功产图后仅视觉质量门禁失败；后续苏璃job自然准入时accelerator严格`active=1/queued=0`、Comfy`running=1/pending=0`，无并发超卖。测试身份未修改代码、配置或正式数据。
- 下一状态：待只读稽查。
- 最终只读稽查：通过。两个60GB Qwen公共入口均在共享accelerator claim内复用同一有限释放握手；等待态持久化、LangGraph queued投影、job取消检查、60秒超时失败关闭、空闲Comfy主动释放及非释放窗口立即拒绝边界一致。正式旧失败与新job对比证明只消除内存误拒绝，视觉质量门禁仍独立失败关闭；关联`168 passed`、完整unit`584 passed, 9 subtests passed`均无失败无跳过。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭。

### BUG-20260811-057：H3源视频重复生成无业务用途音轨

- 状态：阻塞
- 关联任务：M9.198
- 正式事实：用户明确MiniMax H3视频不使用音频输入；现行Ref2VA graph虽然没有传入参考音频，却仍执行`VAEDecodeAudio`并将H3自生音轨写入MP4，后续独立Qwen TTS与口型链又会覆盖音频。
- 首个事实：`MiniMaxH3ReferenceToVideo`官方节点要求`audio_vae`参与AV latent构造，不能直接删除必填输入；冗余发生在采样完成后的音频解码与`CreateVideo.audio`封装。
- 风险：无用途音频解码增加显存/耗时，源视频混入非权威声音还可能污染审核、配音与最终混音边界。
- 下一状态：保留官方节点必需audio VAE，删除H3音频解码与封装，明确源视频无音轨，音频只由后续独立台账阶段产生。
- 主线实现：H3 graph移除`VAEDecodeAudio`与`CreateVideo.audio`，保留官方`MiniMaxH3ReferenceToVideo.audio_vae`必填输入；completed job写入`audio_mode=not_applicable_h3_source_video`，视频规范同步明确权威声音只来自后续TTS/口型/混音。
- 开发自检：Comfy当前`CreateVideo`运行时确认audio为optional；H3、Context IR、媒体、3D及生产门禁关联`81 passed, 1 deselected`，无失败无skip，唯一deselect为用户跳过BUG038静态断言；Python编译和文档门禁通过。
- 正式阻塞：资源空闲后通过正式`/api/videos/generate`提交隔离H3验证，服务返回409`production_gate_blocked: previous stage is not completed: image`。该项目image阶段完成依赖人物确认/多角度链，属于用户明确要求跳过的BUG038；不得绕过已修复的生产阶段门禁，也不得把未运行真实H3计为通过。
- 下一状态：阻塞；需要用户允许完成BUG038人物确认链，或提供另一个image阶段已完成且具备已确认3D源视频/人物身份图的正式项目，之后才能真实生成并用ffprobe验证无音轨，再进入独立软件测试。
- 阻塞解除：用户已授权补齐正式image前序；BUG058串行内存握手最终闭环，正式人物Qwen已可执行。继续完成当前项目image确认并提交真实H3，使用ffprobe证明源视频无音轨。

### BUG-20260811-056：3D确认混用业务名称与文件安全名

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：道具“信纸/信件”正式3D job`d3783388-3b53-457e-9d94-159d8c340e17`已completed，报告9497顶点/18990面、非流形边0；调用正式确认接口却409`3D候选与资产不匹配`。
- 首个事实：生成任务的`asset_name`和`subject_key`保留业务原名`信纸/信件`，确认入口先对请求名称执行`_safe_name`得到`信纸_信件`，再拿净化名比较业务身份与subject key，必然不一致；候选目录使用安全名本身正确。
- 风险：任何包含斜杠、空格或其他需文件净化字符的合法资产都能生成但不能确认归档，3D结果永久停在待确认并阻断后续视频。
- 下一状态：分离业务身份原名与文件/归档安全名，身份比较保持精确原名，路径仍只使用安全名并保持越界保护。
- 根因：`_confirm_asset_3d_job`只保留净化后的`asset_name`，该变量同时用于业务身份、subject key、候选fallback和归档路径；文件安全规则错误侵入业务唯一身份比较。
- 框架整改：确认入口分别维护`project_identity/asset_identity`与`project_id/asset_name`安全路径名；任务字段和subject key只按精确业务身份比较，候选fallback、普通资产归档和服装归档仍统一使用`_safe_name`，原有OUTPUT_ROOT越界保护不变。
- 开发验证：新增含斜杠业务名成功确认归档为安全目录、不同业务名不能借净化通过的动态矩阵；3D及任务直接关联`32 passed`，Python编译、文档门禁通过。正式服务由PID`8480`重载至`13211`，原job确认成功，归档路径为`3d/props/信纸_信件`且不可变版本已创建。
- 独立软件测试：通过。含斜杠原名确认后归档目录为安全名，相近不同业务名精确拒绝；任务身份、subject key、候选根目录越界保护、不可变版本与原正式job均通过。关联`56 passed, 1 deselected`，完整unit`581 passed, 1 deselected, 9 subtests passed`，无失败无skip；唯一deselect为用户明确跳过BUG038静态断言，与本次确认函数无调用关系。编译和文档门禁通过。
- 下一状态：待只读代码稽查。
- 最终只读稽查：通过。业务身份精确绑定job/project/subject，路径组件独立净化且候选必须位于受控OUTPUT_ROOT；相近名称、旧任务与越界候选均不能借安全名碰撞通过。正式原任务、不可变归档、测试与文档一致，BUG038隔离明确。
- 下一状态：已关闭；M9.198继续服装道具3D及后续全链。

### BUG-20260811-055：3D网格清理后残留非流形边阻断场景资产

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：确认“空房间”成功基准图后，通过正式`/api/assets/3d/generate`启动job`eb3eda72-a969-4334-9fd7-78c22b79ae41`；任务完成TripoSR重建并进入Blender清理，随后failed：`网格审核失败：仍有4条非流形边`。
- 首个事实：任务心跳、阶段和失败终态均正常，阻断点是公共Blender清理/审核链在处理TripoSR开放或破损表面后仍留下4条非流形边，不是资源、超时或投影问题。
- 风险：任何带孔洞、内部面或开放边界的单图重建网格都会确定性失败，重试同一输入无修复增量，场景/道具3D及后续视频全链无法推进。
- 下一状态：定位asset_3d_worker清理顺序与非流形审核首个不变量，增加确定性封孔/内部几何清理并保留失败关闭。
- 根因：TripoSR原始网格经去重、清游离、批量封孔及多面共边裁剪后，留下一个由4条边组成、每个顶点在该边界中度数均为2的微型闭环；Blender`bmesh.ops.holes_fill`对该闭环无动作，因此审核稳定报告4条边界非流形边。
- 框架整改：公共worker在批量`holes_fill`后按边界连通分量识别简单闭合环，仅当分量不少于3边且所有顶点边界度严格为2时按拓扑顺序创建封口面；开放、分叉、重复面等复杂损坏不兜底，继续由最终非流形审核失败关闭。
- 开发验证：同一正式GLB动态复现旧链`before=4`，公共兜底封闭1个简单环后`after=0`；3D工作流单测`19 passed`，Python编译通过。8787重载至PID`5838`后，正式重试job`fb1c04d2-f14f-4073-ac97-febc03ddc676`完成，报告10422顶点/20827面、`non_manifold_edges=0`、`loose_vertices=0`、7张审核图及24FPS/96帧/4秒源视频，资源池和重模型进程均为空。
- 下一状态：待独立软件测试覆盖简单闭环、复杂边界失败关闭、正式产物和关联回归。
- 独立软件测试：通过。Blender动态合成测试中，立方体单面缺失形成的4边简单环由`4→0`且封闭1环；两个三角面仅共享顶点形成的度4分叉边界保持`6→6`且封闭0环，证明异常复杂边界仍失败关闭。关联`61 passed, 1 deselected`，完整unit`576 passed, 1 deselected, 9 subtests passed`，无失败无skip；唯一deselect是用户明确跳过BUG038的人物静态断言，与本问题无调用关系。文档门禁、编译、正式report及资源终态通过。
- 下一状态：待只读代码稽查。
- 最终只读稽查：通过。修复位于场景/道具/人物共用worker并直接处理批量封孔遗漏的简单闭环；连通分量、边界度和闭环顺序门禁完整，复杂边界仍由最终审核失败关闭。无项目/资产特判，无公共契约变化；动态测试、正式报告、资源释放与记录一致，BUG038未执行项隔离明确。
- 正式关闭：job`fb1c04d2-f14f-4073-ac97-febc03ddc676`已通过正式确认接口归档至项目hot区不可变版本，状态completed；BUG055关闭，M9.198继续道具3D及后续全链。

### BUG-20260811-054：重新激活并确认的成功台账保留旧失败错误

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：BUG053关闭后通过正式API恢复“空房间”成功媒体，将原failed资产scope重新激活为pending_confirmation并确认；ledger lifecycle正确变为completed、confirmation已写入，但error仍为旧值`图片生成失败：图片任务已停止`。
- 首个事实：`/api/production/scopes`重新激活请求未显式传error时沿用旧失败错误；随后`/api/production/assets/confirm`提交completed也未清除error，形成成功生命周期、有效确认和失败错误三者矛盾。
- 风险：后续3D、阶段聚合、审核导出和manifest可能把已确认成功资产判为失败或输出过期故障证据；重试成功无法形成干净唯一终态。
- 根因：`ProductionLedger.upsert`对未携带error的所有生命周期一律继承当前error；`confirm`的CAS SQL只写completed与confirmation，不更新error。因此旧失败诊断跨越重新激活并污染成功终态。
- 框架整改：`reactivate=true`且目标非失败类生命周期时默认清空旧error；任何直接completed upsert及所有confirm CAS均原子写`error=''`。显式写入的pending_confirmation诊断继续保留，failed/cancelled/stale错误语义不变。
- 开发验证：新增failed→reactivate→confirm以及pending显式诊断→confirm矩阵；ProductionLedger专项`84 passed`，台账及全部直接依赖`225 passed, 1 deselected`。唯一deselect为用户明确跳过BUG038的人物角度静态断言，现行代码新增肢体门禁但其断言未同步，与本次ProductionLedger无调用关系；未修改该问题。Python编译通过。
- 正式验证：8787在Comfy资源空闲后重载至PID`3569`，再次确认原`scene:空房间`记录；返回lifecycle=completed、confirmation有效、error为空、revision=54，旧`图片任务已停止`不再残留。
- 独立软件测试：通过。ProductionLedger及直接依赖`225 passed, 1 deselected`无失败无skip；唯一未执行项为用户明确跳过BUG038的已知人物静态断言，与本问题无调用关系。失败→reactivate→confirm、pending显式诊断、重复确认、CAS、回滚、增强/导出台账关联、正式原记录和构建门禁均通过。
- 最终只读稽查：通过。reactivate、直接completed和confirm三个公共入口维护成功error为空不变量；显式completed错误不能覆盖，pending诊断、失败态、CAS、回滚、历史快照和正式记录边界均成立。BUG038未执行项范围隔离明确。
- 下一状态：已关闭；M9.198继续正式全链。

### BUG-20260811-053：场景候选子进程退出后任务停在无心跳processing

- 状态：已关闭（最终复稽查通过）
- 关联任务：M9.198
- 正式复现：三个道具连续成功后自动生成“空房间”场景；界面持续“正在生成”超过六分钟。持久job为`processing/klein9b_baseline`，`pid=None`、`process_group=None`，heartbeat停在候选子进程退出时，后端无子进程且Ollama为空。
- 首个事实：物理Klein候选已退出并记录`empty_scene_retry_2.png`，但候选后的场景验收/重试返回链没有继续心跳或受监督终态；只有人工暂停才清除非终态任务。
- 风险：任何耗时验收、候选重试或结果回填若脱离子进程监督，可形成无执行者processing并永久占用界面批次。
- 根因：图片监督器只在`_run_image_process`物理子进程存活期间写心跳；子进程成功退出后，道具/场景视觉验收改为同步`urlopen(timeout=600)`，既不写图片job心跳，也不检查停止或硬截止。请求处理worker虽仍存活，看门狗不会回收，但持久状态成为无PID、无心跳的processing，界面无法区分仍在验收与失去执行者。
- 框架整改：新增统一后验收监督器，道具和场景均显式进入`prop_validation/scene_validation`，每两秒更新持久心跳并检查停止与图片任务硬截止；单次验收最长180秒。停止、硬截止或验收超时会终止`llava:latest` runner并等待验收线程释放资源，晚到结果没有持久写权限；成功、异常统一回到既有唯一终态提交。
- 开发验证：新增阻塞验收心跳、停止、有限超时与模型终止回归；图片任务专项`33 passed`，关联`85 passed, 2 skipped, 3 subtests passed`（两项仅因未绑定Node），完整unit`570 passed, 2 skipped, 9 subtests passed`，补充绑定Node后原跳过文件`25 passed`。Python编译、文档门禁、Vue typecheck、83模块构建及diff-check通过。
- 正式验证：资源空闲后8787重载至PID`94931`，重放原“空房间”持久请求得到job`5a5f555b-5620-4645-a2c6-a504b328ef27`；Klein PID退出后状态从`generating/klein9b_baseline`切到`processing/scene_validation`且PID为空、heartbeat持续推进，约2秒后`completed`。三项场景视觉验收均为true，Ollama已卸载；随后并行BUG038自行占用Comfy，不属于本问题且未介入。
- 独立软件测试：通过。绑定Node运行时后关联`87 passed, 3 subtests passed`、完整unit`572 passed, 9 subtests passed`，无失败无skip；Python编译、Vue typecheck、83模块构建和文档门禁通过。正式job为completed/scene_validation，媒体存在且为2,462,708字节，PID/进程组及error为空，三项验收全真，Ollama为空；并行BUG038的Comfy任务不计入本BUG资源残留。
- 首轮只读稽查退回：P1。验收线程使用随机`scene-audit/prop-audit`资源job并可排队900秒，而外层图片job只等待180秒；accelerator繁忙时外层可能先失败，后台票据仍在终态后获得资源并启动LLaVA，违反取消、晚到隔离和资源释放门禁。
- 稽查整改：道具/场景验收资源票据统一绑定原图片`job_id`，资源排队上限同步为180秒；外层停止、硬截止或超时先调用`RESOURCE_SCHEDULER.cancel_job(job_id)`唤醒并撤销排队票据，再终止可能已活动的LLaVA。新增调用方job传递、票据所有权、取消和同界超时回归。
- 稽查整改开发验证：图片专项`34 passed`、完整unit`573 passed, 9 subtests passed`无失败无skip，Python编译通过；原正式成功场景事实未变，未在并行BUG038重任务期间重复启动模型。
- 稽查整改独立软件复测：通过。关联`88 passed, 3 subtests passed`、完整unit`573 passed, 9 subtests passed`无失败无skip；原心跳/停止/超时、资源票据job所有权、排队取消、活动模型终止、服务重启和正式场景证据均通过。Python编译、Vue typecheck、83模块构建及文档门禁通过。
- 最终只读复稽查：通过。后验收作用于道具/场景共享链；阶段心跳、停止、硬截止、180秒有限超时、LLaVA活动终止、原job资源票据取消及终态晚到隔离闭环。正式成功场景、无skip复测和文档证据一致，无阻断缺陷。
- 下一状态：已关闭；M9.198继续正式全链。

### BUG-20260811-052：串行资产任务在前一模型释放完成前被内存门禁拒绝

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：正式“信纸/信件”成功并调用Comfy释放后，资产批次立即串行启动下一服装道具；下一任务被拒绝：`预计需要42GB，必须为系统保留58GB；任务需拆分后串行执行`，但当前本来就是单任务串行。
- 首个事实：Schnell链在finally调用`/free`后立即返回，下一道具同步执行`_require_memory(42GB)`；Comfy释放为异步，前一权重/缓存尚未反映到available，门禁把可恢复的释放窗口直接判为业务失败。
- 风险：任意混合模型串行批次可在上一模型刚释放时误失败，提示“拆分串行”却无法通过现有串行队列解决，阻断自动生产。
- 框架整改：重任务准入不足时仅在最近120秒已有成功Comfy释放，或只读确认Comfy运行/等待队列均空后主动释放，才进入最长60秒`waiting_memory`；每秒复核任务可运行性、心跳和内存，满足后恢复processing，超时真实失败。Comfy有活动任务、队列查询失败或非释放窗口的真实不足继续立即拒绝。
- 开发验证：覆盖近期释放后恢复、服务重启丢失时间戳后空闲Comfy主动释放、等待期间取消检查、60秒有限超时及非释放窗口立即拒绝；关联`139 passed`、完整unit`570 passed, 9 subtests passed`无skip，Python编译、Vue typecheck、83模块构建与文档门禁通过。
- 正式验证：8787重载至PID`83178`后，从已完成信件继续同一串行队列；此前被42GB门禁拒绝的`costume_0153a6e9_daily@v1`成功，随后`林婉清-daily服装`也成功并自动进入场景，连续三道具无内存误拒绝。场景后续无心跳为下一独立问题，不属于本BUG。
- 独立软件测试：通过。关联`139 passed`、完整unit`570 passed, 9 subtests passed`无失败无skip，编译、typecheck、83模块构建和文档门禁通过；正式项目无活动图片任务、无子进程、Ollama为空。
- 最终只读稽查：通过。accelerator序列化池保证空闲检查与释放无并发重任务；近期/重启释放窗口、waiting_memory心跳与取消、有限超时和真实不足失败关闭均成立，正式连续道具及资源终态通过。
- 下一状态：已关闭；M9.198继续真实全链。

### BUG-20260811-051：道具提示词与无文字硬门禁互相冲突

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：正式项目“信纸/信件”连续两批均在有限候选后失败，错误为`道具图未通过：画面出现文字或招牌，请继续生成`，任务与模型均正常释放。
- 首个事实：持久`image_prompt`同一段同时要求`表面有娟秀笔迹`与`无文字干扰`；后端又对全部道具强制`no_text_or_signage`，生成目标与验收契约不可同时满足。
- 风险：资产提取模型只要给无文字类道具写入正向字迹/标签/铭文描述，后续有限重试仍沿用矛盾提示，形成确定性失败并阻断全链。
- 框架整改：道具基准图和变体进入任一provider前统一拆分提示子句，移除正向笔迹、字迹、文字、书法、铭文、刻字、标签、标牌、招牌、logo等字形线索，保留同句非文字材质/形态片段和原有否定约束，并追加确定性无字硬约束；有限重试复用净化后的indexed prompt。
- 开发验证：冲突样例确认移除“娟秀笔迹”且保留“指纹压痕/边缘微卷/无文字干扰”；关联`135 passed`、完整unit`566 passed, 9 subtests passed`无skip，Python编译、Vue typecheck、83模块构建与文档门禁通过。
- 正式验证：8787空闲重载至PID`80071`后，同一正式项目再次生成“信纸/信件”成功，资产卡出现45°基准图和“就要这张”，不再触发文字质检失败；后续道具的独立内存保护拒绝不属于本BUG。
- 独立软件测试：通过。关联`135 passed`、完整unit`566 passed, 9 subtests passed`无失败无skip，编译、typecheck、83模块构建及文档门禁通过；正式道具为`waiting_confirmation`、媒体URL存在、error为空，Ollama为空。
- 首轮只读稽查退回：否定检测只要子句存在任意“无/禁止”就整体放行，例如“带铭文且无人”会因无关的“无人”保留正向铭文。整改要求逐个字形cue判断其紧邻前后是否为直接否定，无关否定不得旁路。
- 稽查整改开发验证：每个字形cue分别检查前12字符及后16字符的直接否定；支持“禁止出现任何文字”“文字不得出现”等有限组合，“带铭文且无人”移除铭文且保留后续金属纹理。关联`135 passed`、完整unit`566 passed, 9 subtests passed`无skip，编译、typecheck、83模块构建及文档门禁通过。
- 稽查整改独立软件复测：通过。关联`135 passed`、完整unit`566 passed, 9 subtests passed`无失败无skip，编译、typecheck、83模块构建和文档门禁通过；正式产物仍为waiting_confirmation且资源为空。
- 最终只读复稽查：通过。逐cue直接否定覆盖前后短语与有限修饰，无关“无人”等否定不能旁路正向字形；正式产物、重试、资源释放和复测证据一致。
- 下一状态：已关闭；M9.198继续真实全链。

### BUG-20260811-050：资产生成失败状态和错误未投影到资产卡

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：BUG049关闭后在正式项目资产页点击“继续生成图片”；首个道具“信纸/信件”先显示正在生成，约一分钟后批次停止，卡片回到“等待生图”且没有失败原因或全局提示。
- 首个事实：服务端项目持久数据已正确保存该道具`status=failed`和`error=道具图未通过：画面出现文字或招牌，请继续生成`，assets顶层也保存同一错误；浏览器投影却显示pending文案并隐藏错误，属于前端状态/错误投影分裂，不是模型卡死。
- 风险：真实质量门禁失败被界面伪装为未开始，用户无法判断失败原因，重复点击只会盲目重跑并阻断自动资产队列。
- 根因：`recoverCompletedAssetImages`轮询收到真实failed时把条目状态写成pending，随后批次聚合无法找到failed profile；`UnifiedAssetCard`又把`item.error`仅放在手动展开的简介层，卡片主体无失败可见性。
- 框架整改：结果回填保留后端failed终态和脱敏错误，只有显式重试才清除；人物、道具、场景共用的`UnifiedAssetCard`在主体持续展示卡片级错误，简介层保留详细上下文。
- 开发验证：关联`134 passed`、完整unit`565 passed, 9 subtests passed`无skip，Vue typecheck、83模块构建和文档门禁通过。
- 首轮独立软件测试退回：代码回归`134 passed`、完整unit`565 passed, 9 subtests passed`，正式页面错误正文已持续显示；但无图占位仍显示“等待生图”，与failed终态矛盾。整改要求共享卡依据slide failed显示“生成失败”。
- 退回整改开发验证：共享卡无图占位依据slide failed显示“生成失败”；关联`134 passed`、完整unit`565 passed, 9 subtests passed`无skip，typecheck、83模块构建和文档门禁通过。
- 独立软件复测：通过。正式项目失败道具同时显示“生成失败”和`道具图未通过：画面出现文字或招牌，请继续生成`；关联`134 passed`、完整unit`565 passed, 9 subtests passed`无失败无skip，typecheck、83模块构建和文档门禁通过。
- 最终只读稽查：通过。后端failed结果保持终态和脱敏错误，只有显式重试清除；共享资产卡依据slide状态显示“生成失败”，并在主体持续显示卡片级错误。正式页面、持久状态与测试证据一致。
- 下一状态：已关闭；M9.198继续真实全链。

### BUG-20260811-049：资产阶段完成后被晚到前端投影覆盖为无执行者运行态

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：正式项目分镜脚本生成并确认后自动提取资产；约两分钟后项目`assets.status=generating`、LangGraph `assets=running`且时间戳不再前进，但统一任务、阶段租约、资源池和Ollama均为空，资产人物/场景数据已经存在。
- 根因：公开项目阶段写入直接调用内部`_write_project_stage`并同步改写ledger/LangGraph，缺少服务端generation围栏；恢复入口又把“已有预览卡片/项目status”误当资产权威成功，资产页主按钮可绕过LangGraph直接生图。首次真实恢复还暴露9B资产JSON截断没有有限重试。
- 风险：任一已完成/待确认阶段可被排队或晚到的客户端`generating`快照倒退为无owner运行态，刷新后永久等待，并阻塞后续阶段。
- 框架整改：公开`/api/projects/stage`改为projection-only，只保存界面数据且不写ledger/Graph；服务端generation终态拒绝晚到running/queued投影倒退。分镜入口和资产页批量入口均同时读取项目投影与LangGraph assets状态，只有`pending_confirmation/completed`才允许基准图；失败恢复必须重新执行正式assets。资产JSON解析失败只允许一次结构化重试，仍失败真实关闭。
- 开发验证：动态覆盖晚到generating不能改Graph/终态、两个前端入口双权威门禁及一次有限JSON重试；关联`110 passed`，完整unit在显式Node运行时`565 passed, 9 subtests passed`无skip，Vue typecheck、83模块生产构建、Python编译与文档门禁通过。
- 正式验证：服务重启回收无owner assets后，从分镜入口重试；首个generation 2真实返回截断JSON并failed，加载整改后generation 3一次重试成功，Graph assets保持`pending_confirmation`且generation=3，随后才启动人物基准图。人物0°图完成后启动下一资产；主动暂停后任务、租约、Ollama均释放，assets未被晚到图片投影倒退。
- 独立软件测试：通过。关联`111 passed`、完整unit`565 passed, 9 subtests passed`，均无失败无skip；Vue typecheck、83模块生产构建、Python编译与文档门禁通过。正式任务、租约、Ollama为空，Graph assets仍为generation 3 `pending_confirmation`，未被图片暂停投影倒退。
- 首轮只读稽查退回：generation终态保护仅覆盖status/error；晚到`generating`快照仍可用旧预览资产集合覆盖正式提取后的完整census，导致状态正确但人物/场景/道具丢失。整改要求终态下资产投影按名称合并并保留服务端现有集合，非资产阶段拒绝整个晚到数据快照。
- 稽查整改开发验证：受保护的assets晚到投影强制进入既有名称合并路径，保留正式census中仅服务端存在的人物/场景/道具及媒体字段；非assets阶段保留当前完整权威数据。动态夹具覆盖旧快照仅含人物、正式状态另含场景/道具的删除风险；关联`111 passed`、完整unit`565 passed, 9 subtests passed`，Vue typecheck、83模块构建、Python编译及文档门禁通过。
- 稽查整改独立软件复测：通过。关联`111 passed`、完整unit`565 passed, 9 subtests passed`，均无失败无skip；Vue typecheck、83模块构建、Python编译和文档门禁通过。
- 最终只读复稽查：通过。公开projection-only不写ledger/Graph；受保护assets晚到快照按名称合并并保留正式census独有项及现有媒体字段，非assets保留当前完整权威数据；generation、生命周期和Graph均不倒退。软件复测证据完整，无阻断项。
- 下一状态：已关闭；M9.198继续真实全链。

### BUG-20260811-048：前端显示大纲已确认但权威工作流未完成

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：M9.198新项目真实大纲完成后点击“生成剧本”，界面提示“故事大纲已确认”，随即剧本入口返回`previous stage is not completed: outline`；项目stage_state为`confirmed`，ledger存在`completed`但无confirmation的outline scopes，LangGraph仍为`pending_confirmation`。
- 根因：非upscale的公开`upsert_projection`直接调用权威`upsert`，允许不可信UI把scope lifecycle写成`completed`并携带generation/confirmation；前端确认循环却只对服务端返回的`pending_confirmation`调用确认接口，导致无确认的伪completed无法推进LangGraph，并与项目投影分裂。
- 风险：大纲、剧本、分镜及其他非增强scope均可出现伪完成、确认断链或客户端伪造权威字段，下游永久阻塞或错误推进。
- 框架整改：所有非upscale公开projection统一剥离客户端confirmation、generation及production/audit evidence；请求completed在无当前精确确认时降为pending_confirmation，必须走服务端确认接口；同fingerprint+audit batch的既有确认由服务端保留且不允许UI降级，新指纹自动清确认并重新等待确认。
- 开发验证：伪generation 99/100、伪confirmation/证据、首次completed、同代降级和新指纹重确认动态通过；确认接口唯一推进LangGraph。关联`135 passed`、完整unit`564 passed, 9 subtests passed`、关键编译、文档门禁和diff-check通过。
- 正式验证：8787重载后，既有项目stage_state confirmed、ledger completed无confirmation、LangGraph pending三方坏状态经UI同步自动收敛；outline全部权威scope带confirmation，LangGraph outline completed；真实32B剧本完成，script亦completed并推进storyboard，任务与模型均释放。
- 独立软件测试：通过。关联`135 passed`、完整unit`564 passed, 9 subtests passed`，均无失败无skip；关键Python编译、文档状态门禁及限定diff-check通过。正式outline/script确认、工作流推进及资源空状态复核一致。
- 最终只读代码稽查：通过。整改位于所有非upscale公开projection共用边界；不可信confirmation/generation/权威证据被剥离，completed必须服务端确认，同代确认不可被UI降级，新指纹清确认。事务锁、批量替换保护、正式旧数据收敛、真实剧本和无skip回归证据完整。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭；M9.198继续分镜脚本至增强导出，BUG039—041保持排队未分析。

### BUG-20260811-047：停止阶段后整个生产工作流无法重新生成

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：新项目大纲真实生成运行约1分钟后点击暂停，界面进入“已停止生成，可保留现有内容后重新生成”；资源和32B模型释放后再次点击“生成大纲”，正式接口返回`workflow is cancelled`。
- 根因：阶段停止把统一LangGraph工作流写为cancelled终态，但重新生成入口没有按新generation显式重新激活同一项目工作流，前端恢复承诺与服务端状态机不一致。
- 风险：任何阶段主动停止后项目永久无法继续生产，只能新建项目或改库，违反停止、恢复、局部重做与可恢复终态门禁。
- 框架整改：统一工作流`begin`只允许目标阶段携带严格大于已取消代际的新generation重新激活；同代、generation 0及旧代晚到继续失败关闭，新代启动后状态回到running并保留generation围栏。
- 开发验证：取消generation 4后，同代与generation 0均被拒；generation 5可恢复，随后旧generation 4取消响应被拒。定向`120 passed`、完整unit`558 passed, 9 subtests passed`、关键Python编译通过。正式8787重载后，同一project_id从持久`cancelled`点击生成，创建新outline generation，32B完成真实大纲并自动卸载；全程仅一个重负载任务。
- 独立软件测试阻塞：显式Node运行时下定向`120 passed`且无skip，关键Python编译与diff-check通过；完整unit为`3 failed, 555 passed, 9 subtests passed`，三项失败全部来自并行BUG038的唯一索引为“开发完成，待独立软件测试”而Tracker首状态仍为“已关闭（最终稽查通过）”。连续只读核验未收敛；测试身份未改BUG038，按门禁不提交稽查。
- 独立软件复测：通过。并行BUG038状态收敛后，显式Node运行时定向`120 passed`、完整unit`560 passed, 9 subtests passed`，均无失败无skip；关键Python编译、文档状态门禁及限定diff-check通过。正式恢复证据中的任务、模型均已释放。
- 首轮只读稽查退回：业务增量、generation恢复与晚到围栏未发现阻断；唯一问题是当前状态索引使用未注册口径“软件测试通过，待代码稽查”，导致文档门禁失败。主线仅改为规范口径“软件测试通过，待只读稽查”，不改业务代码。
- 稽查整改独立复测：文档状态门禁通过；完整unit`560 passed, 9 subtests passed`，无失败无skip，业务代码未变。
- 最终只读复稽查：通过。cancelled工作流只允许严格更新的目标stage generation重新激活；同代、零代及旧代晚到均失败关闭，正式服务重启后的真实32B生成、任务终态与模型释放证据完整；状态索引口径已合法且一致。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭；M9.198继续真实全链，BUG039—041保持排队未分析。

### BUG-20260811-046：新项目创建后显示旧项目全阶段内容

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.198
- 正式复现：在正式5173工作台从已有项目创建新项目`M9.198真实全链验收-20260811`；服务端新project_id `83eaa695-0a31-4119-aa94-060c232053fd`的`stage_state`为空，但界面持续显示旧项目已完成大纲/剧本/分镜标记及3人物/1场景资产。
- 根因：项目创建成功后只执行`abortProjectWork`、切换project store并关闭弹窗，没有调用`loadProjectFlowState`；各阶段响应式投影因此保留旧项目值，直到未来某次显式选择项目才重置。
- 风险：用户可在新项目界面对旧投影执行确认、生成或持久化，造成跨项目旧内容污染和伪造全链完成事实。
- 框架整改：新增统一十阶段投影同步清空入口，每次项目流程加载先清空大纲至导出的全部响应式状态，再按固定project/session顺序恢复；创建/编辑保存切换store后必须等待新项目流程及资源/任务/版本加载完成，旧会话晚到仍由session围栏拒绝。
- 开发验证：正式旧项目人物3项，切换空新项目的立即帧与稳定帧均无旧人物/资产，最终人物0项且提示先生成分镜；新项目后端stage_state保持空。定向与文档contract`45 passed`、完整unit`556 passed, 9 subtests passed`，Vue typecheck和83模块构建通过。
- 关联测试基础设施整改：文档状态夹具不再硬编码已移出索引的M9.196/BUG044，动态选取当前成对里程碑/BUG，保证下一工作项仍能检测重复、冲突、未知状态与Tracker反向完备。
- 独立软件测试：通过。正式5173连续三轮旧项目→空新项目切换，旧项目均为3人物，新项目立即帧/稳定帧均零旧人物和资产；后端新project_id的stage_state持续为空。定向/contract`45 passed`、完整unit`556 passed, 9 subtests passed`无skip，Vue typecheck及83模块构建通过。
- 最终只读代码稽查：通过。统一清空覆盖大纲至导出十阶段且发生于异步恢复前；创建/编辑保存等待新project/session加载，旧会话晚到由既有session围栏拒绝。正式动态与后端空状态证据一致，文档当前索引驱动夹具不存在固定里程碑依赖。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭；M9.198继续真实全链，BUG039—041仍只排队。

### BUG-20260811-045：可观测数据仅驻留进程内且无可插拔导出与告警

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.197
- 复现：`MetricsRegistry`与`TraceRecorder`仅保存Python内存对象，服务退出后证据消失；没有可抓取指标格式、统一exporter或可执行告警，运行手册要求无法形成机器证据。
- 根因：可观测模块停留在接口原型，日志sink、指标和trace各自封闭，未定义与业务解耦的导出协议、持久边界及告警求值边界。
- 框架整改：新增统一`RecordExporter`协议、空/组合/JSONL/Prometheus textfile实现；JSONL逐条flush+fsync，指标快照临时文件原子替换；指标标签规范化、counter单调，span和alert可绑定request/trace；嵌套敏感字段拒绝导出。默认空exporter保持旧调用兼容。
- 开发验证：持久日志/指标/span三类导出、Prometheus抓取文本、队列积压告警、关联ID、嵌套秘密拒绝、标签规范化及counter单调专项`5 passed`；关键Python编译通过。未启动模型或正式任务。
- 边界：本BUG只关闭可插拔持久导出和故障告警底座；全链request/trace贯穿、仪表盘和正式告警演练仍在剩余清单，不得伪报完成。
- 独立软件测试首败：可观测专项`5 passed`、events关联`18 passed`及额外动态均通过；全unit为`1 failed, 520 passed, 1 skipped, 9 subtests passed`。失败用例只将DuckDuckGo/Bing模拟为空，未隔离现行注册表新增的Google News/Google后备，真实网络返回结果后自然不抛“所有provider失败”；属于测试夹具未覆盖现行五provider注册表，而非失败关闭实现回归。按门禁退回同步测试后重跑。
- 主线整改：失败关闭用例同步隔离DuckDuckGo、Bing、Google News和Google全部免Key后备；测试现在精确表达“现行全部可用provider均无结果”，未修改或放宽生产失败关闭实现。定向`14 passed`，全unit`521 passed, 1 skipped, 9 subtests passed`，文档状态检查和Python编译通过。
- 第二轮独立测试首败复现：指标labels在结构化快照中转换为二元list后，原递归秘密检查只识别Mapping键，`authorization=TOP-SECRET`可进入JSONL，Prometheus导出同样无入口拦截。整改在labels规范化、structured snapshot及两个持久exporter入口统一拒绝敏感二元键；新增直接构造恶意快照防绕过测试。专项`6 passed`；全unit扩大运行时出现3项并行文档事实源冲突及1项已知资源池排队瞬态失败，与本整改无调用关系，未据此宣称全量通过。
- 冻结快照主线自检：可观测与联网搜索定向`18 passed`；完整unit`554 passed, 1 skipped, 9 subtests passed`；文档状态检查、关键Python编译和限定diff-check通过。BUG首状态已与唯一索引同步为待测试；该结果不替代独立软件复测。
- 下一状态：待独立软件复测。
- 最新独立软件复测：通过。可观测、联网搜索失败关闭及Node动态关联`41 passed`；完整unit`555 passed, 9 subtests passed`且无skip。敏感二元标签在注册、结构化快照、JSONL与Prometheus四层均拒绝；持久JSONL、原子textfile、counter单调、request/trace关联及队列积压告警通过。关键Python编译通过，临时测试目录自动清理，未启动模型或修改正式数据。下一状态：待只读稽查。
- 最终稽查退回：`MetricsRegistry.increment`只检查`value < 0`，NaN/+Infinity可绕过并持久化；标签键未校验Prometheus语法。隔离复现实际输出`requests_total{bad-key="x"} nan`，违反counter单调和可抓取文本契约。
- 稽查整改：统一有限数值校验拒绝非数字、bool、NaN和±Infinity；标签键强制Prometheus规范。Prometheus exporter对手工快照再次独立校验指标名、标签结构/名称与有限数值，禁止绕过注册表。开发专项`6 passed`、完整unit`555 passed, 9 subtests passed`、复现脚本、文档门禁、Python编译及diff-check通过；下一状态为待独立软件复测。
- 同根因扩大整改：指标快照语义校验抽为JSONL与Prometheus共用门禁，手工NaN/非法指标名/非法标签/畸形集合在任何持久exporter写入前统一拒绝，Composite首个JSONL也不会留下部分非法证据。专项`6 passed`、完整unit`555 passed, 9 subtests passed`、文档门禁、编译与diff-check通过。
- 稽查整改独立软件复测：通过。注册表、JSONL、Prometheus、Composite、敏感标签及关联入口`41 passed`；完整unit`555 passed, 9 subtests passed`且无skip，关键Python编译通过。临时文件自动清理、正式数据零修改；下一状态为待只读复稽查。
- 最终只读复稽查：通过。有限数值、指标名、标签结构/名称、敏感字段及手工快照语义由注册表与JSONL/Prometheus共享门禁覆盖；Composite在首个持久写入前失败关闭，无部分非法证据。边界仍明确不宣称全链trace与正式仪表盘已完成。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭。

### BUG-20260811-044：文档当前状态存在多事实源

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.196
- 复现：四份职责文档同时保留多轮“待测试/待稽查/已完成”，按搜索结果或尾部追加项判断会把历史状态误作现行状态。
- 根因：计划、Tracker、进度和记忆均承担了当前状态裁决，缺少机器可检查的唯一索引、历史边界和重复编号门禁。
- 框架整改：新增`docs/product/当前开发状态.md`作为唯一当前状态索引；新增标准库检查器，拒绝重复ID、未知状态、BUG详情缺失、索引与BUG首状态冲突及第二事实源声明；历史证据原样保留。
- 独立软件测试退回：首版缺少Tracker活动项反向完备性、本地Markdown链接检查、跨文档同编号多现行状态冲突判定及统一contract测试入口。
- 整改：补充上述四项门禁；“历史/已被覆盖”作为唯一冲突豁免，新增确定性失败矩阵并由pytest自动收集。
- 第二轮独立软件测试退回：secondary组合行只提取首个M编号，`M9.196 / BUG044`中的BUG简写未独立归一，也未逐项与索引状态族比较；追加`BUG044（已关闭）`未被拒绝。
- 第二轮整改：组合行分别提取全部M/BUG，BUG三位简写按索引唯一后缀归一；每项先与索引状态族比较，再执行跨文档重复状态检查。MainDev、项目进度、项目记忆参数化覆盖M与BUG冲突及历史豁免。
- 整改自检：文档门禁通过；专项与contract `18 passed`，Python编译和diff-check通过。
- 第二轮独立软件复测：通过。专项与contract `18 passed`；Dev_MainDev、项目进度、项目记忆三文档组合`M9.196 / BUG044`对M与BUG分别报冲突，显式历史/已被覆盖豁免，动态探针`6/6`；Tracker活动项反向完备、坏本地链接、pytest contract入口和BUG简写归一均通过。Python编译与限定范围diff-check通过，未修改业务代码或启动模型。
- 最终稽查退回：Tracker冲突测试曾依赖BUG044处于特定生命周期；状态流转后可能未真正构造相反状态，产生假绿。
- 最终稽查整改：测试按BUG编号动态定位section边界和首个状态行，断言目标存在、替换实际发生且状态族相反；参数化覆盖待测试、待稽查、已关闭，并保证不修改相邻BUG。
- 整改自检：专项与contract`21 passed`，全部contracts`40 passed, 51 subtests passed`；文档门禁、Python编译和diff-check通过。
- 最终独立软件复测：通过。专项与contract`21 passed`；全部contracts`40 passed, 51 subtests passed`；完整unit`555 passed, 9 subtests passed`且无skip，关键Python编译通过。测试身份未修改代码、配置或正式数据。
- 最终只读复稽查：通过。Tracker夹具按目标BUG section动态定位首状态，强制断言替换发生且状态族相反；待测试、待稽查、已关闭三类生命周期和相邻条目保护均成立。唯一索引、双向完备、组合编号归一、历史豁免、链接与contract门禁证据完整。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭。

### BUG-20260811-041：历史对话图片资源仍显示

- 状态：待处理（排队，未分析）
- 用户现象：对话框仍显示两张已属于旧资源的人物图片。
- 串行约束：等待 BUG-20260811-038 完整闭环并经用户确认后处理。

### BUG-20260811-040：生成成功的图片未显示

- 状态：软件测试通过，待只读稽查
- 用户现象：图片生成后界面不显示结果。
- 串行约束：等待前序问题完整闭环并经用户确认后处理。
- 根因复核：该排队现象对应旧前端只消费发起请求的即时响应；页面刷新、服务恢复或原请求连接中断后，后端job即使`completed`并持有媒体URL，资产baseline/角度投影仍可能保持generating或空URL。当前框架已由BUG038后续整改加入`recoverCompletedAssetImages`两秒权威终态对账，因此本项不再需要另造恢复链。
- 增量闭环：补充直接执行当前正式恢复函数的Node动态回归，同一矩阵同时覆盖云长老baseline completed与人物variant completed：从job结果回填URL、转`waiting_confirmation`、触发展示节奏并持久化一次；variant失败仍维持明确失败终态。未修改用户并行前端实现。
- 开发验证：显式Node运行时动态恢复用例通过；扩大恢复/图片关联`52 passed, 1 failed, 1 deselected`，唯一失败为用户并行删除局部修复入口后的旧静态断言，与成功媒体投影/显示链无关，未计作本BUG通过证据。
- 独立软件测试：通过。冻结提交`56dc605`以显式Node运行时执行baseline/variant completed和variant failed正式函数动态矩阵及文档状态，共`21 passed`，无失败无跳过；测试身份未修改用户前端现场或正式数据。

### BUG-20260811-039：云长老人物图无法生成

- 状态：已关闭（最终只读稽查通过）
- 用户现象：云长老生成返回 `capability provider has in-flight invocations: image.variant.qwen/comfy-qwen-image-edit-2511`。
- 串行约束：等待前序问题完整闭环并经用户确认后处理。
- 正式根因：能力注册表是进程级单例，但兼容API可被多个模块身份装载，每个模块各自持有`BUILTIN_PRODUCTION_CAPABILITIES_INSTALLED=False`和安装锁。后装载模块发现同名builtin后使用`replace_provider=True`刷新；若另一人物任务正在Qwen调用，热插拔保护正确拒绝替换，却把正常并发生成错误终止。
- 框架整改：能力注册表新增原子`register_once`，完整复用注册参数校验；同一进程生命周期内同能力/provider只安装一次，重复模块安装原样复用现有definition和handler，不执行替换、卸载或健康翻转。builtin安装统一使用该原语；代码升级仍通过进程重启加载新实现，运行中provider热插拔保护保持不变。
- 开发验证：动态线程在`image.variant.qwen`真实inflight计数为1时再次`register_once`，不抛热替换错误、不改变inflight或handler；原调用及后续调用均返回原provider。生产控制面与文档状态`104 passed`，无失败无跳过。扩大图片恢复关联为`1 failed, 156 passed`，唯一失败读取用户并行删除的前端`asset_phase:"repair"`入口，与本后端注册原语无调用关系，未计作本BUG通过证据。
- 独立软件测试：通过。冻结提交`d01c81e`复跑能力安装/并发/inflight保护、生产控制面和文档状态`104 passed`，无失败无跳过；Python编译通过。测试身份未修改用户前端现场、依赖授权或正式运行数据。
- 最终只读稽查：通过。`register_once`在同一RLock临界区内完成存在性判断和首次注册，重复调用先完整校验参数再复用definition，不修改handler、metadata、健康或inflight；真实`replace`、`replace_provider`和`unregister`路径仍原样拒绝活动provider。builtin安装不再包含热替换参数，根因闭合且未削弱架构v2.2保护。
- 关闭时间：2026-08-12（Asia/Shanghai）。下一状态：已关闭；进入BUG040只读复现与根因分析，保留用户并行前端现场。

### BUG-20260811-038：人物全身图顶部留白低于8%仍被放行

- 状态：已关闭（最终只读复稽查通过）
- 关联任务：M9.193
- 复现：正式苏璃0°正面全身图发顶接近画面顶边，实际明显低于8%，但结果携带归一标记并通过机器验收。
- 根因：构图归一器使用 YOLO 人体检测框估算头脚边界；该框可能从发顶下方开始。验收器又把 `normalized_variant_margins=true`直接转换为顶部8%和底部3%通过，未核验真实像素数值。
- 框架整改：归一器改用 GrabCut 人物可见轮廓细化检测框，统一按9%顶部、5%底部容差重排至928×1664；返回可持久化的像素边界及四边比例。验收器只接受同时具备归一标记、数值证据和8%/3%阈值的结果，所有全身角度统一强制`deterministic_full_frame`，旧布尔标记不能放行。
- 开发验证：同一正式失败旧图经新归一器得到顶部`0.089960`、底部`0.050040`，输出928×1664且视觉无接缝；新增数值门禁与轮廓归一测试。定向`34 passed, 1 skipped`，完整单元测试`503 passed, 1 skipped, 9 subtests passed`；Python编译、Vue typecheck及83模块生产构建通过。正式任务、三资源池、Ollama与ComfyUI均为空后受控重载8787，新PID`55404`健康并加载当前实现。
- 首轮稽查：不通过。GrabCut异常被宽泛捕获后退回YOLO框，仍可产生`yolo_person_box_fallback`并被数值门禁接受；测试未覆盖轮廓识别异常的失败关闭路径。
- 稽查整改：删除全部YOLO确定性证据回退。GrabCut、连通域或轮廓质量任一失败均抛`foreground_segmentation_failed`，由既有候选循环删除失败图片并重生成；验收额外强制`source=grabcut_person_silhouette`，旧回退证据即使数值满足也拒绝。
- 整改验证：新增强制GrabCut异常执行测试、YOLO回退证据拒绝测试及源码无回退门禁。专项`3 passed`；真实旧图连续两次归一顶部`8.9960%/9.0084%`、底部`5.0040%/4.9916%`；图片关联`116 passed, 3 subtests passed`。完整单元扩展为`521 passed, 1 failed, 9 subtests passed`，唯一失败仍为独立联网搜索状态测试，与人物构图增量无调用关系。Python编译、文档状态检查、Vue typecheck及83模块构建通过；正式8787已在全资源空闲时重载为PID`58574`。
- 二次稽查：不通过。P1：正式0° baseline路径的轮廓异常在候选重试之前逸出，未删除失败候选，也未执行有限重生成；原异常测试只覆盖归一器。
- 二次稽查整改：新增`_prepare_character_full_frame_candidate`统一归一失败的物理文件清理，新增`_run_character_full_frame_candidate_loop`统一有限候选生命周期；正式baseline调用共享循环，最多3次、成功返回实际次数、末次保留可定位错误，失败候选不残留。动态测试覆盖连续两次归一失败后第三次成功、provider重试序列`[2,3]`、失败候选清理`[1,2]`及三次全失败明确终态。关联`118 passed, 1 skipped, 3 subtests passed`，Python编译、Vue typecheck和83模块构建通过。全单元`537 passed, 2 failed, 9 subtests passed`，两项失败均由并行文档当前状态冲突引起，与本修复无直接依赖。
- 最新独立软件测试：通过。真实`ThreadingHTTPServer + Handler`向`/api/characters/generate` POST的参数化测试2/2通过：前两次轮廓失败、第三次成功返200且job为`completed`；三次全失败返502且job为`failed`。provider严格调用3次，失败图片全部删除，成功链只保留第3张。关联`120 passed, 1 skipped, 3 subtests passed`，后端编译通过；测试身份未修改项目文件。
- 最终独立代码稽查：通过。稽查独立实跑正式HTTP/Handler参数用例，确认GrabCut失败关闭、旧回退证据拒绝、失败候选物理清理、最多3次生成及200/completed、502/failed终态均成立。BUG045的文档状态冲突属独立并行问题，不影响BUG038限定结论。
- 用户真实页面复现：原关闭结论撤销。云长老真实第三张的确定性姿态为偏航`0.41°`，顶/底安全区`8.9867%/5.0133%`，但VLM误判`correct_orientation=false`；同一VLM返回还缺失`plain_background`，而 baseline caller 将两者当作必需字段，导致确定性合格图连续被误杀并在界面暴露截断JSON。
- 重开整改：`front_full`方向以实际人脸姿态确定性结果为准，不再与VLM主观布尔值做AND；0° baseline硬门禁收敛为`correct_orientation + required_928x1664 + deterministic_full_frame`，单人和头脚由同一GrabCut/YOLO候选准备链证明，背景与其他主观项保留证据及人工“就要这张”门禁；最终错误只返回中文硬门禁摘要，不再暴露原始JSON。
- 真实端到端自检：正式9B直接HTTP生成云长老一次成功，随后在真实浏览器资产卡点击“重新生成”，页面从“此图正在生成”转为显示`云长老0°正面全身`图与“就要这张”。最终job`completed`、第1次通过，顶/底安全区`8.9992%/5.0008%`，Comfy/Ollama队列全空。关联回归`128 passed, 1 skipped, 3 subtests passed`。
- 重开后独立软件测试：通过。文档状态门禁通过；正式HTTP Handler参数矩阵`10 passed`，包含两项目内VLM返回原始JSON且连续3次失败时返502、错误不含`{`、仅中文硬门禁摘要、job failed且三张候选全删除；第1/2/3次成功及轮廓三次失败同样通过。关联`131 passed, 3 subtests passed`，0 failed/0 skipped；真实9B job、浏览器IMG 928×1664显示及资源释放证据均复核通过。
- 下一状态：待独立代码稽查。
- 最终稽查再次退回：真实浏览器曾显示的job仍为`completed`，但后续排队重生成先调用`purgeGenerated`删除其物理文件，旧job及历史快照继续引用该URL，刷新后返回404。根因是媒体发布采用“先删旧图、再生成新图”，不具备代际一致性。
- 媒体生命周期框架整改：baseline重生成不再调用资产级预清理；旧成功媒体作为不可变版本保留，新图生成成功并持久化新URL后才成为当前投影，失败则继续保留上一张可用图。服务恢复新增完成态媒体存在性核验，缺失文件的`completed`任务自动降级为明确`failed`，禁止假完成。新增重启时缺失/存在媒体双向测试；关联专项`92 passed, 1 skipped, 3 subtests passed`，后端编译通过。
- 角度图假运行同根因整改：正式任务`89215588...`已被服务重启回收为failed、Comfy队列为空，但恢复轮询只处理`!item.image_url`的baseline，并在已有基准图时跳过整个人物，导致左45°角度投影永久停在generating。现将baseline及全部`detail_assets`纳入统一2秒终态对账，按generation nonce和角度序号读取权威job；completed回填URL，failed写入角度及人物终态，页面不再伪运行。轮询触发条件覆盖item与variant generating。专项`77 passed, 1 skipped`、编译、Vue typecheck及83模块构建通过；真实页面刷新后苏璃左45°从“此图正在生成”收敛为“生成失败”，显示可重新生成，Comfy队列保持为空。
- 测试退回补证：新增直接执行正式`recoverCompletedAssetImages`源码的Node动态矩阵；已有baseline时，variant completed会回填URL、转waiting_confirmation、持久化一次并触发完成展示，variant failed会同步variant/item failed并持久化一次，动态`1 passed`。扩大回归受并行任务正在修改的Comfy内存等待测试2项`StopIteration`阻断；该代码不属于BUG038增量，未越权覆盖，待冻结后重新独立复测。
- 并行改动冻结后主线重跑：角度终态动态矩阵及图片恢复/FIFO/任务运行关联组合`82 passed`，0 failed/0 skipped；文档门禁通过，准备重新提交独立软件测试。
- 用户确认当前角度已正确后，角度链冻结为版本化硬基线：左右三分之四提示目标35°、确定性偏航左`+30°—+60°`/右`-60°—-30°`且滚转≤7°、角度LoRA权重0.35、Lightning 4步LoRA权重1.0、4步、CFG 1.0；90°、180°和0°继续执行既有严格方向门禁。生产规范明确禁止未经真实六格回归、独立测试和稽查单独改动上述任一项。
- 四肢验收增量：全身图统一要求手、脚及全部可见肢体/手指/脚趾无粘连、缺失、多余、重复、断裂、融化或异常连接；左右45°、90°、180°及0°baseline均把三个解剖布尔字段列为硬门禁，失败候选删除并有限重生成，不能进入“就要这张”。baseline重试提示同步要求完整分离的四肢。专项`36 passed`、Python编译和文档状态门禁通过，8787在任务、三资源池和Comfy队列全空时重载健康。
- 独立测试首轮退回整改：旧角度断言已同步为共享解剖门禁；新增正式HTTP Handler动态矩阵，覆盖左45°、右45°、90°、180°各自的`hands`、`feet`、`no_fused`任一单字段false，以及四姿态全真正常链。每个失败样本严格生成2次、两张候选均物理删除并返回502；全真样本首张返回200且保留。共享`_character_variant_required_checks/_character_variant_verdict_passes`成为生产与测试唯一门禁定义。关联`60 passed, 2 skipped`，Python编译和文档门禁通过，待独立复测补齐Node环境项。
- 独立复测二次退回整改：0°baseline正式Handler矩阵拆分为`hands=false`、`feet=false`、`no_fused=false`三个单字段用例，各自连续3次失败、三张候选全删、502且持久job failed；不再用两个字段同时false替代单项证明。开发关联`64 passed, 2 skipped`，编译和文档门禁通过，待独立测试补齐Node环境后复测。
- 最终独立软件复测通过：0°baseline正式Handler矩阵`19 passed`，四个全身角度×三项解剖单字段及全真链全部动态通过；扩大关联`116 passed`，规范/服装/空场景补充`30 passed, 3 subtests passed`，合计146项及3个子测试，0失败0跳过。角度硬基线与文档一致，编译、文档门禁及8787/三资源池/tasks/Comfy/Ollama空闲终态通过。下一状态：待独立代码稽查。
- 最终只读复稽查：通过。0°基准由正式Handler的`baseline_required_checks`强制手、脚及四肢/指趾三项解剖门禁，左右45°、90°、180°由共享required-check契约强制；失败候选统一有限重试、物理删除并落明确failed，成功候选才可发布。绑定显式Node运行时复跑正式Handler、候选生命周期、前端恢复、FIFO、持久投影和规范关联为`117 passed, 3 subtests passed`，0失败0跳过；未发现旧媒体覆盖、伪终态或姿态漏项。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭。

### BUG-20260811-037：分镜已自动生图却仍提示手动上传并清空成品

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.191
- 原因：`enterAssetGeneration`仍保留旧上传式流程，进入资产页会清空全部媒体、角度、确认状态并提示上传四视图；与当前逐集自动提取和自动生图链冲突。
- 修复：移除破坏性清空和手动上传提示；使用固定project/session进入统一资产FIFO，只补生成缺失基准图，已有成品和确认状态保持。
- 最终稽查：通过。逐集自动提取生图、project/session owner single-flight、P1/P2晚到隔离、只补缺及失败停止完成框架闭环。最终状态：已关闭。
- 独立软件测试：通过。分镜逐集完成仍调用`queueStoryboardAssetExtraction(project, session, episode)`，每集提取后经统一资产FIFO串行调用generate-all；`enterAssetGeneration`固定捕获project/session，仅准备缺失档案、持久化并enqueue补缺，未清理image URL、detail_assets、confirmation、generation nonce，旧“上传四视图/资产上传槽”提示不存在，手动逐槽导入入口保留。已有成品、waiting_confirmation及confirmed投影保持；generate-all只筛选`!item.image_url`且批次内无`purgeGenerated`。重复点击入口和generate-all single-flight去重、项目切换晚到隔离、首资产失败停止及FIFO无回归。定向`102 passed, 1 skipped`，全部单元测试`490 passed, 1 skipped, 9 subtests passed`；关键Python文件编译、Vue typecheck及Vite生产构建通过（83 modules，714ms）。未启动重模型、未修改业务代码。下一状态：待稽查。
- 稽查整改独立复测首败：`tests/unit/test_production_gate_reconciliation.py::test_assets_are_a_server_owned_langgraph_stage_not_a_frontend_legacy_call`仍强制旧断言`if (assetEntryPromise) return assetEntryPromise`，而正式整改已改为`assetEntryPromise && assetEntryPromiseKey === entryKey`，以允许P1未决时P2建立独立transaction。该定向文件结果`1 failed, 21 passed, 1 skipped`。测试契约仍要求会造成跨项目阻塞的旧行为，当前冻结快照无法全绿；按首败规则立即停止，未继续确定性P1/P2动态、全unit、Python编译、Vue typecheck或Vite构建。未启动重模型、未修改业务代码。下一状态：待处理。
- 过期测试同步后独立复测：通过。确定性动态分别将P1阻塞在`confirmStoryboards`和`prepareAssetProfilesFromStoryboard`，切换P2后两种场景均创建不同transaction，P2各自仅执行一次`persistAssetState(p2, session2)`和generate-all enqueue；P1解除阻塞后均未prepare/persist/enqueue污染P2，P1旧finally未清除P2 promise/key，同scope再次调用严格复用P2 Promise，动态`2/2`通过。定向`102 passed, 1 skipped`，完整单元测试`490 passed, 1 skipped, 9 subtests passed`；关键Python文件编译、Vue typecheck及Vite生产构建通过（83 modules，759ms）。未启动重模型、未修改业务代码。下一状态：待稽查。

### BUG-20260811-036：苏璃确认弹窗显示云长老批次错误

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.190
- 原因：`assetError`同时承载阶段错误和具体资产错误；批次继续到云长老失败后，全局错误仍显示在当前打开的苏璃卡片上方。
- 修复：新增`assetStageError`投影，带具体资产名前缀的错误只交给对应卡片；确认当前人物基准时清除旧兄弟资产全局提示。人物角度请求继续只携带当前人物自身基准与已确认角度。
- 最终稽查：通过。卡片错误归属、stage错误保留、人物自身references及FIFO/session隔离闭环。最终状态：已关闭。
- 独立软件测试首败：M9.190定向错误投影、卡片归属、确认清理、人物自身reference、FIFO和项目/session关联回归`78 passed, 1 skipped, 3 subtests passed`；确定性矩阵确认苏璃/云长老具体前缀均不进入全局，非资产阶段错误仍保留，variant references只取当前`item.image_url`及当前`item.detail_assets`中confirmed角度，不访问其他人物集合。但扩大执行全部`tests/unit`时出现4项失败（汇总`4 failed, 468 passed, 1 skipped, 9 subtests passed`）：资源池并发测试期望GPU queued=1实际0；`test_production_stage_scope_coverage.py`三项关于完整分集放行/后续完整集/多集边界的断言失败。按首败规则立即停止，未执行Vue typecheck或Vite构建；未启动重模型、未修改业务代码。下一状态：待处理。
- 冻结快照独立复测：通过。将上轮四个失败点连同M9.190错误投影、卡片归属、确认清理、自身reference、FIFO及项目/session链按同一顺序定向重跑，结果`118 passed, 1 skipped, 3 subtests passed`，资源池排队与三项分集范围门禁均未复现失败；随后完整`tests/unit`为`489 passed, 1 skipped, 9 subtests passed`。关键Python文件编译、Vue typecheck及Vite生产构建均通过（83 modules，593ms）。苏璃/云长老具体资产错误继续只在对应卡片显示，确认苏璃清旧全局提示，苏璃variant只引用自身已确认0°基准及自身confirmed角度。未启动重模型、未修改业务代码。下一状态：待稽查。
- 稽查整改独立复测：通过。确认错误动态矩阵`5/5`：兄弟云长老前缀错误与苏璃自身前缀错误在确认苏璃时清空；真实stage全局错误、含云长老文本但不以前缀开头的复合错误、无资产前缀错误均原值保留。M9.190定向及上轮边界`118 passed, 1 skipped, 3 subtests passed`，完整单元测试`489 passed, 1 skipped, 9 subtests passed`；关键Python文件编译、Vue typecheck和Vite生产构建通过（83 modules，550ms）。人物自身reference、FIFO、批次失败停止及项目/session隔离无回归。未启动重模型、未修改业务代码。状态保持：待稽查。

### BUG-20260811-033：并发生图重复注册与人物全身留白下限

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.189
- 现象：已有Klein 9B请求运行时，新请求再次安装并替换同一内置提供器，返回`capability provider has in-flight invocations`；旧日志同时存在升级后生产台账列数不一致错误。
- 修复：内置能力安装改为进程内幂等，不再替换已注册内置提供器；台账写入统一显式24列；人物全身角度提示词、归一器、机器验收与规范统一为头顶留白至少8%、脚底留白至少3%，均为下限。
- 开发验证：关联`113 passed, 1 skipped`，Python编译通过；未启动重模型。
- 最终稽查：通过。能力注册一次性绑定、inflight稳定、24列台账、全身8%/3%非固定安全区及历史规范隔离全部闭环。最终状态：已关闭。
- 独立软件测试首败：M9.189定向能力注册、生产台账、构图门禁和规范回归`192 passed, 1 skipped, 3 subtests passed`；但扩大执行全部`tests/unit`时出现2项失败（汇总`2 failed, 456 passed, 1 skipped, 9 subtests passed`）。`test_text_task_runtime.py::test_ollama_generation_always_runs_explicit_unload`的模拟网络异常被`_ollama_json`接受而未抛出；`test_cancelled_waiter_cannot_start_after_heavy_lock_releases`中已标记failed的等待任务仍被接受，未抛“已停止”。按首败规则立即停止，未继续Python编译、Vue typecheck或Vite构建；未启动重模型、未修改业务代码。下一状态：待处理。
- 首败整改后独立软件复测：通过。确定性动态验证同一服务模块首次安装后，在`image.generate/mlx-flux2-klein`真实inflight=1期间再次调用安装函数直接早退，provider对象身份不变、无replace、无in-flight异常，释放后原调用正常完成；模块级首次绑定与后续幂等同时成立。定向能力注册、24列生产台账、全身8%/3%最低安全区、半身隔离、规范及文本任务回归`209 passed, 1 skipped, 3 subtests passed`；全部单元测试`458 passed, 1 skipped, 9 subtests passed`。`compat_server.py`、`image_task_supervisor.py`、`production_ledger.py`、`production_orchestrator.py`编译通过；Vue typecheck与Vite生产构建通过（83 modules，942ms）。未启动重模型、未修改业务代码。下一状态：待稽查。

### BUG-20260811-035：upscale权威台账写入先于阶段取消提交围栏

- 状态：已关闭（最终稽查通过）
- 关联任务：后续统一阶段原子提交增量
- 问题：`review_export/upscale`在`_run_server_production_stage`内部直接执行`commit_upscale_authorities()`，而stage lease的`commit_guard`只在函数返回后的Handler中进入。取消可在权威增强证据已落SQLite后抢赢，使后续Graph提交被拒绝，形成ledger `pending_confirmation`与Graph `cancelled/failed`双事实。
- 隔离动态证据：fake ledger提交时设置同一cancel event，当前函数仍正常返回`operation=upscale`且`ledger_committed=1`；紧接的统一checkpoint稳定抛出`production stage cancelled or lease lost: review_export`。未启动模型或正式任务。
- 主线整改：upscale执行器改为仅返回延迟authority payload，最终提交统一进入owner+generation lease commit guard。ProductionLedger整批事务以内嵌Graph callback形成失败回滚边界；Graph失败、取消先赢或旧代失租均不产生成功authority，commit先赢唯一消费租约并同步得到ledger pending与Graph pending。
- 崩溃恢复：Graph事件持久保存scope/generation/fingerprint/batch精确tuple；服务重启发现Graph pending而ledger事务缺项时按原stage generation失败关闭，已完整落账则保持待确认。
- 开发验证：cancel-first、commit-first、Graph故障整批回滚、旧owner被新代接管、Graph成功但ledger未落的重启恢复动态`5/5`；review_export/upscale、stage cancellation、production control关联`147 passed`，Python编译、Vue typecheck与83模块生产构建通过。未启动重模型或正式任务。
- 独立软件测试：通过。原5项动态全部通过；补充覆盖多集第二条authority故障时首条同事务回滚、完全相同批次重复提交幂等、tenant/user/project三维隔离，以及Graph已持久但ledger缺失的崩溃窗口恢复失败关闭。BUG028 authority CAS/confirm/export关联回归`147 passed`，完整单元测试`495 passed, 1 skipped, 9 subtests passed`；关键Python文件编译、Vue typecheck及Vite生产构建通过（83 modules，775ms）。未启动重模型、未操作正式任务、未修改业务代码。
- 最终稽查：通过。代码原子边界无阻断；待用户正式图片任务自然结束后，在任务、三池、Ollama与ComfyUI全空时安全重载8787。新PID53734已加载当前代码，唯一worker健康且active/queued为0，正式任务与模型队列为空。最终状态：已关闭。

### BUG-20260811-034：单条已确认媒体scope可越级完成整个阶段

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.188
- 问题：`_begin_production_request()`仅按stage名称收集任意`completed+confirmation`记录，再以`trusted=True`直接把整阶段写completed；当同集镜头1已确认、镜头2待确认时仍可成功启动video，绕过已存在但未被入口复用的统一范围门禁。
- 主线整改：阶段入口改为统一调用`_reconcile_completed_production_stages`；确认、资产延迟确认、恢复与入口四类路径共用`_confirmed_production_gate_record`。四个shot阶段从storyboard台账构建分集期望集合，缺scope以失败占位参与门禁，至少一集完整才允许推进。
- 动态验证：旧路径稳定复现`begin(video)`成功且额外报告`image=completed`，而统一门禁同时判定false；整改后partial、完全缺失兄弟镜头及无storyboard census均拒绝，完整单集放行，第一集残缺但第二集完整时精确选择第二集。扩大关联`170 passed, 1 skipped`，Python编译通过；未启动模型或正式任务。
- 独立软件测试首败：权威storyboard census仅包含`1:1`时，image同时存在已确认`1:1`和多余`1:2`；`_stage_gate_records("image", records)`仅返回`1:1`，统一完成判定为true，未按规范对多余scope失败关闭。动态断言`extra image scope must fail closed`稳定失败。
- 测试范围处置：依软件测试首败规则立即退回，未继续确认fp/audit batch绑定、八阶段入口/恢复语义、M9.187旧`left45`断言、关联回归、编译、类型与构建；未启动模型或正式服务。
- 首败整改独立复测：多余scope、非法ID、重复及别名碰撞的新增专项`22 passed`；但媒体确认事实仍未绑定当前权威指纹与审核批次。隔离动态用例稳定证明：`content_fingerprint`顶层为`img-new`而confirmation为`img-old`、`audit_batch_id`顶层为`batch-new`而confirmation为`batch-old`、以及顶层fingerprint或batch缺失四种情形，`_production_stage_gate_complete("image", records)`均错误返回`True`；只有空confirmation被拒绝。
- 本轮测试处置：按首败规则立即停止，未继续八阶段入口/确认/延迟/恢复一致性、M9.187旧`left45`断言、关联回归、Python编译、Vue typecheck或Vite构建；未启动模型或正式服务，未修改业务代码。
- 第二首败整改：共享`_confirmed_production_gate_record`仅对image/video/audio/subtitle shot scope强制顶层fp/batch非空，confirmation内fp/batch与顶层当前值精确一致；非媒体stage维持既有确认边界。四stage×缺fp/缺batch/旧确认/合法矩阵定向`39 passed`；扩大关联`202 passed, 1 skipped`，Python编译、Vue typecheck及83模块Vite构建通过；未启动模型或正式任务。
- 最终独立复测：通过。专项`79 passed, 1 skipped`；独立动态覆盖四媒体阶段、额外/非法/别名碰撞、多集边界及确认/延迟确认/恢复/入口共用门禁，扩大关联`192 passed, 1 skipped`。Python编译、Vue typecheck及83模块Vite生产构建通过；未启动模型或正式任务。
- 最终稽查：通过。代码专项`61 passed, 1 skipped`；四媒体census、额外/非法/非shot/别名碰撞、指纹/批次确认绑定和非媒体兼容均闭环。正式8787已在资源空闲时安全重载为PID50323，健康且仅一个worker，任务、三池、Ollama与ComfyUI均为空。最终状态：已关闭。

### BUG-20260811-032：人物基准角度与多角度提示词冲突

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.187
- 问题：人物首张左45°生成提示与身份描述中的“正面近照”发生方向和景别冲突，其他角度提示也缺少完整的互斥角度约束，导致姿态失败率偏高。
- 修复：人物首张改为0°正面平视完整全身并人工确认；其后左45°、右45°、90°、180°、0°半身逐槽生成确认。六角度提示逐项明确偏航、构图和禁止项；身份描述剥离全部角度与景别词。人物3D输入同步为已确认0°正面全身，道具/场景45°基准不变。
- 最终稽查退回整改：清除3D规范、M9.168开发记录和项目记忆中三处仍把左45°声明为TripoSR人物输入的现行冲突；统一为0°正面全身唯一人物几何输入，并明确历史口径已被M9.187覆盖。
- 软件测试首败：正式`baselineIdentityPrompt`未完整剥离角度与景别词。动态执行当前函数，输入`苏璃，16岁，左45度全身，黑色长发`，输出仍为原文，保留`左45度全身`；这会与0°正面baseline或其他目标角度提示形成直接方向冲突。对照`正面近照`可被清除，说明正则只覆盖部分带“照/视图”的表达，未覆盖常见“左/右45度全身、90度侧面全身、180度背面全身、0度正面半身”等无“照/视图”后缀口径。按首败规则立即停止，未继续关联回归/编译/构建，未启动模型、未修改业务代码。
- 首败整改复测新失败：无后缀常见表达已修，但明确要求的带空格组合仍未完整清洗。动态输入`苏璃，16岁，左 45 ° 完整全身视图，黑色长发`，前端正式函数输出`苏璃，16岁， 完整，黑色长发`；后端同源正则输出仍保留`完整全身视图`。根因是角度表达与可选`完整/景别`之间未允许空白，前端后续通用景别替换只删除`全身视图`而残留`完整`。同类影响`右 45 度 完整全身照`、`90 ° 侧面 完整全身`、`180 ° 背面 完整全身视图`。按首败规则立即停止，未继续其余范围与回归构建，未启动模型、未修改业务代码。
- 第二次整改独立软件复测：通过。前后端身份清洗分别动态覆盖15种常见、空格、`°/度`及`完整+景别`组合，全部只保留姓名、年龄、发色等身份属性，重复逗号与残留“完整”均为0。人物卡显示严格为`0°半身→0°全身baseline→左45→右45→90→180`；内部生成严格为`0°全身baseline→左45→右45→90→180→0°半身`。六角度提示目标方向、互斥方向和全身/半身构图逐项`6/6`通过。
- 运行链验证：front_full baseline首图/第二图/第三图成功及三次失败动态`4/4`，验收调用`front_full`、重试提示为zero-degree front-facing、最终错误明确“人物0度正面全身”且无left45残留。旧view contract清基准/variants并先生成新nonce，再按新nonce查询job，旧left45 job不得恢复。人物3D强制`front_full`，道具/场景保持`three_quarter_45`，服务端三类确认映射`3/3`及错误角度拒绝`3/3`。
- 回归：项目/session、FIFO、逐槽确认、恢复、停止与failed终态关联`186 passed, 1 skipped, 3 subtests passed`；Python编译、Vue typecheck、Vite生产构建通过（83 modules，546ms）。未启动真实重模型。
- 最终稽查文档整改软件测试首败：目标三处已修（3D规范明确0°正面全身唯一3D输入；Dev_MainDev与项目记忆M9.168均标历史并由M9.187覆盖），但完整扫描仍发现未隔离的现行冲突。`docs/memory/项目记忆.md:105`的M9.151仍以“最终稽查通过，已关闭”现行口径记载“Klein 9B左45°基准照、TripoSR与Blender静态链”，未声明历史或被M9.187覆盖；会继续把左45°解释为TripoSR人物输入。另`docs/technical/IMAGE_GENERATION_SPEC.md:10-11,48`和`docs/technical/HUMAN_MULTIVIEW_REMOTE_PROVIDER_SPEC.md:5`仍以现行规范口吻要求正面近照首图、四图/Visual Persona/PSHuman旧链，未标历史，直接冲突M9.187六格与0°正面全身首图。
- 本轮按首败规则停止：未继续关键代码回归/编译/构建，未启动模型、未修改业务代码。下一状态：待处理。
- 文档首败整改：M9.151人物左45°文字已标为被M9.187覆盖；`IMAGE_GENERATION_SPEC.md`与`HUMAN_MULTIVIEW_REMOTE_PROVIDER_SPEC.md`已在首行标记历史归档、禁止执行，并指向M9.187的0°正面全身六格权威链。
- 文档第二次首败整改：项目进度与项目记忆的M9.158固定种子源、M9.156人物基准/LoRA/3D门禁均统一由M9.187覆盖为0°正面全身与`front_full`。
- 文档整改第二轮独立软件测试首败：上述三个定向整改点均已通过，但全量扫描继续发现未隔离冲突。`docs/product/项目进度.md`与`docs/memory/项目记忆.md`的M9.158条目仍写“当前左45°全身为首格及固定种子源”，仅声明被M9.166覆盖，未声明已被M9.187的0°正面全身baseline/固定种子源再次覆盖；同一项目记忆的M9.156 LoRA条目仍称门禁继续有效且加载目标为M9.166左45°首图。它们会把历史左45°重新解释成当前首图和种子源，与M9.187权威链直接冲突。按首败规则立即停止，未执行关键代码回归、Python编译、Vue typecheck或Vite构建；未启动模型、未修改业务代码。下一状态：待处理。
- 文档整改第三轮独立软件复测：跨文档全量扫描通过。项目进度/项目记忆M9.158均明确由M9.187覆盖并以0°正面全身作为首张和固定种子源；项目记忆M9.156的契约、LoRA和3D门禁均统一`front_full`；技术旧规范已明确历史归档、禁止执行，现行总规范、3D规范、AI执行提示及Dev记录均未再发现未隔离的左45°首图或TripoSR输入冲突。定向资产/图片/规范/FIFO回归`70 passed, 3 subtests passed`，补充合同与集成回归`40 passed`，Python编译、Vue typecheck和Vite构建通过（83 modules，570ms）。
- 第三轮完整回归首败：扩大执行全部`tests/unit`时，`test_project_store_recovery.py`两项失败：`test_concurrent_stage_writes_preserve_every_stage`和`test_corrupt_store_recovers_latest_valid_snapshot`调用`_write_project_stage(..., "outline", ...)`均被生产编排器以`ValueError: previous stage is not completed: requirements`拒绝；汇总为`2 failed, 446 passed, 1 skipped, 9 subtests passed`。虽然M9.187定向链已通过，该仓库完整回归不全绿，按AGENTS规则仍退回，未标待稽查；未启动重模型、未修改业务代码。下一状态：待处理。
- 最终独立软件复测：通过。跨文档全量扫描确认项目进度/项目记忆M9.158、M9.156契约/LoRA/3D门禁、Dev记录、现行总规范/3D规范/AI执行提示均统一为0°正面全身首张、固定种子源与TripoSR唯一人物输入；两份旧technical规范保持历史归档、禁止执行，未发现未隔离冲突。M9.187定向链连同项目存储恢复隔离测试`73 passed, 3 subtests passed`；全部单元测试`448 passed, 1 skipped, 9 subtests passed`。`compat_server.py`、`image_task_supervisor.py`、`production_orchestrator.py`编译通过；Vue typecheck与Vite生产构建通过（83 modules，541ms）。未启动重模型、未修改业务代码。下一状态：待稽查。
- 最终稽查：通过。人物显示/生成顺序、六提示互斥、身份视角清洗、`front_full`三轮自适应、旧契约失效、人物3D唯一`front_full`、道具/场景`three_quarter_45`及全部现行/历史规范边界一致。最终状态：已关闭。

### BUG-20260811-031：人物基准图自动重生成次数与错误汇总不完整

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.186
- 问题：人物左45°基准图只有首图+1次重试，第二次失败即暂停；错误汇总遍历全部布尔字段，误报非左45°硬门禁的头身比、手臂比例等项目。
- 修复：改为首图+最多2次自适应重生成，共3次；重试提示携带本轮真实required失败项；最终错误只汇总左45°required并明确三次耗尽，成功写`validation_attempts`。
- 主线验证：专项及关联`55 passed, 1 skipped, 3 subtests passed`。
- 独立软件测试：通过。动态抽取并执行正式人物baseline验收块，四条确定性mock路径全部成立：首图成功`validation_attempts=1`、首图失败后第二图成功为2、前两图失败后第三图成功为3；失败候选分别删除0/1/2张。每次重试提示只注入当轮`baseline_required_checks`失败项，未混入top margin、头身比、手臂比例等非required字段。
- 三次失败边界：共调用首图+2次重生成，三个候选文件全部删除，第三次后才抛“自动生成3次仍未通过规范验收”；最终错误只来自七项required，本轮故意置假的`top_margin_about_5_percent/head_to_body_ratio_7_to_7_8/upper_lower_arm_length_difference_percent`均未进入提示或错误。停止、failed终态、FIFO owner/epoch及全局单并发无回归。
- 回归：关联`185 passed, 1 skipped, 3 subtests passed`，Python编译、Vue typecheck、Vite生产构建通过（83 modules，543ms）；未启动真实重模型。
- 最终稽查：通过。三次候选、自适应required提示、失败候选清理、成功尝试次数、停止/终态/FIFO及单并发均无剩余阻断。
- 关闭时间：2026-08-11。

### BUG-20260811-030：资产续生删除成品并触发自身阶段门禁

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.185
- 问题：`/api/characters/generate`被作为下游image阶段执行前序门禁，资产尚未完成时形成`previous stage is not completed: assets`循环；页面在全部基准图存在时把主按钮改为“重新生成图片”，调用`purgeGenerated`删除全部文件并清空卡片。
- 修复：资产基准/variant/repair和3D生成识别为assets内部构建子任务，跳过聚合阶段前序门禁但保留image/3d资源池与FIFO；页面主按钮只补缺失项，不再调用purge。历史storyboard/assets门禁错误精确迁移，其他错误保持。
- 数据恢复：恢复仍存在的墨无痕、宗门试炼场URL与待确认状态；苏璃、云长老物理文件已被旧purge删除，仅标为pending，不伪造成功。
- 主线验证：关联`125 passed, 1 skipped`；Python编译、Vue typecheck、Vite生产构建通过（83 modules，541ms）。
- 软件测试首败：正式当前项目持久状态与物理媒体不一致。`output/narrative-cache/projects.json`中苏璃、云长老仍为`waiting_confirmation`且保留旧`image_url`，但对应文件在`output`中均不存在，正式`/api/result-media`均返回HTTP404；要求是两项清除失效URL并恢复`pending`。对照墨无痕与宗门试炼场均为`waiting_confirmation`，对应物理文件分别存在且大小`1561200`、`2733928`字节。正式8787健康、三池active/queued为0，8194 queue为0/0。按首败规则立即停止，未继续关联回归/编译/构建，未启动重模型、未修改业务代码。
- 首败前已通过：资产子任务路由矩阵`17/17`；shots HTTP仍触发image门禁409，scene variant资产子任务绕过聚合门禁后按自身规则400且零job；历史门禁错误迁移`7/7`，真实错误保持；主按钮源码只筛选`!image_url`且batch内无purge，单卡重做仍保留purge能力。
- 首轮整改：服务端`_write_project_stage`在assets持久化事务内校验所有本地`/api/result-media`基准及variant URL；文件不存在时强制清URL、确认字段和服装引用并恢复pending，旧页面内存无法再次写入假成功。存在文件与远程URL保持不变。
- 首轮整改独立软件复测：通过。临时项目动态写入覆盖基准、`detail_image_urls`与variant：不存在的本地媒体强制清URL、`baseline_confirmed_at/confirmation_phase/clothing_reference_url`、error并恢复pending；存在的基准与variant保持原状态，远程HTTPS URL不误清；旧页面再次回写同一失效URL仍被持久层拦截，共`12/12`。
- 完整功能与正式状态：资产子任务路由矩阵`17/17`，shots仍触发image聚合门禁，资产子任务绕过前序聚合门禁但保留自身校验与零job边界；历史storyboard/assets错误迁移`7/7`，其他真实错误保持。页面批次只选择`!image_url`，batch内无purge且不清detail/confirmation，单卡重做仍可精确purge替换。正式项目苏璃、云长老均pending且无URL/确认；墨无痕、宗门试炼场均waiting_confirmation，物理文件存在且大小分别`1561200`、`2733928`字节。8787健康且三池active/queued为0，8194 queue为0/0。
- 回归：关联`171 passed, 1 skipped`，Python编译、Vue typecheck、Vite生产构建通过（83 modules，550ms）；未启动重模型。
- 最终稽查：通过。资产内部子任务门禁、只补缺图、单卡重做、媒体权威校验及正式状态均无剩余阻断。
- 关闭时间：2026-08-11。

### BUG-20260811-029：M9.184资产操作并发确认导致连接中断

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.184
- 问题：资产批次仍在运行时，其他卡片操作可并发提交；单资产确认又直接执行assets总阶段完成门禁。storyboard为waiting_confirmation时抛出未捕获`ValueError: previous stage is not completed: storyboard`，Vite收到`socket hang up`并显示“服务连接中断（HTTP 500）”。
- 修复：资产页生产操作统一项目会话FIFO；停止/切项目按代际清理排队。单资产确认先持久化，上一阶段未完成时仅延迟总阶段推进；production ValueError统一转换HTTP409。
- 主线验证：新增FIFO/延迟确认专项3项，关联23 passed、1 skipped；Python编译、Vue typecheck、Vite生产构建83 modules通过。
- 首轮软件测试退回：停止/切项目清空旧队列后，新会话提交同key任务；旧任务finally无代际所有权判断，错误删除新代key并递减新代计数，造成去重失效与UI误报空闲。
- 首轮整改：队列key改为`key -> ownerToken`所有权映射；finally仅在当前key仍归属自身token时才删除并递减，旧代任务无法清理新代状态。
- 第二轮软件测试退回：FIFO、owner token、项目隔离、延迟确认和HTTP409均通过；关联测试仍要求3D生成/确认模板直绑旧函数，与当前队列包装契约冲突，结果`1 failed, 162 passed, 1 skipped`。
- 第二轮整改：3D前端测试契约同步为`queueAsset3D`与`queueAsset3DConfirmation`，停止仍保持`stopAsset3D`即时直连。
- 软件测试首败：停止/项目切换提升`assetOperationEpoch`后会清空全局key/count并把tail重置为已完成Promise，但旧代每个`schedule.finally`仍无代际/所有权判断地执行`queuedAssetOperationKeys.delete(key)`和全局count减一。确定性动态用例中，旧长任务运行、同key旧任务排队时执行正式重置逻辑，再提交同key新代任务；旧代收尾后新代计数从1被改为0，且新代稳定key被删除，违反“旧finally不污染新会话”。原始状态：`order=[start:old-running,start:fresh,end:old-running]`、`count=0`、`hasKey=false`；预期新任务仍运行时`count=1`、`hasKey=true`。同根因还会使重复点击绕过去重，并让UI错误显示队列已空。按首败规则停止，后端延迟确认、HTTP409及关联构建本轮未继续；未启动模型、未修改业务代码。
- 首败整改复测：owner token门禁通过。正常三任务严格FIFO、顺序`a→b→c`、`maxConcurrent=1`，同key重复零执行；stop/session重置后旧finally不再删除新owner或递减新count；项目切换旧排队任务不执行、新项目任务正常执行。后端延迟确认动态验证单资产先持久completed、storyboard未完成时workflow保持pending_confirmation，上一阶段完成后正常推进completed；非预期校验错误回滚pending，HTTP ValueError稳定返回409 JSON。
- 关联回归新首败：`tests/unit/test_asset_3d_workflow.py::test_frontend_exposes_generate_stop_confirm_and_downloads`仍强制要求模板直接绑定`@generate3d="generateAsset3D`与`@confirm3d="confirmAsset3D`，而M9.184正式实现已按需求改为`queueAsset3D/queueAsset3DConfirmation`进入统一FIFO。结果`1 failed, 162 passed, 1 skipped`。该断言与本次强制FIFO契约冲突，不能通过删除队列包装回退产品；应同步测试为要求queue包装并保留stop即时直连。按首败规则未继续Vue typecheck/Vite build，未启动模型、未修改业务代码。
- 最终独立软件复测：通过。正式FIFO动态覆盖长任务后连续入队、稳定key去重、严格`a→b→c`与`maxConcurrent=1`；stop/session提升epoch并清队列后，旧owner finally不删除或递减新owner，项目切换旧排队任务不执行、新项目任务正常。自动/手动生成、重做、修复、导入、基准/variant确认、3D生成/确认及资产超分均经统一队列，3D停止保持即时直连。后端动态验证资产scope先持久`completed+confirmation`，storyboard未完成时workflow保持`pending_confirmation/deferred_confirmation`，上一阶段完成后可正常推进completed；非预期校验错误回滚pending，ValueError经真实临时HTTP稳定返回409 JSON而非断连。
- 最终回归：关联`164 passed, 1 skipped`；跳过项为环境可选测试，不影响本增量。Python编译、Vue typecheck、Vite生产构建通过（83 modules，549ms）。正式5173/8787健康，8787三资源池active/queued均0；未启动重模型。
- 最终稽查退回：统一FIFO只在操作启动前检查project/session/epoch；已启动的导入、修复、确认、3D生成/确认和超分缺少响应后围栏，且项目切换/stop重置FIFO尾链会让新项目操作与旧项目未结束操作并发。旧项目晚到可修改全局资产并通过无参持久化写入当前新项目，违反跨项目隔离与全局单路执行。
- 稽查整改：项目切换/stop不再重置`assetOperationTail`，新操作继续排在已启动旧操作之后，旧代未启动任务到位后按epoch跳过；导入、修复、基准/角度确认、3D生成/确认及超分均捕获固定project/session，在每个异步响应、状态修改、通知和持久化前复核会话，持久化显式使用原项目上下文。队列与单项finally继续以owner token/session/key精确回收，旧操作不得清除新项目状态。
- 主线整改验证：定向Python回归`43 passed, 1 skipped`，后端编译、Vue typecheck及Vite生产构建通过（83 modules，546ms）；待独立软件复测已启动旧任务切项目后的晚到隔离与全局FIFO。
- 最终稽查整改独立软件复测：通过。动态直接执行正式函数：p1导入分别阻塞`resource.save`与`semanticAudit`后切p2，晚到均零merge、零persist、零p2通知；p1 `generateAsset3D`、`confirmAsset3D`、局部repair、upscale分别在服务响应阻塞后切p2，晚到均不写结果、状态、持久化或UI。已启动p1旧操作、旧排队操作、p2新操作矩阵严格为`old-start→old-end→new-start→new-end`，`maxConcurrent=1`；旧排队按epoch跳过，owner token确保旧finally不删除新owner或递减新count。全部资产操作继续经FIFO，3D stop保持即时直连。
- 后端与回归：资产scope先持久`completed+confirmation`、storyboard未完成时workflow保持`pending_confirmation/deferred_confirmation`，上一阶段完成后推进completed；真实临时HTTP ValueError返回409 JSON。关联`164 passed, 1 skipped`，Python编译、Vue typecheck、Vite生产构建通过（83 modules，547ms）；未启动重模型。
- 下一状态：待稽查。

### BUG-20260811-028：M9.183增强阶段缺输入未整批失败关闭

- 最终状态：已关闭（最终稽查通过）
- 最终权威CAS闭环：upscale的fingerprint、audit_batch_id、generation、production/audit evidence、confirmation与前端progress物理隔离；公开single/bulk投影无权创建或覆盖服务端权威字段。同代异证拒绝，真实生成跨实例单调分配generation，revision CAS与不可变history拒绝低代、旧tuple和历史批次重放；人工确认及enhanced导出精确绑定fp+batch+generation。
- 最终验证：独立对抗动态覆盖公开篡改、stale fp/batch/generation确认、同代伪证据、旧generation重放、跨Ledger并发仅最新代提交及正常确认导出；关键专项`47/47`，主线关联`159 passed, 1 skipped`，Python编译、Vue typecheck及83模块Vite构建通过。正式PID43900启动晚于最新compat/ledger代码，8787健康、唯一worker active0/queued0、三池空、tasks=0、Ollama与ComfyUI空。
- 关闭时间：2026-08-11（Asia/Shanghai）。

- 最终权威篡改漏洞独立软件测试通过，待最终稽查：`production_scopes`新增持久generation/revision和独立production/audit evidence列，另设generation高水位与不可变authority history。公开`/api/production/scopes`及`/bulk`统一走无权projection路径，只能合并不含证据的progress；客户端伪造fp/batch/generation/evidence/confirmation/completed均不能创建或覆盖服务端权威，bulk replace保护服务端代际与确认记录。
- 真实upscale在provider前跨实例原子分配单调generation，fingerprint绑定generation+服务端batch；提交仅接受当前预留代，revision CAS拒绝低代、旧fp+batch重放及同代证据篡改，完全相同值幂等且不改确认。人工确认和enhanced export精确核对fp+batch+generation，旧页面确认不会误确认新代。
- 开发动态证据：公开single/bulk同代篡改与投影shell、跨实例并发代际分配/仅最新提交、reload、旧代与旧tuple重放、同代幂等/伪证据、deep-watch合法进度、正常生成→确认→authority均通过；专项`32 passed`、关联`161 passed, 1 skipped`，Python编译与Vue typecheck通过。本进程Vite受ChatGPT内置Node与Rollup原生模块Team ID签名不兼容阻断，留待独立测试运行时复验；未启动模型或正式任务。
- 最终权威边界独立软件测试：通过。现有关键动态`5/5`：公开single/bulk无法篡改或创建server fp/batch/generation/production+audit evidence/confirmation/completed；两个独立Ledger实例并发分配generation 1/2后仅代2合法提交；同代不同证据拒绝；旧generation及旧fp+batch重放拒绝；正常生成→确认→enhanced authority/export通过。额外临时SQLite动态精确验证stale fp、stale batch、stale generation三类确认全部拒绝，当前fp+batch+generation唯一确认且导出为generation 2；同代伪证据与旧generation重放各自稳定失败。只引用主线已交付的关联`159 passed`、Python编译、Vue typecheck与83模块Vite生产构建证据，本轮未重跑大套件；未启动模型或操作正式服务。当前状态：软件测试通过，待最终稽查。
- 最终稽查阻断整改完成，待独立软件复测：账本证据保留已改为严格代际语义。只有fingerprint与batch均不变时，missing/null投影才保留既有production/audit evidence；任一变化会在合并前清空两项旧证据并无条件撤销confirmation，传入旧/伪confirmation不能恢复。新代仅接收本次非空规范证据，新批缺证即使重新确认仍被enhanced authority拒绝；新证据落入新代并重新确认后才可跨实例reload放行。
- 主线动态证据：临时SQLite参数化覆盖仅fp变化、仅batch变化、两者同时变化及missing/null/空字符串/空对象/空数组；旧证据和confirmation均为null。缺证新批confirm后authority拒绝；携带新production/audit evidence的新代先保持未确认，跨新实例confirm/reload后authority只返回新证据。专项`36 passed`，关联`203 passed, 1 skipped`；Python pycompile、Vue typecheck、Vite生产构建通过（83 modules，708ms），未启动模型或操作正式服务。
- 最新稽查退回整改完成，待独立软件复测：前端`syncProductionLedger`为upscale scope把`production_evidence/audit_evidence`原结构写入progress，深watch对undefined/null均不发送擦除值；SQLite ledger对progress执行字段级合并，缺失或null证据保留现有权威值，fingerprint或batch任一变化自动撤销旧confirmation。
- enhanced导出不再使用legacy缺省证据：权威upscale scope缺任一非空规范JSON production/audit evidence即整集失败关闭；`legacy_base_scope`的`not_available/not_applicable`只允许base历史scope。enhanced客户端声明必须同时携带fingerprint与audit_batch_id，authority精确核对台账、confirmation和声明三方fp+batch；同fp的新批次会拒绝旧batch声明。
- 主线动态证据：临时SQLite覆盖结构证据写入→缺字段deep-watch→显式null→新实例reload全程不丢；enhanced缺证拒绝、base legacy边界、同fp旧batch拒绝/新batch放行端到端通过。专项`44 passed`，扩大关联`171 passed, 1 skipped`，交付链`4 passed`；Python编译、Vue typecheck和83模块生产构建通过，未启动模型或正式任务。
- 最新稽查整改独立软件复测：通过。动态执行正式`syncProductionLedger`确认嵌套`production_evidence/audit_evidence`原样进入upscale progress，缺失证据字段完全省略且fingerprint+batch保持；SQLite missing/null保留、跨新实例reload/confirm及同fp新旧batch代际门禁全部通过。enhanced缺证失败关闭，legacy缺省仅限base；四步骤失败/取消围栏`8/8`、第二条scope写入故障整批回滚、规范JSON空值/NaN/±Infinity/不可序列化拒绝及全树键序稳定通过。真实隔离导出文件与`manifest.json`逐集携带权威source version/fingerprint/batch/production/audit证据。
- 最终复测：专项`52 passed`；扩大关联（生产控制、阶段取消、门禁、single-flight/FIFO、delivery、manifest与集成）`181 passed, 1 skipped`，跳过项为既有可选环境用例。Python pycompile、Vue typecheck、Vite生产构建通过（83 modules，550ms）；未启动模型或正式任务。
- 当前状态：软件测试通过，待稽查

- 端到端证据持久化整改：upscale scope将production_evidence/audit_evidence作为结构化JSON写入权威progress，`ProductionLedger.list`恢复为顶层结构字段；跨新实例reload与confirm类型和值不变。导出权威校验返回服务端scope证据并覆盖客户端声明，manifest每集包含source_version/fingerprint/batch/production/audit evidence；legacy base明确标记证据边界。临时SQLite端到端及关联`124 passed`，编译/类型/构建通过。

- 复稽查残留整改：production_evidence保持原始JSON类型，不再`str`降格；空值、不可序列化对象、NaN/Infinity等非规范JSON失败关闭。完整fingerprint payload统一`sort_keys + allow_nan=False`递归规范化，嵌套command/output/production/OCR/face/final各层键序变化哈希稳定，任一语义值变化哈希变化。
- 资产FIFO真实动态：直接执行正式`enqueueAssetOperation`，验证A→B严格顺序、重复key不重复执行且沿用当前owner、epoch停止/切项目后新owner可立即执行、旧任务finally不删除新owner，新owner完成后精确释放。证据/FIFO专项`31 passed`。
- 复稽查扩大回归：增强证据、权威导出、口型回退、生产控制/取消及资产FIFO`144 passed`；Python编译、Vue类型检查、Vite生产构建通过（83 modules，583ms），未启动模型或正式任务。

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.183
- 测试范围：`review_export/upscale`统一服务端阶段的整批输入门禁与零副作用边界。
- 软件测试首败：提交两集commands，其中第1集仅含`episode=1`、缺少输入媒体`path`，第2集含合法path。服务端只预校验episode正整数和唯一性，未在任何本地调用前验证每集输入媒体非空；实际先后调用第1集`/api/videos/upscale`、`/api/videos/audit`，随后继续调用第2集相同接口，并返回两集`waiting_confirmation`。
- 预期：多集任一command缺少输入媒体时整批拒绝，所有超分、字幕OCR、人脸审核、终审provider调用均为0，不产生任何增强items或阶段成功投影。
- 原始动态证据：`calls=[('/api/videos/upscale',1,None),('/api/videos/audit',1,'/generated.mp4'),('/api/videos/upscale',2,'/valid.mp4'),('/api/videos/audit',2,'/generated.mp4')]`；函数错误地返回两集成功items。断言`calls == []`失败。
- 同类风险：当前成功item只直接包含enhanced返回与`audit_evidence`，尚需整改后复测权威fingerprint/batch/evidence；每步取消、失败/异常停止后续、项目/session晚到、single-flight/停止和M9.179 enhanced导出门禁因首败规则尚未继续。
- 测试结论：不通过；发现首个失败后立即停止，未启动模型、未修改业务代码。
- 整改：新增`_validate_upscale_commands`，在任何local/provider调用前整批校验非空列表、对象类型、episode严格正整数且唯一、绝对本地路径或合法HTTP/result-media URL、source_version=base，以及target width/height/fps/mode完整合法；混合批次任一非法整批ValueError且零调用。前端命令显式提供base与1080×1920@30 quality目标。
- 开发验证：空/None/非对象、重复、布尔/负数/小数/非数字episode、空/相对/坏URL、缺失或错误source_version、缺失/非法target及混合合法非法矩阵全部零副作用；专项与关联`116 passed`，待扩大回归。
- 扩大回归：upscale、review_export权威门禁、生产控制、会话与阶段取消`150 passed, 1 skipped`；Python编译、Vue类型检查与Vite生产构建通过（83 modules，551ms），未启动模型。
- 首轮整改软件复测：整批输入预验证专项`22/22`通过，空/None/非对象、非法或重复episode、缺失/相对/畸形媒体路径、错误source_version、缺失/非法target及混合批次末项非法均在provider前整批拒绝，调用数0。
- 新首败：成功增强item仅返回`episode/status/path/video_url/production_evidence/audit_evidence`，缺少非空`content_fingerprint`和`audit_batch_id`。动态成功结果为`{'episode':1,'status':'waiting_confirmation','path':'/enhanced.mp4','video_url':'/enhanced.mp4','production_evidence':{'model':'x'},'audit_evidence':{'audit':'ok'}}`，无法形成供M9.179 enhanced导出严格匹配的权威upscale ledger证据。
- 当前测试结论：仍不通过；发现首个新失败后停止，未启动模型。四步取消/失败、前端single-flight/stop/会话晚到及关联构建待下一轮完整复测。
- 新首败整改：服务端为每批生成唯一`upscale-*` batch，同批共享且跨批不同；每集fingerprint由source media/version、增强输出、target、production_evidence和真实audit_evidence规范序列化后SHA-256生成，不接受客户端自报。整批全部成功且cancel checkpoint通过后，原子写入`review_export/episode/upscale:{episode}` pending_confirmation；失败/cancel零成功ledger。前端持久保存并原样同步fingerprint/batch，人工确认调用权威confirm，enhanced导出声明使用该fingerprint。
- 端到端轻量动态：成功item→pending ledger→confirm completed→enhanced export严格放行；篡改fingerprint拒绝，第二批覆盖为新batch后旧确认/旧fingerprint拒绝。专项23项通过，待扩大回归。
- 扩大回归：upscale证据、review_export导出权威门禁、生产控制、会话与取消`151 passed, 1 skipped`；Python编译、Vue类型检查与Vite生产构建通过（83 modules，546ms），未启动模型。
- 第二轮软件复测进展：upscale/review_export/stage cancellation权威证据相关`52/52`通过，确认成功item含同批一致、跨批不同的batch及绑定证据的SHA-256；pending→人工confirm completed→enhanced export放行，篡改及旧批次拒绝。
- 第二轮新首败：动态执行正式`runUpscale()`，在`upscaleQuote`等待期间同项目连续调用两次，`quoteCalls=2`且`first===second`为false。入口仍为`async function runUpscale`且没有project/session级flight；`upscaleStatus`在quote和用户确认后才设为generating，因此重复点击可并行报价并继续形成重复runStage提交。
- 预期：报价预检、确认和生产提交应由同一权威single-flight覆盖；同project/session重复点击严格返回同一Promise，quote与runStage各最多一次。stop/项目切换须释放旧flight并以代际围栏阻止旧finally清新任务。
- 当前测试结论：不通过，待处理。发现首败后停止，未启动模型；其余前端stop/晚到、原子upsert故障注入、全关联/type/build待整改后复测。
- 第三轮软件复测功能矩阵：正式前端函数重复点击严格同Promise，quote/confirm/runStage各1；取消与quote异常可重试；stop携带tenant/user/project/review_export完整scope，停止及项目切换后的旧响应零污染、旧finally不清新flight，动态`18/18`。后端四步取消/失败零后续及零ledger`8/8`，第二条upsert故障整批回滚`1/1`，权威证据与导出专项`52/52`。
- 第三轮关联首败：扩大回归`1 failed, 170 passed, 1 skipped`。失败项`test_optional_media_enhancements.py::test_musetalk_remains_primary_with_latentsync_fallback`仍要求前端源码存在`mediaService.lipSync`后再出现`mediaService.latentSync`；现行统一video服务端已明确`/api/videos/lipsync`失败后调用`/api/videos/latentsync`，前端不应恢复旧直连。判定为关联测试契约未同步，但按首败规则退回，未继续pycompile/type/build。
- 关联测试整改：改为动态执行正式服务端video阶段，精确验证MuseTalk成功时LatentSync调用0、MuseTalk RuntimeError时LatentSync调用1、主链失败后取消checkpoint时LatentSync调用0；同时双向断言前端generateShotVideos无lipSync/latentSync直连、后端两端点均存在。业务代码未回退旧架构。扩大关联`156 passed, 1 skipped`。
- 关联门禁：Python编译、Vue类型检查与Vite生产构建通过（83 modules，596ms），未启动模型或正式任务，待软件复测。
- 当前状态：软件测试退回，待处理；同步旧静态测试为服务端统一阶段行为契约后完整重跑。
- 前端整改：公开`runUpscale`改为非async并直接返回project/session唯一`upscaleFlight`；报价、confirm、runStage、merge、persist全事务共用controller与epoch。同项目重复点击严格同Promise；项目切换/stop同步abort并释放旧键，新任务无需等待忽略signal旧Promise，旧finally按flight/controller/epoch身份不得清新任务。报价拒绝、取消或异常finally释放后可重试。
- 开发专项：静态契约与后端证据/门禁`43 passed, 1 skipped`；待独立软件测试执行正式函数quote阻塞、stop重试和忽略signal晚到动态。
- 开发扩大回归：upscale、review_export、生产控制、项目会话与阶段取消`151 passed, 1 skipped`；Python编译、Vue类型检查和Vite生产构建通过（83 modules，560ms），未启动模型。
- 最终独立软件复测：通过。旧口型测试现动态执行正式服务端video阶段，覆盖MuseTalk成功零回退、RuntimeError后LatentSync精确一次、取消checkpoint零回退，并双向断言前端生成链无两类口型直连，未弱化为静态存在性。正式前端single-flight/stop/忽略signal晚到动态复跑`10/10`，此前取消/quote异常/项目切换完整矩阵`18/18`保持；后端四步取消/失败`8/8`、台账中途失败原子回滚`1/1`、权威证据/输入门禁/增强导出相关`52/52`通过。
- 最终扩大回归：`171 passed, 1 skipped`；跳过项为既有可选环境用例。Python pycompile、Vue typecheck、Vite生产构建通过（83 modules，542ms）；文档一致，未启动模型。
- 稽查退回整改：fingerprint现规范化绑定完整command（含subtitles/reference_urls/process_audits/content_compliance_status及扩展字段）、完整增强输出、source/version、target、production evidence和结构化三步audit evidence。OCR/face启用时pass但无真实evidence失败关闭；未启用时明确记录not_applicable原因；final始终要求真实evidence。键顺序不影响哈希，任一输入或步骤evidence变化必改fingerprint，整批原子台账/确认/导出契约保持。
- 新增专项：完整输入/步骤绑定、键序稳定、四类输入突变、步骤evidence突变、not_applicable原因及启用无证据失败关闭，共`26 passed`，待扩大回归。
- 扩大回归首败记录：本增量相关`review_export/upscale/optional-media/production-control/stage-cancel`累计`157 passed, 1 skipped`；两条`test_production_gate_reconciliation`旧源码断言仍要求资产按钮直调`generateAllAssetImages`及队列内直接await，现行共享前端已统一为`queueGenerateAllAssetImages`/`enqueueAssetOperation`，结果`2 failed`。未越权修改资产队列契约。Python编译、Vue类型检查、Vite构建通过（83 modules，580ms）。
- 下一状态：待复测。

- 复稽查残留最终软件复测：通过。`production_evidence`结构化对象原类型保留；空对象/数组/字符串、NaN、Infinity及不可序列化对象均在台账前拒绝。完整嵌套command、enhanced output、production、OCR、face、final evidence递归键序重排指纹稳定，任一语义变化指纹改变；not_applicable原因、pending→confirm→enhanced export及旧批次拒绝无回归。
- 正式资产FIFO动态：严格顺序、同key单owner、epoch stop/项目切换后新owner立即执行、旧finally不删新owner或递减新count均通过。专项`45 passed`，扩大关联`180 passed, 1 skipped`；Python pycompile、Vue typecheck、Vite生产构建通过（83 modules，552ms），未启动模型。
- 最终状态：软件测试通过，待稽查。

- 端到端证据最终软件复测：通过。临时SQLite生成upscale后以全新`ProductionLedger`实例reload并confirm，嵌套dict/list production与OCR/face/final audit evidence类型和值不丢；客户端伪造evidence被权威ledger覆盖。真实导出files与manifest逐集携带`source_version/content_fingerprint/audit_batch_id/production_evidence/audit_evidence`，旧batch拒绝；base legacy明确返回`not_available/legacy_base_scope`与`not_applicable/legacy_base_scope`，不伪造证据。
- 前端`EnhancedEpisode.production_evidence/audit_evidence`为`unknown`且merge/persist/reload原样保存，不做字符串降格。事务第二条失败零部分台账、确认导出及FIFO关联保持通过。
- 最终关联回归`180 passed, 1 skipped`，Python pycompile、Vue typecheck、Vite生产构建通过（83 modules，548ms）；未启动模型。状态保持软件测试通过，待稽查。

### BUG-20260811-027：M9.182场景资产混入人物动作

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.182
- 问题：分镜编译曾把画面首句写入scene字段，导致“苏璃跪在地上”“弟子们哄笑抢夺”等人物动作被当作场景资产；空场景视觉验收虽正确拒绝人物，但无法修正上游错误分类。
- 修复：分镜编译从背景与地点词识别可复用空间并跨镜延续；资产提取、前端所有场景入口及生成API统一过滤人物动作/状态/群体行为，重建纯空场景提示；历史伪场景自动迁移。当前项目已清除20个错误场景并补回“宗门试炼场”。
- 首轮软件测试退回：伪场景校验最初位于外层production image门禁之后，直接HTTP请求先得到409 `production_gate_blocked`，未返回预期400 `invalid_scene_asset_subject`；纯函数边界10/10和新增专项4/4先行通过，发现首败后未启动模型。
- 首轮整改：伪场景校验已提升到请求JSON解析之后、工作负载转发与production gate之前；正式HTTP提交“苏璃跪在地上”现返回400 `invalid_scene_asset_subject`，不会进入调度、阶段门禁、cleanup、任务登记、ACTIVE或模型调用。
- 第二轮软件测试退回：门禁整改通过，但分镜编译只识别“背景是/为”，未识别“地点在藏经阁”，导致第11镜换场后仍沿用宗门试炼场。
- 第二轮整改：地点解析新增“地点在/是/为/：”语法，并补齐藏经阁、阁楼、楼阁等空间词；换场镜更新active_scene，后续镜头延续新地点。专项新增两种藏经阁表达并通过。
- 主线验证：纯函数与入口门禁专项、关联回归`50 passed, 1 skipped, 3 subtests passed`；Python编译、Vue类型检查、Vite构建通过（83 modules）；真实页面场景计数由20降为1，仅显示45°空场景全景。
- 软件测试首败：直接HTTP调用`/api/characters/generate`提交scene baseline伪subject时，Handler先执行`PRODUCTION_ENDPOINT_STAGES`映射的image阶段门禁，尚未进入后面的`invalid_scene_asset_subject`校验。隔离HTTP动态用例输入“苏璃跪在地上”，实际返回HTTP 409 `production_gate_blocked`，不是要求的HTTP 400 `invalid_scene_asset_subject`。现有专项只断言场景校验位于`_cleanup_invalid_image_tasks()`之前，未覆盖它仍位于外层production gate之后。发现首个失败后立即停止；此前纯函数合法地点/人物动作边界`10/10`及专项`4/4`通过，未启动模型。
- 首败整改复测：前置HTTP门禁通过。三类伪subject均返回400 `invalid_scene_asset_subject`，forward/cleanup/model调用均0，jobs文件和ACTIVE四映射均空；合法“宗门试炼场”成功越过校验进入forward。
- 第二首败：分镜编译未完整实现“从背景/地点识别可复用地点”。20镜动态剧本第1镜`背景是古色古香的宗门试炼场`可识别并跨镜延续，但第11镜`地点在藏经阁，木制书架`未识别，镜头11—20仍沿用“宗门试炼场”。`_scene_location_from_text`仅显式解析`背景是/为`，地点后缀枚举也不含`藏经阁`，对`地点在/地点：`不生效。发现失败后立即停止，未继续关联回归与构建。
- 第二首败整改复测：通过。背景是/为、地点在/是/为/冒号及藏经阁/阁楼/楼阁均识别；20镜动态用例第1—10镜为宗门试炼场，第11镜切换藏经阁后第11—20镜稳定延续，scene不含人物或群体行为。
- 最终软件测试：通过。直接HTTP三类伪场景均400 `invalid_scene_asset_subject`且forward/cleanup/model为0、jobs文件未创建、ACTIVE四映射为空；合法宗门试炼场可越过前置门禁。后端抽取净化、前端load/seed/merge/权威接管/import六入口、纯空prompt重建及45°单槽断言通过。正式唯一项目assets为waiting_confirmation，仅1个场景“宗门试炼场”，status pending/error空，prompt包含无人/无人形/无人体；8787健康且资源active/queued为0。关联回归`131 passed, 1 skipped, 3 subtests passed`，Python编译、Vue typecheck、Vite生产构建通过（83 modules）。
- 最终稽查退回：服务端前置门禁未读取项目人物名单，纯人物姓名“苏璃”“云长老”及未命中有限动作词的剧情句“苏璃被夺走玉佩”可绕过；Dev_MainDev与项目记忆状态也未同步。
- 稽查整改：新增地点型名称硬门禁，并按tenant/user/project精确读取assets与outline权威人物名单；服务端两层门禁与前端统一执行。纯姓名、剧情句、人物动作和群体行为均拒绝，合法“宗门试炼场”保留；流程文档状态已同步。
- 稽查整改软件测试首败：outline-only项目的人物实际位于`stage.data.plan.characters`，初版只读`stage.data.characters`，导致资产阶段尚未建立时权威人物名单为空。
- 首败整改与完整复测：outline plan与assets两路权威人物、跨scope隔离、非法HTTP4/4零副作用、合法宗门试炼场/藏经阁均通过；关联`132 passed, 1 skipped, 3 subtests passed`，编译、类型检查和构建通过。
- 第二次最终稽查退回：封闭地点后缀集合过窄，会误拒厨房、医院、学校、办公室、商场、酒店、机场等跨题材合法场景。
- 第二次稽查整改：服务端地点判断、地点提取与前端六入口统一扩展古装、居住、餐饮、医疗、校园、办公、商业、交通、工业、宗教、文体与自然环境地点；人物名单与动作剧情硬拒绝保持不变。
- 第二次稽查整改软件测试首败：地点扩展后，“玉佩被夺走后藏进仓库”“病人被推进医院”“车辆失控冲入商场”等以地点结尾的剧情句仍可通过。
- 首败整改：前后端新增被动事件、进入/推进/藏入/冲入、失控、夺走、打斗、爆炸等剧情结构门禁；地点白名单只负责地点候选，剧情动作门禁继续拥有否决权。
- 最终稽查：通过。跨题材合法地点、地点结尾剧情句否决、项目权威人物名单scope隔离、HTTP登记前零副作用门禁、换场延续与纯空prompt链全部闭环。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭。
- 稽查整改软件测试首败：`_project_character_names`对assets读取`stage.data.characters`正确，但对outline也只读取`stage.data.characters`；正式outline人物实际位于`stage.data.plan.characters`。隔离项目仅保存outline plan人物“苏璃/云长老”时，精确tenant/user/project查询实际返回空列表，outline权威人物无法参与伪场景拒绝；跨scope查询同样为空。发现首个失败后立即停止，未继续HTTP/回归/构建。
- 稽查整改最终软件复测：通过。outline-only精确scope返回`苏璃/云长老`，assets项目返回对应人物，跨tenant/user/project返回空。直接HTTP对“苏璃”“云长老”“苏璃被夺走玉佩”“苏璃跪在地上”均在forward/cleanup/jobs/ACTIVE/model前返回400 `invalid_scene_asset_subject`，零副作用；“宗门试炼场”“藏经阁”均放行。前端正式函数同组4个非法/2个合法动态结果与后端一致；地点后缀、人物/动作/群体规则及文档待测试状态同步。关联回归`132 passed, 1 skipped, 3 subtests passed`，Python编译、Vue typecheck、Vite生产构建通过（83 modules）；正式8787 PID 21092健康。
- 第二次稽查整改独立软件复测：通过。后端与前端正式函数分别动态覆盖跨题材合法地点`23/23`、人物/动作/剧情非法名称`9/9`及“背景是/地点在/地点：/地点为”抽取`5/5`，前后端地点集合共92项完全一致；15镜编译器动态验证“现代公司办公室”跨镜延续并在第11镜切换“医院病房”。临时HTTP对7项非法名称均在forward/cleanup/jobs/ACTIVE/model前返回400 `invalid_scene_asset_subject`且零副作用，15项合法地点均越过门禁。关联回归`132 passed, 1 skipped, 3 subtests passed`，Python编译、Vue typecheck、Vite生产构建通过（83 modules）；正式8787健康且资源active/queued为0，当前项目仅“宗门试炼场”一项、pending/error空、纯空提示完整。Dev_MainDev、项目进度、项目记忆三份流程记录已同步。
- 下一状态：待稽查。

### BUG-20260811-026：M9.181全局提示统一进入项目对话框

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.181
- 开发结果：统一`notify()`不再生成底部蓝色Toast，改为向当前项目对话追加助手侧“系统提示”消息；连续相同提示去重并自动滚动到末尾。系统提示不写回助手历史，避免保存失败递归；阶段状态与错误字段继续作为恢复和任务门禁事实源。
- 主线验证：真实后台页面点击“预览设置”后，对话区出现“已打开预览显示设置 / 系统提示”，DOM不存在Toast横幅；关联回归`115 passed, 1 skipped, 3 subtests passed`，Vue类型检查与Vite生产构建通过（83 modules）。
- 独立软件测试：通过。动态执行正式`notify`函数：空文本忽略、连续同文去重、非连续同文保留，3条消息均为助手侧`status=系统提示/notice=true`，聊天滚动位置精确到scrollHeight。静态验证App.vue无toast ref/DOM，持久化统一`filter(chat => !chat.notice)`，项目切换通过project-scoped cache隔离，history响应与发送均有project/session门禁。关联回归`115 passed, 1 skipped, 3 subtests passed`，Vue typecheck与Vite生产构建通过（83 modules）。独立浏览器控制实例不可用，本轮以正式函数动态执行、DOM源码门禁和主线真实UI证据组合验收。
- 最终稽查：通过。正式提示统一进入当前项目助手对话，空文本、连续去重、非连续保留、自动滚动、项目隔离及聊天恢复/发送链均成立；Toast引用与DOM已移除，notice不写助手历史。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭。

### BUG-20260811-025：M9.180资产自动生图与assets阶段冲突修复

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.180（按当前M9.179顺延；用户消息中的M9.175为待确认旧编号）
- 软件测试首败：新增门禁测试要求`/api/characters/generate`不再属于`PRODUCTION_ENDPOINT_STAGES`的assets阶段、仅属于image资源；但关联回归`tests/unit/test_production_control.py::ProductionControlTests::test_formal_production_endpoints_enter_langgraph_gate`仍强制断言`"/api/characters/generate":"assets"`。
- 测试证据：`test_production_gate_reconciliation.py + test_production_control.py`运行结果`1 failed, 95 passed`；失败断言与本次设计直接冲突。发现首个失败后立即停止，未启动真实Klein任务、未修改业务代码，动态HTTP、停止/失败终态、编译与前端构建尚未执行。
- 首轮关联测试契约整改后复测：相关回归`107 passed`，但发现项目切换竞态仍未封闭。`generateAllAssetImages(project, session)`等待`projectService.readStage`返回后，在合并characters/scenes/props和清理error前没有`isCurrentProjectSession(project.id, session)`围栏；随后还调用`persistAssetState(project, projectSession)`，误用当前会话而非捕获session。p1读取阻塞期间切换p2时，p1晚到数据可直接覆盖并以p2当前session持久化。发现首个功能失败后立即停止，未启动真实Klein任务。
- 第二轮整改复测：项目切换确定性动态用例通过，p1 read阻塞后切p2，p1晚到时merge/persist/baseline/purge调用均为0；watchdog活worker processing保留、死worker回收、活worker硬截止失败`3/3`；关联回归`122 passed`。
- 第二轮真实任务首败：既有job `10bb153a-f7cc-4b37-affb-b44bbaf78beb`从04:17:25运行至04:19:11，证明跨4秒审核期间未被watchdog误杀，但最终为failed而非completed；错误为人物左45°全身基准图未通过左45方向、顶部留白、头身比、腰部裁切及上下臂比例规范验收。终态pid/pgid均空，8787健康且资源active/queued为0。因明确要求“真实任务跨4秒审核与完成”，发现失败后立即停止，未继续编译/typecheck/build。
- M9.180开发收口：资产批次新增project/session级single-flight、独立AbortController和batch token；权威read响应后、合并/状态/error变更、purge/基准图模型调用前后及每次persist前后统一检查启动project+session+signal+token。generateAssetBaseline继承同一signal，项目切换/停止会abort并释放旧flight，旧成功/异常/忽略signal均零写回、零后续模型；finally按flight/controller/token身份清理，新重试不受旧Promise影响。所有persist统一使用捕获session。
- 动态首败修复：新增按旧flight/controller/token三重身份的`reclaimAssetBatchProjection`，项目切换或stop同步复位batchGenerating、stage status及旧generating卡片并释放旧键，使新项目/重试立即启动。旧finally仅在三重身份仍一致时复位；stop增加epoch，旧stop响应不得覆盖其后新批次。
- 第四轮修复：公开`generateAllAssetImages`移除async包装，直接返回唯一`assetBatchFlight`；内部`runAssetImageBatch`仍为async。相同project/session重复调用获得严格相同Promise identity且只启动一批，既有await调用兼容；异常finally、项目切换和stop仍按三重身份释放。
- 第三轮软件测试首败：真实执行正式`generateAllAssetImages/runAssetImageBatch`异步闸门，p1在权威`readStage`阻塞时切换p2并执行现行项目回收（abort controller、清flight/key/token）。p1已使`assetBatchGenerating=true`，项目回收没有复位该全局标志；p2调用被`assetImagesRunning.value`直接拦截，`readStage`调用数保持1而非2，无法启动独立新批次。
- 根因：`abortProjectWork`清除controller/flight/token但不清`assetBatchGenerating`、`activeAssetGenerationKey`或相关项目级运行投影；旧p1因session/token已失效，其finally也不会清理这些标志，形成跨项目永久背压。不同项目实际仍共享残留运行态，不满足本轮明确门禁。
- 动态证据：切换前`reads=1, assetBatchGenerating=true`；切换并调用p2后`reads=1, assetBatchGenerating=true`，p2零权威读取、零批次启动。发现首个失败后立即停止，未执行其余purge/model/stop矩阵、关联、编译与构建，未启动模型。
- 预期整改：项目切换回收必须按旧controller/token身份安全复位资产批次运行标志，且不得让旧finally清除随后建立的新批次；p2应立即取得独立flight并发起自己的权威读取。
- 最终复测首败：真实证据job `e6bdf6db-e8c6-4289-95b6-8cd49b4bd9cd`已completed，苏璃waiting_confirmation/error空，后续云长老job `29623e2e-7ee3-4546-b162-58b2f0df2af3`紧接启动为processing，串行顺序成立；但关联回归`test_automatic_asset_generation_keeps_original_project_session_fences`失败。测试仍要求`stopAllAssetGeneration`源码直接出现`batchController?.abort()`，当前实现已改由`reclaimAssetBatchProjection(assetBatchFlight, assetBatchController.value, activeAssetBatchToken)`内部执行`controller?.abort()`并按flight/controller/token身份回收，测试契约未同步现行封装。回归结果`1 failed, 126 passed`。发现首败后立即停止，未继续编译/typecheck/build。
- 最终完整复测：通过。停止回收及purge signal测试契约已同步；资产/生产门禁/图片任务/方向验收/场景/服装/规范关联回归累计`154 passed, 3 subtests passed`。watchdog动态活worker保留、死worker回收、硬截止强制failed`3/3`。真实苏璃job `e6bdf6db…` completed并持久waiting_confirmation/error空，随后云长老job `29623e2e…`自动串行启动；云长老规范验收失败后正确停止为pending/error保留，未继续后续资产，pid/pgid清空，8787健康且资源active/queued为0。最新左45候选镜像后重新验收、30—60度确定方向及失败终态断言通过；project/session/controller/token/single-flight/finally隔离与精确assets冲突清理通过。Python编译、Vue typecheck、Vite生产构建通过（83 modules）。
- 第四轮动态复测进展：p1权威readStage阻塞切p2后立即第二次read，释放p1不清p2 flight/controller/token/generating/status且仅p2完成复位，`10/10`；p1 baseline忽略signal晚到不继续下一资产、不写p2，`7/7`；p1 purge忽略signal晚到不清p2或旧上下文，`6/6`。三组共`23/23`通过，persist均使用捕获project/session。
- 第四轮软件测试首败：同项目连续两次调用`generateAllAssetImages`时，底层批次只启动一次，但两个返回值不是同一Promise。正式入口仍声明为`async function generateAllAssetImages`；即使命中`return assetBatchFlight`，async函数也会返回采用该flight状态的新外层Promise，动态严格身份`first === second`为false。
- 预期整改：将公开单飞入口改为非async函数并直接返回权威`assetBatchFlight`，内部`runAssetImageBatch`保持异步；整改后重跑stop epoch、失败释放重试、三重身份、关联与构建。
- 第四轮首败整改复测：通过。正式入口现为非async `function generateAllAssetImages`并直接返回权威flight；动态执行当前源码，同项目连续调用严格`first === second`为true，底层`runAssetImageBatch`启动计数精确为1。历史项目切换、token/controller/finally、stop epoch、purge signal、watchdog、真实completed→自动续生证据保持有效；关联回归`154 passed, 3 subtests passed`，Python编译、Vue typecheck、Vite生产构建通过（83 modules）。
- 第四轮独立软件复测：通过。当前正式函数严格`first === second`、底层批次1次；stop先回收后可立即取得不同新flight，旧stop响应与旧finally不清新controller/token/status；异常finally完整释放且重试取得新Promise，专项`16/16`。readStage、purge、baseline忽略signal的跨项目晚到矩阵`23/23`保持通过，所有persist使用捕获project/session。
- 第四轮关联复测：资产/生产门禁/图片任务/方向验收/场景/服装/规范共`155 passed, 1 skipped, 3 subtests passed`；跳过项为环境可选测试，不影响本增量。Python编译、Vue typecheck、Vite生产构建通过（83 modules，637ms），文档一致，未启动模型。
- 稽查退回：`_durable_task_projection`仍把`/api/characters/generate`投影为assets，导致人物/场景/道具二维任务的running/completed/failed可覆盖资产清单阶段；同时正式stage、资源映射与持久投影不一致。
- 稽查整改：二维人物/场景/道具、分镜及辅助生图三处统一为image；`asset_3d`明确为assets stage/3d资源。新增临时SQLite/outbox动态验证characters/generate从running到pending_confirmation/failed全程只报告image且绝不报告assets；首轮关联`102 passed, 1 skipped`，待扩大回归与独立软件复测。
- 开发验证：投影专项与核心生产门禁`102 passed, 1 skipped`；扩大图片/3D/阶段回归`171 passed, 1 skipped, 1 failed`。唯一首败为`test_storyboard_resume_frontend.py::test_storyboard_resume_preserves_existing_shots_and_only_appends_missing`，期望App.vue包含旧源码字面量`existingShots:StoryboardShot[] = []`，现行共享前端不存在该字面量；按首败规则保留给独立软件测试判定，未修改该链。Python pycompile、Vue typecheck、Vite生产构建通过（83 modules，598ms），未启动模型。
- 软件测试确认上述分镜失败为真实产品回归：既有完整ep1+scripts1/2仍调用1、2集并整体替换shots。整改后服务端读取body/context既有shots，完整性契约为15–23镜、镜号和时间线连续、单镜2–9秒、覆盖目标总时长；完整集跳过、部分集整集重生。完整ep1含图片/确认/版本字段序列化前后不变，无缺失零模型；重复/非法/跨集provider输出拒绝。前端随请求提交existingShots，仅按generated_episodes替换，并在响应、异常与持久化前保持启动project/session/signal围栏。专项与关联`104 passed, 1 skipped`，待扩大回归。
- 开发扩大验证：storyboard续生成、持久image投影、生产门禁、图片生命周期、asset_3d、服装、阶段取消共`176 passed, 1 skipped`；Python pycompile、Vue typecheck、Vite生产构建通过（83 modules，589ms）。未启动模型或正式任务，交独立软件测试执行项目切换晚到动态闸门。
- 投影软件复测：通过。二维人物/场景/道具、分镜与辅助生图三份映射均为image，`asset_3d`为assets/3d；临时durable outbox/Graph验证generating→running、completed→pending_confirmation、failed→failed全程只报告image且绝不报告assets，专项`3/3`。
- 扩大回归首败判定：`test_storyboard_resume_frontend`不是可忽略的旧字面量。动态执行当前正式`_run_server_production_stage(stage=storyboard)`，输入已有第1集分镜及第1、2集剧本，实际仍调用`/api/storyboard`生成第1集和第2集，并返回两集全新结果；已有第1集分镜未保留。实际调用`[(storyboard,1),(storyboard,2)]`，预期仅`[(storyboard,2)]`。
- 最终独立软件复测：通过，状态流转待稽查。动态覆盖15/23镜边界、连续镜号/时间线、单镜2–9秒及目标总时长；完整ep1+scripts1/2仅调用ep2且ep1嵌套字段序列化不变，partial ep1整集重生，全完整零模型；重复剧本、重复镜头、跨episode及不完整provider输出均在错误合并前拒绝，服务端动态矩阵`18/18`。实际前端merge函数动态验证仅替换`generated_episodes`并保留existing/audits，项目/session晚到成功与异常零污染，新项目正常合并`5/5`。二维图片与asset_3d投影专项`3/3`；扩大关联回归`163 passed, 1 skipped, 3 subtests passed`，Python编译、Vue typecheck及Vite生产构建（83 modules）通过。既有资产批次read/purge/model晚到与strict Promise专项39项证据保持有效；本轮未启动模型。
- 状态：软件测试退回，待处理。
- 根因：分镜服务端内核初始化`shots=[]`并遍历全部scripts，既不读取/接受权威existing shots，也不按已完整episode过滤missing scripts；前端现在只提交scripts且最终用response.result.shots整体替换。因此“续生成仅补missing并保留existing”功能确实回退，不是测试仍引用旧前端实现方式的问题。
- 预期整改：把续生成行为迁入服务端权威内核：接收或从持久stage读取已完成shots，按完整episode只生成缺失集，确定性合并并返回existing+new；测试应验证行为/调用集合，不绑定旧前端局部变量字面量。
- 本轮按首败停止，未继续batch晚到/strict Promise、扩大关联、编译与构建；未启动模型。
- 下一状态：已关闭。
- 最终稽查：通过。二维图片入口、资源类型及durable Graph投影统一为image，仅asset_3d保持assets/3d；自动串行、project/session/controller/token/epoch隔离、严格同一Promise及精确回收闭环。分镜完整集按15–23镜、连续时间线、2–9秒和目标时长权威识别并原样保留，partial整集重生，仅补缺集；非法、重复与跨集输出失败关闭。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 最终状态：最终稽查通过，已关闭。
- 稽查证据：目标组合`145 passed, 1 skipped, 3 subtests`，扩大组合`197 passed, 1 skipped, 3 subtests`，Python编译通过；软件类型检查及83模块构建有效。正式PID18800健康，唯一worker、三池、Ollama及ComfyUI均空闲。

### BUG-20260811-024：M9.179前端最终审核仍循环重复提交服务端阶段

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.179
- 软件测试：不通过；review_export后端专项`6 passed`后检查前端正式入口发现首败并立即停止。未启动模型或正式任务。
- 失败项：`auditFinalEpisodes`仍在`for (const master ...)`逐集循环内，再套`while (attempts <= 2)`修复重试循环；`productionLedgerService.runStage(stage=review_export, operation=audit)`位于该双重循环内部。一次“最终审核”点击可提交`集数 × 最多3次`独立阶段请求，并非要求的单次整批runStage。
- 动态/静态证据：目标函数存在episode loop=true、retry loop=true，runStage位于retry loop之后且在其作用域内；源码调用点虽只有1处，运行次数不唯一。服务端现有audit执行器已支持commands数组，但前端每次只传一个command。
- 风险：阶段租约在每次请求结束即提交pending_confirmation；前端随后再次调用同一阶段，可能出现阶段已运行/待确认冲突、部分集已写回、重复模型审核和项目切换晚到污染。有限修复仍由前端编排，未迁入服务端唯一内核。
- 预期：一次用户操作只调用一次`runStage(review_export/audit)`，一次传入所有目标episode；批量审核、每集有限修复及最终证据由服务端阶段执行器完成。前端仅原子接收整批结果，并以project/session/abort围栏拒绝晚到响应。
- 修复：前端先汇总全部待审分集，单次提交一个`review_export/audit`整批命令；服务端负责逐集执行、瞬态失败最多重试一次、保留每集`status/issues/evidence/attempts`。前端以project/session/abort围栏原子接收整批结果，失败集不假通过、不越级导出。
- 软件复测进展：整批审核单次runStage、服务端逐集/最多一次瞬态重试、取消不重试、needs_fix证据、导出门禁和零副作用矩阵通过；专项`12/12`、关联`133 passed`、Python编译、Vue typecheck及Vite构建83 modules通过。
- 软件复测首败：`createExports`虽只调用一次runStage，但没有捕获`projectSession`、没有AbortController/signal，也没有任何`isCurrentProjectSession`响应围栏；请求返回后无条件写`exportFiles/exportManifestUrl/exportStatus`并持久化。p1导出阻塞后切换p2，p1晚到成功或异常会污染p2。
- 静态证据：目标函数`runStage=1`，但`projectSession=false`、`AbortController=false`、`signal=false`、`current_guard=false`，同时存在无条件`exportFiles.value = result.files`。这与本轮明确要求的project/session/abort晚到隔离不符。
- 预期：导出与审核采用相同project/session/AbortController围栏；提交前、响应后、catch和每次持久化前校验当前项目，项目切换主动abort；不遵守signal的晚到成功/异常也必须丢弃，不能改写新项目状态或错误。
- 第二首败修复：导出按project ID复用同一在途Promise，提交前、响应后、状态/文件/manifest替换及持久化前均校验project+session+abort；项目切换和停止统一abort。晚到成功/异常零写回，finally仅释放自身flight/controller，释放后可安全重试。
- 第三轮软件复测首败：`stopExports`仅执行`exportController.abort()`并把本地状态持久为failed，没有调用任何服务端定向stage stop，也不清理当前`exportFlight`。若runStage忽略signal或网络请求迟迟不返回，服务端review_export租约继续执行，同项目再次点击仍返回旧Promise，无法按“已停止，可重新提交”立即重试。
- 静态证据：stop函数`abort=true`、`failed=true`、`persist=true`，但`stage_stop=false`、`clear_flight=false`。这不满足本轮明确要求的“stop后abort+定向stage stop/failed持久且可重试”。
- 预期：停止必须先abort本地请求，再以完整tenant/user/project定向调用正式stage stop（review_export）；持久停止状态并解除或代际隔离旧flight，使新提交不复用已取消Promise。旧请求即使忽略signal晚到仍零写回。
- 第三首败修复：`stopExports`使用完整tenant/user/project调用统一`/api/generation/stop`并精确指定`stage=review_export`；服务端按租户stage lease取消，未确认停止返回冲突而非伪成功。停止先递增export epoch并释放旧flight键，旧Promise仍阻塞时也可重新提交；旧flight晚到与finally受epoch/Promise/controller身份隔离。
- 第三轮软件复测：通过。直接提取并执行正式`App.vue`函数，以不遵守AbortSignal的旧`runStage`闸门验证：同项目重复点击单飞、完整tenant/user/project/review_export定向stop恰一次、确认停止后立即新建flight、旧成功响应晚到零污染且旧finally不清新flight，共`7/7`；stop返回503时保持非终态generating、保留既有files/manifest并持久诊断错误、不伪报已停止，共`4/4`。
- 关联复测：审核/导出整批、空/非法/重复episode零副作用、审核pass+confirmed门禁、瞬态最多重试一次、取消不重试、完整租户隔离及generation/commit guard共`135 passed`；合计动态与关联`146/146`。Python编译、Vue typecheck和Vite生产构建通过（83 modules，689ms）。未启动重模型或正式任务。
- 稽查退回：导出门禁仍信任请求体`audit_results`，可伪造pass+confirmed；未读取服务端生产台账的分集审核确认与当前媒体指纹。
- 稽查修复：`audit_results`仅作声明。服务端按tenant/user/project读取`PRODUCTION_LEDGER`的`review:{episode}`和composition/upscale权威scope，强制completed、confirmation存在且confirmation/声明/台账的content_fingerprint与audit_batch_id一致；伪造、跨租户项目、旧指纹批次、未确认及媒体版本不匹配均在调用export provider前失败。显式`audit_required=false`保留。
- 复稽查2修复：`audit_required=false`只跳过review审核，不跳过媒体门禁；媒体scope始终要求completed、confirmation、非空fingerprint/batch且完全匹配。source_version仅允许base/enhanced，分别精确绑定composition/upscale，禁止交叉匹配或回落；多集缺任一集整批零副作用。
- 关联旧测试契约已回正：production endpoint断言不再要求characters/generate进入assets阶段，改为run-stage负责assets清单、characters/generate使用image资源；自动资产队列调用必须显式传project/session，并断言会话晚到隔离。业务实现未回退旧映射。关联126项通过。
- 复稽查2软件测试：不通过。严格动态媒体来源矩阵`15/15`、审核开启权威矩阵`8/8`及专项`14/14`通过后，关联回归发现首败并按规范停止；未执行pycompile/typecheck/build，未启动模型或正式任务。
- 关联首败：`tests/unit/test_production_control.py::ProductionControlTests::test_formal_production_endpoints_enter_langgraph_gate`仍断言`/api/characters/generate → assets`，现行权威映射明确为`/api/characters/generate → image`。独立核对确认不是产品回退：资产清单提取统一经服务端`run-stage assets → /api/characters/extract`，人物图片生成是后续image阶段；`test_production_gate_reconciliation.py`也明确要求旧assets映射不存在、image资源映射存在。旧静态断言与共享现行契约冲突。
- 同类旧断言：继续隔离确认时，`test_storyboard_persists_each_completed_episode_and_frontend_creates_asset_cards_immediately`仍要求无上下文`generateAllAssetImages()`；正式代码已使用`generateAllAssetImages(project, session)`保持项目/会话晚到隔离。该断言同样是旧不安全调用签名，不是产品功能回退。
- 预期整改：同步两条关联静态测试到现行共享契约：图片生成端点属于image；自动基准生成必须显式传project/session。整改后重新执行完整关联、动态stop/session/singleflight、Python编译、Vue类型检查与生产构建。
- 最终软件复测：通过。两条旧测试已改为双向精确契约：显式断言`characters/generate→assets`不存在且`characters/generate→image`存在；自动队列强制`generateAllAssetImages(project, session)`并校验提取先于生成，未通过删除断言放宽门禁。
- 最终回归：production_control、gate_reconciliation、review_export、stage_cancel四组`126 passed`，其中权威导出专项14项覆盖audit false媒体门禁、base/enhanced严格来源、审核台账、批次指纹、多集零副作用及stop/session/singleflight。Python编译、Vue typecheck、Vite生产构建通过（83 modules，692ms）；文档一致，未启动模型。
- 权威门禁软件复测：通过。临时SQLite动态矩阵覆盖伪造pass+confirmed无台账、跨tenant/user/project、review未completed/无confirmation、声明或台账fingerprint/batch不一致、review/media确认陈旧、当前媒体不匹配及多集缺一项，全部零export provider；真实逐集review+composition completed/confirmation/匹配指纹批次唯一放行，`audit_required=false`显式放行，共`15/15`。
- 真实API复测：localhost正式Handler `/api/production/run-stage`在匹配权威证据时HTTP 200且导出调用1次，伪造batch时HTTP 409且导出调用0次，`2/2`。前端实际指纹函数验证审核落台账content_fingerprint/audit_batch_id与导出声明完全一致`2/2`，审核和导出各仅一个正式runStage调用点。
- 关联复测：正式前端函数stop/late/session动态闸门`7/7`；整批审核、租户隔离、取消与commit guard共`137 passed`；合计专项与关联`163/163`。Python编译、Vue typecheck和Vite生产构建通过（83 modules，728ms），文档一致。未启动重模型或正式任务。
- 最终稽查：通过。`audit_required=false`仅豁免review审核，媒体权威门禁始终执行；`source_version=base/enhanced`分别严格绑定composition/upscale，跨scope、旧fingerprint/batch、缺集均在provider调用前整批拒绝。整批单runStage、项目会话/epoch/single-flight、精确停止及generation/cancel/commit围栏无回归。
- 稽查证据：动态探针覆盖伪造、交叉版本、合法base与多集缺证；关联`126/126`与Python编译通过。正式8787健康，唯一worker及三池空闲，Ollama、ComfyUI均为空。
- 下一状态：已关闭。

### BUG-20260811-023：M9.178阶段取消未贯穿审核修复内部链

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.178
- 软件测试：不通过；阶段cancel-before与基础循环专项`14 passed`后，审核中途取消动态发现首败并立即停止。未启动模型或正式任务。
- 失败项：outline/script/storyboard调用`_audit_and_repair_narrative`时只传`context`，没有传递`_cancel_event`；该函数在分块循环、初审→修复→终审之间也没有阶段checkpoint。取消在初审返回时发生，代码仍继续提交修复模型和最终审核模型，直到整个审核链返回外层后才检测取消。
- 动态证据：outline单集生成后进入audit；隔离初审`audit.narrative`设置cancel event并返回needs_fix，实际后续调用序列仍包含`text.narrative.repair`及第二次`audit.narrative`，随后外层才抛`production stage cancelled or lease lost: outline`。
- 同类风险：三种叙事阶段共享审核函数；超9KB分块在取消后仍可继续下一批，审核、修复和终审均可能产生取消后的新模型调用、费用及晚到结果。
- 预期：阶段cancel event必须传入审核内部；每个chunk、初审前后、修复前后、终审前后均调用同一租约checkpoint。任一点取消后不得再调用任何模型，也不得进入pending_confirmation或项目写回。
- 主线整改：outline/script/storyboard把同一`_cancel_event`传入共享审核函数；分块、初审、修复和终审前后均执行统一stage checkpoint。取消控制对象只在进程内使用，provider/远端审核payload会主动剔除，避免Event进入序列化边界。
- 开发验证：新增“初审返回时取消”动态用例，确认调用序列仅有第一次`audit.narrative`，不再调用repair或终审；取消对象未进入能力payload。阶段取消关联回归`109 passed`，Python编译通过，未启动模型或正式任务。
- 软件复测后端：通过。outline/script/storyboard在chunk、初审、repair、final audit各节点中途取消矩阵`10/10`，取消后零后续模型调用且`_cancel_event`未进入provider payload；八阶段/批次/command/video poll、租户隔离、显式取消/纯失租/commit guard关联共`126 passed`，Python编译通过。
- 软件复测首败：Vue类型检查失败，`App.vue:4039`的`stopAsset3D`调用`productionTaskContext(project)`，但函数作用域没有声明`project`。原始错误：`TS2304: Cannot find name 'project'`。当前停止入口无法通过正式构建门禁，发现后停止Vite build。
- 同类边界：该函数必须取得并校验当前活动项目上下文；项目缺失时禁止发送停止请求，不得使用未定义变量或把停止发往错误项目。
- 前端整改：`stopAsset3D`在发送停止请求前读取并校验当前活动项目；项目缺失直接返回，存在时把该项目显式传入`productionTaskContext`，不再引用未声明变量或构造空project ID。
- 开发验证：Vue typecheck通过；Vite生产构建通过（82 modules，722ms）。后端关联`109 passed`与Python编译继续通过。
- 最终软件复测：通过。无活动项目时`stopAsset3D`零停止请求；有项目时使用`productionTaskContext(project)`发送完整tenant/user/project身份。审核节点取消矩阵`10/10`、八阶段及停止/租户/代际/commit guard关联`126 passed`，Python编译、Vue typecheck与Vite生产构建通过（82 modules，701ms）。
- 测试期间未启动模型或正式任务。
- 最终稽查：通过。八阶段入口及批次、command、poll、本地调用、审核、修复与fallback均受同一lease event约束；provider payload不含进程内Event。结果提交继续受owner/generation与SQLite commit guard保护，显式取消与纯失租语义不混淆；完整租户身份及child scope阻止跨租户误停。
- 稽查复核：只读回归`128/128`与Python编译通过；正式PID98981唯一worker健康，三池、Ollama与ComfyUI均空闲，未干预服务。
- 下一状态：已关闭。

### BUG-20260811-021：M9.177跨实例派发预留未接入正式派发入口

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.177
- 软件测试：不通过；发现首个失败后立即停止，未执行其余回归，未启动模型或操作正式服务。
- 失败项：`WorkerRegistry.reserve/release_reservation`虽已实现，但正式`_forward_production_request`仍只调用进程内`WORKLOAD_ROUTER.route`，从未创建、持有或释放SQLite dispatch reservation。多个网关依据同一心跳可同时选择同一capacity=1远端worker，M9.177要消除的跨实例超卖在正式路径仍然存在。
- 动态证据：隔离替换`WORKER_REGISTRY`记录reserve/release调用，并让旧router选中远端节点完成一次`/api/outline/plan`转发；响应HTTP 200且`_dispatch.worker_id=remote`，实际`reserve_calls=0`、`release_calls=0`。
- 同类范围：所有进入`_forward_production_request`的text/audit/image/video/audio/control/3d/upscale及`run-stage`远端投递均未使用预留；request幂等、TTL、generation、容量与内存预留因此只停留在未消费的注册表API。
- 预期：正式请求边界以稳定唯一request_id调用共享`WORKER_REGISTRY.reserve`原子选点/占槽，转发完成或失败后精确释放；同一request重试保持幂等，释放/TTL/generation围栏生效，旧`route`仅保留兼容入口且不得绕过跨实例容量。
- 主线整改：`_forward_production_request`已正式调用共享`WORKER_REGISTRY.reserve`选点；显式request/job ID优先，否则按规范化路径与body生成稳定SHA-256 request ID。成功、远端业务错误、网关错误与连接异常统一在`finally`精确释放，转发头披露reservation ID。
- 开发验证：成功、HTTP 502与连接异常均验证释放；相同request重试ID稳定；跨实例容量、内存、TTL和generation关联回归共`95 passed`，Python编译与差异格式检查通过。未操作正式服务或重模型。
- 软件复测：不通过；正式派发成功、业务409、网关502/503/504、URLError/OSError、响应JSON异常的reserve/finally release矩阵`10/10`，关联`76 passed`及Python编译通过后，幂等资源身份边界发现首败并停止。
- 复测失败：`worker_reservations`只以`request_id`为主键；命中未过期记录时未校验本次`resource_class/service_scope/estimated_memory`与旧预留一致。相同稳定job ID先预留text后请求video，实际仍返回仅支持text的旧worker，绕过video资源与90内存门禁。
- 动态证据：`shared-job`先以`text/scope-a/memory10`预留`text-only`成功；随后同ID以`video/scope-a/memory90`调用仍返回`text-only(resource_classes=('text',))`，SQLite记录仍为旧text/memory10。预期拒绝冲突身份或使用绑定阶段/资源的无碰撞reservation ID。
- 同类风险：同一job ID跨阶段、资源或service scope复用均可错误路由并绕过容量与内存。幂等键必须绑定完整派发身份。
- 整改：reservation schema新增`service_scope`并兼容迁移旧库；命中相同request_id时必须与原`resource_class/estimated_memory/service_scope`三元契约完全一致，否则原子拒绝且旧预留不变。新增跨资源、内存、scope冲突矩阵，关联95/95通过。
- 第二次软件复测：通过。相同ID的resource、estimated_memory、service_scope冲突全部原子拒绝且旧预留不变；一致契约保持幂等。成功、业务409、502/503/504、URLError/OSError、JSON异常均精确释放并携带reservation头，规范SHA稳定且path敏感；容量、内存、generation、TTL、防循环与旧route兼容无回归。
- 测试证据：派发异常矩阵`10/10`、关联`78 passed`，WorkerRegistry与compat_server Python编译通过。未操作正式服务或模型。
- 稽查退回：旧schema并发迁移使用无锁`PRAGMA→ALTER`，8实例同时启动稳定7个报`duplicate column name: service_scope`。
- 迁移整改：WorkerRegistry初始化以`BEGIN IMMEDIATE`串行建表/读schema/ALTER/建索引；新增8线程旧schema并发迁移测试，8/8构造成功、列唯一，关联96/96通过。
- 迁移软件复测：通过。8实例旧schema并发初始化全部成功且service_scope唯一，迁移后reservation正常；关联`79 passed`及Python编译通过。
- 正式加载：PID98981晚于最新WorkerRegistry/compat代码，schema唯一service_scope且当前reservation=0；旧worker超时清退后唯一worker healthy/active0，三池0、Ollama0、Comfy0/0。
- 下一状态：待稽查。

### BUG-20260811-022：统一任务仓库遗留非终态图片任务未被恢复

- 状态：已关闭（最终稽查通过）
- 正式只读证据：job `56efa931-14de-4005-b22c-4e9c89192537`在`unified-tasks.sqlite`为`image/queued/qwen_repairing`，heartbeat为2026-08-08；无PID、进程组、worker、资源或Comfy占用。分类JSON中的同ID payload只有heartbeat/stage，没有status与身份。诊断期间未手工删除或改写正式数据库。
- 根因：统一仓库列状态由旧缺字段payload默认成`queued`，但`_merge_durable_tasks`恢复时只复制原payload、不回填仓库权威`status/job_id/identity`列；`_recover_image_jobs`读取到`status=None`后跳过，watchdog同样无法识别。
- 主线整改：`_merge_durable_tasks`使用统一仓库权威列补齐历史payload缺失的job ID、租户身份、stage、status、进程和时间字段；启动恢复与watchdog因此能识别分类JSON缺失/残缺的非终态任务，并复用正常`_save_image_jobs → durable upsert/outbox → Graph projection`失败化。
- 动态验证：隔离构造仅存在统一仓库、payload无status的旧image queued任务；启动恢复后仓库与payload均为failed、租户身份保持、outbox清空、对应租户项目Graph image=failed；第二次恢复保持终态不变。专项及关联`119 passed`，编译与差异格式检查通过。正式数据库未修改。
- 正式首验退回：历史任务虽收敛failed/nonterminal=0，但原始project_id为空，投影被ignored直接ack，未形成Graph状态。
- 身份隔离整改：缺失真实project的可证明遗留image孤儿不猜测任何用户项目；分配确定性租户级`recovered-orphan-image-<job_id>`隔离身份并写入`identity_recovery=quarantined_missing_project`，再沿正常save/outbox/Graph链提交failed。
- 身份隔离软件复测：通过。缺project孤儿生成确定性隔离项目与identity_recovery证据，经正常save/outbox投影Graph failed并ack；真实project保持，普通terminal缺project不改，二次恢复幂等。动态`12/12`、关联`79 passed`及Python编译通过。
- 独立软件测试：隔离覆盖repository-only `queued/generating/retrying/processing`、分类JSON缺项、权威job/identity/stage/status/pid/heartbeat补齐、正常save/outbox/Graph投影、租户隔离、terminal保护与二次恢复幂等，动态矩阵`15/15`；关联`78 passed`，DurableTaskRepository与compat_server Python编译通过。未操作正式服务、数据库或模型。
- 剩余验收：主线仅可在正式资源/Ollama/Comfy全空后安全加载最新代码；软件测试随后只读确认历史`56efa931-14de-4005-b22c-4e9c89192537`通过正常恢复链变为failed、Graph/outbox一致且tasks nonterminal=0，禁止直接改库。
- 正式加载软件验收：不通过。PID 98000已加载最新代码，历史job通过正常恢复变为failed、payload补齐job_id/status/tenant/user/stage/pid、nonterminal=0且outbox=0；但权威列与payload的`project_id`仍为空，身份不完整。
- 正式首败：`_durable_task_projection`要求tenant/user/project全非空；该job project为空，因此投影返回None，`_drain_durable_task_projections`把事件加入ignored并直接ack删除。outbox=0并非Graph提交成功，而是无项目身份事件被丢弃；无法取得对应Graph state，违反“payload身份完整、outbox/Graph一致”。
- 只读证据：统一库job=`failed`、tenant=`local-default`、user=`aoo`、project=`''`，payload同样无project_id；`task_projection_outbox=0`、全库nonterminal=0。调用ProductionOrchestrator空project state明确报`tenant_id, user_id and project_id are required`。
- 正式环境：LaunchAgent PID98000路径/cwd/PYTHONPATH正确且晚于最新代码；worker清退后唯一healthy/active0，三池0、Ollama0、Comfy0/0。BUG021正式schema已含service_scope并加载。
- 预期：历史任务缺少可证明project identity时不得伪造Graph一致或静默ack；必须通过可验证的持久关联恢复项目身份后投影，或保留明确不可归属的失败/outbox诊断状态供受监督处置，禁止把无效投影视为完成。
- 最终正式补验：通过。历史`56efa...`及同类可证明孤儿均持久为`recovered-orphan-image-<jobid>`、`identity_recovery=quarantined_missing_project`、failed；目标Graph image=failed，outbox0、nonterminal0。正式仍有82条普通terminal缺project记录未写identity_recovery，未被隔离逻辑改写。
- 正式环境：PID98981路径/cwd/PYTHONPATH正确且加载时间晚于最新代码；唯一worker healthy/active0，三池、reservation、Ollama与Comfy全空。
- 下一状态：待稽查。

### BUG-20260811-020：视频任务已终态但所属Comfy prompt继续占用通道

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.175视频任务生命周期补强。
- 只读现场：正式job `4ebd29d2-80d6-4605-ac2b-7db821cd6cbc`已于2026-08-11 09:48:11持久化为`cancelled/stage=cancelled`并释放accelerator，但其owned prompt `6a8985fe-bd92-4fa0-9c75-72c5bd59d953`在09:55仍处于Comfy `queue_running`。诊断和开发期间未手工停止、清队列、重启或干预该prompt。
- 根因：旧`_cancel_comfy_prompt`只发送一次delete/interrupt，吞掉异常且不确认prompt从queue消失；`_stop_video_generation`随后无条件写cancelled、取消资源并移除ACTIVE。H3/Context finally同样只发取消不确认；watchdog只处理非终态任务，不核对终态job仍持有的prompt。
- 主线整改：owned prompt取消改为精确确认`queue_running/queue_pending`消失；未确认时stop只写`generating/cancel_pending`和cancel_requested，不返回stopped、不取消资源票据、不移除ACTIVE。Context/H3 finally与所有视频终态提交前后均等待所属prompt确认消失。
- 看门狗恢复：识别`completed/failed/cancelled`但owned prompt仍在queue的矛盾状态；取消无法即时确认时恢复为`cancel_pending`、重新取得视频资源票据，由专属恢复worker持续核销，确认queue消失后才恢复原终态。重启与关闭同样禁止取消未确认却写回终态。
- 开发测试：轻量动态覆盖running→absent确认、持续queued超时返回false、stop未确认不报成功/不释放、终态orphan持票据恢复及结果查询分支原子终态；关联`119 passed`，后端Python编译、Vue类型检查与Vite构建通过（82 modules，718ms）。未启动重模型。
- 软件测试：不通过；A项BUG019专项组合`30/30`通过后进入B项foreign prompt保护，发现首个失败即停止。未启动或干预正式重模型及现场orphan prompt。
- 失败项：owned prompt处于running时，`_cancel_comfy_prompt`无论同一queue是否还有foreign running prompt，均调用全局`POST /interrupt {}`。隔离队列同时返回`owned`和`foreign`两条running记录，取消owned实际发出空payload全局interrupt，可能终止不属于本任务的foreign prompt。
- 根因：`_comfy_prompt_queue_state`把完整queue压缩为单一状态字符串，丢失其他running prompt证据；running取消路径使用无prompt_id的全局interrupt，未提供所有权隔离或多任务保护。
- 动态证据：调用序列`GET /queue → POST /interrupt {} → GET /queue`，返回True；断言禁止全局interrupt失败。pending精确delete路径不受此问题影响。
- 预期：running取消必须使用Comfy支持的精确prompt标识；若当前接口只能全局interrupt，则发现任一foreign running prompt时禁止发送全局interrupt，保持cancel_pending与资源票据并由受监督恢复机制继续确认，绝不能影响foreign prompt。
- 整改：queue读取保留`foreign_running`证据；owned running仅在不存在任何foreign running时允许调用全局interrupt，否则不发送任何中断并返回未确认，由cancel_pending持票据恢复。新增foreign并行保护动态测试，专项组合31/31通过。
- 软件复测：通过。running/pending/absent/不可达、foreign保护、stop确认失败保持cancel_pending/ACTIVE/票据、确认成功唯一终态，以及result/watchdog/recover/shutdown终态orphan持票据恢复均通过。
- 测试证据：A/B专项`32/32`、持久路径补充`8/8`、关联`182 passed, 3 subtests passed`、Python编译、Vue typecheck、Vite build通过。正式8787健康、worker active0、三池active/queued0、Ollama0；现场orphan prompt仍running，按要求未停止、清队列或重启。
- 正式加载补验：通过。orphan prompt于10:33自然结束后由主线安全kickstart；8787 PID 91425启动于10:33:52，晚于compat_server 10:19:17，LaunchAgent `com.local.ai.compat-server`使用绝对Python/脚本、WorkingDirectory和PYTHONPATH，cwd正确。旧cancelled job保持`cancelled/stage=cancelled`且未被误恢复；唯一worker healthy/active0/capacity11，任务0、三池0、Ollama0、Comfy0/0。
- 下一状态：待稽查。

### BUG-20260811-019：M9.175 Context IR前置异常绕过统一清理

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.175
- 软件测试：不通过；发现首个失败后立即停止，未启动或干预任何重模型，未触碰正式H3任务。
- 失败项：`_optimize_h3_ref2va_prompt`在进入统一`try/finally`之前执行`_start_comfy`、创建临时目录并`shutil.copy2`身份参考。隔离故障注入让copy2抛`OSError("copy failed")`后，函数直接退出；`_terminate_ollama_model`与`_free_comfy_memory`调用均为0，临时`short_drama_h3_context_ir`目录残留。H3调用为0，但不满足“所有异常删除临时输入/中转、卸载并释放”的硬门禁。
- 根因：统一清理边界起点晚于Comfy启动和临时输入准备，前置阶段异常不受finally保护。同类风险包括`_start_comfy`成功后copy失败、目录创建失败及部分复制后OSError，均可能遗留Comfy/Context模型状态或临时文件。
- 预期：从首次启动Comfy及准备临时输入开始即纳入异常安全作用域；无论prompt是否取得，均只取消自身已取得prompt，删除本任务临时输入/中转，尝试卸载Context模型、释放Comfy，并保持H3调用0。清理本身异常不得掩盖原始失败，但模型仍驻留必须维持硬阻断。
- 动态证据：`events=['start']`、`terminate=0`、`free=0`、H3调用0，临时目录仍存在。
- 下一状态：待处理。
- 稽查退回整改最终软件复测：通过。动态逐项改变subtitles、reference_urls、process_audits、content compliance及OCR/face/final evidence，指纹均独立变化；command键序反转指纹稳定，未启用OCR/face分别记录`no_subtitles/no_reference_urls`，专项`10/10`。启用步骤无真实evidence失败且ledger为空、成功pending→confirm completed→enhanced export及旧batch/篡改拒绝均通过。
- 资产关联旧断言判定：现行`queueGenerateAllAssetImages`确实委托统一`enqueueAssetOperation`；所有资产操作共享FIFO tail/key去重，project/session/epoch在执行前及等待中复核，stop/切项目递增epoch、清key/count/tail并回收生图single-flight。关联测试已改为双向队列行为契约，未放宽为按钮存在性；专项与关联`73 passed, 1 skipped`。
- 最终扩大回归：`178 passed, 1 skipped`；Python pycompile、Vue typecheck、Vite生产构建通过（83 modules，549ms）。未启动模型。
- 最终状态：软件测试通过，待稽查。
- 首败整改：将`_start_comfy`、临时目录创建和身份图copy2移入统一try/finally；finally在未取得prompt时不误取消，仍删除本任务临时文件及空目录、终止并核验专用模型、free Comfy。H3调用保持0。
- 原子落盘补强：三份输出改为唯一版本staging目录写齐后以一次`os.replace`发布，失败清理staging，不暴露半套文件。
- 第二轮软件测试：不通过；发现首个失败后立即停止，未启动或干预正式重模型。
- 失败项：成功链没有读取或验证已落盘的`optimized_prompt`，仍直接把Context history中的内存字符串返回给H3。隔离注入让`_persist_h3_context_ir_outputs`返回三条不存在的路径，任务仍记录completed，随后H3被调用1次并收到内存`in-memory optimized`；三条落盘文件实际均不存在。
- 根因：`_optimize_h3_ref2va_prompt`只信任持久化函数返回值并返回局部变量`result[0]`，没有在提交H3前验证三文件存在、属于当前发布批次并从`optimized_prompt`文件重新读取非空内容。磁盘丢失、异常存储适配器或发布后文件消失均可绕过“仅消费落盘optimized_prompt”门禁。
- 预期：Context完成与H3提交前验证三条路径均为当前job原子发布目录中的普通文件，读取三件套成功且非空；H3唯一prompt必须来自落盘`optimized_prompt`文件。任一缺失、不可读、空内容或批次不一致都应failed并保持H3调用0，同时执行清理与卸载。
- 动态证据：`H3_CALLS=1`、传参`in-memory optimized`、三条`FILES_EXIST=[False, False, False]`。
- 第二轮整改：持久化返回后严格解析三条真实普通文件，要求全部位于当前job同一原子发布目录、内容非空且两份JSON可解析；随后只用磁盘回读值更新job并传给H3。持久输出错误使用不可重试异常，禁止再次启动Context重推理。新增缺文件门禁和第二件写失败无半成品测试，专项23/23通过。
- 第三轮软件测试：不通过；按要求首先覆盖symlink边界即发现首败，已立即停止，未启动或干预正式重模型。
- 失败项：路径先执行`resolve(strict=True)`再检查`is_file()`，原始符号链接信息已丢失。隔离持久函数返回当前job同一发布目录内的`optimized_prompt.txt`符号链接，链接目标也是该目录普通文件；校验全部通过，H3被调用1次并收到链接目标内容`disk optimized`。
- 根因：门禁只检查解析后目标是普通文件和父目录一致，没有对持久化返回的原始Path执行`is_symlink()`/`lstat`，无法拒绝同目录或指向受信目录内的符号链接。
- 动态证据：`IS_SYMLINK=True`、`H3=1`、结果`disk optimized`；预期持久输出不可用且H3=0。
- 预期：三条原始路径在resolve/read前均须以lstat确认非symlink且为普通文件；失败属于不可重试持久化错误，Context提交仍仅1次。
- 第三轮整改：构造原始Path后、任何resolve/read之前拒绝三条路径中的任意symlink；再执行strict resolve、当前job同批目录和普通文件门禁。新增同目录symlink动态回归，专项24/24通过，H3零提交。
- 第四轮软件测试：不通过；symlink专项与安装关联`19/19`通过，继续覆盖中转输出清理时发现首败并立即停止；未启动或干预正式重模型。
- 失败项：Context graph始终包含三个`SaveText`节点，但当history已直接返回完整三项文本时，代码不执行fallback glob，`saved_files`保持空。隔离模拟Comfy按三个filename_prefix真实写出optimized/skills/raw中转文件且history同时返回完整文本，任务成功后三个文件全部留在`COMFY_OUTPUT/h3_context_ir/`。
- 根因：中转文件发现与清理绑定在“history输出缺失”的fallback分支，而SaveText节点无论history是否含文本都会执行；成功主路径因此无法登记本任务中转文件，finally无对象可删。失败/重试的同类中转文件也可能残留。
- 动态证据：Context返回`optimized`，创建3个本任务SaveText文件，finally后`REMAINING=3`，精确为同一job/prefix的optimized、skills、raw文件。
- 预期：每次prompt的三个唯一filename_prefix应在finally独立glob并只删除本任务匹配文件，不依赖是否走fallback；普通成功、失败、重试、取消和job写回异常均应无本任务中转残留，且不得删除其他任务文件。
- 第四轮整改：finally不再依赖fallback登记，始终按本任务唯一`prefix_root`扫描`COMFY_OUTPUT`并只删除匹配的普通文件；成功history完整路径同样清理optimized/skills/raw三项中转。结合确认式owned prompt核销，避免异步写入晚于清理。专项组合30/30通过。
- 第五轮软件测试：不通过；A/B专项`31/31`及成功中转清理/foreign相似前缀保护动态通过，继续持久路径symlink回归时发现首败并立即停止；未干预正式prompt或重模型。
- 失败项：仅检查三条最终文件自身`is_symlink()`，未检查其父级发布目录。隔离构造`job/batch`为指向同一job内`job/real`的目录symlink，三条文件本身均非symlink；resolve后父目录为合法`job/real`，全部门禁通过并调用H3一次。
- 根因：路径组件中的symlink在`resolve(strict=True)`后同样丢失，当前校验只覆盖末级文件，未对从job root到publication/file的每个原始路径组件执行lstat。目录链接还允许校验后替换目标，存在输入漂移风险。
- 动态证据：`PARENT_SYMLINK=True`、结果`disk`、`H3=1`；预期持久输出不可用、Context不重试且H3=0。
- 预期：三条路径必须位于真实非symlink的当前job根和真实非symlink的同一publication目录；从受信root之后的所有路径组件逐级lstat拒绝symlink，再进行普通文件和内容校验。
- 第五轮整改：先按未解析绝对路径验证固定`job_root/publication/file`层级，逐级拒绝job根、publication目录和三文件symlink，再执行strict resolve、同批普通文件及内容门禁。新增publication目录symlink动态回归，专项组合32/32通过。
- 完整软件复测：通过。成功history完整/缺失fallback、普通失败单次重试、history异常、超时/取消、前置与持久化/job update故障、模型卸载双门禁、三件套原子发布与磁盘唯一prompt、owned中转清理和foreign相似prefix保护均通过。
- 路径矩阵：缺失、跨job、跨批、末级/父目录symlink、目录、FIFO、空内容、坏JSON及发布后消失全部不可重试，Context仅1次且H3=0；补充动态`8/8`。
- 生命周期及回归：context_ir_prompt_id覆盖stop/result/watchdog/recover/shutdown；终态、票据、single-flight与重启关联通过。A/B专项`32/32`、关联`182 passed, 3 subtests passed`、pycompile、typecheck/build通过，正式prompt未干预。
- 正式加载补验：通过。PID 91425加载时间晚于最新compat_server，LaunchAgent绝对路径/cwd/PYTHONPATH正确；重启后旧cancelled orphan未进入Context恢复或新推理，任务仓库活动任务0、资源与Ollama/Comfy全空。
- 下一状态：待稽查。

### BUG-20260811-018：M9.174资产卡片保留已失效的并发阶段错误

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.174
- 现象：正式资源队列和阶段租约均为空，项目assets已为waiting_confirmation，但苏璃卡片仍显示`production stage is already running: assets`。
- 原因：资产提取成功合并时为保留既有媒体成果，同时无条件保留旧profile的status/error，历史阶段冲突因此覆盖新的成功提取状态。
- 整改：前端加载、前端增量合并和后端权威合并统一识别该精确错误；无图恢复pending、有图恢复waiting_confirmation并清空error，其他生成失败与图片/确认/detail/3D字段保持不变。
- 开发验证：关联后端回归82/82通过，Python编译、Vue类型检查及Vite构建通过；正式8787已空闲重载，当前项目stage revision 1381、assets=waiting_confirmation、苏璃=pending/error空、资源active/queued为0。
- 软件测试退回：前端`clearResolvedAssetStageConflict`使用`includes`、后端`_write_project_stage`使用`in`做子串匹配，并非只匹配精确历史错误。隔离动态用例输入真实扩展错误`真实生成失败：production stage is already running: assets；模型输出损坏`，后端错误地清空error并把failed改为pending，违反“其他真实生成失败必须保留”。发现首个失败后已立即停止，未执行其余回归与正式状态验收。
- 首轮整改：清理条件收紧为trim后的完整错误文本必须精确等于`production stage is already running: assets`；任何前后缀或复合错误均保留原status/error。
- 整改复测：通过。隔离动态33项断言覆盖人物/场景/道具，精确历史错误无图恢复pending、有图恢复waiting_confirmation且error清空，任意前缀/后缀复合真实错误保持failed/error，image、detail_assets、confirmation_phase、baseline_confirmed_at、model3d_status/result/job_id均保持。前端load/merge专项`15/15`，关联回归`82 passed`，Python编译、Vue类型检查、Vite构建通过。正式8787健康，三资源池active/queued均0；唯一项目assets revision 1381/status waiting_confirmation，苏璃status pending/error空。
- 下一状态：待稽查。
- 重新最终稽查：通过。前端load/merge及后端写回均以waiting_confirmation/confirmed/completed三状态和精确整串错误为双门禁；其他状态、复合错误、preview/seed/import均不清理。三类资产媒体、确认、detail及3D字段保持，软件96/96与关联134证据有效。
- 最终状态：已关闭。
- 最终稽查退回：前端load只按卡片错误文本清理，未验证权威assets状态；后端merge同样未限定incoming status，失败写回也携带merge_existing。因此本次权威assets failed时仍可能清除旧错误并改成pending/waiting，掩盖真实失败。
- 稽查整改：前端清理函数新增authoritativeSuccess参数，load从权威stage status判定，preview/seed/import等非权威合并默认禁止清理，正式assets成功及已验证成功恢复路径才显式允许。后端仅当incoming status精确属于waiting_confirmation/confirmed/completed时清理精确错误；pending_confirmation/failed/generating/cancelled不处理。
- 开发验证：前端typecheck、Vite build、后端py_compile及production gate专项`15 passed`；待独立完成三类资产×成功/失败状态矩阵与字段保持测试。
- 最终整改软件测试：不通过；发现首个失败后立即停止，未运行关联回归、typecheck/build，未干预H3。
- 失败项：后端`_write_project_stage`把`pending_confirmation`也列为`authoritative_asset_success`，但本轮权威成功清理白名单仅为`waiting_confirmation/confirmed/completed`。动态输入人物旧卡`status=failed`、精确历史错误和incoming `status=pending_confirmation`，实际被改为`waiting_confirmation/error=""`；预期status/error保持不变。
- 同类风险：人物/场景/道具共用同一分支，因此三类均受影响；前端白名单已精确为三种状态，当前前后端契约不一致。其余已执行的三类资产×7个明确状态×精确/复合错误×有图/无图动态矩阵`84/84`通过，媒体、确认和3D字段序列化值保持不变。
- 首败整改：后端权威成功白名单删除`pending_confirmation`，仅保留`waiting_confirmation/confirmed/completed`，与前端一致。
- 完整软件复测：通过。人物/场景/道具×8种状态×精确/复合错误×有图/无图动态矩阵`96/96`；只有三种权威成功状态与精确错误同时满足时清理，`pending_confirmation/failed/generating/cancelled/pending`均保持原status/error。image、detail_assets、confirmation_phase、baseline_confirmed_at及model3d_status/result/job_id序列化值完全不变。
- 调用边界：前端load按权威stage状态判定；正式commitStage与验证后的成功恢复允许清理；preview、seed和import默认不清理。关联回归`134 passed`、后端Python编译、Vue typecheck及Vite正式构建通过；未干预H3。
- 下一状态：待稽查。

### BUG-20260811-017：M9.173扩展提供方缺少运行接口仍可被激活

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.173
- 问题：扩展注册表此前只检查factory可调用和实例非空；替换为PostgreSQL/Redis/远程provider时，即使缺少新增接口也会成功激活，直到生产任务中途才AttributeError。
- 整改：ProductionExtensionRegistry.create读取活动provider metadata中的required_methods并验证实例对应成员可调用；缺失项以extension point/provider/methods明确报错。
- 内置契约：8类基础设施全部声明contract_version=1与方法清单；task lease包含acquire/renew/release/owns/request_cancel/cancellation_requested/commit_guard/reap_expired。
- 开发验证：缺少acquire/commit_guard的provider创建时拒绝，完整provider正常创建；关联专项`66 passed`及Python编译通过。
- 下一状态：待软件测试。
- 稽查整改软件首败：状态矩阵发现后端额外接受`pending_confirmation`，会把旧failed卡片清成waiting_confirmation；该值不属于最新允许的三种权威成功状态。其余7状态×三类×精确/复合×有图/无图84组及媒体/确认/3D字段保持已通过。
- 首败整改：删除pending_confirmation别名，前后端统一只接受waiting_confirmation/confirmed/completed。
- 下一状态：待软件测试复测。
- 稽查整改独立复测：通过。p1导入在`resource.save`或`semanticAudit`阻塞后切p2，旧响应零merge、零persist、零通知；3D生成/确认、修复与超分晚到同样零污染。执行严格`old-start→old-end→new-start→new-end`、`maxConcurrent=1`，旧排队任务按epoch跳过，owner token精确释放。后端延迟确认、后续completed与HTTP409均通过；关联`164 passed, 1 skipped`，编译、类型检查及83模块构建通过。
- 最终稽查：通过。确认全部资产生产入口统一FIFO，stop保持即时；已启动异步操作的project/session响应围栏、定向持久化与旧finally隔离完整，无剩余阻断。
- 关闭时间：2026-08-11。
- 首轮软件测试：不通过；发现首个失败后立即停止，未启动重模型。
- 失败项：契约仅在`create()`实例化后验证，`register(... activate=True)`和`activate()`在切换活动绑定前不验factory返回值及required_methods。缺方法、非callable或factory None的provider因此可先成为active，随后create虽明确失败，但原活动provider已失去active绑定，违反“拒绝且不影响活动绑定”。
- 动态复现：先激活完整`stable` task-lease provider，再安装缺`acquire/commit_guard`的`broken`并显式activate。`create()`正确报`contract mismatch; missing methods: acquire,commit_guard`，但`get('storage.task_lease').provider_id`仍为`broken`，原`stable`未自动恢复。`replace=True`也可在契约失败前删除整个旧point，风险更高。
- 整改要求：任何会改变active的register/replace/activate操作必须先在临时候选上完成factory None、非callable及required_methods实例契约验证，或在失败时原子回滚extensions与active全状态；失败候选不得占用活动绑定或删除旧provider。需同时覆盖replace_provider、显式activate和并发create/切换无空窗。
- 整改：required_methods非空时强制提供implementation_type，并在注册表任何写入前验证类方法可调用；失败发生于replace/activate之前。成功定义记录contract_validated与实现类型名称，create继续验证真实实例。
- 开发验证：broken普通注册与replace=true均在写入前拒绝，stable active和create保持；完整provider正常创建。专项`67 passed`及Python编译通过。
- 第二轮软件测试：不通过；发现首个失败后立即停止，未启动重模型。
- 失败项：`implementation_type`只能证明类属性存在，不能保证factory真实返回该类实例。factory返回`None`，或返回以实例属性覆盖类方法为非callable的对象，仍可通过register并被activate；直到create二次验证才失败，但active已切换且不回滚。
- 动态复现：完整`stable` task-lease provider为active；新`none` provider声明同一完整`Lease`为implementation_type，但factory返回`None`。register和activate均成功，create报`extension returned no instance`，但active provider仍为`none`，原stable未恢复。这仍违反本轮明确的“factory None拒绝且不影响活动绑定”。
- 整改要求：活动切换必须以真实factory实例验证为前置条件，或在create失败时CAS回滚到原active；不能仅信任申报的implementation_type。需动态覆盖factory None、实例非callable覆盖、replace/replace_provider/activate及并发create与切换，所有失败后provider集合与active必须与之前完全一致。
- 实例探测整改：非builtin provider在任何注册表写入前实际执行contract probe（可由probe_configuration提供配置），验证返回非None且真实实例required_methods均可调用；声明类型撒谎、factory None/异常、实例缺方法均原子拒绝。builtin可信类型保持类级前验并在create二次验证。
- 开发验证：None与lying factory在replace+activate前拒绝，stable active保持；专项`67 passed`及Python编译通过。
- 下一状态：待软件测试复测。
- 最终稽查：通过。前后端仅按完整错误文本精确归一化，三类资产load/merge一致；无图pending、有图waiting_confirmation，复合真实错误及媒体、确认、detail、3D字段保持。正式项目与资源空闲状态复核通过。
- 下一状态：已关闭。
- 实例探测软件复测：隔离功能通过。factory None、implementation_type撒谎、实例属性覆盖为非callable、factory异常、replace与replace_provider均在任何注册写入前拒绝，provider集合和stable active完全不变；probe_configuration正常实例化且不暴露到运行metadata，动态`6/6`。
- 契约与并发：8个内置扩展点均具有`contract_version=1`、非空required_methods、contract_validated和implementation_type，隔离真实实例全部方法可调用，动态`8/8`；8读1切换共`2400/2400`次create/activate并发无异常、无空绑定。task lease cancel/commit_guard新语义由专项保持通过。
- 关联回归：`146 passed, 3 subtests passed`；ProductionExtensionRegistry与compat_server Python编译通过，未启动重模型。
- 正式加载阻断：8787当前PID 54550启动于08:38:11，早于compat_server 08:51:00和ProductionExtensionRegistry 08:53:16最新文件；正式`/api/production/workers` `extensions=[]`，尚未加载M9.173 metadata披露和实例探测。当前资源active/queued0、Ollama0、Comfy0/0，未自行重启。
- 下一状态：待正式服务安全加载最新代码后补验。
- 正式补验：通过。8787在空闲时由主线安全kickstart为PID 56761，启动时间08:55:52晚于compat_server 08:51:00和ProductionExtensionRegistry 08:53:16，确认加载最新代码。LaunchAgent绝对Python/脚本/PYTHONPATH/WorkingDirectory与cwd均正确，health healthy。
- 正式管理契约：`/api/production/capabilities`披露8个扩展点，全部唯一active且metadata完整包含`contract_version=1`、非空`required_methods`、`implementation_type`与`contract_validated=true`；task lease清单精确包含acquire/renew/release/owns/request_cancel/cancellation_requested/commit_guard/reap_expired。隔离真实create `8/8`与metadata匹配。
- 最终空闲：旧worker超时清退后仅PID 56761 healthy/active0/queue0，三池active/queued0，Ollama模型0，ComfyUI队列0/0。最终证据为失败原子性`6/6`、内置契约`8/8`、并发`2400/2400`、关联`146 passed, 3 subtests passed`及Python编译通过；未启动重模型。
- 下一状态：待稽查。
- 最终稽查退回：`activate()`没有重新探测真实factory，可变factory在注册后变为None/异常/坏实例时仍会切走稳定active；实例探测只检查同名方法，未验证真实对象属于声明的implementation_type；`required_methods`为字符串等非法结构时会跳过契约门禁。
- 最终整改：新增注册表内部`_ProviderContract`，统一保存声明类型、规范化方法清单、私有probe配置和builtin可信边界。注册/replace/replace_provider在任何写入前执行统一探测；显式activate先在锁外重新探测，回锁后校验factory与contract未被并发替换再原子切换；create继续对实际生产实例二次验证。真实实例必须`isinstance(implementation_type)`且全部方法可调用，非法required_methods立即拒绝；probe_configuration不进入公开metadata。
- 整改验证：激活时factory变为None或抛异常均拒绝且stable active保持；错误类型即使实现全部同名方法仍拒绝；字符串required_methods拒绝。专项`69 passed`，ProductionExtensionRegistry与compat_server Python编译通过。
- 下一状态：待独立软件测试。
- 最终整改隔离复测：通过。provider注册时factory正常，之后变为None/抛异常/错误implementation_type/实例非callable覆盖时，activate均在切换前拒绝，stable active/provider集合/create完全不变；required_methods为字符串或映射均在写入前拒绝，probe_configuration不出现于公开metadata，动态`7/7`。
- 并发与契约：activate与register/replace_provider/enable/unregister/create并发压力下读取500次无异常或错误active；全部线程按时结束。8 builtin真实create与契约`8/8`及既有失败矩阵/并发`6/6`、`2400/2400`证据保持有效。
- 回归：专项`69 passed`，关联`149 passed, 3 subtests passed`，ProductionExtensionRegistry与compat_server Python编译通过，未启动重模型。
- 正式加载阻断：8787当前PID 57053启动于08:58:09，早于compat_server 08:59:55和ProductionExtensionRegistry 09:03:30最新文件，尚未加载最终activate重探测。当前worker/三池active/queued0、Ollama0、Comfy0/0，未自行重启。
- 下一状态：待正式服务安全加载最新代码后补验。
- 最终正式补验：通过。8787已在资源/模型空闲时由主线安全kickstart为PID 63381，启动时间09:07:26晚于compat_server 08:59:55和ProductionExtensionRegistry 09:03:30，确认加载最新activate重探测。LaunchAgent绝对Python/脚本/PYTHONPATH/WorkingDirectory与cwd均正确，health healthy。
- 正式契约：`/api/production/capabilities`披露8个唯一active扩展，`contract_validated=8/8`；每项metadata均含contract_version=1、非空required_methods、implementation_type，且全部不含probe_configuration。task lease精确含request_cancel/cancellation_requested/commit_guard等全8方法；隔离8 builtin真实create `8/8`证据保持有效。
- 最终空闲：旧PID worker超时清退后仅PID 63381 healthy/active0/queue0，三池active/queued0，Ollama模型0，ComfyUI队列0/0。最终证据：时间差与非法schema `7/7`、并发读取500次无错误active、专项`69 passed`、关联`149 passed, 3 subtests passed`及Python编译通过；未启动重模型。
- 下一状态：待重新稽查。
- 第二次最终稽查退回：候选provider仍可省略required_methods/implementation_type，使contract=None后直接激活；第三方还可在公开metadata伪造builtin=true取得探测豁免，实例级门禁未覆盖这两条降级路径。
- 第二次整改：注册表维护extension-point级required_methods规范；一旦该点建立契约，后续provider省略或缩减方法清单均在写入前拒绝，并在mutation lock内二次检查并发首注册。builtin可信资格不再读取metadata，而由composition root构造注册表时传入固定(point,provider)白名单；非白名单即使声明builtin=true仍执行真实factory probe。
- 整改验证：稳定task lease存在时，空metadata+None factory完整replace被拒绝；伪造builtin=true+None factory仍拒绝；provider集合、active与create保持。专项`70 passed`、Python编译与diff检查通过。
- 第二次整改软件复测：通过。已有point契约时，空metadata、省略required_methods、缩减required_methods在普通注册、完整replace和replace_provider三种路径共`12/12`均原子拒绝，旧provider集合、active与create保持；公开metadata伪造builtin但不在构造白名单的None factory仍被真实probe拒绝。
- 契约建立与自动接管：已有无契约provider时，非完整替换建立point契约被拒绝，完整replace可建立并清退旧provider；point有规范时无contract provider不能激活。卸载active前会重新探测fallback，动态变为None的候选不得接管且原集合/active不变；符合相同required_methods的第三方不同implementation_type可正常注册、激活与创建。
- 并发边界：契约provider与无契约provider同时首注册动态`100/100`，mutation lock二次校验保证最终仅完整契约provider存在且可创建；无中间错误active。
- 回归与编译：专项`70 passed`；关联`150 passed, 3 subtests passed`；ProductionExtensionRegistry与compat_server Python编译通过。未启动重模型。
- 正式验收：通过。8787 PID 64512启动于09:14:28，晚于ProductionExtensionRegistry 09:13:28和compat_server 09:14:17，cwd为项目根目录且健康。管理接口披露8个唯一active扩展，`contract_validated=8/8`，每项contract_version、required_methods、implementation_type完整且公开metadata无probe_configuration；唯一worker healthy/active0/capacity11，Ollama模型0，ComfyUI队列0/0。
- 下一状态：待重新稽查。
- 最终空闲关闭补验：代码稽查既有通过结论有效；新PID 91425已加载最新registry/compat，正式8个扩展点全部唯一active/enabled且`contract_validated=8/8`，metadata完整、probe_configuration披露0。唯一worker healthy/active0，任务0、三池active/queued0、Ollama0、Comfy0/0；同一orphan阻塞已自然消失。
- 最终状态：已关闭。

### BUG-20260811-016：M9.172生产阶段单飞与取消仅限当前服务进程

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.172
- 问题：`ACTIVE_PRODUCTION_STAGE_REQUESTS/CANCEL_EVENTS`仅在单进程内生效；多个API实例可同时执行同一tenant/user/project/stage，取消请求也无法通知实际owner。
- 整改：run-stage增加稳定stage key的SQLite任务租约；租约generation由独立持久序列表单调递增。`cancel_requested`写入当前活租约，owner每秒续租并在取消或失租时设置本地事件。
- 提交围栏：阶段执行结果返回后、项目阶段写回后、LangGraph pending_confirmation提交前复核owner+generation；取消/失租统一投影cancelled，禁止正常完成。
- 开发验证：两个独立compat实例共享租约库，同阶段第二实例拒绝且可跨实例取消owner；取消后renew/owns均失败，新owner取得更高generation且不继承旧取消。专项`61 passed`及Python编译通过。
- 首轮软件测试退回：assets结果通过首次ownership检查后，另一实例取消；旧owner仍先写waiting_confirmation，catch再写failed，虽Graph为cancelled但形成项目双事实。
- 竞态整改：新增`TaskLeaseRepository.commit_guard`，在SQLite写事务内复核owner/generation/expiry/cancel，持有事务完成项目写回和LangGraph提交，成功后消费租约。取消先取得事务则guard拒绝且零业务写回；提交先取得事务则取消等待并在租约已消费后返回未取消。
- 终态整改：取消/失租异常不再把assets项目写failed，只报告LangGraph cancelled；正常失败仍保持failed处置。
- 开发验证：跨Repository取消与commit并发线性化、取消先到拒绝进入guard、generation持续递增；专项`62 passed`及Python编译通过。
- 最终稽查退回：旧gen1失租后catch仍无代际围栏报告cancelled，可覆盖已接管的gen2 running；同时assets项目写回内已报告pending，handler又重复报告一次。
- 代际整改：LangGraph状态新增每阶段`stage_generations`，所有带代事件拒绝低于当前代；run-stage的running/pending/cancelled均携带租约generation。纯失租旧owner不再报告任何Graph终态，仅持久`cancel_requested`证明的显式取消可报告cancelled。
- 唯一提交整改：assets使用`_write_project_stage`返回的workflow，不再由handler重复报告pending_confirmation。
- 开发验证：gen1 running→gen2 running后，gen1 cancelled/failed均被拒绝；gen2 pending保持且generation=2。专项`63 passed`及三文件Python编译通过。
- 代际围栏软件复测退回：当前gen1被另一实例显式取消后，结果线程可在续租线程轮询前进入`_ensure`；业务写回虽为0，但旁路`cancel_requested`尚未设置，catch误判纯失租而让Graph停留running/gen1。
- 同步取消整改：`_ensure_production_stage_request_active`在任何owns失败时立即按lease_key/owner/generation查询持久cancel_requested并写入事件，再抛出终止；显式取消即时报告cancelled，纯失租仍保持零Graph终态。
- 开发验证：不启动续租线程，持久request_cancel后立即执行active check，可同步识别cancel_requested=true。专项`64 passed`及Python编译通过。
- 重新稽查退回：同实例commit-first时，本地ACTIVE event先被无条件set并计数，随后SQLite request_cancel虽返回false，停止接口仍误报stopped=1，与实际waiting_confirmation矛盾。
- 取消裁决整改：`_cancel_production_stage`先执行SQLite request_cancel，并以其布尔结果作为唯一返回事实；仅成功后才在本实例查找并设置匹配Event。commit-first返回0且不形成取消终态，cancel-first仍返回1并唤醒owner。
- 开发验证：同一compat实例commit_guard阻塞、并发stop、释放提交后，stop精确返回0且ACTIVE事件清理；专项`65 passed`及Python编译通过。
- 软件测试退回：同实例cancel-first/commit-first动态均通过，但关联旧静态测试仍要求遍历ACTIVE映射的历史实现文本，未接受精确`map.get(target_key)`与SQLite唯一裁决；`1 failed, 143 passed, 3 subtests passed`。
- 测试契约整改：静态断言更新为精确scope map lookup及`TASK_LEASES.request_cancel`唯一裁决；相关组合回归`120 passed`。
- 下一状态：待软件测试复测。
- 首轮软件测试：不通过；发现首个失败后立即停止，未启动重模型。`test_production_control.py`现有专项`61 passed`及TaskLeaseRepository/compat_server Python编译通过，但未覆盖结果返回与项目写回之间的取消竞态。
- 失败项：assets owner在生产结果返回并通过第一次`_ensure_production_stage_request_active`后，另一实例恰好持久写入`cancel_requested`；旧owner仍执行`_write_project_stage(... status=waiting_confirmation)`，随后第二次围栏才发现失租，catch分支又写入`status=failed`。LangGraph虽投影`cancelled`，项目阶段却留下两次旧owner写回且终态为failed，违反“取消后阻断项目写回、终态cancelled”。
- 动态证据：隔离HTTP服务与第二TaskLeaseRepository共享SQLite，在首次所有权检查后立即`request_cancel`；公开run-stage返回HTTP 502/cancelled-or-lease-lost，Graph report为`assets/cancelled`，但捕获到项目写回`2`次，状态依次为`waiting_confirmation`、`failed`。
- 整改要求：项目阶段写回必须纳入owner+generation原子提交围栏，不能仅在写前/写后分离检查；取消/失租异常分支不得把项目状态写成failed，应与LangGraph统一为cancelled，且旧owner的业务结果不得落盘。
- 下一状态：待处理。
- 首败整改软件复测：隔离功能通过。取消先到的原HTTP闸门返回502/cancelled，项目写回0且Graph仅cancelled；提交先到时cancel在SQLite事务后返回false，项目唯一写回waiting_confirmation且Graph唯pending_confirmation。
- 边界证据：不同项目/阶段并行、release/reap/Repository重建后generation严格递增、旧owner拒绝、缺scope拒绝、SQLite acquire异常无本地ACTIVE泄漏，动态`11/11`通过。关联回归`141 passed, 3 subtests passed`，专项`62 passed`，TaskLeaseRepository与compat_server Python编译通过。
- 正式验收阻断：8787 PID 44757启动于07:51:19，本轮TaskLeaseRepository和compat_server整改文件修改时间为08:08:36，正式进程尚未加载M9.172最新提交围栏。当前8787 cwd正确/health healthy、worker active0、三池active/queued0、Ollama0、Comfy0/0；未自行重启或启动模型。
- 下一状态：待正式服务安全加载最新代码后补验。
- 正式补验：通过。8787已在空闲时由主线安全kickstart为PID 48450，启动时间08:12:10晚于TaskLeaseRepository/compat_server整改时间08:08:36，确认加载最新代码。LaunchAgent `com.local.ai.compat-server`的Python、服务脚本、PYTHONPATH、WorkingDirectory均为`/Users/aoo/Code/AI Agent`绝对路径，cwd正确，health healthy。
- 正式租约与空闲证据：`task_leases`包含`owner_id/generation/lease_expires_at/heartbeat_at/cancel_requested`，`task_lease_generations`独立保留单调generation，当前活动租约0。旧PID worker在30秒健康超时后自动清理，最终仅PID 48450 worker healthy/active0/queue0；三池active/queued0，Ollama模型0，ComfyUI队列0/0。
- 最终结论：通过。取消/提交两种线性化顺序、边界`11/11`、专项`62 passed`、关联`141 passed, 3 subtests passed`及Python编译证据保持有效；未启动重模型。
- 下一状态：待稽查。
- 代际围栏软件复测：不通过；发现首个失败后立即停止，未启动重模型。跨两个ProductionOrchestrator动态复现gen1 TTL失租→gen2 running/commit→gen1晚到已通过，Graph保持outline pending_confirmation/generation2，旧owner未覆盖新结果。
- 失败项：当前代显式取消在owner续租线程下一次1秒检测前发生时，`_ensure_production_stage_request_active`只因`owns=False`设置cancel_event，不同步读取持久`cancel_requested`。catch中`explicit_cancel=False`，将当前代显式取消误当纯失租并跳过Graph cancelled。
- 动态证据：两独立compat实例共享租约SQLite，assets owner阻塞后由另一实例显式取消返回1并立即释放owner；HTTP返回502 cancelled-or-lease-lost，业务项目写回0，但Graph仍为`assets=running/stage_generation=1`，未转cancelled。当前专项`63 passed`但未覆盖小于1秒的取消竞态。
- 整改要求：所有owns/commit guard失败路径在区分显式取消和纯失租时，必须直接按owner+generation查询持久cancel_requested，不得依赖1秒续租线程的旁路标志。当前代显式取消必须稳定投影cancelled，纯失租旧owner仍不得投影终态。
- 下一状态：待处理。
- 显式取消竞态整改软件复测：隔离功能通过。当前代assets在续租线程检测前由第二实例显式取消，HTTP返回502，项目写回0，Graph稳定为`assets=cancelled/generation1`。gen1 TTL失租→gen2 running/commit→gen1晚到跨两orchestrator反序亦通过，最终保持outline pending_confirmation/generation2。
- 回归证据：专项`64 passed`，关联`143 passed, 3 subtests passed`，TaskLeaseRepository、ProductionOrchestrator和compat_server Python编译通过；未启动重模型。
- 正式加载阻断：当前8787 PID 48450启动于08:12:10，早于ProductionOrchestrator 08:17:47和compat_server 08:23:28最新整改文件，正式服务尚未加载当前代显式取消修复。
- 下一状态：待正式服务安全加载最新代码后补验。
- 最终正式补验：通过。8787已由主线在空闲时安全kickstart为PID 51682，启动时间08:26:37晚于ProductionOrchestrator 08:17:47和compat_server 08:23:28，确认加载最新generation/cancel围栏。LaunchAgent绝对Python/脚本/PYTHONPATH/WorkingDirectory与cwd均指向`/Users/aoo/Code/AI Agent`，health healthy。
- 正式Graph契约：公开`/api/production/workflow`响应已披露`stage_generations`持久字段；正式orchestrator SQLite保持2630个checkpoint，响应从持久状态读取。最终仅PID 51682 worker healthy/active0/queue0，三池active/queued0。验收期间合法H3 Context IR任务自然结束，qwen3-vl-h3-context-ir按expires_at自然卸载；未停止、清队列或重启。最终Ollama模型0、ComfyUI队列0/0。
- 最终证据：当前代即时显式取消为Graph cancelled且业务写回0；gen1纯失租→gen2提交→gen1晚到保持pending_confirmation/generation2。专项`64 passed`，关联`143 passed, 3 subtests passed`，三文件Python编译通过。
- 下一状态：待重新稽查。
- 同实例commit-first/cancel-first动态复测：功能通过。cancel-first返回1、HTTP 502、项目写回0、Graph cancelled；commit-first期间cancel被SQLite事务线性阻塞，提交后返回0且不触发本地event，HTTP 200、项目唯一waiting_confirmation、Graph pending_confirmation。专项`65 passed`及三文件Python编译通过。
- 关联回归退回：`test_production_gate_reconciliation.py::test_storyboard_stop_requires_complete_exact_project_identity`仍强制断言已删除的旧遍历实现文本`if key != target_key: continue`，而新实现改为精确`ACTIVE_PRODUCTION_STAGE_CANCEL_EVENTS.get(target_key)`查找。实际项目身份边界动态仍通过，但关联契约未同步，全量结果为`1 failed, 143 passed, 3 subtests passed`，不得流转。
- 正式加载：当前PID 51682启动于08:26:37，早于compat_server本轮08:34:16修改，亦尚未加载同实例取消语义整改。按首败停止，未启动重模型。
- 下一状态：待同步关联测试契约并安全加载正式服务后复测。
- 同实例语义与旧契约最终复测：通过。精确取消契约与production_control组合`66 passed`；同实例cancel-first返回1并唤醒event，业务写回0/Graph cancelled；commit-first时cancel等待SQLite事务后返回0且不触发event，项目唯一waiting_confirmation/Graph pending_confirmation。跨实例、generation反序及旧owner围栏证据保持通过。
- 最终回归：`144 passed, 3 subtests passed`；TaskLeaseRepository、ProductionOrchestrator和compat_server Python编译通过。正式8787 PID 54550启动于08:38:11，晚于compat_server 08:34:16整改，确认加载最新代码；LaunchAgent绝对路径、PYTHONPATH、cwd正确，health healthy。仅新worker healthy/active0/queue0，三池active/queued0，Ollama模型0，ComfyUI队列0/0；未启动重模型。
- 下一状态：待重新稽查。
- 最终稽查：通过。SQLite唯一取消裁决、commit guard线性化、stage generation低代拒绝、纯失租零终态、显式取消同步与assets单次pending均无阻断。
- 最终空闲补验：合法H3模型自然卸载，全程未stop/restart/清队列；8787 PID54550、worker、三池、tasks、Ollama与ComfyUI全部空闲。
- 最终状态：已关闭。

### BUG-20260811-015：M9.171 MiniMax H3 Context IR提示词优化节点安装

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.171
- 安装：节点提交771cb3cb…、MIT许可、openai-agents/openai依赖、本地qwen3-vl-h3-context-ir 16K模型、ComfyUI白名单与持久LaunchAgent。
- 开发验证：object_info发现FL2VA/Ref2VA两节点；真实prompt 7d423397… success并输出非空结构化H3提示词；原262K配置90.4GB已终止，专用16K实测24.5GB；结束后Comfy队列0/0、Ollama models为空。
- 能力边界：仅安装、发现、手动接线和真实调用完成；自动插入短剧H3生产图、独立阶段与卸载审计仍为pending_development。
- 软件测试：通过。节点仓库固定提交`771cb3cb01af9543b4f424518bb19b7fa0cf31d8`、MIT许可；Comfy venv依赖`openai-agents 0.19.4/openai 2.53.0/Pillow 12.3.0/numpy 2.4.6`完整；`config.toml`被git忽略、使用本地Ollama端点与非敏感占位Key；专用模型为32B来源、16K上下文/2048输出，262K配置明确禁止。LaunchAgent运行中且白名单包含节点；8194发现FL2VA/Ref2VA两节点；真实history `7d423397-b780-4ed6-b776-2fd1278f433d`为success，非空输出含三项H3结构字段；队列`0/0`、Ollama加载模型`0`。五份规范均保留`pending_development`自动接线边界。专项及关联回归`102 passed, 3 subtests passed`，Python编译通过；未启动H3视频重模型。
- 最终稽查退回：上游Python依赖使用浮动下限且无项目锁/哈希/SBOM/安全扫描；专用Modelfile使用浮动`qwen3-vl:32b`，无法保证重装使用相同权重。
- 供应链整改：新增42项全量精确版本+下载哈希锁、固定Git提交/许可/requirements/model blob校验及可复现安装脚本；Modelfile固定引用已实测SHA-256为`6e416d…a99b`的20,910,274,496字节源blob；新增CycloneDX SBOM、pip-audit漏洞0项报告与Bandit静态扫描（高0/中0/低1，B110为上游清理OSError接受项）及统一供应链JSON台账。
- 供应链软件测试退回：`docs/security/h3-context-ir-bandit.json`唯一低危B110实际为上游`nodes.py:252`对`set_tracing_disabled(True)`的`except Exception: pass`，但`deploy/comfyui/h3-context-ir-supply-chain.json`将处置对象记为“best-effort image cleanup catches OSError”，证据位置、异常类型和用途均不一致，安全处置台账失真。退回前已通过：固定commit且工作树clean、`install_h3_context_ir_agent.sh --verify`、42项精确锁及全项下载哈希、SBOM与锁42项完全一致、pip-audit 0漏洞、Bandit高0/中0/低1。
- 安全台账整改：台账与节点规范已准确记录B110位于`nodes.py:252`，实际为`set_tracing_disabled(True)`的宽异常吞吐；风险定性为追踪禁用API异常时静默失败。固定本地回环Ollama、占位Key、禁用追踪配置保持，安装/校验脚本新增固定Agents API真实disabled状态断言；测试新增位置、调用和旧错误描述不存在的机器门禁。
- 第二轮供应链软件测试退回：台账与规范声称LaunchAgent设置`OPENAI_AGENTS_DISABLE_TRACING=1`，但当时变量只存在于节点忽略配置，plist及正式进程环境均缺失；其余B110处置、verify、6项专项、42项哈希与dry-run均通过。
- 第二轮整改：启动脚本显式export且LaunchAgent EnvironmentVariables固定`OPENAI_AGENTS_DISABLE_TRACING=1`；队列空闲时已重载正式8194，PID 49426的真实进程环境与launchctl均返回该变量为1，节点在线、队列0/0，verify再次通过。
- 第二轮供应链软件测试退回：B110位置、调用与旧错误描述已整改，`--verify`及专项`6/6`通过；但manifest与H3规范均声称“配置和LaunchAgent设置/声明`OPENAI_AGENTS_DISABLE_TRACING=1`”，实际`com.aiagent.comfyui8194.plist`及当前launchctl运行环境均无该变量，只有节点忽略配置`config.toml`包含该键，风险缓解证据仍不准确。42项require-hashes dry-run解析通过且未移除锁外依赖。
- 第三轮供应链软件测试退回：LaunchAgent与正式PID 49426环境均已真实携带`OPENAI_AGENTS_DISABLE_TRACING=1`，`--verify`、专项`6/6`、固定commit/clean工作树、许可/requirements/lock/model blob大小与SHA、42项锁=42项SBOM、pip-audit 0、Bandit高0/中0/低1及B110精确位置均通过；但服务重载后8194 `/history/7d423397-b780-4ed6-b776-2fd1278f433d`不存在，完整`/history`为0条，无法验证要求的真实success与非空H3结构输出。当前队列0/0、Ollama加载0。
- 第三轮整改中发现真实输出边界：重跑prompt `011bf0ba…`（chat_completions）、`6d8b380d…`（responses）以及4096输出的`eaa6140e…`均被Comfy标success，但全部预算消耗于Qwen thinking，`optimized_prompt/raw_json`为空，均不作为通过证据。根因是Ollama `qwen3-vl-thinking` renderer/parser忽略禁用思考参数；专用Modelfile现固定官方问题建议的`qwen3-vl-instruct` renderer/parser并保留16K/2048，须重跑取得非空输出后才可复测。
- Thinking权重替换：已下载官方`qwen3-vl:32b-instruct`非思考权重，源blob为20,910,274,592字节、`sha256-4c7fee11…607ea`；专用Modelfile、安装脚本、供应链台账和测试全部切换并固定该实物及instruct renderer/parser。必须以此权重重新取得非空Comfy history后放行。
- 本地兼容与真实验收：固定上游节点无条件发送reasoning参数，Instruct模型会拒绝；新增哈希固定兼容补丁仅对专用模型省略reasoning，安装脚本拒绝任何其他工作树漂移。正式prompt `46356c27-a347-4e5d-88f0-452109b650e5`在23.404秒成功，optimized_prompt/selected_skills/raw_json三项均非空，包含`integrated_multimodal_description/overall_soundscape/non_diegetic_music`；完整证据已固化到项目，不再依赖重启后history。
- 第四轮供应链软件测试：通过。`qwen3-vl:32b-instruct`源blob大小`20,910,274,592`及SHA-256 `4c7fee11…607ea`一致，Modelfile固定blob/16K/2048/instruct renderer/parser；上游commit固定，工作树仅含哈希完全一致的唯一compatibility patch，verify对缺patch及额外漂移均拒绝。42项require-hashes锁与42项SBOM完全一致，pip-audit漏洞0，Bandit高0/中0/低1且B110处置准确；LaunchAgent正式PID 55158环境变量为1。真实prompt `46356c27-a347-4e5d-88f0-452109b650e5` history success，三输出非空，三个落盘产物大小/哈希均匹配runtime-smoke；两节点可发现，队列0/0、Ollama加载0。五份规范均保持`pending_development`及资源边界。专项与关联回归`112 passed, 3 subtests passed`，verify、JSON、bash、Python编译及reverse patch检查通过；未启动H3视频重模型。
- 最终稽查：通过。固定提交与唯一补丁、42项依赖及哈希、SBOM与安全扫描、32B Instruct源模型摘要、LaunchAgent追踪禁用、两个节点发现、真实三项输出及落盘哈希、资源卸载、五份规范与`pending_development`边界均复核通过。
- 下一状态：已关闭

### BUG-20260811-014：M9.170服装独立道具资产与镜头级换装链

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.170
- 开发范围：服装归入道具栏`costume`子类；分镜逐镜绑定`costume_id/costume_version`；45°单图进入TripoSR/Blender穿衣链；确认版归档`3d/costumes/`；三份权威规范同步。
- 首轮软件测试退回：模型遗漏category/asset_type或owner时可形成普通prop/无主服装。
- 第一次整改：名称/分类/描述确定性识别服装；唯一出镜角色可补owner，多角色歧义或owner越界拒绝。
- 第二轮软件测试退回：确定性词表遗漏“战斗服”。
- 第二次整改：补齐日常服、战斗服、练功服、常服、华服等规范词，并保持owner门禁。
- 最终软件测试：通过。六类服装缺字段归一`6/6`；owner歧义和越界均拒绝；双人物15镜服装绑定`30/30`，缺version拒绝；服装确认归档与metadata四字段通过；运行时stage注入`4/4`；关联回归`123 passed, 3 subtests passed`；Python编译、Vue类型检查、Vite构建通过。
- 下一状态：待稽查
- 最终稽查退回：Blender穿衣/蒙皮尚未实现却被文档宣称已执行；分镜固定daily服装不解析真实换装；人物3D仍固化默认服装；服装归档按asset_name而非稳定costume_id。
- 稽查整改：分镜编译器解析日常服/战斗服/战甲/礼服/华服/练功服/制服/袍/披风等显式换装并跨镜延续；服装归档改用costume_id。未实现的无服装角色基础体、Surface Deform/蒙皮、碰撞穿插及穿衣后H3→Qwen链统一标记pending_development/capability_not_implemented，明确当前人物基准仍含默认服装且不得冒充已分离。
- 稽查整改软件复测：通过。换装施事、共同换装、脱旧换新、省略主语最近角色继承动态`7/7`；服装资产自动补齐、按`costume_id`归档、未实现能力阻断保持通过；关联回归`128 passed, 3 subtests passed`；Python编译、Vue类型检查、Vite构建通过。
- 服务端防绕过复测：通过。`/api/shots/generate`与`/api/shots/repair`携带`change_type=change`均返回HTTP 501 `capability_not_implemented`；`run-stage image`传播为HTTP 502 `production_stage_failed`且消息保留能力未实现错误；三路均未创建图片任务文件，`ACTIVE_IMAGE_SUBJECTS/ACTIVE_IMAGE_JOBS/ACTIVE_IMAGE_PROCESSES`均为0，cleanup与模型调用均为0。关联回归`129 passed, 3 subtests passed`；Python编译、Vue类型检查、Vite构建通过。
- 下一状态：待稽查

### BUG-20260811-013：M9.169任务批提交与LangGraph投影仍非原子边界

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.169
- 来源：M9.169首轮最终稽查退回。
- 阻断一：多job store逐条独立upsert，第N条失败会留下前N-1条部分提交。
- 阻断二：SQLite已提交后LangGraph report异常向业务层抛出，外层可能把completed反写failed，造成权威终态倒退。
- 整改：`DurableTaskRepository.upsert_many`在单一事务内提交全部任务并同事务写`task_projection_outbox`；第二条失败整批回滚。LangGraph投影失败保留outbox且不抛业务异常，由服务启动与worker心跳重放，成功后确认删除。
- 开发验证：第二条DB失败整批0提交；graph失败后任务保持completed、outbox保留，恢复后投影pending_confirmation并清outbox；关联测试与Python编译待独立复测确认。
- 下一状态：待软件测试复测
- 最终软件复测：通过。generate/repair直接请求均HTTP501 capability_not_implemented，production image stage返回502 production_stage_failed；任务文件无新增，ACTIVE三映射、cleanup和模型调用均为0；关联回归129 passed + 3 subtests，编译、类型检查和构建通过。
- 最终稽查：通过。服务端权威门禁位于任务ID、cleanup、ACTIVE、落盘和模型调用之前；production stage不降级并正确失败化。换装语义、跨镜延续、costume资产补齐、owner/version、按costume_id归档、pending能力边界及三份规范全部一致。
- 下一状态：已关闭
- 第三次稽查退回：stage revision检查仍依赖单个`ProductionOrchestrator`实例锁；两个服务实例可能同时读取旧revision并反序提交checkpoint。
- 跨进程整改：统一任务SQLite新增`task_projection_locks`，按tenant/user/project/stage获取带TTL的跨进程租约并由后台线程自动续租；持锁后重新读取最新outbox才允许report和CAS ack。进程退出后租约自动过期，不形成永久锁。
- 跨实例验证：两个独立DurableTaskRepository与两个ProductionOrchestrator实例共享数据库；rev1持锁阻塞时rev2 drainer返回不确认，rev1结束后rev2重放，最终图pending_confirmation/rev2且outbox空。专项`55 passed`及Python编译通过。
- 下一状态：待软件测试复测
- 软件测试：通过。动态故障注入验证`upsert_many`第二条DB失败时整批回滚为0任务/0 outbox；text/image/video三类Graph失败均不向业务抛出，SQLite与JSON保持completed一致且outbox各保留1条，未发生failed倒退。
- 重放证据：直接重启重放与worker heartbeat重放均把completed投影为LangGraph `pending_confirmation`并成功ack清空outbox；批事务/outbox动态`14/14`、心跳重放`3/3`通过。并发、重启与终态保护关联回归`133 passed, 3 subtests passed`，DurableTaskRepository与compat_server Python编译通过。
- 正式验收：8787 PID 41879、cwd正确、health healthy；worker active 0、三池queued 0且分层限额完整，Ollama模型0、Comfy队列0/0；未启动重模型。
- 下一状态：待重新稽查
- 重新稽查退回：outbox以job_id覆盖且ack仅按job_id删除；旧drain暂停期间新completed事件可覆盖旧queued，旧drain恢复后会误删新事件并把图状态回退。
- 并发整改：outbox新增SQLite全局单调`event_revision`；ack改为`job_id + event_revision` CAS。LangGraph按stage持久`projection_revisions`并忽略小于等于当前版本的旧投影；shutdown中途不ack，留待重启重放。
- 并发整改验证：动态交错“旧queued drain暂停→写completed rev2→新drain→旧drain恢复”后，outbox为空且图保持`pending_confirmation/revision=2`；专项`55 passed`及三文件Python编译通过。
- 下一状态：待软件测试复测
- 无变化去重补测：通过。text/image/video三类任务在首次投影成功并ack后，以完全相同payload再次保存均不执行upsert、不新增outbox且不重复调用Graph；payload状态从queued变为completed并修改内容后才重新入队，均投影最新`pending_confirmation`并成功ack。动态`9/9`、production_control专项`54 passed`及Python编译通过。
- 下一状态：待重新稽查
- Revision围栏补测：通过。动态闸门复现旧rev1 drain阻塞、rev2 completed写入并由新drain先完成、最后释放旧drain；LangGraph最终保持`pending_confirmation`与projection_revision=2，outbox清空，旧事件未覆盖或误ack新事件。专项交错测试通过。
- CAS与迁移：旧outbox表自动新增event_revision且历史行按revision=0可读；新事件取得全局单调rev1/rev2，使用rev1确认无法删除rev2，rev2确认成功。迁移/CAS动态`7/7`，shutdown在report后置位时不ack动态`2/2`。
- 最终回归：`134 passed, 3 subtests passed`；DurableTaskRepository、ProductionOrchestrator与compat_server Python编译通过。正式8787 PID 42569、cwd正确、health healthy，资源池active/queued 0、Ollama模型0、Comfy队列0/0；未启动重模型。
- 下一状态：待重新稽查
- 跨进程租约补测：通过。两个独立进程、独立Repository和共享ProductionOrchestrator实测rev1持锁阻塞后写入rev2，第二进程drain在租约占用期间返回0且不确认；旧进程结束后重放rev2，最终图为`pending_confirmation`/revision=2且outbox空，动态`8/8`。
- 租约边界：活动租约跨原TTL持续续期且拒绝抢占；不同stage可并行取得租约；持锁进程`os._exit`后在TTL内拒绝、过期后成功接管，动态`7/7`。shutdown中途不ack证据保持有效。
- 跨进程回归：`134 passed, 3 subtests passed`及三文件Python编译通过。正式8787 PID 43096、cwd正确、health healthy，资源池active/queued 0、Ollama模型0、Comfy队列0/0；未启动重模型。
- 下一状态：待重新稽查
- 第四轮稽查退回：续租线程更新失败或数据库异常只会退出，未向执行体暴露失租；旧owner可能在新owner完成并ack后继续提交旧checkpoint。并发首次抢锁的SQLite busy也可能向heartbeat抛出异常。
- 失租围栏整改：`ProjectionLease`显式维护`lost/owns`；续租异常、owner变化或过期立即失效。投影在Graph report前后验证租约，report途中失租或shutdown时从SQLite权威任务重建更高revision outbox事件，禁止旧owner确认新事件并保证后续重放修复。抢锁改为`BEGIN IMMEDIATE`原子判定，busy按未取得返回。
- 开发验证：旧rev1 report阻塞期间模拟租约接管、rev2完成并ack，旧report恢复后产生rev3权威修复事件，重放后图保持pending_confirmation且revision>2；两个Repository并发抢空锁仅一个成功。专项`57 passed`及三文件Python编译通过。
- 失租围栏首轮软件测试退回：租约退出删除锁行遇SQLite busy仍向drain/heartbeat抛出`OperationalError`。
- 释放整改：owner条件删除改为best-effort；瞬时SQLite异常不外抛，锁行由TTL自动回收。新增释放busy故障注入，专项`58 passed`及Python编译通过。
- 心跳容错：重放按text/image/video逐库隔离异常；单库busy保留outbox到下次心跳并继续其他库，禁止异常终止heartbeat。专项更新为`59 passed`。
- 失租围栏功能复测：release busy `2/2`、双进程空锁争抢`5/5`、续租异常lost `3/3`、失租晚到重建高revision 2项均通过；关联`137 passed, 3 subtests passed`及Python编译通过。正式8787与Ollama空闲；ComfyUI存在用户合法H3任务，未干预，待自然结束后补正式空闲验收。
- 下一状态：待软件测试复测
- 失租围栏软件复测：不通过；发现首个失败后立即停止，未启动重模型。
- 失败项：`DurableTaskRepository.projection_lock`仅在获取、续租和`owns()`路径捕获SQLite异常，但`finally`中的租约删除没有异常保护。释放阶段遇到`sqlite3.OperationalError: database is locked`会直接逃逸出上下文，能够中断`_drain_durable_task_projections`并终止worker heartbeat循环。
- 动态复现：成功取得`t:u:p:outline`租约后，在退出阶段注入SQLite busy；`cm.__exit__()`稳定抛出`OperationalError: database is locked`。这违反“SQLite busy不抛出且不得终止heartbeat”的明确验收边界。
- 预期行为：释放租约的SQLite busy/IO异常不得从context manager逃逸；应安全标记失租并由TTL回收，drain返回且heartbeat继续。仍需覆盖续租失败/owner接管后旧执行体不ack、旧report晚到重建更高revision事件及两进程空锁抢占。
- 下一状态：待处理
- 释放busy整改软件复测：增量功能通过。释放busy best-effort故障注入`2/2`；两独立进程/两Repository空锁争抢`5/5`，仅1方成功且无SQLite异常；续租异常置lost并禁止旧owner继续持有`3/3`。
- 失租与权威修复：精确回归`test_lost_projection_lease_requeues_authoritative_state`和`test_projection_lock_concurrent_acquire_has_one_owner`均通过；覆盖旧rev1 report阻塞、接管后rev2确认、旧report晚到重建更高revision事件并最终修复Graph。旧有shutdown不ack、CAS、跨进程续租/过期接管证据保持有效。
- 关联回归：`137 passed, 3 subtests passed`；DurableTaskRepository、ProductionOrchestrator与compat_server Python编译通过。
- 本轮正式验收：不通过，未启动任何测试重模型。8787 PID 44757、cwd正确、health healthy，worker active 0、三池queued 0，Ollama模型0；但ComfyUI 8194存在`queue_running=1`的MiniMaxH3FL2VAPromptAgentOpenAIAPI任务，不符合本轮“正式服务与资源空闲”验收前提；未停止或干预该任务。
- 下一状态：待ComfyUI自然空闲后补正式验收。
- 最终补验：通过。合法H3任务自然结束后，ComfyUI `queue_running=0/queue_pending=0`；全程未停止、清队列或重启。逐库replay瞬时busy专项通过，text库异常时保留outbox且继续image/video，heartbeat不退出；`test_production_control.py` `59 passed`。
- 最终正式验收：8787 PID 44757、cwd正确、health healthy；worker active 0、queue_depth 0，三池active/queued均0；Ollama模型0，ComfyUI队列0/0。关联全量`137 passed, 3 subtests passed`及三文件Python编译证据保持有效，未启动测试重模型。
- 最终稽查：通过。批事务、持久outbox、全局revision、CAS ack、跨进程ProjectionLease、失租高revision补偿、release busy TTL兜底与逐库heartbeat异常隔离均形成闭环。
- 最终空闲补验：Ollama上下文模型自然卸载，全程未停止或重启；8787 PID44757 healthy，worker与三池空闲，tasks=[]，Ollama models=[]，ComfyUI 0/0。
- 最终状态：已关闭。

### BUG-20260811-012：M9.167正式8787未加载分层背压资源池配置

- 状态：已关闭（重新最终稽查通过）
- 关联任务：M9.167
- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；正式服务验收失败，未启动重模型。
- 失败项：正式`GET /api/production/workers`的`resources.pools`仅披露`capacity/queue_limit/active/queued`，缺少M9.167要求的`tenant_queue_limit`与`project_queue_limit`。正式PID仍为37107，未加载当前资源调度器新快照契约。
- 预期正式值：accelerator全局/租户/项目=`16/8/4`，cpu-media=`64/32/16`，control=`256/128/64`；每个活动/排队票据同时披露tenant/user/project scope。
- 动态增量证据：隔离ResourceScheduler分层背压`14/14`通过，覆盖同项目超限、同租户跨项目超限、其他租户不受影响、拒绝不入队、取消/超时释放及部分身份拒绝。关联回归`130 passed, 3 subtests passed`，Python编译通过。
- 正式证据：8787 PID 37107、cwd正确且health healthy，worker active 0、queued 0，Ollama模型0、Comfy队列0/0；但三池均缺少两级限额字段，因此不得流转待稽查。
- 下一状态：待处理
- 第二次整改：统一任务仓库继续原样保存`waiting_memory`；向LangGraph投影时映射为`queued`，不再混用任务子状态与图生命周期。
- 第二次整改回归：关联`107 passed`，ResourceScheduler与compat_server Python编译通过；未启动重模型。
- 下一状态：待软件测试复测
- 第二轮软件测试：通过。正式8787已安全切换至PID 39852，cwd正确、health healthy；三池快照精确披露accelerator `16/8/4`、cpu-media `64/32/16`、control `256/128/64`，active与queued均为0。
- 第二轮动态证据：票据scope `3/3`验证排队项完整披露tenant/user/project并在执行后释放；首轮分层背压`14/14`证据继续有效。关联回归`130 passed, 3 subtests passed`，ResourceScheduler与compat_server Python编译通过；Ollama模型0、Comfy队列0/0，未启动重模型。
- 下一状态：待稽查
- 最终稽查退回：同步HTTP票据正确，但视频即时线程、waiting-memory恢复线程和3D后台线程不会继承`threading.local`，其票据scope为空，可绕过租户/项目限额。
- 主线整改：`_claim_production_resource`新增显式identity参数；视频与3D执行器从持久请求body传入完整tenant/user/project，waiting-memory恢复复用同一视频执行器。thread-local只保留同步请求兼容用途。
- 整改回归：关联`106 passed`，ResourceScheduler与compat_server Python编译通过；未启动重模型。
- 下一状态：待软件测试复测
- 稽查整改复测：不通过；动态覆盖waiting-memory真实持久路径时发现首个失败，已立即停止，未启动重模型。
- 失败项：`_save_video_jobs`调用`_sync_durable_tasks`时，`lifecycle_map`把视频状态`waiting_memory`映射为同名生命周期，再调用`ProductionOrchestrator.report(..., "waiting_memory")`；LangGraph拒绝并抛出`ValueError: invalid production lifecycle: waiting_memory`。带完整tenant/user/project身份的等待内存视频任务因此无法正常持久化和进入后续`_launch_waiting_video_job`。
- 动态复现：隔离输出目录写入`status=waiting_memory`且`request`含完整identity的视频任务，调用`_save_video_jobs`稳定触发上述异常；堆栈位于`compat_server.py::_sync_durable_tasks → production_orchestrator.py::report/apply_event`。
- 预期行为：等待内存属于资源排队子状态，投影到LangGraph时应使用其支持的`queued`生命周期，并把`waiting_memory`保留为任务stage/substate证据；持久化、重启恢复和内存满足后的异步启动均不得失败。
- 下一状态：待处理
- 第二次整改软件测试：通过。隔离真实持久仓库验证任务payload保持`waiting_memory`、LangGraph video阶段投影`queued`；即时video、waiting-memory恢复启动、asset3d后台执行器三条路径均把完整tenant/user/project显式传入资源claim，动态`5/5`通过。
- 最终回归证据：关联测试`131 passed, 3 subtests passed`；ResourceScheduler与compat_server Python编译通过。正式8787 PID 40741、cwd正确、health healthy；三池分层限额16/8/4、64/32/16、256/128/64，active/queued均0，Ollama模型0、Comfy队列0/0；未启动重模型。
- 下一状态：待重新稽查
- 重新最终稽查：通过。同步HTTP、即时视频、waiting-memory恢复与3D后台线程均携带完整identity；三级限额原子生效，任务仓库保留`waiting_memory`且LangGraph仅接收`queued`投影。
- 关闭证据：软件动态异步`5/5`、关联`131 passed, 3 subtests passed`；正式PID40741三池限额正确且任务、资源、Ollama、Comfy均空。
- 下一状态：已关闭

### BUG-20260811-011：M9.165项目加载仍会自动提交资产生产阶段

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.165
- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个失败后立即停止，未启动重模型。
- 失败项：`loadProjectFlowState`与其调用的`loadAssetState`仍存在两条自动执行`extractProductionAssets("manual")`的路径；该函数最终调用`runProductionAssetExtraction`并提交`productionLedgerService.runStage(stage:"assets")`，项目刷新可能自动启动资产文本提取生产任务。
- 复现边界一：已确认分镜、存在镜头且人物/场景/道具框架均为空时，`loadProjectFlowState`在加载末尾直接`void extractProductionAssets("manual")`。
- 复现边界二：读取旧资产阶段后发现`census_version/source_episodes`过期时，`loadAssetState`清空框架、持久化并直接`await extractProductionAssets("manual")`。
- 实际行为：页面加载和刷新不只是恢复持久状态与提示，仍可自动提交assets阶段、占用资源并启动模型；中断assets或旧census项目存在重复重提风险。
- 预期行为：M9.164加载链只能读取、失败化本地展示状态并给出统一人工继续提示；上述两处自动提取必须移出load路径，由用户显式操作触发。10类恢复阶段加载期间生成、提取、合片、审核、超分和导出调用均应为0。
- 已验证后端边界：隔离动态探针确认outline/script/storyboard/assets/image/video/composition/review_export八个running阶段可写项目failed、revision递增、ledger failed并通知Condition；无存储映射仍graph failed，completed/pending未误改。该结果因首败规则不作为整项通过结论。
- 下一状态：待处理
- 第二轮软件测试：通过。`loadProjectFlowState`的confirmed空资产路径及`loadAssetState`的stale census路径均只调用`seedAssetCardsFromStoryboard`建立本地pending卡并持久化提示，`extractProductionAssets`、`runStage(assets)`和`extractCharacters`调用为0；10类resume恢复区段无生成、合片、审核、超分或导出调用，分镜视频无50ms自动重提。
- 服务端动态验证：outline、script、storyboard、assets、image、video、composition、review_export八个running阶段均同步写入项目failed、revision从7递增至8、ledger lifecycle=failed并通知watch Condition；无项目存储映射仍写graph failed，completed/pending不误改，多项目相互隔离，第二次恢复不再写入，资源池active/queued始终为0。
- 回归证据：本增量及关联用例`126 passed, 3 subtests passed`；另有2条并行M9.164人物45°新口径尚未同步的旧0°静态断言失败，与M9.165恢复增量无关。Python编译、Vue TypeScript检查和Vite正式构建通过（82 modules，690ms）。正式8787 PID 37107、cwd正确、health healthy，worker active 0、三池queued 0，Ollama模型0、Comfy队列0/0；未启动重模型。
- 下一状态：待稽查
- 最终稽查：通过。前端10类加载链不再自动启动生产；空资产与过期census仅播种本地卡片；服务端八阶段恢复同步失败化项目阶段、revision、watch、生产台账与LangGraph，重复恢复幂等且不占资源。正式服务及模型队列为空。
- 关闭证据：最终独立回归`128 passed, 3 subtests passed`，类型检查与正式构建通过；稽查专项动态与Python编译通过。
- 下一状态：已关闭
- 最终软件复测：通过。并行遗留的两条人物0°旧断言已同步为M9.164左45°基准契约；M9.165页面加载零自动重提、空资产/stale census仅播种pending卡、八阶段服务端失败化恢复及现行45°资产流程共同回归通过。
- 最终回归证据：`128 passed, 3 subtests passed`；Python编译、Vue TypeScript检查及Vite正式构建通过（82 modules，677ms）。正式8787 PID 37107、cwd正确、health healthy，worker active 0、三池queued 0，Ollama模型0、Comfy队列0/0；未启动重模型。
- 下一状态：待稽查

### BUG-20260811-010：M9.162最终分镜响应无法立即终止阶段订阅

- 状态：已关闭（重新最终稽查通过）
- 关联任务：M9.162
- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个失败后立即停止，未启动重模型。
- 失败项：最终`runStage(storyboard)`响应到达后，前端未取消正在阻塞的`watchStage`长轮询。
- 复现路径：`progressPoll`正阻塞于`projectService.watchStage(... timeout_seconds:20, controller.signal)`且期间无阶段写入；最终`runStage`先返回。当前代码只执行`polling=false`，随后立即`await progressPoll`，但共享controller未abort且没有独立订阅controller，因此watch仍要等服务端超时，最终响应处理最多额外阻塞20秒。
- 代码证据：`plugins/builtin/short_drama/frontend/App.vue::generateStoryboards`只有主生成`controller`；最终响应路径在`await progressPoll`前没有终止watch请求的独立AbortSignal。若abort主controller又会命中后续`controller.signal.aborted`并丢弃合法最终结果。
- 预期行为：阶段订阅使用独立、与主生成任务分离的AbortController；项目切换/用户停止同时取消两者，最终响应仅取消watch并立即等待其退出，不得取消或丢弃最终生成结果。
- 同类边界：最终成功、最终失败、项目切换、用户停止和组件卸载均需精确释放订阅槽；断线重连仍从最后revision恢复，禁止遗留20秒挂起订阅。
- 下一状态：待处理
- 第二次整改：新增独立`project-stage-watch-reaper`守护线程，每秒调用统一回收函数，取消标记满30秒即清除，不依赖后续请求；守护线程复用服务关闭事件自动退出。取消接口仍同步清理过期项并保留cancel-before-register保护。
- 第二次开发验证：关联107项及3个子测试、回收函数动态边界、Python编译、Vue类型检查与Vite构建通过；未启动重模型。
- 下一状态：待软件测试复测
- 主线整改：主生成与阶段订阅拆为独立AbortController；最终响应只停止订阅并保留合法生成结果，项目切换/停止仍由主controller联动取消订阅。每个长轮询使用唯一request_id，前端终止时调用定向cancel接口，服务端Condition立即唤醒并释放订阅槽；取消标记30秒过期清理，覆盖请求注册竞态且不永久泄漏。
- 开发验证：关联107项及3个子测试、Python编译、Vue类型检查与Vite构建通过；未启动重模型。
- 下一状态：待软件测试复测
- 第二轮软件测试：不通过；发现首个失败后立即停止，未启动重模型。
- 第二轮失败项：取消先于订阅注册、且对应订阅请求最终未到达时，`PROJECT_STAGE_CANCELLED_WATCHES`中的取消标记不会在30秒后自动清理。当前清理循环仅位于后续`POST /api/projects/stage/watch/cancel`处理过程中；若系统此后没有新的取消请求，该孤儿标记会无限期驻留，未满足“30秒清理无泄漏”。
- 动态与回归证据：关联测试`128 passed, 3 subtests passed`；Python编译、Vue TypeScript检查及Vite正式构建通过（82 modules，697ms）。正式8787 PID 35461、cwd正确、health healthy，worker active 0、三池queued 0，Ollama模型0、Comfy队列0/0。隔离HTTP夹具未启动重模型。
- 预期行为：取消标记必须有不依赖后续请求的到期回收机制，或使用可证明自动过期的数据结构；30秒后孤儿标记应实际消失，同时保留取消先于注册的竞态保护。
- 下一状态：待处理
- 第三轮软件测试：通过。动态验证取消标记在29.9秒仍保留、满30秒清除；独立reaper每秒执行且不依赖新请求，cancel/watch/reap并发无异常，服务关闭事件可在1秒内结束线程。cancel-before-register与活动watch均能立即唤醒并释放槽。
- 事件通道验证：final使用独立watch controller并在等待progressPoll前定向取消，主生成controller及合法最终结果保持；项目切换/用户停止联动终止订阅。revision即时返回、无变化超时、同项目多订阅、跨项目隔离、断线续订、无效参数、25秒上限、128槽背压与释放恢复均通过；等待不占生产资源池，响应位于项目锁外。
- 回归证据：关联测试`128 passed, 3 subtests passed`；reaper动态专项`5/5`；Python编译、Vue TypeScript检查与Vite正式构建通过（82 modules，695ms）。正式8787 PID 35461、cwd正确、cancel/watch接口通过，worker active 0、三池queued 0，Ollama模型0、Comfy队列0/0；未启动重模型。
- 下一状态：待稽查
- 最终稽查退回：取消键仅含request_id，可跨租户/项目/阶段碰撞；shutdown只置停止事件但未notify活动Condition，槽和请求线程最长滞留25秒。
- 第三次整改：取消标记键升级为`tenant_id + user_id + project_id + stage + request_id`完整作用域，GET与cancel共同校验；相同request_id在不同作用域完全隔离。watch循环检测shutdown并返回503 cancelled，main finally在同一Condition广播，所有活动等待立即进入finally释放槽。
- 第三次开发验证：关联107项及3个子测试、Python编译、Vue类型检查与Vite构建通过；同时同步人物六格与逐角度确认的现行测试契约，未启动重模型。
- 下一状态：待软件测试复测
- 第四轮软件测试：通过。动态HTTP闸门`12/12`验证相同request_id可在不同tenant/user/project/stage并存，定向取消仅目标scope退出，另一项目保持等待；缺任一scope返回400，cancel-before-register仅命中完整scope。
- Shutdown验证：7个活动watch在关闭事件置位并Condition广播后均于4ms内返回503、`cancelled=true`，全部订阅槽可重新获取；reaper复用关闭事件退出。final独立取消、合法主结果保留、revision、timeout、断线续订、128槽背压与释放恢复无回归。
- 第四轮回归证据：关联测试`128 passed, 3 subtests passed`；Python编译、Vue TypeScript检查和Vite正式构建通过（82 modules，718ms）。正式8787 PID 37107、cwd正确；完整scope取消、跨scope隔离及缺scope拒绝通过，worker active 0、三池queued 0，Ollama模型0、Comfy队列0/0；未启动重模型。
- 下一状态：待重新稽查
- 重新最终稽查：通过。五元作用域取消、跨scope同ID隔离、cancel-before-register、shutdown广播/503/槽释放、reaper退出、revision无丢唤醒、锁外响应、独立controller、128槽背压和断线恢复均符合规范。
- 稽查证据：关联79项及3个子测试、Python编译通过；软件128项及3个子测试、HTTP 12/12、7个活动watch在4ms内shutdown退出有效。正式资源与模型队列空闲。
- 关闭状态：已关闭。

### BUG-20260811-009：M9.161增量分镜轮询晚到响应污染新项目

- 状态：已关闭（重新最终稽查通过）
- 关联任务：M9.161
- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个失败后立即停止，未启动重模型。
- 失败项：分镜500ms增量轮询在`readStage`响应返回后缺少project/session/abort复核。
- 复现路径：p1进入`generateStoryboards`并阻塞在`await projectService.readStage(storyboard)`；此时切换并加载p2，使project session变化且p1 controller被abort；随后释放p1旧响应。当前代码直接解析旧响应并执行`storyboardShots.value = incoming...`，仅之后调用的`seedAssetCardsFromStoryboard`按项目ID返回，因此p2分镜数组已被p1晚到镜头覆盖。
- 代码证据：`plugins/builtin/short_drama/frontend/App.vue`的`progressPoll`只在while条件和发请求前检查上下文；`await readStage(...).catch(...)`之后，未执行`isCurrentProjectSession(project.id, session)`或`controller.signal.aborted`检查，就比较并写入`storyboardShots.value`。
- 预期行为：增量读取响应返回后、读取/比较/写入分镜前必须同时复核project ID、session及abort；旧项目晚到成功或异常不得修改新项目分镜、资产卡、提取队列、状态、错误或持久数据。
- 同类边界：最终`runStage(storyboard)`响应已有上下文复核；增量轮询必须使用同等级围栏，并覆盖旧请求成功、异常、忽略signal、项目切换和轮询与最终响应竞态。
- 下一状态：待处理
- 主线整改：增量`readStage`返回后、比较镜头前、写入前和资产卡创建后均复核启动项目ID、session及AbortSignal；旧项目响应即使忽略signal晚到也立即丢弃。资产卡播种函数显式接收原session/signal，持久化不再读取可变全局session。
- 开发验证：关联105项及3个子测试、Python编译、Vue类型检查和Vite构建通过；未启动重模型。
- 下一状态：待软件测试复测
- 第二轮软件测试：通过。动态闸门验证p1增量`readStage`阻塞后切换p2并abort，p1忽略signal的晚到成功与异常均不会修改p2的shots/assets/status/error/persist或提取队列；轮询晚到与最终`runStage`响应竞态由最终结果保持权威且不重复播种/提取。
- 流式与恢复：服务端动态验证每集完成均累积shots并写`generating + streaming_episode`；第二集失败时只保留第一集generating部分记录，不写confirmed、不推进LangGraph/assets。前端按500ms读取，按project/session/episode去重并串行提取；最终只补未处理集，名称合并保留既有图片、确认状态和版本。
- 回归证据：关联`109 passed, 3 subtests passed`；Python编译、Vue TypeScript检查和Vite正式构建通过（82 modules，706ms）。正式8787 healthy/langgraph且资源池空，Ollama模型0，Comfy队列0/0；未启动重模型。
- 下一状态：待稽查
- 重新最终稽查：通过。storyboard running期间逐集仅执行`storyboard_preview`，不提交或推进assets；最终停止并等待轮询和同一预览队列后仅一次正式assets。项目围栏、按集去重、失败恢复、部分状态与保留式合并均符合规范。
- 稽查证据：软件110项及3个子测试、动态竞态、编译与构建证据有效；稽查专项与Python编译通过。正式资源池、Ollama、Comfy均空闲。
- 关闭状态：已关闭。
- 最终稽查退回：生成中逐集提取错误提交公开`assets`阶段，会被仍处于running的storyboard前序门禁拒绝；最终收口也未等待逐集队列，存在互相abort与重复提交竞态。
- 第二次整改：逐集任务改用`storyboard_preview`非推进式预览能力，只合并并持久化pending卡片，不改变LangGraph assets阶段；正式分镜响应先停止并等待轮询，再等待同一资产预览串行队列排空，确认project/session后对全量完成集只提交一次正式`stage:assets`。
- 第二次开发验证：关联106项及3个子测试、Python编译、Vue类型检查和Vite构建通过；未启动重模型。
- 下一状态：待软件测试复测
- 第三轮软件测试：通过。动态闸门验证生成中逐集预览仅调用非stage `/api/characters/extract`并以`storyboard_preview`合并pending卡片，正式`runStage(assets)`调用0、LangGraph不推进；最终响应先停止并等待轮询，再等待预览队列，随后对全量完成集仅调用1次正式assets。
- 竞态与失败：预览阻塞时最终收口等待且不会互相abort；预览失败不会阻断最终正式assets；项目切换后旧预览和最终响应均不修改新项目shots/assets/status/error/persist或提取队列。服务端逐集累积持久和cancel边界通过。
- 回归证据：关联`110 passed, 3 subtests passed`；Python编译、Vue TypeScript检查及Vite正式构建通过（82 modules，689ms）。正式8787 healthy/langgraph且资源池空，Ollama模型0，Comfy队列0/0；未启动重模型。
- 下一状态：待稽查

### BUG-20260811-008：M9.160扩展替换校验失败会破坏原活动绑定

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.160
- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个失败后立即停止，未启动重模型。
- 已通过：`test_production_control.py` 49/49通过；`production_extensions.py`与正式后端Python编译通过。
- 失败项：`ProductionExtensionRegistry.register(..., replace=True)`异常路径不是原子操作。
- 动态复现：先注册并激活`storage/stable`，再调用`register('storage','bad', ..., enabled=False, replace=True)`；接口按预期抛出`disabled extension provider cannot be activated`，但抛错前已删除原`stable`提供方并清除active绑定。随后`list()`为空，`create('storage')`报`extension has no active provider`。
- 预期行为：所有输入和激活条件必须在修改注册表前完成校验；替换注册失败时原已安装提供方、唯一active绑定及可创建实例必须完整保留。
- 实际行为：`replace`分支先重写`_extensions`并弹出`_active`，随后才校验禁用提供方不能激活，导致失败请求破坏生产基础设施绑定。
- 同类风险：任何在修改注册表之后抛出的替换校验异常都可能留下空扩展点；需覆盖`replace=true`禁用/显式激活冲突及异常后原绑定仍可创建，并验证并发观察不到中间空状态。
- 下一状态：待处理
- 主线整改：将完整替换的激活决策和禁用校验前移到任何注册表写操作之前；无效替换在持锁状态下直接拒绝，原提供方集合、active绑定和工厂实例能力均保持不变，不产生并发可见的空窗口。
- 开发验证：新增`test_rejected_extension_replacement_is_atomic`，确认失败后仍只有原`stable`活动提供方且可正常创建；关联回归104项及3个子测试、Python编译全部通过，未启动重模型。
- 下一状态：待软件测试复测
- 第二轮软件测试：通过。动态验证禁用完整替换、`activate=true`冲突及active provider的禁用provider级刷新失败时，原provider集合、active绑定和`create`结果完全不变；8读1写并发各1500轮未观察到空窗口。多provider安装、唯一active、显式激活/回滚、provider级启停/卸载、active卸载确定性接管、禁用active后无静默fallback、builtin刷新保留plugin与active均通过。
- 回归证据：关联`108 passed, 3 subtests passed`；Python编译通过。正式8787由LaunchAgent绝对路径和正确cwd运行，health为healthy/langgraph；管理接口披露8个唯一扩展点且全部active/enabled，provider与metadata完整；资源池、Ollama和Comfy队列均空闲。
- 下一状态：待稽查
- 最终稽查：通过。注册、完整替换、单提供方刷新、激活、启停、卸载与唯一active投影均在同一RLock临界区；失败替换写入前拒绝，create锁内快照并在锁外创建实例。回滚、确定性接管、禁用active无fallback及内置刷新保留插件均符合规范。
- 稽查证据：直接关联79项和Python编译通过；软件108项及3个子测试、8读1写压力与正式8项唯一active证据有效。资源池、Ollama及Comfy队列空闲。
- 关闭状态：已关闭。

### BUG-20260811-007：M9.157正式服务未加载节点内资源池调度增量

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.157
- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个失败后立即停止，未重启服务、未启动重模型。
- 增量验证：`test_production_control.py` 44/44通过；动态验证默认全局串行兼容、accelerator容量1互斥、GPU占用期间control与两个audio并发、cpu第三项等待/取消、超时清队列、snapshot兼容，以及accelerator/cpu-media/control三池超限立即backpressure且拒绝项不入队，均通过。Python编译通过。
- 失败项：正式8787仍运行旧资源调度器快照与旧工作节点容量。
- 复现证据：只读`GET /health`返回HTTP 200且`orchestrator=langgraph`，但`resources`仅含`active`和`queued`，缺少新增`active_items`与`pools`；只读`GET /api/production/workers`返回健康工作节点`capacity=1`，并同样只返回旧资源快照，未达到M9.157要求的池容量总和11和真实票据活动数口径。
- 预期行为：正式服务加载当前M9.157代码后，健康快照同时保留旧`active`并提供`active_items/pools`；本机健康worker capacity为11，active取实际活动票据数量。
- 实际行为：源码与隔离测试已通过新框架，但正式服务未加载该增量，正式运行契约仍是旧版本。
- 下一状态：待处理
- 主线整改：确认正式任务、Ollama与Comfy均空闲后，通过LaunchAgent后台受控重启8787；新PID 30315以目标绝对路径和cwd启动。`/health`现返回active兼容字段、active_items及三池快照，`/api/production/workers`中新健康worker上报capacity=11、active=0，Ollama模型0。
- 附加框架修复：受控重启暴露旧PID worker在进程内WorkloadRouter仅标记不健康但不删除；新增`WorkloadRouter.reap()`并在心跳/看门狗周期同步清退持久发现和内存路由投影，补心跳过期清退动态测试。
- 开发验证：`test_production_control.py`扩为45项并通过，平台调度器与正式后端Python编译通过；未启动重模型。
- 下一状态：待测试
- 第二轮软件测试：通过。`test_production_control.py` 45/45通过；动态覆盖默认全局串行与旧优先级、accelerator容量1互斥、GPU占用期间control与两个audio并发、cpu第三项等待与取消、超时清理、三池独立backpressure且拒绝项不入队、snapshot兼容。Python编译通过。
- 正式验收：LaunchAgent `com.local.ai.compat-server`使用目标绝对Python/脚本/PYTHONPATH及cwd，正式PID 30535由launchd托管；`/health`为healthy/langgraph，资源快照同时含active/active_items/queued/pools，三池容量1/2/8且均空；旧worker已清退，仅一个健康worker，capacity=11、active=0。Ollama模型0，Comfy 8194队列0/0。
- 下一状态：待稽查
- 最终稽查：通过。资源池准入/释放在Condition锁内原子更新；accelerator容量1叠加execution_lock保持物理互斥，control与cpu-media独立并发；默认global串行兼容，资源映射/容量/队限/serialized_pools均可注入。快照、worker真实容量、双层reap及正式运行态均通过。
- 稽查证据：45/45与四文件Python编译通过；正式PID30535、三池1/2/8空闲、唯一健康worker capacity11 active0、Ollama0、Comfy 0/0。
- 关闭状态：已关闭。

### BUG-20260811-006：资产阶段后台自动提交与按钮提交发生冲突

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.156
- 现象：页面显示`production stage is already running: assets`，但正式资源队列为空，项目资产阶段保存为failed。
- 根因：项目加载只要存在分镜且资产为空就会后台调用资产提取，未要求分镜已确认；用户点击“生成图片”又会提交一次。原`assetEntryPromise`只覆盖按钮事务，未覆盖加载、确认、恢复与图片生成前的全部提取入口。
- 主线整改：按用户既定“资产图片手动上传”口径，项目加载/刷新彻底禁止自动启动assets；仅点击进入资产时确认分镜、提取清单并创建上传卡槽，不自动生图。点击相关资产提取入口统一进入键控单飞事务。保留服务端LangGraph前序和并发门禁。
- 开发验证：专项与生产控制51/51通过，Vue类型检查与Vite正式构建通过；正式资源队列为空，未启动重模型。

#### 第一轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个阻断后立即停止，未启动重模型。
- 已通过边界：`loadProjectFlowState`仅在storyboardStatus=confirmed、分镜非空且三类资产均为空时触发自动提取；waiting_confirmation加载路径不触发runStage。
- 失败项：资产提取single-flight跨项目共享，旧项目忽略signal的晚到结果会污染新项目。
- 动态复现：p1调用`extractProductionAssets()`并阻塞runStage；切换到p2、加载p2既有资产与confirmed状态后再次调用提取，第二次直接返回p1的同一`assetExtractionPromise`。释放p1成功响应后，p1结果无项目/session校验地写入当前`characterProfiles/sceneProfiles/propProfiles`并把p2状态改为waiting_confirmation；动态结果`samePromise=true`、`runCalls=1`、p2资产被`p1-late`覆盖。
- 出错模块：`plugins/builtin/short_drama/frontend/App.vue::extractProductionAssets`与`runProductionAssetExtraction`。
- 预期行为：单飞必须绑定project ID/session；同项目加载、确认、按钮和生成前路径共享一次执行，不同项目不得共享Promise。响应、异常、持久化和通知前均需验证启动项目/session仍有效及controller未abort；忽略signal的晚到响应不得修改新项目。
- 实际行为：`assetExtractionPromise`为无身份全局Promise；项目切换后的p2调用仍复用p1 Promise。执行函数只在catch检查controller.aborted，成功响应及结果合并路径没有项目/session/abort围栏。
- 同类风险：旧项目409或其他异常也可能把新项目状态写failed/error；旧项目成功会覆盖新项目档案并把持久化写向当前项目。
- 下一状态：待处理
- 追加整改：单飞改为按`project.id:projectSession`键控Map，同项目共享、跨项目隔离；提取响应、归档、结果替换、持久化、通知和异常路径均执行project/session/abort围栏。`persistAssetState`支持显式project/session并在排队写入前复核上下文，旧项目晚到结果不得写入新项目。专项51/51、类型检查与构建通过。
- 用户口径补充：资产图片为手动上传。已删除项目加载时的全部自动资产提取调用；确认/进入资产只建立人物、场景、道具上传卡槽，不调用图片生成模型。
- 界面闭环：分镜下一步改为“上传资产图片”，资产页主操作改为手动上传指引并移除`generateAllAssetImages`绑定；恢复到旧自动任务时只提示手动上传，不再自动续跑生图。

#### 第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 手动上传口径：`loadProjectFlowState`内资产提取调用0、production runStage调用0；waiting_confirmation、confirmed及空资产三类加载均不会后台启动assets。点击入口才确认分镜并提取一次清单，创建人物/场景/道具待上传卡槽；该事务内`generateCharacter`调用0，不自动生图。
- 键控单飞：同一project ID/session并发调用返回同一Promise且runStage=1；p1阻塞后切换p2，p2取得独立Promise并独立runStage。p1忽略signal的晚到成功或异常均不改变p2档案、status、error或通知，两个键最终均释放。
- 失败与恢复：409/异常后对应键释放，下一次点击形成新事务并成功重试；abort路径不提交结果。持久化按显式project/session捕获数据快照，排队实际写入前再次复核，旧上下文不写新项目。
- 正式前序门禁：当前项目workflow保持status=failed/current_stage=assets，storyboard=pending_confirmation、assets=failed。资源空闲时轻量重试公开assets返回409 `previous stage is not completed: storyboard`，未启动执行器、未绕过前序确认，状态保持原值。
- 回归与构建：专项与生产控制`51 passed`；Vue TypeScript检查和Vite正式构建通过（82 modules，677ms）。
- 正式空闲：8787为healthy/langgraph，资源active为空、queue为空，Ollama模型0。
- 流转状态：待稽查

#### 手动上传界面闭环增量软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；业务实现符合新增口径，但关联回归存在2条旧契约失败，按规范退回。
- 已通过业务项：分镜下一步文案为“上传资产图片”；资产页主按钮为“手动上传图片”并仅提示逐卡导入；主按钮未绑定`generateAllAssetImages`。项目加载、assets恢复和图片中断恢复均不调用自动批量生图；空态提示手动上传。`UnifiedAssetCard`仍按slide精确调用`openAssetPhotoReplacement`，基准/角度导入、确认门禁及`assetsReadyForShotImages`进入分镜画面逻辑保持。
- 失败回归1：`tests/unit/test_short_drama_spec_validation.py::test_workflow_next_steps_use_complete_episode_minimums`仍强制查找旧文案`storyboardHasCompleteEpisode ? '生成图片'`，新实现按用户口径为`上传资产图片`，断言失败。
- 失败回归2：`tests/unit/test_image_job_recovery.py::test_stale_image_jobs_are_failed_and_resumable`仍强制要求`resumeStages.includes("assets")) { void generateAllAssetImages()`，该自动生图行为已被用户明确禁止，断言失败。
- 旧契约整改：规范测试改为要求“上传资产图片”；恢复测试改为要求中断提示且恢复区段不得调用`generateAllAssetImages`。关联75项及3个子测试、Vue类型检查、Vite构建通过。
- 测试计数：本次关联套件`88 passed, 2 failed, 3 subtests passed`；失败均为未同步的新需求静态断言，不是业务实现回退。
- 预期整改：将两条测试契约更新为“上传资产图片”和“assets恢复只提示手动上传且不得调用generateAllAssetImages”，再重新提交全套软件测试。
- 下一状态：待处理

#### 手动上传界面闭环第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 界面与恢复：分镜下一步精确为“上传资产图片”；资产页主操作精确为“手动上传图片”并提示逐卡导入。`loadProjectFlowState`资产提取0次，assets恢复区段`generateAllAssetImages`调用0次，中断只显示手动上传提示，空态文案正确。
- 卡片与门禁：`UnifiedAssetCard`的baseline/variant仍按slide精确进入`openAssetPhotoReplacement`；主操作未绑定自动生图；`assetsReadyForShotImages`确认门禁及“生成分镜画面”入口保持有效。
- 关联回归：更新后的完整套件`90 passed, 3 subtests passed`，原2条旧契约均通过。
- 构建与运行态：Vue TypeScript检查与Vite正式构建通过（82 modules，699ms）；8787 healthy/langgraph、资源active为空、queue为空，Ollama模型0。
- 流转状态：待稽查

#### 用户最新临时自动流程（覆盖手动上传口径）

- 最新要求：分镜脚本完成后自动提取人物、道具、场景框架；图片恢复自动生成。人物严格三张全身视图：0°、90°、180°；首次只生成0°正面基准图，人工确认后才生成90°与180°。
- 主线整改：审核关闭或审核通过时，分镜结果自动置confirmed、同步LangGraph/ledger后提取资产框架；confirmed项目重载且框架为空时自动补提取，提取仍使用项目/session键控单飞。
- 人物视图：删除45°基准和额外正面variant，固定三槽为0°基准、90°侧面、180°背面。首轮批量仅生成0°；`confirmAsset`后才创建并生成90°/180°。
- 后端验收：人物基准提示、Klein9B元数据、重试提示与视觉验收统一改为`front_full`；旧45°资产通过`view_contract`失效，禁止冒充0°基准。
- 确认门禁：0°人工确认必须等待生产ledger确认成功后才启动90°/180°；确认同步失败恢复waiting_confirmation且两个角度保持pending，项目切换后不得生成旧项目角度图。
- 第一轮最新流程复测退回：90°请求期间切换项目时，忽略signal的晚到响应会继续提交180°并污染当前项目状态。
- 追加整改：90°/180°生成链增加按项目+资产键控AbortController与project/session/abort围栏；每个角度提交前、响应后、状态更新、持久化及进入下一角度前均复核，项目切换会取消旧链并禁止180°继续提交。相关92项及3个子测试、类型检查、构建通过。
- 0° LoRA检查：正式国风厚涂项目走Klein9B，动态只读选择结果包含批准的`风格_古代幻想厚涂_FLUX2_Klein9B_仅测试.safetensors`（scale 0.9，SHA开头42253aaa6214）；当前男女Klein9B人物LoRA均`production_approved=false`，因此0°不会加载未批准人物LoRA。Schnell路径则会按项目风格与性别选择已批准风格/人物LoRA。
- 最终稽查退回：项目load/resume与中断图片恢复仍自动调用`generateAllAssetImages`；现行生产规范仍写左45°基准。
- 稽查整改：load只允许自动补资产框架，图片中断仅恢复pending并提示点击生成，不自动启动模型；`短剧从剧本到成片生产规范.md`统一为0°确认后90°/180°，删除45°基准。
- 开发验证：相关92项及3个子测试通过，Vue类型检查与Vite构建通过，未启动重模型。

#### M9.156人物三视图自动流程软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；确认失败门禁已修正，继续测试发现项目切换阻断后立即停止，未启动重模型。
- 已通过项：人物槽位精确为0°正面全身、90°侧面全身、180°背面全身三槽；首次批量只生成baseline，后两槽不在首次队列；ledger确认失败恢复0° waiting_confirmation，90°/180°均回到pending且生成调用0。
- 失败项：确认成功后生成固定角度期间切换项目，旧项目仍继续生成后续角度。
- 动态路径：p1确认0°成功后进入`generateAssetVariantsFromConfirmedBaseline`，90°请求阻塞；切换并加载p2后释放p1的90°晚到成功。该函数没有捕获projectSession，也未在响应后、持久化前和下一次循环前检查`isCurrentProjectSession`/abort，因而继续提交p1的180°请求，并执行全局`assetStatus/assetError/persistAssetState()`路径。
- 出错模块：`plugins/builtin/short_drama/frontend/App.vue::generateAssetVariantsFromConfirmedBaseline`。
- 预期行为：函数必须显式接收启动project/session及专属controller；每个角度提交前、响应后、状态替换和持久化前均执行project/session/abort围栏。切换项目后允许已发请求晚到但必须丢弃，且不得继续提交下一角度。
- 实际行为：函数仅在开始时读取project，没有session或controller；循环对90°/180°连续执行，晚到响应无隔离，默认`persistAssetState()`还会使用当前新项目上下文。
- 同类风险：旧项目90°/180°结果、失败信息及资产总状态可污染新项目，且产生用户不可见的旧项目重模型任务。
- 下一状态：待处理

#### M9.156人物三视图自动流程第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 自动框架：分镜生成在审核关闭或审核通过时置confirmed，依次持久化、同步production ledger后自动提取人物/道具/场景框架；审核未通过保持waiting_confirmation且不提取。confirmed项目加载且框架为空可补提取，图片模型调用0；提取项目/session键控单飞与跨项目晚到隔离保持。
- 三槽与阶段：人物视图精确仅0°正面全身、90°侧面全身、180°背面全身，无人物45°及额外正面variant。首次`generateAllAssetImages`仅调用baseline，variant调用0；0°进入waiting_confirmation。ledger确认成功后90°/180°各生成1次；确认失败时两槽保持pending且生成0次。
- 固定角度隔离：p1的90°阻塞后切p2并释放忽略signal的晚到成功或异常，p1结果均丢弃、180°调用0、p2状态及持久化0污染；abort同样阻断。相同资产重入终止前一controller，不同资产使用独立controller并可并发，finally仅清自身实例。
- 后端契约：人物baseline提示、Klein9B结果元数据、视觉验证和重试均为front_full；旧无`character-fullbody-0-90-180-v1`契约的45°资产加载时失效；新版生成与手动导入均写入该契约。场景和道具既有角度流程关联回归通过。
- LoRA边界：正式国风厚涂男女0°动态选择均只加载已批准风格LoRA`风格_古代幻想厚涂_FLUX2_Klein9B_仅测试.safetensors`，scale=0.9、SHA=`42253aaa6214aa6765f370189eb4b67fed90a5b947a9123f1cbfb2548d8a9007`；结果记录filename/scale/SHA。未批准女性/男性Klein9B人物LoRA均未加载。Schnell variant禁用LoRA；浅涂本地无批准可用权重时选择为空，不会加载未批准性别权重。
- 回归与构建：关联`95 passed, 3 subtests passed`；Vue TypeScript检查与Vite正式构建通过（82 modules，708ms）。
- 正式空闲：8787 healthy/langgraph，资源active为空、queue为空，Ollama模型0。
- 流转状态：待稽查

#### 最终稽查退回整改软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个文档阻断后立即停止，未启动重模型。
- 代码初检：load/resume assets区段不再调用`generateAllAssetImages`，只恢复pending并提示点击；图片中断恢复同样只持久化pending提示。confirmed storyboard且框架空时仍只调用一次`extractProductionAssets`，未发现图片模型调用。
- 失败项：现行规范之间仍存在人物第一张基准图的直接冲突。
- 冲突证据：`docs/specs/短剧从剧本到成片生产规范.md:46`规定第一张为Klein‑9B 0°正面全身，禁止45°基准；但`docs/specs/短剧3D资产生产规范.md:30-32,40,101`仍规定人物第一张为左45°全身基准、0°是后续图、正面近照不替代45°输入，并要求复用已确认左45°建模参考。
- 预期行为：所有现行生产规范必须统一为人物严格三槽0°/90°/180°；0°是唯一baseline，人工确认后生成90°/180°。45°只能出现在场景、道具或Blender审核角度中，不得作为人物输入基准或必需人物槽位。
- 实际行为：主生产规范与3D专项规范对人物baseline给出互斥要求，AI和开发按不同文档会分别生成0°或45°第一张。
- 下一状态：待处理
- 主线文档整改：`短剧3D资产生产规范.md`人物输入已统一为0°正面全身唯一baseline，人工确认后才生成90°/180°；TripoSR复用0°基准。人物槽位与纯2D回退均删除45°，45°仅保留在道具、场景和Blender输出审核视角。Dev_MainDev、项目记忆与项目进度同步标明M9.145旧角度已被M9.156覆盖。
- 整改状态：规范冲突整改完成，待软件测试复测。
- 最终稽查再次退回：正式3D请求仍发送`left_45_full`，可执行AI生产提示仍写人物左45°，后端人物3D缺少已确认0°输入硬门禁。
- 追加整改：前端人物3D固定发送`front_full`与`baseline_confirmed`，未确认时禁止提交；重新生成、修复或导入新基准会清除旧确认凭据。后端在环境/模型检查前拒绝人物缺图、未确认或非front_full输入，禁止回退自行生成人物参考图。AI生产提示严格改为0°→人工确认→90°→180°。新增请求契约、三类非法输入与运行提示静态/动态测试。
- 追加开发验证：3D、图片恢复与短剧规范关联`42 passed, 3 subtests passed`，未启动重模型；待软件测试复测。
- 用户追加人物第四格：在0°/90°/180°全身图后新增0°正面半身照；四图共同锁定人物，不把半身照孤立为单用途资产。半身照硬规范为正面平视、人物居中、腰部裁切、手部完全出画、头部至腰部约占画高75%、头顶微小留白、肩膀不触边、左右留白适中、纯色无杂物背景。
- 主线实现：人物卡片与完成门禁扩为四格，确认0°全身后按90°→180°→0°半身串行；半身走Qwen‑Edit独立`front_half`路由，跳过全身脚底归一化，视觉审核新增腰部裁切、手部出画、75%主体占高、肩部边距与两侧留白门禁。TripoSR仍只读取已确认0°全身图。
- 第四格首轮软件测试退回：人物卡虽显示四格，但`assetUploadComplete`仍只硬编码检查90°/180°，缺半身图会提前放行。
- 追加整改：人物上传/生成完成门禁改为复用`hasCompleteAssetVariants("character", item)`与`fixedAssetAngles.character.slice(1)`权威四格定义；半身图必须存在且为confirmed，缺失或未确认均禁止进入分镜画面等下游阶段。新增防旧两标签硬编码回归断言。
- 第四格最终稽查退回：四图虽完成生成与卡片门禁，但分镜参考映射仍把0°全身误标为`face_primary`，其余三图因旧精确标签判断全部成为`audit_only`并被后端排除，未实际共同锁定。
- 追加整改：分镜两条正式命令构建路径统一为0°半身=`face_primary`、0°全身=`clothing_body`、90°/180°=`angle_continuity`，不再产生人物`audit_only`。后端多参考生成明确四图共同约束单一人物，半身独占脸/妆发/近景表情口型，全身锁体型服装，侧背锁跨角度轮廓与服饰连续性；语义重复人物审核也按三类usage纳入四图。新增reference manifest与审核链测试。

#### 人物四图共同锁定主线收尾

- 主线整改完成：分镜两条正式命令构建路径均固定0°半身=`face_primary`、0°全身=`clothing_body`、90°/180°=`angle_continuity`；后端多参考提示禁止混合推导人脸，四图全部参与单一人物约束与语义一致性审核。
- 半身硬规范完成：0°正面平视、人物居中、头顶微小留白、腰部裁切、手部完全出画、头至腰约占画高75%、双肩不触边、左右留白适中、纯色无杂物；`front_half`生成和视觉验收均执行该契约。
- 3D边界保持：TripoSR只接收已人工确认的0°正面全身基准，0°半身与90°/180°不进入几何重建。
- 开发验证：关联回归`97 passed, 3 subtests passed`；后端Python编译、Vue TypeScript检查与Vite正式构建通过（82 modules，693ms）。未启动重模型。
- 流转状态：待独立软件测试。

#### 最终稽查退回整改第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 恢复门禁：项目加载在分镜已确认且框架为空时仅补提取框架；`resumeStages assets`与图片任务中断恢复均只置`pending`、持久化并提示用户点击继续，图片生成调用为0。
- 人物契约：人物资产严格只有0°正面全身baseline、90°侧面全身、180°背面全身；0°人工确认后才生成90°/180°。TripoSR复用已确认0°，纯2D回退同样只保留0°/90°/180°。
- 规范一致性：现行主生产规范和3D资产规范均无人物45°基准、人物45°输入或人物45°槽位；45°只保留于道具、场景及Blender审核视角。历史M9.145左45°口径已明确由M9.156覆盖。
- 回归证据：关联测试`50 passed, 3 subtests passed`；Vue TypeScript检查通过；Vite正式构建通过（82 modules，660ms）。
- 下一状态：待稽查

#### 最终稽查新增人物3D门禁软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 前端门禁：人物3D正式请求固定携带`reference_angle=front_full`、已确认0°基准URL及`baseline_confirmed=true`；0°未确认时不提交。重新生成、基准修复及导入新基准均清除旧确认并重新进入人工确认。
- 运行时规范：`AI_SHORT_DRAMA_PRODUCTION_SPEC.md`严格规定0°正面全身→人工确认→90°侧面→180°背面，不含人物左45°基准或左45°前置链。
- 后端前置拒绝：动态轻量验证人物缺`source_baseline_url`、`baseline_confirmed`非严格`true`、`reference_angle`非`front_full`三类请求均在环境与模型检查前返回精确`ValueError`，没有生成或回退调用。
- 回归证据：关联测试`56 passed, 3 subtests passed`，另有3项动态前置拒绝用例通过；Vue TypeScript检查通过；Vite正式构建通过（82 modules，667ms）。
- 下一状态：待稽查

#### 人物第四格追加需求软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个失败后立即停止，未启动重模型。
- 失败项：人物四格完成门禁未包含`0°正面半身`。
- 复现证据：`plugins/builtin/short_drama/frontend/App.vue`的`assetUploadComplete`对人物仅检查`90°侧面全身`与`180°背面全身`存在图片，未检查`0°正面半身`；因此0°全身baseline、90°和180°存在而半身缺失时仍返回完成，并可提前开放后续分镜图片阶段。
- 预期行为：人物完成必须同时满足已确认0°正面全身baseline，以及90°侧面全身、180°背面全身、0°正面半身三张后续图全部完成；缺任一格均不得判定资产完成。
- 同类测试缺口：现有新增测试只断言四格展示和三项variant，未对`assetUploadComplete`的四格完成门禁建立断言或动态用例。
- 下一状态：待处理

#### 人物第四格追加需求第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 四格与完成门禁：人物卡固定按0°正面全身baseline、90°侧面全身、180°背面全身、0°正面半身展示；首次仅生成baseline，人工确认后后三格按数组顺序串行。人物完成统一调用`hasCompleteAssetVariants("character", item)`，90°、180°、半身均须存在图片且状态为confirmed，缺失或未确认半身不会放行。
- 半身生成与审核：半身固定走Qwen `front_half`；服务端跳过全身脚底归一化。机器门禁强制正面平视、居中、完整头顶与微小留白、腰部裁切、手部出画、头至腰约75%画高、肩不触边、侧边留白、纯色无杂物，并保持身份、体型、服装和配饰一致。
- 项目隔离：90°请求晚到时在响应后命中project/session/controller门禁并停止，180°和半身均不继续；180°晚到同样在响应后停止，半身不继续。旧项目结果、状态和持久化不得污染新项目。
- 3D输入：人物3D请求仍只携带已确认0°正面全身baseline的`source_baseline_url`、`reference_angle=front_full`与严格`baseline_confirmed=true`；0°半身不进入TripoSR。
- 文档一致性：运行时AI规范、主生产规范与3D资产规范均统一四格顺序、半身构图和TripoSR仅用0°全身输入。
- 回归证据：关联测试`56 passed, 3 subtests passed`；Vue TypeScript检查通过；Vite正式构建通过（82 modules，646ms）。
- 下一状态：待稽查

#### 四图共同进入分镜链软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 两条正式命令：单镜生成与服务端批量命令均构造完整人物reference manifest；0°正面半身标记`face_primary`，0°正面全身标记`clothing_body`，90°/180°标记`angle_continuity`。
- 后端推理：`generation_resolved`仅排除`audit_only`，三类人物usage均实际进入多参考推理；提示词明确四图共同约束同一人物，严禁把角度参考复制成多人物、拼图或分栏。
- Face Lock与审核：Face Lock只从`face_primary`选择0°半身；语义一致性和重复人物专项审核同时纳入`face_primary`、`clothing_body`、`angle_continuity`三类人物参考。
- 原流程回归：四格顺序、baseline人工确认、后三格串行、四格完成门禁、半身Qwen `front_half`构图及视觉验收、90°/180°晚到隔离、TripoSR仅使用已确认0°全身、人物3D `front_full`确认门禁均保持有效。
- 回归证据：关联测试`57 passed, 3 subtests passed`；Python编译、Vue TypeScript检查及Vite正式构建通过（82 modules，697ms）。
- 下一状态：待稽查

#### 最终稽查关闭记录

- 稽查时间：2026-08-11。
- 结论：通过，BUG关闭。
- 四图执行证据：两条正式分镜manifest均为0°半身=`face_primary`、0°全身=`clothing_body`、90°/180°=`angle_continuity`；三类全部进入后端推理，Face Lock仅取半身，语义重复人物审核纳入四图。
- 回归证据：四格顺序与完成门禁、半身构图审核、项目晚到隔离、TripoSR仅使用已确认0°全身、3D front_full确认硬门禁及三份规范均通过。稽查复跑53项及3个子测试、Python编译通过；软件测试57项及3个子测试、类型检查和正式构建通过。
- 正式运行态：8787路径正确，资源active/queue为空，Ollama为空，ComfyUI未运行；旧离线worker条目不健康且不占资源，不影响本BUG关闭。

### BUG-20260811-005：正常合片仍由前端逐集循环旧接口

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.153
- 现象：图片与视频已由服务端阶段执行器编排，但正常成片仍在`mergeEpisodes`中逐集调用`mediaService.merge`，composition缺少服务端执行器，前端继续承担批处理职责。
- 主线整改：新增服务端`composition`阶段执行器，接收全剧可合片分集命令并统一调用合片能力；前端先同步视频/音频/字幕台账，再单次`runStage(composition)`，原子合并阶段结果。单集明确返修仍保留局部接口。
- 开发验证：轻量动态2集只形成一次服务端阶段调用并返回2项待确认成片；关联77项、Python编译、Vue类型检查与Vite构建通过。未启动重模型。

#### 第一轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个阻断后立即停止，未启动重模型。
- 失败项：composition请求返回前切换项目，旧项目结果会写入当前新项目状态。
- 动态复现：项目p1启动`mergeEpisodes()`并阻塞在`runStage(composition)`；切换到p2并加载其既有master后释放p1响应。正式结果处理没有项目ID/session复核，直接按episode替换`episodeMasters`，最终p2的master被p1返回项替换，`mergeStatus`也被写为waiting_confirmation。
- 出错模块：`plugins/builtin/short_drama/frontend/App.vue::mergeEpisodes`。
- 预期行为：同步台账后、提交composition前、响应返回后及每次持久化前均必须确认当前项目仍是启动项目；项目切换或controller abort后禁止替换master、状态、错误和新项目持久数据。
- 实际行为：入口捕获旧project后仅依赖AbortController；成功响应路径没有`activeProjectRecord/projectSession`双检。请求在切换竞态中仍返回时，旧结果会无条件覆盖当前响应式数组并调用`persistMergeState()`写入新项目。
- 同类风险：失败catch同样缺少项目上下文检查，旧项目异常可把新项目`mergeStatus`改为failed并写入旧错误；仅abort不足以保护已返回或不遵守signal的请求适配器。
- 下一状态：待处理

#### 第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；项目切换成功/异常/晚到响应隔离整改已复核有效，继续测试发现首个服务端阻断后立即停止，未启动重模型。
- 失败项：composition执行器未保证“每集只调用一次内部合片”。
- 动态复现：直接调用`_run_server_production_stage({stage:"composition", commands:[{episode:1,...},{episode:1,...}]})`并轻量替换`_local_api`。服务端接受重复episode，连续调用两次`/api/videos/merge`，返回两个episode=1结果项；`merge_calls=2`，预期最多1次或明确拒绝重复命令。
- 出错模块：`plugins/builtin/short_drama/backend/compat_server.py::_run_server_production_stage`的composition分支。
- 预期行为：commands非空、episode为正整数且在一次批次内唯一；重复episode必须在任何内部merge调用前整体拒绝，或确定性去重为单次调用，禁止重复生成同集成片。
- 实际行为：分支只逐项验证`int(episode)>=1`，没有批次级episode唯一性校验，按原数组逐项调用内部merge。
- 同类风险：重复命令会重复消耗合片资源、产生互相覆盖的同集结果，并破坏前端“按episode原子替换”的唯一键假设。
- 下一状态：待处理
- 追加整改：合片事务捕获`projectSession`，在台账同步后、提交前、响应后、替换后与持久化前执行project ID/session/abort三重围栏；失败分支同样只允许更新发起上下文。`persistMergeState`改为显式项目+session并在写入前复制数据快照，旧项目响应不得污染新项目。类型检查及77项回归通过。

#### 第二轮软件测试记录

- 测试结果：不通过；项目切换隔离有效，但发现批次集数可重复。
- 失败项：`commands=[episode1, episode1]`会调用两次内部合片并返回两个同集结果。
- 追加整改：composition在任何合片副作用发生前整批解析集数，强制每项为正整数且全批唯一；空批、非法集数或重复集数整体拒绝，禁止部分执行。相关专项50/50通过。

#### 第三轮软件测试与最终稽查

- 软件测试：96项及3个子测试通过；非法/重复集数零执行、媒体包异常409零执行、项目切换晚到响应隔离、批量与局部返修边界、类型检查和构建均通过。
- 最终稽查：通过。服务端整批门禁、逐镜媒体包权威校验、前端单次runStage、项目/session/abort围栏及持久快照完整。

#### 第三轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 命令整批校验：空commands、episode=0、非数字episode及重复episode全部在内部调用前拒绝，四类场景`merge_calls=0`；合法episode 1/2分别且仅调用一次内部`/api/videos/merge`，返回2项完整waiting_confirmation结果。
- 公开媒体包门禁：通过隔离公开`/api/production/run-stage`动态验证缺subtitle、未确认、audit batch不一致、确认后fingerprint篡改均返回409 `production_gate_blocked`，四类场景内部composition执行增量均为0。
- 项目切换隔离：p1请求阻塞后切换并加载p2，分别释放成功响应、异常响应、忽略signal的晚到响应及已abort响应；p2 masters/status/error均保持原值，持久快照仅含切换前p1 generating快照，无p2污染写入。
- 前端事务：正常批量先await台账同步，再单次`runStage(composition)`，直接`mediaService.merge`调用0；结果按episode原子替换。同步/服务失败保留既有master且不伪成功；重复点击仅提交1次；单集`mergeEpisode`保留唯一一次局部直调供明确返修使用。
- 回归与构建：关联回归`96 passed, 3 subtests passed`；Python编译、Vue TypeScript检查、Vite正式构建通过（82 modules，645ms）。
- 正式空闲：8787为healthy/langgraph，资源active为空、queue为空，Ollama模型0；ComfyUI未启动且无运行队列。
- 流转状态：待稽查


### BUG-20260811-004：分镜后的资产提取绕过LangGraph且未先确认分镜

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.152
- 现象：点击“生成图片”时，前端直接调用旧`/api/characters/extract`并自行编排资产阶段；按钮路径未先把分镜确认同步到生产台账。服务端没有`assets`阶段执行器，导致统一工作流在分镜后断开。
- 主线整改：服务端新增`assets`阶段执行器，统一返回人物、场景、道具及census；前端改为单次`runStage(assets)`。进入资产阶段时先自动确认分镜、持久化并同步台账，确认成功后才启动资产提取。
- 开发验证：动态轻量调用确认服务端正确转发全部提取上下文并返回三类资产；关联回归76项通过，Python编译与Vue类型检查通过。未启动重模型。

#### 第一轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个阻断后立即停止，未启动重模型。
- 失败项：分镜自动确认失败时仍会启动资产准备和`assets`阶段。
- 复现边界：`storyboardHasCompleteEpisode=true`、`storyboardStatus!=confirmed`、`narrativeAuditEnabled=true`且`narrativeAuditsPassed=false`。`enterAssetGeneration()`先`await confirmStoryboards()`；后者因审核未通过直接返回且状态仍非confirmed，但入口不检查返回值或确认状态，随后在资产档案为空时调用`prepareAssetProfilesFromStoryboard(project)`，该函数最终调用`extractProductionAssets("manual")`并提交`runStage(stage:"assets")`。
- 出错模块：`plugins/builtin/short_drama/frontend/App.vue::confirmStoryboards`、`enterAssetGeneration`、`prepareAssetProfilesFromStoryboard`。
- 预期行为：自动确认必须返回明确成功值；只有持久化成功、`await syncProductionLedger(project)`成功且状态已confirmed后才能准备或运行assets。确认失败、审核失败、持久化失败、台账同步失败均不得启动assets。
- 追加整改：`confirmStoryboards`改为显式布尔事务；审核、项目、持久化、台账同步或项目切换任一失败均返回false并恢复待确认。入口同时检查返回值与confirmed状态后才允许资产阶段。Vue类型检查、Vite构建及76项回归通过。
- 实际行为：`confirmStoryboards()`返回`void`，审核门禁失败也是无值返回；`enterAssetGeneration()`忽略结果并继续准备资产，因此确认失败边界可越过门禁。
- 同类风险：任何未抛异常的确认前置失败都会被当作可继续执行，重复点击时还可能在确认尚未形成权威状态前进入资产请求。
- 下一状态：待处理
- 第二轮追加整改：资产入口新增同项目single-flight Promise，覆盖确认、台账同步、资产准备和页面切换全过程；并发调用直接复用同一Promise，finally仅清理自身实例，项目切换后再次门禁。类型检查及76项回归通过。
- 最终稽查：通过。确认false/异常/项目切换均阻断assets；single-flight异常后可重试；服务端仅一次提取并完整返回四类结果。软件79项与3个子测试、稽查52/52通过，允许关闭。

#### 第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；首轮确认失败边界已修复，但发现并发重复点击阻断后立即停止，未启动重模型。
- 已通过项：`confirmStoryboards():Promise<boolean>`对审核/项目前置失败返回false；持久化或台账同步异常恢复`waiting_confirmation`并返回false；项目切换检查返回false；`enterAssetGeneration`仅在确认返回true且状态confirmed后继续。
- 失败用例：两次快速调用`enterAssetGeneration()`。第一次进入`confirmStoryboards()`后立即把`storyboardStatus`设为confirmed并阻塞于`await persistStoryboardState`；第二次调用看到confirmed，跳过确认，在资产档案仍为空时直接调用`prepareAssetProfilesFromStoryboard`。第一次完成同步后也调用同一prepare，最终触发两次`extractProductionAssets`/`runStage(assets)`。
- 动态复现：用与正式函数相同的异步顺序设置持久化闸门，两次并发进入后`prepareAssetsCalls=2`，预期为1。
- 出错模块：`plugins/builtin/short_drama/frontend/App.vue::enterAssetGeneration`与`confirmStoryboards`。
- 预期行为：资产入口必须有单飞门禁；确认、台账同步和资产准备作为一个互斥事务，同项目并发点击只允许一次prepare及一次`runStage(stage:"assets")`。
- 实际行为：确认开始时提前暴露confirmed状态，且入口没有共享in-flight Promise或布尔锁，第二次调用绕过确认并与第一次并行启动资产准备。
- 下一状态：待处理

#### 第三轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 服务端执行器：轻量动态执行`_run_server_production_stage(stage="assets")`，精确只调用一次`/api/characters/extract`，完整转发outline、scripts、extraction_phase、target_episodes、required_characters、style、max_characters及项目上下文，返回characters/scenes/props/census。
- 前端单入口：`extractProductionAssets`内`productionLedgerService.runStage`精确1次，旧`assetService.extractCharacters`调用0次；分镜确认严格按persist后await sync顺序执行，审核、项目、持久化、同步失败均返回false并阻断assets。
- 并发与恢复：原异步持久化闸门下两次并发入口返回同一Promise，prepareAssetsCalls=1、runStage=1；事务异常后锁释放，第二次重试成功；项目在确认期间切换时prepare=0、runStage=0；事务完成及异常后的锁均释放。
- 项目隔离：入口在prepare前后双检项目ID；项目切换统一abort包含assetController，旧项目结果不会进入新项目导航或状态。
- 回归与构建：直接关联回归`79 passed, 3 subtests passed`；Python编译、Vue TypeScript检查与Vite正式构建通过（82 modules，698ms）。
- 正式空闲：8787返回healthy/langgraph，资源active为空、queue为空，Ollama模型0。
- 流转状态：待稽查


### BUG-20260811-002：Blender源视频与H3身份重绘未接入短剧分镜视频

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.151
- 现象：Klein 9B、TripoSR、Blender及H3权重/节点虽已安装，但Blender只输出静态审核图，正式分镜视频仍固定走Wan2.2，未把3D源视频与2D定妆照交给H3 Ref2VA。
- 主线整改：Blender新增24FPS/96帧源视频；资产结果持久化`source_video_url`；前端按镜头匹配已确认3D资产和人物正面定妆照；后端双输入齐备时运行独立MiniMax H3 Ref2VA图，否则保留Wan2.2。H3 prompt ID、心跳、超时、定向停止、恢复/关闭回收和模型释放已接入统一视频任务生命周期。
- 测试退回整改：已在既有白瓷仙壶3D资产上执行真实Blender 5渲染，形成H.264 `blender_source.mp4`，实际解码1024×576、24FPS、96帧、4.0秒；同时修复Blender 5无FFMPEG图像格式、空World、Action API变化及修复后再次减面导致非流形边的兼容问题。候选result已写入`source_video_url/source_video_spec`，经确认进入hot归档；服务重启后任务、确认态和归档视频保持，URL编码后的媒体请求HTTP 200（172156字节）。

#### 第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动Blender、H3或其他真实重模型。
- 真实产物：独立读取`output/assets3d/m9145-smoke/prop/白瓷仙壶/blender_source.mp4`，文件172156字节；既有实际解码证据为1024×576、24FPS、96帧、4.0秒，hot归档同名视频存在。
- 正式恢复：LaunchAgent重启后的正式`/api/assets/3d/status?job_id=74625204-007a-4ae1-bfd4-cd15b82108af`返回job=`completed`、result=`completed`、asset_confirmation_status=`confirmed`；result持续包含同一`source_video_url`及24FPS/96帧/4秒规格。
- 媒体访问：对URL编码后的`source_video_url`执行正式HTTP GET，返回200、`video/mp4`、172156字节；`data/hot/projects/m9145-smoke/3d/props/白瓷仙壶/blender_source.mp4`持续存在。
- 接入证据：本机四项H3权重、ComfyUI `MiniMaxH3ReferenceToVideo`/`VHS_LoadVideoPath`节点、正式`video.shot.h3_ref2va`能力及双输入路由证据保持有效；首轮缺失的真实worker完成、确认持久化与重启读取证据已补齐。
- 流转状态：待稽查
- 最终稽查：通过。新任务`source_video_url/source_video_spec`、确认/磁盘重载/hot归档、H3双输入路由与任务生命周期均复核有效；只读补跑92项与3个子测试通过，允许关闭。

#### 第一轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个阻断后按规范立即停止，未启动Blender、H3或其他真实重模型。
- 失败项：缺少“Blender真实24FPS/96帧源视频生成、result写回、人工确认后持久化”的可验证产物和任务证据。
- 只读复现：在项目`output/`、`data/hot/`、`/Users/aoo/AI/Projects/ShortDramaPipeline`及本机任务临时目录搜索`blender_source.mp4`，结果为0；在正式`output/narrative-cache/character-image-jobs.json`检查全部`workflow=asset_3d`任务，现有completed/pending_confirmation及已确认任务的`result`均没有`source_video_url`；热归档内同样不存在源视频。
- 当前测试缺口：`tests/unit/test_h3_rv2v_bridge.py::test_blender_produces_real_h3_source_video`仅断言源码包含文件名、`bpy.ops.render.render(animation=True)`及`fps/frames`字符串，没有解码真实MP4、核验24FPS/96帧、验证result URL可访问，也没有执行确认前后持久化与重建恢复测试。源码和静态测试通过不能替代用户要求的真实产物证据。
- 预期整改：在隔离轻量3D夹具或已验收真实3D资产上完成一次Blender源视频产出；保留可读MP4及ffprobe的24FPS/96帧证据；任务pending_confirmation结果必须含可访问`source_video_url`；确认后热归档、任务result及服务重建查询继续保持同一URL/文件。补充动态回归后重新提交软件测试。
- 下一状态：待处理

#### 最终稽查退回整改复测记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；使用临时目录及monkeypatch轻量worker报告，未启动Klein、TripoSR、Blender或H3。
- 新任务结果：动态调用`_generate_asset_3d`，新任务直接返回`pending_confirmation`，同时持有`source_video_url`及worker报告原样的`source_video_spec`（24FPS、96帧、4秒、1024×576、geometry_camera_motion_only）。
- 确认与恢复：将候选写入隔离任务仓库后调用`_confirm_asset_3d_job`，result转为completed且URL/spec保持；清除内存引用并从磁盘重新加载后，job/result仍completed、asset_confirmation_status仍confirmed、URL/spec完全一致，hot归档视频存在。
- 流转状态：待稽查

### BUG-20260811-003：大纲已确认但LangGraph残留待确认导致剧本门禁阻断

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.151
- 现象：项目阶段与生产台账的大纲均已完成并确认，但LangGraph检查点残留`outline=pending_confirmation`及旧`script=failed`，点击生成剧本返回`production_gate_blocked`。
- 主线整改：批量台账同步后按11阶段顺序读取持久确认事实，连续阶段全部为completed且具备确认凭证时自动修复LangGraph投影；遇缺失或未确认阶段立即停止，禁止越级。阶段门禁按权威汇总范围判定：剧本/分镜有故事弧批次时以批次确认覆盖分集，台词行与镜头明细仅保留追踪和影响传播，不再要求重复人工确认。当前项目已恢复`requirements/outline/script=completed`，下一阶段为`storyboard`。
- 分镜失败追加整改：真实生产先复现默认预算在JSON第5173字符截断，扩大预算后又复现610秒无响应；最终改为Qwen3-VL-32B只输出512-token视觉导演方案，服务端按已确认剧本时间段确定性编译并执行15—23镜、2—9秒、连续时间轴、对白覆盖及去重硬校验。正式HTTP实测10.6秒返回20镜、0—60秒，资源与模型均释放。同步修复故事事实库把同集20镜误判为“第1集重复”的持久化门禁，当前项目已保存`waiting_confirmation`。前端错误优先显示服务端`message`，不再用通用错误码覆盖真实故障。
- 最终稽查整改：删除按比例容许漏词逻辑，任意1句剧本台词/旁白未被分镜承接即拒绝；新3D任务结果同时持久化worker报告的`source_video_spec`，禁止只保存URL。
- 软件复测追加整改：无“台词：”字段前缀的`角色：对白`行不再丢弃说话人；分镜必须同时匹配角色与正文，`苏璃：回来`不能由`云澜：回来`冒充覆盖。
- 最终稽查：通过。紧凑导演方案、确定性编译、15—23镜/2—9秒/连续时间轴/字段/去重/台词旁白零遗漏及说话人门禁均有效；StoryBible同集多镜归并安全，只读补跑92项与3个子测试通过，允许关闭。

#### 软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动真实长篇生成、72B审核或其他重模型。
- 分镜结果：正式项目持久结果精确20镜，镜号1—20，时间轴连续覆盖0.0—60.0秒，单镜2/3/4秒且全部满足2—9秒；已确认剧本提取的18条对白/旁白全部被镜头覆盖，`visual/action/dialogue`组合重复数0。
- 正式接口与恢复：正式`/api/projects/stage`读取storyboard为`waiting_confirmation`、20镜、空error；生产workflow为`waiting_human`且当前阶段storyboard，requirements/outline/script均completed，storyboard为pending_confirmation。服务重启读取保持一致。
- 门禁与并发：故事事实库按episode对同集多镜去重测试通过；stage batch与LangGraph按权威已确认批次恢复。隔离公开HTTP动态验证同一tenant/user/project/stage重复运行返回409 `production_gate_blocked`，未启动模型。
- 模型与生命周期：正式持久20镜结果完整，无截断；开发留存真实HTTP耗时10.6秒、200证据有效。复测结束正式`/health`为healthy/langgraph、资源active为空、queue为空，Ollama模型0，72B审核保持暂停。
- 前端与回归：服务端`message`优先于error/fallback的真实错误展示路径通过；直接关联回归`95 passed, 3 subtests passed`，Python编译、Vue TypeScript检查、Vite正式构建全部通过。
- 流转状态：待稽查

#### 最终稽查退回整改软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：不通过；发现首个阻断后立即停止，未启动任何重模型，资产3D动态夹具留待整改后同轮复测。
- 用例结果：单句对白遗漏拒绝、两句对白部分遗漏拒绝、旁白遗漏拒绝、完整对白与旁白覆盖接受均通过；说话人错配失败。
- 失败复现：剧本输入`苏璃：回来。`，分镜对白输入`云澜：回来。`，其余15镜、0—60秒及必填字段均有效；调用`_validate_storyboard(shots, 60, script)`未抛异常并错误接受。
- 出错模块：`plugins/builtin/short_drama/backend/compat_server.py::_script_dialogue_lines`与`_validate_storyboard`。
- 预期行为：对白覆盖必须同时匹配说话人与台词内容，`苏璃：回来。`不得由`云澜：回来。`满足。
- 实际行为：`_script_dialogue_lines`只保留冒号后的台词正文，`_validate_storyboard`再以正文子串检查拼接后的镜头对白；说话人身份被丢弃，因此错误说话人复述相同正文即可通过。
- 同类风险：同一句台词被任意角色、群演或旁白错配时均可能被当作完整覆盖，导致服务端确定性编译后的角色归属门禁失效。
- 下一状态：待处理

#### 最终稽查退回整改第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；未启动任何重模型。
- 动态边界：单句对白遗漏、两句对白部分遗漏、旁白遗漏、说话人错配均被`_validate_storyboard`拒绝；完整说话人、对白和旁白覆盖被接受，5/5通过。
- 解析证据：混合输入`苏璃：回来。`、`台词：云澜：住手。`、`旁白：风雨将至。`解析结果精确为`['苏璃回来', '云澜住手', '风雨将至']`；剧本苏璃、分镜云澜复述相同正文已拒绝。
- 关联回归：`95 passed, 3 subtests passed in 1.49s`；四份主线状态文档均记录新3D URL/spec持久化、台词/旁白零遗漏及说话人一致性门禁。
- 流转状态：待稽查

### BUG-20260811-001：视觉风格为空且生成大纲按钮无响应

- 状态：已关闭
- 关联任务：M9.150
- 现象：正式8787 LaunchAgent缺少项目`PYTHONPATH`，服务启动恢复失败，前端无法取得风格列表且大纲请求无响应；同时国风浅涂当前没有可选LoRA权重，旧实时扫描将已明确建档的视觉风格整个隐藏。
- 主线整改：LaunchAgent补齐绝对项目`PYTHONPATH`并重新加载；风格扫描允许存在`README.md`视觉规范的正式风格目录在可选LoRA库存为0时继续作为项目/提示词风格契约显示，未建档空目录仍隐藏；正式接口现返回国风厚涂与国风浅涂。Qwen3-VL-32B生成路由保持生效，72B文本审核按用户指令暂停。
- 追加交互：完整大纲处于待确认时，点击“生成剧本”自动执行大纲确认并立即启动剧本；不再要求单独点击确认。大纲不完整或失败时仍阻断，服务端LangGraph确认门禁不被绕过。
- 主线验证：正式8787健康、LangGraph与Qwen3-VL能力已注册；`/api/lora/styles`返回两项；关联单测97项与3个子测试通过。

#### 软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-11
- 测试结果：通过；关联回归`97 passed, 3 subtests passed in 2.93s`，Vue TypeScript检查与Vite正式构建通过，独立运行态与动态边界全部通过；未启动新的长篇任务或72B推理。
- 正式启动：LaunchAgent `com.local.ai.compat-server`处于running，程序与后端均为`/Users/aoo/Code/AI Agent`绝对路径，`PYTHONPATH`和WorkingDirectory均精确指向该项目；8787监听进程cwd正确，`/health`返回healthy、`orchestrator=langgraph`。
- 风格接口：正式`/api/lora/styles`精确返回`国风厚涂(model_count=5)`与`国风浅涂(model_count=0)`两项；隔离扫描验证带`README.md`建档但无权重的风格仍可选，未建档空目录隐藏。前端选择器绑定`newProjectGenre`，保存同时写入category/style，创建按钮与服务端创建/更新接口均拒绝未索引或空风格。
- 文本路由：正式当前项目`361598b4-1064-44ba-8b3f-f6ffa094b00a`的plan任务`03ef3f67-5154-46b0-b555-8928d557f304`与episodes任务`a0b2c383-a187-4116-a00f-191fc21a55d4`均为completed；运行期间只读观察到Ollama加载`qwen3-vl:32b`，完成后模型0、资源active为空、queue为空。轻量注入确认outline阶段`audit_enabled=false`时只调用plan/episodes，不调用audit，结果audit为空；72B能力保留但默认暂停，不进入三阶段生产请求。
- JSON兼容：Qwen3-VL正常`response`结构化JSON与`response`为空、JSON位于`thinking`两种返回均解析通过；模型请求精确使用`qwen3-vl:32b`并在结束后卸载。
- 大纲转剧本：`generateScriptsFromOutline`对完整待确认大纲先`await confirmOutline()`，确认成功后仅调用一次`generateScripts()`；缺失或集数不完整在确认前直接返回；确认返回false明确阻断，确认持久化/台账同步抛异常时无catch吞错且不会越过到剧本生成。
- 文档一致：`Dev_MainDev.md`、`docs/memory/项目记忆.md`和`docs/product/项目进度.md`均记录Qwen3-VL-32B正式路由、Qwen2.5 72B审核默认暂停、正式启动与两项视觉风格恢复，以及完整大纲自动确认后进入剧本、缺失/失败阻断。
- 流转状态：待稽查

#### 最终代码稽查关闭记录

- 稽查人：代码稽查
- 稽查时间：2026-08-11
- 稽查结果：通过。
- 文本链路：故事总纲、分集梗概、剧本及分镜正式请求均使用`qwen3-vl:32b`；Ollama标准`response`及`response`为空而结构化JSON位于`thinking`两种响应均可解析，任务结束执行模型卸载。`qwen2.5:72b`审核能力保留，但三阶段生产默认`audit_enabled=false`，暂停期间不调用审核或修正模型。
- 风格链路：正式接口同时返回国风厚涂与国风浅涂；有README视觉契约但零LoRA库存的浅涂保持可选，未建档空目录不暴露。前端选择值同时保存为`category/style`，创建、编辑及服务端写入口均校验当前索引，选择与持久化端到端一致。
- 启动链路：LaunchAgent程序、后端脚本、WorkingDirectory、日志路径与`PYTHONPATH`均为`/Users/aoo/Code/AI Agent`绝对路径；正式8787由该LaunchAgent运行且cwd正确。
- 交互与门禁：完整待确认大纲点击生成剧本时先等待`confirmOutline()`完成，再且仅再启动一次剧本阶段；大纲缺失或集数不完整、确认返回false、确认持久化或台账同步异常均不会清空既有剧本，也不会启动下游。确认仍通过生产台账同步及服务端LangGraph前序门禁，不存在前端越级完成。
- 生命周期与文档：正式统一非终态任务0，当前健康worker active=0、queue=0，资源队列为空，Ollama加载模型0；`Dev_MainDev.md`、项目记忆、项目进度及生产规范对Qwen3-VL路由、72B暂停、风格恢复和自动确认边界一致。
- 测试证据：软件测试`97 passed + 3 subtests`、Vue类型检查、Vite正式构建及动态边界证据有效；本次只读补跑直接关联回归`101 passed + 3 subtests`，失败0。
- 最终状态：已关闭。

### BUG-20260810-008：短剧三套编排与能力直连导致大纲到成片状态分裂

- 状态：已关闭
- 关联任务：M9.149
- 现象：旧JSON流水线、旧LangGraph流水线、兼容服务和前端批处理分别持有编排职责；模型、审核、存储、队列及媒体后处理存在直接绑定，阶段状态、停止恢复和人工确认无法形成单一事实链。
- 当前整改：已建立LangGraph SQLite唯一控制面、生产台账、故事事实库、统一任务仓库和资源调度；旧两套流水线改为统一内核兼容适配器；模型、审核、图片、视频、音频、3D、合片、字幕、超分、导出及基础设施进入可插拔注册表；视频包内配音/口型按视频阶段受控执行，完成后独立落盘音频与字幕证据，再开放合片。
- 开发验证：当前专项及关联测试91项与3个子测试通过；Python编译、Vue类型检查和Vite正式构建通过。
- 架构边界：前端仅保留当前人工触发阶段内的批次展示与请求提交，不持有跨阶段权威状态；所有请求由服务端LangGraph前置门禁，输出、确认、停止、恢复和推进以SQLite检查点及生产台账为准。分镜视频内部的配音、口型与字幕作为受管媒体包执行，完成后分别登记video/audio/subtitle证据，三阶段齐备后才开放composition。
- 开发完成验证：专项及关联测试91项与3个子测试通过；Python编译、Vue类型检查、Vite正式构建通过。正式8787为新内核且健康，25项生产能力、5项基础设施扩展已加载，统一任务0，Ollama模型0，ComfyUI运行/等待0。

#### 第一轮软件测试退回与整改

- 软件测试：53/54；发现公开`workflow/report`可直接伪造`subtitle=completed`，并在缺少video/audio/subtitle持久证据与确认时开放composition。
- 主线整改：`completed`状态强制校验前序阶段完成及持久人工确认；公开`workflow/report`禁止写completed；系统恢复仅允许受信任内部路径并按11阶段顺序重放已确认台账。composition额外从SQLite生产台账逐镜核验video/audio/subtitle三类scope集合完全一致、生命周期completed、confirmation存在、内容指纹和审核批次非空。
- 整改验证：专项及关联测试92项与3个子测试通过；新增伪造subtitle完成、越级composition及空确认拒绝用例。正式8787已重启到整改版本。

#### 并发与负载均衡增量

- 用户追加：统一生产内核必须覆盖负载均衡和高并发，且实现、规范、规划、进度和记忆同步更新。
- 开发范围：API无状态、多实例工作节点、能力/资源池路由、服务端幂等、任务世代、原子所有权租约、心跳续租、租约过期重排、晚到结果CAS、租户/项目/资源池背压；本机仍保持单重负载和35GB保留内存。
- 当前实现：新增健康感知工作节点路由和SQLite原子任务租约扩展；24处重负载入口统一执行资源匹配、节点选择、世代租约、10秒续租、本机优先级队列和精确释放；管理接口返回节点健康及资源快照。SQLite仅为本机提供方，横向正式部署通过同一扩展协议替换PostgreSQL/Redis。
- 并发开发验证：租约冲突、过期接管、世代递增、旧所有者续租/释放拒绝、按资源/容量/内存选路、心跳失效和背压用例通过。

#### 第二轮软件测试退回与整改

- 软件测试：54/55；同一镜头video/audio/subtitle虽来自不同指纹和审核批次，旧门禁仅比较scope集合而错误开放composition。
- 主线整改：前端为每个镜头计算唯一媒体包审核批次并由video/audio/subtitle三类记录共同引用；服务端从SQLite台账逐镜验证三类scope、completed、confirmation、确认时指纹、确认时审核批次及跨阶段媒体包批次完全一致，任一不符即阻断。
- 整改验证：专项及关联回归96项与3个子测试通过；新增正确媒体包、不匹配批次、确认后篡改指纹、并发抢租约、过期接管、节点路由和背压用例；Vue类型检查与Vite正式构建通过。

#### 第三轮软件测试退回与整改

- 软件测试：34/35；路由器虽能选出远端节点，但资源申请直接抛错，没有共享发现和远端投递数据面。
- 主线整改：新增SQLite共享工作节点发现扩展，节点心跳持久化服务地址、资源、容量、内存、队列和世代；API请求边界按资源类型选节点，远端命令保持原路径与body转发，携带`X-Production-Dispatched`防循环标头，响应披露实际执行节点；目标节点再取得执行租约并进入本机资源队列。远端不可达返回503且不错误本地执行。
- 同类整改：服务关闭先设置shutdown gate，任务失败化只更新权威存储，不再触发全局导演或122B审核模型。
- 开发验证：专项及关联回归98项与3个子测试通过；共享注册表跨实例可见、真实HTTP远端转发及防循环测试通过。两个隔离实例8788/8789均看到cluster-a/cluster-b；向8789提交命令实际由8788处理并返回`_dispatch.worker_id=cluster-a`。未启动重模型。

#### 第一轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目`.venv` Python；隔离SQLite控制面；未启动真实重模型。
- 测试范围：11阶段LangGraph依赖门禁、人工确认、媒体包video/audio/subtitle证据门禁、SQLite检查点、生产台账、故事库、统一任务仓库、能力与基础设施注册表、旧流水线委托及直接关联测试。
- 用例总数：54
- 通过数：53
- 失败数：1
- 通过证据：`.venv/bin/python -m pytest -q tests/unit/test_production_control.py tests/unit/test_short_drama_text_pipeline.py tests/unit/test_short_drama_media_pipeline.py tests/unit/test_short_drama_delivery_pipeline.py tests/integration/test_short_drama_pipeline.py tests/integration/test_langgraph_orchestrator.py tests/integration/test_task_tracking.py`返回`53 passed in 3.09s`。
- 失败用例：LangGraph状态报告允许无前置确认地越级完成任意阶段，composition只检查subtitle状态，不校验持久化video/audio/subtitle媒体证据。
- 复现步骤：创建空白`ProductionOrchestrator`；直接调用`report(identity, "subtitle", "completed", evidence={})`；随后调用`begin(identity, "composition")`。
- 原始结果：空白项目接受`subtitle=completed`，状态仅含`{"subtitle":"completed"}`；`begin composition`继续成功并写入`composition=running`。video与audio均未执行、未确认，subtitle evidence为空，仍开放合片。
- 出错模块：`plugins/builtin/short_drama/workflows/production_orchestrator.py`的`report()`与`begin()`；兼容接口`/api/production/workflow/report`直接暴露同一越级写入口。
- 入参：`stage="subtitle"`、`lifecycle="completed"`、`evidence={}`，此前全部阶段为空。
- 预期行为：阶段写入`completed`必须验证前一阶段已完成及当前阶段存在人工确认；subtitle完成必须存在真实字幕证据，composition开放前必须从持久控制面确认video、audio、subtitle三类证据分别齐备并已人工确认。
- 实际行为：`report()`不检查前序阶段、人工确认或证据；`begin()`只检查紧邻的subtitle状态，因此可伪造一个空subtitle完成记录绕过大纲至成片全部门禁。
- 根因及同类风险：权威写入口只在`execute()`与`begin()`检查前置依赖，`report()`可任意写阶段生命周期；所有11阶段均可通过该入口越级完成。媒体包没有独立持久证据结构门禁，composition对video/audio/subtitle的要求仅存在于合片函数传入body的临时字段，不是SQLite权威事实。
- 测试结果：不通过
- 下一状态：待处理

#### 第二轮软件测试复测记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目`.venv` Python；隔离LangGraph与生产台账SQLite；未启动真实重模型。
- 测试范围：completed前序与持久确认门禁、公开workflow report、composition逐镜video/audio/subtitle证据、确认记录顺序恢复及直接关联回归。
- 用例总数：55
- 通过数：54
- 失败数：1
- 通过证据：专项及关联测试返回`54 passed in 3.29s`；空白项目越级`report(subtitle, completed)`已被前序门禁拒绝；completed缺少持久confirmation已被拒绝；公开`/api/production/workflow/report`写completed路径返回409；系统恢复按规范阶段顺序只重放带confirmation的completed记录。
- 失败用例：composition媒体包只比较video/audio/subtitle的shot scope ID集合，未逐镜比对三类记录的`content_fingerprint`和`audit_batch_id`是否属于同一媒体包。
- 复现步骤：隔离生产台账依次写入并确认requirements之后至image的前置阶段；对shot 1分别写入并确认`video(VIDEO-FP, VIDEO-BATCH)`、`audio(UNRELATED-AUDIO-FP, OTHER-AUDIO-BATCH)`、`subtitle(UNRELATED-SUB-FP, OTHER-SUB-BATCH)`；调用`_begin_production_request(identity, "composition")`。
- 原始结果：三个阶段scope集合均为`{"1"}`且各字段非空，composition成功进入`running`；完全不相关的音频、字幕证据被当作同一镜头媒体包接受。
- 出错模块：`plugins/builtin/short_drama/backend/compat_server.py`的composition门禁。当前集合推导只保留`scope_id`，`content_fingerprint`与`audit_batch_id`仅做非空过滤，随后被丢弃，未执行逐镜跨阶段一致性比较。
- 入参：同一`scope_type=shot, scope_id=1`，三阶段均completed且有confirmation，但fingerprint与audit batch分别不同。
- 预期行为：每个shot必须建立video/audio/subtitle三元证据；三者除scope一致、completed和confirmation外，还必须按媒体包关联规则校验`content_fingerprint`与`audit_batch_id`一致或具有可验证的父子关联，任一不匹配必须阻断composition。
- 实际行为：只要三类shot ID集合相同且字段各自非空即可通过，无法证明音频、字幕对应当前视频版本。
- 根因及同类风险：composition门禁将完整台账记录降维成scope集合，丢失版本和审核批次关系；旧视频搭配新音频、其他版本字幕或跨批次证据均可绕过。当前测试只覆盖字段存在与scope集合，未覆盖值不一致。
- 测试结果：不通过
- 下一状态：待处理

#### 第三轮软件测试记录（媒体包整改＋负载均衡/高并发增量）

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；隔离服务`127.0.0.1:8788`；隔离输出`/tmp/short-drama-m9149-service`；worker=`m9149-smoke-worker`；未启动真实重模型；未访问、停止或重启正式8787用户任务。
- 测试范围：composition同一媒体包绑定、WorkloadRouter资源/容量/内存/心跳/背压、TaskLease唯一租约/续租/过期接管/世代围栏、24处重负载入口、7项基础设施扩展、workers API、可配置多实例及直接关联回归。
- 用例总数：35
- 通过数：34
- 失败数：1
- 通过证据：`.venv/bin/python -m pytest -q tests/unit/test_production_control.py`返回`34 passed in 0.43s`。隔离8788的`/api/production/workers`返回唯一健康worker `m9149-smoke-worker`、capacity 1、active 0、queue 0及资源快照；`/api/production/capabilities`返回25项启用能力、7项启用扩展及worker快照。源码中24个重负载调用点进入统一`_claim_production_resource`。
- 失败用例：WorkloadRouter选中远端健康worker后，正式资源申请路径直接抛出`RuntimeError`，没有远端任务提交、共享队列入队、转发或可恢复调度。
- 复现步骤：隔离加载兼容服务；在同一scope登记唯一符合image资源与内存要求的`remote-worker`，让local worker内存不足；调用`_claim_production_resource("image", "job-remote", estimated_memory=1024)`。
- 原始报错：`RuntimeError: workload routed to remote worker remote-worker`。
- 出错模块：`plugins/builtin/short_drama/backend/compat_server.py::_claim_production_resource`、`platform/core/workload_router.py`及worker发现链路。
- 预期行为：选中远端worker后任务必须通过共享任务仓库/远端worker接口可靠投递，携带job ID、租约世代和资源类别；调用端获得排队/接收状态，远端执行并以世代CAS回写。多实例worker心跳必须进入共享发现存储，其他实例可见。
- 实际行为：每个服务实例仅向进程内`WORKLOAD_ROUTER`登记自身心跳；workers API仅只读本进程快照；无远端注册、共享发现或任务投递接口。即使测试注入远端worker并被正确选中，集成层仍立即报错拒绝任务。
- 根因及同类风险：当前实现具备路由算法与SQLite租约原语，但没有跨实例发现和执行数据面，属于“能选远端、不能把任务交给远端”。新增host/port只能启动多个互相不可见的独立实例，无法形成负载均衡；24类重负载入口选中远端时均会同类失败。
- 正式服务只读验收：用户任务自然结束并由主线安全切换后补验；8787返回`healthy`、`orchestrator=langgraph`、25项启用能力、7项启用扩展，worker `local-production-8787`健康且active/queue均为0；统一非终态任务0；Ollama模型0；ComfyUI运行/等待0。未启动模型、未停止任务、未重启或干预服务。该运行态通过不消除跨实例远端投递阻断。
- 测试结果：不通过
- 下一状态：待处理

#### 第四轮软件测试记录（共享发现与远端投递整改）

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；隔离轻量双实例`127.0.0.1:8788/8789`；共享SQLite WorkerRegistry；未启动真实重模型。
- 测试结果：不通过；发现首个失败后按规范立即停止其余测试。
- 已通过证据：专项及直接关联回归`60 passed in 4.00s`；8788与8789均返回`healthy/langgraph`并共同发现`cluster-a@8788`、`cluster-b@8789`两个健康节点；25项能力、8项基础设施扩展均启用。向8789提交`POST /api/exports/create`，请求由`cluster-a@8788`处理，409业务门禁响应明确携带`_dispatch.worker_id=cluster-a`与endpoint；携带`X-Production-Dispatched: 1`直接请求8789时响应不含`_dispatch`，循环防护通过。
- 失败用例：远端节点不可达没有统一返回HTTP 503。
- 复现步骤：隔离加载`compat_server.py`，在独立`WorkloadRouter`登记唯一`control`远端节点`dead`，endpoint=`http://127.0.0.1:1`；调用`_forward_production_request('/api/exports/create', {'project_id':'p'}, False)`。
- 原始结果：返回`(502, {'_dispatch': {'worker_id':'dead','endpoint':'http://127.0.0.1:1'}})`；进入公开Handler后会原样对客户端返回502。预期远端连接失败、代理502或无有效远端JSON均统一映射为`503 workload_dispatch_failed`，且不得回退本机执行。
- 出错模块：`plugins/builtin/short_drama/backend/compat_server.py::_forward_production_request()`。该函数仅把`URLError/OSError`交由外层映射503，却把连接路径产生的`HTTPError 502`当作远端业务响应原样透传；本机网络代理/转发层对不可达地址返回502时违反“远端不可达503”契约。
- 同类风险：远端网关502、无效响应体及其他传输层5xx会被误当成目标业务状态；调用端无法稳定区分生产门禁失败与调度基础设施不可用。需只保留目标节点明确业务响应的状态码，对连接/代理/网关失败统一503并补公开Handler动态用例。
- 下一状态：待处理

#### 第五轮软件测试复测记录（远端网关状态归一化）

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；隔离轻量公开Handler、轻量远端HTTP节点、临时SQLite WorkerRegistry；正式8787只读验收；未启动真实重模型。
- 测试结果：通过；共84项，仓库自动化61项、独立动态断言16项、正式运行态断言7项，失败0项。
- 自动化证据：`.venv/bin/python -m pytest -q tests/unit/test_production_control.py tests/unit/test_short_drama_text_pipeline.py tests/unit/test_short_drama_media_pipeline.py tests/unit/test_short_drama_delivery_pipeline.py tests/integration/test_short_drama_pipeline.py tests/integration/test_langgraph_orchestrator.py tests/integration/test_task_tracking.py`返回`61 passed in 4.37s`。覆盖远端转发、502归一化、共享发现、防循环、WorkloadRouter资源/容量/内存/心跳/背压、TaskLease并发唯一/续租/过期接管/世代围栏、composition同一媒体包指纹和审核批次、11阶段人工确认、停止恢复及关联流程。
- 公开Handler动态证据：真实轻量远端分别返回HTTP 502、503、504，经公开`/api/exports/create`均严格归一为HTTP 503、`error=workload_dispatch_failed`并保留准确`_dispatch.worker_id/endpoint`；远端业务409保持HTTP 409及原错误体并附执行节点证据；携带`X-Production-Dispatched: 1`时不再次转发且响应无`_dispatch`。未出现不可达后回退本机执行。
- 共享发现与关闭门禁：两个独立`WorkerRegistry`实例通过同一SQLite立即发现相同endpoint节点；设置`SERVICE_SHUTTING_DOWN`后执行持久任务同步，注入的生产编排器调用计数为0，未触发全局导演或122B审核。
- 正式服务证据：8787健康；25项生产能力与8项基础设施扩展已加载；至少一个正式worker健康且active=0、queue=0；Ollama模型0；ComfyUI运行0、等待0。
- 流转状态：待稽查

#### 最终稽查残留整改软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试结果：不通过；发现首个文档一致性失败后按规范立即退回。
- 已通过项：相关仓库回归`102 passed, 3 subtests passed in 7.75s`；隔离waiting_human取消后返回cancelled，重建`ShortDramaPipeline`并load仍为cancelled，LangGraph status及requirements阶段均为cancelled；手工把JSON checkpoint篡改成`status=completed,next_index=11`后load仍投影为graph的`cancelled,next_index=0`；取消后approve、resume、orchestrator begin及execute全部拒绝；runner调用仍仅requirements一次，artifact文件集合未新增。Vue TypeScript检查通过，Vite正式构建通过；正式8787 cwd正确、healthy/langgraph、25能力、8扩展、无活动资源，Ollama与ComfyUI空闲。
- 失败项：`docs/memory/项目记忆.md`顶部M9.149摘要仍是上一轮“最终稽查退回整改完成，待复测”，只记录原子确认、JSON投影、双重租约与五入口单次提交，没有记录本轮“兼容流水线取消写入LangGraph、重启后保持cancelled、approve/resume/begin/execute均拒绝”的残留整改；同一文件底部“当前主线”、`Dev_MainDev.md`和`docs/product/项目进度.md`已记录该取消持久化整改，四处口径不一致。
- 预期：项目记忆顶部、项目记忆当前主线、Dev_MainDev与项目进度对M9.149的阶段名称、待复测状态和本轮取消持久化边界保持一致，且不保留上一轮摘要作为当前顶部状态。
- 下一状态：待处理

#### 文档一致性整改软件测试复测

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试结果：通过。
- 文档证据：`docs/memory/项目记忆.md`顶部M9.149、同文件“当前主线”、`Dev_MainDev.md`及`docs/product/项目进度.md`均明确LangGraph权威取消、重启后保持cancelled/取消持久化，以及不可批准、恢复或继续执行；阶段均为最终稽查残留整改完成待复测，未保留第三轮旧状态。
- 功能证据复核：取消持久化与LangGraph相关专项重跑`48 passed in 2.68s`；此前完整关联回归`102 passed, 3 subtests passed`、独立取消注入、类型检查、正式构建及正式服务空闲证据继续有效。此次仅文档变更，未启动真实重模型。

#### 最终稽查关闭记录

- 稽查时间：2026-08-10
- 稽查结果：通过。
- 单一事实源：兼容流水线取消会写入LangGraph；重建实例及重新加载后仍为`cancelled`，手工篡改JSON的`status/next_index`不能覆盖图状态；取消后的`approve/resume/begin/execute`均被拒绝，不会新增runner调用或artifact。旧JSON仅保存展示投影，阶段执行、恢复和推进继续只认LangGraph的`current_stage/next_stage/status`。
- 历次阻断回归：公开scope、asset、episode-batch确认均先做LangGraph完成校验再写生产台账，图提交异常具备确认回滚；生产资源在物理执行前及结果提交前均复核owner与generation；composition继续逐镜要求video/audio/subtitle属于同一已确认媒体包；五个前端生产入口各仅提交一次`runStage`，批处理、重试与终审仍由服务端阶段执行器负责。
- 架构边界：11阶段LangGraph门禁、25项生产能力、8项基础设施扩展、24处重负载路由与租约、共享WorkerRegistry、远端HTTP转发、防循环及502/503/504归一为503、业务4xx透传、shutdown不触发导演或模型均无回归；四处M9.149文档对LangGraph权威取消及待复测口径一致。
- 测试证据：软件测试专项`48/48`、完整关联回归`102 passed + 3 subtests`及此前`139`项证据有效；本次只读补跑取消/生产控制直接关联测试`44/44`通过（使用项目`PYTHONPATH=.`环境）。
- 正式运行态：8787由PID 69525监听，命令与cwd均位于`/Users/aoo/Code/AI Agent`；健康检查通过，正式健康worker active=0、queue=0，资源队列为空；Ollama已加载模型0；ComfyUI未运行且无活动队列。
- 最终状态：已关闭。
- 流转状态：待稽查

#### 最终整改代码稽查复核

- 稽查人：代码稽查
- 稽查时间：2026-08-10
- 稽查结果：不通过，继续退回主线开发。
- 已通过整改：三类公开确认均进入`_confirm_production_scope()`，执行LangGraph完成先验后写台账，graph提交异常会将当前scope补偿回`pending_confirmation`；`_claim_production_resource()`已在物理执行前和yield返回后的结果提交前双检租约owner+generation；五个指定前端生成入口均只提交一次`runStage`，拆批、有限重试、终审、图片修复和视频媒体包由服务端阶段执行器接管；composition、能力/扩展、24处资源申请、共享发现、远端转发、防循环、503归一化、shutdown门禁均保持有效。
- 残留阻断1（兼容流水线取消仍非图权威）：`ShortDramaPipeline.cancel()`只取消旧队列并把JSON checkpoint写为`cancelled`，未向`ProductionOrchestrator`报告`cancelled`。随后`load()`按LangGraph状态重新投影，立即把取消结果恢复为`waiting_human`。只读动态探针稳定复现：`cancel_return=cancelled`，重新加载为`waiting_human`，图状态仍为`waiting_human`。因此JSON status仍短暂产生与图冲突的控制事实，取消不能跨重启保持，违反“执行/恢复/推进只认LangGraph current/status/next_stage”。现有139项软件测试未覆盖取消后重启恢复。
- 残留阻断2（文档未完整同步）：`docs/memory/项目记忆.md`顶部已写“最终稽查退回整改完成”，但同文件“当前主线”仍写“M9.149第三轮测试退回项已整改，待独立复测”，与实际第五轮软件测试待稽查状态及`Dev_MainDev.md`、项目进度不一致。
- 整改标准：兼容流水线cancel必须先/同时由LangGraph权威写入cancelled，JSON只保存图投影；补充cancel→load/restart仍cancelled、取消后禁止approve/resume/execute的动态测试。统一更新项目记忆当前主线状态，消除旧轮次口径。
- 复核证据：只读复跑关联仓库64/64通过；正式8787当前PID 69525且cwd为`/Users/aoo/Code/AI Agent`，健康接口正常，能力25、扩展8，健康worker active=0/queue=0，Ollama模型0，ComfyUI运行/等待0。
- 最终状态：待处理

#### 最终稽查残留整改

- 兼容流水线`cancel()`先将当前阶段以`cancelled`写入LangGraph，再取消旧队列并把JSON保存为图投影；重新实例化后仍恢复`cancelled`。
- `ProductionOrchestrator.begin/execute`对已取消流程统一拒绝；兼容层`approve/resume`同样禁止继续。
- 项目记忆“当前主线”已更新为本轮最终稽查残留整改状态，删除第三轮旧口径。
- 主线验证：取消→重启恢复、取消后approve/resume/execute拒绝专项44/44通过；相关完整回归102项与3个子测试通过。
- 当前状态：待软件测试复测。

#### 第四轮软件测试退回整改

- 主线整改：远端`HTTP 502/503/504`网关与代理失败统一规范化为`HTTP 503 workload_dispatch_failed`，保留目标worker和endpoint证据，不回退本机；远端明确业务4xx继续原样透传。
- 开发验证：新增真实轻量502远端动态用例；专项及关联回归99项与3个子测试通过。公开Handler继续将`_forward_production_request`返回状态原样写出，因此调度不可用稳定为503。

#### 最终代码稽查

- 稽查人：代码稽查
- 稽查时间：2026-08-10
- 稽查结果：不通过，退回主线开发。
- 已通过项：25项生产能力与8项基础设施扩展均可查询；24处重负载入口已进入共享资源申请；WorkerRegistry共享发现、远端HTTP转发、防循环标头、502/503/504归一为503及业务4xx透传已接入；composition逐镜校验video/audio/subtitle的completed、confirmation、确认时指纹及同一审核批次；shutdown gate阻止持久任务同步触发导演或模型。只读复跑关联仓库61/61通过；正式8787健康，当前PID 64974且cwd为`/Users/aoo/Code/AI Agent`，能力25、扩展8、健康worker active=0/queue=0，Ollama模型0，ComfyUI运行/等待0。
- 阻断问题1（权威状态非原子）：公开`/api/production/scopes/confirm`先执行`PRODUCTION_LEDGER.confirm()`把台账写成completed，再调用LangGraph `report(... completed)`校验前序阶段。越级确认时LangGraph拒绝，但台账已永久完成，形成SQLite生产台账与LangGraph检查点分裂。只读隔离探针确认：空图确认outline后，LangGraph报`previous stage is not completed: requirements`，但ledger仍为`completed`且graph stages为空。现有测试只直接测试orchestrator门禁，未覆盖公开确认接口的写入顺序和回滚。
- 阻断问题2（仍有第二套编排事实）：`workflows/pipeline.py::ShortDramaPipeline`继续以`PipelineCheckpoint.next_index`、本地JSON checkpoint、`NODES`索引和`for range(next_index, len(NODES))`决定当前/下一阶段、等待人工、恢复、完成与失败；LangGraph仅被逐次调用。该JSON checkpoint仍是可驱动生产的独立控制状态，违反“LangGraph唯一服务端编排器、JSON仅兼容投影不得覆盖权威状态”。现有集成测试明确从该JSON的`next_index/status`恢复并继续推进，证明其不是只读投影。
- 阻断问题3（租约晚到结果未围栏）：`_claim_production_resource()`只在进入物理执行前校验`renewal_failed/owns`，`yield ticket`返回后直接进入finally释放租约，未在物理执行结束、结果提交前再次校验世代所有权。长任务执行期间续租失败或租约被新世代接管时，旧执行者仍可正常离开上下文并提交晚到结果；TaskLeaseRepository原语虽拒绝旧世代续租/释放，但调用层缺少提交前CAS门禁。现有测试覆盖租约原语和进入前校验，未覆盖执行中失租后的结果拒绝。
- 阻断问题4（前端仍承担生产编排）：`App.vue`中的`generateOutline/generateScripts/generateStoryboards/generateAllAssetImages/generateShotImages/generateShotVideos`仍由前端循环拆批、按顺序调用生产能力、发起终审并决定阶段内重试与继续；这超出“前端只提交命令、显示状态和执行人工确认”的规范边界。现有测试未设置“前端不存在生产编排循环”门禁。
- 整改标准：确认接口必须在同一事务/补偿边界内先通过LangGraph前序门禁再提交台账与检查点，任一失败不得留下单边completed；`ShortDramaPipeline`兼容层只读取LangGraph权威current/next/status，移除可驱动推进的JSON next_index状态；资源上下文在yield返回后、提交结果前再次验证租约owner+generation，失租必须抛错并禁止结果写入；阶段拆批、重试、终审和推进移入服务端LangGraph节点，前端只提交单次阶段命令并轮询权威状态。补充四类动态异常测试后重新经过软件测试与稽查。
- 最终状态：最终稽查退回整改完成，待软件测试复测

#### 最终稽查退回整改

- 权威确认原子化：公开scope、资产和分集批次确认统一先由LangGraph校验前序与人工确认，再写生产台账；图状态提交异常时台账回滚为`pending_confirmation`。
- 单一编排事实：旧`ShortDramaPipeline`只执行LangGraph返回的`next_stage`；JSON checkpoint的`status/next_index`仅由图状态派生用于兼容展示，不再驱动循环、恢复或推进。
- 晚到结果围栏：全部重负载上下文在执行前和退出提交前分别复核任务owner与generation；执行中失租直接拒绝旧结果。
- 前端退出生产编排：大纲、剧本、分镜、分镜图片和分镜视频入口均只提交一次`/api/production/run-stage`命令；服务端统一负责拆批、顺序、有限重试、终审、图片修复和视频媒体包生成。前端只显示、停止和人工确认。
- 主线验证：相关Python回归`102 passed, 3 subtests passed`；Vue类型检查和Vite正式构建通过；新增原子确认、LangGraph唯一推进、提交前租约复核、五个前端入口无生产循环测试。
- 下一状态：待软件测试复测。

#### 最终稽查退回整改软件测试复测

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试结果：通过；共139项，关联仓库回归102项、独立动态断言21项、类型检查与正式构建2项、正式运行态断言14项，失败0项；另在主线最新`pipeline.load`投影调整后重跑相关专项48/48通过，该48项与102项重合，未重复计数。
- 原子确认：隔离越级确认outline被LangGraph前序门禁拒绝，ledger保持`pending_confirmation`且confirmation为空，graph stages为空；注入graph提交异常后ledger同样补偿回滚为pending、graph未产生outline单边状态。公开scope、asset、episode-batch三个确认入口均统一调用`_confirm_production_scope`。
- 单一编排事实：`ShortDramaPipeline.load/_run/approve/resume`只从LangGraph state的status、current_stage与next_stage投影和推进；JSON checkpoint的status/next_index未再用于选择节点、循环或恢复推进。最新相关专项`48 passed in 3.00s`。
- 租约提交围栏：隔离注入执行前`owns=True`、yield返回后`owns=False`，上下文严格抛出`task ownership lease lost before result commit`，晚到结果未被接受；并发唯一、续租、过期接管、世代及旧owner拒绝回归通过。
- 前后端职责：`generateOutline`、`generateScripts`、`generateStoryboards`、`generateShotImages`、`generateShotVideos`五个正式入口各仅出现一次`productionLedgerService.runStage`，入口内无`for/while`生产循环；服务端`_run_server_production_stage`接管outline/script/storyboard/image/video拆批、有限修复、终审与视频媒体包生成。
- 关联回归：`.venv/bin/python -m pytest -q tests/unit/test_production_control.py tests/unit/test_short_drama_text_pipeline.py tests/unit/test_short_drama_media_pipeline.py tests/unit/test_short_drama_delivery_pipeline.py tests/unit/test_image_job_recovery.py tests/unit/test_image_task_runtime.py tests/unit/test_short_drama_spec_validation.py tests/unit/test_asset_category_image_totals_frontend.py tests/integration/test_short_drama_pipeline.py tests/integration/test_langgraph_orchestrator.py tests/integration/test_task_tracking.py`返回`102 passed, 3 subtests passed in 6.96s`；覆盖共享发现、远端转发与503、防循环、三元媒体包、shutdown门禁和资产关联回归。
- 前端验证：Vue TypeScript检查通过；Vite 7.2.2正式构建通过，82 modules transformed，产物成功生成。
- 正式服务：8787监听PID 69525，cwd严格为`/Users/aoo/Code/AI Agent`；`/health`返回healthy、`orchestrator=langgraph`、25项能力、资源active为空且queue为空；生产接口返回25项能力、8项扩展及健康worker active=0/queue=0；Ollama模型0，ComfyUI运行0、等待0。未启动真实重模型。
- 流转状态：待稽查

### BUG-20260810-005：TripoSR已下载但未接入短剧3D生产链

- 状态：已关闭
- 关联任务：M9.145
- 现象：TripoSR只有权重，没有Klein 9B参考图、受管重建任务、Blender清理渲染、前端入口、空间锚规范及2D/3D身份边界，无法进入短剧资产与分镜生产。
- 修复：接入`FLUX.2 Klein 9B 8-bit/8步 → TripoSR MPS → Blender 5 Headless`；人物首张改为左45°全身基准照；新增资产3D生成/状态/停止链、唯一UUID、心跳、超时、有限重试、进程树与恢复看门狗；新增GLB、Blend、七角度RGB/蒙版/深度/法线和前端确认下载入口；合并完整3D资产、空间锚与动态动作规范。
- 开发验证：公开MLX Klein 9B真实8步推理通过，约11秒、峰值12.59GB；TripoSR与Blender真实链约20秒，输出GLB、Blend及七角度四通道审核图；专项及关联回归44项与3个子测试通过；Python编译、Vue类型检查、Vite正式构建通过。
- 流程：稽查退回整改的软件测试复测通过，待代码稽查。

#### 首轮稽查退回与二次整改

- 稽查退回：3D通道未被后续2D/分镜实际消费；活动映射使阶段间卡死线程绕过看门狗；Blender实际Eevee和拓扑审核弱于规范；候选在人工确认前覆盖热归档。
- 二次整改：已确认3D资产的RGB、Depth、Normal、Mask作为真实多参考输入进入分镜生成和语义审核；看门狗按队列超时、无进程心跳及总硬截止回收，不再因活动映射永久豁免；Blender最终图改为Cycles 64采样，新增删除松散几何、补洞、非流形边/孤点/UV/材质/边界/单位审核；候选仅保留在output，新增服务端确认接口，确认后以版本副本和原子staging替换归档，未确认重生成不覆盖历史版本。
- 二次开发验证：Cycles 64真实全链成功，7视图四通道用时约137秒；报告为CYCLES/64采样、非流形边0、孤点0、面数20000；专项及关联45项与3个子测试、Python编译、Vue类型检查、Vite构建通过。

#### 第二轮稽查退回与三次整改

- 第二轮稽查退回：看门狗失败化等待重锁的3D线程后，该线程仍可能进入阶段更新并把failed写回processing；归档以删除正式目录后再替换候选，崩溃窗口可能丢失正式路径。
- 三次整改：`_update_image_job`新增failed/completed终态CAS，禁止任何阶段回写非终态；3D线程取得重锁后及Klein、TripoSR、网格、Blender各阶段前统一执行任务终态和硬截止检查，回收后禁止启动后续子进程。归档改为正式目录原子rename到backup、staging原子rename为正式，异常自动把backup原子恢复；服务启动扫描残留backup并恢复缺失正式归档，成功后旧版移入版本目录。
- 三次开发验证：关联45项与3个子测试、Python编译、Vue类型检查、Vite构建通过；正式服务活动任务0。

#### 第三轮稽查退回与四次整改

- 第三轮稽查退回：`_run_image_process`锁外初检与锁内Popen之间存在停止/看门狗写failed的竞态，锁内直接登记generating可能绕过终态CAS。
- 四次整改：在与停止、看门狗相同的`IMAGE_JOB_LOCK`内且Popen之前重新加载持久任务，原子校验failed/completed终态、started硬截止和shutdown门禁；任一不通过时Popen调用为0，终态保持且不进入重试。Popen后的PGID/登记/落盘异常继续执行既有进程树与活动映射完整回滚。
- 四次开发验证：专项与关联回归、Python编译、Vue类型检查、Vite构建通过；待独立竞态注入复测。

#### 最终软件测试与稽查关闭

- Popen竞态软件测试：67/67通过。GateLock将线程暂停在锁外初检后、Popen前，stop原子写failed后恢复；Popen调用0次，failed及原错误保持，ACTIVE三映射为0，无重试、候选或归档。关联56项与3个子测试、3项Python编译、Vue类型检查和Vite构建均通过；正式8787健康且活动任务0。
- 最终稽查：通过。Popen前同锁终态/硬截止/shutdown原子门禁、HEAVY锁后和各3D阶段runnable检查、终态CAS、watchdog、进程回滚、版本化原子归档及崩溃恢复全部成立；3D四通道真实进入分镜生成与语义审核，Cycles 64拓扑和七视图证据有效，跨项目确认被拒绝。关闭时间：2026-08-10。

#### 软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB，正式兼容服务8787，FLUX.2 Klein 9B 8-bit、TripoSR MPS、Blender 5 Headless。
- 测试范围：异步3D API、UUID/心跳/超时/三次尝试/停止/恢复/看门狗、前端轮询与生成/停止/确认/下载、人物左45°基准、资产3D范围、七视图四通道、GLB/Blend/归档、面数门禁、2D身份边界、空间锚规范、模型缓存、编译与前端构建。
- 用例总数：75
- 通过数：75
- 失败数：0
- 用例清单：55项Python关联测试与3个子测试；3项Python编译；Vue类型检查与Vite正式构建；12项真实HTTP、产物、模型缓存、生命周期和正式服务检查。
- 测试证据：完成任务`5d5eb90e-32d6-4b7c-b410-335d6a6c4511`为completed，report严格按`front_0/left_45/right_45/side_90/back_180/top/bottom`排列，7视图共28个RGB/Mask/Depth/Normal PNG均为1920×1080且可解码；GLB 2,280,780字节、Blend 679,588字节，10003顶点/19998面满足道具20000面上限，热归档与工作副本四个核心文件SHA一致。停止任务`fddeaea1-052b-4b93-b462-4188c20fbb40`在HTTP202返回UUID后被精确停止，持久状态failed、错误“图片任务已停止”、PID/PGID为空且未被晚到完成覆盖。FLUX.2 Klein 9B缓存revision`07c85fd971952e5959a9314f4f2da446ff1b59b2`完整存在16文件约16.639GiB；TripoSR权重1,677,246,742字节且SHA-256为`429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee`。正式8787健康，PID 25466命令与cwd均为当前项目，持久活动任务0且无Klein/TripoSR/Blender受管进程残留。
- 测试结果：通过
- 流转状态：待稽查

#### 稽查退回整改软件测试复测记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB，正式兼容服务8787，临时隔离任务存储。
- 测试范围：3D四通道进入分镜生成与语义审核、watchdog三类超时回收、failed终态保护、Cycles 64与拓扑审核、确认后版本化原子归档、未确认候选隔离、跨项目确认防护，以及M9.145全部既有回归。
- 用例总数：77
- 通过数：77
- 失败数：0
- 用例清单：56项Python测试与3个子测试；3项Python编译；Vue类型检查与Vite构建；8项动态异常/隔离用例；5项真实产物、模型与正式服务复核。
- 测试证据：新记录与兼容旧记录的跨项目确认均被拒绝，正式任务`5d5eb90e-32d6-4b7c-b410-335d6a6c4511`伪造`project-b`确认返回HTTP409“3D候选与资产不匹配”。临时动态用例确认ACTIVE_IMAGE_SUBJECTS仍登记的无进程processing任务可被watchdog回收，已停止failed任务不被晚到结果改成completed，确认产生独立archive/version，后续未确认候选不覆盖已确认归档。`spatial_structure/depth_control/normal_control/mask_control`四类参考均实际进入多参考生成命令，语义审核请求实际包含候选图加4张3D参考图，审核结果继续持久化。`output/3d-smoke/cycles-audit/report.json`记录136.712秒、CYCLES、64采样、7视图、非流形边0、孤点0、20000面；新任务七视图28个PNG仍全部可解码。Klein 9B缓存18项清单无缺失LFS实物，TripoSR大小1,677,246,742字节且SHA-256匹配。正式8787 PID29597、命令与cwd均为当前项目，健康且活动任务0，无受管重进程残留。
- 测试结果：通过
- 流转状态：待稽查

#### 第二轮稽查残留整改软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试范围：图片任务终态CAS、HEAVY锁等待期间watchdog硬截止、各3D阶段运行门禁、晚到线程保护、归档原子替换失败回滚、启动恢复崩溃backup，以及M9.145完整回归。
- 用例总数：73
- 通过数：73
- 失败数：0
- 用例清单：56项Python测试与3个子测试；3项Python编译；Vue类型检查与Vite构建；4项并发、终态及归档故障注入动态用例；5项正式服务和真实烟测复核。
- 测试证据：动态持有`HEAVY_TASK_LOCK`启动真实后台线程，并将watchdog/硬截止缩短；任务在等待锁期间被标记failed，释放锁后`_generate_asset_3d`调用次数仍为0，任务未复活、无结果归档且ACTIVE映射清零。failed任务收到晚到`status=processing/phase/result`更新时CAS保持原终态。对`staged.replace(archive_root)`注入OSError后，旧正式归档立即由backup恢复且内容保持；模拟启动前正式目录缺失、仅残留`.backup`时，`_recover_asset_3d_archive_backups`恢复正式目录并移除backup。正式8787 PID29597健康、cwd与命令均为当前项目、活动任务0；Cycles真实报告仍为136.712秒、CYCLES/64、7视图、非流形边0、孤点0。
- 测试结果：通过
- 流转状态：待稽查

#### 第三轮Popen竞态整改软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试范围：锁外初检至Popen前的停止竞态、终态与硬截止前置门禁、shutdown门禁、登记异常回滚、无重试与ACTIVE清理，以及M9.145完整回归。
- 用例总数：67
- 通过数：67
- 失败数：0
- 用例清单：56项Python测试与3个子测试；3项Python编译；Vue类型检查与Vite构建；1项确定性并发竞态注入；2项正式服务状态复核。
- 测试证据：自定义门禁锁将真实工作线程暂停在`_run_image_process`锁外初检后、`IMAGE_JOB_LOCK`内Popen前；并发stop将任务置failed并清理登记后恢复线程，最终Popen调用数0、错误仅“图片任务已停止”、任务failed不变、ACTIVE_IMAGE_JOBS/ACTIVE_IMAGE_PROCESSES/ACTIVE_IMAGE_SUBJECTS均为0、无候选目录且无重试/归档。`test_registration_failure_terminates_spawned_process_and_does_not_retry`及完整`test_image_task_runtime.py`13项通过，确认Popen后登记异常会终止进程并禁止第二进程。全部关联回归56项与3个子测试通过；正式8787健康且持久活动任务0。
- 测试结果：通过
- 流转状态：待稽查

测试或稽查失败时改回 `待处理`，并保留原修复、测试和稽查记录。

主力开发提交 `待测试` 后，协作调度器必须先自动触发软件测试；测试全部通过并提交 `待稽查` 后才自动触发代码稽查。测试或稽查不通过均自动退回主力开发，禁止跳过任何关口。

## 职责边界

- 稽查：发现工程问题、输出结构化 BUG、执行最终工程稽查；稽查保持只读，由协作记录器持久化提交内容。
- 软件测试：执行本次增量单元、接口、参数、边界和异常测试，填写完整测试报告；不得修改代码或配置。
- 主力开发：定位原因、修改代码、执行开发自检、填写修复记录。
- 稽查不得修改业务代码；主力开发不得代替软件测试或稽查填写结论；软件测试不得代替稽查关闭 BUG。

## BUG 编号规则

统一使用 `BUG-YYYYMMDD-序号`，例如：`BUG-20260808-001`。

## BUG 提交模板

### BUG-YYYYMMDD-001｜问题标题

- 状态：已关闭
- 严重程度：阻断 / 严重 / 一般 / 轻微
- 提交人：稽查
- 提交时间：YYYY-MM-DD HH:mm:ss
- 所属模块：
- 运行环境：
- 问题描述：
- 复现步骤：
  1. 
  2. 
  3. 
- 预期结果：
- 实际结果：
- 错误信息：
- 证据：截图、日志或相关文件路径
- 关联任务：

#### 开发修复记录

- 负责人：主力开发
- 开始时间：
- 完成时间：
- 根因：
- 修复方案：
- 改动文件：
- 测试命令：
- 测试结果：
- 提交状态：待测试

#### 软件测试记录

- 测试人：软件测试
- 测试时间：
- 测试环境：
- 测试范围：
- 用例总数：
- 通过数：
- 失败数：
- 用例清单：
- 失败用例：
- 错误信息：
- 测试证据：
- 测试结果：通过 / 不通过
- 流转状态：待稽查 / 待处理

#### 稽查验证记录

- 验证人：稽查
- 验证时间：
- 验证环境：
- 验证结果：通过 / 不通过
- 验证证据：
- 最终状态：已关闭 / 待处理

---

## BUG 列表

### BUG-20260810-004：30集大纲多轮重模型装卸、超时后残留生成状态

- 状态：已关闭
- 严重程度：阻断
- 提交人：用户反馈
- 提交时间：2026-08-10 17:35:00
- 所属模块：短剧故事大纲生成、文本任务生命周期
- 问题描述：30集大纲在总纲阶段长时间无结果，接口超时后项目仍保持generating，无法保证连续生产。
- 证据：正式项目`宗门小师妹，全宗门抢着护我`累计667秒、分集0项；Ollama加载`qwen3.5:27b-q8_0`；后端记录TimeoutError/BrokenPipe；文本任务表为空。
- 关联任务：M9.144

#### 开发修复记录

- 负责人：主力开发
- 开始时间：2026-08-10 17:36:00
- 完成时间：2026-08-10 17:50:00
- 根因：大纲未纳入文本任务登记、停止、恢复、关闭及看门狗；30集每10集执行一次122B批审并追加一次全剧终审；27B各请求间反复装卸；前端逐字符逐帧展示产生额外等待；项目切换只终止请求但不持久化失败及定向停止后端任务。
- 修复方案：总纲及各分集批次生成均使用服务端唯一任务ID并登记真实工作线程、阶段、心跳和1800秒硬超时；停止按项目和客户端批次精确匹配；服务恢复与关闭统一回收大纲和剧本四类非终态；27B在同一大纲批次内保留300秒并于末批或异常立即卸载；取消每10集一次122B重复批审，仅保留一次全剧122B终审；前端改为整段即时展示；项目切换和停止同步持久化失败并定向停止后端任务。
- 改动文件：`plugins/builtin/short_drama/backend/compat_server.py`、`plugins/builtin/short_drama/frontend/App.vue`、`tests/unit/test_text_task_runtime.py`、`tests/unit/test_qwen35_text_routing.py`、`Dev_MainDev.md`、`docs/product/项目进度.md`、`docs/memory/项目记忆.md`
- 开发验证：专项与关联文本任务31/31通过；Python编译通过；Vue类型检查通过；Vite正式构建通过。已知`test_short_drama_spec_validation.py`存在2项与本增量无关的旧资产卡片静态断言失败，未纳入本BUG通过数。
- 提交状态：待测试

#### 软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目`.venv` Python；正式8787兼容服务；本地Ollama与ComfyUI 8194。
- 测试范围：大纲plan/episodes唯一任务ID、真实线程、5秒心跳、1800秒硬超时、同项目冲突、项目与客户端批次精确停止、错误客户端不误停、failed终态、恢复与关闭同时回收大纲/剧本、27B批次复用及末批释放、异常释放、全剧单次122B终审、前端即时展示、项目切换持久失败并定向停止、正式服务路径及资源空闲、关联文本回归。
- 用例总数：46
- 通过数：46
- 失败数：0
- 失败用例：无
- 错误信息：无
- 测试证据：专项及关联测试`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py`返回`31 passed in 1.61s`；独立并发探针验证任务ID唯一、5秒心跳更新、同项目第二任务HTTP 409、错误`client_generation_id`停止列表为空、正确项目与客户端批次只停止目标任务、请求最终返回冲突且持久任务保持`failed`；恢复与关闭探针均同时将outline/script任务及项目阶段回收为`failed`；27B调用参数验证总纲及非末批`release_model=False, keep_alive=300`，末批`release_model=True`，任务结束活动表为空；前端仅在全剧内容齐备后调用一次`stage:"outline", audit_mode:"final", range:"全剧"`，分集循环不存在批次审核；即时整段展示、项目切换先持久化失败并携带原项目ID和原客户端批次定向停止均通过门禁；Python编译、Vue类型检查、Vite正式构建全部通过。
- 正式运行态：8787监听PID 22773，命令及cwd均位于`/Users/aoo/Code/AI Agent`；`/api/health`返回healthy及9B/27B/122B三档正确模型；Ollama加载模型为空；ComfyUI运行与等待队列均为空。
- 关联回归：`test_short_drama_spec_validation.py`返回13通过、2失败；两项均为既有资产卡片静态字符串断言，与本次大纲任务增量无调用链关联，不影响本BUG判定。
- 冻结证据：测试前后`compat_server.py`、`App.vue`、`test_text_task_runtime.py`、`test_qwen35_text_routing.py`四个关键文件SHA-256完全一致，软件测试未修改业务实现。
- 测试结果：通过
- 流转状态：待稽查

#### 最终稽查记录

- 稽查人：代码稽查
- 稽查时间：2026-08-10
- 稽查结果：不通过，退回主力开发。
- 已通过项：大纲plan与episodes均登记服务端唯一任务ID、真实worker线程、5秒心跳和1800秒期限；同项目outline冲突、按项目与client批次定向停止、failed终态保护、recover/shutdown同步回收outline/script、27B正常批次保留及末批释放、前端整段展示与项目切换失败持久化均已接入。只读复跑专项及关联测试31/31通过；正式8787为PID 22773，命令与cwd均位于`/Users/aoo/Code/AI Agent`，健康接口三档模型正确，Ollama加载模型为空，当前正式项目outline已回收为failed且不存在非终态文本任务。
- 阻断问题1：分集接口在27B成功返回但`_validate_outline_episode_batch()`抛出结构或语义异常时，`_ollama_json(... release_model=False)`已将本次调用标记completed，外层异常路径只写failed，未执行`_unload_ollama_model(TEXT_FORMAL_MODEL)`；不符合“异常立即卸载”，可使27B继续驻留300秒。现有测试仅覆盖网络异常卸载与正常末批释放，未覆盖“推理成功、后置校验失败”的真实异常边界。
- 阻断问题2：1800秒看门狗只将任务记录置failed并移除`ACTIVE_TEXT_JOBS`，未取消正在阻塞的`urlopen`、未终止实际Ollama推理、也未卸载27B；因此“超时”仍可能存在有模型进程但无活动任务状态，不能保证释放重负载通道。现有测试以源码字符串和任务状态为主，未验证超时后实际推理终止及Ollama模型释放。
- 阻断问题3：前端`generateOutline()`最多执行两轮，每轮末尾均调用`stage:"outline", audit_mode:"final", range:"全剧"`；首次终审返回needs_fix时会重生成并再次调用122B，全剧终审实际最多2次，与“只保留一次122B全剧终审”的交付口径不一致。现有测试只证明分集循环无批审，未覆盖needs_fix后的122B调用次数。
- 整改标准：后置校验及任意outline异常统一立即卸载27B；超时与停止必须使实际推理终止并释放模型后才落最终failed，任务状态与实际模型进程保持一致；明确并实现单次122B全剧终审策略，或同步修正交付口径并对最大调用次数建立硬门禁；补充三项真实异常测试后重新提交软件测试与稽查。
- 最终状态：待处理

#### 第一轮稽查退回与主线整改

- 稽查结论：不通过；分集后置校验失败时27B可能继续驻留，硬超时只改状态未终止实际Ollama runner，终审失败自动修复轮会再次调用122B。
- 整改结果：分集后置校验任意异常统一立即卸载27B；看门狗和用户停止改为调用`ollama stop qwen3.5:27b-q8_0`终止实际runner并由请求异常收尾；大纲每次生成固定只执行一次122B全剧终审，未通过时保留结果与问题并停止，禁止自动整套重跑与二次122B加载。
- 新增测试：后置校验失败释放、硬终止命令门禁、单次终审次数门禁。
- 流转状态：主线整改完成，待软件测试复测

#### 稽查整改后软件测试复测记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目`.venv` Python；正式8787兼容服务；本地Ollama 0.32.5与ComfyUI 8194。
- 测试范围：稽查三项阻断整改、上一轮46项大纲生命周期与性能回归、短剧规范关联回归、正式运行态。
- 用例总数：65
- 通过数：65
- 失败数：0
- 失败用例：无
- 错误信息：无
- 整改专项证据：`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py`返回`33 passed in 2.12s`。独立HTTP探针模拟27B成功返回后`_validate_outline_episode_batch`后置校验抛错，接口返回502、仅对27B执行一次立即卸载、任务持久状态为`failed`且活动表为空。独立runner探针确认执行`/usr/local/bin/ollama stop qwen3.5:27b-q8_0`；命令抛出`OSError`时准确回退`_unload_ollama_model`。独立看门狗超时探针确认调用同一runner终止路径、清除`ACTIVE_TEXT_JOBS`并落盘`failed`。
- 单次终审证据：`generateOutline()`生产路径固定单轮，全文仅一次`stage:"outline", audit_mode:"final", range:"全剧"`调用；`needs_fix`写入`outlineAudit`并持久化后立即抛错，异常分支恢复并保留本轮plan、episodes与audit，最终状态为`failed`，不存在自动第二轮生成或第二次122B调用。
- 上轮回归证据：独立并发探针再次验证唯一job ID、5秒心跳、同项目HTTP 409、错误客户端批次不误停、项目与客户端精确停止、原请求冲突收尾和`failed`终态；recover与shutdown均同时回收outline/script任务和项目阶段；27B总纲及非末批保留、末批及异常释放；前端即时整段展示、项目切换先持久失败再定向停止保持有效。
- 关联回归：`test_short_drama_spec_validation.py`返回`15 passed, 3 subtests passed`；此前2项旧资产卡片静态断言本轮已全部通过。Python编译、Vue类型检查和Vite正式构建均通过。
- 正式运行态：8787监听PID 24168，命令与cwd均位于`/Users/aoo/Code/AI Agent`；健康接口返回healthy及9B/27B/122B三档正确模型；Ollama加载模型为空；ComfyUI运行与等待队列均为空。
- 冻结证据：复测前后`compat_server.py`、`App.vue`、`test_text_task_runtime.py`、`test_qwen35_text_routing.py`四个关键文件SHA-256完全一致，软件测试未修改业务实现。
- 测试结果：通过
- 流转状态：待稽查复核

#### 第一轮整改最终稽查复核

- 稽查人：代码稽查
- 稽查时间：2026-08-10
- 稽查结果：不通过，继续退回主力开发。
- 已关闭问题：分集27B成功返回后发生后置校验异常时，接口异常分支已显式调用`_unload_ollama_model(TEXT_FORMAL_MODEL)`并保持任务failed；大纲生产路径已固定单轮、单次122B全剧终审，needs_fix审核结果与本轮plan、episodes均保留，最终状态为failed，不再自动重生成或二次审核。
- 残留阻断：`_terminate_ollama_model()`使用`subprocess.run(..., check=False)`后未检查`returncode`，仅在命令抛出OSError或SubprocessError时执行fallback。`ollama stop`可正常返回非零退出码而不抛异常；本机只读实测停止不存在模型返回`exit_code=1`。当前实现会把这种终止失败当成成功，watchdog/stop已先落盘failed并移除活动任务，但实际runner可能仍存在，任务终态与真实进程仍可能失配；同时未在命令后查询`/api/ps`验证目标模型确已消失。软件测试只覆盖成功调用门禁与OSError fallback，未覆盖非零退出码及终止后runner仍在的边界。
- 整改标准：检查`ollama stop`返回码；任意非零结果必须执行卸载fallback，并在终止后以Ollama实际运行模型列表确认目标runner消失；未消失时不得静默视为已释放，需保持可恢复的明确失败证据。补充“非零退出码”“命令零退出但runner仍存在”“终止确认成功”三类测试后重新提交软件测试与稽查。
- 复核证据：只读复跑专项及关联测试33/33通过；正式8787为PID 24168，命令与cwd均位于`/Users/aoo/Code/AI Agent`，健康接口三档模型正确；当前文本活动任务0、Ollama模型0、ComfyUI运行及等待队列0。
- 最终状态：待处理

#### 第二轮稽查退回与主线整改

- 稽查结论：不通过；`ollama stop`非零退出未触发fallback，停止后未通过`/api/ps`确认runner消失，任务可能早于实际模型终止落为failed。
- 整改结果：`ollama stop`非零或异常均执行卸载fallback；终止后循环读取`/api/ps`确认目标模型不存在，首次未消失则再次卸载并复核；两轮仍存在时返回失败。看门狗仅在runner确认消失后才写failed并移除ACTIVE，未确认时保持processing并继续回收；用户停止同样仅在确认终止后写failed，否则返回503且保持任务运行态。
- 新增测试：非零退出fallback、runner消失验证、runner持续存在不得伪报成功。

#### 第三轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目`.venv` Python；正式8787兼容服务；Ollama 0.32.5；ComfyUI 8194。
- 测试范围：`ollama stop`零退出、非零退出、OSError与runner持续存在；看门狗终止成功/失败状态；停止接口终止成功/失败状态；跨项目精确停止回归；后置校验释放、单次122B终审、文本与短剧规范回归、正式服务和资源空闲。
- 用例总数：68
- 通过数：67
- 失败数：1
- 通过证据：专项与关联测试返回`50 passed, 3 subtests passed`；独立隔离探针确认exit 0且runner消失返回True、exit 1执行fallback且runner消失返回True、OSError执行fallback且runner消失返回True、runner持续存在返回False；看门狗在False时保持`processing`与ACTIVE且不写`finished_at`，True时才落`failed`并清ACTIVE；停止接口False返回503且任务保持`generating`与ACTIVE，True返回200后才落`failed`并清ACTIVE。真实本机`ollama stop qwen3.5:27b-q8_0`返回exit 0，随后`/api/ps`确认模型列表为空。后置校验异常释放、单次122B全剧终审、Python编译、Vue类型检查和Vite正式构建继续通过。
- 失败用例：跨项目活动任务并存时，按项目与客户端批次停止目标outline任务仍无runner所有权校验，直接调用全局`_terminate_ollama_model(TEXT_FORMAL_MODEL)`。
- 错误信息：隔离HTTP探针同时登记`p1/target`与`p2/other`两个活动outline任务；请求停止`p1+c1`后，持久与ACTIVE只移除target，但全局27B终止函数被调用一次，p2仍显示活动。若实际runner属于p2，p2推理会被误杀，产生“有活动任务但实际runner被另一项目停止”的状态失配。
- 出错模块：`plugins/builtin/short_drama/backend/compat_server.py`；停止接口`/api/generation/stop`及同类看门狗终止路径。
- 预期行为：只有确认目标job当前拥有27B runner时才能执行全局模型终止；目标仅在等待重负载锁时，不得终止其他项目实际运行的runner。跨项目非目标任务的runner、ACTIVE及持久状态必须同时保持不变。
- 实际行为：活动任务记录不保存runner所有权；停止或超时任一outline任务都会终止共享27B模型，无法区分当前实际推理属于哪个项目/job。
- 正式运行态：8787监听PID 25184，命令与cwd均位于`/Users/aoo/Code/AI Agent`；健康接口三档模型正确；Ollama模型列表为空；ComfyUI运行与等待队列为空。
- 冻结证据：测试前后四个关键业务与测试文件SHA-256一致，软件测试未修改业务实现。
- 测试结果：不通过
- 流转状态：待主线开发整改

#### 第四轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目`.venv` Python；正式8787兼容服务。
- 测试范围：第三次runner所有权整改、跨项目等待/owner停止、取消等待后禁止推理、owner专属终止、关联文本与短剧规范回归。
- 用例总数：55
- 通过数：54
- 失败数：1
- 通过证据：专项及关联仓库测试返回`52 passed, 3 subtests passed`；独立HTTP探针确认p1等待、p2 owner时停止p1不调用`ollama stop`，p2 ACTIVE保持，随后停止p2 owner才调用27B终止；取消任务取得重负载锁前由持久`failed`门禁拒绝且未发出Ollama请求。exit code与`/api/ps`双门禁、看门狗owner判断、后置校验释放和单次122B终审关联用例继续通过。
- 失败用例：运行中的script任务为`FORMAL_MODEL_OWNER_JOB_ID`时，`/api/generation/stop`未执行27B runner终止即写入failed并移除ACTIVE。
- 错误信息：隔离HTTP探针登记`script-owner`为当前27B owner，请求按项目`sp`与客户端批次`sc`停止script；接口返回HTTP 200及`stopped:["script-owner"]`，持久任务变为`failed`、ACTIVE被移除，但`_terminate_ollama_model`调用次数为0，owner仍为`script-owner`。实际27B推理可继续运行，形成“任务已失败且无ACTIVE，但runner仍存在”。
- 出错模块：`plugins/builtin/short_drama/backend/compat_server.py`的`/api/generation/stop`。当前硬终止条件写死为`stage == "outline" and owner in targets`，未覆盖已使用`owner_job_id=job_id`登记所有权的script任务。
- 预期行为：outline或script目标只要是当前27B owner，都必须先确认runner终止成功；终止失败返回503并保持非终态和ACTIVE；确认终止后才允许写failed并清ACTIVE。等待任务仍不得终止其他owner。
- 实际行为：outline owner路径符合要求，script owner路径绕过终止确认直接落终态。
- 冻结证据：测试前后关键业务与测试文件未由软件测试修改。
- 测试结果：不通过
- 流转状态：待主线开发整改

#### 第五轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目`.venv` Python；正式8787兼容服务；Ollama 0.32.5；ComfyUI 8194。
- 测试范围：第四次runner所有权整改、outline/script owner停止成功与失败双门禁、跨项目等待隔离、取消等待禁止推理、owner异常清理、exit code与`/api/ps`确认、后置校验释放、单次122B终审及全套关联回归。
- 用例总数：67
- 通过数：67
- 失败数：0
- 失败用例：无
- 错误信息：无
- 专项与关联证据：`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py tests/unit/test_short_drama_spec_validation.py`返回`53 passed, 3 subtests passed`；后置校验失败立即释放、exit 0/exit 1/OSError及runner持续存在、看门狗所有权、单次122B终审和短剧规范回归全部通过。
- owner停止证据：独立HTTP参数化探针分别验证outline与script当前owner。runner终止返回False时两类接口均返回503、任务保持`generating`且ACTIVE不变；返回True时才返回200、写入`failed`并清ACTIVE；两类owner均准确调用一次`_terminate_ollama_model(TEXT_FORMAL_MODEL)`。
- 跨项目证据：p1等待、p2 owner并存时，按p1项目与客户端批次停止只失败化p1等待任务，不调用`ollama stop`，p2 ACTIVE与owner保持；停止p2时才允许终止runner。取消的等待任务取得重负载锁后，在发出Ollama请求前被持久`failed`门禁拒绝。
- owner清理证据：模拟owner完成登记后`urlopen`抛出TimeoutError，finally准确清空`FORMAL_MODEL_OWNER_JOB_ID`；取消门禁路径未登记owner、未调用Ollama；正常、异常及停止路径不存在残留owner。
- 正式运行态：8787监听PID 27026，命令及cwd均位于`/Users/aoo/Code/AI Agent`；健康接口返回三档正确模型；Ollama模型列表为空；ComfyUI运行与等待队列为空。Python编译、Vue类型检查与Vite正式构建通过。
- 冻结证据：复测前后`compat_server.py`、`App.vue`、`test_text_task_runtime.py`、`test_qwen35_text_routing.py`四个关键文件SHA-256完全一致，软件测试未修改业务实现。
- 测试结果：通过
- 流转状态：待稽查复核
- 流转状态：主线第二次整改完成，待软件测试复测

#### 第三轮软件测试退回与主线整改

- 测试结论：67/68，不通过；跨项目outline任务并存时，停止等待中的p1会调用全局27B终止并可能误杀实际属于p2的runner。
- 整改结果：新增27B`owner_job_id`登记；总纲、分集和剧本进入实际Ollama推理前在重任务锁内登记owner，统一finally清除。停止与看门狗仅在目标job等于当前owner时终止runner；等待锁任务只写自身failed，取得锁后先检查终态并禁止启动推理。跨项目停止不再影响其他owner。
- 新增测试：停止等待项目不调用终止且owner项目保持运行；已取消等待任务取得重任务锁后不得发起Ollama请求。
- 流转状态：主线第三次整改完成，待软件测试复测

#### 第四轮软件测试退回与主线整改

- 测试结论：54/55，不通过；script任务已登记为27B owner，但停止接口的runner终止条件仍限定`stage == "outline"`，导致script提前落failed并清ACTIVE。
- 整改结果：runner终止条件统一为`owner in targets`，不再区分outline/script；任一27B owner均须先确认runner消失，成功后才写failed，失败返回503并保持非终态与ACTIVE。等待任务仍不终止其他owner。
- 新增测试：停止script owner必须调用runner终止一次，确认后才清ACTIVE并写failed。
- 流转状态：主线第四次整改完成，待软件测试复测

#### 第五轮最终稽查

- 稽查人：代码稽查
- 稽查时间：2026-08-10
- 稽查结果：通过。
- 所有权与终态：outline与script仅在目标job等于当前27B owner时执行runner终止；终止确认失败保持原非终态与ACTIVE并返回503，确认成功后才写failed并移除ACTIVE。等待锁任务不终止其他项目owner；等待任务被取消后，在取得重任务锁且发出Ollama请求前由持久failed门禁拒绝。owner在正常、异常及停止收尾均由finally按原job精确清除。
- runner确认：`ollama stop`零退出、非零退出及命令异常均有明确路径；非零与异常执行卸载fallback，随后通过`/api/ps`轮询验证目标模型消失，两轮仍存在时返回False，禁止伪造释放成功。看门狗与用户停止共用同一owner和runner确认门禁。
- 生产链路：分集27B成功返回后的任意后置校验异常立即卸载正式模型并保持failed；正常非末批保留、末批释放；大纲固定单轮且全剧只调用一次122B终审，needs_fix保留plan、episodes与audit并落failed，不自动重生成或二次审核。
- 测试与正式证据：只读复跑`test_text_task_runtime.py`、`test_qwen35_text_routing.py`、`test_short_drama_spec_validation.py`为53/53通过及3/3子测试通过，Python编译通过。正式8787监听PID 27026，命令与cwd均位于`/Users/aoo/Code/AI Agent`，健康接口返回正确9B/27B/122B模型；非终态文本任务0、Ollama模型0、ComfyUI运行队列0、等待队列0。
- 最终状态：已关闭

### BUG-20260810-002：短剧文本任务仍使用单一旧模型，缺少Qwen3.5分层路由

- 状态：已关闭（历史模型口径，已被M9.163覆盖）
- 严重程度：严重
- 提交人：用户需求
- 提交时间：2026-08-10
- 所属模块：短剧大纲、剧本、分镜及文本审核
- 问题描述：分集梗概、正式叙事生成和初终审未按任务复杂度分别绑定Qwen3.5 9B、27B与122B MXFP4，重模型缺少统一按需串行加载与完成卸载。
- 关联任务：M9.141

#### 开发修复记录

- 负责人：主力开发
- 开始时间：2026-08-10
- 根因：兼容后端仅保留单一`_ollama_json`默认模型，文本审核接口未接入本地122B MXFP4。
- 修复方案：接入9B 4-bit轻量路由、27B Q8正式生成路由和122B MXFP4审核路由；27B与122B共享重任务互斥锁，Ollama请求结束按模型卸载，MLX审核使用一次性子进程退出释放。
- 改动文件：`plugins/builtin/short_drama/backend/compat_server.py`、`plugins/builtin/short_drama/backend/mlx_json_worker.py`、`tests/unit/test_qwen35_text_routing.py`、`tests/unit/test_text_task_runtime.py`
- 完成时间：2026-08-10
- 当前验证：Python语法检查通过；专项单元测试10/10通过；关联文本任务回归21/21通过；27B Q8真实结构化推理返回严格JSON并确认Ollama已卸载；122B MXFP4真实结构化推理返回严格JSON，一次性工作进程退出后无残留且系统可用内存恢复87%。
- 提交状态：待测试

#### 第一轮软件测试退回与整改

- 测试结论：不通过；测试期间分集梗概路由被并发改成27B，违反用户明确指定的9B路由，专项测试出现失败。
- 整改：保留新增的分集结构完整性校验，恢复`/api/outline/episodes`仅调用默认9B 4-bit；测试门禁恢复为强制断言9B，禁止通过同步改写测试接受错误路由。
- 整改验证：后端与worker语法通过；专项指定10项10/10通过；正式8787重启后健康接口继续返回三档模型。
- 流转状态：待软件测试复测

#### 第二轮软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试范围：9B/27B/122B精确任务路由、重模型串行与卸载、模型实物完整性、真实结构化推理、后端语法、专项及文本任务回归、正式8787运行态。
- 用例总数：31
- 通过数：31
- 失败数：0
- 测试证据：专项指定测试10/10、当前路由与文本任务关联回归24/24、后端及MLX worker语法检查2/2通过；分集梗概调用默认`qwen3.5:9b-q4_K_M`，故事总纲/正式剧本/分镜调用`qwen3.5:27b-q8_0`，大纲/剧本/分镜审核调用`mlx-community/Qwen3.5-122B-A10B-mxfp4`。27B Q8真实结构化推理6.97秒返回严格JSON，结束后Ollama加载列表为空；122B MXFP4真实结构化推理21.13秒返回严格JSON，一次性worker退出且无残留。27B实物29,970,380,512字节且SHA-256匹配；122B共13/13分片、61.279GiB、1922个索引张量，13个分片SHA-256均匹配Hugging Face下载元数据。128GB机器推理前可用内存90%，串行推理结束后86%，满足至少保留35GB门禁。正式8787监听PID 3899，命令与cwd均位于`/Users/aoo/Code/AI Agent`，`/api/health`返回三档正确模型。冻结前后关键文件SHA-256一致。
- 测试结果：通过
- 流转状态：待稽查

#### 最终稽查记录

- 验证人：代码稽查
- 验证时间：2026-08-10
- 验证结果：通过
- 验证证据：三档任务路由精确符合用户要求；27B与122B共用重任务串行锁并在完成后卸载；Ollama无加载模型、MLX无残留worker；9B/27B/122B实物量化、大小、分片、索引与哈希一致；只读复跑路由及文本任务24/24、Python语法2/2通过；正式8787运行于当前项目并返回三档正确模型；计划、进度、记忆与BUG记录一致。
- 最终状态：已关闭

#### 第三轮软件测试记录（本次增量）

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目 `.venv` Python；本地 8787 兼容服务；Codex Node 运行时
- 测试范围：`compat_server.py` 大纲完整结构与语义去重、分集梗概 27B 路由、122B 审核提示及参数/边界/异常；`App.vue` 默认审核、全剧大纲终审、剧本全上下文；`test_qwen35_text_routing.py` 专项门禁；关联文本任务与正式健康接口。
- 用例总数：27
- 通过数：26
- 失败数：1
- 用例清单：Qwen3.5 专项16项（15通过、1失败）；文本任务运行回归8项（8通过）；Python语法1项（通过）；Vue类型检查1项（通过）；正式8787健康接口1项（通过）。
- 失败用例：`tests/unit/test_qwen35_text_routing.py::test_02_light_tasks_keep_default_9b`
- 复现步骤：在项目根目录执行 `.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py`。
- 错误信息：断言仍要求 `_validate_outline_episode_batch(_ollama_json(prompt).get("episodes", [])`；当前 `/api/outline/episodes` 已按本次需求显式调用 `_ollama_json(prompt, TEXT_FORMAL_MODEL, TEXT_FORMAL_ESTIMATED_MEMORY)`，因此专项测试失败。
- 出错模块：`tests/unit/test_qwen35_text_routing.py`；入参/场景：分集梗概路由静态门禁；预期行为：断言分集梗概使用 `qwen3.5:27b-q8_0` 与正式模型内存预算；实际行为：测试仍断言默认9B。
- 根因及同类风险排查结果：实现与测试路由期望未同步。后端当前故事总纲、分集梗概、正式剧本和分镜均显式走27B；大纲/剧本/分镜审核走122B。其余专项15项及关联运行测试8项通过。前端默认启用全部流程审核、全剧大纲终审携带完整大纲、单集剧本生成携带全剧分集状态和此前全部已完成剧本；但现有测试门禁只检查字符串片段，当前失败会阻断提交稽查。
- 测试命令与证据：`.venv/bin/python -m pytest -q tests/unit/test_qwen35_text_routing.py`（15通过、1失败）；`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py`（23通过、1失败）；`.venv/bin/python -m py_compile plugins/builtin/short_drama/backend/compat_server.py`（通过）；`PATH=/Users/aoo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/vue-tsc --noEmit`（通过）；`curl -sS --max-time 5 http://127.0.0.1:8787/api/health`（HTTP响应 healthy，三档模型正确）。
- 测试结果：不通过
- 流转状态：待处理

#### 第四轮软件测试复测记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目 `.venv` Python；本地 8787 兼容服务；Codex Node 运行时
- 测试范围：`compat_server.py` 大纲完整结构与语义去重、分集梗概27B路由、122B审核提示及参数/边界/异常；`App.vue` 默认审核、全剧大纲终审、剧本全上下文；`test_qwen35_text_routing.py` 修正后的专项门禁；关联文本任务与正式健康接口。
- 用例总数：27
- 通过数：27
- 失败数：0
- 用例清单：Qwen3.5专项16项、文本任务运行回归8项、Python语法1项、Vue类型检查1项、正式8787健康接口1项，全部通过。
- 失败用例：无
- 错误信息：无
- 测试证据：`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py` 返回 `24 passed in 1.08s`；`.venv/bin/python -m py_compile plugins/builtin/short_drama/backend/compat_server.py`通过；`PATH=/Users/aoo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH ./node_modules/.bin/vue-tsc --noEmit`通过；`/api/health`返回`healthy`及9B/27B/122B三档正确模型。修正后的`test_02_outline_episode_structure_uses_27b`明确断言分集梗概使用`TEXT_FORMAL_MODEL`与`TEXT_FORMAL_ESTIMATED_MEMORY`。
- 根因及同类风险排查结果：过期9B断言已同步为27B路由门禁；故事总纲、分集梗概、剧本和分镜正式生成路由以及122B审核路由的关联测试均通过；大纲字段完整性、连续编号、精确与语义重复、无效审核结构、缺失模型运行环境等边界和异常用例均通过；前端默认审核、全剧大纲终审及剧本全上下文门禁通过。
- 测试结果：通过
- 流转状态：待稽查

#### 第五轮软件测试复测记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目 `.venv` Python；本地8787兼容服务；Codex Node运行时
- 测试范围：同义归一化、剧情阶段编号门禁、不可逆变化语义去重、伪覆盖整改、独立功能探针test_17/test_18；27B/122B路由、默认审核、全剧终审、剧本全上下文及直接关联回归。
- 用例总数：31
- 通过数：31
- 失败数：0
- 用例清单：Qwen3.5专项18项、文本任务运行回归8项、合法低相似度不可逆变化边界探针2项、Python语法1项、Vue类型检查1项、正式8787健康接口1项，全部通过。
- 失败用例：无
- 错误信息：无
- 测试证据：`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py`返回`26 passed in 1.09s`；test_17准确拒绝剧情阶段倒流，test_18准确拒绝同义改写后的不可逆变化重复；两组连续编号、结构完整且不可逆变化互不相关的合法批次均被接受；Python语法与Vue类型检查通过；`/api/health`返回`healthy`及9B/27B/122B三档正确模型。
- 根因及同类风险排查结果：同义词归一化已覆盖策反/收买、围堵/围困、伪造/栽赃、盗取/夺走、揭露/查明、撤职/罢免等同类表达；剧情阶段必须与当前集号一致；不可逆变化同义复述可被阻断，抽样无关变化未出现误拒绝；独立探针不再依赖既有重复门禁提前抛错，伪覆盖已消除。
- 测试结果：通过
- 流转状态：待稽查

#### 第六轮软件测试复测记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目 `.venv` Python；本地8787兼容服务；Codex Node运行时
- 测试范围：毒害类同义策略签名、不可逆变化去通用永久措辞后的语义比对、能力阶级退阶及代价门禁、无编号剧情阶段确定性补号、显式错误编号拒绝；27B/122B路由、前端审核和剧本全上下文直接回归。
- 用例总数：35
- 通过数：35
- 失败数：0
- 用例清单：Qwen3.5专项21项、文本任务运行回归8项、独立边界探针3项、Python语法1项、Vue类型检查1项、正式8787健康接口1项，全部通过。
- 失败用例：无
- 错误信息：无
- 测试证据：`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py`返回`29 passed in 1.12s`；独立探针验证“觉醒阶段”补为“第1集·觉醒阶段”、第2集显式携带“第1集·”被拒绝、二阶到三阶且带冷却代价的合法升级被接受；Python语法和Vue类型检查通过；`/api/health`返回`healthy`及9B/27B/122B三档正确模型。
- 根因及同类风险排查结果：毒酒/下毒与噬灵虫等毒害变体可归入同一策略并阻断复用；去除“永久、永远、再也、不能、无法、失去、不可恢复、不可逆”等通用措辞后，主体和结果不同的变化不会因通用词误判；明确一至十阶和数字阶级可检测退阶，能力推进缺少代价/限制会拒绝；实际模型无编号阶段可确定性补号，显式错号仍硬拒绝。
- 测试结果：通过
- 流转状态：待稽查

#### 第七轮软件测试复测记录

- 测试人：软件测试
- 测试时间：2026-08-10
- 测试环境：macOS 128GB；项目 `.venv` Python；本地8787兼容服务；Codex Node运行时
- 测试范围：稽查原始毒害样本“茶中下药/酒里投毒”、毒害词形扩展、否定代价语义硬拒绝；此前大纲结构、语义去重、能力与阶段门禁、27B/122B路由、前端审核及全上下文直接回归。
- 用例总数：45
- 通过数：45
- 失败数：0
- 用例清单：Qwen3.5专项21项、文本任务运行回归8项、否定代价语义边界8项、合法冷却代价1项、毒害词形参数4项、Python语法1项、Vue类型检查1项、正式8787健康接口1项，全部通过。
- 失败用例：无
- 错误信息：无
- 测试证据：`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py`返回`29 passed in 1.09s`；`test_19`使用“茶中下药/酒里投毒”准确命中反派手段重复；`test_20`使用“三阶灵视，可看穿所有伪装，无需代价”准确命中缺少代价。独立参数探针验证“无需代价、没有代价、无任何代价、不需代价、不消耗、零消耗、无副作用、没有限制”8/8拒绝，“冷却一刻钟”正确接受，“下药、投药、投毒、噬灵虫”4/4归入毒害签名；Python语法、Vue类型检查和正式健康接口均通过。
- 根因及同类风险排查结果：毒害签名已覆盖原始词形与既有毒物表达；代价门禁先识别否定短语再识别正向代价词，避免“无需代价”因含“代价”被误接受；合法明确冷却限制未受误伤。此前阶段补号/错号、能力退阶、不可逆变化及无关变化边界继续通过。
- 测试结果：通过
- 流转状态：待稽查

#### 本次增量代码稽查记录

- 验证人：代码稽查
- 验证时间：2026-08-10
- 验证范围：`compat_server.py`、`App.vue`、`test_qwen35_text_routing.py`及同一 BUG 的软件测试证据
- 验证结果：不通过
- 严重问题1：`compat_server.py:204-253` 的所谓语义重复门禁仅使用字符二元组 Jaccard 和 8 组固定关键词签名，真实同义改写可直接绕过。只读行为探针中，既有“在茶中下药/茶水藏毒”后提交“往酒里投毒/宴席毒酒”被接受，未实现可靠的核心事件、反派手段和冲突流程语义去重。
- 严重问题2：27B 输出结构只校验字段非空，没有校验 `story_stage` 单向推进、`irreversible_change` 不可逆且不重复、能力阶段与代价递进等全剧状态约束。只读行为探针确认前集为“高潮”后回退到“起始”仍被接受；重复不可逆状态同样可被接受。
- 严重问题3：`test_qwen35_text_routing.py` 大量使用源码字符串包含/计数作为门禁；`test_15_outline_rejects_semantic_title_and_villain_repetition` 同时构造标题与反派手段重复，只要标题门禁先抛错即通过，不能证明反派语义重复门禁有效；未覆盖同义改写绕过、阶段倒流、不可逆状态重复，因此 24/24 通过属于不充分测试证据。
- 已确认项：分集梗概真实调用27B Q8；前端向后端传递全部既有分集、全部分集状态表和此前完整剧本文本；大纲存在122B批次初审与全剧终审，剧本存在122B分批初审与终审；专项与关联测试复跑为`24 passed in 1.08s`。
- 回归风险：当前启发式门禁可能误杀共享通用字词的不同事件，同时漏放无字面重合的同义重复；后续批次可在字段齐全时发生剧情阶段倒流和状态重复，直接破坏全剧连续性。
- 整改标准：将结构状态约束变为可验证的确定性门禁，至少拒绝阶段倒流、不可逆变化重复和能力进程倒退；语义重复必须覆盖同义改写并分别验证标题、核心事件、反派手段及冲突流程；测试必须以独立行为用例逐项证明每个门禁，禁止用源码字符串存在或一个先触发的错误替代目标行为验证。整改后重新经过软件测试再提交稽查。
- 验证证据：`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py`返回`24 passed in 1.08s`；独立只读行为探针返回`semantic_villain_bypass ACCEPTED`、`stage_regression ACCEPTED`、`irreversible_repeat ACCEPTED`。
- 最终状态：待处理

#### 整改后二次代码稽查记录

- 验证人：代码稽查
- 验证时间：2026-08-10
- 验证范围：同义归一化、阶段编号门禁、不可逆变化门禁及新增独立测试
- 验证结果：不通过
- 已整改项：`story_stage`现强制与当前集号一致；策反/收买、围堵/围困等已登记同义词的反派手段可独立拦截；不可逆变化同义复述测试已独立覆盖；关联测试复跑`26 passed in 1.15s`。
- 残留严重问题1：语义门禁仍是有限同义词表加字符二元组相似度，原稽查指出的未登记同义改写仍可绕过。只读探针中，“在茶中下药/茶水藏毒”与“往酒里投毒/宴席毒酒”的反派手段相似度仅`0.1667`，整批被接受。
- 残留严重问题2：不可逆变化阈值固定为`0.15`，会把共享常见措辞但主体、器官和事件均不同的合法变化误判重复。只读探针中“掌门永久失去右手”与“宗主永久失去左眼”相似度`0.2727`并被拒绝，与第五轮测试所称合法边界无误拒绝不一致。
- 残留严重问题3：上一轮明确要求的能力进程倒退门禁仍未实现。既有“灵视二阶，代价为失明一日”后提交“灵视一阶，无需代价”被接受；新增test_17/test_18未覆盖能力退阶。
- 测试证据判定：31/31软件测试不足以放行；新增测试只覆盖登记过的同义词和选定样本，未复测原始绕过样本，也未覆盖通用短语导致的误杀及能力退阶。
- 整改标准：对原始同义绕过样本建立有效门禁；不可逆变化比较必须区分主体、状态对象与变化结果，避免仅因“永久失去”等通用短语误杀；实现并独立测试能力等级倒退和代价消失；补充原始失败样本、近义改写、合法高词面重合边界和能力进程的行为测试后重新经过软件测试。
- 验证证据：专项与关联测试`26 passed in 1.15s`；独立探针返回`poison_semantic_repeat ACCEPTED`、`unrelated_irreversible REJECTED`、`ability_regression ACCEPTED`。
- 最终状态：待处理

#### 第三轮整改代码稽查记录

- 验证人：代码稽查
- 验证时间：2026-08-10
- 验证结果：不通过
- 已通过项：阶段无编号确定性补号、显式错号拒绝、数字/一至十阶能力退阶、普通缺少代价描述、不可逆变化通用措辞误杀样本、登记毒害词之间的重复门禁均已生效；专项及关联测试复跑`29 passed in 1.12s`。
- 残留严重问题1：原始稽查样本仍未修复。`_conflict_signature`毒害组包含“下毒/投毒”等，但不包含“下药”；既有“在茶中下药/茶水藏毒”后提交“往酒里投毒/宴席毒酒”仍返回接受。`test_19`使用“下毒”替代原始“下药”，未覆盖原始失败证据。
- 残留严重问题2：能力代价门禁只检查正向关键词是否出现，不识别否定语义。“三阶灵视，无需代价”因包含“代价”被判定有代价并接受；“无消耗”“没有限制”等同类表达也存在相同风险。`test_20`仅使用完全不含代价关键词的文本，未覆盖显式无代价绕过。
- 测试证据判定：35/35软件测试仍不足以放行，新增探针避开了两条原始/同类负向边界。
- 整改标准：毒害策略覆盖并独立复测原始“下药→投毒”样本；代价门禁必须先拒绝“无需/无/没有/不产生/免除代价、消耗、限制、反噬”等否定表达，再验证真实非空代价；增加对应独立行为测试并重新经过软件测试。
- 验证证据：`.venv/bin/python -m pytest -q tests/unit/test_text_task_runtime.py tests/unit/test_qwen35_text_routing.py`返回`29 passed in 1.12s`；独立探针返回原始毒害改写`ACCEPTED`、`explicit_no_cost ACCEPTED`。
- 最终状态：待处理

#### 最终代码稽查记录

- 验证人：代码稽查
- 验证时间：2026-08-10
- 验证结果：通过
- 验证结论：原始“茶中下药/酒里投毒”重复样本已由独立行为测试准确拒绝；“下药、投药、投毒、噬灵虫”均归入毒害策略。八类否定代价表达均返回无有效代价，合法“冷却一刻钟”保持接受。此前阶段补号与错号拒绝、能力退阶、不可逆变化去重及合法高重合边界继续有效。
- 完整验收：27B分集结构生成、确定性结构门禁、标题/核心事件/反派手段/冲突流程/不可逆变化重复门禁、122B初审与终审、全剧分集及此前完整剧本上下文均已实现；未发现本轮新增回归或伪测试残留。
- 验证证据：专项及关联测试只读复跑`29 passed in 1.10s`；独立函数探针确认否定代价语义8/8拒绝、合法冷却代价接受、毒害词形4/4同类命中；独立软件测试45/45通过。
- 最终状态：已关闭

### BUG-20260809-05：视觉风格被隐藏默认值覆盖且接口可绕过风格门禁

- 状态：已关闭
- 严重程度：严重
- 提交人：代码稽查
- 提交时间：2026-08-09 01:45:00
- 所属模块：短剧项目设置与生图风格
- 问题描述：新建项目隐藏写入“现代真人电影质感”，可见选择未成为权威风格；创建、更新接口可保存空值、失效风格或不一致的 `category/style`。
- 关联任务：M9.92

#### 开发修复记录

- 负责人：主力开发
- 完成时间：2026-08-09
- 根因：视觉风格选项被移除后仍保留隐藏默认值，前端与后端均未建立有效索引一致性门禁。
- 修复方案：恢复视觉风格下拉，统一保存所选风格；前后端同时校验非空、当前索引有效且 `category/style` 一致；历史失效风格不静默替换。
- 改动文件：`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/backend/compat_server.py`、`tests/unit/test_short_drama_spec_validation.py`
- 测试命令：`python -m unittest tests.unit.test_short_drama_spec_validation`、`vue-tsc --noEmit`、`vite build`
- 测试结果：11 项单元测试、Vue 类型检查和 Vite 正式构建通过。
- 提交状态：待测试

#### 软件测试记录

- 测试人：软件测试
- 测试时间：2026-08-09
- 测试范围：视觉风格前端选择、创建/更新接口、空值、不一致、失效索引和历史项目边界。
- 用例总数：33
- 通过数：33
- 失败数：0
- 测试证据：11 项项目单元测试、10 项后端校验、4 项接口门禁、8 项前端边界全部通过；Vue 类型检查通过。
- 测试结果：通过
- 流转状态：待稽查

#### 稽查验证记录

- 验证人：代码稽查
- 验证时间：2026-08-09
- 验证环境：本地开发环境
- 验证结果：通过
- 验证证据：后端创建/更新持久化前门禁、前端双重门禁、历史风格保持策略复核通过；11 项单元测试复跑通过；独立软件测试 33/33 通过。
- 最终状态：已关闭

### BUG-20260808-01：定位基准图批次在首张后停止

- 状态：已修复
- 现象：首张人物定位基准图生成后提前等待人工确认，未继续生成人物、道具和场景基准图。
- 修复：按男主角、女主角、其他人物、道具、场景连续串行生成；全部定位基准图完成后统一开放人工确认；资产阶段存储写入串行化并增加三次重试，避免并发写入中断批次。
- 改动文件：`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：Vue 类型检查通过；Vite 正式构建通过；短剧媒体、文本及契约测试 14 项通过。

### BUG-20260808-02：生成下一流程未统一清空下一流程旧数据

- 状态：已修复
- 现象：部分流程进入下一流程时继续复用旧内容或旧媒体。
- 修复：大纲→剧本、剧本→分镜脚本、分镜脚本→资产、资产→分镜画面、分镜画面→分镜视频、分镜视频→成片，统一只清空紧邻下一流程后自动生成；其他流程数据保持不变。
- 改动文件：`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：分镜脚本→资产真实界面验证旧资产即时清空为0、重新提取17项并自动开始首图生成；Vue 类型检查、Vite正式构建及14项短剧关联测试通过。

### BUG-20260808-03：资产图片重生成误清空资产简介

- 状态：已修复
- 现象：分镜脚本已提取的资产结构与图片生成结果未分离。
- 修复：分镜完成后预建人物、道具、场景简介和空图片位；生成图片仅清空图片、角度图和生成状态，保留资产结构与简介。
- 改动文件：`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：项目资产阶段已验证4个人物、4个道具、7个场景简介持续存在，未生成项保持空图片位；Vue类型检查、Vite正式构建及14项关联测试通过。

### BUG-20260808-04：资产生图状态显示在错误图片位

- 状态：已修复
- 现象：单张资产生成时，同一资产的多个图片位统一显示生成状态，无法识别真实生成项。
- 修复：生成状态与资产类别、资产名称和图片角度唯一键绑定；页面恢复后按持久化单项状态回退定位。
- 改动文件：`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：真实界面仅当前人物基准图显示“此图正在生成中”和停止按钮，其余图片位保持“等待生图”；后台生图进程正常运行；Vue类型检查、Vite正式构建及14项关联测试通过。

### BUG-20260808-05：后台生图完成后自动切换资产分类

- 状态：已修复
- 现象：用户查看人物页面时，道具或场景生成完成会强制跳转对应分类。
- 修复：移除批量生图循环对当前资产分类的写入，完成结果只更新对应图片数据。
- 改动文件：`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：真实界面停留道具页期间人物和道具图片连续完成，分类始终保持道具；Vue类型检查、Vite正式构建及14项关联测试通过。

### BUG-20260808-06：人物基准照“就要这张”按钮被全批次门禁隐藏

- 状态：已修复
- 现象：人物基准照已生成且待确认时，按钮仍因其他资产未完成而不可见。
- 修复：按钮改为按当前人物基准照的图片与待确认状态独立显示。
- 改动文件：`plugins/builtin/short_drama/frontend/App.vue`
- 验证：真实界面4张已生成人物基准照均显示“就要这张”；新建项目“中文 LoRA 模式”已确认移除；Vue类型检查、Vite正式构建及14项关联测试通过。

### BUG-20260808-07：大纲核心人物未完整建立资产预制框

- 状态：已修复
- 现象：大纲核心人物简介有5人，资产生成页只建立4个人物预制框。
- 修复：资产提取携带完整核心人物清单；提取结果与大纲按姓名对齐，模型漏项自动补齐；历史资产加载时自动补建并持久化缺失人物框。
- 改动文件：`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/backend/compat_server.py`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：当前项目资产人物页已由4个预制框自动补齐为5个；Vue类型检查、Vite正式构建、Python编译及9项短剧文本/契约关联测试通过。

### BUG-20260808-08：现代真人项目未应用 LoRA

- 状态：已修复
- 现象：现代真人角色生图记录为 `lora.id=none`、权重0。
- 修复：新增现代写实人像 LoRA，并将现代真人角色自动匹配到 `modern-realistic-portrait`、权重0.75；接入 FLUX.1-dev 开放镜像和 Diffusers MPS 兼容推理；场景和道具不使用人像 LoRA。
- 改动文件：`plugins/builtin/short_drama/backend/compat_server.py`、`models/loras/模型索引.json`、`models/loras/README.md`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：真实人物生图接口已返回 `modern-realistic-portrait`、现代中国人像写实摄影、权重0.75并生成有效图片文件；LoRA 权重912/912层兼容加载；Python编译、模型索引JSON校验及9项短剧文本/契约关联测试通过。

### BUG-20260809-01：人物定位基准照未执行构图验收

- 状态：已修复
- 现象：古风人物首张定位基准照出现纸伞、樱花、户外山景、手部动作及腰部以下构图，仍被系统标记为生成完成。
- 根因：固定古风 LoRA 的风格与场景特征压过基准照构图提示；后端只有道具真人禁入校验，没有人物首张定位基准照的视觉验收门禁。
- 修复：保留并锁定项目唯一全局风格 LoRA；加强证件照式正面胸像提示；生成后使用本地视觉模型逐项校验单人、正面、平视、胸口裁切、纯灰背景、无手部、无道具、无场景和非拼图，违规图删除并原槽位最多重试三次，仍失败则暂停且禁止确认和后续角度生成。
- 改动文件：`plugins/builtin/short_drama/backend/compat_server.py`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：用户所示违规图片实测识别为纯灰背景不合格、存在手持道具和胸口以下身体，判定失败；Python编译通过；全局风格 LoRA 唯一锁定规则已写入生产规范。

### BUG-20260809-02：剧本段落固定为5秒且分镜时间轴机械等分

- 状态：已修复
- 现象：每集目标时长固定取60-70秒中位数65秒，剧本持续输出5秒一段，分镜再次均分整集时间轴。
- 修复：每集根据项目、集号和分集剧情稳定选择60-70秒内的实际总时长；剧本改为结构化段落并由后端按对白量、动作复杂度、冲突、情绪和钩子强制分配2-9秒非等长时间，至少包含3种段长；分镜继承剧本总时长并使用非等长镜头计划；加载、恢复、完成判定全部改用逐集真实时长。
- 改动文件：`plugins/builtin/short_drama/backend/compat_server.py`、`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：后端剧本时间分配单测、Python编译、Vue类型检查和正式构建通过。

### BUG-20260809-03：分镜中断后被误报数量不足且无法断点续生成

- 状态：已修复
- 现象：逐镜头生成中断后保留13个镜头，加载时直接执行15-23个成品门禁并报错；点击继续后不能可靠补齐。
- 修复：生成中间态不再执行完整数量终审；根据本集真实时长建立固定镜头时间计划，校验已保存镜头为连续有效前缀后从首个缺失镜头继续生成；只有前缀损坏时才重建该集，完整后再执行数量、时间轴和重复镜头终审。
- 改动文件：`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：Vue类型检查与正式构建通过；中断状态会显示已完成/总数并保留有效镜头。

### BUG-20260809-04：LoRA生图重复加载未量化模型导致单图耗时过长

- 状态：已修复
- 现象：每张928×1664图片都通过Diffusers重新加载完整FLUX.1-dev并执行20步，等待时间过长。
- 修复：现有LoRA实测与原生MLX矩阵维度不兼容，保留兼容的FLUX.1-dev通道，将20步降为8步并把文本序列限制为256；全剧年代画风优先锁定LoRA家族；增加同一资产任务去重，避免重复点击排队跑两次；保持原尺寸、LoRA权重、串行任务及视觉验收不变。
- 改动文件：`plugins/builtin/short_drama/backend/compat_server.py`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`
- 验证：原生MLX兼容测试准确拦截矩阵维度不匹配；兼容通道参数校验、Python编译、Vue类型检查和正式构建通过。

### BUG-20260809-05：人物 LoRA 未绑定且项目内缺少唯一占用

- 状态：已修复
- 现象：项目仅保存全剧风格 LoRA，人物档案没有独立人物 LoRA，已下载的商用人物 LoRA 未进入生图链路。
- 修复：增加同风格、同性别人物 LoRA 确定性分配；项目内一人物独占一 LoRA，重复占用硬阻断；人物 LoRA 的文件名、路径、SHA-256 与底模写入人物档案；定位基准照使用项目固定风格 LoRA 与人物独占 LoRA 的 SDXL 双层工作流。
- 改动文件：`plugins/builtin/short_drama/backend/compat_server.py`、`plugins/builtin/short_drama/frontend/App.vue`、`plugins/builtin/short_drama/frontend/stores/asset.store.ts`、`docs/specs/LORA_ASSET_SPEC.md`、`/Users/aoo/AI/Tools/ComfyUI/main/extra_model_paths.yaml`
- 验证：当前项目林婉儿、陆云渊、苏青梧已持久化三份不同人物 LoRA；重复占用测试、索引与 SHA-256 校验、Python 编译、Vue 类型检查、Vite 正式构建、8787 与 8194 健康检查通过；ComfyUI 已识别国风厚涂全部25个项目 LoRA。

### BUG-20260809-06：生图旧任务占用重负载通道导致后续资产永久等待

- 状态：已关闭
- 现象：数据库保留生成中状态但实际进程已失效，多个旧人物角度请求继续争抢唯一重负载锁，道具任务长期显示生成中但没有实际推理进程。
- 修复：每个生图重负载任务持久化唯一任务ID、排队状态、PID、进程组、心跳、超时和重试次数；实际子进程使用独立进程组，超时或停止时终止完整进程树；普通进程失败只重试一次；新任务启动前回收无进程旧状态及无任务孤儿进程；服务重启统一终止残留PID并释放内存登记；独立看门狗双向检测任务与进程不一致；停止接口接入真实进程终止。
- 改动文件：`plugins/builtin/short_drama/backend/compat_server.py`、`tests/unit/test_image_job_recovery.py`、`tests/unit/test_image_task_runtime.py`、`tests/unit/test_short_drama_spec_validation.py`
- 开发验证：Python编译通过；短剧规范12项通过；任务运行、PID/心跳、单次重试、超时进程树终止、服务重启回收、无进程状态看门狗及静态链路共9项通过；真实“符咒”道具任务已解除旧人物任务占用并完成写回。
- 软件测试：第一轮31项中26项通过、5项状态边界失败；整改后复测43/43通过，覆盖真实HTTP冲突、停止、父子进程树、四类状态回收、孤儿识别、重启恢复、M9.96底模双门禁和正式服务健康。
- 稽查退回：服务端任务ID、PID复用防误杀、手工进程隔离、停止终态保护、优雅关闭持久回收和流程记录不完整。
- 二次整改：任务ID改为服务端UUID，客户端名称仅作查询别名；模型进程统一由携带任务ID和随机所有权令牌的专属监督进程启动；重启只终止PID、PGID、监督器、任务ID和令牌全部匹配的进程；孤儿扫描仅识别专属监督器；终态写入拒绝覆盖failed；服务关闭同步终止进程树、写入failed并清空全部活动登记。
- 二次软件测试：UUID、别名、终态、PID防伪及关闭回收通过；并存正式/临时实例压力测试发现看门狗会跨实例误收监督进程，退回开发。
- 三次整改：监督进程新增由任务存储根目录计算的`service_scope`；持久任务同步记录作用域；孤儿扫描只处理本服务作用域，重启恢复继续按持久作用域核验。正式服务并行运行期间临时实例运行时测试连续10轮全部通过。
- 第三轮软件测试：52项/轮次全部通过；正式看门狗并行下10/10轮超时与单次重试稳定，不同作用域零误杀，同作用域孤儿真实终止；UUID、别名、PID防伪、终态、停止、关闭回收、正式健康及M9.96门禁均通过，提交第三轮稽查。
- 第三轮稽查退回：持久恢复未强制记录作用域等于当前服务；关闭未覆盖无Popen的非终态；别名停止会改写同名历史完成任务；流程状态未同步。
- 四次整改：持久恢复新增当前服务作用域强一致门禁；关闭统一遍历并失败化queued/generating/retrying/processing全部状态；别名停止仅选择最新非终态任务，UUID停止也只允许非终态，历史completed保持不变。
- 第四轮软件测试：67项/断言全部通过，覆盖跨作用域恢复、无Popen四态关闭回收、最新非终态别名停止、10轮正式服务并行压力、正式健康、任务状态和M9.96底模门禁，提交第四轮稽查。
- 第四轮稽查退回：关闭流程存在快照后新进程注册竞态；国风浅涂目录改名后商用索引、下载脚本和运行代码仍指向失效旧目录。
- 五次整改：新增全局关闭门禁，关闭锁内先封禁新进程；模型监督进程改为同一锁内检查门禁、启动并登记，消除快照后越界注册。国风浅涂正式根目录、下载脚本、运行代码和41条商用索引统一为`models/loras/国风浅涂/`，现有20个非商用测试权重继续隔离保留。
- 第五轮软件测试：104项全部通过，覆盖图片任务回归、shutdown/Popen真实并发、41条商用索引、20个仅测试权重隔离、脚本重跑、旧根清理、正式健康与流程记录，提交第五轮稽查。
- 第五轮稽查退回：Popen成功后PGID获取或持久化失败缺少进程树和活动映射回滚；流程记录未同步第五轮测试。稽查提出脚本会移走仅测试权重，但仓库现行`retire_unlisted_person_loras`已明确跳过文件名含`_仅测试`的权重，复跑验证保持61总权重、41商用、20测试隔离。
- 六次整改：Popen后登记链路增加异常回滚；PGID获取或落盘发生OSError时立即终止已启动监督进程树、清理活动任务及进程映射、尽力写入failed并禁止再次重试，避免产生无登记进程或第二个重负载任务。
- 第六轮软件测试：36/36通过，包括规格12项、图片运行时13项、恢复静态4项、getpgid真实异常1项、shutdown/Popen真实并发1项、正式退休函数1项、正式健康与状态2项、流程记录2项。getpgid与首次登记落盘异常均只启动一个监督进程，进程树实际终止、ACTIVE映射清空、任务failed且不重试；正式退休函数返回0，61个权重继续保持41商用与20测试隔离；正式8787健康且运行任务0，提交第六轮最终稽查。
- 第六轮稽查：代码、资产及25项只读回归均通过；仅流程记录缺少第六轮软件测试与待稽查状态，退回补齐记录后复核关闭。
- 最终稽查：流程记录补齐后复核通过；代码、进程安全、LoRA资产、测试证据和强制流转完整，允许关闭BUG。

### BUG-20260809-07：ComfyUI 幽灵任务与临时输入污染后续生图

- 状态：已关闭
- 现象：API 请求退出或任务已标记失败后，ComfyUI 内部 prompt 仍可能继续运行，占用唯一重负载通道；Qwen 临时参考图与蒙版残留。
- 修复：持久化的 Schnell/Qwen/Comfy prompt ID 在清理、服务启动恢复、关闭和任务异常时逐一核销；运行中 prompt 自动中断、排队 prompt 定向删除，不清空其他客户端任务；启动清除本流程全部临时参考图与蒙版；任务结束无论成功失败均清理输入并释放模型。
- 验证：服务重启后 ComfyUI `queue_running` 与 `queue_pending` 均为空，临时输入为0；图片恢复、运行时及短剧规范测试31项、3个子测试全部通过。

### BUG-20260809-08：并发阶段写入覆盖项目历史数据

- 状态：已关闭
- 根因：`projects.json` 的阶段接口以无事务锁的“读取—修改—整文件替换”写入，并发请求可用旧副本覆盖其他阶段；原版本接口未落盘。
- 修复：项目读改写使用全局可重入事务锁；阶段接口始终基于最新磁盘数据仅合并目标阶段并记录revision；每次保存前保留最近50份整库快照；损坏时自动读取最近有效快照；项目版本创建、查询及回滚全部真实落盘，删除项目前自动建版本。
- 验证：6阶段并发写入全部保留，损坏恢复和版本可恢复性通过；合计34项、3个子测试通过。当前资产状态已创建首个真实保护版本。

### BUG-20260809-09：剧本生成中断后按钮永久禁用

- 状态：已关闭

- 现象：剧本阶段持久化为`generating`后请求中断，数据库保留空内容占位且没有实际Ollama任务；前端只在内存中改为失败，刷新后重复恢复，空占位又阻止该集重新生成，“生成分镜脚本”长期禁用。
- 修复：剧本请求使用唯一任务ID；服务端持久化活动线程、集数、开始时间和心跳，330秒看门狗回收无活动线程或心跳超时任务，停止与服务重启统一失败化非终态任务和项目阶段；前端5秒持久化心跳，中断状态立即写回失败；空内容集不计完成并在续生成前移除；普通失败最多重试一次，成功正文持久化后才清任务状态。
- 开发验证：Python编译和Vue类型检查通过；新增剧本任务恢复3项及短剧规范13项全部通过；正式8787健康，当前项目第1集剧本标题与65秒正文完整，阶段为confirmed，分镜脚本门禁条件成立；Ollama当前无残留模型进程。
- 第一轮软件测试退回：复测瞬间Ollama仍在卸载截止时间前保留`qwen3:8b`进程，未继续其他测试。
- 一次整改：`_ollama_json`无论成功、网络异常或超时均在`finally`显式提交`keep_alive=0`卸载请求；服务关闭同步失败化全部活动剧本任务并再次卸载Qwen3 8B。整改后`/api/ps`为空。
- 第二轮软件测试退回：本次剧本增量全部通过，但仓库固定角度回归仍断言旧IP-Adapter标记；主线复核发现正式路由也发生回退，与已验收M9.104不一致。
- 二次整改：人物`variant + target_pose`正式路由恢复为`_generate_qwen_character_variant`，无固定角度的人物参考编辑继续使用IP-Adapter；同步更新回归断言到Qwen FP8Mixed、`qwen_variant`阶段及精确任务ID链路。
- 第三轮软件测试退回：36项既有回归、编译、类型检查、构建、正式项目和Ollama卸载均通过；服务关闭未失败化持久层中无活动线程的非终态文本任务。
- 三次整改：`_shutdown_text_jobs`统一扫描并失败化持久层全部queued/generating/retrying/processing，completed保持不变；同步回收项目script生成态、清空任务ID与心跳，再卸载Qwen3 8B。
- 第四轮软件测试退回：37项回归及全部恢复边界通过；新剧本接口登记时位置参数与持久字段同名，触发`got multiple values for argument 'job_id'`并返回HTTP 502。
- 四次整改：`_update_text_job`内部任务键形参改为`text_job_id`，允许持久记录同时保存`job_id`字段，正常请求可完成唯一任务登记。
- 第五轮软件测试退回：同一全剧批次的多集请求复用前端`generation_id`，后生成集覆盖先生成集的任务记录。
- 五次整改：每个单集HTTP请求始终由服务端生成独立UUID；前端`generation_id`仅保存为`client_generation_id`批次别名。同批次连续两集现在持久化两条独立任务记录。
- 第六轮软件测试退回：剧本任务全链路通过；固定角度正式路由和旧测试同时被外部增量覆盖回IP-Adapter，39项测试假绿。
- 六次整改：再次恢复固定角度Qwen路由；测试改为截取正式HTTP生成路由和`variant + target_pose`分支精确断言Qwen调用，并明确禁止目标分支在`else`前调用IP-Adapter，消除全文件字符串命中造成的假绿。
- 第七轮软件测试：86项全部通过，状态流转为待稽查。
- 第七轮稽查退回：项目切换只abort未持久回收；script stop未按项目/任务筛选；独立心跳线程可能给已卡死工作线程持续续命。
- 七次整改：项目切换/页面关闭在切换上下文前立即将原项目script写为failed并按项目+client批次定向stop；服务端stop支持job UUID或项目+client批次精确筛选，禁止跨项目误停；活动登记保存真实工作线程对象与启动时间，看门狗同时核验线程存活、线程ID、心跳和330秒硬截止。
- 第七轮软件测试通过：关联仓库回归39项（文本任务7、图片恢复6、短剧规范13、图片生命周期13），独立真实HTTP同批次两集唯一任务7项、同集冲突/停止/失败终态7项、330秒看门狗与shutdown回收12项、前端任务边界及M9.104 Qwen固定角度14项、当前项目第1集与分镜按钮门禁7项，合计86项全部通过；Python编译、Vue类型检查、Vite构建通过。正式8787健康，项目`local-default/aoo/4eadd09d-6405-444d-a8d6-f308427547fa`的第1集《血脉觉醒》正文1425字符、65秒且script为confirmed，Ollama `/api/ps`为空。
- 第七轮稽查退回：一是项目切换等路径调用`abortProjectWork()`时只执行`scriptController.abort()`，`generateScripts()`捕获AbortError后直接返回，未立即将原项目script阶段持久化为failed，也未调用服务端stop；原项目仍可保留`generating`空占位直到刷新或服务重启。二是`/api/generation/stop`对script未按项目、单集、服务端job UUID或client批次别名限定，直接遍历并失败化`ACTIVE_TEXT_JOBS`全部任务，多项目并行时会误停其他项目剧本。三是330秒看门狗只检查独立心跳线程持续刷新的`heartbeat_epoch`，未校验已登记的请求工作线程`thread_id`是否仍存活；工作线程或Ollama调用卡死时，心跳线程仍会永久续心跳，任务不会由330秒看门狗回收。仓库39项、3个子测试复跑仍通过，说明现有测试未覆盖上述三条真实边界；正式8787健康、Ollama模型列表为空、当前项目第1集script为confirmed，不影响本次退回结论。M9.104正式`variant + target_pose`分支仍严格调用Qwen Image Edit 2511 FP8Mixed 12步，未发现再次回退或测试假绿。
- 稽查整改后软件测试通过：关联仓库回归40项（文本任务8、图片恢复6、短剧规范13、图片生命周期13）；独立定向stop按项目+client、job UUID、空条件、错误项目及跨项目保护12项；worker线程缺失/死亡、心跳超时、330秒硬截止、健康线程与completed保护12项；前端原项目failed持久、定向stop及上下文切换顺序8项；正式项目第1集与分镜按钮门禁7项，合计79项全部通过。Python编译、Vue类型检查、Vite构建通过；正式文本任务运行态0、8787健康、Ollama `/api/ps`为空，M9.104固定角度Qwen路由回归通过。
- 最终稽查：三项退回问题复核通过。`abortProjectWork()`在切换上下文和中断控制器前保存原项目failed状态并按原项目ID与client批次定向停止；服务端stop仅接受精确job UUID或项目ID加可选client批次，空条件、错误项目和跨项目任务均不命中；看门狗同时核验真实worker线程对象、线程ID、活动心跳和启动时间330秒硬截止，failed/completed终态保护保持有效。服务端单集UUID、多集同批次不覆盖、冲突、重试、恢复、关闭、Ollama卸载及前端5秒心跳、空内容、只补缺集和按钮门禁均无新增问题。只读复跑仓库40项、3个子测试通过；正式8787健康、文本活动任务0、Ollama模型0，当前项目第1集《血脉觉醒》正文1425字符、65秒且script为confirmed。M9.104正式固定角度分支继续严格使用Qwen Image Edit 2511 FP8Mixed 12步。允许关闭BUG。

### BUG-20260809-10：场景45度视角未区分左右方向

- 状态：已关闭
- 现象：场景卡片只有一个“45°斜侧全景”，无法分别生成左45度与右45度。
- 修复：四槽统一为主平视、左45度、右45度、高角度微俯视；左右提示词明确互斥方向；历史单45度/低角度明细在确认或继续生成时按当前固定定义归一化，左右槽独立生成和持久化。
- 开发验证：左右45度定义、互斥提示、四槽数量及历史角度归一化2项单元测试通过；Vue类型检查通过。
- 第一轮软件测试退回：本次场景角度2项、计数、类型检查和构建通过；关联图片恢复测试当时仍断言旧Schnell固定验收文案。仓库并行增量已将该测试同步为当前动态`validation_evidence`与`validation_passed`门禁，主线只读复跑图片恢复6项全部通过。
- 第二轮软件测试通过：相关资产仓库回归37项（场景固定角度2、资产分类计数1、图片任务恢复6、图片生命周期13、短剧规范15），前端四槽/左右互斥/历史恢复/确认与续生成归一化/逐槽映射/`onlyVariant`隔离/完成门禁/人物道具保持38项，历史旧单45度与低角度、单槽导入重生成及三槽完成状态数据边界16项，合计91项全部通过；Vue类型检查和Vite正式构建通过。
- 最终稽查：通过。场景定义严格保持主平视、左45°、右45°、高角度微俯视四槽；左右提示分别限定展示左侧/右侧空间并显式禁止相反方向，标签、提示、任务名和持久槽位独立。新基准确认、历史基准确认、继续生成、恢复展示、单槽导入与重生成均按当前三项明细重建，旧单45°和低角度不再进入正式槽；`onlyVariant`按当前对象或精确标签重新绑定，只执行目标槽；完成门禁要求三个当前标签均有图且confirmed。人物四槽与道具四槽定义、生成和完成门禁未回归。只读复跑相关仓库37项、3个子测试通过；正式项目现有历史场景仍保留旧失败槽作为待迁移数据，继续确认生成会按新定义替换，不会静默冒充完成。M9.117计划、项目记忆及BUG流程记录一致，允许关闭BUG。
### BUG-20260810-003：TripoSR 下载增量夹带缓存且目录规范版本未同步

- 状态：已关闭（最终稽查通过）
- 测试范围与变更文件：`models/3d/TripoSR/`、`DIRECTORY_README.md`、`docs/technical/ADR/ADR-0005-3d-model-storage.md`
- 测试环境：macOS arm64，物理内存137438953472字节，Python 3，PyYAML 6.0.2，PyTorch 2.8.0
- 测试结果：不通过；用例10项，通过8项，失败2项。
- 通过用例：必需文件存在；`model.ckpt`实际大小1677246742字节与`SOURCE.json`一致；SHA-256实际值`429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee`与登记值一致；`SOURCE.json`可解析且模型来源为`stabilityai/TripoSR`；`config.yaml`可安全解析为13个顶层配置项且`cond_image_size=512`；`torch.load(..., weights_only=True, mmap=True)`成功安全加载549个全为Tensor的权重项、总参数419275628、数据类型均为`torch.float32`；`LICENSE`为MIT许可证且版权归属Tripo AI与Stability AI；ADR-0005状态已接受并登记`models/3d/TripoSR/`、官方来源及MIT许可证，权重、配置、README模型卡和许可证均同目录存在。
- 失败用例1：`models/3d/TripoSR/.cache/huggingface/CACHEDIR.TAG`与`.gitignore`实际位于模型权重目录；ADR-0005明确要求缓存进入`data/`，预期模型目录不含运行或下载缓存，实际夹带`.cache/`。
- 失败用例2：`DIRECTORY_README.md`正文头部仍声明“版本：1.2”，版本记录已新增“1.3（2026-08-10）”；预期当前版本号与最新版本记录一致，实际规范自身版本标识冲突。
- 根因及同类风险排查：Hugging Face下载缓存随模型快照一并落入正式模型目录；目录规范新增1.3记录时未同步文档头版本号。限定检查范围内未发现权重大小、摘要、配置解析、checkpoint安全元数据、许可证、模型卡或ADR登记异常。
- 测试命令与证据：`find models/3d/TripoSR -maxdepth 3 -type f -print -exec stat -f '%z bytes' {} \\;`；`shasum -a 256 models/3d/TripoSR/model.ckpt`；PyYAML `safe_load`；PyTorch `torch.load(path, map_location='cpu', weights_only=True, mmap=True)`；`models/3d/TripoSR/SOURCE.json`、`DIRECTORY_README.md`、`docs/technical/ADR/ADR-0005-3d-model-storage.md`。
- 下一状态：待处理
- 主线整改：`loadProjectFlowState`的空资产路径改为只调用本地`seedAssetCardsFromStoryboard`建立空卡和提示；`loadAssetState`旧census路径只清理旧清单、播种空卡并保持pending，不再调用正式assets提取。两条路径均不占资源、不启动模型，完整档案必须由用户显式操作提交。
- 编号校正：流水线既有“45°单图3D输入与七角度回填”已占M9.164，本恢复任务统一调整为M9.165，三份状态文档与BUG关联同步。
- 开发验证：关联108项及3个子测试、Python编译、Vue类型检查与Vite构建通过；未启动重模型。
- 下一状态：待软件测试复测

- 整改后软件测试：通过。原10项全部通过；`models/3d/TripoSR/.cache/`已不存在，原`CACHEDIR.TAG`与`.gitignore`已迁移至`data/cache/huggingface/TripoSR/`，符合ADR-0005缓存归属；`DIRECTORY_README.md`头部版本已更新为1.3并与最新版本记录一致。回归确认必需文件齐全，`model.ckpt`大小1677246742字节、SHA-256 `429e2c6b22a0923967459de24d67f05962b235f79cde6b032aa7ed2ffcd970ee`均与`SOURCE.json`一致；配置安全解析为13项且`cond_image_size=512`；`weights_only=True, mmap=True`安全加载549个Tensor、419275628参数、均为`torch.float32`；MIT许可证与ADR-0005登记保持有效。
- 最终稽查：通过。官方 Hugging Face API、官方 LFS 指针、本地文件大小与SHA-256完全一致；README、配置和MIT许可证与官方来源一致。权重安全加载549个Tensor、419275628参数；模型正式目录无下载缓存，ADR、目录规范、开发计划、项目进度和项目记忆同步一致，且未将下载完成误报为生产链路接入。
- 状态：已关闭
### BUG-20260810-006：M9.146 FLUX.2 Klein 9B 国风厚涂 LoRA 候选库测试

- 状态：已关闭
- 测试范围与变更文件：`scripts/download_flux2_klein9b_houtu_loras.py`、`models/loras/国风厚涂/`、`models/loras/Flux2Klein9B测试LoRA索引.json`、`data/cache/retired_loras/国风厚涂/`、`output/lora_validation/flux2-klein9b/`、`tests/unit/test_flux2_klein9b_houtu_loras.py`
- 测试环境：macOS arm64，物理内存128GB，项目`.venv` Python。
- 测试结果：通过；用例14项，通过14项，失败0项。
- 用例清单：下载脚本Python编译；脚本5项候选声明与索引逐字段一致；索引基座为`black-forest-labs/FLUX.2-klein-9B`且量化运行时为`mlx-community/flux2-klein-9b-8bit`；生产启用为false；活动目录权重总数5；分类为风格2、人物女性1、人物男性1、灵兽1；5文件登记路径与文件存在；5文件大小逐项一致；5文件SHA-256逐项一致；5个Safetensors头均可解析且含有效Tensor键；活动目录FLUX.1权重为0；旧FLUX.1权重5项位于`data/cache/retired_loras/国风厚涂/`；5张索引样图均为有效PNG并可解码，女性、男性及两张风格图为512×768，灵兽图为768×512；男女样图人物性别与文件分类一致；视觉结论与索引一致，古代幻想图具备低对比电影CG厚涂候选特征，绘画图存在平涂与伪文字，女性和男性图偏平涂，犬类图不是国风神兽，后4项均保持不合格测试隔离。
- 完整性证据：5文件大小分别为662730032、82866728、304650320、165704416、8398392字节；SHA-256分别为`42253aaa6214aa6765f370189eb4b67fed90a5b947a9123f1cbfb2548d8a9007`、`18c7c42859ddef8913244823858207c6eb1600c2fb7d9180841e8cd39fcec9fc`、`1f362f112a050ff2c007304ec9f4eab38f8ee294f09154f20d524993ec2c0272`、`59a4dac5a4d72a06456bcfb2a0b7e68e679180a37343167c1328bab78f022b99`、`ba5603a1ceac055614c34ca80b23e4a02db5f074f18eb0dc0bf91bbd54033d14`。Safetensors Tensor键数量依次为224、224、288、224、64；前三个224键文件及男性文件元数据明确为`flux2_klein_9b`，5项索引加载证据均为通过。
- 测试命令与证据路径：`.venv/bin/python -m pytest -q tests/unit/test_flux2_klein9b_houtu_loras.py`结果`2 passed`；`.venv/bin/python -m py_compile scripts/download_flux2_klein9b_houtu_loras.py`通过；只读AST/JSON/Safetensors头、文件大小与SHA-256交叉校验通过；`sips`解码5张PNG通过；5张样图逐张人工视觉复核通过。
- 失败用例、报错、根因及同类风险：无。限制许可或来源未公开的4项未进入生产，`production_enabled=false`与`tested_candidate`隔离状态正确。
- 下一状态：待稽查

- 后续生产接入软件测试：不通过；专项与动态边界20项中19项通过、1项失败。
- 通过项：Klein9B国风厚涂索引`production_enabled=true`；5文件大小与SHA-256完整性继续通过；生产命令动态测试同时包含`--lora-paths`与`--lora-scales`；女性人物选择古代幻想风格0.9加女性0.72、男性人物选择古代幻想风格0.9加男性0.72、灵兽选择古代幻想风格0.9加灵兽0.75、场景只选择古代幻想风格0.9；篡改大小触发“LoRA文件缺失”、篡改SHA触发“LoRA校验失败”、关闭启用标志触发“尚未启用”；活动国风厚涂目录FLUX.1权重为0；后端旧`国风厚涂 → 风格_油画仙韵_FLUX1`映射已清除；正式8787返回healthy，运行进程为当前项目`.venv/bin/python .../compat_server.py`。
- 失败项：关联回归`tests/unit/test_image_job_recovery.py::test_all_asset_baselines_use_local_flux1_schnell_gguf`仍断言后端必须包含已按本次需求清除的`"国风厚涂":"风格_油画仙韵_FLUX1_仅测试.safetensors"`，执行结果为`1 failed, 11 passed`。预期回归契约同步确认旧FLUX.1厚涂映射不存在，实际测试仍要求旧映射存在。
- 根因及同类风险排查：生产实现与新Klein9B接入目标一致，失败根因为关联测试契约未随旧FLUX.1厚涂链退出同步更新；同一专项测试已明确断言旧映射不存在，两套测试当前互相矛盾。未发现四类选择、命令参数、权重门禁或正式服务异常。
- 测试命令：`.venv/bin/python -m pytest -q tests/unit/test_flux2_klein9b_houtu_loras.py tests/unit/test_image_job_recovery.py`；动态调用`_klein9b_houtu_loras`覆盖女性、男性、灵兽、场景及大小/SHA/启用门禁；`curl -fsS --max-time 5 http://127.0.0.1:8787/api/health`。
- 下一状态：待处理

#### 最终代码稽查记录

- 验证人：代码稽查
- 验证时间：2026-08-10
- 验证结果：通过
- 模型实物：活动目录严格为5个BF16 Safetensors权重；大小与SHA-256逐项匹配索引，Tensor键数为224、224、288、224、64，键结构与FLUX.2 Klein适配器一致；前三项及男性项元数据明确指向`flux2_klein_9b`，女性与灵兽项由真实9B加载出图元数据及FLUX.2键结构交叉确认。
- 分类与隔离：风格2、女性1、男性1、灵兽1的路径及文件名前缀一致；5项均为`tested_candidate`且总索引`production_enabled=false`，未进入商用索引。活动目录FLUX.1权重为0，旧5项FLUX.1仅位于`data/cache/retired_loras/国风厚涂/`；生产扫描仅匹配FLUX.1商用/明确批准文件，不会选取本批FLUX.2“仅测试”候选。
- 真实样图：5张PNG均可解码，尺寸分别符合4张512×768与灵兽768×512；PNG生成元数据逐张记录`mlx-community/flux2-klein-9b-8bit`、原生9B基座、对应LoRA路径、种子、步数、精度和生成耗时。女性样图为女性、男性样图为男性；古代幻想图符合低对比电影CG厚涂候选，其余平涂、伪文字或普通犬类缺陷与索引结论一致，均未伪装为生产合格项。
- 测试与文档：专项测试只读复跑`2 passed in 0.48s`，下载脚本编译通过；索引、README、`Dev_MainDev.md`、项目记忆与BUG软件测试14/14证据一致，未发现回归或伪测试。
- 最终状态：已关闭

- 后续生产接入整改复测：通过。合并回归12/12通过，旧`test_all_asset_baselines_use_local_flux1_schnell_gguf`已改为`test_asset_baselines_use_style_specific_local_models`，明确国风浅涂继续使用FLUX.1 Schnell、国风厚涂禁止旧FLUX.1映射并使用Klein9B LoRA分流；后端Python编译通过。
- 动态复核：女性、男性、灵兽、场景分别准确选择“风格+女性”“风格+男性”“风格+灵兽”“仅风格”，权重为0.9/0.72/0.75；大小篡改与SHA篡改均被门禁拒绝；活动国风厚涂目录FLUX.1权重为0；正式8787返回healthy且进程路径属于当前项目。
- 状态：待稽查

- 稽查退回整改软件复测：通过。索引与下载脚本5项`production_approved`严格为`[true,false,false,false,false]`，唯一批准项为“风格_古代幻想厚涂”；绘画风格、女性、男性、灵兽4项均为false。女性、男性、灵兽、场景四类动态调用均只返回唯一批准风格LoRA，未批准的人物与灵兽权重未进入生产命令；生产命令仍携带批准项的`--lora-paths`与`--lora-scales`。
- 回归证据：`tests/unit/test_flux2_klein9b_houtu_loras.py`与`tests/unit/test_image_job_recovery.py`合并回归12/12通过；后端与下载脚本Python编译通过；5文件大小及SHA-256门禁、活动目录无FLUX.1、文档批准说明均保持通过；正式8787返回healthy，PID 32898为当前项目兼容服务。
- 状态：待稽查

#### 后续生产接入代码稽查记录

- 验证人：代码稽查
- 验证时间：2026-08-10
- 验证结果：不通过
- 已通过项：正式命令构造同时携带`--lora-paths`和`--lora-scales`；女性为风格0.9+女性0.72，男性为风格0.9+男性0.72，灵兽为风格0.9+灵兽0.75，场景仅风格0.9；每次选择前执行文件大小和SHA-256校验，总启用门禁有效；旧国风厚涂FLUX.1映射已清除且活动目录FLUX.1为0。合并回归只读复跑`12 passed in 0.93s`，Python编译通过；正式8787为当前项目PID 32334并返回healthy。
- 严重问题1：接入违反同一BUG既有验收结论和项目文档。索引中绘画风格、女性、男性、灵兽的`visual_test`分别为平涂/伪文字、平涂、平涂、非神兽失败；`Dev_MainDev.md`、项目记忆和目录README均明确仅古代幻想风格达到候选标准，其余禁止进入生产。当前将总开关改为`production_enabled=true`后，正式选择函数会实际加载女性、男性和灵兽失败权重。
- 严重问题2：正式链路启用了许可未公开的男性权重和`other/unpublished`灵兽权重；此前软件测试及最终稽查明确要求这两项保持测试隔离。当前启用门禁只有全局布尔值，没有逐模型生产批准、视觉验收和许可证门禁。
- 测试问题：12/12测试把全局`production_enabled=true`及四类候选被选中直接作为成功条件，未断言逐模型`visual_test`、许可证和生产批准状态；测试通过不能证明生产合规，与文档口径相反。
- 整改标准：生产选择只能加载逐项具备明确生产批准、合格视觉验收及可用许可证的权重；未通过视觉验收或许可未公开项必须保持隔离且不得进入命令。建立逐模型启用字段及失败关闭门禁，补充拒绝未批准/未合格/许可不明权重的动态测试，并同步代码、索引、README、开发计划和项目记忆后重新经过软件测试。
- 验证证据：动态只读调用确认女性、男性、灵兽正式选择均包含各自此前失败候选；索引仍记录`failed_thick_paint_too_flat`、`failed_not_mythical_beast`及`unpublished`许可；文档仍声明后四项禁止生产。
- 最终状态：待处理

#### 后续生产接入最终复核记录

- 验证人：代码稽查
- 验证时间：2026-08-10
- 验证结果：通过
- 复核结论：索引5项逐模型`production_approved`严格为`[true,false,false,false,false]`，唯一批准项为已通过视觉验收的古代幻想风格；正式选择函数先执行总启用与逐模型批准门禁，再执行大小和SHA-256校验。女性、男性、灵兽和场景四类动态调用均只返回古代幻想风格0.9，未批准的绘画、女性、男性和灵兽权重均未进入命令。
- 命令与回归：正式9B生成仍真实传递批准权重的`--lora-paths`与`--lora-scales`并返回LoRA审计元数据；旧国风厚涂FLUX.1映射保持清除。合并回归只读复跑`12 passed in 0.75s`，后端及下载脚本编译通过。
- 运行与文档：正式8787为当前项目PID 32898并返回healthy；索引、README、`Dev_MainDev.md`、项目记忆和同一BUG均明确仅古代幻想风格获准生产，其余4项继续测试隔离，口径一致。
- 最终状态：已关闭
### BUG-20260810-007：对话框图片反推返回提示词字段模板

- 状态：已关闭（最终稽查通过）
- 测试范围：对话框上传图片反推、`POST /api/vision`、图片超分、PuLID/ReActor入口、MuseTalk、RealESRGAN与RIFE前后端接线。
- 测试结果：不通过。专项单元测试18/18通过；真实图片反推失败。
- 复现：向`POST /api/vision`提交真实PNG的Base64，`prompt`为“请反推这张图片的完整生图提示词和负面提示词”。接口返回HTTP 200，但`description`固定为“正向提示词：主体；年龄性别；五官发型……负面提示词：与画面冲突的主体……”，没有输出该图片的实际人物、场景、颜色、光影或画风。
- 预期：返回依据上传图片提取的具体正向提示词与负面提示词；实际：直接返回JSON示例中的字段模板，用户无法使用反推结果生图。
- 精确位置：`plugins/builtin/short_drama/backend/compat_server.py`的`_ollama_vision()`反推二次整理；前端调用链位于`plugins/builtin/short_drama/frontend/App.vue`的`inspectAsset()`和`processAssistantMessage()`。
- 已通过证据：`tests/unit/test_optional_media_enhancements.py`、`tests/unit/test_short_drama_media_pipeline.py`、`tests/unit/test_image_job_recovery.py`合计18项通过；`POST /api/images/upscale`真实生成1080×1920 PNG；`POST /api/images/identity-refine`的ReActor模式真实生成928×1664 PNG；ComfyUI枚举到RealESRGAN x4、RIFE 4.9、MuseTalk、PuLID与ReActor节点及所需模型选项；前端存在AI图片超分、PuLID修正、ReActor修正入口，MuseTalk失败后进入LatentSync回退。
- 异常参数证据：图片超分、身份修正、视频增强、MuseTalk及空图片反推在缺失媒体或图片时均返回HTTP 502和明确中文错误，未出现服务崩溃。
- 下一状态：退回主线开发。

- 整改复测：不通过。真实PNG调用`POST /api/vision`返回HTTP 200，已输出该图具体人物、青白服装、白发蓝眼、灰色背景、明亮光线和传统中国风格，原功能缺陷已修复；但相关专项回归为17通过、1失败。失败项`tests/unit/test_optional_media_enhancements.py::test_chat_reverse_prompt_is_bounded_and_structured`仍断言修复前固定模板字符串`"prompt":"主体；年龄性别；五官发型；服装配饰`必须存在，当前后端已移除该模板，测试契约未同步。
- 当前状态：待处理；需同步反推专项测试后重新复核。

- 最终软件测试：通过。更新后的反推专项、媒体流程、图片恢复与图片任务运行时组合31/31通过；此前真实PNG复核已确认`POST /api/vision`返回HTTP 200，并输出图片具体人物、服装、背景、光线、画风及负面提示词，不再返回字段模板。
- 当前状态：待稽查。

#### 主线修复记录

- 修复时间：2026-08-10
- 修复内容：反推视觉阶段改为直接、具体的图片观察指令；二次整理禁止复述字段名和占位模板，并增加模板结果检测与视觉证据回退。
- 真实验证：同一真实PNG重新调用`POST /api/vision`返回HTTP 200，正向提示词包含年轻东亚女性、黑色直发、蓝色服装、正面站立、纯白背景、柔和漫射光和数字艺术质感，负面提示词按该画面生成，不再返回字段模板。
- 下一状态：提交软件测试复核。

#### 最终稽查记录

- 稽查时间：2026-08-10
- 稽查结果：通过。
- 反推链路：对话框上传图片已接入`POST /api/vision`；输入最多4帧并缩放至768像素，真实PNG复测已返回具体人物、服装、背景、光线、画风及负面提示词，未再返回字段模板。
- 增强链路：图片超分使用RealESRGAN x4并输出独立1080×1920文件；视频增强使用RealESRGAN x4与RIFE 4.9；原始媒体未被覆盖。
- 身份链路：PuLID与ReActor均为按需按钮，前后端接口接通；输入临时文件使用UUID隔离并在结束阶段清理，ComfyUI任务结束释放模型。
- 口型链路：生产流程优先调用MuseTalk，失败后调用LatentSync-1.6；两条链路的模型标记与版本标记一致。
- 运行证据：8787健康检查通过，8194队列为空；MuseTalkRun、RIFE VFI、RealESRGAN、PuLID与ReActor节点均已加载；专项、媒体、恢复与任务运行时组合回归31/31通过。
- 最终状态：已关闭。
### BUG-20260811-042：机器人缺少真实联网搜索能力

- 状态：已关闭（最终稽查通过）。
- 最终稽查：业务、质量、安全及流程复核全部通过；原句真实回答仅采用SenseNova U1、Flux.2 Klein、GLM-Image并按发布日期倒序，LLM调用0。专项147 passed/1 skipped/3 subtests，全unit543 passed/1 skipped/9 subtests，pycompile+compileall、Vue typecheck、Vite 83 modules通过。
- 根因：`/api/assistant` 只调用本地模型，没有搜索意图路由、搜索提供方、来源证据、失败阻断或审计字段，因此会用过时参数回答“最新/许可”等问题。
- 框架整改：新增统一 `web.search` 能力、三提供方路由、来源约束提示、引用与审计、SSRF/协议/体积/超时门禁；搜索失败禁止无来源回答。
- 主线证据：真实网络检索 LangGraph 返回官网/GitHub/官方文档；专项6项、全unit 501 passed/1 skipped/9 subtests；py_compile、Vue typecheck、Vite 83 modules通过。
- 独立软件测试首败：真实公网搜索通过，查询`LangGraph official documentation GitHub`由`bing-html`返回3条非空可核验来源（LangChain官网、GitHub、官方文档），并携带query/provider_id/searched_at；专项`6 passed`。但真实临时HTTP调用`GET /api/assistant/capabilities`返回的`web_search.providers`仅列Brave与DuckDuckGo，遗漏实际已接入且本次真实使用的Bing后备，能力接口与三提供方真实路由不一致。按首败规则立即停止，未继续assistant时效/失败阻断/普通对话、SSRF完整矩阵、全unit、Python编译、Vue typecheck或Vite构建；未调用本地模型、未启动重模型、未修改业务代码。下一状态：待处理。
- 能力接口整改后独立软件复测：通过。真实公网再次检索LangGraph，`bing-html`返回LangChain官网、GitHub与官方文档3条来源；能力接口由`WEB_SEARCH_PROVIDER_DESCRIPTIONS`单一事实源动态披露Brave优先、DuckDuckGo第一后备、Bing第二后备。真实临时HTTP验证时效问题严格search→LLM，响应含sources/query/provider/searched_at；显式true强制搜索、显式false关闭搜索、普通对话不联网；搜索失败返回HTTP502且本地模型调用0次。Brave有Key优先及失败→DDG无结果→Bing回退专项通过。SSRF/回环/localhost/私网/链路本地/IPv6/非HTTP矩阵`10/10`，重定向/响应类型/1MB体积`3/3`，provider host白名单`3/3`；能力注册、前端thinking及响应契约通过。专项与兼容回归`141 passed, 1 skipped, 3 subtests passed`，完整单元测试`501 passed, 1 skipped, 9 subtests passed`；关键Python文件编译、Vue typecheck和Vite生产构建通过（83 modules，574ms）。未调用真实本地模型、未启动重模型、未修改业务代码。下一状态：待稽查。
- 用户真实回答质量退回：问题“最新开源的文生图模型是哪个”错误引用Google Translate与Tamil输入站。根因是中文查询未领域化，且旧链只验证来源存在而不验证来源与问题相关。整改新增中英查询归一、image/open-source主题相关性门禁、Google News日期证据、发布时间排序；时效回答改为确定性列举证据，标题未写型号时禁止模型猜测。真实HTTP复现已不含翻译/Tamil站点；主线专项9/9、全unit521 passed/1 skipped/9 subtests，pycompile/typecheck/83模块构建通过。状态：待独立软件测试。
- M9.194稽查整改独立复测首败：逐跳禁重定向确定性用例通过，provider首跳返回`Location: http://127.0.0.1:8787/private`时仅发生1次open、第二次open为0；198.18/15仅注册provider transport可通过，任意结果域名解析到该网段仍被private_network拒绝，定向`3/3`通过。但紧接着从当前冻结快照执行真实公网`search_web({query:"LangGraph official documentation GitHub",count:3})`时，DuckDuckGo与Bing均返回`no_results`，最终抛`all_search_providers_failed`，未取得任何可核验来源，真实联网验收失败。按首败规则立即停止，未继续citation/搜索意图/显式开关、全安全矩阵、全unit、Python编译、Vue typecheck或Vite构建；未调用本地模型、未启动重模型、未修改业务代码。下一状态：待处理。
- 公网可用性整改后独立复测首败：连续3次真实公网查询均由`bing-html`稳定返回3条非空来源（LangChain官网、GitHub、官方文档），真实公网稳定性`3/3`通过。但专项`tests/unit/test_web_search_assistant.py::test_search_provider_falls_back_and_returns_auditable_sources`仍要求attempts仅为Brave、DuckDuckGo各1次，正式框架已改为每provider有限2次，实际attempts为Brave×2、DuckDuckGo×2，断言失败；专项汇总`1 failed, 7 passed`。当前测试契约未同步M9.194重试边界，冻结快照无法全绿。按首败规则立即停止，未继续DoH/逐跳/citation/意图全矩阵、全unit、Python编译、Vue typecheck或Vite构建；未调用本地模型、未启动重模型、未修改业务代码。下一状态：待处理。
- 最新冻结快照独立软件复测：通过。连续3次真实公网搜索均由Bing RSS稳定返回LangChain官网、GitHub与官方文档3条来源；结构化注册表按Brave→DuckDuckGo→Bing→Google顺序统一ID、描述、hosts、handler、env，所有provider最多2次且attempt审计准确。逐跳私网Location仅1次open、第二次0；198.18/15只允许注册provider transport，结果域通过禁重定向dns.google DoH取得全公网权威地址才放行，DoH空结果/私网答案`3/3`失败关闭。SSRF/localhost/回环/私网/链路本地/IPv6/非HTTP`10/10`，响应类型/1MB体积`2/2`，provider registry schema/order`4/4`。真实临时HTTP验证当前项目/当前任务本地问句不联网`2/2`，语言显式联网和按钮显式true强制搜索`2/2`，无有效citation四种情况均HTTP502且不自动附来源，搜索全失败HTTP502且LLM调用0。能力接口单一事实源、前端联网按钮/thinking/结果契约通过。专项兼容`143 passed, 1 skipped, 3 subtests passed`，完整单元测试`509 passed, 1 skipped, 9 subtests passed`；关键Python文件编译、Vue typecheck和Vite生产构建通过（83 modules，540ms）。未调用真实本地模型、未启动重模型、未修改业务代码。下一状态：待稽查。
- 非阻断安全硬化最终独立复测：通过。`_public_http_url(..., allow_managed_proxy=True)`自身强制hostname属于结构化provider hosts，attacker/result/localhost任意域拒绝`3/3`，Brave/DuckDuckGo/Bing/Google注册host放行`4/4`；无需依赖调用方保持安全。真实公网连续搜索再次`3/3`，每次Bing RSS返回同一组3条官方来源。assistant最终矩阵为当前项目不联网`1/1`、显式按钮强制`1/1`、无有效citation失败关闭`4/4`、搜索失败LLM零调用`1/1`；专项兼容`143 passed, 1 skipped, 3 subtests passed`。完整单元测试最新为`519 passed, 1 skipped, 9 subtests passed`；关键Python文件编译、Vue typecheck和Vite生产构建通过（83 modules，533ms）。三流程单一M9.194当前主线状态保持软件测试通过待稽查；未调用真实本地模型、未启动重模型、未修改业务代码。最终状态：待稽查。
- 用户真实回答质量整改独立复测首败：原句`最新 开源的文生图模型是那个?`真实临时HTTP通过，生成英文领域query`"open-source" "image generation" model`，由`google-news-rss`返回6条按published_at降序的相关来源；Google Translate/Tamil/字体站为0，所有来源均含image与open-source语义，时效回答LLM调用0，明确“仅凭最新无法安全断言唯一型号”，回答中的标题与URL逐项对应sources。相关性矩阵非法`4/4`拒绝、合法`1/1`接受，专项兼容`144 passed, 1 skipped, 3 subtests passed`。但继续复跑此前要求的真实公网连续稳定性时，首轮`LangGraph official documentation GitHub`查询即失败：DuckDuckGo两次HTTPError、Bing两次no_results、Google News一次URLError一次no_results、Google HTML两次no_results，最终`all_search_providers_failed`；未达到真实公网连续`3/3`。按首败规则中断正在扩大的全unit（中断前`242 passed, 6 subtests passed`），未执行Python编译、Vue typecheck或Vite构建；未调用真实本地模型、未启动重模型、未修改业务代码。下一状态：待处理。
- 公网异常恢复框架整改后独立复测：通过。原句真实HTTP继续生成英文领域query，返回按时间排序的相关开源图像生成来源，翻译/Tamil/字体站为0、时效回答LLM调用0、无法确认唯一型号且reply与sources逐项一致。全新空缓存下LangGraph真实连续`3/3`均由`github-api`实时返回，首条严格为`langchain-ai/langgraph`且`cache_hit=false`。全provider模拟失败后，同query+count有效缓存恢复成功并含`cache_hit=true/live_attempts=10/provider_id=cache:github-api`；跨query、过期、损坏JSON、失效私网URL均失败关闭`4/4`。六provider结构化事实源、SSRF/协议/managed-proxy安全矩阵通过。专项兼容`145 passed, 1 skipped, 3 subtests passed`，完整单元测试`525 passed, 1 skipped, 9 subtests passed`；关键Python文件编译、Vue typecheck和Vite生产构建通过（83 modules，557ms）。未调用真实本地模型、未启动重模型、未修改业务代码。下一状态：待稽查。
- 最终稽查五项整改独立复测首败：用户原句真实HTTP质量链通过，query为`"image generation" "open-source" latest 2026 model official release`，Google News严格返回SenseNova U1（2026-04-30）、Flux.2 Klein（2026-01-16）、GLM-Image（2026-01-14）三项并按日期降序，工具/客户端/提示库为0、LLM调用0。随后以全新空缓存验证明确`LangGraph official documentation GitHub`时，GitHub API真实两次返回HTTPError，框架降级到`bing-html`；结果首条为LangChain官网而非`langchain-ai/langgraph`，provider也不是`github-api`，未满足“明确LangGraph仍GitHub官方且连续3次首条官方仓库”的验收。该失败同时证明repository_updated_at路径本轮未能取得真实GitHub证据。按首败规则立即停止，未继续附加条件、缓存审计透传、全部安全缓存恢复、专项、全unit、Python编译、Vue typecheck或Vite构建；未调用真实本地模型、未启动重模型、未修改业务代码。下一状态：待处理。
- 纠正验收契约后最终独立复测：通过。GitHub匿名API允许合法限流并自动降级，不再强制provider或首条固定仓库；全新空缓存真实公网连续`3/3`成功，每次至少包含`langchain-ai/langgraph`权威来源。确定性模拟GitHub HTTP403时，两次失败均写入`attempts`，DuckDuckGo两次`no_results`同样可审计，随后Bing后备成功。用户原句质量、附加条件保留、同查询短TTL缓存恢复与`cache_hit/cache_recovered_at/live_attempts`透传、跨查询/过期/损坏/失效URL失败关闭、六provider事实源及安全矩阵由专项与全量回归覆盖。状态冲突测试机制修复点`1 passed`；专项兼容`147 passed, 1 skipped, 3 subtests passed`；完整单元测试`543 passed, 1 skipped, 9 subtests passed`。关键Python文件`py_compile`及后端`compileall`通过，Vue typecheck通过，Vite生产构建通过（83 modules，582ms）。未调用真实本地模型、未启动重模型。最终状态：软件测试通过，待稽查。
### BUG-20260811-043：被代际围栏拒绝的旧事件仍污染LangGraph持久事件快照

- 状态：已关闭（最终稽查通过）
- 关联任务：M9.195
- 现象：`apply_event`会拒绝旧`projection_revision`或旧`stage_generation`对阶段生命周期的覆盖，但LangGraph在进入节点前已把本次输入写入顶层`event`；拒绝分支未恢复旧值，导致持久`event`、重启恢复authority核对和导演故障决策仍读取被拒绝的旧owner信息。已有正代际后，无代际 legacy 回调也可覆盖阶段状态。
- 根因：阶段状态、revision和generation具备围栏，承载同一事实的事件payload却没有独立的“已接受事件”持久槽；拒绝只返回空revision/generation差量，不能撤销输入合并。
- 修复：LangGraph状态新增`accepted_event`及按stage保存的`stage_events`；事件通过双围栏后原子更新生命周期、代际、revision和事件快照，任一围栏拒绝时恢复最近一次已接受事件。已有正代际时，缺失/零代际事件按旧代拒绝，禁止无围栏回调降级权威阶段。
- 开发验证：新增旧revision、旧generation、无generation、跨stage及SQLite重载动态用例；专项与关联`110 passed, 1 skipped`，完整单元测试`507 passed, 1 skipped, 9 subtests passed`。未启动重模型或操作正式任务。
- 软件测试退回整改：事件接受顺序改为先比较`stage_generation`；更高代无条件建立新revision序列并允许`4/10 -> 5/1`，revision只在同代内严格递增。旧代、已有正代后的零代、同代旧/相等/缺失revision均恢复最近权威事件；新代revision为0时显式重置旧代revision，避免后续同代首个revision被旧代数值阻断。
- 整改开发验证：未来高代低revision、同代revision单调、旧代、零代、跨stage、SQLite reload及两个独立orchestrator实例共享checkpoint共`7 passed`；完整单元测试`525 passed, 1 skipped, 9 subtests passed`。Python编译、Vue typecheck与83模块Vite生产构建通过。扩大首轮仅出现已知资源池queued线程观测瞬态，单项立即复跑及随后完整unit均通过。未启动模型或正式任务。
- 第二轮复测退回整改：新代`revision=0`首次接受后，不再以`current_revision`真假判断是否已有序列，而以该stage是否已有accepted event判断；正代际已有事件时，同代重复/缺失`revision=0`均拒绝，`revision=1`唯一推进。真正缺少`stage_events`的旧checkpoint允许当前owner首个事件建立迁移基线，此后立即执行严格单调。
- 合法阶段调用同步：run-stage开始固定新代revision 0，成功/失败提交固定revision 1；后续确认、台账协调与重启恢复从Graph当前代际读取并提交`current revision + 1`，避免严格围栏阻断真实终态。资源池并发测试增加等待排队线程真实入队的确定性同步，消除测试自身调度竞态。
- 第二轮整改验证：revision0首个/重复/缺失/推进及旧checkpoint迁移在内事件专项`9 passed`，阶段终态/authority恢复关联`15 passed`，完整单元测试`543 passed, 1 skipped, 9 subtests passed`；Python编译、Vue typecheck及83模块构建通过。未启动模型或正式任务。
- 下一状态：待独立软件测试复测
- 扩大验证：LangGraph与短剧生产集成、生产控制、原子authority提交及恢复关联首轮出现既有资源池线程排队观测瞬态失败，立即单测复跑通过，冻结组合复跑`117 passed, 1 skipped`；Python编译、Vue typecheck及83模块Vite生产构建通过。
- 独立软件测试首败：更高`stage_generation`携带从新代重新计数的较小`projection_revision`时，当前`apply_event`先执行全局revision比较并直接拒绝。确定性动态从`generation=4/revision=10/request_id=old`提交`generation=5/revision=1/request_id=new`后，状态仍为`running/generation=4/revision=10/event.request_id=old`，新owner事件未获接受。revision必须只在同一generation内保持单调；更高generation应建立新的权威代际并接受其revision。按首败规则停止，未执行其余矩阵、全unit、编译、前端类型检查或构建；未启动模型、未操作正式服务。
- 下一状态：修复代际优先比较后重新独立软件测试。
- 最新独立软件复测：通过。generation/revision事件围栏、阶段取消、authority原子提交、项目恢复及文档状态关联`132 passed`；完整unit`554 passed, 1 skipped, 9 subtests passed`，唯一初始skip为Node运行时未在默认PATH，补充项目既有Node后对应动态文件`23 passed`。关键Python编译、Vue typecheck及83模块生产构建通过。测试仅使用临时SQLite/checkpoint，未启动模型、未修改正式数据；下一状态为待只读稽查。
- 最终只读稽查：通过。generation第一所有权围栏、同代revision严格单调、新代revision 0唯一基线、legacy checkpoint一次迁移、被拒事件权威恢复及开始/终态/确认/恢复调用方递增均与统一生产内核规范一致；未发现阻断性功能、并发、持久化、兼容或证据缺陷。
- 关闭时间：2026-08-11（Asia/Shanghai）。
- 下一状态：已关闭。
