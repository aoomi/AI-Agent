# ADR-0004：平台级前端服务与状态边界

状态：已接受  
日期：2026-08-07

## 决策

平台级 HTTP 客户端进入 `frontend/src/services/`，平台级服务状态进入 `frontend/src/stores/`。根目录 `frontend/src/store.ts` 继续只管理 UI 偏好；短剧等行业业务状态继续只进入对应插件，不得迁入平台级 Store。

## 结果

任务中心可复用平台任务契约和身份请求头，插件业务状态仍与通用视图层隔离。
