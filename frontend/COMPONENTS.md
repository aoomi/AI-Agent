# 前端组件台账

版本：2.0  
日期：2026-08-07

## 平台入口

- `src/App.vue`：装配平台任务中心、插件运行时和 Canvas 插槽。
- `src/main.ts`：启动 Vue 并加载短剧插件样式。
- `src/services/task-service.ts`：访问任务服务。
- `src/stores/task.store.ts`：管理真实任务状态。
- `src/components/task/TaskCenter.vue`：任务列表、详情、取消和恢复入口。

## 插件插槽

`src/plugin-slots/` 提供 Toolbar、Sidebar、Canvas、Navigation 和 Settings 插槽及统一注册表。

## 短剧插件界面

原版短剧工作台、组件、状态、服务和视觉资源统一位于 `plugins/builtin/short_drama/frontend/`，由 `register.ts` 注册到平台 Canvas 插槽。

平台前端不保留短剧组件副本；业务状态来自服务端和插件服务适配，页面不得伪造成功状态。
