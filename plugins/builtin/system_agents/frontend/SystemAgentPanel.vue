<script setup lang="ts">
import { onMounted, ref } from "vue";
import { AgentConfigurationService, type AgentConfiguration, type AgentSummary, type ConversationMessage, type ConversationProposal, type ConversationSession, type ModelSummary } from "../../../../frontend/src/services/agent-configuration-service";
import { AgentCollaborationService, type CollaborationSession, type InspectionReport } from "../../../../frontend/src/services/agent-collaboration-service";

const service = new AgentConfigurationService({ requestId: crypto.randomUUID(), traceId: crypto.randomUUID(), identityId: "local-user", identityKind: "user", tenantId: "local-default" });
const collaborationService = new AgentCollaborationService({ requestId: crypto.randomUUID(), traceId: crypto.randomUUID(), identityId: "local-user", identityKind: "user", tenantId: "local-default" });
const models = ref<ModelSummary[]>([]); const agent = ref<AgentSummary>(); const configuration = ref<AgentConfiguration>();
const session = ref<ConversationSession>(); const messages = ref<ConversationMessage[]>([]); const proposal = ref<ConversationProposal>();
const selectedModel = ref(""); const input = ref(""); const error = ref(""); const open = ref(false);
const modelForm = ref({ model_id: "", provider_id: "", display_name: "", context_window: 32768 });
const developerId=ref(""); const testerId=ref(""); const inspectorId=ref(""); const collaboration=ref<CollaborationSession>(); const inspection=ref<InspectionReport>(); const projectId=ref("default-project"); const taskId=ref("main-task");

async function run(action: () => Promise<void>) { error.value = ""; try { await action(); } catch (value) { error.value = value instanceof Error ? value.message : "操作失败"; } }
async function loadModels() { models.value = (await service.listModels()).items; if (!selectedModel.value) selectedModel.value = models.value[0]?.model_id || ""; }
async function chooseSkill(skillId: string) { await run(async () => { agent.value = await service.registerAgent(skillId); if(skillId==='system_main_developer') developerId.value=agent.value.agent_id; else if(skillId==='system_software_tester') testerId.value=agent.value.agent_id; else inspectorId.value=agent.value.agent_id; configuration.value = undefined; session.value = undefined; messages.value = []; proposal.value = undefined; await loadModels(); }); }
async function startCollaboration(){await run(async()=>{collaboration.value=await collaborationService.open({project_id:projectId.value,root_task_id:taskId.value,developer_agent_id:developerId.value,inspector_agent_id:inspectorId.value});});}
async function submitInspection(){if(!collaboration.value)return;await run(async()=>{const handoff=await collaborationService.submit(collaboration.value!.session_id,{task_id:taskId.value,context_reference:`contexts/${taskId.value}.json`});inspection.value=await collaborationService.inspect(handoff.handoff_id);collaboration.value=await collaborationService.state(collaboration.value!.session_id);});}
async function runCollaboration(){if(!collaboration.value)return;await run(async()=>{const cycle=await collaborationService.cycle(collaboration.value!.session_id,{task_id:taskId.value,context_reference:`contexts/${taskId.value}.json`});inspection.value=cycle.report;collaboration.value=await collaborationService.state(collaboration.value!.session_id);});}
async function remediate(){if(!inspection.value)return;await run(async()=>{await collaborationService.remediate(inspection.value!.report_id);collaboration.value=await collaborationService.state(collaboration.value!.session_id);});}
async function registerModel() { await run(async () => { await service.registerModel({ ...modelForm.value, capabilities: ["chat", "reasoning", "tool_calling", "structured_output"] }); await loadModels(); }); }
async function bindModel() { if (!agent.value || !selectedModel.value) return; await run(async () => { configuration.value = configuration.value ? await service.updateConfiguration(configuration.value, selectedModel.value) : await service.createConfiguration(agent.value!.agent_id, selectedModel.value); }); }
async function startConversation() { if (!agent.value) return; await run(async () => { session.value = await service.openConversation(agent.value!.agent_id, { project_id:projectId.value, task_id:taskId.value, interface_language:"zh-CN" }); const state = await service.getConversation(session.value.session_id); messages.value = state.messages; }); }
async function send() { if (!session.value || !input.value.trim()) return; await run(async () => { const turn = await service.sendMessage(session.value!.session_id, input.value.trim()); const state = await service.getConversation(session.value!.session_id); messages.value = state.messages; proposal.value = turn.proposal || undefined; input.value = ""; }); }
async function decide(confirm: boolean) { if (!proposal.value) return; await run(async () => { proposal.value = confirm ? await service.confirmProposal(proposal.value!.proposal_id) : await service.rejectProposal(proposal.value!.proposal_id); }); }
onMounted(() => run(loadModels));
</script>

