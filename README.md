# AI Agent

可插拔 AI 应用平台，同一底座支持本地、私有化和 SaaS 演进。平台提供身份、权限、配置、任务、事件、模型与插件治理；短剧、开发 AI、稽查 AI 等能力通过内置或自定义 Skill/插件接入。

## 当前状态

- M1：Skill 注册、独立智能体、生命周期、上下文隔离与串联调度已完成。
- M2：短剧 11 节点持久流程、人工关口、失败/取消/恢复与真实提供方入口已完成。
- M3：任务查询、详情、取消、恢复、实时进度与前端任务中心已完成。
- M4：开发/稽查 Skill、模型选择和对话配置正在开发。
- 原 Drama Pipeline 前端已迁入 `plugins/builtin/short_drama/frontend/`，平台入口通过插件插槽加载。

## 文档唯一来源

| 内容 | 唯一文件 |
|---|---|
| AI 行为与身份 | `AGENTS.md` |
| 连续开发任务 | `Dev_MainDev.md` |
| BUG 提交与修复闭环 | `Dev_BUG_TRACKER.md` |
| 稽查规则 | `Dev_INSPECTION_SPEC.md` |
| 软件测试规则 | `Dev_TESTING_SPEC.md` |
| 命名规则 | `AI_EXECUTION_NAMING_RULES.md` |
| 目录归属 | `DIRECTORY_README.md` |
| 长期愿景 | `docs/product/VISION.md` |
| 产品决定 | `docs/product/PRODUCT_DECISIONS.md` |
| 版本能力 | `docs/product/产品迭代规划.md` |
| 当前里程碑 | `docs/product/项目进度.md` |
| 当前状态与下一步 | `docs/memory/项目记忆.md` |
| API 契约 | `docs/contracts/` |
| 系统架构 | `docs/technical/系统架构设计.md` |

## 工程入口

- Python：`python -m pip install -e .`
- 平台 API：`ai-agent-api`
- 前端：进入 `frontend/` 后执行 `pnpm install && pnpm dev`
- 前端地址：`http://127.0.0.1:5173/`
- 健康检查：`http://127.0.0.1:8000/health`

## 目录

- `platform/`：通用底座。
- `plugins/`：业务插件和系统 Skill。
- `shared/contracts/`：跨层契约。
- `frontend/`：平台前端入口和公共插槽。
- `tests/`：单元、契约、集成、端到端和安全测试。
- `docs/`：产品、契约、技术、安全与运维文档。

## 交付边界

- 未注入真实模型或媒体提供方时明确失败，不使用演示结果冒充成功。
- 稽查 Skill 永久只读，不因模型或对话配置获得写权限。
- 生产部署、备份恢复、灾难恢复和插件进程沙箱仍需完成真实环境验收。
