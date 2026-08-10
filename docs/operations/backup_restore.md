# 备份与恢复

## 备份范围

- 数据库与迁移版本。
- 对象存储中的源素材、母版、增强版和导出文件。
- 任务检查点、项目资产账本和审核证据。
- 插件清单、版本、配置与授权信息。

## 强制流程

1. 生成带租户、项目、时间和版本的备份清单。
2. 计算数据库转储和媒体对象校验和。
3. 将备份写入与主存储故障域不同的位置。
4. 在隔离环境恢复，并核对数量、校验和、权限和可播放性。
5. 保存恢复耗时、缺失项和验证证据。

当前自动化脚本尚未实现；未完成真实恢复演练不得标记备份有效。
# 备份与恢复

正式备份覆盖 `config`、`database`、`assets`、`audit` 和 `checkpoints`，归档同时生成 SHA-256 清单。

```bash
python scripts/maintenance/backup_restore.py backup /var/lib/ai-agent /srv/backups/ai-agent.tar.gz
python scripts/maintenance/backup_restore.py restore /srv/backups/ai-agent.tar.gz /var/lib/ai-agent-restored /srv/backups/ai-agent.tar.gz.manifest.json
```

恢复目标必须为空；校验和不一致或归档路径越界时强制终止。恢复完成后执行健康检查、任务检查点恢复和审计链验证。
