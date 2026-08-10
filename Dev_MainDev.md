# AI 开发任务规划

版本：2.2  
生效日期：2026-08-07  
适用对象：主线开发 AI

### M9.169：统一任务权威提交与JSON投影崩溃一致性（失租围栏整改完成，待软件测试复测）

- text/image/video任务保存顺序统一为：先提交可插拔统一任务仓库，再写兼容JSON投影。禁止JSON先成功、SQLite后失败造成重启时终态倒退。
- JSON投影失败时权威任务仍可从SQLite读取并覆盖旧投影；权威提交失败时禁止修改JSON，避免兼容文件冒充已提交事实。
- 三类保存函数共用同一顺序契约；故障注入覆盖投影失败、权威失败与重启合并读取。
- 多任务使用单个SQLite事务批量提交；同时写入持久投影outbox。LangGraph异常不再抛回业务层或反写任务failed，后台心跳与服务重启会重放outbox，成功后才确认删除。
- outbox事件使用SQLite全局单调revision；确认删除必须匹配job_id+revision。LangGraph按stage保存最新投影revision并拒绝旧版本，保证并发drain不会误删新事件或用旧queued覆盖新completed。
- 多服务实例投影前必须取得SQLite中的tenant/user/project/stage级租约；租约自动续期、进程失联后过期。持锁后重新读取最新outbox，跨实例禁止同时写同一阶段checkpoint。
- 续租失败、租约被接管或数据库异常必须立即标记`lost`；Graph提交前后及ack前均复核所有权。提交途中失租时，从SQLite权威任务重新生成更高revision事件，禁止旧持有者确认新事件，并由后续投影自动修复可能的旧checkpoint。
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

- 六格能力继续保留；当前顺序改为左45°全身基准、0°正面、右45°、90°、180°、0°半身。
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
- 历史0°/`front_full`人物3D输入已废止；当前M9.166固定使用已确认左45°全身与`reference_angle=left_45_full`。
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

## 一、自动执行规则

### M9.144：大纲生产任务可靠性与性能闭环（历史模型口径，已被M9.163覆盖）

- 大纲总纲和分集批次统一登记服务端唯一任务ID、真实工作线程、阶段、心跳和1800秒硬超时。
- 当时的27B推理登记唯一owner job_id；当前qwen3-vl:32b生成继续沿用同一owner隔离，停止或超时仅终止目标owner。
- 大纲停止按项目ID与客户端生成批次精确终止；服务重启和关闭统一回收大纲、剧本非终态，禁止残留generating。
- 历史27B Q8复用与122B审核模型口径已废止；当前按M9.163固定为qwen3-vl:32b生成、qwen2.5:72b初审→最多一次修正→终审，串行加载并在完成后卸载。
- 前端大纲结果整段即时展示，项目切换和页面中断立即持久化失败并定向停止后端任务。

1. 严格按 M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M9 → M10 → M11 和任务编号顺序连续执行，不重复确认。
2. 每项完成后立即执行相关测试、同步 `docs/product/项目进度.md` 与 `docs/memory/项目记忆.md`，随后自动进入下一项。
3. 单项完成、阶段切换、阶段性汇报和外部稽查均不构成停止条件。
4. 仅用户明确说“停下”、全部任务完成或出现无法自行消除的真实阻塞时停止。
5. 软件测试与外部稽查独立进行；问题统一登记到 `Dev_BUG_TRACKER.md`，固定按“主力开发 → 软件测试 → 代码稽查”流转，任一失败均按原 BUG 编号退回主力开发，稽查关闭后返回原任务。
6. 所有实现遵守 `DIRECTORY_README.md`；不得创建 `server/`、`platform/registry/` 或其他未登记目录。
7. 平台通用能力进入 `platform/`，短剧业务只进入 `plugins/builtin/short_drama/`，跨层结构只进入 `shared/contracts/`。
8. 每项必须同时具备实现、正常场景测试、直接异常测试和文档同步才算完成。

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
- M9.128：人物正面全身、严格90°侧面、严格180°背面统一强制发顶上方约5%画高、完整鞋底下方约5%画高安全边距；生成提示词、视觉验收字段和正式图片规范同步执行。
- M9.129：道具基准图新增单一独立道具、纯中性背景、无场景环境、无文字招牌、无真人人体五项硬验收；道具禁止加载人物风格 LoRA，商店、街道、房间和建筑等场景图无法再以道具图放行。
- M9.130：项目图片预览已统一为 Codex 式底部悬浮缩放条，支持适窗实际百分比、加减缩放、滚轮缩放、拖拽平移、双击/百分比复位和键盘快捷键；人物固定角度图生成后先执行确定性前景归一化，强制发顶与鞋底各约5%安全边距，再执行身份、方向、服装、体型和尺寸验收。
- M9.131：人物固定角度一致性门禁已纠正错误放行：正面全身独立核对脸型年龄、刘海分缝、扎发/辫子、发长发色、领口扣饰、服装主色和装饰复杂度；旧全身服装引用在重生时清除，缺失引用强制回退到已确认基准图。当前错误候选已作废，新候选因身份、发型、服装不一致被正确拦截，未进入人工确认。
- M9.132：“就要这张”确认链路已解除生产台账同步等待，确认后立即切换生成状态并异步登记台账；人物基准确认时强制重置失效服装引用为当前基准图，后端缺失引用同步回退。真实页面验证按钮点击后立即消失、显示生成中和暂停，并创建全身角度任务。
- M9.125：全网及 GitHub 扩展检索后下载14个 FLUX.1 仅测试候选，严格归入国风浅涂或国风厚涂：风格5、女性3、男性3、灵兽3；许可、来源、大小、SHA-256、Safetensors 与 FLUX 权重键登记到独立测试索引，正式模型索引和商用索引继续保持为空，未实图验收前禁止进入生产。
- 所有缺陷提交、修复证据和复核结论统一记录于 `Dev_BUG_TRACKER.md`。

