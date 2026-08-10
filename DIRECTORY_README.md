# AI Agent 项目目录规范

版本：1.3  
生效日期：2026-08-07  
定位：项目全局唯一目录归属与分层标准。

## 一、核心规则

1. 每个文件只有一个职责和一个正式归属，禁止同类实现散落多处。
2. `.kernel/` 为只读内核；`platform/` 为无业务通用底座；业务能力只进入 `plugins/`。
3. 运行数据只进入 `data/`，模型权重只进入 `models/`，禁止写入源码目录。
4. 前后端及插件共享的数据结构只进入 `shared/contracts/`。
5. 新增或调整一级、二级目录必须先形成架构决策记录，不得由业务任务临时创建。

## 二、根目录唯一职责

| 路径 | 唯一职责 |
|---|---|
| `.kernel/` | 平台内核，只读；业务与插件禁止修改 |
| `platform/` | 启动、配置、安全、租户、事件、队列、模型网关及外部系统适配 |
| `plugins/` | 全部可插拔业务能力，禁止业务逻辑进入底座 |
| `frontend/` | Vue 前端页面、组件、UI Store、样式与插件插槽 |
| `shared/contracts/` | 跨层数据结构、事件、枚举和接口契约的唯一可信源 |
| `deploy/` | 镜像、部署编排与环境模板 |
| `docs/` | 产品、技术、契约、安全、运维和开发文档 |
| `tests/` | 单元、集成、端到端、安全及插件夹具 |
| `scripts/` | 部署、迁移、维护、授权和安全运维脚本 |
| `data/` | 运行时数据、缓存、日志、检查点及临时文件 |
| `models/` | 模型注册表、模型元数据与外置权重索引 |
| `tools/` | 非业务调试和诊断工具 |

## 三、平台目录

| 路径 | 唯一职责 |
|---|---|
| `platform/bootstrap/` | 启动编排、阶段初始化与健康检查 |
| `platform/core/` | 核心配置、生命周期、异常和平台入口 |
| `platform/adapters/` | LangGraph、Dify、ComfyUI 等外部系统适配 |
| `platform/llm_gateway/` | 模型注册、路由与 Token 优化 |
| `platform/security/` | 加密、密钥、输入净化与授权校验 |
| `platform/tenant/` | 身份和租户隔离能力 |
| `platform/events/` | 跨模块事件总线和事件类型 |
| `platform/queue/` | 异步任务定义与队列接入 |
| `platform/common/` | 无业务通用常量、类型、校验、时间和加密工具 |
| `platform/discovery/` | 插件发现与加载 |
| `platform/circuit_breaker/` | 熔断、降级与故障隔离 |

## 四、前端目录

| 路径 | 唯一职责 |
|---|---|
| `frontend/src/views/` | 页面级视图 |
| `frontend/src/components/base/` | 无业务基础组件 |
| `frontend/src/components/business/` | 仅通过 Props/事件工作的业务展示组件 |
| `frontend/src/components/task/` | 任务展示组件 |
| `frontend/src/plugin-slots/` | 插件 UI 插槽、类型和注册表 |
| `frontend/src/styles/` | 设计变量、全局样式和布局样式 |
| `frontend/src/store.ts` | 仅 UI 偏好与布局状态；业务状态不得进入 |
| `frontend/src/services/` | 平台级 HTTP 客户端与统一传输边界；行业服务不得进入 |
| `frontend/src/stores/` | 平台级服务状态；行业业务状态只进入对应插件 |
| `frontend/public/` | favicon、字体和无需编译的静态资源 |

## 五、插件目录

1. 固定结构为 `plugins/{builtin|custom}/{plugin_name}/`。
2. 官方插件进入 `plugins/builtin/`；客户私有插件进入 `plugins/custom/{customer_name}/`。
3. 单插件包含 manifest、后端能力、Skill、前端插槽、工作流和自有资源；实际子目录以插件契约为准。
4. 插件仅能访问自身目录和已授权公共契约，禁止跨插件直接导入。
5. 行业属性、兼容版本和权限写入 manifest，禁止用另一套根目录表达行业分类。

## 六、归属判定顺序

1. 跨层契约、事件、枚举 → `shared/contracts/`。
2. 平台通用能力 → `platform/` 对应职责目录。
3. 业务能力 → `plugins/{builtin|custom}/` 对应插件。
4. 页面和组件 → `frontend/src/views/` 或 `frontend/src/components/`。
5. 插件 UI 扩展 → `frontend/src/plugin-slots/` 与插件自身前端入口。
6. 部署、迁移和运维动作 → `deploy/` 或 `scripts/`。
7. 动态数据、缓存、日志和输出 → `data/`。
8. 无法唯一归属时停止创建，先更新本规范或新增架构决策。

## 七、引用关系

- 命名格式以根目录 `AI_EXECUTION_NAMING_RULES.md` 为唯一来源。
- 插件原理以 `docs/technical/系统架构设计.md` 为准；执行细则以 `docs/technical/研发工程统一规范文档.md` 为准。
- V1.0/V2.0/V3.0 能力边界以 `docs/product/产品迭代规划.md` 为唯一来源。

## 八、版本记录

- 1.3（2026-08-10）：登记 `models/3d/` 为三维重建与几何生成模型权重唯一目录。
- 1.2（2026-08-07）：登记平台级前端服务与状态目录，任务追踪状态与短剧业务状态保持分离。
- 1.1（2026-08-07）：统一实际四层架构目录；前端统一为 `frontend/`；底座统一为 `platform/`；插件统一为 `plugins/{builtin|custom}/{plugin_name}`；删除其他文档中的重复目录表。
