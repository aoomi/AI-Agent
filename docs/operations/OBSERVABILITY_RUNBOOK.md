# 可观测性运行手册

## 必须观测

- API 请求率、延迟、错误率和关联 ID。
- 队列深度、任务年龄、超时、取消、重试和死信。
- 模型调用时延、失败率、Token/积分和供应商状态。
- 数据库连接、慢查询、对象存储错误和容量。
- 插件加载、熔断、降级及权限拒绝。
- 租户级异常与安全审计事件。

## 告警处理

告警必须指向可执行 Runbook，包含影响范围和关联 ID；先保护租户隔离和数据完整性，再恢复吞吐。任何手工改状态操作必须留审计记录。

## V1 导出边界

- 平台统一通过`RecordExporter.export(kind, record)`插槽发布`log`、`metrics_snapshot`、`span`和`alert`；默认空导出器不改变旧调用行为，生产配置可组合多个导出器。
- 本地私有化最小配置使用`JsonLinesExporter(data/logs/observability.jsonl)`保存关联证据，使用`PrometheusSnapshotExporter(data/metrics/ai_agent.prom)`原子发布最新指标快照。运行数据不得写入源码目录。
- JSONL每条记录完成flush和fsync后才返回；Prometheus textfile通过同目录临时文件及原子替换发布，抓取方不会读取半写文件。多主机部署必须替换为集中式exporter，不能共享追加同一个本地文件。
- 指标标签在注册表内排序规范化，counter只能增加；禁止tenant、project、request、trace、task等无界ID作为Prometheus标签，关联ID进入日志、span和告警证据。
- `request_id`和`trace_id`是结构化日志、span、指标导出批次和告警的标准关联字段。当前V1底座允许调用方传入；API→LangGraph→任务→provider→worker→ledger→manifest的强制贯穿仍须按剩余框架清单逐入口验收。

## 最小告警演练

1. 在隔离测试注册`queue_oldest_seconds{pool="accelerator"}`并设为超过规则阈值。
2. 导出结构化指标快照，执行`AlertEvaluator`；期望恰好一条`alert`记录，并包含规则名、当前值、阈值、request_id和trace_id。
3. 将值降到阈值以下再次求值；期望零告警。不得通过直接修改生产任务或台账制造告警。
4. 从告警关联ID检索JSONL中的请求日志和span，确认能够定位失败范围；若关联链任一环缺失，登记为全链追踪缺陷，不能手工补字段伪造闭环。

首批规则建议覆盖队列最老年龄、worker心跳、租约丢失、provider失败、台账提交失败和磁盘余量。具体阈值必须由单节点基准与生产容量确定并写回NFR，未实测前不承诺固定数值。
