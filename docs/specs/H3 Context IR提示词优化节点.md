# MiniMax H3 Context IR提示词优化节点规范

版本：1.1｜生效日期：2026-08-11｜状态：已接入短剧Ref2VA生产链

## 1. 定位与边界

- 安装项目：`JerryZRic/comfyui-minimax-h3-context-ir-agent`，固定提交`771cb3cb01af9543b4f424518bb19b7fa0cf31d8`，MIT许可。
- 本节点是H3提示词翻译/结构化预处理器，不生成视频，不是MiniMax云端官方Context-IR端点，也不替代MiniMax H3模型。
- Ref2VA提供方的设备/量化算子兼容门禁必须先于本节点执行；若固定`INT8 ConvRot`制品所在节点仅提供MPS或CPU，任务直接进入`model_blocked`，不得先加载32B Context IR，也不得让量化算子静默回退CPU。
- 两个已加载节点：`MiniMaxH3FL2VAPromptAgentOpenAIAPI`支持T2VA/I2VA/L2VA/FL2VA；`MiniMaxH3Ref2VAPromptAgentOpenAIAPI`支持最多9张参考图的Ref2VA。
- 输出固定为`optimized_prompt、selected_skills、raw_json`；`optimized_prompt`接入官方H3 conditioning/video节点的prompt输入。
- 主`h3-prompt-writing`材料既内联到Agent instructions，也以同名只读工具注册；工具只返回供应链固定目录中已加载的Skill正文与当前mode guide，不访问网络、不接受路径参数。这样本地模型显式选择主Skill时与Agents SDK工具表一致，不能因“tool not found”跳过Context IR或回退原提示词。

## 2. 本地安装与配置

- 节点目录：`/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/custom_nodes/comfyui-minimax-h3-context-ir-agent`
- ComfyUI Python：`/Users/aoo/AI/Tools/ComfyUI/main/ComfyUI/.venv/bin/python3`
- 依赖固定为`openai-agents 0.19.4、openai 2.53.0、Pillow 12.3.0、numpy 2.4.6`；全部42项直接/传递依赖及下载哈希以`deploy/comfyui/h3-context-ir-requirements.lock`为唯一安装清单，禁止直接执行上游浮动`requirements.txt`。
- 本地OpenAI兼容端点：`http://127.0.0.1:11434/v1`；模型：`qwen3-vl-h3-context-ir:latest`，源自官方非思考权重`qwen3-vl:32b-instruct`，固定16K上下文、2048输出、temperature 0.2及`qwen3-vl-instruct` renderer/parser。Thinking权重实测会把全部输出预算耗在thinking并返回空正文，禁止用于本节点。
- 配置文件位于节点目录的忽略文件`config.toml`，不写入工作流JSON；本地Ollama使用非敏感占位Key。切换官方OpenAI时必须单独配置真实Key，禁止写入仓库、日志或工作流。
- ComfyUI由LaunchAgent `com.aiagent.comfyui8194`持续运行；启动脚本固定白名单加载本节点，禁用Manager UI和其他未批准节点。
- 可复现安装入口为`scripts/install_h3_context_ir_agent.sh`：固定Git提交、校验MIT许可与上游requirements哈希、使用`--require-hashes`同步依赖、校验32B源blob后重建专用模型。供应链台账为`deploy/comfyui/h3-context-ir-supply-chain.json`。
- 上游节点无条件发送`reasoning_effort`，非思考Instruct模型会拒绝该参数；本地兼容补丁`deploy/comfyui/h3-context-ir-local-instruct.patch`仅对固定专用模型省略reasoning参数，补丁SHA-256为`499703d22b4d5598ca543e8634cd6f08472cc45839899c33662eecec48d5de55`。安装脚本只接受固定上游提交加该唯一补丁，任何其他工作树变化均阻断。
- `qwen3-vl-h3-context-ir.Modelfile`不得使用浮动模型标签，固定引用32B Instruct源blob `sha256-4c7fee11ee9e3b139575eedb4cd68521729ece7fc0a356150a6672e773c607ea`；实物大小20,910,274,592字节，内容SHA-256必须与文件名一致。

## 3. 运行规则

1. T2VA/I2VA/L2VA/FL2VA使用FL2VA Prompt Agent；Ref2VA使用Ref2VA Prompt Agent。
2. 参考图同时连接提示词节点与正式H3节点；提示词节点只理解参考语义，正式H3节点继续接收原始图像/视频、clip、vae与audio_vae。
3. 最终本地实测一条古风T2VA提示词在23.404秒完成，输出包含镜头、主体动作、花瓣运动、光线和声音结构；该耗时计入文本优化阶段，不得伪装为H3视频推理时间。
4. 本地32B专用模型单任务约占24.5GB统一内存；禁止使用原262K上下文配置（实测约90.4GB），禁止与H3视频重模型并行。任务结束必须`keep_alive=0`卸载Ollama并释放Comfy内存。
5. Ref2VA生产固定拆为两张完全独立的Comfy图：第一张只运行Context IR并落盘`optimized_prompt、selected_skills、raw_json`；确认专用32B模型不驻留且Comfy已释放后，第二张才加载H3 Ref2VA。禁止嵌套、并行或共享模型驻留。
6. 视频任务持久化`h3_context_ir`独立阶段、`context_ir_prompt_id`、心跳、尝试次数、原始三项输出和磁盘路径；Context普通执行失败最多重试一次，超时、持久化失败、取消和模型未卸载不重试。
7. H3只允许消费非空`optimized_prompt`；Context失败时整个视频任务进入failed且不得提交H3，不得直接回退原提示词冒充优化。停止、结果中断检查、看门狗、服务恢复和关闭均精确取消当前Context prompt。
8. Context finally必须删除临时身份参考输入和Comfy中转文本，调用卸载并验证`api/ps`无专用模型，再释放Comfy内存；验证失败硬阻断H3。

## 4. 验收证据

- ComfyUI 8194 `object_info`同时返回两个Context IR节点。
- 真实Comfy prompt ID：`46356c27-a347-4e5d-88f0-452109b650e5`，终态`success`；完整输入、非空输出与时间戳固化在`docs/security/h3-context-ir-runtime-smoke.json`，不依赖Comfy重启后可能清空的内存history。
- 实际输出以`integrated_multimodal_description、overall_soundscape、non_diegetic_music`组织，非空且可供H3 prompt输入。
- 测试完成后Comfy队列为0/0、Ollama已加载模型为空。
- CycloneDX SBOM：`docs/security/h3-context-ir-sbom.cdx.json`，42项组件；`pip-audit`报告：`docs/security/h3-context-ir-pip-audit.json`，已知漏洞0项；Bandit报告：`docs/security/h3-context-ir-bandit.json`，高危0、中危0、低危1。唯一低危B110准确位于上游`nodes.py:252`：调用`set_tracing_disabled(True)`时使用`except Exception: pass`。其风险是API异常时可能静默未关闭追踪；当前仅允许127.0.0.1 Ollama与占位Key，配置和LaunchAgent均声明禁用追踪，安装校验还会验证固定版本Agents API确实进入disabled状态。源代码与依赖哈希漂移时一律阻断。
