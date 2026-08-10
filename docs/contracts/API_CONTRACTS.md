# API 契约清单

版本：1.2  
状态：运行、智能体、任务、模型、配置和对话路径已验证

## 当前事实

- 平台进程已验证 `GET /health`。
- 智能体已验证 `POST /api/v1/agents/register` 与 `GET /api/v1/agents/{agent_id}`。
- 任务已验证列表、详情、取消和恢复路径；身份与租户请求头、统一响应壳及错误壳已进入 `openapi.yaml`。
- 模型已验证注册和查询路径；智能体配置已验证创建、更新、指定版本和历史路径。
- 配置对话已验证会话、消息、结构化提案、确认与拒绝路径；未注入真实模型客户端时返回明确失败。
- 旧 Drama Pipeline API 不直接复制；每个接口必须按新身份、租户、会话、幂等和任务契约重新登记。
- 身份、租户、项目、任务、插件、资产、错误和事件的 V1 跨层类型已冻结在
  `shared/contracts/domain.contract.ts`；这只代表契约基线，不代表对应服务或接口已实现。

## V1 共享契约基线

| 契约 | 核心身份/范围字段 | 状态枚举 |
|---|---|---|
| IdentityContract | identity_id, identity_kind | is_active |
| AuthorizationContract | identity_id, tenant_id, scope_kind, scope_id, action | allowed, denied；拒绝时必须携带封闭 denial_reason |
| TenantContract | tenant_id | inactive, active, suspended |
| ProjectContract | project_id, tenant_id, owner_identity_id | draft, active, archived |
| TaskContract | task_id, tenant_id, project_id, operation_key | queued, running, waiting_human, paused, completed, failed, cancelled |
| PluginContract | plugin_id, source, version | discovered, enabled, disabled, failed |
| AssetContract | asset_id, tenant_id, project_id, task_id | pending, available, invalidated, failed |
| ErrorContract | data.request_id, data.error_code | HTTP 规范状态码 |
| EventContract | event_id, trace_id, tenant_id, project_id, actor_identity_id | PROJECT_CREATED, TASK_STATUS_CHANGED, PLUGIN_STATUS_CHANGED, ASSET_STATUS_CHANGED |

所有契约携带 `contract_version: "1.0"`（统一响应壳除外）。V1/V2 使用稳定默认
租户范围，V3 才启用 SaaS 多租户能力；契约预留不代表提前启用 V3 功能。

任务状态只能使用 `TaskStateTransition` 的封闭转换集合。写操作以 `operation_key` 和请求
指纹区分首次接受、相同请求重放与同键冲突。人工关口处于 `pending` 时禁止携带决策人
或决策时间；只有显式 `approved`/`rejected` 后才能恢复后续调度。

插件清单以 `PluginManifestContract` 冻结版本范围、能力、显式权限、三类依赖、数据
作用域、前后端入口、卸载策略和完整性哈希。插件默认无权限，生命周期不得跳过清单
校验或安装阶段；卸载态不可恢复。

资产使用不可变 `AssetVersionContract` 保存父版本、来源任务、内容哈希及模型/Prompt/依赖
溯源。失效必须限定最小作用域、列出受影响版本并固定保留历史。导出只引用明确资产版本，
携带幂等键、状态、输出存储键和完成后的内容哈希。

公共错误码封闭为参数、认证、权限、资源、冲突、超时、依赖不可用和内部错误八类。
事件信封统一携带 request_id、trace_id、身份及项目/租户范围；四类事件必须使用与
event_type 匹配的封闭载荷，禁止任意对象或跨事件字段混用。

## 接口登记字段

每个接口必须记录：operation_id、方法、路径、版本、权限、身份范围、请求 schema、响应 schema、错误码、幂等规则、超时、取消、所有者、实现状态和测试证据。

## 状态定义

- `draft`：仅设计，禁止客户端依赖。
- `implemented`：代码存在，尚未完成真实验证。
- `verified`：契约测试和真实链路通过，可由客户端使用。
- `deprecated`：进入弃用期，保留替代路径和截止日期。

只有 `verified` 接口可进入正式插件契约。
