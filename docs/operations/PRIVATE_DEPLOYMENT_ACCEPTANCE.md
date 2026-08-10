# 私有化部署验收

## 安装

复制 `deploy/environments/private-production.env.example` 为 `private-production.env`，通过部署环境注入数据库和密钥引用，执行 `python scripts/deploy/install_private.py`。安装程序完成依赖检查、镜像构建、服务启动和健康检查。

## 监控

采集 JSON 日志、任务与提供方指标和 trace/span；加载 `deploy/alert-rules.yaml`。服务不可用、提供方失败率、队列积压和备份过期必须触发告警。

## 备份恢复

每日备份配置、数据库、资产、审计和 LangGraph 检查点并校验 SHA-256。每月恢复到空目录，验证健康检查、检查点续跑、资产校验和审计哈希链。

## 升级回滚

升级前完成备份与兼容校验，准备新 release 后原子切换。健康检查失败时执行 `release_manager.py ... rollback`，恢复上一版本并记录事件。

## 验收证据

保留安装日志、健康检查、告警触发与恢复、备份清单、恢复演练、升级回滚、容量测试和故障注入测试结果。
