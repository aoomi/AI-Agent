# AI 主线开发计划

版本：2.3
生效日期：2026-08-07  
适用对象：主线开发 AI
职责与完成门禁：统一以 `AGENTS.md` 为准。

## 使用规则

- 本文件只记录里程碑、当前状态和开发证据，不重复定义通用职责。
- 当前问题只以文件顶部最新未关闭条目和同编号 `Dev_BUG_TRACKER.md` 记录为执行依据。
- 当前问题与排队状态唯一从 `docs/product/当前开发状态.md` 读取；本文件只保留里程碑计划和证据。
- 标记为“历史、已覆盖、已关闭、已完成”的条目仅供追溯，不得作为现行需求或下一任务自动执行。
- 同一里程碑存在多轮记录时，以日期最新且通过完整测试、稽查闭环的记录为准；状态冲突时以 `Dev_BUG_TRACKER.md` 为准。
- 当前问题完成后停止，等待用户确认下一条；禁止从历史条目自动挑选任务。
- 未经用户对具体界面改动的明确允许，主力开发不得在界面上新增、删除、移动、改名或修改任何元素，也不得改动现有布局、文案、样式和交互；功能开发本身不构成界面改动授权。
- 新增功能如确需界面入口，只允许增加该功能对应的按钮，不得连带新增或修改其他界面内容；按钮以外的任何界面改动必须另行取得用户明确允许。

## GitHub 推送机制

- 开发分支：`develop`，禁止直接推送 `main`。
- 流程：开发 → 测试 → 稽查 → 更新文档 → 提交 → 推送 `develop`。
- 推送前必须：检查 `status`/`diff`；排除密钥、Token、环境变量、模型权重、运行数据、缓存、虚拟环境和生成产物；仅提交任务相关文件；使用中文提交说明；核对本地与远端一致。
- 禁止推送：测试或稽查未通过；存在合并冲突、认证失败、远端未知提交或敏感文件。
- 未经批准禁止：合并或推送 `main`、强制推送、改写历史、删除远端分支、创建标签和 Release。
- 仅当用户明确说“发布正式版”后，才执行：`develop` 回归测试 → 最终稽查 → 合并 `main` → 推送 `main` → 创建标签 → 发布 Release。
- 稽查身份只负责核验推送门禁并给出结论；稽查通过后，由主力开发提交并推送。

**开始持续开发**：持续执行当前项目任务。每项任务开发 → 测试 → 稽查闭环后自动推送 `develop`。完成一项继续下一项，直到用户说停下。严格执行 GitHub 推送机制。

**临时立即推送**：检查本地变更，排除敏感文件；测试、稽查通过后提交并推送 `develop`，不操作 `main`。

### M9.198：真实全链路成片生产验收（主线开发中）

- BUG072架构横向稽查第一项整改：基础设施extension provider原可在工厂创建进行中被卸载、禁用、替换或切换；现按point/provider维护inflight并对五类变更失败关闭，候选探针后删除前二次复核。关联`145 passed`；继续其余v2.2契约入口稽查。
- BUG072第二项稽查已确认原子边界首败：ProductionLedger与LangGraph当前使用两个SQLite文件和两条独立连接，`commit_callback`不能构成同一写事务；现有回滚测试未覆盖Graph已提交后台账提交失败。进入同库同连接事务、旧checkpoint迁移及故障注入整改。
- BUG072第二项整改闭环：LangGraph checkpoint/writes与ProductionLedger统一数据库及同一事务连接，旧独立Graph库幂等迁移且保留；Graph完成写入后故障注入证明图与台账同步回滚。composition/review/export和upscale均接线，关联`208 passed`；继续横向稽查。
- BUG072第三项整改：可观测脱敏由敏感键扩展到核心Prompt、账号类键以及中性字符串内Bearer/Basic、常见token和完整手机号；logger、指标、快照、JSONL和Prometheus共享递归门禁。专项`7 passed`，继续横向稽查。
- BUG072第四项整改：视频`waiting_memory`准入统一要求本地资源空闲且Comfy running/pending双队列为空，不可达失败关闭；初次请求与持久恢复共用，Graph仍只接收queued投影。关联`120 passed`，继续横向稽查。
- BUG072第五项整改：LangGraph阶段executor新增inflight围栏，运行中replace/disable/unregister统一拒绝，自然终态后允许变更；关联`101 passed`，继续横向稽查。
- BUG072第六项整改：启动恢复不再把waiting_memory误判为中断生成并失败化；保留持久queued子状态、清运行标识，交由Comfy释放门禁重准入。关联`122 passed`，继续横向稽查。
- BUG072第七项整改：base导出删除legacy缺证默认值，与enhanced一致强制非空权威生产/审核证据；缺证在导出前失败关闭。关联`56 passed`，继续横向稽查。
- BUG072第八项整改：ProductionLedger通用upsert及非upscale projection补齐expected_revision CAS，与upscale路径一致在事务内拒绝旧快照覆盖；关联`164 passed`，继续横向稽查。
- BUG072第九项整改：视频结果查询的job_id分支补齐tenant/user/project完整所有者过滤，空身份拒绝且异主查询无恢复副作用；关联`103 passed`，继续横向稽查。
- BUG072第十项整改：运行任务读取端点由可选过滤改为tenant/user/project完整身份门禁，阻断空查询全表泄露及部分身份扩大读取；前端既有完整身份调用无需修改，关联`92 passed`，继续横向稽查。
- BUG072第十一项整改：项目版本读取与列表在访问历史快照前补齐当前tenant/user/project所有权门禁，阻断仅凭project/version ID跨所有者读取完整快照；关联`93 passed`，继续横向稽查。
- BUG072第十二项整改：3D任务状态查询由仅凭job UUID改为tenant/user/project完整所有者过滤，异主查询不再读取请求、进度或候选结果；轮询调用同步身份，关联`108 passed`，继续横向稽查。
- BUG072第十三项整改：系统AI任务状态补齐tenant/user/project/session四字段所有者门禁，与创建时持久context精确匹配，阻断跨项目及旧会话UUID读取；关联`88 passed`，继续横向稽查。
- BUG072第十四项整改：图片结果查询补齐tenant/user/project完整所有者过滤，阻断同名资产或已知job UUID跨项目读取及异主孤儿恢复副作用；五个调用点同步身份，关联`108 passed`，继续横向稽查。
- BUG072第十五项整改：平台通用任务队列由仅tenant隔离提升为tenant+identity双重隔离，列表、详情、取消和恢复统一拒绝同租户异身份任务；关联`12 passed`，继续横向稽查。
- BUG072第十六项整改：ProductionCapability运行中禁用或降健康补齐inflight围栏，与替换/卸载一致等待自然终态；关联`92 passed`，继续横向稽查。
- BUG072第十七项整改：系统AI启动强制tenant/user/project/session完整身份，request_id幂等由全局裸查收敛为同所有者命中，阻断异主领取旧job UUID；关联`89 passed`，继续横向稽查。
- BUG072第十八项整改：系统AI任务由状态读取时伪造当前心跳改为执行期每5秒持久真实心跳，成功/异常终态统一停止；关联`90 passed`，继续横向稽查。
- BUG072第十九项整改：平台实时任务事件投影补齐identity_id存储键与读取过滤，与队列隔离一致拒绝同租户异身份进度读取；关联`16 passed`，继续横向稽查。
- BUG072第二十项整改：provider调用审计记录和查询补齐user_id强制所有者作用域，阻断同租户同项目异用户共享费用与产物证据；关联`5 passed`，继续横向稽查。
- BUG072第二十一项整改：系统AI重启恢复不再自动重放已running且可能产生副作用的Codex任务，仅queued重启；running明确失败并要求显式重试，关联`91 passed`，继续横向稽查。
- BUG072第二十二项整改：助手历史、草稿和会话的共享JSON读改写统一进入RLock事务，阻断并发不同会话最后写覆盖；关联`91 passed`，继续横向稽查。
- BUG072第二十三项整改：资源列表、媒体读取、创建和删除共享JSON访问统一进入RLock，阻断并发资源读改写最后写覆盖；关联`91 passed`，继续横向稽查。
- BUG072第二十四项整改：助手历史、草稿和会话四路在访问共享存储前强制tenant/user/project/session完整，阻断空段共享键串线；关联`92 passed`，继续横向稽查。
- BUG072第二十五项整改：主助手、同步系统AI与自动路由执行入口统一在模型/搜索/子进程前校验完整tenant/user/project/session；关联`91 passed`，继续横向稽查。
- BUG071最终闭环：composition、review、export权威证据与Graph状态在同一SQLite事务提交；导出manifest绑定generation、audit batch、视频及manifest哈希。正式三镜静音母版导出8.1秒、243帧、704×1216 H.264且仅video stream，重启后HTTP可读；关联`134 passed`。用户要求的不超过15秒、只验证视频范围已可测试，继续BUG072架构v2.2全仓一致性稽查。
- BUG070最终闭环：普通生产端点门禁移到派发前；worker只接受进程私有loopback token或精确共享reservation，伪造dispatched头正式403，缺前序请求409且无副作用，合法run-stage composition generation 3通过并确认。关联`130 passed`；继续BUG071静音母版审核导出。
- BUG069最终闭环：LTX三镜经正式run-stage与同批次video/audio-not-applicable/subtitle-not-applicable台账确认后，显式video-only composition生成8.1秒、243帧、704×1216@30 H.264静音母版；重启恢复、HTTP媒体与队列归零通过，关联`129 passed`。继续BUG070生产端点派发门禁旁路。
- BUG057按用户更新口径最终闭环：本机LTX-Video 2B Distilled经正式API串行生成3镜，每镜65帧/2.708秒/704×1216/24fps/H.264，仅视频流，总长8.125秒；首中尾9帧无黑屏、结构崩坏或主体消失，三个job均精确登记provider并completed，Comfy队列与任务资源归零。关联`169 passed`；完整unit的8项失败来自用户并行前端改动及既有文本测试隔离，不属于本次视频链。
- BUG061最终闭环：嵌套3D媒体URL在受控根内安全解析，穿越/绝对路径失败关闭；正式H3已越过原文件不存在点并进入真实`h3_rv2v`。直接关联31项、完整599项及9个子测试无失败无跳过。
- 后续正式推理登记BUG062：当前H3 INT8 ConvRot在Darwin/MPS静默落入`_int_mm_cpu`，70分钟仍为0/20；任务已按取消协议收敛且Comfy队列归零，当前整改提供方设备/量化算子兼容门禁与`model_blocked`状态。
- BUG062主线实现：固定制品只准入声明的CUDA设备，MPS/CPU/未知设备在Context IR前持久`model_blocked`并投影LangGraph paused，禁止自动改模。正式job约2秒阻断且两个prompt ID均空；关联159项通过，完整unit当前仅受用户并行前端改动4项失败影响。
- BUG062独立测试与最终稽查通过并关闭：冻结提交关联159项无失败无跳过；兼容白名单、未知设备失败关闭、无重模型副作用、paused投影和显式重放边界一致。BUG057保持真实阻塞，需CUDA兼容H3提供方后才能继续静音源视频与后续成片链。
- BUG062补充稽查退回整改：公共能力表原仍发布H3 provider健康；现与同一设备契约接线，MPS/CPU/未知注册为unhealthy并公开CUDA白名单及阻断原因。正式能力接口已验证，关联160项通过，待独立复测与复稽查。
- BUG062补充独立复测与只读复稽查通过并重新关闭：提交`2a94278`关联160项无失败无跳过，正式能力接口unhealthy/CUDA白名单/MPS原因断言通过；注册表与业务准入状态一致。

- BUG060最终闭环：正式Ref2VA已实际调用精确注册的`h3-prompt-writing`并完成Context IR持久输出；关联`33 passed`、完整unit`595 passed, 9 subtests passed`无失败无跳过，供应链与应用态双SHA门禁通过。
- 后续正式H3登记BUG061：`_local_media_path`把多级3D资产`subfolder`截断为末级目录，导致存在且可播放的Blender源视频在H3输入解析时误报不存在；当前只整改受控根内嵌套媒体路径解析。

