# 插件契约

版本：1.0  
状态：设计基线

## Manifest 必填字段

插件必须声明：plugin_id、name、version、platform_version_range、provider、capabilities、permissions、dependencies、data_scopes、frontend_slots、entrypoints、migration、uninstall_policy 和 integrity_hash。

## 依赖类型

1. `required`：缺失时插件拒绝启动。
2. `replaceable_input`：可通过标准素材或其他能力提供同等输入。
3. `optional_enhancement`：缺失时降级，不得跳过主流程或伪造成功。

## 生命周期

`discovered → validated → installed → enabled → disabled → uninstalled`。安装、升级、禁用和卸载必须幂等、可审计、可回滚。

## 权限与数据

- 默认无权限；文件、网络、模型、队列、密钥和租户数据均需显式声明。
- 插件只能访问授权项目和范围，禁止跨插件直接读取。
- 卸载必须声明数据保留、导出和删除行为，禁止静默销毁用户资产。

## 前端扩展

插件只能挂载已登记插槽，Props 和事件来自共享契约；禁止覆盖核心 UI、注入全局样式或直接调用底座内部实现。

后端与前端扩展 Schema 基线位于 `docs/contracts/`。运行时校验器和有效/无效夹具测试通过前，不得标记插件加载器已完成。
