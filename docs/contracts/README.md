# 契约目录说明

`docs/contracts/` 保存跨系统可验证的正式契约及其说明。

| 文件 | 职责 |
|---|---|
| `API接口规范.md` | API 设计、安全、错误和兼容规则 |
| `API_CONTRACTS.md` | 当前契约清单、状态和负责人 |
| `openapi.yaml` | HTTP API 的机器可读契约 |
| `license_schema_v1.json` | 授权文件 JSON Schema 基线 |
| `plugin_backend.schema.yaml` | 插件后端扩展 Schema 基线 |
| `plugin_frontend.schema.json` | 插件前端扩展 Schema 基线 |

跨层领域契约的唯一源文件为 `shared/contracts/domain.contract.ts`，配套运行时校验文件为
`shared/contracts/domain.schema.json`。两者使用同一 `contract_version: "1.0"`，变更必须
同时通过 TypeScript 编译型契约测试与 JSON Schema 夹具测试。

Schema 已补齐基础字段定义；尚未接入运行时验证器和有效/无效夹具测试，不能据此标记加载器完成。