- 按`docs/product/剩余框架工作清单.md`顺序启动单机V1真实全链验收；目标为新项目从需求/大纲贯穿增强导出，并保存task、provider、版本、指纹、审核批次、资源票据、耗时和manifest证据。
- 同一闭环必须覆盖长媒体阶段停止、服务重启恢复、局部重做、旧代隔离、成片播放/音画/字幕及base/enhanced版本绑定；未取得正式链证据前不得宣称完成。
- 当前仅进入只读盘点与资源核验，排队BUG039—041不分析、不修改。
- 正式首步发现BUG-20260811-046：新项目服务端`stage_state`为空，但创建成功后的前端未加载新项目流程，持续显示旧项目全阶段投影。先修复创建/编辑切换后的项目会话加载与晚到隔离，再继续真实生产。
- BUG046主线整改完成：项目加载先同步清空大纲至导出十阶段投影，创建/编辑保存后等待新project/session流程、资源、任务和版本恢复；正式新旧项目立即切换无旧资产瞬态。定向/contract`45 passed`、全unit`556 passed, 9 subtests passed`、typecheck和83模块构建通过，待独立软件测试。
- BUG046独立软件测试通过：正式连续三轮新旧项目切换的立即/稳定投影均隔离，空新项目stage_state保持空；定向/contract`45 passed`、全unit`556 passed, 9 subtests passed`无skip，typecheck和83模块构建通过，待只读稽查。
- BUG046最终只读稽查通过并关闭：统一十阶段同步清空、创建/编辑新会话加载和晚到session围栏闭环；M9.198继续在隔离新项目执行真实全链。
- 正式停止/恢复首败登记BUG047：大纲停止后UI允许重新生成，但统一工作流已是cancelled，再次运行返回`workflow is cancelled`。当前先修复全阶段一致的重新激活/新代际协议，再继续真实链。
- BUG047主线整改完成：统一`begin`只接受严格更新的stage generation从cancelled恢复，同代、零代及旧代晚到均失败关闭；正式服务重载后同项目新代际真实32B大纲完成并卸载。定向`120 passed`、全unit`558 passed, 9 subtests passed`和编译通过，待独立软件测试。
- BUG047独立测试当前阻塞：定向`120 passed`无skip；完整unit中BUG047及业务回归均通过，但文档门禁因并行BUG038索引/Tracker状态冲突产生3项失败（其余`555 passed, 9 subtests passed`）。未越界修改BUG038，待其事实源收敛后重跑完整unit；当前不得进入稽查。
- BUG047独立软件复测通过：并行状态收敛后，定向`120 passed`、完整unit`560 passed, 9 subtests passed`均无skip；编译、文档门禁和diff-check通过，进入只读代码稽查。
- BUG047首轮稽查仅退回状态口径：索引改用允许值“软件测试通过，待只读稽查”；业务代码与测试未变，重新提交软件测试。
- BUG047最终只读复稽查通过并关闭：新generation恢复、同/旧代拒绝、正式重启生成与资源释放闭环；整改复测完整unit`560 passed, 9 subtests passed`无skip。M9.198继续剧本至增强导出真实链。
- 正式大纲确认进入剧本首败登记BUG048：UI提示大纲已确认，但项目投影、无confirmation的ledger completed与LangGraph pending_confirmation分裂，剧本返回前序未完成。当前整改全部非upscale公开投影的确认/generation权威边界。
- BUG048主线整改完成：非upscale公开projection不能写confirmation/generation/权威证据，无精确现行确认的completed统一降为pending_confirmation；正式坏状态重载后自动收敛，真实32B剧本完成并推进storyboard。关联`135 passed`、全unit`564 passed, 9 subtests passed`及编译/文档门禁通过，待独立测试。
- BUG048独立软件测试通过：关联`135 passed`、全unit`564 passed, 9 subtests passed`无skip，编译、文档门禁及正式权威状态/资源终态复核通过，待只读稽查。
- BUG048最终只读稽查通过并关闭：统一非upscale projection权威边界、确认唯一入口、同代保护和新指纹重确认闭环；正式旧数据收敛及真实剧本通过。M9.198继续分镜脚本。
- 正式分镜完成后登记BUG049：资产正式执行已无租约/任务/模型，但晚到前端`generating`项目投影再次把项目与LangGraph覆盖为`running`；当前整改公开项目阶段投影与服务端generation权威边界。
- BUG049主线整改完成：公开项目阶段写入不再改生产权威；分镜与资产页入口均以项目投影+LangGraph双事实门禁正式assets，结构化JSON仅一次有限重试。正式generation 3恢复至assets pending_confirmation后才生图，暂停后资源全空。关联`110 passed`、全unit`565 passed, 9 subtests passed`无skip、typecheck与83模块构建通过，待独立软件测试。
- BUG049独立软件测试通过：关联`111 passed`、全unit`565 passed, 9 subtests passed`无失败无skip；typecheck、83模块构建、编译、文档门禁及正式assets generation 3/资源终态复核通过，待只读稽查。
- BUG049首轮稽查退回：晚到资产running投影仍可删除正式census的额外资产；主线改为终态下按名称合并资产集合并保留current-only profiles，非资产阶段丢弃整份晚到数据快照，待重新测试。
- BUG049稽查整改开发完成：晚到assets强制按名称合并，保留正式census独有场景/道具及媒体字段；其他阶段保留当前完整权威数据。关联`111 passed`、全unit`565 passed, 9 subtests passed`、typecheck、83模块构建、编译和文档门禁通过，待独立软件复测。
- BUG049稽查整改独立软件复测通过：关联`111 passed`、全unit`565 passed, 9 subtests passed`无失败无skip，typecheck、83模块构建、编译及文档门禁通过，待只读复稽查。
- BUG049最终只读复稽查通过并关闭：公开投影与生产权威隔离，晚到assets保留正式完整census，非assets拒绝整份旧快照；M9.198继续自动资产图片及后续全链。
- 正式资产续跑登记BUG050：道具质检失败已在项目数据保存明确failed/error，但资产卡显示“等待生图”且隐藏原因；当前定位统一结果回填与卡片错误投影。
- BUG050主线整改完成：资产结果轮询不再把真实failed降为pending，共享资产卡主体持续展示错误；关联`134 passed`、全unit`565 passed, 9 subtests passed`、typecheck、83模块构建及文档门禁通过，待独立软件测试。
- BUG050首轮独立测试退回：正式错误已可见，但失败卡无图占位仍显示“等待生图”；共享卡按slide failed统一显示“生成失败”，重新提交测试。
- BUG050退回整改开发完成：failed卡统一显示“生成失败”与错误正文；关联`134 passed`、全unit`565 passed, 9 subtests passed`、typecheck、83模块构建及文档门禁通过，待独立复测。
- BUG050独立软件复测通过：正式失败卡状态与真实错误一致，关联`134 passed`、全unit`565 passed, 9 subtests passed`无失败无skip，typecheck、83模块构建及文档门禁通过，待只读稽查。
- BUG050最终只读稽查通过并关闭：失败终态、失败占位和卡片错误统一，显式重试边界保持；M9.198继续资产图片及后续全链。
- 正式资产重试登记BUG051：道具提取提示同时正向要求笔迹并要求无文字，后端无文字硬门禁使其不可满足；当前整改公共提示词净化契约。
- BUG051主线整改完成：无文字道具进入provider前统一移除正向字形线索并保留材质形态，有限重试复用净化提示；正式“信纸/信件”真实生成成功。关联`135 passed`、全unit`566 passed, 9 subtests passed`、编译/typecheck/83模块构建/文档门禁通过，待独立测试。
- BUG051独立软件测试通过：正式道具waiting_confirmation且媒体存在、错误为空、模型释放；关联`135 passed`、全unit`566 passed, 9 subtests passed`无失败无skip及全部门禁通过，待只读稽查。
- BUG051首轮稽查退回整改：否定词改为必须直接邻接并约束具体文字cue；“带铭文且无人”不能再被无关否定旁路，待重新测试。
- BUG051稽查整改开发完成：逐cue直接否定覆盖前后短语及多段修饰，无关否定不再旁路；关联`135 passed`、全unit`566 passed, 9 subtests passed`及全部门禁通过，待独立复测。
- BUG051稽查整改独立复测通过：关联`135 passed`、全unit`566 passed, 9 subtests passed`无失败无skip，正式产物及资源终态保持，待只读复稽查。
- BUG051最终只读复稽查通过并关闭：逐cue直接否定与无关否定隔离闭环；M9.198继续正式资产队列。
- 正式下一道具登记BUG052：前一Comfy任务调用异步释放后，串行下一任务立即做42GB内存门禁而误失败；当前整改释放完成与下一重任务准入握手。
- BUG052主线整改完成：仅在Comfy近期释放或队列空闲主动释放后进入有限、可取消waiting_memory；非释放窗口立即拒绝。正式三道具连续成功。关联`139 passed`、全unit`570 passed, 9 subtests passed`及全部门禁通过，待独立测试。
- BUG052独立软件测试通过：等待/取消/超时/重启恢复矩阵、正式连续道具与资源终态通过；关联`139 passed`、全unit`570 passed, 9 subtests passed`无失败无skip，待只读稽查。
- BUG052最终只读稽查通过并关闭：accelerator序列化、Comfy空闲释放、有限waiting_memory及失败边界闭环；M9.198继续场景。
- 正式场景登记BUG053：Klein候选子进程退出后job保持processing且heartbeat停止，界面长期生成；当前定位候选后验收/回填监督链。
- BUG053主线整改完成：道具/场景后验收统一纳入图片job阶段、心跳、停止、180秒超时和LLaVA终止释放；正式空房间在生成PID退出后进入scene_validation并持续心跳，最终completed。图片专项`33 passed`、全unit`570 passed, 2 skipped, 9 subtests passed`，Node补测消除跳过来源，编译/typecheck/83模块构建/文档门禁通过，待独立软件测试。
- BUG053独立软件测试通过：关联`87 passed, 3 subtests passed`、完整unit`572 passed, 9 subtests passed`无失败无skip；构建门禁、正式媒体终态和LLaVA释放通过，待只读代码稽查。
- BUG053首轮稽查退回整改完成：验收资源票据不再使用随机audit job等待900秒，统一绑定图片job且与180秒验收同界；停止/超时先取消排队票据再终止活动LLaVA，关闭终态后晚到启动重模型窗口。图片专项`34 passed`、全unit`573 passed, 9 subtests passed`，待独立软件复测。
- BUG053稽查整改独立软件复测通过：关联`88 passed, 3 subtests passed`、完整unit`573 passed, 9 subtests passed`无失败无skip，票据所有权/取消、构建及正式证据通过，待只读复稽查。
- BUG053最终只读复稽查通过并关闭：后验收心跳/停止/有限超时、原job资源票据取消、活动LLaVA终止和晚到隔离闭环；M9.198继续资产确认、3D/视频至增强导出正式链。
- 正式场景恢复确认登记BUG054：原failed资产scope重新激活并确认后lifecycle为completed且confirmation有效，但仍保留旧失败error；当前整改ProductionLedger成功状态转换的错误清理契约。
- BUG054主线整改完成：reactivate、直接completed与confirm统一清除旧失败error，pending显式诊断和真实失败错误保持；正式原场景复确认为completed/error空。台账专项`84 passed`、直接依赖`225 passed, 1 deselected`（仅用户跳过BUG038静态断言），待独立软件测试。
- BUG054独立软件测试通过：台账及直接依赖`225 passed, 1 deselected`无失败无skip，唯一deselect为用户跳过BUG038；正式记录、CAS/回滚、构建门禁通过，待只读稽查。
- BUG054最终只读稽查通过并关闭：成功台账的reactivate/direct-completed/confirm统一清旧error，失败与诊断边界不变；M9.198继续3D及后续正式链。
- 正式场景3D登记BUG055：TripoSR完成后Blender清理仍残留4条非流形边并明确failed；当前只整改场景/道具共享网格修复与审核链。
- BUG055主线整改完成：批量封孔后仅对顶点边界度严格为2的简单闭合环确定性封口，复杂损坏仍由非流形审核失败关闭；同一正式GLB由4条降为0条，正式重试完成并产出7视图及4秒源视频。3D专项`19 passed`、编译通过，待独立软件测试。
- BUG055独立软件测试通过：简单4边环动态封口为0，度4分叉边界保持6条并失败关闭；关联`61 passed`、全unit`576 passed, 9 subtests passed`无失败无skip，唯一deselect为用户跳过BUG038静态断言，待只读稽查。
- BUG055最终只读稽查通过并关闭：共享worker仅封闭严格简单边界环，复杂损坏保持失败关闭；正式场景3D已确认归档不可变版本。M9.198继续道具3D及后续真实链。
- 正式“信纸/信件”3D生成成功后登记BUG056：确认入口将业务原名净化后再比对原始subject key，合法含斜杠资产被误报候选不匹配；当前分离业务身份名与文件安全名。
- BUG056主线整改完成：业务身份原名与路径安全名分离，精确subject比较和路径越界门禁同时保留；原含斜杠候选已正式确认归档。关联`32 passed`及编译/文档门禁通过，待独立软件测试。
- BUG056独立软件测试通过：关联`56 passed`、全unit`581 passed, 9 subtests passed`无失败无skip，唯一deselect为用户跳过BUG038；身份碰撞拒绝、路径安全、正式归档及门禁一致，待只读稽查。
- BUG056最终只读稽查通过并关闭：业务原名精确身份与安全路径组件分界成立，碰撞/越界/旧任务保持拒绝；M9.198继续服装道具3D，H3按用户要求不使用音频输入。
- 三项道具及场景3D均正式确认后登记BUG057：H3无参考音频输入但仍解码自生音轨；当前保留官方节点必需audio VAE，仅移除交付音轨，权威声音继续由后续TTS/口型链产生。
- BUG057静音图实现与关联`81 passed`完成，但正式H3被权威image前序门禁409阻断；该前序正是用户要求跳过的BUG038人物确认链。未绕过门禁、未把静态证据视为真实通过，当前阻塞等待授权或合格正式项目。
- 用户随后授权继续补齐正式image前序；资产页确认“林婉清”0°基准图后，五个Qwen固定角度因上一Comfy权重异步释放窗口被60GB直接门禁连续拒绝，登记BUG058。人物Qwen固定角度及独立修复共用入口已接入既有有限、可取消`waiting_memory`握手，当前处于主线开发验证。
- BUG058主线整改完成待独立软件测试：林婉清左45°正式job已越过原60GB误拒绝并完成Qwen产图，最终只因独立视觉质量门禁失败；后续苏璃左45°也在释放窗口后自然准入。accelerator与Comfy全程单执行体，无并发超卖；完整单元`584 passed, 9 subtests passed`无失败无跳过。
- BUG058独立软件测试通过待只读稽查：定向`168 passed`、完整unit`584 passed, 9 subtests passed`，0失败0跳过；正式任务从内存误拒绝恢复为Qwen执行，资源池保持单accelerator执行体。
- BUG058最终只读稽查通过并关闭：两个60GB Qwen入口共享有限、可取消Comfy释放握手，waiting_memory持久态/图queued投影、超时和非释放窗口边界成立；正式串行任务恢复且不绕过视觉质量门禁。M9.198继续静音H3真实链。
- 正式前序续跑登记BUG059：人物角度Qwen产图后的LLava验收使用随机资源job且不更新原图片job心跳，停止/超时不能精确取消排队票据，并使后续图片内存等待超时。当前只整改人物后验收与原job生命周期的共享边界。
- BUG059主线整改完成待独立测试：人物baseline/固定角度验收统一进入原图片job后验收监督器，三类审核共用原job资源票据、显式身份、可取消心跳与180秒截止。正式job`ef558c27-c3b3-4bef-ad8d-f662fd6a8579`的`character_validation`心跳持续八分钟并以真实质量失败收敛，资源与Comfy队列归零。关联`175 passed, 3 subtests passed`、完整unit`586 passed, 9 subtests passed`无失败无跳过。
- BUG059独立软件测试通过：在提交`430397b`上重跑直接关联`175 passed, 3 subtests passed`和完整unit`586 passed, 9 subtests passed`，均无失败无跳过；编译、文档状态、diff与干净工作树门禁通过，待只读稽查。
- BUG059首轮只读稽查退回：LLava票据边界成立，但后续InsightFace/OpenPose/比例子步骤未共享job deadline，OpenPose Comfy prompt也未持久并精确核销。当前继续同编号整改确定性后验收的停止、超时、晚到隔离和资源释放。
- BUG059稽查整改完成待独立复测：InsightFace三类子进程已纳入原job活动进程与200ms可运行性/deadline监督；OpenPose prompt ID持久为`validation_prompt_id`并进入停止、超时、恢复和关闭精确核销集合。子进程停止、prompt超时取消和原job精确核销动态通过；关联`178 passed, 3 subtests passed`，完整unit`589 passed, 9 subtests passed`无失败无跳过。
- BUG059稽查整改独立复测通过：提交`9685d38`上直接关联`178 passed, 3 subtests passed`、完整unit`589 passed, 9 subtests passed`无失败无跳过，编译、文档、diff与工作树门禁通过，待只读复稽查。
- BUG059二轮只读复稽查退回：OpenPose Comfy子步骤尚未纳入原job资源票据；取消确认失败时外层、看门狗和关闭均仍可写failed终态。当前整改原job `audit` claim及核销未确认时的`cancel_pending`持续对账。
- BUG059二轮稽查整改完成待独立复测：OpenPose复用原job完整身份、`audit`资源claim和共享deadline；核销未确认统一持久`cancel_pending`与预定终态，看门狗持续对账且不释放subject所有权，确认离队后才恢复原completed或提交failed。关联`110 passed, 3 subtests passed`、完整unit`593 passed, 9 subtests passed`无失败无跳过。
- BUG059二轮整改独立软件复测通过：冻结提交`ec12a1c`直接关联`110 passed, 3 subtests passed`、完整unit`593 passed, 9 subtests passed`，均无失败无跳过；编译、文档、diff与干净工作树门禁通过，待只读复稽查。
- BUG059三轮只读复稽查退回：通用无owner清理会覆盖`cancel_pending`保存的预定completed语义；LLava持续核销未重新取得原job accelerator票据，可能误停随后准入的审核任务。当前整改预定终态原样恢复与有限资源claim后再停模。
- BUG059三轮稽查整改完成待独立复测：通用清理优先无损恢复`pending_terminal_*`；LLava持续核销以原job完整身份重新取得250ms有限`audit`claim，资源忙时保持pending且不触碰后续任务。关联`112 passed, 3 subtests passed`、完整unit`595 passed, 9 subtests passed`无失败无跳过。
- BUG059三轮整改独立软件复测通过：冻结提交`490d2a0`直接关联`112 passed, 3 subtests passed`、完整unit`595 passed, 9 subtests passed`无失败无跳过；编译、文档、diff与干净工作树门禁通过，待只读复稽查。
- BUG059最终只读复稽查通过并关闭：原job资源claim、持久`cancel_pending`、Comfy/LLava/子进程核销、预定终态无损恢复及后续job隔离完整闭环；M9.198恢复BUG057正式静音H3与2—3镜头、总时长不超过15秒的全链验收。
- BUG060正式登记：3镜头隔离项目已完成image权威前序，首个3秒H3任务的Ref2VA Context IR连续两次因`Tool h3-prompt-writing not found in agent`失败。当前只修供应链固定补丁中的主Skill工具注册契约，BUG057保持阻塞。
- BUG060仓库内整改完成：主Skill以精确`h3-prompt-writing`只读工具注册，补丁SHA、安装AST门禁与规范同步；隔离上游worktree真实apply/编译通过，关联`48 passed`、完整unit`595 passed, 9 subtests passed`。因当前授权范围仅限仓库，需用户允许把固定补丁应用到仓库外Comfy运行节点并重启后才能完成正式复测。
- 用户将M9.198最终媒体验收范围收敛为2—3个镜头、总时长不超过15秒；仍须跑通大纲至成片的全部阶段、音画字幕/导出和生命周期门禁，不再要求完整剧集时长。
- M9.193 / BUG038最终只读复稽查通过并关闭：0°基准及左右45°/90°/180°全身图统一强制手、脚和四肢/指趾解剖门禁，失败候选有限重试后物理清理并落明确终态；复稽查关联`117 passed, 3 subtests passed`，0失败0跳过。角度版本化硬基线保持不变。

### M9.197：可观测性持久导出与告警最小闭环（最终稽查通过，已完成）

- 将原进程内日志、指标和trace底座扩展为统一`RecordExporter`插槽；默认`NullExporter`保持既有调用兼容，可组合接入持久JSONL及Prometheus textfile原子快照。
- 指标标签规范化、counter禁止回退，结构化快照及span/alert统一携带可选`request_id/trace_id`；嵌套敏感字段拒绝写入持久证据。
- 增加队列积压类确定性告警规则/导出测试；本增量只建立生产化可观测底座，不宣称API、任务、provider、ledger和manifest全链追踪已经完成。
- 专项`5 passed`、Python编译通过；未启动模型、未操作正式服务或生产任务。BUG-20260811-045等待独立软件测试。
- 首轮独立测试中可观测专项及动态全部通过；全unit唯一失败来自联网搜索“全provider失败”测试只隔离2个免Key provider、遗漏现行注册表另2个免Key后备，真实网络成功使断言未抛错。已按五provider权威注册表补全测试隔离，待重跑后再次提交独立测试。
- 整改自检：联网搜索与可观测定向`14 passed`；全unit`521 passed, 1 skipped, 9 subtests passed`，文档状态检查及Python编译通过。生产搜索实现未改动。
- 第二轮复测发现敏感指标标签可在tuple→list后绕过递归检查；现已在标签注册、结构化快照、JSONL和Prometheus四层拒绝敏感二元键，直接恶意快照不能绕过。可观测专项`6 passed`；扩大unit受并行文档状态变更及资源池瞬态用例阻断，等待冻结快照独立复测。
- 2026-08-11冻结快照主线自检：可观测与联网搜索定向`18 passed`，完整unit`554 passed, 1 skipped, 9 subtests passed`；文档状态门禁、关键Python编译和限定diff-check通过。同期修正BUG045首状态与唯一索引冲突，当前仍为待独立软件复测。
- 最新独立软件复测通过：可观测及关联`41 passed`、完整unit`555 passed, 9 subtests passed`且无skip；敏感二元标签四层失败关闭、持久导出、原子快照、告警和关联ID均通过，关键Python编译通过。BUG045待只读稽查。
- 最终稽查退回整改：非有限数值和非法Prometheus标签曾可进入counter/textfile；现注册与直接导出双层拒绝非数字、bool、NaN、±Infinity、非法指标名/标签名及畸形标签结构。专项`6 passed`、完整unit`555 passed, 9 subtests passed`、复现脚本、文档门禁、编译与diff-check通过，待独立软件复测。
- 同根因扩大整改将指标快照语义门禁统一复用于JSONL和Prometheus，任何持久exporter均在写入前拒绝恶意手工快照，Composite不会产生JSONL部分写入；自检保持专项`6 passed`、全unit`555 passed, 9 subtests passed`。
- 稽查整改独立复测：定向`41 passed`、完整unit`555 passed, 9 subtests passed`且无skip；JSONL/Prometheus/Composite共用门禁及关键Python编译通过，待只读复稽查。
- 最终只读复稽查通过：注册与全部持久exporter共享有限数值、合法名称/标签结构和秘密字段门禁，Composite无部分非法写入；BUG-20260811-045已关闭。全链trace、仪表盘和正式告警演练仍按剩余框架清单继续。

### M9.196：文档当前状态唯一事实源（最终稽查通过，已完成）

- 新增机器可读的`docs/product/当前开发状态.md`，集中维护并行工作流、里程碑、BUG及唯一当前状态；原四份文档的多轮状态明确降级为历史证据。
- 新增`scripts/maintenance/check_document_status.py`及单元测试，自动拒绝重复里程碑/BUG、未知状态、BUG详情缺失、状态族冲突和第二当前事实源声明。
- 不改业务代码、不启动模型或正式生产任务；BUG-20260811-044等待独立软件测试。
- 首轮独立测试退回后补齐Tracker活动项反向完备性、本地链接存在性、跨文档同编号状态冲突与显式历史豁免，并接入pytest自动收集的contract门禁。
- 第二轮退回后，secondary组合行会分别归一M编号与BUG完整/简写编号，并逐项和索引状态族比较；三份职责文档的M/BUG参数化矩阵及contract共`18 passed`。
- 最终稽查退回后，Tracker测试改为动态section定位和相反状态族变异，参数化覆盖待测试/待稽查/已关闭；专项与contract`21 passed`、全部contracts`40 passed, 51 subtests passed`。
- 第二轮独立复测通过：专项与contract `18 passed`、三文档组合M/BUG冲突与历史豁免动态`6/6`，反向完备、链接、contract入口和简写归一均通过；待最终只读稽查。
- 最终整改独立复测通过：专项与contract`21 passed`、全部contracts`40 passed, 51 subtests passed`、完整unit`555 passed, 9 subtests passed`且无skip，关键Python编译通过。
- 最终只读复稽查通过：状态冲突夹具不绑定当前生命周期，三类状态族和相邻BUG保护均闭环；BUG-20260811-044已关闭并从当前索引移除。

### M9.193：人物全身安全区改为轮廓级数值门禁（开发完成，待独立软件测试）

