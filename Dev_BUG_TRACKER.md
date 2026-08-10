# BUG 跟踪记录

本文件只用于提交、处理和关闭项目 BUG，不用于存放开发规范、需求或功能计划。

## 状态流转

`待处理` → `修复中` → `待测试` → `待稽查` → `已关闭`

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

- 状态：待处理
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

- 状态：已修复，待软件测试复核
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

- 状态：主线已整改，待软件测试复测
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

- 状态：待处理
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
