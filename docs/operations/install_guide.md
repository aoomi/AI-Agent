# 安装指南

## 当前可安装范围

- Python 3.11 及以上。
- 根目录执行 `python -m pip install -e '.[test]'`。
- 平台启动命令：`ai-agent-api`。
- 默认健康检查：`GET http://127.0.0.1:8080/health`。
- 前端在 `frontend/` 执行 `pnpm install`、`pnpm typecheck`、`pnpm build` 和 `pnpm dev`。

## 当前交付状态

本地开发入口已验证；生产镜像、离线安装包、数据库、对象存储、密钥系统、升级回滚和灾备自动化尚未验收，不得描述为可生产部署。