- 修复 YOLO 人体框可能漏掉发顶/鞋底却被布尔标记直接放行的问题；全身归一统一使用 GrabCut 可见人物轮廓，按9%顶部、5%底部容差重排并输出实际边界比例。
- 机器验收只接受归一标记与数值证据同时满足8%/3%的结果；0°、左右45°、90°和180°全身统一要求确定性完整构图，旧标记或视觉模型主观判断不能绕过。
- 正式失败旧图实测归一后顶部8.996%、底部5.004%；定向`34 passed, 1 skipped`、完整单元测试`503 passed, 1 skipped, 9 subtests passed`，Python编译、Vue typecheck及83模块构建通过；正式8787已在全资源空闲时重载至PID`55404`。
- 稽查退回整改：轮廓识别异常不再回退YOLO框；异常直接失败关闭并进入既有候选重生成，验收只接受`grabcut_person_silhouette`来源。专项`3 passed`、真实旧图重复归一通过、图片关联`116 passed, 3 subtests passed`；正式8787已重载至PID`58574`，等待重新独立软件测试。
- 二次稽查退回整改：0° baseline不再直接调用归一器，baseline与variant共用候选准备生命周期。轮廓失败立即删除当前文件，baseline统一有限3次生成，末次返回可定位失败。新增动态测试核对provider重试次数、失败文件清理、最终成功及末次失败；关联`118 passed, 1 skipped, 3 subtests passed`，编译、类型检查与83模块构建通过。全单元`537 passed, 2 failed, 9 subtests passed`，2项均为其他并行文档状态冲突，与BUG038代码链无调用关系。
- BUG-20260811-038待独立软件测试；BUG039—041仅登记排队，未提前处理。

### M9.192：增强权威台账与阶段状态统一提交（最终稽查通过，已完成）

- `review_export/upscale`物理执行只生成延迟authority payload，不再提前写入成功台账；最终权威记录、项目/Graph状态统一由owner+generation提交helper在stage lease commit guard内发布。
- ProductionLedger整批authority事务在全部记录校验写入后、SQLite提交前执行Graph callback；Graph/项目提交异常会回滚整批权威记录，取消先赢、失租旧代和失败路径均为零成功证据，提交先赢则唯一消费租约。
- Graph事件持久记录精确authority commit tuple；启动恢复发现Graph已pending但对应ledger事务未持久化时自动failed关闭，禁止崩溃后长期保留无权威证据的waiting状态。
- 开发动态覆盖cancel-first、commit-first、Graph原子故障、失租新代及重启恢复5项；review_export/upscale、取消与生产控制关联`147 passed`，Python编译、Vue typecheck与83模块生产构建通过。未启动模型或操作正式任务。
- 独立软件测试补充验证多集第二条authority故障整批回滚、完全相同批次重复提交幂等、tenant/user/project三维隔离，以及Graph已落盘但ledger缺失的崩溃窗口恢复失败关闭；原5项动态、关联`147 passed`、完整单元测试`495 passed, 1 skipped, 9 subtests passed`全部通过。Python编译、Vue typecheck与83模块生产构建通过；未启动重模型或操作正式任务。
- 最终只读稽查与正式加载验收通过；用户图片任务自然结束后安全重载8787，新进程已加载当前代码且任务、资源池、Ollama、ComfyUI全空，BUG-20260811-035已关闭。

### M9.191：分镜资产自动生图与取消手动上传前置（最终稽查通过，已完成）

- 分镜脚本逐集产出后继续沿现有串行队列自动提取资产卡并生成缺失基准图；进入资产页也会自动续跑缺失项。
- 移除“请上传人物四视图、场景和道具”的旧提示与进入资产页时清空已有图片/角度/确认状态的破坏性逻辑；手动导入仅保留为可选替换能力，不再是生产前置条件。
- 资产页入口single-flight按`project_id + projectSession`绑定，旧项目未决Promise不会吞掉新项目首次进入；旧代finally也不能清除新代owner。
- 稽查整改复测：P1/P2分别阻塞confirm与prepare的跨项目动态2/2；P2新建transaction并唯一persist/enqueue，P1晚到零写回且旧finally不清P2 owner；定向102 passed、1 skipped；完整单元测试490 passed、1 skipped、9 subtests；编译、类型检查与83模块构建通过。
- 最终稽查通过，BUG-20260811-037已关闭。

### M9.190：资产人物错误提示按卡片隔离（最终稽查通过，已完成）

- 资产批次中某个人物的失败信息只显示在该人物卡片，不再作为全局阶段错误覆盖其他人物的确认弹窗。
- 确认苏璃等当前人物基准图时清除旧的兄弟资产批次提示；当前人物其余角度仍严格使用自身已确认基准与自身已确认角度。
- 冻结快照复测：定向118 passed、1 skipped、3 subtests；完整单元测试489 passed、1 skipped、9 subtests；编译、类型检查与83模块构建通过。
- 最终稽查通过，BUG-20260811-036已关闭。

### M9.189：生图能力幂等注册、台账兼容与人物构图安全区（最终稽查通过，已完成）

- 内置生产能力只在进程内首次安装；运行中的Klein 9B请求不再触发同提供器热替换，后续请求继续由既有FIFO与资源池串行调度。
- 生产台账统一使用显式24列写入，兼容升级后的SQLite结构。
- 人物所有全身角度图统一执行最高发顶上方纯背景至少8%、最低鞋底下方纯背景至少3%的安全区下限；提示词、确定性归一、机器验收和三份现行规范同步。
- 独立软件测试：动态inflight二次安装通过；定向209 passed、1 skipped、3 subtests；全部单元测试458 passed、1 skipped、9 subtests；编译、类型检查与83模块构建通过。
- 最终稽查通过，BUG-20260811-033已关闭。

### M9.188：分镜媒体阶段完整范围门禁统一（最终稽查通过，已完成）

- 修复阶段入口把“任意一条已确认scope”直接当作整个阶段完成的问题；入口、人工确认、资产延迟确认和重启/批量同步恢复统一复用同一台账门禁判定，禁止`trusted`旁路。
- image/video/audio/subtitle以storyboard权威shot census为期望集合；只有至少一集全部镜头均存在且已确认时才能推进。缺镜头、待确认镜头或缺storyboard census均失败关闭，其他完整分集可独立向后生产。
- 媒体实际scope必须全部属于storyboard目标集合；目标外、非法/非规范ID、重复/别名碰撞及非shot类型均失败关闭，门禁保留全部实际记录。媒体完成还必须有非空fingerprint/audit batch，且confirmation两项与顶层当前值精确一致；非媒体stage不受该证据特约束影响。最新扩大关联`202 passed, 1 skipped`，类型检查与83模块生产构建通过。
- 隔离动态复现旧实现一张已确认分镜图即可放行video；整改后partial/missing均拒绝、完整单集精确放行、后续完整集不受前面残缺集阻断。扩大关联`170 passed, 1 skipped`、Python编译通过，未启动模型或正式任务。
- 最终独立复测覆盖四媒体阶段、额外/非法scope、别名碰撞、多集边界及确认/延迟确认/恢复/入口共用门禁；专项`79 passed, 1 skipped`、扩大关联`192 passed, 1 skipped`，编译、类型检查与83模块生产构建通过。
- 最终只读稽查与正式加载验收通过；8787已加载当前实现，任务、资源池、Ollama与ComfyUI均空闲，BUG-20260811-034已关闭。

### M9.187：人物0°正面全身基准与全角度提示词消歧（最终稽查通过，已完成）

- 人物首张定位基准改为0°正面平视完整全身；人工确认后才依次生成左45°、右45°、90°侧面、180°背面和0°半身。
- 六个角度提示词分别声明唯一目标姿态、偏航范围、构图及禁止的其他角度/景别；人物身份描述统一移除视角、近照、半身和全身等冲突词。
- 人物3D确认输入同步为已确认0°正面全身基准；道具45°三分之二与场景45°空场景全景保持不变。
- 独立软件测试：定向73 passed、3 subtests；全部单元测试448 passed、1 skipped、9 subtests；编译、类型检查与83模块构建通过。最终稽查通过，BUG-20260811-032已关闭。

### M9.186：人物基准图验收自动三次生成（历史左45口径，已被M9.187覆盖）

- 左45°人物基准图执行首图加最多2次自适应重生成，共3次候选；每次重试携带上一候选实际失败的硬门禁。
- 失败汇总只检查左45°真正 required 的单人物、方向、底部留白、纯灰背景、尺寸、完整构图和30—60°面部角度，不再误报无关头身比、手臂比例等字段。
- 第三次仍不合格才暂停当前资产队列，错误明确说明“自动生成3次仍未通过”；成功结果记录`validation_attempts`。

### M9.185：资产续生保留成品与子任务循环门禁修复（最终稽查通过，已完成）

- 人物/道具/场景基准、角度修复及3D建模属于assets内部构建子任务，不执行其下游阶段前序门禁；资源调度仍使用image/3d资源池和统一FIFO。
- 资产页主按钮固定为生成/继续生成，只补`image_url`缺失项；禁止调用全量purge或清空已有图。单卡重做仍是唯一显式替换入口。
- 历史`previous stage is not completed: storyboard/assets`错误按精确文本迁移；已有图恢复待确认、无图恢复待生成，其他真实错误不清除。
- 当前项目墨无痕与宗门试炼场成品保留；已被旧purge物理删除的苏璃、云长老仅标记为待补生成。关联`125 passed, 1 skipped`，编译、类型检查及83模块构建通过。
- 首败整改独立复测通过：持久媒体门禁12/12、子任务路由17/17、历史错误迁移7/7；关联`171 passed, 1 skipped`，编译、类型检查和83模块构建通过。正式项目状态与物理媒体一致。
- 最终稽查通过，BUG-20260811-030已关闭。

### M9.184：资产操作统一FIFO与延迟阶段确认（最终稽查通过，已完成）

- 资产页自动/手动生成、重做、局部修复、图片导入、基准/角度确认、3D生成/确认及图片超分统一进入项目会话级FIFO，按提交顺序单路执行；重复操作按稳定key去重。
- 队列在已有资产任务运行时等待，项目切换或“停止”会提升代际并清除未执行操作；停止/取消保持即时控制命令，不进入普通队列。
- 单资产确认先持久确认该资产；若storyboard尚未完成，只延迟assets总阶段推进，不回滚资产确认。生产阶段冲突统一返回HTTP 409，禁止未捕获异常导致socket hang up和伪HTTP 500。
- 稽查整改后，已启动操作与新项目操作仍共享同一FIFO尾链，项目切换只使旧代未启动任务失效，不再重置尾链制造旧新并发；导入、修复、确认、3D生成/确认和超分在每个异步响应后均校验固定project/session，所有持久化使用捕获的原项目上下文，旧项目晚到结果不得写入或清理新项目状态。
- 独立复测确认旧任务与新项目任务严格`old-start→old-end→new-start→new-end`且最大并发为1；各类旧响应晚到零状态、零持久化、零提示污染。关联`164 passed, 1 skipped`，编译、类型检查及83模块构建通过。
- 最终稽查确认统一FIFO、跨项目响应围栏、owner token精确回收、延迟确认和HTTP 409链均无剩余阻断，BUG-20260811-029已关闭。

### M9.183：增强版视频统一服务端阶段（最终稽查通过，已完成）

- BUG028最终权威篡改整改开发完成，待独立软件测试：upscale权威字段已从projection progress物理拆分；公开single/bulk只允许进度投影，不能创建或覆盖fp/batch/generation/evidence/confirmation及已确认生命周期。真实生成先持久分配单调generation，fingerprint绑定generation+batch，authority history与revision CAS原子拒绝低代、旧fp+batch重放和同代不同证据；完全相同同代提交幂等。确认与enhanced导出三方精确绑定fp+batch+generation，旧UI确认拒绝。专项`32 passed`、关联`161 passed, 1 skipped`，pycompile与Vue typecheck通过；本进程Vite构建受ChatGPT内置Node与Rollup原生模块Team ID签名不兼容阻断，待独立测试运行时复验。未启动模型或操作正式服务。
- 最终稽查阻断整改完成，待独立软件复测：`ProductionLedger.upsert`以`content_fingerprint + audit_batch_id`作为证据代际。仅两者均未变化时，missing/null progress可保留既有production/audit evidence；任一变化先原子清除两项旧证据和confirmation，再只接收本次upsert携带的非空规范证据，禁止同fingerprint新batch继承旧证。临时SQLite覆盖fp-only、batch-only、双变化、missing/null/空结构、新证据、跨实例reload/reconfirm与enhanced authority；专项`36 passed`、关联`203 passed, 1 skipped`，pycompile、Vue typecheck及83模块构建通过，未启动模型或操作正式服务。
- 最新稽查三项阻断已整改：upscale深watch同步携带结构化production/audit evidence，SQLite progress对缺失/null执行保留式字段合并；enhanced缺权威证据失败关闭，legacy缺省仅允许base；enhanced导出声明及服务端authority同时精确绑定fingerprint+audit batch，同fp旧批次不得复用。
- 临时SQLite深watch/reload、enhanced/base证据边界、同fp新旧batch端到端及关联回归通过：`44`项专项、`171 passed, 1 skipped`关联、`4`项交付链；pycompile、Vue typecheck、83模块构建通过，待独立软件复测。
- 独立软件复测通过：正式前端sync动态保留嵌套证据并在缺失时省略擦除字段；SQLite跨实例/确认不丢证据，enhanced缺证、legacy base边界及同fp新旧batch精确拒绝成立。四步骤失败/取消`8/8`、原子回滚、规范JSON、真实files/manifest、single-flight/FIFO与关联`181 passed, 1 skipped`通过；pycompile/typecheck/83模块构建通过，未启动模型或正式任务。

- 权威证据已贯穿SQLite reload→confirm→enhanced export manifest：嵌套production/audit JSON不降格，客户端篡改被服务端ledger覆盖；基础版遗留scope输出明确not_available/not_applicable边界。

- 复稽查整改：production_evidence保留结构类型，空/NaN/不可序列化值拒绝；fingerprint全树规范JSON。资产操作FIFO新增正式函数动态，覆盖顺序、重复key owner、停止/切换新owner及旧finally代际保护。
- 复稽查最终软件测试通过：补测Infinity、深层全树键序/语义、确认导出及正式FIFO owner/epoch隔离；扩大回归180项、1项环境跳过，pycompile/typecheck/83模块构建通过。
- 端到端证据复测通过：SQLite跨实例reload/confirm保持嵌套证据类型，客户端伪证据被权威scope覆盖，enhanced files/manifest携带完整版本、指纹、批次与证据；legacy base缺省原因明确。关联180项、1项环境跳过，构建通过。

- 原`runUpscale`由前端逐集直调超分、字幕OCR、人脸与终审四类接口，绕过统一stage lease/cancel/资源路由；失败还会把全部基础母版伪写为skipped。
- 现一次提交`review_export/upscale`整批commands，服务端逐集串行执行超分及真实质量审核，任一失败停止后续且阶段failed，禁止假成功/假skipped。
- 前端仅原子接收服务端items，使用project/session/AbortController围栏；项目切换主动abort，旧项目晚到成功/异常零污染。报价仍为无副作用预检，不属于生产提交。
- 软件测试首败：多集commands中第1集缺path时未整批预校验，仍调用第1、2集超分与终审并返回waiting_confirmation；违反缺输入整批零副作用，登记BUG-20260811-028后停止测试。
- 最终权威边界：增强证据改为server-owned列并以单调generation、revision CAS和不可变history保护；公开projection仅可更新progress，不能篡改指纹、批次、证据、确认或终态。确认与导出严格绑定fp+batch+generation，旧代与同代伪证据永久拒绝。最终稽查及正式加载验收通过，BUG028已关闭。
- BUG028整改：所有upscale command在首次provider前整批验证对象、唯一正整数episode、合法绝对媒体来源、base版本和目标分辨率/FPS/模式；混合批次任一非法整批失败且零副作用。
- 软件复测：非法输入22/22通过；成功item缺少`content_fingerprint`与`audit_batch_id`，不能落与enhanced导出匹配的权威upscale证据，BUG028继续待处理。
- 权威证据整改：服务端生成绑定输入版本、增强输出、目标参数和审核证据的SHA-256及服务端批次ID，整批成功后原子落`upscale:{episode}` pending_confirmation；人工确认后enhanced导出严格匹配，篡改或旧批次拒绝。失败/cancel不写成功证据。
- 第二轮软件首败：正式runUpscale报价等待期间重复点击启动2次quote且返回不同Promise，尚无覆盖报价→确认→runStage全事务的project/session single-flight；BUG028继续待处理。
- 第三轮动态功能复测已通过前端18项、后端取消/失败8项、台账原子回滚1项及权威证据52项；扩大回归唯一失败为旧测试仍要求前端直连MuseTalk→LatentSync，而现行权威回退已在服务端统一video阶段，需同步测试契约后重跑。
- 关联旧测试已同步为服务端动态契约：MuseTalk成功不回退、失败仅回退一次、取消不回退；前端正式生成入口无口型直连。业务架构保持统一video阶段。
- 稽查退回最终复测通过：完整command与OCR/face/final证据逐项影响指纹、键序稳定、not_applicable原因明确，确认/导出代际门禁无回归；资产按钮统一FIFO契约经独立判定成立。扩大回归178项、1项环境跳过，编译/类型/83模块构建通过。
- 最终软件测试通过：前端single-flight/停止/晚到、服务端四步取消失败、原子台账、权威fingerprint/batch/confirm/enhanced导出及输入门禁均通过；扩大回归`171 passed, 1 skipped`，pycompile/typecheck/83模块构建通过，未启动模型。
- 前端整改：非async公开入口直接返回同一flight，quote→确认→runStage→merge→persist共享project/session/controller/epoch；切项目和stop释放旧flight并隔离晚到，旧finally不清新任务，拒绝/异常后可重试。
- 稽查整改：增强指纹绑定完整command与完整输出；OCR/face/final分别记录status+evidence或明确not_applicable原因，启用步骤无真实evidence失败关闭。规范JSON排序保证键序稳定，任一输入或步骤证据变化改变指纹。

### M9.182：纯空场景资产与动作伪场景清理（最终稽查通过，已完成）

- 场景提取只接受地点型可复用空间，地点词覆盖古装、都市、校园、医疗、交通、商业、工业与自然环境；服务端读取项目权威人物名单，人物姓名、人物动作、姿态、状态、群体行为和剧情句子均在任务登记前拒绝。
- 服务端统一重建场景提示词，仅保留地点、布局、光线和固定陈设，并强制无人、无人形、无人体、无文字；伪场景在任务登记和资源占用前返回`invalid_scene_asset_subject`。
- 前端对加载、增量合并、权威接管、标准导入和分镜预建的场景统一归一；历史伪场景自动删除并持久化，从分镜背景描述补回真实地点。