<template>
  <section class="system-agent-panel">
    <button type="button" @click="open = !open">系统 AI 配置</button>
    <div v-if="open" class="panel-body">
      <div class="row"><button @click="chooseSkill('system_main_developer')">主线开发 AI</button><button @click="chooseSkill('system_software_tester')">软件测试 AI</button><button @click="chooseSkill('system_inspector')">稽查 AI</button><span>{{ agent?.name || '未选择 Skill' }}</span></div>
      <div class="row model-create"><input v-model="modelForm.model_id" placeholder="模型 ID"><input v-model="modelForm.provider_id" placeholder="提供方 ID"><input v-model="modelForm.display_name" placeholder="显示名称"><button @click="registerModel">注册模型</button></div>
      <div class="row"><select v-model="selectedModel"><option v-for="model in models" :key="model.model_id" :value="model.model_id">{{ model.display_name }}</option></select><button :disabled="!agent || !selectedModel" @click="bindModel">{{ configuration ? '切换模型' : '绑定模型' }}</button><span v-if="configuration">v{{ configuration.configuration_version }} · {{ configuration.writable ? '可写' : '只读' }}</span></div>
      <div class="row"><button :disabled="!configuration" @click="startConversation">开始配置对话</button><input v-model="input" :disabled="!session" placeholder="描述配置变更或复杂任务" @keyup.enter="send"><button :disabled="!session" @click="send">发送</button></div>
      <div class="messages"><p v-for="message in messages" :key="message.message_id"><b>{{ message.role }}</b> {{ message.content }}</p></div>
      <div v-if="proposal" class="proposal"><span>{{ proposal.proposal_type }} · {{ proposal.status }}</span><pre>{{ proposal.requested_changes }}</pre><button v-if="proposal.status === 'pending_confirmation'" @click="decide(true)">确认</button><button v-if="proposal.status === 'pending_confirmation'" @click="decide(false)">拒绝</button></div>
      <div class="proposal"><div class="row"><input v-model="projectId" placeholder="项目 ID"><input v-model="taskId" placeholder="主线任务 ID"><button :disabled="!developerId||!testerId||!inspectorId" @click="startCollaboration">建立开发→测试→稽查协作</button><button :disabled="!collaboration" @click="runCollaboration">运行协作闭环</button><button :disabled="!collaboration" @click="submitInspection">仅稽查</button></div><p v-if="collaboration">{{ collaboration.status }} · 整改 {{ collaboration.remediation_round }}/{{ collaboration.max_remediation_rounds }}</p><div v-if="inspection"><strong>{{ inspection.verdict }} · {{ inspection.read_only?'只读报告':'' }}</strong><p v-for="issue in inspection.issues" :key="issue.issue_id">[{{ issue.severity }}] {{ issue.title }} · {{ issue.file_reference }}</p><button v-if="inspection.verdict==='changes_required' && collaboration?.status==='waiting_remediation'" @click="remediate">生成整改任务</button></div></div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </section>
</template>

<style scoped>
.system-agent-panel{font-size:12px;color:#eef1f7}.system-agent-panel>button,.row button{border:1px solid #39404d;background:#232833;color:inherit;border-radius:6px;padding:5px 8px}.panel-body{position:absolute;z-index:30;top:44px;left:12px;width:min(760px,calc(100vw - 24px));padding:12px;background:#171a21;border:1px solid #39404d;border-radius:10px;box-shadow:0 12px 40px #0008}.row{display:flex;gap:8px;align-items:center;margin-bottom:8px}.row input,.row select{min-width:0;flex:1;background:#0f1116;color:inherit;border:1px solid #39404d;border-radius:6px;padding:6px}.messages{max-height:180px;overflow:auto;background:#0f1116;padding:8px}.messages p{margin:4px 0}.proposal{margin-top:8px;padding:8px;border:1px solid #52607a}.proposal pre{white-space:pre-wrap}.error{color:#ff8f8f}
</style>
