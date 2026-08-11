# 灾难恢复

## 恢复优先级

1. 身份、授权与租户边界。
2. 数据库、任务检查点和资产账本。
3. 对象存储与不可变母版。
4. 平台 API、任务执行器和插件。
5. 前端与非关键增强能力。

## 验证

恢复后必须核对数据数量与哈希、租户权限、未完成任务状态、人工确认关口、媒体可播放性、导出完整性和审计连续性。RPO/RTO 在真实基础设施确定前标记为待确认，不得编造指标。

## 单节点V1备份与恢复

正式备份源只允许包含`config`、`database`、`assets`、`audit`和`checkpoints`五个根目录。执行：

```bash
python3 scripts/maintenance/backup_restore.py backup <source> <archive.tar.gz>
python3 scripts/maintenance/backup_restore.py restore <archive.tar.gz> <empty-target> <archive.tar.gz.manifest.json>
```

- SQLite文件通过在线backup API生成一致性副本，WAL/SHM/journal运行边车不进入归档；普通文件复制到隔离快照后再打包。
- 源目录和归档中的符号链接、硬链接、特殊文件、越界路径、重复成员及非白名单根均失败关闭。
- manifest v2记录归档流式SHA-256及每个文件的相对路径、大小和SHA-256；归档和manifest分别以临时文件、`fsync`和原子替换发布。
- 恢复先进入同盘临时目录，完整复核文件集合、大小和哈希后才原子切换到空目标；失败不发布部分恢复目录。

2026-08-12隔离单节点演练：在SQLite WAL持续写入期间备份200条初始记录和1MiB媒体，恢复后`PRAGMA integrity_check=ok`、可查询记录471条、媒体SHA-256一致；备份耗时0.0076秒、manifest只含SQLite主快照与媒体两个文件。该结果只证明本机临时样本的一致性，不是生产RPO/RTO承诺；正式数据规模和部署硬件仍须单独演练。