### M9.181：全局提示统一进入项目对话框（最终稽查通过，已完成）

- 所有既有`notify()`提示统一追加为左侧助手消息，并标记“系统提示”；不再渲染页面底部蓝色Toast横幅。
- 相同连续提示自动去重，写入后自动滚动到对话末尾；提示服从当前项目对话隔离，不污染其他项目。
- 系统提示不写回助手历史接口，避免历史保存失败触发递归保存；业务阶段状态与错误字段继续作为恢复和任务门禁事实源。

### M9.180：资产批次、图片投影与分镜续生成闭环（最终稽查通过，已完成）

- generateAllAssetImages按project+session单飞，独立controller与batch token贯穿权威读取、合并、清状态、purge、模型提交、响应写回和持久化。
- 图片持久投影专项3/3通过；动态确认分镜续生成会重新生成已有完整集并覆盖existing shots，旧测试反映真实产品回归，需迁入服务端仅补missing的行为契约。
- 已整改：服务端按15–23镜、连续镜号/时间线、2–9秒和目标总时长权威识别完整分集；完整集零模型且所有旧字段原样保留，部分集整集重生。新镜头确定性合并，重复/非法/跨集输出失败关闭；前端仅替换generated_episodes并保持project/session/abort围栏。
- 切项目或停止立即abort并隔离旧flight；旧请求即使忽略signal也不能写新项目或继续下一模型。停止后释放旧键可安全重试，旧finally不清新flight。
- 回收按旧flight/controller/token三重身份同步清batchGenerating/旧generating卡片；新项目立即可启动。stop使用epoch围栏，旧stop响应和旧finally不得复位新批次投影。
- 单飞公开入口必须是普通函数并直接返回权威flight；禁止async包装导致相同底层任务返回不同Promise identity。内部执行器保持async，调用方await语义不变。
- 动态首败：p1 readStage阻塞时切p2，回收虽清controller/flight/token但未清assetBatchGenerating；p2被全局assetImagesRunning拦截且零readStage。旧p1失去token后finally也不会复位，形成跨项目残留背压。
- 第四轮动态read/purge/model晚到23项通过；同项目重复调用因公开入口仍为async而返回不同外层Promise，严格同Promise契约失败。
- 第四轮整改独立复测通过：严格同Promise、异常重试、stop epoch、旧finally与三重身份隔离共16项；晚到矩阵23项、关联155项及3个子测试、编译/类型/构建通过。
- 稽查退回修复：人物、场景、道具基准图及分镜/辅助生图在入口stage、资源类别和持久任务Graph投影三处统一为`image`；`assets`仅承载资产清单与`asset_3d`工作流，后者资源类别为`3d`。人物生图的running/completed/failed只报告image，禁止污染assets租约与状态。
- 最终独立复测：完整集边界与续生成动态`18/18`、前端实际合并及项目晚到隔离`5/5`、投影`3/3`；扩大关联`163 passed, 1 skipped, 3 subtests passed`，pycompile/typecheck/Vite 83模块构建通过，未启动模型。
- 最终只读稽查：2D图片三处契约统一image、asset_3d保持assets/3d；严格批次单飞与会话代际围栏、完整集原样保留和缺集补生成全部通过。扩大回归197项通过，正式资源与模型队列空闲。

### M9.179：review_export服务端内核（最终稽查通过，已完成）

- 后端review_export专项6项通过后发现前端最终审核仍在逐集与最多三轮重试双循环内调用runStage；一次点击可重复提交同一阶段，未满足单次整批服务端编排。
- 已按首败停止其余测试，未启动模型或正式任务。
- 整批审核与后端门禁已通过，但导出入口缺少project/session/abort围栏；旧项目晚到响应会无条件覆盖当前项目导出结果，继续退回。
- 已补project级AbortController与single-flight Promise；同项目重复点击返回同一Promise且只提交一次runStage。项目切换/停止abort，files/manifest/status和persist均受启动project/session围栏，旧项目晚到成功或异常零污染，finally身份释放后可重试。
- 已补完整租户身份的服务端review_export精确停止；服务端未确认取消明确409。停止递增epoch并立即释放旧单飞键，新重试不等待忽略signal的旧Promise；旧响应与finally按epoch/Promise/controller身份隔离。
- 稽查修复导出信任边界：请求审核结果仅为声明，服务端必须从生产台账读取同tenant/user/project的review episode与composition/upscale确认，校验completed、confirmation和当前审核/媒体fingerprint+batch；任何伪造、跨项目、旧版本或未确认均零调用导出provider。
- 复稽查2：媒体权威门禁无条件执行，audit_required=false只豁免review；source_version=base只认composition，enhanced只认upscale，不允许any合并或回落。多集任一缺证整批失败且零provider副作用。
- 关联测试契约同步现行架构：assets run-stage只负责清单提取，characters/generate归image资源；队列生成统一传入启动project/session并验证晚到隔离，不再接受无上下文旧签名。关联126项及类型/构建通过。
- 最终独立复测：两条测试保持双向精确断言，无放宽；四组权威与关联回归126/126、Python编译、Vue类型检查和83模块生产构建通过。
- 第三轮首败：stopExports只有本地abort/failed持久化，无定向review_export stage stop且旧flight不释放；忽略signal时服务端继续、同项目无法立即重试。
- 第三轮独立复测通过：正式前端异步闸门覆盖定向停止、即时重试、旧响应/旧finally隔离及503诊断；关联135项、Python编译、Vue类型检查和83模块生产构建通过，未启动模型或正式任务。
- 权威审核门禁独立复测通过：临时SQLite与真实HTTP覆盖伪造、跨身份、未确认、旧fingerprint/batch、媒体版本及多集原子门禁；前端停止晚到动态7项、专项19项、关联137项、类型与构建全部通过。
- 复稽查2动态门禁23项与专项14项通过；关联回归发现两条旧静态断言仍要求`characters/generate→assets`及无project/session的`generateAllAssetImages()`，与现行image阶段和会话隔离契约冲突，已按首败退回同步测试。
- 最终只读稽查通过：审核开关不影响媒体权威门禁，base/enhanced精确绑定composition/upscale；跨身份、旧证据和多集缺项均零导出调用。整批编排、停止、会话与代际围栏通过，正式资源和模型队列空闲。

### M9.178：统一服务端阶段取消（最终稽查通过，已完成）

- 软件测试首败：叙事初审中途取消后，内部审核链仍继续调用修复模型与最终审核模型，外层审核完成后才检查取消；cancel event未传入审核/修复内部。
- 动态调用序列确认取消后新增`text.narrative.repair`和第二次`audit.narrative`；已按首败停止其余测试，未启动正式模型或任务。
- 已把同一cancel event贯穿outline/script/storyboard共享审核链，在分块、初审、修复、终审前后统一检查；内部Event不会进入provider payload。新增动态回归及关联`109 passed`，待独立复测。
- 审核节点动态矩阵与126项关联通过；Vue typecheck发现`stopAsset3D`引用未定义`project`（TS2304），正式构建门禁失败。
- `stopAsset3D`现显式取得并校验活动项目后再发送完整身份停止请求；无项目不发送。Vue typecheck与Vite生产构建通过。
- 独立最终复测：审核取消矩阵10/10、关联126项、Python编译、Vue typecheck与82模块生产构建全部通过；未启动模型或正式任务。
- 最终只读稽查：八阶段检查点、审核Event隔离、generation/commit围栏、完整身份停止与跨租户保护全部通过；只读回归128/128，正式worker、资源池及模型队列空闲。

### M9.178：统一服务端阶段取消检查点（历史开发记录，已由M9.178最终闭环覆盖）

- 大纲、剧本、分镜、资产、图片、视频、合片及审核导出入口统一复用现有stage lease/cancel event；入口、批次、command、poll、本地调用、审核和fallback前后均检查，取消后禁止新模型、新command和晚到pending_confirmation。
- 所有正式停止统一先定向stage cancel，再精确终止当前文本、图片或视频子任务；强制完整tenant/user/project，子job停止同步校验身份。
- 专项及关联`135 passed`，Python编译通过。当前环境无`npm`命令，前端类型与构建待独立测试环境执行。

### BUG-20260811-022：统一仓库孤儿图片任务恢复（最终稽查通过，已关闭）

- 统一任务仓库权威列会补齐旧残缺payload的status、身份、stage、进程和时间字段；启动恢复/watchdog不再漏掉分类JSON缺失或无status的非终态任务。
- 恢复沿用分类保存、durable upsert、outbox与Graph投影正常链，保持租户隔离、终态幂等和投影一致性；隔离动态及关联`119 passed`，未修改正式数据库。
- 独立动态矩阵15/15、关联78项与Python编译通过；待全空闲安全加载后只读确认历史任务正常failed收敛且nonterminal为0。
- 正式历史job虽failed且nonterminal=0，但project_id仍为空；投影被ignored直接ack，无法形成Graph状态，身份完整与Graph一致门禁未通过。
- 对完全缺失真实project的可证明遗留image孤儿使用确定性`recovered-orphan-image-<job_id>`隔离身份并记录quarantine证据，禁止伪造归属到用户真实项目；failed必须经outbox成功投影后才能ack。
- 独立动态12/12、关联79项及正式PID98981补验通过；历史孤儿Graph failed、outbox/nonterminal为0，普通terminal未改。

### M9.177：跨实例worker派发容量原子预留（最终稽查通过，已完成）

- SQLite工作节点发现新增dispatch reservation；多个网关实例通过`BEGIN IMMEDIATE`原子选择并占用worker容量，避免心跳更新前同时把任务派给同一节点。
- 预留同时核算worker活动数、容量、资源类别、服务范围、可用内存与已预留内存；支持request幂等、TTL自动过期、generation围栏、精确释放和快照。
- 专项及关联`92 passed`，Python编译与差异格式检查通过；未修改兼容服务、未操作正式任务。
- 软件测试首败：正式`_forward_production_request`仍只调用进程内`WORKLOAD_ROUTER.route`，未调用共享注册表reserve/release；动态远端转发`reserve_calls=0/release_calls=0`，跨实例超卖风险仍存在。
- BUG-20260811-021已将预留正式接入`_forward_production_request`；成功、业务错误、连接异常均finally释放，相同request使用稳定ID，整改关联`95 passed`。
- 幂等契约复测通过：同ID仅在resource/memory/scope完全一致时复用，冲突保持旧预留并拒绝；异常矩阵10/10、关联78项与Python编译通过。
- 软件复测首败：稳定job ID跨resource/scope/memory复用时直接命中旧预留，text预留后的video请求被错误返回text-only worker，完整派发身份未绑定。
- 稽查整改：旧schema迁移使用`BEGIN IMMEDIATE`锁内复核并仅执行一次ALTER；8实例并发初始化全部成功，避免升级启动竞态。
- 独立关联79项及正式schema/service_scope、唯一worker和空闲状态补验通过。

### M9.176：生产能力提供方并发容量与热插拔保护（最终稽查通过，已完成）

- `ProductionCapabilityRegistry`新增提供方级`max_concurrency`、实时`inflight`占用和容量背压；同优先级提供方在并发请求下按可用容量分流。
- 软件测试通过：专项72项、20线程容量/公平/无超卖动态矩阵、关联96项及Python编译均通过；未访问正式服务、重模型或orphan prompt。
- 运行中的提供方禁止卸载、全量替换或同提供方热替换；任务释放后可正常插拔，避免在途调用失去实现与版本归属。
- 新增运行快照与并发契约校验；专项及关联`82 passed`，Python编译和差异格式检查通过，未修改兼容服务、未启动重模型或干预正式任务。

### BUG-20260811-020：视频终态与Comfy owned prompt原子核销（最终稽查通过，已关闭）

- 视频停止与终态提交前后必须确认owned prompt已从Comfy queue消失；取消未确认时保持`generating/cancel_pending`并保留资源票据，禁止返回停止成功。若同队列存在foreign running，禁止调用全局interrupt，只等待安全窗口。
- 看门狗发现终态job仍有owned prompt时恢复资源票据，由专属worker核销后还原原终态；重启和关闭不得在取消未确认时伪造failed/cancelled。
- 关联轻量生命周期回归`119 passed`，后端编译、Vue类型检查和Vite正式构建通过；未启动或干预正式重模型。

### M9.175：H3 Context IR Agent接入Ref2VA生产链（最终稽查通过，已完成）

- Ref2VA固定执行独立串行链：Context IR落盘优化结果→卸载专用32B模型并确认不驻留→释放Comfy→H3 Ref2VA；禁止两重模型并存或嵌套同一工作流。
- Context IR持久化独立阶段、prompt ID、心跳、尝试次数及`optimized_prompt/selected_skills/raw_json`文件；H3只消费非空优化提示词，任何优化、落盘、取消、超时或卸载失败均阻断H3。
- 第三轮测试发现当前job同批次内的符号链接在resolve后仍通过普通文件门禁并提交H3一次，BUG-20260811-019继续待处理。
- symlink门禁已整改；第四轮测试发现history完整的正常成功路径不会登记并删除三个SaveText中转输出，任务结束仍残留文件，BUG-20260811-019继续待处理。
- 中转清理已整改；第五轮测试发现publication父目录symlink仍可绕过末级文件检查并提交H3一次，BUG-20260811-019继续待处理。
- 前置异常与三文件原子发布已整改；第二轮整改将当前job同批三文件设为唯一事实源，强制普通文件/同目录/非空/JSON门禁并从磁盘回读，缺失或错误零H3提交且不重试重推理。
- 首败整改：Comfy启动、建目录与身份图复制全部进入统一清理域；清理文件失败不覆盖原始异常。三份Context IR产物先写唯一staging目录，写齐后以目录原子替换一次发布，任一写入失败均无可见半成品。
- 首败已整改：Comfy启动、建目录和身份图复制全部进入统一清理作用域；前置异常也会卸载、free并移除本任务空目录，H3保持零提交。
- Context prompt已纳入停止、结果中断回收、看门狗、恢复和关闭核销；临时输入与中转文本finally清理，完整资源票据、终态保护和最多一次普通重试保持。
- 轻量动态测试覆盖成功、失败单次重试、history瞬时异常、超时、持久化失败、取消、卸载失败阻断及优化提示词唯一传递；关联`150 passed, 3 subtests passed`，Python编译、类型检查与正式构建通过，未启动重模型。

### M9.174：资产阶段成功后清理历史并发冲突错误（最终稽查通过，已关闭）

- 资产阶段已进入`waiting_confirmation/confirmed/completed`时，人物、道具、场景卡片不再保留历史`production stage is already running: assets`失败状态。
- 前端加载、增量合并与后端权威资产合并统一归一化：无图恢复`pending`，已有图恢复`waiting_confirmation`，只清理已失效的阶段并发错误，不覆盖图片、确认、角度和3D成果。
- 正式项目历史错误已通过项目阶段接口清理，资产阶段保持`waiting_confirmation`且资源队列为空。
- 软件复测确认前后端白名单统一为`waiting_confirmation/confirmed/completed`；三类资产96项动态矩阵、关联134项、类型检查和正式构建通过。
- 清理必须同时满足权威assets状态属于waiting_confirmation/confirmed/completed与错误文本精确匹配；failed/generating/cancelled等状态即使错误文本相同也不得改写卡片事实。

### M9.173：基础设施提供方接口契约门禁（历史测试记录，已由最终稽查闭环覆盖）

- 8类基础设施扩展metadata统一声明`contract_version`与`required_methods`，覆盖资源调度、台账、事实库、任务仓库、LangGraph、路由、任务租约和worker发现。
- 扩展实例创建后、投入生产前逐项验证所需方法可调用；缺少任一方法立即抛出provider contract mismatch，禁止运行到任务中途才失败。
- task lease契约包含跨实例阶段执行新增的request_cancel、cancellation_requested与commit_guard，PostgreSQL/Redis替换实现必须完整支持同等语义。
- provider注册必须提供implementation_type；注册表在任何replace/activate写入前按类型验证全部required_methods，失败保持原provider集合、active绑定与实例创建能力不变；create仍对真实实例二次校验。
- 非builtin provider在写入前还必须完成真实factory contract probe；factory None、异常、实例方法不可调用或申报类型与实物不符均原子拒绝。
- 软件已覆盖factory注册后变坏、类型撒谎、非法schema、activate/替换/启停/卸载并发与8 builtin真实实例；专项`69 passed`、关联`149 passed, 3 subtests passed`，正式8契约及资源空闲通过。
- 注册、完整替换、单provider刷新与显式激活共用同一契约验证：`required_methods`必须是合法集合，真实实例必须属于声明的`implementation_type`且方法全部可调用；激活时重新探测可变factory，失败保持原active。探测配置仅存注册表内部，不进入公开metadata。
- 契约提升为extension-point级强制规范：已有契约的扩展点禁止候选省略或缩减required_methods；builtin探测豁免只由composition root构造白名单授予，公开metadata中的builtin字段不能产生信任。
- 软件复测覆盖契约降级三类写入、伪造builtin、旧无契约完整替换、坏fallback自动接管和并发首注册；专项`70 passed`、动态`116`组、关联`150 passed, 3 subtests passed`及正式8项契约/空闲验收通过。
- 软件已验证失败原子性`6/6`、8内置实例`8/8`、并发create/activate `2400/2400`和关联`146 passed, 3 subtests passed`；正式8个active metadata完整，资源全空。

### M9.172：生产阶段跨实例单飞与持久取消（最终稽查通过，已关闭）

- `/api/production/run-stage`同一tenant/user/project/stage必须持有SQLite分布式执行租约；进程内集合仅作快速提示，不再是多实例权威单飞依据。
- 阶段租约使用持久单调generation；释放或过期后再次取得不得复用旧generation，防止旧执行体提交晚到结果。
- 取消请求写入租约仓库，任意API实例均可取消实际owner；owner续租检测到持久取消后设置本地事件并停止提交。
- 阶段结果写项目状态与LangGraph前均复核owner+generation；失租或取消按cancelled终态处理，禁止写waiting_confirmation。
- 最终项目写回与LangGraph提交位于租约仓库`commit_guard`的同一SQLite写事务围栏内；取消与提交线性化，提交成功消费租约，取消先到则业务结果零写回。
- LangGraph按stage持久最新执行generation并拒绝低代生命周期；纯失租的旧owner禁止报告任何Graph终态，只有确认属于当前代的显式取消才允许报告cancelled。
- 软件已验证当前代即时取消、gen1/gen2反序、同/跨实例cancel-first与commit-first线性化、唯一项目写回及正式持久响应；专项`65 passed`、关联`144 passed, 3 subtests passed`，正式资源全空。
- 每个失租/提交前检查点同步按owner+generation读取持久cancel_requested；不得等待续租线程设置旁路标志，确保当前代取消即时进入Graph cancelled。
- 取消接口以SQLite request_cancel结果为唯一线性化事实；只有持久取消成功才设置本地Event并返回stopped=1，commit-first时必须返回0。
- 软件已验cancel-first零业务写回/Graph cancelled与commit-first唯一waiting_confirmation/Graph pending_confirmation；不同scope并行、generation重启单调、异常无泄漏及正式服务均通过，关联`141 passed, 3 subtests passed`。