## 十五、最终完成标准

M1—M11 全部实现并通过单元、契约、集成、端到端、安全、性能、部署和灾备验收；正式环境可安装、升级、回滚和恢复；文档与真实状态一致；不存在模拟成功、跨层业务污染、跨租户访问或未记录缺口。
- M9.122：人物正面近照唯一标准构图固定为928×1664、脸高占画40%—50%（自动目标45%）、完整头发与双耳入框、发顶保留5%安全边距、左右各保留2%安全边距、肩胸完整、InsightFace偏航/翻滚≤7°；后端已强制执行单脸、发顶与发宽检测及规范化裁切。
- M9.138（历史人物角度链，已被M9.163覆盖）：曾以Klein扩展全身并以RealVisXL/IP-Adapter/OpenPose生成侧背；当前固定角度唯一执行链为Qwen-Edit多参考六格，原比例验收门禁继续保留。
- M9.139（历史未落地候选，已被M9.163覆盖）：Visual Persona/PSHuman三视图未成为当前执行链；当前固定角度唯一执行链为Qwen-Edit多参考六格。
- M9.141（历史文本路由，已被M9.163覆盖）：曾使用9B/27B/122B三档Qwen3.5；当前唯一执行口径为qwen3-vl:32b生成、qwen2.5:72b初审→最多一次修正→终审，并继续共用重任务互斥锁、按需串行加载和完成后卸载。
- M9.142：官方 `stabilityai/TripoSR` 单图转3D模型权重下载至 `models/3d/TripoSR/`；目录、来源、MIT许可证、文件大小与SHA-256固定登记，权重必须通过安全元数据加载后才可接入当前资产3D链；“人物三视图”旧称已被M9.163六格输入口径覆盖。
### M9.148：全链路规范冲突闭环（2026-08-10）

- 全链路规范统一为55—65秒，明确剧本段落与分镜镜头映射、4—8秒视频切片/2帧缓冲、遮挡区间、剧本审核问题段闭环、2D身份量化、镜头版本引用和单集失败人工升级。
- 新增`视频模型选择规则.md`与`题材音画参数模板.md`作为目标验收规范；尚未接线的能力统一标记`pending_development/capability_not_implemented`，禁止冒充已实现。
- AI规范保持14个唯一章节；后端大纲/分集/剧本/单镜/整集分镜入口统一拒绝55—65秒外请求，不再静默夹值。
### M9.166：45°单图3D输入与七角度自动回填（开发完成，待软件测试）

- 人物首张改为左45°全身并作为TripoSR唯一人物几何输入；人物卡保持六格，其余五格继续由Qwen‑Edit逐槽生成确认。
- 道具只生成45°三分之二视图，场景只生成45°空场景全景；人工确认后自动启动TripoSR→Blender，禁止2D继续补角度。
- Blender七角度RGB/Mask/Depth/Normal完成后自动回填道具/场景卡片；3D审核图只读，不提供2D导入、重做或修复操作。
### M9.168：资产生成冲突接管与人物卡排序（开发完成，待软件测试）

- 图片按钮遇到同项目assets提取已运行时不再直接失败；前端等待服务端权威阶段完成，合并人物/道具/场景后继续生图，超时才给出中文可恢复提示。
- 人物卡展示顺序固定为0°正面半身、0°正面全身、左45°全身、右45°全身、90°侧面全身、180°背面全身；左45°仍是TripoSR唯一人物几何输入，显示顺序不改变生成职责。
