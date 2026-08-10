# AI Agent 全局命名规范

版本：1.1  
生效日期：2026-08-07  
定位：项目全局唯一通用命名标准。

## 一、通用规则

1. 同一概念只使用一个正式名称，优先复用现有词汇，禁止同义别名并存。
2. 名称必须表达业务或技术含义，禁止无意义缩写、拼音、临时编号和测试残留名称。
3. 代码标识符使用英文；用户可见文案和正式中文文档不受此限制。
4. V1.0/V2.0/V3.0 只用于文档、发布和兼容声明；普通文件和函数名禁止携带无必要版本号。

## 二、格式矩阵

| 对象 | 格式 | 示例 |
|---|---|---|
| Python 文件、目录、函数、变量 | `snake_case` | `plugin_registry.py` |
| Python 类、异常、数据模型 | `PascalCase` | `PluginRegistry` |
| TypeScript/JavaScript 文件 | `kebab-case` | `plugin-registry.ts` |
| TypeScript/JavaScript 变量、函数 | `camelCase` | `registerPlugin` |
| TypeScript 类型、接口、枚举类型 | `PascalCase` | `PluginManifest` |
| Vue 组件 | `PascalCase` | `ShotImageCard.vue` |
| Vue Composable | `useXxx` | `usePluginRegistry` |
| Store 文件 | `xxx.store.ts` | `project.store.ts` |
| 常量、枚举值、事件类型 | `UPPER_SNAKE_CASE` | `TASK_COMPLETED` |
| 数据库表、字段、索引 | `snake_case` | `tenant_project` |
| YAML/JSON 字段 | `snake_case` | `operation_key` |
| URL 路径段 | 小写 `kebab-case` | `/api/v1/plugin-runs` |

## 三、契约边界

1. 网络 API、持久化字段和共享契约统一使用 `snake_case`。
2. 前端内部变量使用 `camelCase`，只允许在统一 API Client 边界转换；组件不得私自改名或重新解释字段。
3. 数据库字段、API 字段和共享契约语义必须一致，不得因格式转换改变含义。
4. 写操作统一使用 `operation_key` 和 `request_id`；不得建立第二套同义字段。

## 四、数据库补充

1. 表名和字段名使用模块＋业务语义，禁止复数与单数混用。
2. 历史表使用 `{table_name}_history`。
3. 索引使用 `idx_{table_name}_{field_names}`，唯一索引使用 `uq_{table_name}_{field_names}`。
4. 外键使用 `fk_{source_table}_{target_table}`。
5. 数据库类型、字段长度等实现细则只在 `docs/technical/数据库设计规范.md` 维护。

## 五、插件与版本补充

1. 插件 ID、能力键和 manifest 字段使用 `snake_case`，发布后不可复用或改变语义。
2. V3.0 租户字段统一为 `tenant_id`，不得机械地给所有租户相关表或字段增加 `tenant_` 前缀。
3. 兼容版本采用明确范围字段，不把版本号散写到普通函数和目录。

## 六、禁止项

- 禁止中文代码标识符、拼音、无定义首字母缩写。
- 禁止同类 TS 文件同时使用 `snake_case`、`camelCase` 和 `kebab-case`。
- 禁止 `temp`、`new`、`old`、`final2`、`test_copy` 等临时正式名称。
- 禁止一份契约在前端、后端、插件中分别定义不同字段名。
- 禁止通过重命名绕过兼容、迁移或弃用流程。

## 七、引用关系

- 文件放置路径由 `DIRECTORY_README.md` 唯一定义。
- API 行为、状态码和响应结构由 `docs/contracts/API接口规范.md` 定义。
- 数据库字段类型、索引和迁移规则由 `docs/technical/数据库设计规范.md` 定义。
- 其他文档只引用本规范，不得再次维护通用命名表。

## 八、版本记录

- 1.1（2026-08-07）：统一 TS 文件、Store、URL 与跨端字段边界；删除架构、研发、数据库和 API 文档中的通用命名重复口径。