### M9.171：MiniMax H3 Context IR提示词优化节点安装（供应链整改完成，待软件测试复测）

- 固定安装JerryZRic Context IR Agent提交771cb3cb…，MIT许可；ComfyUI白名单加载FL2VA与Ref2VA两个提示词节点。
- 本地OpenAI兼容端点使用专用qwen3-vl 32B/16K模型；真实Comfy调用输出非空H3结构化提示词，结束后模型卸载、队列清空。
- 新增持久LaunchAgent与固定启动脚本；节点路径、依赖、模式、内存、真实证据及“非官方云Context-IR”边界已同步规范。
- M9.175已完成短剧Ref2VA自动生产接线、独立任务状态、落盘、精确取消和卸载门禁；FL2VA等其他模式仍只保留节点安装能力。
- 供应链已固定Git提交、MIT许可哈希、42项Python完整版本及下载哈希、32B源blob SHA-256；提供可复现安装/校验脚本、CycloneDX SBOM、pip-audit与Bandit证据。

### M9.169：统一任务权威提交与JSON投影崩溃一致性（最终稽查通过，已关闭）

- text/image/video任务保存顺序统一为：先提交可插拔统一任务仓库，再写兼容JSON投影。禁止JSON先成功、SQLite后失败造成重启时终态倒退。
- JSON投影失败时权威任务仍可从SQLite读取并覆盖旧投影；权威提交失败时禁止修改JSON，避免兼容文件冒充已提交事实。
- 三类保存函数共用同一顺序契约；故障注入覆盖投影失败、权威失败与重启合并读取。
- 多任务使用单个SQLite事务批量提交；同时写入持久投影outbox。LangGraph异常不再抛回业务层或反写任务failed，后台心跳与服务重启会重放outbox，成功后才确认删除。
- outbox事件使用SQLite全局单调revision；确认删除必须匹配job_id+revision。LangGraph按stage保存最新投影revision并拒绝旧版本，保证并发drain不会误删新事件或用旧queued覆盖新completed。
- 多服务实例投影前必须取得SQLite中的tenant/user/project/stage级租约；租约自动续期、进程失联后过期。持锁后重新读取最新outbox，跨实例禁止同时写同一阶段checkpoint。
- 续租失败、租约被接管或数据库异常必须立即标记`lost`；Graph提交前后及ack前均复核所有权。提交途中失租时，从SQLite权威任务重新生成更高revision事件，禁止旧持有者确认新事件，并由后续投影自动修复可能的旧checkpoint。
- 软件复测已覆盖失租晚到修复、两进程原子抢锁、续租/释放/replay SQLite busy、shutdown不ack及正式空闲验收；关联`137 passed, 3 subtests passed`，专项`59 passed`。
- 租约释放与单个任务库重放遇到SQLite busy时保留TTL/outbox并等待下次心跳；异常不得逃逸并终止worker heartbeat，其他任务库仍须继续重放。

### M9.170：服装独立道具资产与镜头级换装链（最终稽查通过，已关闭）

- 服装从人物本体拆分为道具栏`costume`子类；资产提取不再过滤衣服、长袍和服装，并强制记录owner、costume_id、version与tags。
- 分镜人物条目逐镜携带`costume_id/costume_version`；延续不得省略，ID变化登记换装事件，AI只执行、不自行决定换装。
- 已实现服装Klein‑9B 45°单图→TripoSR独立网格→Blender七角度→按costume_id归档；角色基础体穿衣/蒙皮/碰撞与穿衣后H3→Qwen链明确为待开发并禁止冒充完成。
- 前端道具数据、3D请求、后端元数据与三份运行规范已同步服装类型、归属、标签和版本字段。

### M9.167：资源池租户/项目分层背压（重新最终稽查通过，已关闭）

- 在全局池队列上限之外新增租户级与项目级上限：`accelerator=8/4`、`cpu-media=32/16`、`control=128/64`，避免单个租户或项目占满整个节点队列。
- HTTP请求作用域通过线程级请求上下文传入统一资源调度器；所有实际资源票据记录tenant/user/project，缺少部分身份时明确拒绝，非项目型工具请求保持无作用域兼容。
- 视频即时执行、waiting-memory恢复及3D后台线程不依赖thread-local继承，统一从持久请求body显式传递完整identity，确保异步重负载同样受租户/项目配额约束。
- `waiting_memory`保留为统一任务仓库的真实子状态；同步LangGraph时投影为`queued`，禁止把模型资源等待状态冒充图生命周期。
- 背压校验与入队位于同一Condition临界区；拒绝不创建票据、不占队列。健康快照同时披露全局、租户和项目队列限额及每张票据作用域。

### M9.165：重启恢复权回收服务端与前端零自动重提（最终稽查通过，已关闭）

- 项目加载统一通过`applyInterruptedStageRecovery`恢复10类阶段的可操作状态和提示，禁止自动重新提交大纲、剧本、分镜、资产、画面、视频、合片、审核、超分或导出，避免页面刷新与仍运行/刚完成的服务端任务重复执行。
- 移除分镜视频加载后的50ms自动重提；用户显式点击才创建新任务。服务端启动恢复将LangGraph running阶段标为failed，并同步对应项目阶段记录、revision、台账与事件通知，前端读取的是持久事实而不是临时猜测。
- 恢复映射覆盖outline/script/storyboard/assets/image/video/composition/review_export；没有项目阶段载体的阶段仍由LangGraph失败化。所有恢复不启动模型、不占生产资源池。
- 首轮测试发现空资产与旧census加载仍自动提交assets；现均改为只播种本地空卡和人工继续提示，正式提取调用为0。

### M9.163：全链路规范冲突统一（文档整改完成，待软件测试）

- 人物资产统一为六格；Blender统一为七角度；旧版本保留、结果递增`_vN`且禁止覆盖。
- 文本链固定`qwen3-vl:32b`生成、`qwen2.5:72b`审核；标题节奏改为强钩子→快速铺垫→冲突升级→反转收尾。
- 3D转2D固定H3 Ref2VA先转换、Qwen‑Edit后局部细化；LangGraph、SQLite与统一任务仓库继续作为强制唯一事实源。
- 项目LoRA默认锁定；单镜可人工批准微调强度，连续失败3次以上可仅使用一次合规备用LoRA并人工确认，禁止整集重跑。

### M9.162：统一阶段进度事件通道与轮询降载（重新最终稽查通过，已关闭）

- 新增按项目、阶段和单调revision订阅的`/api/projects/stage/watch`长轮询通道；写阶段状态时在同一项目锁内提交revision并通知等待者，避免固定500ms请求放大和先检查后等待的丢事件窗口。
- 分镜增量读取改用统一`projectService.watchStage`，携带最后revision并支持AbortSignal；项目切换、停止或最终响应到达会终止订阅，断线重连从最后revision继续。
- 单次等待最长25秒，默认20秒；服务端设置128个并发订阅槽，超限返回429`stage_watch_backpressure`和重试时间。等待期间不占项目锁，响应写回也在释放锁后执行。
- 首轮测试发现最终响应无法立即结束正在等待的订阅；现已拆分主任务与订阅controller，并增加request_id定向取消端点，最终结果保留且服务端槽立即释放。
- 第二轮发现cancel-before-register孤儿标记只会被后续请求清理；现已增加每秒运行、随服务关闭的独立reaper，标记满30秒自动回收。
- 最终稽查发现裸request_id可跨作用域取消且shutdown不唤醒活动等待；取消键现绑定租户/用户/项目/阶段/request，服务关闭在Condition内广播并由watch返回503后立即释放槽。
- 第四轮软件测试128项及3个子测试、HTTP隔离/shutdown专项和重新最终稽查通过，任务关闭。

### M9.161：分镜生成期间增量建立资产卡片（重新最终稽查通过，已关闭）

- 服务端每完成一集分镜立即把当前镜头集合以`generating`状态持久化，并登记`streaming_episode`，不等待全剧分镜结束。
- 前端生成期间每500毫秒读取增量分镜；出现新镜头后立即建立已识别人物与场景空卡，并按完成集串行调用资产提取补齐人物、道具、场景描述。
- 增量资产按名称合并并保留已有图片、确认状态和版本；全剧分镜完成后不再清空已创建卡片，只补提取尚未处理的集数。
- 首轮测试发现旧项目增量读取晚到可先覆盖新项目分镜；现已在响应后、写入前及播种后建立project/session/abort围栏，并使用显式session持久化。
- 最终稽查发现逐集提取越级提交assets且最终收口未等待预览队列；现已拆成不推进阶段的`storyboard_preview`和确认后唯一一次正式assets提交，最终收口先停止轮询并等待同一队列排空。
- 第三轮软件测试110项及3个子测试和重新最终稽查通过，任务关闭。

### M9.160：基础设施多提供方安装、激活、回滚与卸载（最终稽查通过，已关闭）

- 8类生产基础设施扩展点由“单点单实现”升级为`extension_point + provider_id`多提供方安装模型；同一扩展点可并存SQLite/PostgreSQL、内存/Redis、本地/远程等实现，但任一时刻仅允许一个活动绑定。
- 支持显式激活、回滚到已安装提供方、按提供方启停/卸载；卸载活动提供方时仅确定性切到仍启用的已安装提供方。内置提供方刷新只替换自身，不覆盖插件提供方或当前插件绑定。
- 管理接口披露每个提供方的`active/enabled/provider_id/metadata`。有状态且`hot_swappable=false`的组件只影响后续实例创建，正式切换必须经排空、迁移、重启和恢复验证，禁止替换正在使用的实例。
- 首轮测试发现无效完整替换会先删除旧绑定；现已将全部校验前置到持锁写入前，失败替换保持原提供方、活动绑定与创建能力，关联104项及3个子测试通过。
- 第二轮软件测试108项及3个子测试与并发压力通过；最终稽查确认原子切换、显式回滚、确定性接管、插件保留及非热插拔边界，任务关闭。

### M9.159：同能力多提供方插拔与健康路由（最终稽查通过，已关闭）

- `ProductionCapabilityRegistry`由单能力单实现升级为`capability + provider_id`多绑定；支持优先级、健康、启停、显式提供方、同优先级轮转和provider粒度卸载。
- 默认失败不自动切换，防止非幂等生图/视频/付费API重复执行；只有调用方显式`allow_fallback=true`时才按优先级尝试后备提供方。
- `replace=true`保留旧“整能力替换”兼容语义；新增`replace_provider=true`只刷新同一提供方。内置能力安装改为provider粒度刷新，不会覆盖插件提供方。
- 健康与能力管理接口披露priority/healthy/enabled/provider metadata；LangGraph继续只依赖能力名，具体模型保持可插拔。
- 软件测试：关联105项及3个子测试通过；多提供方兼容、轮转、优先级、显式选择、健康过滤、provider粒度操作、安全fallback、并发选择与实际provider证据动态通过；正式27条能力绑定披露完整，资源与模型队列空闲。

### M9.158：人物左右45°多角度档案（历史顺序，已被M9.166覆盖）

- 六格能力继续保留；该左45°首张顺序已被M9.187的0°正面全身首张口径覆盖。
- Qwen‑Edit支持`left_45_full/right_45_full`，所有角度固定使用0°基准图哈希种子；已生成角度自动合成人物档案并作为Image 3传入后续角度。
- 分镜继续读取人物全部已确认角度作为身份、服饰与轮廓参考，0°半身保持人脸主参考。

### M9.157：节点内资源池并发与背压（最终稽查通过，已关闭）

- 平台`ResourceScheduler`由单活动票据升级为可配置资源池；保留默认全局串行兼容模式，插件可注入资源映射、池容量、队列上限与需物理互斥的池。
- 短剧节点固定`accelerator=1`、`cpu-media=2`、`control=8`：GPU/统一内存重任务仍严格互斥，音频与控制流可安全并发，不再被长视频任务整体阻塞。
- 每池执行独立优先级、超时、取消和背压；快照新增`active_items`与`pools`，同时保留旧`active`兼容字段。工作节点容量与活动数改为真实池容量/票据数上报。
- 本增量不改变LangGraph、租约世代、远端转发或具体模型路由；跨节点继续由健康感知路由器调度，节点内由资源池完成二级准入。
- 工作节点心跳过期时同时从SQLite发现仓库和进程内路由投影清退，避免服务重启后旧PID节点长期残留在管理接口。

### M9.156：人物0°全身→确认→90°/180°全身→0°半身自动流程（历史口径，已被M9.166覆盖）

- 分镜完成且审核关闭/通过后，自动同步确认并提取人物、道具、场景框架；项目加载只补提取框架，不直接启动图片模型。
- 人物固定四格：0°正面全身基准、90°侧面全身、180°背面全身、0°正面半身。生成按钮首次只生成0°全身；人工确认后串行生成其余三格，四图共同锁定身份、体型、服装、配饰和视角连续性。
- 半身照规范：正面平视特写型，人物居中、头顶微小留白、腰部裁切、手部完全出画、头部至腰部约占画高75%、双肩不触边且左右留白适中、纯色无杂物背景；补强脸部、妆发、领口、近景、表情和口型，不参与TripoSR几何重建。
- 分镜多参考职责固定为：0°半身=`face_primary`且独占人脸/妆发/近景表情口型，0°全身=`clothing_body`锁体型/服装/配饰，90°与180°=`angle_continuity`锁侧背轮廓和跨角度连续性；四图全部进入生成与审核，禁止降级为`audit_only`。
- 人物基准后端提示、Klein9B元数据、视觉验收与重试均统一为`front_full`；旧三格/45°产物通过`character-0-90-180-fullbody-front-half-v2`契约失效。
- 0°确认先同步生产ledger，只有确认成功才生成90°/180°；同步失败或项目切换均阻断后续角度。
- 90°/180°链使用按项目+资产键控控制器，每个网络与持久化边界复核project/session/abort；旧项目90°晚到不得启动180°。
- 当前厚涂0°会加载批准的Klein9B厚涂风格LoRA；男女Klein9B人物LoRA未获production_approved，不得偷偷加载。结果元数据记录实际LoRA文件、scale和SHA。
- 项目加载只自动补资产框架；图片中断恢复为pending并提示主动点击生成，禁止load/resume自动启动图片模型。
- 该M9.166左45°人物3D输入已被M9.187覆盖；当前固定使用已确认0°正面全身与`reference_angle=front_full`。
- 资产框架提取继续使用project/session键控单飞和晚到响应围栏，避免`assets already running`回归。

### M9.155：Flux场景/道具固定角度CFG锁定（2026-08-11）

- 场景、道具固定角度的Flux.2 Klein 9B 8-bit生成请求强制`CFG=1.5`、`steps=20`，不再使用执行器默认CFG。
- 人物固定角度继续走Qwen‑Edit CFG 1.0，不受本次变更影响；生成结果记录实际CFG与步数。

### M9.154：资产阶段统一单飞与确认门禁（已由M9.156最新临时自动流程覆盖）

- 项目加载与刷新不自动启动assets；仅用户点击进入资产时提取清单、创建上传卡槽，资产图片继续使用既定手动上传流程，不自动调用生图模型。
- 保留服务端前序与并发门禁；旧`already running`失败不能通过绕开LangGraph处理。
- 单飞按项目ID+session键控，跨项目不共享Promise；响应、异常、归档、替换、持久化和通知均受project/session/abort围栏保护。
- 资产页不再暴露批量自动生图主入口；各卡片通过导入按钮分别上传基准照与角度照，中断恢复也不得自动续跑模型。

### M9.153：分镜视频→合片纳入LangGraph统一编排（已完成）

- composition整批命令在执行前强制正整数、唯一集数门禁，重复集数不得触发任何内部合片。

- 正常批量合片由服务端`composition`阶段执行器接管，前端只提交一次全剧阶段请求，不再逐集循环旧merge接口。
- 合片前强制同步视频、音频、字幕的镜头级媒体包证据，由既有composition门禁核验三者批次一致后才执行。
- 单集人工返修保留局部操作，不承担正常全剧编排。
- 合片事务以项目ID、session和AbortSignal三重围栏保护响应、状态与持久化；旧项目晚到结果不会覆盖新项目。

### M9.152：分镜→资产阶段纳入LangGraph统一编排（最终稽查通过，已关闭）

- “生成图片”先自动确认分镜并同步生产台账，再进入资产阶段，禁止本地状态先行导致服务端门禁滞后。
- 资产提取由服务端`assets`阶段执行器统一编排，前端只提交一次`runStage(assets)`；人物、场景、道具与census作为阶段结果返回并持久化。
- 后续基准图、固定角度图仍沿现有统一图片任务生命周期执行，本增量不启动重模型。
- 分镜确认采用布尔事务门禁：审核、持久化、台账同步或项目上下文任一失败均阻断资产阶段，不允许“确认失败但继续生成”。
- 资产入口以single-flight Promise覆盖确认、同步、准备全过程；重复点击只允许一次资产阶段请求。

### M9.150：大纲、剧本与分镜统一切换 Qwen3-VL-32B（历史审核暂停口径，已被M9.163覆盖）

- 本条记录保留当时的审核暂停历史，不作为当前执行口径。当前唯一口径由M9.163规定：`qwen3-vl:32b`生成，`qwen2.5:72b`固定执行初审、最多一次修正和终审。
- 模型通过Ollama正式清单安装；文本生产仍复用统一任务UUID、owner、心跳、超时、停止、卸载、资源调度和LangGraph阶段门禁。自动修正必须保持条目数量、episode/shot标识和顺序不变，第二次终审不通过即阻断人工确认。
- 大纲已完整且处于待确认时，用户点击“生成剧本”会先写入大纲确认并立即启动剧本阶段；大纲缺失或失败时仍禁止越级。

### M9.151：Blender源视频接入MiniMax H3 Ref2VA（最终稽查通过，已关闭）

