# 人物全身与多视图远程 CUDA 服务契约

## 固定职责

- 本机：FLUX.1 Schnell 正面近照、人工确认、任务持久化、尺寸/身份/比例/边距验收和主动局部修复。
- Visual Persona 服务：读取已确认近照与预置 7.5 头身 OpenPose，只生成正面全身候选。
- PSHuman 服务：只读取已人工确认正面全身图，重建共享人体并渲染 90°侧面与 180°背面。
- 未确认正面全身图时禁止调用 PSHuman。任何服务均不得自动加载项目 LoRA 或 Qwen。

## 环境变量

```text
SHORT_DRAMA_VISUAL_PERSONA_API_URL=https://gpu.example/v1/visual-persona/generate
SHORT_DRAMA_VISUAL_PERSONA_API_TOKEN=secret
SHORT_DRAMA_VISUAL_PERSONA_LICENSE_APPROVED=true
SHORT_DRAMA_PSHUMAN_API_URL=https://gpu.example/v1/pshuman/render
SHORT_DRAMA_PSHUMAN_API_TOKEN=secret
SHORT_DRAMA_PSHUMAN_LICENSE_APPROVED=true
```

许可证批准变量必须由部署方在完成代码、模型权重、数据集衍生权利及依赖模型审查后设置；代码仓库公开不等于权重可商用。

## Visual Persona 请求与响应

请求为 JSON，必须接收：`mode=pose_guided_full_body`、`model`、`width`、`height`、`reference_image_base64`、`pose_image_base64`、`prompt`、`character_gender`、`requirements`。

服务必须输出严格 928×1664 PNG/JPEG，并返回以下任一字段：

```json
{"image_base64":"...","model_version":"..."}
```

或：

```json
{"image_url":"https://...","model_version":"..."}
```

## PSHuman 请求与响应

请求为 JSON，必须接收：`mode=reconstruct_and_render`、`model`、`azimuth_degrees`、`elevation_degrees`、`identity_image_base64`、`full_body_image_base64`、`width`、`height`、`background`、`requirements`。

侧面固定 `azimuth_degrees=90`，背面固定 `azimuth_degrees=180`。同一正面全身引用必须复用同一人体网格及纹理缓存。响应格式与 Visual Persona 相同。

## 失败规则

- 未批准许可证：立即失败，不发起网络请求。
- 未配置 URL：立即失败，不回退到 FLUX 扩图或独立 SDXL 抽卡。
- HTTP、超时、无效 Base64、非 PNG/JPEG：任务失败并允许用户重试。
- 正面全身未通过 7.0—7.8 头身、0°正面、完整头脚、鞋底5%和身份门禁：不得进入人工确认。
- PSHuman结果未通过90°/180°、服装纹理、发型、体型和尺寸门禁：不得显示为已完成。