- 3D资产Blender阶段在七路静态审核通道之外输出24FPS、96帧的真实源视频，作为几何、运镜、遮挡和时序参考。
- 真实白瓷仙壶链已完成1024×576、24FPS、96帧、4.0秒MP4解码验证；确认后复制到hot归档，重启后任务结果、确认状态与源视频规格保持，媒体接口可读取。
- 分镜视频命令自动匹配已确认3D资产源视频和已确认人物正面定妆照；两项齐备时走本地MiniMax H3 Ref2VA INT8，缺任一项保留Wan2.2 I2V。
- H3独立图加载Ref2VA、Qwen3-VL编码器、视频/音频VAE，以`<Video 1>`和`<Picture 1>`分离职责；持久化prompt ID、阶段、心跳与输入证据，停止、超时、失败、恢复和关闭精确核销。
- 生产门禁同步补齐权威范围聚合：故事弧批次确认覆盖所属剧本分集，台词行仅作为可追踪明细；持久台账可按连续已确认阶段修复LangGraph旧失败投影，避免剧本已完成仍阻断分镜。
- 分镜改为Qwen3-VL-32B只生成512-token视觉导演方案，服务端以已确认剧本15—23个时间段确定性编译镜头，再执行时间轴、对白覆盖、字段与重复镜头硬校验；正式实测20镜、0—60秒、HTTP 200。故事事实库按分集去重镜头后再校验，避免同集多镜误报“集数重复”；前端显示服务端真实失败信息。
- 稽查整改：所有剧本台词/旁白必须逐句出现在分镜，遗漏任意1句即拒绝；每个新3D任务把worker报告中的`source_video_spec`与URL同时写入结果并随确认/重启持久化。
- 对白覆盖同时锁说话人与正文，角色错配不得以相同台词内容通过。

### M9.149：LangGraph 统一生产内核架构回正（最终稽查通过，已关闭）

- 统一11节点状态契约、30FPS、LangGraph SQLite检查点、生产台账、故事事实库和文本/图片/视频统一任务仓库。
- 全部重负载入口统一进入资源调度器，停止、恢复、超时与看门狗共用真实任务生命周期。
- 图片生产正式路由改为能力注册表解析，Schnell、Klein 9B、Qwen‑Edit、IP‑Adapter和多参考工作流可替换、禁用、卸载。
- 除最小生产内核外，资源调度、生产台账、故事事实库、统一任务仓库、LangGraph检查点和阶段执行器均已纳入扩展注册表，支持提供方查询、替换、启停和卸载；有状态扩展受控重启生效。
- 增加多实例负载均衡与高并发边界：API无状态化、资源池路由、服务端幂等键、任务世代、所有权租约、心跳续租、背压、节点失联重排和晚到结果CAS；本机SQLite实现与PostgreSQL/Redis分布式实现共用扩展协议。
- 已实现健康感知工作节点路由、共享工作节点发现与SQLite任务租约提供方；API选中远端后按原路径转发并携带防循环标头，实际执行节点进入响应。全部24处重负载入口执行前取得带世代租约，10秒续租、45秒过期，完成后精确释放；工作节点、资源池和8项基础设施绑定可查询。本机仍为容量1，跨主机部署必须替换分布式提供方。
- 服务关闭设置全局shutdown gate，持久任务失败化不再触发全局导演或122B审核模型。
- 人物/道具/场景资产卡、四类文本条目操作和四处颜色预设已抽成统一组件；同类实现出现3次及以上强制收口。
- 假说话人、情绪、口型、人脸、连续性、OCR及语音对齐审核已禁止返回通过；真实审核提供方缺失时明确阻断。
- 大纲至导出的正式入口均受LangGraph前置依赖门禁；分镜视频媒体包完成后分别持久化视频、音频和字幕证据，三者确认齐备才允许合片。
- 合片门禁按镜头校验video/audio/subtitle确认记录、内容指纹及同一媒体包审核批次，禁止跨版本拼接。
- 公开确认已改为LangGraph先验、台账后写并具补偿回滚；旧JSON流水线仅投影图状态；重负载执行前后执行双重租约围栏；五个正式前端生成入口只提交单次阶段命令，拆批、重试、终审、修复和媒体包生成由服务端阶段执行器接管。
- 兼容流水线取消已写入LangGraph权威状态，重启后保持`cancelled`并禁止批准、恢复或再次执行，JSON取消状态不再与图冲突。
- 规范：`docs/specs/短剧统一生产内核架构规范.md`。

### M9.147：ComfyUI 媒体增强与对话图片反推（2026-08-10）

- 项目对话框上传图片后可直接反推正向、负向提示词；视觉输入先缩放并限制帧数，避免旧版识别长时间阻塞。
- 接入 RealESRGAN x4 图片超分、RealESRGAN x4 + RIFE 4.9 视频超分插帧、MuseTalk 主口型同步，并保留 LatentSync 备用链。
- 人物一致性按需提供 PuLID-FLUX（FaceNet 后端）和 ReActor 修正，所有增强结果独立版本落盘，不覆盖原图。
- ComfyUI 节点、模型、前后端接口均已接通；26项回归测试、Vue类型检查、正式构建及各链路真实烟测通过。

### M9.146：FLUX.2 Klein 9B 国风厚涂 LoRA 候选库（2026-08-10）

- `models/loras/国风厚涂/` 已按风格、人物男女、灵兽归档5个原生FLUX.2 Klein 9B候选；旧FLUX.1权重已移出活动目录。
- 5个候选均在 `mlx-community/flux2-klein-9b-8bit` 完成真实加载出图；仅古代幻想风格达到国风厚涂候选标准，其余因平涂、伪文字或非神兽表现保持不合格测试隔离。
- 来源、许可、大小、SHA-256、测试图与结论登记于 `models/loras/Flux2Klein9B测试LoRA索引.json`，未进入正式或商用索引。
- 国风厚涂Klein‑9B基准图已接入逐模型批准索引：正式命令固定加载已通过的古代幻想风格；男女与灵兽权重虽已完成技术接线，但因视觉或许可未通过而由门禁排除。命令真实传递`--lora-paths/--lora-scales`并回传文件、权重和哈希审计信息。

文档边界：本文件仅保存开发里程碑、任务顺序与完成状态；BUG 提交、修复和复核记录统一保存到 `Dev_BUG_TRACKER.md`。

### M9.146：3D跨模块与极端边界规范补齐（2026-08-10）

- 3D规范升级为3.0，补齐最终脸强制2D接管、多人遮挡分层、TTS/动作时长冲突、2D/3D仲裁、系统故障降级、跨项目版本引用、资产ID冲突和多机位视线连续性。
- 同步到从剧本到成片总规范与AI直接执行提示词；已有Klein 9B、TripoSR、Blender、2D身份链和归档门禁保持不变。

### M9.145：Klein 9B → TripoSR → Blender 三维资产链（历史角度口径，已被M9.163覆盖）

- 该里程碑的左45°首图和M9.156三槽均为历史口径；当前唯一标准由M9.163规定为人物六格、Blender七角度、H3 Ref2VA→Qwen‑Edit串行细化。人物、灵兽继续进入2D身份+3D身体服装动作混合链，场景与复用独立道具进入3D链。
- TripoSR在本机MPS完成单图重建，Blender 5无界面自动清理、保守减面、落地居中并输出GLB、Blend及七视图RGB、蒙版、深度与法线。
- 前端资产卡提供生成、停止、确认、下载和七视图审核；后端复用唯一UUID、心跳、超时、有限重试、进程树终止、重启恢复及看门狗。
- 3D只审核结构、姿态和服装/道具大致对应，不审核面部相似度；面部一致性继续由2D身份链锁定。
- 规范：`docs/specs/短剧3D资产生产规范.md`、`docs/specs/短剧从剧本到成片生产规范.md`、`plugins/builtin/short_drama/templates/prompts/AI_SHORT_DRAMA_PRODUCTION_SPEC.md`。

### M9.144：大纲生产任务可靠性与性能闭环（历史模型口径，已被M9.163覆盖）

- 大纲总纲和分集批次统一登记服务端唯一任务ID、真实工作线程、阶段、心跳和1800秒硬超时。
- 当时的27B推理登记唯一owner job_id；当前qwen3-vl:32b生成继续沿用同一owner隔离，停止或超时仅终止目标owner。
- 大纲停止按项目ID与客户端生成批次精确终止；服务重启和关闭统一回收大纲、剧本非终态，禁止残留generating。
- 历史27B Q8复用与122B审核模型口径已废止；当前按M9.163固定为qwen3-vl:32b生成、qwen2.5:72b初审→最多一次修正→终审，串行加载并在完成后卸载。
- 前端大纲结果整段即时展示，项目切换和页面中断立即持久化失败并定向停止后端任务。

## 一、历史路线顺序与现行执行约束

1. M1 → M11 仅表示产品路线依赖顺序，不构成自动执行授权。
2. 当前只处理用户明确反馈的一条问题；完成开发、测试、稽查和记录闭环后停止，等待用户确认下一条。
3. 软件测试与代码稽查属于当前问题的完成门禁，不是新的问题；任一失败均按原 BUG 编号退回主线开发。
4. 当前状态以文件顶部最新未关闭条目和 `Dev_BUG_TRACKER.md` 为准，历史条目不得自动恢复执行。
5. 所有实现遵守 `DIRECTORY_README.md`；不得创建 `server/`、`platform/registry/` 或其他未登记目录。
6. 平台通用能力进入 `platform/`，短剧业务只进入 `plugins/builtin/short_drama/`，跨层结构只进入 `shared/contracts/`。
7. 每项必须同时具备实现、正常场景测试、直接异常测试和文档同步才算完成。

## 二、目标与顺序

| 目标 | 名称 | 前置条件 |
|---|---|---|
| M1 | Skill 生成智能体并串联协作 | 无 |
| M2 | 短剧流程完整运行 | M1 完成 |
| M3 | 任务列表与实时进度 | M2 完成 |
| M4 | 可配置开发/稽查 Skill 与模型对话控制 | M1、M3 完成 |
| M5 | 真实能力提供方与生产运行闭环 | M4 完成 |
| M6 | 插件安全、供应链与审计闭环 | M5 完成 |
| M7 | 开发 AI 与稽查 AI 协作闭环 | M6 完成 |
| M8 | 短剧真实视频工作流闭环 | M7 完成 |
| M9 | 全行业通用流程 Skill 机器人 | M8 完成 |
| M10 | 私有化部署、监控与灾备交付 | M9 完成 |
| M11 | SaaS 多租户、配额与商业化能力 | M10 完成 |

## 三、M1：Skill 生成智能体并串联协作

| # | 任务 | 正式文件 |
|---|---|---|
| 1.1 | 扫描 Skill manifest 并注册 | `platform/discovery/skill_registry.py` |
| 1.2 | Skill 生成独立智能体实例 | `platform/discovery/agent_registry.py` |
| 1.3 | 建立 Skill 与智能体 1:1 映射 | `platform/discovery/agent_mapper.py` |
| 1.4 | 实现智能体封闭生命周期 | `platform/core/agent_lifecycle.py` |
| 1.5 | 实现项目、智能体上下文隔离 | `platform/core/agent_context.py` |
| 1.6 | 实现智能体注册与状态 HTTP 路径 | `platform/bootstrap/application.py` |
| 1.7 | 实现上游完成后唤醒下游的调度器 | `platform/core/agent_scheduler.py` |
| 1.8 | 完成双智能体串联、停止、恢复和隔离集成测试 | `tests/integration/test_agent_pipeline.py` |

验收：新增 Skill 自动生成唯一智能体；状态按 idle → loading → running → waiting_human/completed/failed 合法转换；A 完成自动唤醒 B；跨项目和跨智能体上下文不可读取；注册和状态路径通过真实 HTTP 测试。

## 四、M2：短剧插件流程完整运行

固定流程：项目需求 → 大纲 → 剧本 → 分镜 → 资产 → 图片 → 视频 → 音频 → 字幕 → 合片 → 审核与导出。

| # | 任务 | 正式文件 |
|---|---|---|
| 2.1 | 建立短剧插件 manifest、权限和入口 | `plugins/builtin/short_drama/manifests/plugin.yaml` |
| 2.2 | 建立流程状态、节点输入输出契约 | `shared/contracts/short-drama.contract.ts`、`shared/contracts/short-drama.schema.json` |
| 2.3 | 实现项目需求、大纲、剧本和分镜节点 | `plugins/builtin/short_drama/workflows/text_pipeline.py` |
| 2.4 | 实现资产、图片、视频、音频和字幕节点 | `plugins/builtin/short_drama/workflows/media_pipeline.py` |
| 2.5 | 实现合片、审核和导出节点 | `plugins/builtin/short_drama/workflows/delivery_pipeline.py` |
| 2.6 | 接入队列、事件、人工关口、停止与恢复 | `plugins/builtin/short_drama/workflows/pipeline.py` |
| 2.7 | 实现插件后端公开入口 | `plugins/builtin/short_drama/backend/main.py` |
| 2.8 | 接入现有前端流程导航、预览和插件插槽 | `plugins/builtin/short_drama/frontend/`、`frontend/src/plugin-slots/registry.ts` |
| 2.9 | 完成全流程、失败、取消、刷新和恢复测试 | `tests/integration/test_short_drama_pipeline.py` |

验收：全部节点按序运行并产生可解析的版本化产物；失败和取消不伪造成功；人工关口不可绕过；服务重启后可恢复；业务逻辑不进入平台底座。

## 五、M3：任务列表与实时进度

| # | 任务 | 正式文件 |
|---|---|---|
| 3.1 | 实现租户/项目隔离的任务查询服务 | `platform/queue/task_service.py` |
| 3.2 | 实现任务列表、详情、取消和恢复 HTTP 路径 | `platform/bootstrap/application.py` |
| 3.3 | 将任务状态事件投影为实时进度 | `platform/events/task_projection.py` |
| 3.4 | 建立前端任务服务与业务 Store | `frontend/src/services/task-service.ts`、`frontend/src/stores/task.store.ts` |
| 3.5 | 接入任务列表、详情、进度和错误展示 | `frontend/src/components/task/` |
| 3.6 | 完成跨租户、幂等、刷新恢复和实时进度测试 | `tests/integration/test_task_tracking.py`、`tests/e2e/test_task_tracking.py` |

验收：任务列表和详情只返回授权范围；状态与进度实时更新；刷新后恢复；取消和恢复遵守封闭状态转换；跨租户访问被拒绝；前后端契约一致。

## 六、M4：可配置开发/稽查 Skill 与模型对话控制

| # | 任务 | 正式文件 |
|---|---|---|
| 4.1 | 建立开发/稽查 Skill、模型与对话配置契约 | `shared/contracts/agent-configuration.contract.ts`、`shared/contracts/agent-configuration.schema.json` |
| 4.2 | 建立开发与稽查内置 Skill manifest | `plugins/builtin/system_agents/skills/` |
| 4.3 | 实现模型注册、能力约束和模型选择 | `platform/llm_gateway/model_registry.py` |
| 4.4 | 实现智能体配置版本、权限边界和模型绑定 | `platform/core/agent_configuration.py` |
| 4.5 | 实现模型驱动的配置对话与复杂任务入口 | `platform/core/agent_conversation.py` |
| 4.6 | 实现模型、配置和对话 HTTP 路径 | `platform/bootstrap/application.py` |
| 4.7 | 实现前端 Skill、模型和对话配置界面 | `frontend/src/`、`plugins/builtin/system_agents/frontend/` |
| 4.8 | 完成角色隔离、模型切换、对话配置和复杂任务测试 | `tests/integration/test_agent_configuration.py` |

验收：开发 AI 与稽查 AI 均由独立 Skill 生成；模型可查询、选择和切换；配置变更版本化、可追溯；稽查 Skill 保持只读；用户能通过对话生成并确认复杂配置与任务；未配置真实模型时明确失败，不以模拟回复冒充成功。

## 七、M5：真实能力提供方与生产运行闭环

| # | 任务 | 正式文件 |
|---|---|---|
| 5.1 | 建立模型与媒体提供方统一配置、密钥引用和健康状态契约 | `shared/contracts/provider.contract.ts`、`shared/contracts/provider.schema.json` |
| 5.2 | 实现 OpenAI 兼容模型客户端、超时、取消和结构化响应校验 | `platform/llm_gateway/` |
| 5.3 | 实现文字、图片、视频和音频提供方适配注册 | `platform/adapters/` |
| 5.4 | 实现调用限流、有限重试、熔断、降级和错误归一化 | `platform/circuit_breaker/`、`platform/adapters/` |
| 5.5 | 实现 Token、耗时、费用、请求和产物审计 | `platform/events/`、`platform/llm_gateway/` |
| 5.6 | 将短剧全部生成节点绑定真实提供方注册表 | `plugins/builtin/short_drama/workflows/` |
| 5.7 | 实现提供方配置、测试连接和运行状态 HTTP/前端入口 | `platform/bootstrap/application.py`、`frontend/src/` |
| 5.8 | 完成真实客户端夹具、故障降级、成本审计和短剧生产集成测试 | `tests/integration/`、`tests/e2e/` |

验收：所有模型与媒体调用只使用已授权真实提供方；密钥不进入源码、前端和日志；超时、限流、取消、重试和熔断状态可追踪；费用与产物可审计；短剧流程不存在模拟成功。

## 八、M6：插件安全、供应链与审计闭环

| # | 任务 | 正式文件 |
|---|---|---|
| 6.1 | 建立插件签名、哈希、来源和 SBOM 契约 | `shared/contracts/plugin-security.contract.ts`、`shared/contracts/plugin-security.schema.json` |
| 6.2 | 实现安装前签名、完整性、兼容版本和权限校验 | `platform/discovery/`、`platform/security/` |
| 6.3 | 实现插件文件、进程、网络和数据访问隔离 | `platform/security/` |
| 6.4 | 实现 Skill 工具调用授权、输入净化和输出脱敏 | `platform/security/`、`platform/core/` |
| 6.5 | 实现不可绕过的行为审计、导出审计和保留策略 | `platform/events/`、`platform/security/` |
| 6.6 | 建立依赖锁定、SBOM、漏洞扫描和许可证门禁 | `scripts/`、`deploy/` |
| 6.7 | 实现插件安装、启停、升级、回滚和卸载管理界面 | `frontend/src/` |
| 6.8 | 完成越权、逃逸、篡改、恶意依赖和审计完整性安全测试 | `tests/security/` |

验收：未签名、被篡改、不兼容或越权插件无法加载；稽查 Skill 始终只读；高危能力默认拒绝；供应链和关键行为具有可验证证据链。

## 九、M7：开发、测试与稽查 AI 协作闭环

| # | 任务 | 正式文件 |
|---|---|---|
| 7.1 | 建立开发、测试、稽查协作会话、任务交接、测试报告、稽查报告和整改指令契约 | `shared/contracts/agent-collaboration.contract.ts`、`shared/contracts/agent-collaboration.schema.json` |
| 7.2 | 实现开发 AI 提交稽查、稽查 AI 返回只读报告 | `platform/core/agent_collaboration.py` |
| 7.3 | 实现稽查问题转为开发整改任务并回到原主线 | `platform/core/agent_scheduler.py`、`platform/core/agent_collaboration.py` |
| 7.4 | 实现协作上下文、证据、文件引用和任务状态隔离 | `platform/core/agent_context.py`、`platform/core/agent_collaboration.py` |
| 7.5 | 通过 LangGraph 实现串行、并行、暂停、恢复、失败重试和人工接管 | `platform/adapters/langgraph_orchestrator.py`、`platform/core/agent_scheduler.py` |
| 7.6 | 实现协作会话、交接、报告、整改和确认 HTTP 路径 | `platform/bootstrap/application.py` |
| 7.7 | 实现双 AI 对话、任务分工、稽查结果和整改进度界面 | `plugins/builtin/system_agents/frontend/`、`frontend/src/` |
| 7.8 | 完成权限隔离、交接续跑、循环整改和异常恢复测试 | `tests/integration/test_agent_collaboration.py`、`tests/e2e/test_agent_collaboration.py` |

验收：开发 AI 自动提交软件测试；测试 AI 仅验证本次增量并形成完整报告；测试通过后自动提交只读稽查；测试或稽查失败均自动回到开发 AI；整改后重新经过测试与稽查直至通过；全过程可暂停、恢复、追踪和人工接管；不得跳过关口或形成无限整改循环。

## 十、M8：短剧真实视频工作流闭环

| # | 任务 | 正式文件 |
|---|---|---|
| 8.1 | 校准需求至导出的 11 节点输入、输出、状态、依赖与 LangGraph 检查点契约 | `shared/contracts/short-drama.contract.ts`、`shared/contracts/short-drama.schema.json` |
| 8.2 | 跑通需求、大纲、剧本、分镜和资产的真实模型链路 | `plugins/builtin/short_drama/workflows/text_pipeline.py` |
| 8.3 | 跑通人物、场景、道具和镜头图片生成与版本管理 | `plugins/builtin/short_drama/workflows/media_pipeline.py` |
| 8.4 | 跑通图生视频、文生视频、镜头重试和局部重生成 | `plugins/builtin/short_drama/workflows/media_pipeline.py` |
| 8.5 | 跑通配音、音效、字幕、时间轴和音画同步 | `plugins/builtin/short_drama/workflows/media_pipeline.py` |
| 8.6 | 跑通合片、自动审核、人工确认、修复和最终导出 | `plugins/builtin/short_drama/workflows/delivery_pipeline.py` |
| 8.7 | 接通原版工作台全部真实状态、预览、确认和恢复操作 | `plugins/builtin/short_drama/frontend/` |
| 8.8 | 完成 LangGraph 全流程、单节点失败、停止恢复、刷新恢复和成片验收 | `tests/integration/test_short_drama_production.py`、`tests/e2e/test_short_drama_production.py` |
| 8.9 | 在新建项目和项目设置中实现中文 LoRA 风格自动匹配、固定选择、手动覆盖和探索模式 | `plugins/builtin/short_drama/frontend/`、`plugins/builtin/short_drama/backend/`、`shared/contracts/short-drama.contract.ts` |
| 8.10 | 实现通用对话智能体闭环：真实需求理解、上下文注入、长期记忆、Skill 选择、计划执行、澄清控制和确认式变更 | `platform/core/agent_conversation.py`、`platform/bootstrap/application.py`、`plugins/builtin/system_agents/frontend/` |

验收：从项目需求到最终成片全部节点使用真实提供方；每个中间产物可查看、版本化和局部重做；失败、取消和人工关口不可伪造成成功；刷新与服务重启后可恢复；最终视频、音频、字幕和审核记录完整可导出；LoRA 默认按短剧类型确定性匹配并锁定项目版本，用户可在界面确认或覆盖，随机仅在主动开启探索模式时生效；机器人能够结合 Skill、项目、任务和长期偏好理解真实需求，信息充分时直接执行，信息不足时只提出必要澄清，高风险变更形成可追溯确认提案。

## 十一、M9：全行业通用流程 Skill 机器人

| # | 任务 | 正式文件 |
|---|---|---|
| 9.1 | 建立行业、业务流程、流程 Skill、机器人和模型绑定契约 | `shared/contracts/industry-agent.contract.ts`、`shared/contracts/industry-agent.schema.json` |
| 9.2 | 实现通用流程 Skill 模板、manifest 校验和注册 | `platform/discovery/industry_skill_registry.py`、`plugins/` |
| 9.3 | 实现每个流程 Skill 生成唯一隔离机器人的生命周期 | `platform/discovery/agent_registry.py`、`platform/core/agent_lifecycle.py` |
| 9.4 | 实现每个流程 Skill 机器人独立模型选择、版本配置和能力校验 | `platform/core/agent_configuration.py`、`platform/llm_gateway/` |
| 9.5 | 通过 LangGraph 组合流程 Skill 机器人并支持串行、并行、分支、暂停和恢复 | `platform/adapters/langgraph_orchestrator.py`、`platform/core/agent_scheduler.py` |
| 9.6 | 实现通过对话创建、修改、连接和运行行业流程机器人 | `platform/core/agent_conversation.py`、`platform/bootstrap/application.py` |
| 9.7 | 实现行业模板、流程机器人、模型和拓扑配置通用界面 | `frontend/src/`、`frontend/src/plugin-slots/` |
| 9.8 | 将短剧流程作为首个行业模板接入并完成跨行业扩展验证 | `plugins/builtin/short_drama/`、`tests/integration/test_industry_agents.py`、`tests/e2e/test_industry_agents.py` |
| 9.9 | 将短剧 Skill 按六类机器人展示并接通项目级启停、自动模型策略、持久化和执行门禁 | `plugins/builtin/short_drama/frontend/`、`frontend/src/services/industry-agent-service.ts`、`platform/bootstrap/application.py` |
| 9.10 | 在短剧 Skill 卡片接入独立模型选择、云端 API 提供方注册和项目级模型绑定 | `plugins/builtin/short_drama/frontend/`、`frontend/src/services/agent-configuration-service.ts`、`frontend/src/services/provider-service.ts` |
| 9.11 | 增加 Ollama、LM Studio、LocalAI 与 OpenAI 兼容本地模型配置，限制明文 HTTP 仅允许回环地址 | `plugins/builtin/short_drama/frontend/`、`platform/adapters/provider_service.py` |
| 9.12 | 将审核机器人简化为省成本、均衡、高质量三档方案，并直接提供初审/终审切换及文本、视觉、音频独立模型选择 | `plugins/builtin/short_drama/frontend/` |
| 9.13 | 将模型配置重构为两层选择：先选当前机器人、初审或终审，再选本地或云端；模型使用预设下拉框且仅地址手动填写 | `plugins/builtin/short_drama/frontend/` |
| 9.14 | 进入机器人模型配置后自动收起 Skill 分类左栏，并将返回入口固定到收起后的左栏 | `plugins/builtin/short_drama/frontend/` |
| 9.15 | 将本地与云端模型来源设为互斥选择，每个主机器人、初审或终审角色只允许保存一个当前模型绑定 | `plugins/builtin/short_drama/frontend/` |
| 9.16 | 去除本地和云端的独立接入按钮，由统一“保存当前配置”自动完成模型注册与角色绑定 | `plugins/builtin/short_drama/frontend/` |
| 9.17 | 自动发现本机 Ollama 模型并为六类机器人、初审和终审写入能力匹配的项目级默认配置 | `plugins/builtin/short_drama/frontend/`、`skill_bindings` 项目阶段 |
| 9.18 | 修复主模型、初审和终审共用表单值的问题，为每个机器人角色建立独立草稿和持久化模型键 | `plugins/builtin/short_drama/frontend/` |
| 9.19 | 统一 Skill 列表和模型配置按钮为白底、灰边、深色文字的轻量操作样式 | `plugins/builtin/short_drama/frontend/styles.css` |
| 9.20 | 修复模型保存顺序、服务重启后模型重注册、行业机器人解析及项目绑定持久化 | `plugins/builtin/short_drama/frontend/`、`platform/bootstrap/application.py`、`platform/discovery/agent_registry.py` |
| 9.21 | 增加文本、视觉、音频、视频模型类别下拉，并按机器人能力过滤本地和云端模型列表 | `plugins/builtin/short_drama/frontend/` |
| 9.22 | 补全本地视觉模型目录并标记安装状态；启用卡片使用绿色状态，停用卡片使用灰色状态 | `plugins/builtin/short_drama/frontend/`、`plugins/builtin/short_drama/frontend/styles.css` |
| 9.23 | 完成 Mac 快速跑通配置：安装 Qwen3 8B、CosyVoice2 0.5B、Wan2.1 T2V 1.3B，五类流程绑定轻量本地模型并暂停审核 | `models/`、`plugins/builtin/short_drama/frontend/`、`skill_bindings` 项目阶段 |
| 9.24 | 移除 Skill 卡片“模型与 API”入口及模型配置子界面，流程模型统一使用系统自动配置 | `plugins/builtin/short_drama/frontend/` |
| 9.25 | 人物、场景、道具、细节图和分镜图片支持点击打开统一放大预览 | `plugins/builtin/short_drama/frontend/` |
| 9.26 | 恢复短剧 8787 持久化兼容服务，重新接入历史项目、阶段数据和结果媒体文件 | `plugins/builtin/short_drama/backend/compat_server.py` |
| 9.27 | 恢复本地故事总纲与分集梗概生成接口，使用 Qwen3 8B 返回结构化结果 | `plugins/builtin/short_drama/backend/compat_server.py` |
| 9.28 | 恢复项目对话、对话历史、草稿、会话和能力查询接口，使用 Qwen3 8B 正常响应 | `plugins/builtin/short_drama/backend/compat_server.py` |
| 9.29 | 资产卡片改为双列等宽 9:16 大图布局，图片下方提供“导入图片”和“重新生成”操作 | `plugins/builtin/short_drama/frontend/` |
| 9.30 | 资产图片操作移入图片底部，左上角增加“图片简介”并在图片内显示介绍浮层 | `plugins/builtin/short_drama/frontend/` |
| 9.31 | 取消资产、分镜画面和分镜视频的单张确认；启动下一流程时自动确认当前批次，生成分镜视频直接进入视频生产 | `plugins/builtin/short_drama/frontend/` |
| 9.32 | 恢复分镜视频提交、状态查询和媒体访问接口，接入本地 Wan2.2 图生视频及持久化任务结果 | `plugins/builtin/short_drama/backend/compat_server.py` |
| 9.33 | 接入本地 Qwen3-TTS 配音、MuseTalk 主口型、LatentSync 备用口型、CampPlus 声纹检查、情绪检查、口型完整性检查和音频混合 | `plugins/builtin/short_drama/backend/compat_server.py` |
| 9.34 | 接入 OpenPose 全身、手部和面部骨骼提取，并将 SDXL OpenPose ControlNet 与 IP-Adapter 人物一致性生图联合绑定 | `plugins/builtin/short_drama/backend/compat_server.py`、`comfyui_controlnet_aux` |

验收：任何行业可通过标准 manifest 注册多个业务流程 Skill；每个流程 Skill 自动生成唯一隔离机器人并独立选择模型；机器人通过 LangGraph 组成可恢复流程；用户可通过对话和界面配置流程、模型与连接关系；短剧模板完整覆盖需求、大纲、剧本、分镜、资产、图片、视频、音频、字幕、合片、审核与导出，且不把短剧逻辑写入平台底座。

## 十二、M10：私有化部署、监控与灾备交付

| # | 任务 | 正式文件 |
|---|---|---|
| 10.1 | 建立开发、测试、私有化生产环境配置模板 | `deploy/` |
| 10.2 | 实现容器镜像、健康检查、依赖检查和一键安装 | `deploy/`、`scripts/` |
| 10.3 | 实现数据库、对象存储、队列和检查点持久化适配 | `platform/adapters/` |
| 10.4 | 实现日志、指标、链路追踪和告警规则 | `platform/events/`、`deploy/` |
| 10.5 | 实现配置、数据库、资产和审计日志备份恢复 | `scripts/`、`docs/operations/` |
| 10.6 | 实现升级迁移、兼容校验和版本回滚 | `scripts/`、`deploy/` |
| 10.7 | 完成故障注入、恢复演练、容量和性能测试 | `tests/integration/`、`tests/e2e/` |
| 10.8 | 校准安装、运维、事件响应和灾难恢复文档 | `docs/operations/` |

验收：全新环境可重复安装；升级可回滚；服务、数据库和资产故障均可恢复；监控、告警、备份及灾难恢复形成真实演练证据。

## 十三、M11：SaaS 多租户、配额与商业化能力

| # | 任务 | 正式文件 |
|---|---|---|
| 11.1 | 完善租户、成员、角色、资源范围和租户配置契约 | `shared/contracts/` |
| 11.2 | 实现全链路租户隔离、租户密钥和数据生命周期 | `platform/tenant/`、`platform/security/` |
| 11.3 | 实现模型、任务、并发、存储和插件配额 | `platform/tenant/`、`platform/queue/` |
| 11.4 | 实现用量计量、账单事件和外部计费适配边界 | `platform/events/`、`platform/adapters/` |
| 11.5 | 实现租户控制台、成员权限、配额和用量界面 | `frontend/src/` |
| 11.6 | 实现集群任务协调、服务发现和故障转移 | `platform/queue/`、`deploy/` |
| 11.7 | 完成跨租户攻击、并发、压力、计量准确性和数据销毁测试 | `tests/security/`、`tests/e2e/` |
| 11.8 | 完成 SaaS 商业化交付验收与风险关闭 | `docs/product/`、`docs/risks/`、`docs/operations/` |

验收：租户数据、配置、密钥、任务、资产和审计完全隔离；配额与计量准确；集群故障可转移；租户注销按策略完成可审计销毁。

## 十四、历史执行结果

- M9.141：短剧大纲生成新增全剧剧情状态表、标题与核心事件唯一、人物白名单与近形姓名禁止、剧情阶段单向、不可逆状态变化、反派手段差异化及跨集伏笔门禁；后续分批生成携带全部已生成分集，后端对分集数量、连续编号、空内容、重复标题和重复梗概执行确定性拒绝。

- 状态：M1、M2、M3 全部完成。
- 验证：92 项 Python 单元、契约、集成、端到端与安全测试全部通过；TypeScript 契约编译、Vue 类型检查与 Vite 正式构建通过；Python 编译、隔离环境可编辑安装、正式启动入口和 HTTP 健康检查通过。
- 边界：文字、图片、视频和音频生成只消费显式注入的真实能力提供方，不内置演示输出或伪造模型结果。
- M4 状态：M4.1—M4.8 全部完成；开发/稽查 Skill、模型选择、版本化配置、真实模型对话、确认式复杂任务、HTTP 与前端界面已落地。
- M4 验证：116 项 Python 单元、契约、集成、端到端与安全测试通过；18 条 OpenAPI 路径校准；TypeScript 契约编译、Vue 类型检查、Vite 正式构建、Python 编译、隔离安装和正式启动健康检查通过。
- M5 状态：M5.1—M5.8 全部完成；真实提供方配置、调用、韧性、审计、短剧绑定及管理界面已落地。
- M5 验证：151 项 Python 测试、TypeScript 契约编译、Vue 类型检查和 Vite 正式构建通过。
- M6 状态：M6.1—M6.8 全部完成；插件验证、沙箱、工具安全、审计、供应链门禁和管理界面已落地。
- M6 验证：163 项 Python 测试、SBOM 门禁、TypeScript 契约编译、Vue 类型检查和 Vite 正式构建通过。
- M7 状态：M7.1—M7.8 全部完成；LangGraph 已驱动串行、并行、重试、持久中断恢复和人工接管。
- M7 验证：166 项 Python 测试、SBOM 门禁、Vue 类型检查和 Vite 正式构建通过。
- M8 状态：M8.1—M8.10 全部完成；短剧真实生产、LangGraph 持久恢复、局部重做、人工确认、中文 LoRA 锁定及通用对话智能体闭环已落地。
- M8 验证：199 项 Python 测试、SBOM 门禁、Python 编译、Vue 类型检查和 Vite 正式构建通过。
- M9 状态：M9.1—M9.8 全部完成；全行业流程 Skill 机器人、独立模型和 LangGraph 拓扑已落地。
- M9 验证：184 项 Python 测试、SBOM 门禁、Vue 类型检查和 Vite 正式构建通过。
- M10 状态：M10.1—M10.8 全部完成；私有化安装、持久化、可观测性、备份恢复和升级回滚已落地。
- M10 验证：196 项 Python 测试、SBOM 门禁、Python 编译、Vue 类型检查和 Vite 正式构建通过。
- M11 状态：按用户指令暂停，未开始 M11.1。
- 已完成增补功能以代码、测试、产品进度和项目记忆为准，不再逐条写入本开发计划。
- M9.96：国风浅涂人物 LoRA 库已按仙侠人物清单精简为男女各 8 项；新增指定男女各 6 项，保留空灵仙气与仙侠幻想，旧人物 LoRA 从正式目录及商用索引移除。
- M9.97：生图重负载任务已接入唯一任务ID、实际进程状态、PID/进程组、心跳、排队与执行超时、单次重试、启动前回收、服务重启恢复和任务/进程双向看门狗。
- M9.99：生图服务关闭新增原子门禁，禁止关闭快照后再注册模型进程；国风浅涂正式目录、运行代码、下载脚本和41条商用LoRA索引已统一为`models/loras/国风浅涂/`，20个非商用测试权重保持索引外隔离。
- M9.101：资产基准图已接通两段式独立串行链路；FLUX.1 Schnell 单独完成生成并将中间成品保存到磁盘、释放模型后，Qwen Image Edit 2511 单独读取该文件，通过真实噪声蒙版执行局部瑕疵修复并输出最终图。两套模型使用不同ComfyUI提示图与prompt ID，服务任务持久化阶段、prompt ID和心跳，并保持独立模型生命周期，禁止嵌套为同一工作流。
- M9.102：按用户指令清除`models/loras/`全部98个LoRA权重并同步清空模型索引与商用索引；4.1GB文件已移入废纸篓隔离目录，可恢复。LoRA风格接口当前返回空列表。
- M9.103：国风浅涂已重新安装20个可商用FLUX.1 LoRA，风格、女性、男性、仙宠各5个；全部通过许可、FLUX.1底模双重元数据、Safetensors权重键、大小和SHA-256校验。基准图Qwen局部修复由40.86GB BF16切换为20.53GB FP8Mixed并降至8步；停止、重启、看门狗及失败轮询同步取消Comfy prompt，已清除任务失败后仍占队列的幽灵Qwen任务。
- M9.104（历史三槽口径，已被M9.163覆盖）：独立Qwen Image Edit能力继续沿用，但当前固定角度扩展为多参考六格；头顶完整与脚部可见门禁继续有效。
- M9.105：剧本生成新增唯一任务ID、服务端活动线程登记、持久心跳、330秒超时看门狗与重启回收；前端每5秒持久化任务心跳，中断状态立即写回失败，空内容占位不再冒充已完成集，普通失败最多重试一次并仅补生成缺失集数。
- M9.117：场景固定角度改为主平视、左45度、右45度和高角度微俯视四张；左右45度使用独立标签、互斥方向提示和独立图片槽，历史单45度/低角度数据在继续生成时按新定义归一化。
- M9.126（历史人物角度链，已被M9.163覆盖）：曾使用Schnell、RealVisXL、IP-Adapter与OpenPose串行链；当前固定角度唯一执行链为Qwen-Edit多参考六格。
- M9.127：国风浅涂“国风仙韵”和国风厚涂“油画仙韵”两份 FLUX.1 LoRA 已获准直接用于对应项目的 Schnell 基准图；固定角度阶段不继承 LoRA。
- M9.128（历史5%安全边距，已被M9.189覆盖）：当前全部人物全身角度统一为发顶上方纯背景至少8%、鞋底下方纯背景至少3%，均为最低值而非固定值。
- M9.129：道具基准图新增单一独立道具、纯中性背景、无场景环境、无文字招牌、无真人人体五项硬验收；道具禁止加载人物风格 LoRA，商店、街道、房间和建筑等场景图无法再以道具图放行。
- M9.130（图片预览能力保留；历史5%归一口径已被M9.189覆盖）：项目图片预览继续支持适窗、缩放、拖拽和复位；人物全身角度的确定性前景归一现执行发顶至少8%、鞋底至少3%的非固定安全区下限，再进入身份、方向、服装、体型和尺寸验收。
- M9.131：人物固定角度一致性门禁已纠正错误放行：正面全身独立核对脸型年龄、刘海分缝、扎发/辫子、发长发色、领口扣饰、服装主色和装饰复杂度；旧全身服装引用在重生时清除，缺失引用强制回退到已确认基准图。当前错误候选已作废，新候选因身份、发型、服装不一致被正确拦截，未进入人工确认。
- M9.132：“就要这张”确认链路已解除生产台账同步等待，确认后立即切换生成状态并异步登记台账；人物基准确认时强制重置失效服装引用为当前基准图，后端缺失引用同步回退。真实页面验证按钮点击后立即消失、显示生成中和暂停，并创建全身角度任务。
- M9.125：全网及 GitHub 扩展检索后下载14个 FLUX.1 仅测试候选，严格归入国风浅涂或国风厚涂：风格5、女性3、男性3、灵兽3；许可、来源、大小、SHA-256、Safetensors 与 FLUX 权重键登记到独立测试索引，正式模型索引和商用索引继续保持为空，未实图验收前禁止进入生产。
- 所有缺陷提交、修复证据和复核结论统一记录于 `Dev_BUG_TRACKER.md`。

## 十五、最终完成标准

### M10.9：现有资源作用域隔离（最终复稽查通过，已完成）

- 修复资源列表可选过滤、跨所有者ID删除、伪项目创建及通用媒体URL绕过；资源读写改为tenant/user/scope/project一致匹配与专用媒体入口。
- 旧资源列表动态升级安全URL，通用媒体入口拒绝resources目录；关联`114 passed`、编译和Vue类型检查通过。
- 首轮复测通过后稽查发现历史空身份记录旁路，已在专用媒体及删除入口增加非空scope门禁，待整改复测。
- 整改独立复测及最终只读复稽查通过：冻结提交`7ccc1b7`关联`114 passed`，编译与Vue类型检查通过；空身份、跨所有者和旧通用媒体旁路全部失败关闭。

### M10.8：可观测Exporter正式生命周期接线（最终复稽查通过，已完成）

- `RuntimeObservability`将正式服务请求与启停事件写入JSONL，并原子发布Prometheus textfile；HTTP活动数、请求数、累计延时以method/status_class有界标签输出。
- request_id/trace_id沿用请求头或自动生成，仅进入关联日志而不进入指标标签；定向`8 passed`及编译通过。
- 首轮独立复测`113 passed`；稽查发现keep-alive解析前可能继承上次请求头，已改为每请求先生成并仅由当前解析成功的有界合法头替换，待整改复测。
- 整改独立复测及最终只读复稽查通过：冻结提交`749875b`关联`114 passed`；长连接请求关联不跨代，EOF不伪造500且活动计数归零，敏感字段和高基数指标门禁保持。

### M10.7：单节点混合负载容量基准（最终复稽查通过，已完成）

- 正式调度器混合运行control/cpu-media/accelerator，动态覆盖pool/tenant/project背压、取消唤醒、线程和票据归零。
- Darwin arm64小样本吞吐939.06 req/s，control P99 1.582ms、取消0.050ms；基准/文档`21 passed`。数值仅作当前硬件回归基线，不是生产SLA。
- 整改独立复测及最终只读复稽查通过：冻结提交`d674435`关联`22 passed`，峰值活动不得超过容量总和已成为失败关闭门禁，正式复跑7=4+2+1且资源、票据和线程全部归零。

### M10.5：单节点一致性备份恢复（最终复稽查通过，已完成）

- 五类白名单数据先生成隔离快照；SQLite使用在线backup API，运行边车不归档，链接/特殊文件/越界成员失败关闭。
- manifest v2保存归档和逐文件完整性；原子发布及临时恢复通过全量集合/大小/哈希后才切换目标。
- 关联`26 passed`；WAL并发写隔离演练恢复`integrity_check=ok`、471条记录及1MiB媒体哈希一致，0.0076秒小样本不作为生产RPO/RTO。
- 首轮稽查补齐根路径symlink在`resolve()`前失败关闭，恢复目标外部目录零写入；整改关联`27 passed`，待独立复测。
- 首轮整改复测`27 passed`；二轮稽查发现恢复权限漂移，现manifest登记mode并在安全提取后应用/复核，`0600`秘密引用动态保持，关联`28 passed`待复测。
- 二轮整改复测`28 passed`；三轮稽查补齐目录mode逆层级恢复，动态保持config `0700`与秘密引用`0600`，待独立复测。
- 冻结提交`090a7f0`三轮整改独立复测`28 passed`无失败无跳过，Python编译通过。
- 最终复稽查确认SQLite一致副本、链接/成员边界、逐文件完整性、原子发布/恢复及文件目录权限完整；BUG065关闭。

### M9.198：架构总纲v2.2事实同步（最终稽查通过，已完成）

- 顶层架构已按截至2026-08-11的实现事实升级为v2.2，明确M1—M7及LangGraph生产内核完成状态，当前主线仍为全链路成片验收；通用Skill机器人和多租户商业化继续标记待交付。
- 新增ProductionLedger、晚到响应隔离、持久`waiting_memory`、`RecordExporter`章节，并固定provider inflight热插拔保护和Stage四处登记CI门禁。
- 架构契约、生产控制面、台账、阶段一致性、可观测性及文档状态关联`92 passed`。
- 独立复测在冻结提交`1aaf7a9`上以显式仓库模块路径执行`112 passed`，无失败无跳过。
- 最终只读稽查确认11阶段、ProductionLedger原子边界、持久资源等待、统一导出和provider inflight保护与代码一致；BUG063关闭。

### M9.198：Stage四处登记CI门禁（最终稽查通过，已完成）

- 新增版本化11阶段登记表，逐项固定启动恢复、LangGraph名称、项目存储投影和前端继续入口；后端恢复器与前端流程模块直接消费并失败关闭不完整登记。
- requirements/audio/subtitle已补入启动恢复映射；关联`109 passed`无失败无跳过，Vue类型检查通过。
- 冻结提交`2522e17`独立复测同一关联`109 passed`，无失败无跳过，Vue类型检查通过。
- 最终稽查确认11阶段顺序/集合、四项登记、启动恢复实际消费和前端真实继续函数门禁完整；BUG064关闭。

### M9.198：builtin能力重复安装与inflight隔离（最终稽查通过，已完成）

- 进程级能力表与模块级安装标记不一致会把重复builtin发现变成provider热替换；并发Qwen人物图因此触发正确的inflight保护却错误终止业务。
- 新增原子`register_once`并用于全部builtin能力安装；重复模块只复用现有provider，真实替换/卸载仍受inflight保护。生产控制面与文档状态`104 passed`。
- 冻结提交`d01c81e`独立复测`104 passed`无失败无跳过，Python编译通过。
- 最终稽查确认原子首次安装不会改变活动handler或inflight，真实热替换/卸载保护保持；BUG039关闭。

### M9.198：完成图片权威回填显示（最终复稽查通过，已完成）

- 复核确认当前`recoverCompletedAssetImages`已承接旧即时响应缺口：baseline和variant completed都从权威job回填媒体URL、转待确认、触发展示并持久化。
- 新增直接执行正式函数的Node动态双路径回归；未修改用户并行前端实现。
- 冻结提交`56dc605`显式Node动态矩阵与文档状态`21 passed`，无失败无跳过。
- 首轮稽查发现同project新session仍会接收旧轮询响应；现绑定发起session并在每次异步返回/持久化前复核，动态证明旧session零写入。
- 冻结提交`2b25217`复测Node/文档`21 passed`无失败无跳过，Vue类型检查通过。
- 最终复稽查确认completed URL回填、失败关闭及project+session晚到隔离完整；BUG040关闭。

### M9.198：对话历史媒体跨项目隔离（最终稽查通过，已完成）

- 历史接口删除“只有一份历史就回退返回”的跨项目兼容分支，只允许tenant/user/project/session精确键读取；缺失与畸形投影统一为空。
- 动态纯函数矩阵、生产控制面和文档状态`106 passed`，旧项目历史保留且未删除正式数据。
- 冻结提交`a11efb9`独立复测`106 passed`无失败无跳过，Python编译通过。
- 最终稽查确认精确四元上下文、缺失/畸形失败为空且旧项目历史保留；BUG041关闭。

M1—M11 全部实现并通过单元、契约、集成、端到端、安全、性能、部署和灾备验收；正式环境可安装、升级、回滚和恢复；文档与真实状态一致；不存在模拟成功、跨层业务污染、跨租户访问或未记录缺口。
- M9.122（历史正面近照口径，已被M9.187/M9.189覆盖）：曾规定脸高40%—50%、目标45%及发顶5%；当前0°半身仅承担腰部裁切近景身份职责，0°正面全身是唯一基准和TripoSR人物输入，全部全身角度执行发顶至少8%、鞋底至少3%的安全区。
- M9.138（历史人物角度链，已被M9.163覆盖）：曾以Klein扩展全身并以RealVisXL/IP-Adapter/OpenPose生成侧背；当前固定角度唯一执行链为Qwen-Edit多参考六格，原比例验收门禁继续保留。
- M9.139（历史未落地候选，已被M9.163覆盖）：Visual Persona/PSHuman三视图未成为当前执行链；当前固定角度唯一执行链为Qwen-Edit多参考六格。
- M9.141（历史文本路由，已被M9.163覆盖）：曾使用9B/27B/122B三档Qwen3.5；当前唯一执行口径为qwen3-vl:32b生成、qwen2.5:72b初审→最多一次修正→终审，并继续共用重任务互斥锁、按需串行加载和完成后卸载。
- M9.142：官方 `stabilityai/TripoSR` 单图转3D模型权重下载至 `models/3d/TripoSR/`；目录、来源、MIT许可证、文件大小与SHA-256固定登记，权重必须通过安全元数据加载后才可接入当前资产3D链；“人物三视图”旧称已被M9.163六格输入口径覆盖。
### M9.148：全链路规范冲突闭环（2026-08-10）

- 全链路规范统一为55—65秒，明确剧本段落与分镜镜头映射、4—8秒视频切片/2帧缓冲、遮挡区间、剧本审核问题段闭环、2D身份量化、镜头版本引用和单集失败人工升级。
- 新增`视频模型选择规则.md`与`题材音画参数模板.md`作为目标验收规范；尚未接线的能力统一标记`pending_development/capability_not_implemented`，禁止冒充已实现。
- AI规范保持14个唯一章节；后端大纲/分集/剧本/单镜/整集分镜入口统一拒绝55—65秒外请求，不再静默夹值。
### M9.166：45°单图3D输入与七角度自动回填（开发完成，待软件测试）

- 该左45°首张与TripoSR输入已被M9.187覆盖；当前首张及人物几何输入为0°正面全身，人物卡六格和Qwen‑Edit逐槽确认继续有效。
- 道具只生成45°三分之二视图，场景只生成45°空场景全景；人工确认后自动启动TripoSR→Blender，禁止2D继续补角度。
- Blender七角度RGB/Mask/Depth/Normal完成后自动回填道具/场景卡片；3D审核图只读，不提供2D导入、重做或修复操作。
### M9.168：资产生成冲突接管与人物卡排序（开发完成，待软件测试）

- 图片按钮遇到同项目assets提取已运行时不再直接失败；前端等待服务端权威阶段完成，合并人物/道具/场景后继续生图，超时才给出中文可恢复提示。
- 人物卡展示顺序固定为0°正面半身、0°正面全身、左45°全身、右45°全身、90°侧面全身、180°背面全身；该M9.168左45° TripoSR输入属于历史口径并已被M9.187覆盖，当前唯一人物几何输入为0°正面全身。
# M9.179：审核导出服务端闭环（2026-08-11）

- `review_export`不再是未安装占位：统一阶段执行器支持`audit/export`两种串行操作，复用现有stage lease、取消事件、local-call checkpoint与能力注册表。
- 成片审核与交付导出的正式前端入口均改走`/api/production/run-stage`；前端只负责准备命令、展示证据与人工确认，不再直连最终审核/导出能力。
- 审核批次要求非空且分集唯一；导出媒体要求非空且分集唯一。启用审核时，所有待导出集必须存在`status=pass && confirmed=true`的审核事实，否则服务端拒绝导出，禁止绕过质量门禁。
- 轻量动态与关联测试21项通过；前端类型检查与生产构建通过，未启动重模型或操作正式任务。
- BUG-20260811-024修复：一次最终审核点击严格只提交一次整批`runStage`；逐集审核与瞬态失败单次重试归服务端，前端不再按分集/attempt循环提交阶段。整批响应受project/session/abort晚到围栏保护，失败证据原样写回且不得进入导出。
# M9.194 联网搜索能力框架接入（最终稽查通过，已完成）

- 对话新增统一 `web.search` 能力注册与搜索意图路由；Brave（配置 Key）优先，DuckDuckGo/Bing/Google 免 Key 多源后备并有限重试。
- 联网回答强制附来源与检索审计信息；所有提供方失败时阻止本地模型无来源作答。
- 已加入公网 URL/协议/响应类型/体积/超时门禁，前端检索状态与结果继续在对话框展示。
- 最终独立复测：真实公网空缓存连续3/3取得LangGraph权威来源；GitHub限流/403逐次留痕并可审计降级。专项147 passed/1 skipped/3 subtests；全unit 543 passed/1 skipped/9 subtests；py_compile、后端compileall、Vue typecheck、Vite 83 modules及文档状态检查通过。
- 用户截图复现根因与整改：旧链只检查“有来源”，缺少模型实体、主题相关性和发布日期门禁。原句真实HTTP现仅返回SenseNova U1、Flux.2 Klein、GLM-Image，按发布日期倒序，无翻译/Tamil/字体/工具/提示库；确定性回答不调用LLM，回答与来源使用同一结果数组。查询保留本地运行、Apple Silicon、日期和商用等附加条件；缓存恢复透传cache_hit、live_attempts、恢复时间，跨查询、过期、损坏及私网来源均失败关闭。
### M9.195：LangGraph拒绝事件持久快照围栏（最终稽查通过，已完成）

- 修复旧projection revision、旧stage generation虽未回退生命周期却覆盖顶层持久`event`的问题；重启恢复和导演决策不再读取被拒绝的旧owner/旧authority信息。
- 新增`accepted_event`和按stage权威事件映射；阶段事件只有通过revision与generation双围栏后才同时发布。已有正代际时，无代际legacy回调同样失败关闭。
- 动态覆盖旧revision、旧generation、无generation、跨stage隔离和SQLite重载；完整单元测试`507 passed, 1 skipped, 9 subtests passed`，未启动重模型或操作正式任务。BUG-20260811-043待独立软件测试。
- LangGraph/生产集成与authority恢复扩大组合冻结复跑`117 passed, 1 skipped`；Python编译、Vue typecheck及83模块生产构建通过。
- 独立软件测试首败：当前双围栏错误地先全局比较`projection_revision`，导致更高`stage_generation`配合新代较小revision被拒绝；动态`generation 4/revision 10 -> generation 5/revision 1`后仍保留旧owner事件。须改为generation优先、revision仅在同generation内单调，再重新测试完整矩阵。
- 退回整改完成：generation现为第一所有权围栏；更高代重置并建立自身revision序列，同代才执行revision单调检查。未来高代、同代旧/缺revision、旧/零代、跨stage、重载和双实例专项`7 passed`；完整单元测试`525 passed, 1 skipped, 9 subtests passed`，编译、类型检查与83模块构建通过。
- 第二轮退回整改完成：正代际按stage accepted-event存在性识别revision序列，因此新代首个0可接管、第二个重复/缺失0严格拒绝、1正常推进；无stage事件的真旧checkpoint允许一次迁移。run-stage成功/失败、确认、协调提交及恢复入口全部显式递增revision。专项`9 passed`、完整unit`543 passed, 1 skipped, 9 subtests passed`，编译/typecheck/83模块构建通过，待独立复测。
- 最新独立软件复测通过：事件围栏、阶段取消、authority原子提交、项目恢复与文档状态关联`132 passed`；完整unit`554 passed, 1 skipped, 9 subtests passed`，Node运行时补充后对应动态文件`23 passed`；关键Python编译、Vue typecheck及83模块生产构建通过。BUG043待只读稽查。
- 最终只读稽查通过：generation优先、同代revision单调、revision0唯一首事件、legacy一次迁移、拒绝事件恢复与正式调用方revision推进均成立；BUG-20260811-043已关闭。
- BUG072第二十六项：平台智能体会话的消息、提案及确认/拒绝全生命周期已绑定创建者identity；异身份即使获得session/proposal UUID也无法读取、注入或执行。专项及平台关联`24 passed`、`3 subtests passed`，只读稽查通过。
- BUG072第二十七项：开发→稽查协作会话及其handoff/report已绑定tenant+创建identity，读取与全部状态推进入口在副作用前统一验权。关联`25 passed`、`3 subtests passed`，只读稽查通过。
