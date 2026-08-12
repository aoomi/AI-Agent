<script setup lang="ts">
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, toRefs, watch } from "vue";
import { assistantService } from "./services/assistant.service";
import { projectService, type StoredProject } from "./services/project.service";
import { narrativeService } from "./services/narrative.service";
import { assetService } from "./services/asset.service";
import { mediaService } from "./services/media.service";
import { resourceService, type StoredResource } from "./services/resource.service";
import { taskService, type PlatformTask, type RuntimeTask } from "./services/task.service";
import { productionLedgerService, type ProductionCapability, type ProductionExtension, type ProductionLifecycle, type ProductionScopeRecord as LedgerScopeRecord, type ProductionScopeType, type ProductionWorkflowState } from "./services/production-ledger.service";
import { IndustryAgentService, type IndustryRobot } from "../../../../frontend/src/services/industry-agent-service";
import { AgentConfigurationService, type ModelSummary } from "../../../../frontend/src/services/agent-configuration-service";
import { ProviderService, type ProviderConfiguration } from "../../../../frontend/src/services/provider-service";
import type { ProjectVersion } from "./services/project.service";
import type { EpisodeOutline, OutlinePlan, StoryboardShot } from "./stores/narrative.store";
import type { Asset3DResult, AssetStatus, AssetVariant, CharacterProfile, EnhancedEpisode, EpisodeAudit, EpisodeMaster, ExportFile, PropProfile, SceneProfile, ShotImageItem, ShotVideoItem } from "./stores/asset.store";
import type { RightPanelMode, WorkflowNavigation } from "./stores/ui.store";
import { requestBlobOk, type ApiJsonResult } from "./services/api-client";
import { appRuntimeKey } from "./app-runtime";
import { readFileAsDataUrl, validateMediaFile } from "./utils/file-validation";
import { createProjectLoadIsolation, createProjectScopedCache } from "./utils/project-load-isolation";
import type { ProductionScopeRecord, ProductionStage, ProductionStatus } from "./types/production";
import { freezeGenerationClock, restoreGenerationClock } from "./utils/narrative-timing";
import { createEpisodeBatches, createStoryArcBatches } from "./utils/production-state";
import { changeTypeLabel, classifyNarrativeChange, type NarrativeChangeType } from "./utils/narrative-change";
import { buildShotRenderChunks, dialogueVoicePlan } from "./utils/media-planning";
import { resultMediaUrl } from "./utils/media-url";
import StatusPulse from "./components/base/StatusPulse.vue";
import DialogCloseButton from "./components/base/DialogCloseButton.vue";
import MediaOverlayControls from "./components/base/MediaOverlayControls.vue";
import WorkflowStatusHeader from "./components/base/WorkflowStatusHeader.vue";
import WorkflowEpisodeSelector from "./components/base/WorkflowEpisodeSelector.vue";
import ColorPresetPicker from "./components/base/ColorPresetPicker.vue";
import TaskTreeNode, { type TaskTreeItem } from "./components/task/TaskTreeNode.vue";
import WorkflowActionBar from "./components/business/WorkflowActionBar.vue";
import NarrativeCollectionHeader from "./components/business/NarrativeCollectionHeader.vue";
import UnifiedAssetCard, { type UnifiedAssetSlide } from "./components/business/UnifiedAssetCard.vue";
import NarrativeItemActions from "./components/business/NarrativeItemActions.vue";

type ChatItem = { side: "left" | "right"; text: string; status?: string; media?: UploadAsset[]; createdAt?: number; durationSeconds?: number; typing?: boolean; notice?: boolean };
type AssetScope = "临时参考" | "全局公共" | "本集私有";
type UploadAsset = { id: string; name: string; url: string; mediaType: "image" | "video" | "audio"; scope: AssetScope; label: string; aspect?: "portrait" | "landscape"; file?: File };
type VisionResponse = { description: string };
type AssistantResponse = { reply: string; intent?: "chat" | "question" | "create" | "rewrite"; sources?:Array<{ title:string; url:string; snippet:string }>; search?:{ query:string; provider_id:string; searched_at:string; cache_hit?:boolean; cache_recovered_at?:string; live_attempts?:Array<Record<string, unknown>> } };
type MentionAgent = { id:"main_developer" | "software_tester" | "inspector"; label:"主力开发" | "软件测试" | "代码稽查"; description:string };
type AgentExecutionResponse = { reply:string; agent:string; execution_mode:"workspace-write" | "read-only" };
type AgentRouteResponse = { execute:boolean; agent:"main_developer" | "software_tester" | "inspector"; label:"主力开发" | "软件测试" | "代码稽查" };
type AgentJobResponse = { job_id:string; status:"queued" | "running" | "completed" | "failed"; heartbeat_at:string; result?:AgentExecutionResponse; error?:string };
type OutlineAudit = { status:"pass" | "needs_fix"; summary:string; issues:Array<{ location:string; description:string; suggestion:string }>; phase?:"initial" | "final"; batch_id?:string };
function clonePlain<T>(value:T):T {
  return JSON.parse(JSON.stringify(value)) as T;
}
function normalizeOutlineAudit(audit:OutlineAudit):OutlineAudit {
  return { ...audit, issues:Array.isArray(audit.issues) ? audit.issues : [] };
}
function userFacingGenerationError(value:unknown) {
  const message = String(value || "").trim();
  if (!message) return "生成失败，请重试";
  if (/道具资产验收失败/.test(message)) {
    const failed:string[] = [];
    if (/"plain_neutral_background"\s*:\s*false/.test(message)) failed.push("背景不是纯中性灰");
    if (/"no_scene_or_environment"\s*:\s*false/.test(message)) failed.push("画面混入场景环境");
    if (/"no_text_or_signage"\s*:\s*false/.test(message)) failed.push("画面出现文字或招牌");
    if (/"no_live_person_or_body_part"\s*:\s*false/.test(message)) failed.push("画面出现人物或人体");
    if (/"exactly_one_isolated_prop"\s*:\s*false/.test(message)) failed.push("不是单个独立道具");
    return failed.length ? `道具图未通过：${failed.join("、")}，请继续生成` : "道具图不符合单道具规范，请继续生成";
  }
  if (/人物固定角度视觉验收失败/.test(message)) return "人物角度图未通过方向、比例或一致性验收，请继续生成";
  if (/人物(?:0度)?正面(?:全身)?基准图未通过规范验收/.test(message)) return message.replace(/^.*?人物(?:0度)?正面(?:全身)?基准图/, "人物0度正面全身基准图").slice(0, 120);
  if (/mflux|traceback|callbackregistry|permissionerror|site-packages|\bfile\s+"/i.test(message)) return "本地图片生成失败，请重试";
  return message.split(/\r?\n/, 1)[0].slice(0, 120);
}
function effectiveFinalAudits(audits:OutlineAudit[]) {
  const finals = audits.filter(audit => audit.phase === "final");
  return finals.length ? finals : audits.filter(audit => !audit.phase);
}
function narrativeAuditsPassed(audits:OutlineAudit[]) {
  const effective = effectiveFinalAudits(audits);
  return effective.length > 0 && effective.every(audit => audit.status === "pass");
}
function narrativeIssueClass(stage:EditableNarrativeStage, ...tokens:Array<string | number>) {
  const audits = stage === "outline" ? (outlineAudit.value ? [outlineAudit.value] : []) : stage === "script" ? scriptAudits.value : storyboardAudits.value;
  const matches = audits.filter(audit => audit.issues.some(issue => tokens.some(token => String(issue.location || "").includes(String(token)))));
  const initial = matches.some(audit => audit.phase === "initial");
  const final = matches.some(audit => audit.phase === "final" || !audit.phase);
  return initial && final ? "audit-issue-both" : initial ? "audit-issue-initial" : final ? "audit-issue-final" : "";
}
type ScriptItem = { episode:number; title:string; content:string; target_duration?:number };
const NARRATIVE_AUDIT_BATCH_SIZE = 10;
type AccountDialog = "剩余用量" | "显示宠物" | "邀请好友" | "设置" | "退出登录" | "";

const uiStateStorageKey = "yingxu:ui-state:v1";
type PersistedUiState = {
  selectedNode?: string; selectedEpisode?: string; activeTab?: string; input?: string;
  page?: number; selectedImage?: number; rightPanelTitle?: string;
  rightPanelMode?: RightPanelMode;
  previewCollapsed?: boolean; activeWorkflowNavigation?: WorkflowNavigation; workflowEpisode?: number;
  workflowPersonAsset?: string; workflowPropAsset?: string; workflowSceneAsset?: string;
  publicResourcesExpanded?: boolean; projectResourcesExpanded?: boolean;
  chats?: ChatItem[]; chatScrollTop?: number; generationElapsedSeconds?: number; generationStartedAt?: number;
};
function readUiState(): PersistedUiState {
  try {
    const current = window.localStorage.getItem(uiStateStorageKey);
    return JSON.parse(current || "{}") as PersistedUiState;
  }
  catch { return {}; }
}
const restoredUiState = readUiState();
const injectedAppRuntime = inject(appRuntimeKey);
if (!injectedAppRuntime) throw new Error("应用运行时未初始化");
const appRuntime = injectedAppRuntime;
appRuntime.uiStore.replace(restoredUiState);
const {
  selectedNode, selectedEpisode, activeTab, input, page, selectedImage,
  rightPanelTitle, rightPanelMode, previewCollapsed, activeWorkflowNavigation,
  workflowEpisode, workflowPersonAsset, workflowPropAsset, workflowSceneAsset,
  publicResourcesExpanded, projectResourcesExpanded,
} = toRefs(appRuntime.uiStore.state);

const railItems = ["⌂", "⌑", "▦", "▥", "▰", "◇", "⬇", "◆"];
const railCollapsed = ref(false);
const selectedRail = ref(0);
const searchTerm = ref("");
const projects = ref<string[]>([]);
const chatFallbackCreatedAt = Date.now();

function formatChatDuration(seconds = 0) {
  const safeSeconds = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(safeSeconds / 60);
  const remainingSeconds = safeSeconds % 60;
  return minutes ? `${minutes}m ${remainingSeconds}s` : `${remainingSeconds}s`;
}

function formatChatClock(timestamp = chatFallbackCreatedAt) {
  return new Intl.DateTimeFormat("zh-CN", { hour:"2-digit", minute:"2-digit", hour12:false }).format(new Date(timestamp));
}
const projectRecords = ref<StoredProject[]>([]);
const archivedProjects = ref<StoredProject[]>([]);
const projectVersions = ref<ProjectVersion[]>([]);
const productionVersions = ref<Array<LedgerScopeRecord & { version_status:string; versioned_at:string }>>([]);
const productionWorkflow = ref<ProductionWorkflowState | null>(null);
const productionCapabilities = ref<ProductionCapability[]>([]);
const productionExtensions = ref<ProductionExtension[]>([]);
const projectIdentity = { tenant_id:"local-default", user_id:"aoo" } as const;
const assistantSessionId = window.localStorage.getItem("yingxu:assistant-session-id") || crypto.randomUUID();
window.localStorage.setItem("yingxu:assistant-session-id", assistantSessionId);
let projectSession = 0;
const assistantController = ref<AbortController>();
const selectedAssistantModel = ref("");
const modelMenuOpen = ref(false);
const modelDisplayName = ref("5.6 Sol");
const modelEffort = ref<"轻度" | "中" | "高" | "极高">("轻度");
const mentionAgents:MentionAgent[] = [
  { id:"main_developer", label:"主力开发", description:"开发、修改代码并运行验证" },
  { id:"software_tester", label:"软件测试", description:"只读执行本次增量功能、接口、边界和异常测试" },
  { id:"inspector", label:"代码稽查", description:"只读检查代码并输出稽查结论" },
];
const activeMentionIndex = ref(0);
const mentionMatch = computed(() => input.value.match(/(?:^|\s)@([^\s@]*)$/));
const mentionCandidates = computed(() => {
  const query = mentionMatch.value?.[1] || "";
  return mentionMatch.value ? mentionAgents.filter(agent => agent.label.includes(query)) : [];
});
const mentionMenuOpen = computed(() => mentionCandidates.value.length > 0);
const activeProjectRecord = computed(() => projectRecords.value.find(project => project.id === appRuntime.projectStore.state.currentProjectId) || null);
const projectEpisodeOptions = computed(() => Array.from({ length:activeProjectRecord.value?.episode_count || 0 }, (_, index) => `第${String(index + 1).padStart(2, "0")}集`));
const projectMenuOpen = ref(false);
const copiedChatIndex = ref<number | null>(null);
const copiedEpisodeKey = ref("");
const chatFeedback = ref<Record<number, "up" | "down" | "">>({});
const thinking = ref("");
const thinkingElapsedSeconds = ref(0);
let thinkingTimer = 0;
const generationStartedAt = ref(0);
const generationElapsedSeconds = ref(0);
let generationTimer = 0;
function startGenerationTimer(reset = true) {
  window.clearInterval(generationTimer);
  if (reset || !generationStartedAt.value) {
    generationElapsedSeconds.value = 0;
    generationStartedAt.value = Date.now();
  }
  const updateElapsed = () => {
    generationElapsedSeconds.value = Math.max(0, Math.floor((Date.now() - generationStartedAt.value) / 1000));
  };
  updateElapsed();
  generationTimer = window.setInterval(updateElapsed, 1000);
}
function stopGenerationTimer() {
  const frozen = freezeGenerationClock(generationStartedAt.value, generationElapsedSeconds.value);
  generationStartedAt.value = frozen.generationStartedAt;
  generationElapsedSeconds.value = frozen.generationElapsedSeconds;
  window.clearInterval(generationTimer);
  generationTimer = 0;
}
function resetGenerationTimerState() {
  window.clearInterval(generationTimer);
  generationTimer = 0;
  generationStartedAt.value = 0;
  generationElapsedSeconds.value = 0;
}
const chatScroll = ref<HTMLElement>();
const projectTabs = ref<HTMLElement>();
const fileInput = ref<HTMLInputElement>();
const assetReplaceInput = ref<HTMLInputElement>();
const assetReplaceTarget = ref<{ item:CharacterProfile | SceneProfile | PropProfile; variant?:AssetVariant }>();
const shotImageReplaceInput = ref<HTMLInputElement>();
const shotImageReplaceTarget = ref<ShotImageItem>();
const shotVideoReplaceInput = ref<HTMLInputElement>();
const shotVideoReplaceTarget = ref<ShotVideoItem>();
type StandardImportStage = "outline" | "script" | "storyboard" | "assets" | "shot_images" | "shot_videos" | "merged_episodes" | "final_audit";
const standardImportInput = ref<HTMLInputElement>();
const standardImportStage = ref<StandardImportStage>();
const exportSourceVersion = ref<"base" | "enhanced">("base");
const regenerateFileInput = ref<HTMLInputElement>();
const regenerateTarget = ref<UploadAsset>();
const regeneratePrompt = ref("");
const regenerateReference = ref<{ name:string; url:string }>();
const regeneratePosition = ref({ top:16, left:16 });
const isDragging = ref(false);
const uploadedAssets = ref<UploadAsset[]>([]);
const stagedAssets = ref<UploadAsset[]>([]);
const webSearchEnabled = ref(false);
const lastBatch = ref<UploadAsset[]>([]);
type ProjectComposerState = { input:string; uploadedAssets:UploadAsset[]; stagedAssets:UploadAsset[]; lastBatch:UploadAsset[] };
const composerStateByProject = new Map<string, ProjectComposerState>();
const dynamicGlobalNodes = ref<string[]>([]);
const dynamicEpisodeNodes = ref<string[]>([]);
const previewClosing = ref(false);
const previewOpening = ref(false);
function restorePanelWidth(key: string, fallback: number, min: number, max: number) {
  const value = Number(window.localStorage.getItem(key));
  return Number.isFinite(value) && value >= min && value <= max ? value : fallback;
}

const leftPanelWidth = ref(restorePanelWidth("yingxu:left-panel-width", 280, 220, 420));
const rightPanelWidth = ref(restorePanelWidth("yingxu:right-panel-width", 340, 260, 560));
const viewportWidth = ref(window.innerWidth);
function syncViewportWidth() { viewportWidth.value = window.innerWidth; }
const resizingPanel = ref<"left" | "right" | null>(null);
const newProjectOpen = ref(false);
const workspaceDialog = ref<"任务" | "Skill" | "工具" | "">("");
const platformTasks = ref<PlatformTask[]>([]);
const runtimeTasks = ref<RuntimeTask[]>([]);
function taskTreeStatus(status:PlatformTask["status"]):TaskTreeItem["status"] {
  if (status === "completed") return "已完成";
  if (status === "running" || status === "queued") return "进行中";
  if (status === "paused") return "已暂停";
  if (status === "failed") return "失败";
  return "未开始";
}
function platformTaskProductionStage(task:PlatformTask) {
  const stage = String(task.stage || "");
  const handlerStages:Record<string, ProductionStage> = {
    handleOutlinePlan:"outline", handleOutlineEpisodes:"outline", handleNarrativeAudit:"outline", handleScriptEpisode:"script", handleStoryboard:"storyboard",
    handleCharacterProfiles:"assets", handleCharacterImage:"assets", handleShotImage:"image", handleShotSemanticAudit:"image", handleShotVideo:"video",
    handleMergeVideos:"composition", handleFinalVideoAudit:"review_export", handleUpscaleVideo:"review_export", handleCreateExport:"review_export",
  };
  return handlerStages[stage] || stage;
}
const taskTreeDemo = computed<TaskTreeItem[]>(() => {
  const projectId = activeProjectRecord.value?.id;
  const scopeRecords = projectId ? appRuntime.productionStore.state.records.filter(record => record.project_id === projectId) : [];
  if (scopeRecords.length && !platformTasks.value.length) {
    const titleByStage:Record<string, string> = { requirements:"项目需求", outline:"故事大纲", script:"生成剧本", storyboard:"分镜脚本", assets:"人物场景", image:"镜头画面", video:"分镜视频", audio:"配音与声音", subtitle:"字幕", composition:"合并成片", review_export:"审核与导出" };
    const statusOf = (status:ProductionStatus):TaskTreeItem["status"] => status === "completed" || status === "skipped" ? "已完成" : status === "failed" ? "失败" : status === "paused" ? "已暂停" : status === "stale" ? "已失效" : status === "pending_confirmation" ? "待审核" : ["queued", "running", "auditing", "repairing", "rechecking"].includes(status) ? "进行中" : "未开始";
    const grouped = new Map<string, ProductionScopeRecord[]>();
    for (const record of scopeRecords) grouped.set(record.stage, [...(grouped.get(record.stage) || []), record]);
    const queueStages = new Set(platformTasks.value.map(platformTaskProductionStage));
    for (const stage of queueStages) if (!grouped.has(stage)) grouped.set(stage, []);
    const children = [...grouped.entries()].map(([stage, records]) => {
      const progress = appRuntime.productionStore.aggregateStageProgress(projectId || "", stage);
      const liveTasks = platformTasks.value.filter(task => platformTaskProductionStage(task) === stage);
      const queueStatus:TaskTreeItem["status"] | undefined = liveTasks.some(task => task.status === "failed") ? "失败" : liveTasks.some(task => task.status === "paused") ? "已暂停" : liveTasks.some(task => task.status === "running" || task.status === "queued") ? "进行中" : undefined;
      return {
        id:`scope-stage-${stage}`, title:titleByStage[stage] || stage, progress:progress.label, status:queueStatus || statusOf(progress.status as ProductionStatus), open:true,
        children:[
          ...liveTasks.map(task => ({ id:`queue-${task.id}`, title:`${task.label}${task.error?.message ? ` · ${task.error.message}` : ""}`, status:taskTreeStatus(task.status) })),
          ...records.map(record => ({ id:`scope-${record.stage}-${record.scope_type}-${record.scope_id}`, title:`${record.scope_type} · ${record.scope_id}${record.error ? ` · ${record.error}` : ""}`, progress:`${record.completed_count}/${record.total_count}`, status:statusOf(record.status) })),
        ],
      } satisfies TaskTreeItem;
    });
    const completed = scopeRecords.reduce((sum, record) => sum + Math.min(record.completed_count, record.total_count), 0);
    const total = scopeRecords.reduce((sum, record) => sum + record.total_count, 0);
    const rootStatus:TaskTreeItem["status"] = children.some(item => item.status === "失败") ? "失败" : children.some(item => item.status === "已暂停") ? "已暂停" : children.some(item => item.status === "进行中") ? "进行中" : children.some(item => item.status === "待审核") ? "待审核" : children.some(item => item.status === "已失效") ? "已失效" : children.every(item => item.status === "已完成") ? "已完成" : "未开始";
    return [{ id:"production-scopes", title:"短剧生产流程", progress:`${completed}/${total}`, status:rootStatus, open:true, children }];
  }
  const grouped = new Map<string, PlatformTask[]>();
  for (const task of platformTasks.value) {
    const stage = task.stage || "task";
    grouped.set(stage, [...(grouped.get(stage) || []), task]);
  }
  const children = [...grouped.entries()].map(([stage, stageTasks]) => ({
    id:`stage-${stage}`, title:stageTasks[0]?.label || stage, progress:`${stageTasks.filter(task => task.status === "completed").length}/${stageTasks.length}`,
    status:taskTreeStatus(stageTasks.some(task => task.status === "failed") ? "failed" : stageTasks.some(task => task.status === "paused") ? "paused" : stageTasks.some(task => task.status === "running" || task.status === "queued") ? "running" : stageTasks.every(task => task.status === "completed") ? "completed" : "cancelled"),
    open:true, children:stageTasks.map(task => ({ id:`task-${task.id}`, title:task.label, status:taskTreeStatus(task.status) })),
  } satisfies TaskTreeItem));
  return children.length ? [{ id:"production", title:"短剧生产流程", progress:`${platformTasks.value.filter(task => task.status === "completed").length}/${platformTasks.value.length}`, status:taskTreeStatus(platformTasks.value.some(task => task.status === "failed") ? "failed" : platformTasks.value.some(task => task.status === "paused") ? "paused" : platformTasks.value.some(task => task.status === "running" || task.status === "queued") ? "running" : platformTasks.value.every(task => task.status === "completed") ? "completed" : "cancelled"), open:true, children }] : [];
});
const taskFault = ref("");
const expandedTaskStages = ref<string[]>([]);
const expandedTaskEpisodes = ref<string[]>([]);
const storedResources = ref<StoredResource[]>([]);
let taskRefreshTimer = 0;
const agentApiContext = { requestId:crypto.randomUUID(), traceId:crypto.randomUUID(), identityId:projectIdentity.user_id, identityKind:"user" as const, tenantId:projectIdentity.tenant_id };
const industryAgentService = new IndustryAgentService(agentApiContext);
const agentConfigurationService = new AgentConfigurationService(agentApiContext);
const providerService = new ProviderService(agentApiContext);
const enabledSkills = ref<string[]>([]);
// 当前先跑通大纲→剧本→分镜生成链；72B 文本审核能力保留但暂停执行。
const narrativeAuditPaused = ref(true);
const narrativeAuditEnabled = computed(() => !narrativeAuditPaused.value && enabledSkills.value.includes("审核"));
const auditEnabledSkills = ref<string[]>([]);
const skillRobots = ref<Record<string, IndustryRobot[]>>({});
const skillChanging = ref("");
const configuringSkill = ref("");
const availableModels = ref<ModelSummary[]>([]);
const availableProviders = ref<ProviderConfiguration[]>([]);
const selectedSkillModel = ref("automatic");
const skillModelBindings = ref<Record<string,string>>({});
const modelRole = ref<"main"|"initial"|"final">("main");
const modelSource = ref<"local"|"cloud">("local");
const skillReviewModelBindings = ref<Record<string,string>>({});
const roleModelDrafts = ref<Record<string,string>>({});
type AuditPlan = "economy"|"balanced"|"quality";
const auditPlan = ref<AuditPlan>("balanced");
const auditAdvancedOpen = ref(false);
const auditPhase = ref<"initial"|"final">("initial");
const auditModelBindings = ref<Record<string,string>>({ text_initial:"automatic", text_final:"automatic", visual_initial:"automatic", visual_final:"automatic", audio_initial:"automatic", audio_final:"automatic" });
type ModelCategory = "automatic"|"text"|"vision"|"audio"|"video";
type ModelPreset = { id:string; name:string; category:ModelCategory; context:number; capabilities:string[]; available?:boolean };
const localModelPresets:ModelPreset[] = [
  { id:"qwen3:8b", name:"通义千问 Qwen3 8B（快速）", category:"text", context:40960, capabilities:["chat","reasoning","structured_output","tool_calling"] },
  { id:"qwen2.5:72b", name:"通义千问 Qwen2.5 72B", category:"text", context:32768, capabilities:["chat","structured_output","tool_calling"] },
  { id:"qwen3:32b", name:"通义千问 Qwen3 32B", category:"text", context:40960, capabilities:["chat","reasoning","structured_output","tool_calling"] },
  { id:"deepseek-r1:70b", name:"DeepSeek R1 70B", category:"text", context:131072, capabilities:["chat","reasoning","structured_output"] },
  { id:"llava:latest", name:"LLaVA 7B 视觉模型", category:"vision", context:32768, capabilities:["chat","vision"] },
  { id:"qwen2.5vl:7b", name:"通义千问 Qwen2.5 VL 7B", category:"vision", context:32768, capabilities:["chat","vision","structured_output"], available:false },
  { id:"gemma3:12b", name:"Gemma 3 Vision 12B", category:"vision", context:128000, capabilities:["chat","vision","structured_output"], available:false },
  { id:"minicpm-v:8b", name:"MiniCPM-V 8B", category:"vision", context:32768, capabilities:["chat","vision"], available:false },
  { id:"cosyvoice2-0.5b", name:"CosyVoice2 0.5B 中文语音", category:"audio", context:32768, capabilities:["chat"] },
  { id:"wan2.1-t2v-1.3b", name:"Wan2.1 T2V 1.3B（快速）", category:"video", context:32768, capabilities:["vision"] },
];
const cloudModelPresets:Record<string,{ name:string; endpoint:string; secret:string; models:ModelPreset[] }> = {
  openai:{ name:"OpenAI", endpoint:"https://api.openai.com/v1", secret:"env://OPENAI_API_KEY", models:[{ id:"gpt-5.2", name:"GPT-5.2", category:"text", context:400000, capabilities:["chat","reasoning","vision","structured_output","tool_calling"] },{ id:"gpt-4.1", name:"GPT-4.1 视觉", category:"vision", context:1000000, capabilities:["chat","vision","structured_output","tool_calling"] }] },
  anthropic:{ name:"Anthropic", endpoint:"https://api.anthropic.com/v1", secret:"env://ANTHROPIC_API_KEY", models:[{ id:"claude-sonnet-4-5", name:"Claude Sonnet 4.5", category:"text", context:200000, capabilities:["chat","reasoning","vision","structured_output","tool_calling"] }] },
  deepseek:{ name:"DeepSeek", endpoint:"https://api.deepseek.com/v1", secret:"env://DEEPSEEK_API_KEY", models:[{ id:"deepseek-chat", name:"DeepSeek Chat", category:"text", context:128000, capabilities:["chat","structured_output","tool_calling"] },{ id:"deepseek-reasoner", name:"DeepSeek Reasoner", category:"text", context:128000, capabilities:["chat","reasoning","structured_output"] }] },
  gemini:{ name:"Google Gemini", endpoint:"https://generativelanguage.googleapis.com/v1beta/openai", secret:"env://GEMINI_API_KEY", models:[{ id:"gemini-2.5-pro", name:"Gemini 2.5 Pro 视觉", category:"vision", context:1000000, capabilities:["chat","reasoning","vision","structured_output","tool_calling"] }] },
  dashscope:{ name:"阿里云百炼", endpoint:"https://dashscope.aliyuncs.com/compatible-mode/v1", secret:"env://DASHSCOPE_API_KEY", models:[{ id:"qwen-max", name:"通义千问 Max", category:"text", context:32768, capabilities:["chat","reasoning","structured_output","tool_calling"] },{ id:"qwen-vl-max", name:"通义千问 VL Max", category:"vision", context:32768, capabilities:["chat","vision","structured_output"] }] },
};
const localModelForm = ref({ runtime:"Ollama", endpoint:"http://127.0.0.1:11434/v1", model_id:localModelPresets[0].id });
const cloudModelForm = ref({ platform:"openai", endpoint:cloudModelPresets.openai.endpoint, model_id:cloudModelPresets.openai.models[0].id });
const modelCategory = ref<ModelCategory>("text");
const selectedCloudPlatform = computed(() => cloudModelPresets[cloudModelForm.value.platform] || cloudModelPresets.openai);
const filteredLocalModels = computed(() => localModelPresets.filter(model => model.category === modelCategory.value));
const filteredCloudModels = computed(() => selectedCloudPlatform.value.models.filter(model => model.category === modelCategory.value));
const activeRoleModel = computed({
  get:() => modelRole.value === "main" ? selectedSkillModel.value : skillReviewModelBindings.value[`${configuringSkill.value}:${modelRole.value}`] || "automatic",
  set:(value:string) => {
    if (modelRole.value === "main") selectedSkillModel.value = value;
    else skillReviewModelBindings.value[`${configuringSkill.value}:${modelRole.value}`] = value;
  },
});
const skillConfigurationSaving = ref(false);
const skillRobotIds:Record<string, string[]> = {
  "项目策划":["duanju.xiangmu_xuqiu","duanju.gushi_dagang"],
  "编剧":["duanju.juben","duanju.fenjing_jiaoben"],
  "视觉资产":["duanju.shijue_zichan","duanju.fenjing_huamian"],
  "视频制作":["duanju.fenjing_shipin","duanju.yinpin","duanju.zimu"],
  "后期制作":["duanju.hepian","duanju.jicha_daochu"],
  "代码稽查":["system_inspector"],
  "软件测试":["system_software_tester"],
  "主力开发":["system_main_developer"],
  "审核":["duanju.gushi_dagang","duanju.juben","duanju.fenjing_jiaoben","duanju.shijue_zichan","duanju.fenjing_huamian","duanju.fenjing_shipin","duanju.yinpin","duanju.zimu","duanju.jicha_daochu"],
};
const skillDescriptions:Record<string,string> = {
  "项目策划":"项目需求＋故事大纲", "编剧":"剧本＋分镜脚本", "视觉资产":"人物＋场景＋道具＋分镜画面",
  "视频制作":"分镜视频＋音频＋字幕", "后期制作":"合片＋超分降噪＋导出", "审核":"文本＋视觉＋音频审核 · 初审与终审自动分配",
  "代码稽查":"代码质量、安全与规范检查", "软件测试":"增量功能、接口、参数、边界与异常测试", "主力开发":"需求实现、架构与主线开发",
};
const skillCategories = [
  { name:"短剧流程", skills:["项目策划", "编剧", "视觉资产", "视频制作", "后期制作"] },
  { name:"软件开发", skills:["主力开发", "软件测试", "代码稽查"] },
] as const;
const allDefaultSkills = skillCategories.flatMap(category => [...category.skills]);
const activeSkillCategory = ref<(typeof skillCategories)[number]["name"]>("短剧流程");
const visibleSkillCategory = computed(() => skillCategories.find(category => category.name === activeSkillCategory.value) || skillCategories[0]);
const editingProjectName = ref("");
const newProjectName = ref("");
type LocalLoraStyle = { id:string; name:string; model_count:number; updated_at:number };
const localLoraStyles = ref<LocalLoraStyle[]>([]);
const newProjectGenre = ref("");
let localLoraStyleTimer = 0;
async function loadLocalLoraStyles() {
  const response = await fetch("/api/lora/styles", { cache:"no-store" });
  if (!response.ok) throw new Error(`LoRA 风格索引失败：HTTP ${response.status}`);
  const payload = await response.json() as { styles?:LocalLoraStyle[] };
  localLoraStyles.value = Array.isArray(payload.styles) ? payload.styles : [];
  if (!newProjectGenre.value) newProjectGenre.value = localLoraStyles.value[0]?.id || "";
  newProjectStyle.value = newProjectGenre.value;
}
const newProjectLoraMode = ref<"automatic"|"fixed"|"manual"|"exploration">("automatic");
const newProjectLoraId = ref("cn-mythic");
const newProjectLoraSeed = ref<number|null>(null);
const newProjectPrompt = ref("");
const newProjectStyle = ref("");
const newProjectDurationMin = ref(60);
const newProjectDurationMax = ref(70);
const newProjectEpisodes = ref(5);
const newProjectUpscale = ref("不超分");
const newProjectLanguage = ref("简体中文");
const newProjectSubtitle = ref("思源黑体 · 2px · 透明度 100%");
const newProjectAiLabel = ref("AI辅助生成 · 写入文件元数据");
const subtitleExpanded = ref(true);
const subtitlePreviewText = ref("你是不是，从来都没相信过我？");
const subtitleFont = ref("思源黑体");
const subtitleFontSize = ref(16);
const subtitleColor = ref("#FFFFFF");
const subtitleStrokeColor = ref("#000000");
const subtitleStrokeWidth = ref(2);
const subtitleOpacity = ref(100);
const aiLabelExpanded = ref(false);
const visibleAiWatermark = ref(true);
const metadataAiLabel = ref(true);
const aiWatermarkText = ref("AI辅助生成");
const aiWatermarkSize = ref(12);
const aiWatermarkColor = ref("#FFFFFF");
const aiWatermarkStrokeColor = ref("#000000");
const aiWatermarkStrokeWidth = ref(1);
const aiWatermarkOpacity = ref(100);
const aiWatermarkX = ref(82);
const aiWatermarkY = ref(92);
const accountMenuOpen = ref(false);
const accountDialog = ref<AccountDialog>("");
const petVisible = ref(true);
const desktopNotifications = ref(true);
const autoSave = ref(true);
const episodeMenuOpen = ref(false);
const availableEpisodes = Array.from({ length: 30 }, (_, index) => `第${String(index + 1).padStart(2, "0")}集`);
const resourceMenuOpen = ref<"文本" | "图集" | "分镜" | "视频" | "">("");
const assetIntroOpen = ref("");
let assetCarouselMomentumFrame = 0;
const selectedResourceLabels = ref<Record<"文本" | "图集" | "分镜" | "视频", string>>({ 文本: "文本", 图集: "图集", 分镜: "分镜", 视频: "视频" });
const textResourceOptions = ["故事大纲", "全剧本", "分镜脚本"];
const galleryResourceOptions = ["人物定妆图", "场景布景图", "道具图", "封面配图"];
const workflowNavigation = ["大纲", "剧本", "分镜脚本", "资产", "分镜画面", "分镜视频", "成片", "导出"] as const;
const workflowDockNavigation = workflowNavigation;
const workflowDockLabel = (kind:WorkflowNavigation) => kind;
const versionStageMap:Record<string,string> = { requirements:"需求", outline:"大纲", script:"剧本", storyboard:"分镜", assets:"资产", image:"图片", video:"视频", audio:"音频", subtitle:"字幕", composition:"合成", review_export:"审核导出" };
const versionScopeMap:Record<string,string> = { project:"项目", story_arc_batch:"故事弧批次", episode_batch:"集批次", episode:"集", scene:"场景", shot:"镜头", line:"台词", asset:"资产" };
const versionScopeIdPrefixMap:Record<string,string> = { character:"人物", scene:"场景", prop:"道具" };
const versionStatusMap:Record<string,string> = { current:"当前", stale:"已失效", withdrawn:"待复审", expired:"已过期", superseded:"已替代" };
function versionDisplayLabel(v:{stage:string;scope_type:string;scope_id:string;version_status:string}) {
  const stage = versionStageMap[v.stage] ?? v.stage;
  const scopeType = versionScopeMap[v.scope_type] ?? v.scope_type;
  const scopeId = v.scope_id.replace(/^(character|scene|prop):/, (_,k) => `${versionScopeIdPrefixMap[k] ?? k}:`);
  return `${stage} / ${scopeType} / ${scopeId}`;
}
function versionStatusLabel(status:string) { return versionStatusMap[status] ?? status; }
const generatedEpisodeCount = ref(0);
const outlinePlan = ref<OutlinePlan | null>(null);
const outlineEpisodes = ref<EpisodeOutline[]>([]);
const outlineStatus = ref<"idle" | "generating" | "waiting_confirmation" | "confirmed" | "failed">("idle");
const outlineError = ref("");
const outlineAudit = ref<OutlineAudit | null>(null);
const outlineAuditStopped = ref(false);
const outlineController = ref<AbortController>();
const outlineGenerationId = ref("");
type OutlineRevision = { label:string; before:string; after:string };
const outlinePhase = ref<"generating" | "audit" | "repair" | "">("");
const outlineRevisions = ref<OutlineRevision[]>([]);
const outlineReviewPlan = ref<OutlinePlan | null>(null);
const outlineReviewEpisodes = ref<EpisodeOutline[]>([]);
const outlineShowingReviewSnapshot = computed(() => Boolean(outlineReviewPlan.value) && (outlinePhase.value === "audit" || outlinePhase.value === "repair"));
const outlinePhaseText = computed(() => outlinePhase.value === "generating"
  ? "大纲生成中......"
  : outlinePhase.value === "audit"
    ? "正在初审......"
    : outlinePhase.value === "repair" ? "正在终审......" : "");
const outlineThinking = ref(false);
const outlineTypedTitle = ref("");
const outlineTypedPlan = ref("");
const outlineTypedEpisodes = ref<Record<number, { title:string; synopsis:string }>>({});
const outlinePendingEpisode = ref<number | null>(null);
async function typeOutlineText(text:string, setter:(value:string) => void, signal:AbortSignal) {
  if (signal.aborted) throw new DOMException("生成已停止", "AbortError");
  setter(text);
  await new Promise<void>(resolve => window.requestAnimationFrame(() => resolve()));
}
async function revealCompletedUnit() {
  await nextTick();
  await new Promise<void>(resolve => window.requestAnimationFrame(() => resolve()));
}
async function typeOutlinePlan(plan:OutlinePlan, signal:AbortSignal) {
  await typeOutlineText(plan.title || "全剧故事大纲", value => { outlineTypedTitle.value = value; }, signal);
  await typeOutlineText(plan.general_outline, value => { outlineTypedPlan.value = value; }, signal);
}
async function typeOutlineEpisode(episode:EpisodeOutline, signal:AbortSignal) {
  outlineTypedEpisodes.value = { ...outlineTypedEpisodes.value, [episode.episode]:{ title:"", synopsis:"" } };
  await typeOutlineText(episode.title, value => {
    outlineTypedEpisodes.value = { ...outlineTypedEpisodes.value, [episode.episode]:{ ...outlineTypedEpisodes.value[episode.episode], title:value } };
  }, signal);
  await typeOutlineText(episode.synopsis, value => {
    outlineTypedEpisodes.value = { ...outlineTypedEpisodes.value, [episode.episode]:{ ...outlineTypedEpisodes.value[episode.episode], synopsis:value } };
  }, signal);
}
const scripts = ref<ScriptItem[]>([]);
const scriptStatus = ref<"idle" | "generating" | "waiting_confirmation" | "confirmed" | "failed">("idle");
const scriptError = ref("");
const scriptAudits = ref<OutlineAudit[]>([]);
const scriptController = ref<AbortController>();
const scriptPhase = ref<"generating" | "initial_audit" | "final_audit" | "">("");
const scriptGenerationId = ref("");
const scriptGenerationStartedAt = ref(0);
const scriptHeartbeatAt = ref(0);
let scriptHeartbeatTimer:number | undefined;
const scriptPhaseText = computed(() => scriptPhase.value === "generating"
  ? "剧本生成中......"
  : scriptPhase.value === "initial_audit"
    ? "正在初审......"
    : scriptPhase.value === "final_audit" ? "正在终审......" : "");
const storyboardShots = ref<StoryboardShot[]>([]);
const storyboardStatus = ref<"idle" | "generating" | "waiting_confirmation" | "confirmed" | "failed">("idle");
const storyboardError = ref("");
const storyboardAudits = ref<OutlineAudit[]>([]);
const storyboardController = ref<AbortController>();
type EditableNarrativeStage = "outline" | "script" | "storyboard";
type NarrativeEditDraft = { key:string; stage:EditableNarrativeStage; before:string; after:string; source:{ stage:string; scope_type:ProductionScopeType; scope_id:string }; changeType:NarrativeChangeType };
const narrativeEditDrafts = ref<Record<string, NarrativeEditDraft>>({});
const narrativeEditSubmitting = ref(false);
const narrativeStageHasDrafts = (stage:EditableNarrativeStage) => Object.values(narrativeEditDrafts.value).some(draft => draft.stage === stage);

function updateNarrativeDraft(stage:EditableNarrativeStage, key:string, before:string, source:NarrativeEditDraft["source"], event:Event) {
  const target = event.currentTarget as HTMLElement;
  const editableClone = target.cloneNode(true) as HTMLElement;
  editableClone.querySelectorAll('[contenteditable="false"]').forEach(node => node.remove());
  const after = editableClone.innerText.replace(/\u00a0/g, " ").trim();
  if (stage === "script" && source.scope_type === "episode") {
    const beforeLines = before.split(/\r?\n/);
    const afterLines = after.split(/\r?\n/);
    const changed = Array.from({ length:Math.max(beforeLines.length, afterLines.length) }, (_, index) => index).filter(index => (beforeLines[index] || "").trim() !== (afterLines[index] || "").trim());
    if (changed.length === 1) source = { stage:"script", scope_type:"line", scope_id:`${source.scope_id}:${changed[0] + 1}` };
  }
  const drafts = { ...narrativeEditDrafts.value };
  if (after === before.trim()) delete drafts[key];
  else drafts[key] = { key, stage, before, after, source, changeType:classifyNarrativeChange(before, after) };
  narrativeEditDrafts.value = drafts;
}

function applyNarrativeDraft(draft:NarrativeEditDraft) {
  const parts = draft.key.split(":");
  if (draft.stage === "outline" && parts[1] === "project") {
    if (outlinePlan.value) outlinePlan.value = parts[2] === "title" ? { ...outlinePlan.value, title:draft.after } : { ...outlinePlan.value, general_outline:draft.after };
  } else if (draft.stage === "outline") {
    const episode = Number(parts[2]);
    outlineEpisodes.value = outlineEpisodes.value.map(item => item.episode === episode ? { ...item, synopsis:draft.after } : item);
  } else if (draft.stage === "script") {
    const episode = Number(parts[2]);
    scripts.value = scripts.value.map(item => item.episode === episode ? { ...item, content:draft.after } : item);
  } else {
    const episode = Number(parts[2]);
    const shotNumber = Number(parts[3]);
    const field = parts[4] === "action" ? "action" : "visual";
    storyboardShots.value = storyboardShots.value.map(item => item.episode === episode && item.shot_number === shotNumber ? { ...item, [field]:draft.after } : item);
  }
}

async function submitNarrativeEdits(stage:EditableNarrativeStage) {
  const project = activeProjectRecord.value;
  const drafts = Object.values(narrativeEditDrafts.value).filter(draft => draft.stage === stage && draft.changeType !== "none");
  if (!project || !drafts.length || narrativeEditSubmitting.value) return;
  narrativeEditSubmitting.value = true;
  try {
    const previews = await Promise.all(drafts.map(draft => productionLedgerService.previewImpact({ ...projectIdentity, project_id:project.id, source:draft.source, change_type:draft.changeType })));
    const affected = new Map<string, LedgerScopeRecord>();
    previews.flatMap(result => result.records).forEach(record => affected.set(`${record.stage}:${record.scope_type}:${record.scope_id}`, record));
    const categories = [...new Set(drafts.map(draft => changeTypeLabel(draft.changeType)))].join("、");
    const impactText = [...affected.values()].map(record => `${record.stage}/${record.scope_type}/${record.scope_id}`).join("、") || "仅当前正文";
    if (!window.confirm(`变更分类：${categories}\n实际下游影响：${impactText}\n确认提交修改？`)) return;
    await projectService.createVersion({ ...projectIdentity, project_id:project.id, project_name:project.name, stage:`before-${stage}-edit`, reason:`${stage} 正文修改前归档` });
    drafts.forEach(applyNarrativeDraft);
    if (stage === "outline") {
      outlineStatus.value = "confirmed";
      outlineAudit.value = null;
      await persistOutlineState(project);
      const titleDraft = drafts.find(draft => draft.key === "outline:project:title");
      if (titleDraft) await syncProjectNameFromOutline(titleDraft.after);
    } else if (stage === "script") {
      scriptStatus.value = "confirmed";
      scriptAudits.value = [];
      await persistScriptState(project);
    } else {
      storyboardStatus.value = "confirmed";
      storyboardAudits.value = [];
      await persistStoryboardState(project);
    }
    for (const draft of drafts) await productionLedgerService.invalidate({ ...projectIdentity, project_id:project.id, source:draft.source, change_type:draft.changeType, reason:`用户提交${changeTypeLabel(draft.changeType)}修改` });
    const submitted = new Set(drafts.map(draft => draft.key));
    narrativeEditDrafts.value = Object.fromEntries(Object.entries(narrativeEditDrafts.value).filter(([key]) => !submitted.has(key)));
    notify("修改已提交，受影响范围已进入待复审");
  } catch (error) {
    notify(error instanceof Error ? error.message : "提交修改失败");
  } finally { narrativeEditSubmitting.value = false; }
}

async function withdrawConfirmedNarrativeBatch(stage:EditableNarrativeStage) {
  const project = activeProjectRecord.value;
  if (!project) return;
  const candidates = appRuntime.productionStore.state.records.filter(record => record.project_id === project.id && record.stage === stage && record.status === "completed" && ["story_arc_batch", "episode", "project"].includes(record.scope_type));
  const selected = candidates.find(record => record.scope_type === "story_arc_batch" && record.confirmation_scope.scope_ids.includes(String(workflowEpisode.value))) || candidates.find(record => record.scope_type === "project") || candidates[0];
  if (!selected || !window.confirm(`确认撤回 ${selected.scope_type}/${selected.scope_id} 的人工确认？`)) return;
  try {
    await productionLedgerService.withdrawConfirmation({ ...projectIdentity, project_id:project.id, stage:selected.stage, scope_type:selected.scope_type, scope_id:selected.scope_id, user_confirmed:true, reason:"用户在正文页撤回确认" });
    if (stage === "outline") { outlineStatus.value = "waiting_confirmation"; await persistOutlineState(project); }
    else if (stage === "script") { scriptStatus.value = "waiting_confirmation"; await persistScriptState(project); }
    else { storyboardStatus.value = "waiting_confirmation"; await persistStoryboardState(project); }
    notify("确认已撤回，当前批次进入待复审");
  } catch (error) { notify(error instanceof Error ? error.message : "撤回确认失败"); }
}
const projectLoadIsolation = createProjectLoadIsolation();
const {
  characterProfiles, sceneProfiles, propProfiles, assetStatus, assetError,
  shotImages, shotImageStatus, shotImageError, shotVideos, shotVideoStatus, shotVideoError,
  episodeMasters, mergeStatus, mergeError, episodeAudits, finalAuditStatus, finalAuditError,
  enhancedEpisodes, upscaleStatus, upscaleError, exportFiles, exportManifestUrl, exportStatus, exportError,
} = toRefs(appRuntime.assetStore.state);
type WorkflowTimingRecord = { started_at:number; elapsed_seconds:number; running:boolean };
const workflowTimingStorageKey = "yingxu:workflow-real-timings:v2";
const workflowTimings = ref<Record<string, WorkflowTimingRecord>>((() => {
  try { return JSON.parse(window.localStorage.getItem(workflowTimingStorageKey) || "{}"); }
  catch { return {}; }
})());
const workflowTimingNow = ref(Date.now());
let workflowTimingTimer = window.setInterval(() => { workflowTimingNow.value = Date.now(); }, 1000);
function workflowTimingKey(stage:WorkflowNavigation) { return `${activeProjectRecord.value?.id || "none"}:${stage}`; }
function setWorkflowRunning(stage:WorkflowNavigation, running:boolean) {
  const key = workflowTimingKey(stage);
  const current = workflowTimings.value[key] || { started_at:0, elapsed_seconds:0, running:false };
  if (running && !current.running) workflowTimings.value[key] = { started_at:Date.now(), elapsed_seconds:current.elapsed_seconds, running:true };
  else if (!running && current.running) workflowTimings.value[key] = { started_at:0, elapsed_seconds:current.elapsed_seconds + Math.max(0, Math.floor((Date.now() - current.started_at) / 1000)), running:false };
  else return;
  window.localStorage.setItem(workflowTimingStorageKey, JSON.stringify(workflowTimings.value));
}
const workflowElapsedSeconds = computed(() => {
  const timing = workflowTimings.value[workflowTimingKey(activeWorkflowNavigation.value)];
  if (!timing) return 0;
  return timing.elapsed_seconds + (timing.running ? Math.max(0, Math.floor((workflowTimingNow.value - timing.started_at) / 1000)) : 0);
});
watch(
  [() => activeProjectRecord.value?.id, outlineStatus, scriptStatus, storyboardStatus, assetStatus, shotImageStatus, shotVideoStatus, mergeStatus, exportStatus],
  ([, outline, script, storyboard, assets, shotImagesState, shotVideosState, merged, exported]) => {
    setWorkflowRunning("大纲", outline === "generating");
    setWorkflowRunning("剧本", script === "generating");
    setWorkflowRunning("分镜脚本", storyboard === "generating");
    setWorkflowRunning("资产", assets === "generating");
    setWorkflowRunning("分镜画面", shotImagesState === "generating");
    setWorkflowRunning("分镜视频", shotVideosState === "generating");
    setWorkflowRunning("成片", merged === "generating");
    setWorkflowRunning("导出", exported === "generating");
  },
  { immediate:true },
);
type AssetCategory = "人物" | "道具" | "场景";
const activeAssetCategory = ref<AssetCategory>("人物");
const visibleAssetGroups = computed(() => activeAssetCategory.value === "人物"
  ? [{ title:"人物", kind:"character" as const, items:characterProfiles.value }]
  : activeAssetCategory.value === "道具"
    ? [{ title:"道具", kind:"prop" as const, items:propProfiles.value }]
    : [{ title:"场景", kind:"scene" as const, items:sceneProfiles.value }]);
const assetController = ref<AbortController>();
const assetBatchController = ref<AbortController>();
let assetBatchFlight:Promise<void> | undefined;
let assetBatchFlightKey = "";
const assetVariantControllers = new Map<string, AbortController>();
const characterViewContract = "character-front-baseline-left-right-side-back-half-v3";
const assetBatchGenerating = ref(false);
const assetBatchPaused = ref(false);
const activeAssetGenerationKey = ref("");
let activeAssetBatchToken = "";
let assetBatchEpoch = 0;
function reclaimAssetBatchProjection(flight:Promise<void> | undefined, controller:AbortController | undefined, token:string) {
  if (assetBatchFlight !== flight || assetBatchController.value !== controller || activeAssetBatchToken !== token) return false;
  controller?.abort();
  assetBatchFlight = undefined; assetBatchFlightKey = ""; assetBatchController.value = undefined; activeAssetBatchToken = "";
  assetBatchGenerating.value = false; assetBatchPaused.value = false; activeAssetGenerationKey.value = "";
  if (assetStatus.value === "generating") assetStatus.value = "pending";
  for (const item of allAssetProfiles.value) if (item.status === "generating") item.status = item.image_url ? "waiting_confirmation" : "pending";
  return true;
}
const assetSourceEpisodes = ref<number[]>([]);
const allAssetProfiles = computed(() => [...characterProfiles.value, ...propProfiles.value, ...sceneProfiles.value]);
const assetStageError = computed(() => {
  const message = String(assetError.value || "").trim();
  if (!message) return "";
  return allAssetProfiles.value.some(item => message.startsWith(`${item.name}：`)) ? "" : message;
});
const generatedAssetCount = computed(() => allAssetProfiles.value.filter(item => Boolean(item.image_url)).length);
const assetImagesRunning = computed(() => assetStatus.value === "generating" || assetBatchGenerating.value || allAssetProfiles.value.some(item => item.status === "generating"));
const assetImageActionLabel = computed(() => generatedAssetCount.value === 0 ? "生成图片" : "继续生成图片");
const assetGenerationReady = computed(() => storyboardHasCompleteEpisode.value || allAssetProfiles.value.length > 0);
const shotImageController = ref<AbortController>();
let shotImageRefreshTimer = 0;
const shotVideoController = ref<AbortController>();
const mergeController = ref<AbortController>();
const finalAuditController = ref<AbortController>();
const exportController = ref<AbortController>();
const upscaleController = ref<AbortController>();
let upscaleFlight:Promise<void> | undefined;
let upscaleFlightKey = "";
let upscaleFlightEpoch = 0;
let exportFlight:Promise<void> | undefined;
let exportFlightProjectId = "";
let exportFlightEpoch = 0;
const workflowReadStorageKey = "drama-pipeline:workflow-completion-read:v1";
const workflowReadSignatures = ref<Record<string, Partial<Record<WorkflowNavigation, string>>>>((() => {
  try { return JSON.parse(window.localStorage.getItem(workflowReadStorageKey) || "{}"); }
  catch { return {}; }
})());
const workflowCompletionSignatures = computed<Record<WorkflowNavigation, string>>(() => {
  const total = activeProjectRecord.value?.episode_count || 0;
  const reviewed = (status:string) => status === "waiting_confirmation" || status === "confirmed";
  const auditKey = (audits:OutlineAudit[]) => audits.map(audit => `${audit.status}:${audit.summary}`).join("|");
  return {
    大纲:total > 0 && outlineEpisodes.value.length >= total && reviewed(outlineStatus.value) && (!narrativeAuditEnabled.value || outlineAudit.value?.status === "pass") ? `${outlineEpisodes.value.length}:${outlineAudit.value?.summary || "audit-disabled"}` : "",
    剧本:total > 0 && scripts.value.length >= total && reviewed(scriptStatus.value) && (!narrativeAuditEnabled.value || narrativeAuditsPassed(scriptAudits.value)) ? `${scripts.value.length}:${auditKey(scriptAudits.value) || "audit-disabled"}` : "",
    分镜脚本:total > 0 && new Set(storyboardShots.value.map(shot => shot.episode)).size >= total && reviewed(storyboardStatus.value) && (!narrativeAuditEnabled.value || narrativeAuditsPassed(storyboardAudits.value)) ? `${total}:${auditKey(storyboardAudits.value) || "audit-disabled"}` : "",
    资产:reviewed(assetStatus.value) ? `${characterProfiles.value.length}:${sceneProfiles.value.length}:${propProfiles.value.length}` : "",
    分镜画面:reviewed(shotImageStatus.value) ? `${shotImages.value.filter(item => item.image_url).length}` : "",
    分镜视频:reviewed(shotVideoStatus.value) ? `${shotVideos.value.filter(item => item.video_url).length}` : "",
    成片:reviewed(finalAuditStatus.value) ? `${episodeAudits.value.length}:${finalAuditStatus.value}` : "",
    导出:exportStatus.value === "confirmed" ? `${exportFiles.value.length}:${exportManifestUrl.value}` : "",
  };
});
const workflowUnread = computed(() => {
  const projectId = activeProjectRecord.value?.id;
  const read = projectId ? workflowReadSignatures.value[projectId] || {} : {};
  return Object.fromEntries(workflowNavigation.map(kind => [kind,
    kind !== activeWorkflowNavigation.value
      && Boolean(workflowCompletionSignatures.value[kind])
      && read[kind] !== workflowCompletionSignatures.value[kind],
  ])) as Record<WorkflowNavigation, boolean>;
});

function markWorkflowCompletionRead(kind:WorkflowNavigation) {
  const projectId = activeProjectRecord.value?.id;
  const signature = workflowCompletionSignatures.value[kind];
  if (!projectId || !signature || workflowReadSignatures.value[projectId]?.[kind] === signature) return;
  workflowReadSignatures.value = {
    ...workflowReadSignatures.value,
    [projectId]:{ ...workflowReadSignatures.value[projectId], [kind]:signature },
  };
  window.localStorage.setItem(workflowReadStorageKey, JSON.stringify(workflowReadSignatures.value));
}

watch([workflowCompletionSignatures, activeWorkflowNavigation, activeProjectRecord], () => {
  markWorkflowCompletionRead(activeWorkflowNavigation.value);
}, { deep:true, immediate:true });

function runtimeProductionStatus(status:string):ProductionStatus {
  if (status === "generating") return "running";
  if (status === "waiting_confirmation") return "pending_confirmation";
  if (status === "confirmed") return "completed";
  if (status === "failed") return "failed";
  if (status === "skipped") return "skipped";
  return "idle";
}

function ledgerLifecycle(status:string):ProductionLifecycle {
  if (status === "generating") return "running";
  if (status === "waiting_confirmation") return "pending_confirmation";
  if (status === "confirmed") return "completed";
  if (status === "failed") return "failed";
  if (status === "skipped") return "skipped";
  return "idle";
}

function productionRecordFromLedger(record:LedgerScopeRecord):ProductionScopeRecord {
  const status:ProductionStatus = record.lifecycle === "pending_confirmation" ? "pending_confirmation"
    : record.lifecycle === "completed" ? "completed" : record.lifecycle === "running" ? "running"
      : record.lifecycle === "queued" ? "queued" : record.lifecycle === "paused" ? "paused"
        : record.lifecycle === "failed" ? "failed" : record.lifecycle === "stale" ? "stale"
          : record.lifecycle === "skipped" ? "skipped" : record.lifecycle === "cancelled" ? "cancelled" : "idle";
  return {
    project_id:record.project_id, stage:record.stage as ProductionStage, scope_type:record.scope_type,
    scope_id:record.scope_id, content_fingerprint:record.content_fingerprint, audit_batch_id:record.audit_batch_id,
    status, completed_count:record.progress.completed, total_count:record.progress.total,
    confirmation_scope:record.confirmation_scope, impact_scope:record.impact_scope.map(item => ({ ...item, stage:item.stage as ProductionStage })),
    checkpoint:record.checkpoint, error:record.error, created_at:record.created_at, updated_at:record.updated_at,
  };
}

function compactFingerprint(value:unknown) {
  const source = JSON.stringify(value) || "";
  let hash = 2166136261;
  for (let index = 0; index < source.length; index += 1) hash = Math.imul(hash ^ source.charCodeAt(index), 16777619);
  return `fnv1a-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

function finalAuditLedgerEvidence(item:EpisodeAudit) {
  const master = episodeMasters.value.find(value => value.episode === item.episode);
  return { episode:item.episode, status:item.status, issues:item.issues, attempts:item.attempts, confirmed:item.confirmed, audited_path:master?.path || master?.video_url || "", production_evidence:master?.production_evidence || "" };
}

let productionLedgerSaveTimer = 0;
function scheduleProductionLedgerSync() {
  window.clearTimeout(productionLedgerSaveTimer);
  const project = activeProjectRecord.value;
  if (!project) return;
  productionLedgerSaveTimer = window.setTimeout(() => { void syncProductionLedger(project); }, 350);
}

async function syncProductionLedger(project:StoredProject) {
  if (activeProjectRecord.value?.id !== project.id) return;
  const identity = { ...projectIdentity, project_id:project.id };
  const records:Array<{ stage:string; scope_type:ProductionScopeType; scope_id:string; lifecycle:ProductionLifecycle; stage_substate:string; content_fingerprint?:string; audit_batch_id?:string; progress:{ completed:number; total:number }; confirmation_scope:{ scope_type:ProductionScopeType; scope_ids:string[] }; impact_scope:Array<{ stage:string; scope_type:ProductionScopeType; scope_id:string }>; checkpoint:string; error:string }> = [];
  const add = (stage:string, scopeType:ProductionScopeType, scopeId:string, status:string, content:unknown, audit:unknown, progress:{ completed:number; total:number }, error = "", substate = "", confirmationScope = { scope_type:scopeType, scope_ids:[scopeId] } as { scope_type:ProductionScopeType; scope_ids:string[] }) => records.push({
    stage, scope_type:scopeType, scope_id:scopeId, lifecycle:ledgerLifecycle(status), stage_substate:substate,
    content_fingerprint:compactFingerprint(content), audit_batch_id:compactFingerprint(audit), progress,
    confirmation_scope:confirmationScope, impact_scope:[{ stage, scope_type:scopeType, scope_id:scopeId }], checkpoint:"", error,
  });
  add("requirements", "project", project.id, "confirmed", stableProjectRequirements(project), "project-requirements", { completed:1, total:1 });
  add("outline", "project", project.id, outlineStatus.value, { plan:outlinePlan.value, episodes:outlineEpisodes.value }, outlineAudit.value, { completed:outlineEpisodes.value.length, total:project.episode_count }, outlineError.value, outlinePhase.value);
  for (const episode of outlineEpisodes.value) add("outline", "episode", String(episode.episode), outlineStatus.value, episode, outlineAudit.value, { completed:1, total:1 }, outlineError.value, outlinePhase.value);
  const storyArcBatches = createStoryArcBatches(outlinePlan.value?.arcs || [], project.episode_count);
  const storyArcIndex = (episode:number, auditCount:number) => Math.min(Math.max(0, storyArcBatches.findIndex(batch => batch.episodes.includes(episode))), Math.max(0, auditCount - 1));
  const storyArcAudit = (audits:OutlineAudit[], episode:number) => {
    const batch = storyArcBatches.find(item => item.episodes.includes(episode));
    return [...audits].reverse().find((audit:OutlineAudit) => audit.batch_id === batch?.id && audit.phase === "final") || audits[storyArcIndex(episode, audits.length)] || null;
  };
  for (const script of scripts.value) add("script", "episode", String(script.episode), scriptStatus.value === "confirmed" ? "confirmed" : scriptStatus.value, script, storyArcAudit(scriptAudits.value, script.episode), { completed:1, total:1 }, scriptError.value, scriptPhase.value);
  for (const script of scripts.value) script.content.split(/\r?\n/).forEach((line, index) => { if (line.trim()) add("script", "line", `${script.episode}:${index + 1}`, scriptStatus.value, line, storyArcAudit(scriptAudits.value, script.episode), { completed:1, total:1 }, scriptError.value, scriptPhase.value); });
  for (const episode of new Set(storyboardShots.value.map(shot => shot.episode))) add("storyboard", "episode", String(episode), storyboardStatus.value, storyboardShots.value.filter(shot => shot.episode === episode), storyArcAudit(storyboardAudits.value, episode), { completed:1, total:1 }, storyboardError.value);
  for (const shot of storyboardShots.value) add("storyboard", "shot", `${shot.episode}:${shot.shot_number}`, storyboardStatus.value, shot, storyArcAudit(storyboardAudits.value, shot.episode), { completed:1, total:1 }, storyboardError.value);
  for (const batch of storyArcBatches) {
    const batchScripts = scripts.value.filter(script => batch.episodes.includes(script.episode));
    const batchShots = storyboardShots.value.filter(shot => batch.episodes.includes(shot.episode));
    if (batchScripts.length) add("script", "story_arc_batch", batch.id, scriptStatus.value, batchScripts, scriptAudits.value, { completed:batchScripts.length, total:batch.episodes.length }, scriptError.value, scriptPhase.value, { scope_type:"episode", scope_ids:batch.episodes.map(String) });
    if (batchShots.length) add("storyboard", "story_arc_batch", batch.id, storyboardStatus.value, batchShots, storyboardAudits.value, { completed:new Set(batchShots.map(shot => shot.episode)).size, total:batch.episodes.length }, storyboardError.value, "", { scope_type:"episode", scope_ids:batch.episodes.map(String) });
  }
  for (const item of characterProfiles.value) add("assets", "asset", `character:${item.name}`, item.status || "pending", item, item.status || "", { completed:item.status === "confirmed" ? 1 : 0, total:1 }, item.error || "");
  for (const item of sceneProfiles.value) add("assets", "asset", `scene:${item.name}`, item.status || "pending", item, item.status || "", { completed:item.status === "confirmed" ? 1 : 0, total:1 }, item.error || "");
  for (const item of propProfiles.value) add("assets", "asset", `prop:${item.name}`, item.status || "pending", item, item.status || "", { completed:item.status === "confirmed" ? 1 : 0, total:1 }, item.error || "");
  for (const item of shotImages.value) add("image", "shot", `${item.episode}:${item.shot_number}`, item.status, item.image_url || item, item.audit_summary || "", { completed:item.status === "confirmed" ? 1 : 0, total:1 }, item.error || "");
  const mediaPackageBatch = (item:ShotVideoItem) => `shot-media:${item.episode}:${item.shot_number}:${compactFingerprint({ source_video:item.source_video_url || "", video:item.video_url || "", audio:item.audio_url || "not_applicable", voice:item.voice_cast_version || "not_applicable", lipsync:item.lip_sync_version || "not_applicable", subtitle:item.subtitle_status || "pending" })}`;
  for (const item of shotVideos.value) add("video", "shot", `${item.episode}:${item.shot_number}`, item.status, item.video_url || item, mediaPackageBatch(item), { completed:item.status === "confirmed" ? 1 : 0, total:1 }, item.error || "");
  for (const item of shotVideos.value) add("audio", "shot", `${item.episode}:${item.shot_number}`, item.voice_status === "completed" || item.voice_status === "not_applicable" ? "completed" : item.voice_status === "failed" ? "failed" : item.status, item.audio_url || item, mediaPackageBatch(item), { completed:item.voice_status === "completed" || item.voice_status === "not_applicable" ? 1 : 0, total:1 }, item.voice_status === "failed" ? item.error || "配音失败" : "");
  for (const item of shotVideos.value) add("subtitle", "shot", `${item.episode}:${item.shot_number}`, item.subtitle_status === "completed" || item.subtitle_status === "not_applicable" ? "completed" : item.subtitle_status === "failed" ? "failed" : item.status, item.subtitle_status || item, mediaPackageBatch(item), { completed:item.subtitle_status === "completed" || item.subtitle_status === "not_applicable" ? 1 : 0, total:1 }, item.subtitle_status === "failed" ? item.error || "字幕失败" : "");
  for (const item of episodeMasters.value) add("composition", "episode", String(item.episode), item.status, item.path || item.video_url || item, "merge-audit", { completed:item.status === "confirmed" ? 1 : 0, total:1 }, mergeError.value);
  for (const item of episodeAudits.value) { const evidence = finalAuditLedgerEvidence(item); add("review_export", "episode", `review:${item.episode}`, item.confirmed ? "confirmed" : item.status === "pass" ? "waiting_confirmation" : "failed", evidence, evidence, { completed:item.confirmed ? 1 : 0, total:1 }, item.status === "pass" ? "" : item.issues.join("；"), "review"); }
  for (const item of enhancedEpisodes.value) {
    records.push({
      stage:"review_export", scope_type:"episode", scope_id:`upscale:${item.episode}`,
      lifecycle:ledgerLifecycle(item.status), stage_substate:"upscale",
      progress:{ completed:["confirmed", "skipped"].includes(item.status) ? 1 : 0, total:1 },
      confirmation_scope:{ scope_type:"episode", scope_ids:[`upscale:${item.episode}`] }, impact_scope:[],
      checkpoint:"", error:upscaleError.value,
    });
  }
  for (const item of exportFiles.value) add("review_export", "episode", `export:${item.episode}`, exportStatus.value, item.path, exportManifestUrl.value, { completed:exportStatus.value === "confirmed" ? 1 : 0, total:1 }, exportError.value, "export");
  for (const batch of createEpisodeBatches(project.episode_count)) {
    const masters = episodeMasters.value.filter(item => batch.episodes.includes(item.episode));
    const audits = episodeAudits.value.filter(item => batch.episodes.includes(item.episode));
    if (masters.length) add("composition", "episode_batch", batch.id, mergeStatus.value, masters, "merge-batch", { completed:masters.filter(item => item.status === "confirmed").length, total:batch.episodes.length }, mergeError.value, "", { scope_type:"episode", scope_ids:batch.episodes.map(String) });
    if (audits.length) add("review_export", "episode_batch", `review:${batch.id}`, finalAuditStatus.value, audits, audits, { completed:audits.filter(item => item.confirmed).length, total:batch.episodes.length }, finalAuditError.value, "review", { scope_type:"episode", scope_ids:batch.episodes.map(episode => `review:${episode}`) });
  }
  const addImpact = (sourceStage:string, sourceType:ProductionScopeType, sourceId:string, targetStage:string, targetType:ProductionScopeType, targetId:string) => {
    const source = records.find(record => record.stage === sourceStage && record.scope_type === sourceType && record.scope_id === sourceId);
    if (source && !source.impact_scope.some(item => item.stage === targetStage && item.scope_type === targetType && item.scope_id === targetId)) source.impact_scope.push({ stage:targetStage, scope_type:targetType, scope_id:targetId });
  };
  for (const episode of outlineEpisodes.value) addImpact("outline", "project", project.id, "outline", "episode", String(episode.episode));
  for (const script of scripts.value) addImpact("outline", "episode", String(script.episode), "script", "episode", String(script.episode));
  for (const script of scripts.value) script.content.split(/\r?\n/).forEach((line, index) => { if (line.trim()) addImpact("script", "line", `${script.episode}:${index + 1}`, "storyboard", "episode", String(script.episode)); });
  for (const episode of new Set(storyboardShots.value.map(shot => shot.episode))) addImpact("script", "episode", String(episode), "storyboard", "episode", String(episode));
  for (const shot of storyboardShots.value) addImpact("storyboard", "episode", String(shot.episode), "image", "shot", `${shot.episode}:${shot.shot_number}`);
  for (const shot of storyboardShots.value) addImpact("storyboard", "shot", `${shot.episode}:${shot.shot_number}`, "image", "shot", `${shot.episode}:${shot.shot_number}`);
  for (const item of shotVideos.value) addImpact("image", "shot", `${item.episode}:${item.shot_number}`, "video", "shot", `${item.episode}:${item.shot_number}`);
  for (const episode of new Set(shotVideos.value.map(item => item.episode))) {
    for (const item of shotVideos.value.filter(video => video.episode === episode)) {
      const shotId = `${item.episode}:${item.shot_number}`;
      addImpact("video", "shot", shotId, "audio", "shot", shotId);
      addImpact("audio", "shot", shotId, "subtitle", "shot", shotId);
      addImpact("subtitle", "shot", shotId, "composition", "episode", String(episode));
    }
    addImpact("composition", "episode", String(episode), "review_export", "episode", `review:${episode}`);
    addImpact("review_export", "episode", `review:${episode}`, "review_export", "episode", `upscale:${episode}`);
    addImpact("review_export", "episode", `upscale:${episode}`, "review_export", "episode", `export:${episode}`);
  }
  try {
    const saved = await productionLedgerService.upsertMany(records.map(record => ({ ...identity, ...record })), true);
    const desiredConfirmations = new Set(records.filter(record => record.lifecycle === "completed").map(record => `${record.stage}:${record.scope_type}:${record.scope_id}`));
    const savedRecords = Array.isArray(saved.records) ? saved.records : [];
    const confirmed = savedRecords.filter(record => record.lifecycle === "pending_confirmation" && desiredConfirmations.has(`${record.stage}:${record.scope_type}:${record.scope_id}`) && !record.confirmation);
    const batchRecords = confirmed.filter(record => ["story_arc_batch", "episode_batch"].includes(record.scope_type));
    const coveredEpisodes = new Set(batchRecords.flatMap(record => (record.confirmation_scope?.scope_ids || []).map(scopeId => `${record.stage}:episode:${scopeId}`)));
    for (const record of [...batchRecords, ...confirmed.filter(record => !coveredEpisodes.has(`${record.stage}:${record.scope_type}:${record.scope_id}`) && !batchRecords.includes(record))]) {
      await productionLedgerService.confirm({ ...identity, stage:record.stage, scope_type:record.scope_type, scope_id:record.scope_id });
    }
    const dependencies:Array<{ source:{ stage:string; scope_type:ProductionScopeType; scope_id:string }; target:{ stage:string; scope_type:ProductionScopeType; scope_id:string } }> = [];
    const edge = (source:{ stage:string; scope_type:ProductionScopeType; scope_id:string }, target:{ stage:string; scope_type:ProductionScopeType; scope_id:string }) => {
      const exists = (key:{ stage:string; scope_type:ProductionScopeType; scope_id:string }) => records.some(record => record.stage === key.stage && record.scope_type === key.scope_type && record.scope_id === key.scope_id);
      if (exists(source) && exists(target)) dependencies.push({ source, target });
    };
    edge({ stage:"requirements", scope_type:"project", scope_id:project.id }, { stage:"outline", scope_type:"project", scope_id:project.id });
    for (const episode of outlineEpisodes.value) edge({ stage:"outline", scope_type:"project", scope_id:project.id }, { stage:"outline", scope_type:"episode", scope_id:String(episode.episode) });
    for (const script of scripts.value) edge({ stage:"outline", scope_type:"episode", scope_id:String(script.episode) }, { stage:"script", scope_type:"episode", scope_id:String(script.episode) });
    for (const script of scripts.value) script.content.split(/\r?\n/).forEach((line, index) => { if (line.trim()) edge({ stage:"script", scope_type:"line", scope_id:`${script.episode}:${index + 1}` }, { stage:"storyboard", scope_type:"episode", scope_id:String(script.episode) }); });
    for (const episode of new Set(storyboardShots.value.map(shot => shot.episode))) edge({ stage:"script", scope_type:"episode", scope_id:String(episode) }, { stage:"storyboard", scope_type:"episode", scope_id:String(episode) });
    for (const shot of storyboardShots.value) edge({ stage:"storyboard", scope_type:"shot", scope_id:`${shot.episode}:${shot.shot_number}` }, { stage:"image", scope_type:"shot", scope_id:`${shot.episode}:${shot.shot_number}` });
    for (const item of shotVideos.value) edge({ stage:"image", scope_type:"shot", scope_id:`${item.episode}:${item.shot_number}` }, { stage:"video", scope_type:"shot", scope_id:`${item.episode}:${item.shot_number}` });
    for (const episode of new Set(shotVideos.value.map(item => item.episode))) {
      for (const item of shotVideos.value.filter(video => video.episode === episode)) {
        const shotId = `${item.episode}:${item.shot_number}`;
        edge({ stage:"video", scope_type:"shot", scope_id:shotId }, { stage:"audio", scope_type:"shot", scope_id:shotId });
        edge({ stage:"audio", scope_type:"shot", scope_id:shotId }, { stage:"subtitle", scope_type:"shot", scope_id:shotId });
        edge({ stage:"subtitle", scope_type:"shot", scope_id:shotId }, { stage:"composition", scope_type:"episode", scope_id:String(episode) });
      }
      edge({ stage:"composition", scope_type:"episode", scope_id:String(episode) }, { stage:"review_export", scope_type:"episode", scope_id:`review:${episode}` });
      edge({ stage:"review_export", scope_type:"episode", scope_id:`review:${episode}` }, { stage:"review_export", scope_type:"episode", scope_id:`upscale:${episode}` });
      edge({ stage:"review_export", scope_type:"episode", scope_id:`upscale:${episode}` }, { stage:"review_export", scope_type:"episode", scope_id:`export:${episode}` });
    }
    if (dependencies.length) await productionLedgerService.dependencies(dependencies.map(dependency => ({ ...identity, ...dependency })));
    const authoritative = await productionLedgerService.list(identity);
    if (activeProjectRecord.value?.id === project.id) appRuntime.productionStore.replaceSnapshot((Array.isArray(authoritative.records) ? authoritative.records : []).map(productionRecordFromLedger));
  } catch (error) { console.error("[生产范围状态同步失败]", error); }
}

watch([outlineStatus, scriptStatus, storyboardStatus, assetStatus, shotImageStatus, shotVideoStatus, mergeStatus, finalAuditStatus, upscaleStatus, exportStatus, activeProjectRecord], () => {
  const project = activeProjectRecord.value;
  if (!project) return appRuntime.productionStore.replaceSnapshot([]);
  const updatedAt = new Date().toISOString();
  const stages:Array<[ProductionStage, string]> = [
    ["requirements", "confirmed"], ["outline", outlineStatus.value], ["script", scriptStatus.value], ["storyboard", storyboardStatus.value],
    ["assets", assetStatus.value], ["image", shotImageStatus.value], ["video", shotVideoStatus.value],
    ["audio", shotVideoStatus.value], ["subtitle", shotVideoStatus.value], ["composition", mergeStatus.value], ["review_export", exportStatus.value],
  ];
  appRuntime.productionStore.replaceSnapshot(stages.map(([stage, status]):ProductionScopeRecord => ({
    project_id:project.id, stage, scope_type:"project", scope_id:project.id,
    content_fingerprint:"", audit_batch_id:"", status:runtimeProductionStatus(status),
    completed_count:runtimeProductionStatus(status) === "completed" ? 1 : 0, total_count:1,
    confirmation_scope:{ scope_type:"project", scope_ids:[project.id] }, impact_scope:[],
    checkpoint:"", error:"", created_at:updatedAt, updated_at:updatedAt,
  })));
}, { immediate:true });

watch([outlinePlan, outlineEpisodes, outlineStatus, outlineAudit, scripts, scriptStatus, scriptAudits, storyboardShots, storyboardStatus, storyboardAudits, characterProfiles, sceneProfiles, propProfiles, shotImages, shotVideos, episodeMasters, episodeAudits, enhancedEpisodes, exportFiles, exportStatus, activeProjectRecord], scheduleProductionLedgerSync, { deep:true });

function abortProjectWork() {
  const interruptedProject = activeProjectRecord.value;
  const interruptedOutlineGenerationId = outlineGenerationId.value;
  const interruptedGenerationId = scriptGenerationId.value;
  if (interruptedProject && outlineStatus.value === "generating") {
    outlineStatus.value = "failed";
    outlinePhase.value = "";
    outlineError.value = "项目切换或页面关闭，大纲任务已回收；可继续生成";
    outlineGenerationId.value = "";
    void Promise.allSettled([
      persistOutlineState(interruptedProject),
      narrativeService.stop("outline", { ...productionTaskContext(interruptedProject), client_generation_id:interruptedOutlineGenerationId }),
    ]);
  }
  if (interruptedProject && scriptStatus.value === "generating") {
    scriptStatus.value = "failed";
    scriptPhase.value = "";
    scriptError.value = "项目切换或页面关闭，剧本任务已回收；可从缺失集数继续生成";
    scriptGenerationId.value = "";
    scriptGenerationStartedAt.value = 0;
    scriptHeartbeatAt.value = 0;
    if (scriptHeartbeatTimer) window.clearInterval(scriptHeartbeatTimer);
    scriptHeartbeatTimer = undefined;
    void Promise.allSettled([
      persistScriptState(interruptedProject),
      narrativeService.stop("script", { ...productionTaskContext(interruptedProject), client_generation_id:interruptedGenerationId }),
    ]);
  }
  if (interruptedProject && storyboardStatus.value === "generating") {
    storyboardStatus.value = "failed";
    storyboardError.value = "项目切换或页面关闭，分镜任务已回收；可从未完成集数继续生成";
    void Promise.allSettled([
      persistStoryboardState(interruptedProject),
      narrativeService.stop("storyboard", productionTaskContext(interruptedProject)),
    ]);
  }
  projectSession += 1;
  outlineCharactersExpanded.value = false;
  projectLoadIsolation.clear();
  narrativeEditDrafts.value = {};
  resetGenerationTimerState();
  assistantController.value?.abort();
  outlineController.value?.abort();
  scriptController.value?.abort();
  storyboardController.value?.abort();
  assetController.value?.abort();
  assetOperationEpoch += 1;
  queuedAssetOperationOwners.clear();
  queuedAssetOperationCount.value = 0;
  reclaimAssetBatchProjection(assetBatchFlight, assetBatchController.value, activeAssetBatchToken);
  assetBatchEpoch += 1;
  for (const controller of assetVariantControllers.values()) controller.abort();
  assetVariantControllers.clear();
  shotImageController.value?.abort();
  shotVideoController.value?.abort();
  mergeController.value?.abort();
  finalAuditController.value?.abort();
  exportFlightEpoch += 1;
  exportController.value?.abort();
  upscaleController.value?.abort();
  upscaleController.value = undefined;
  upscaleFlightEpoch += 1;
  upscaleFlight = undefined; upscaleFlightKey = "";
  exportController.value = undefined; exportFlight = undefined; exportFlightProjectId = "";
}

function isCurrentProjectSession(projectId:string, session:number) {
  return session === projectSession && activeProjectRecord.value?.id === projectId;
}
const generatedWorkflowEpisodes = computed(() => Array.from({ length: generatedEpisodeCount.value }, (_, index) => index + 1));
const outlineDisplayPlan = computed(() => outlineShowingReviewSnapshot.value ? outlineReviewPlan.value : outlinePlan.value);
const outlineCharactersExpanded = ref(false);
const outlineCoreCharacters = computed(() => (outlineDisplayPlan.value?.characters || []).map(character => ({
  name:String(character.name || "").trim(),
  identity:String(character.identity || character.role || "").trim(),
  personality:String(character.personality || character.arc || character.conflict || "").trim(),
  coreMotivation:String(character.core_motivation || character.goal || "").trim(),
  appearanceCount:Math.max(0, Number(character.appearance_count || 2)),
})).filter(character => character.appearanceCount >= 2 && character.name && character.identity && character.personality && character.coreMotivation));
const outlineDisplayEpisodes = computed(() => outlineShowingReviewSnapshot.value ? outlineReviewEpisodes.value : outlineEpisodes.value);
const outlineVisibleEpisodes = computed(() => workflowEpisode.value === 0 ? outlineDisplayEpisodes.value : outlineDisplayEpisodes.value.filter(episode => episode.episode === workflowEpisode.value));
const visibleScripts = computed(() => workflowEpisode.value === 0 ? scripts.value : scripts.value.filter(script => script.episode === workflowEpisode.value));
const storyboardEpisodeGroups = computed(() => {
  const episodes = [...new Set(storyboardShots.value.map(shot => shot.episode))].sort((a, b) => a - b);
  return episodes
    .filter(episode => workflowEpisode.value === 0 || episode === workflowEpisode.value)
    .map(episode => ({ episode, title:scripts.value.find(script => script.episode === episode)?.title || `第${String(episode).padStart(2, "0")}集`, shots:storyboardShots.value.filter(shot => shot.episode === episode).sort((a, b) => a.shot_number - b.shot_number) }));
});
const visibleShotImages = computed(() => workflowEpisode.value === 0 ? shotImages.value : shotImages.value.filter(item => item.episode === workflowEpisode.value));
const visibleShotVideos = computed(() => workflowEpisode.value === 0 ? shotVideos.value : shotVideos.value.filter(item => item.episode === workflowEpisode.value));
const visibleEpisodeMasters = computed(() => workflowEpisode.value === 0 ? episodeMasters.value : episodeMasters.value.filter(item => item.episode === workflowEpisode.value));
const storyboardReadyForAssets = computed(() => {
  const project = activeProjectRecord.value;
  if (!project) return false;
  return Array.from({ length:project.episode_count }, (_, index) => index + 1).every(episode => {
    const shots = storyboardShots.value.filter(shot => shot.episode === episode);
    const script = scripts.value.find(item => item.episode === episode);
    const targetDuration = script ? scriptTargetDuration(project, script) : episodeTargetDuration(project, episode - 1);
    return shots.length > 0 && !storyboardEpisodeError(shots, targetDuration);
  });
});
const outlineHasCompleteEpisode = computed(() => outlineEpisodes.value.some(episode => episode.title?.trim() && episode.synopsis?.trim()));
const scriptHasCompleteEpisode = computed(() => scripts.value.some(script => script.title?.trim() && humanReadableScriptContent(script.content).trim()));
const completeStoryboardEpisodes = computed(() => {
  const project = activeProjectRecord.value;
  if (!project) return [];
  return [...new Set(storyboardShots.value.map(shot => shot.episode))].filter(episode => {
    const shots = storyboardShots.value.filter(shot => shot.episode === episode);
    const script = scripts.value.find(item => item.episode === episode);
    const duration = script ? scriptTargetDuration(project, script) : episodeTargetDuration(project, episode - 1);
    return shots.length > 0 && !storyboardEpisodeError(shots, duration);
  });
});
const storyboardHasCompleteEpisode = computed(() => completeStoryboardEpisodes.value.length > 0);
function requiredAssetsForEpisode(episode:number) {
  const source = storyboardShots.value.filter(shot => shot.episode === episode)
    .map(shot => `${shot.scene} ${shot.visual} ${shot.action} ${shot.image_prompt}`).join("\n");
  return allAssetProfiles.value.filter(item => source.includes(item.name));
}
function assetUploadComplete(item:CharacterProfile | SceneProfile | PropProfile) {
  if (!item.image_url) return false;
  if (!characterProfiles.value.includes(item as CharacterProfile)) return item.upload_view_mode === "single" || hasCompleteAssetVariants(sceneProfiles.value.includes(item as SceneProfile) ? "scene" : "prop", item);
  if (item.view_contract !== characterViewContract) return false;
  return hasCompleteAssetVariants("character", item);
}
const readyAssetEpisode = computed(() => completeStoryboardEpisodes.value.find(episode => {
  const required = requiredAssetsForEpisode(episode);
  return required.length > 0 && required.every(assetUploadComplete);
}));
const assetsReadyForShotImages = computed(() => readyAssetEpisode.value !== undefined);
const missingAssetsForShotImages = computed(() => {
  const episode = completeStoryboardEpisodes.value[0];
  return episode === undefined ? [] : requiredAssetsForEpisode(episode).filter(item => !assetUploadComplete(item)).map(item => item.name);
});
const readyShotImageEpisode = computed(() => completeStoryboardEpisodes.value.find(episode => {
  const shots = storyboardShots.value.filter(shot => shot.episode === episode);
  return shots.length > 0 && shots.every(shot => shotImages.value.some(item => item.episode === episode && item.shot_number === shot.shot_number && Boolean(item.image_url)));
}));
const shotImagesReadyForVideo = computed(() => readyShotImageEpisode.value !== undefined);
watch(generatedWorkflowEpisodes, episodes => {
  if (workflowEpisode.value !== 0 && episodes.length && !episodes.includes(workflowEpisode.value)) workflowEpisode.value = 0;
});
const outlineEpisodesComplete = computed(() => {
  const total = activeProjectRecord.value?.episode_count || 0;
  return total > 0 && outlineEpisodes.value.length >= total;
});
const outlineTypingComplete = computed(() => outlineEpisodesComplete.value && outlineEpisodes.value.every(episode => {
  const typed = outlineTypedEpisodes.value[episode.episode];
  return typed?.title === episode.title && typed?.synopsis === episode.synopsis;
}));
watch(outlineTypingComplete, (complete) => {
  if (complete) stopGenerationTimer();
});
const workflowHeaderTitle = computed(() => activeWorkflowNavigation.value);
const workflowProgress = computed(() => {
  const totalEpisodes = activeProjectRecord.value?.episode_count || 0;
  if (activeWorkflowNavigation.value === "大纲") return { current:outlineEpisodes.value.length, total:totalEpisodes };
  if (activeWorkflowNavigation.value === "剧本") return { current:scripts.value.length, total:totalEpisodes };
  if (activeWorkflowNavigation.value === "分镜脚本") return { current:new Set(storyboardShots.value.map(item => item.episode)).size, total:totalEpisodes };
  if (activeWorkflowNavigation.value === "资产") {
    const assets = [...characterProfiles.value, ...sceneProfiles.value, ...propProfiles.value];
    return { current:assets.filter(item => item.status === "confirmed").length, total:assets.length };
  }
  if (activeWorkflowNavigation.value === "分镜画面") return { current:shotImages.value.filter(item => item.image_url).length, total:storyboardShots.value.length };
  if (activeWorkflowNavigation.value === "分镜视频") return { current:shotVideos.value.filter(item => item.video_url).length, total:storyboardShots.value.length };
  if (activeWorkflowNavigation.value === "成片") return { current:episodeMasters.value.filter(item => item.video_url).length, total:totalEpisodes };
  return { current:exportFiles.value.length, total:totalEpisodes };
});
const lightboxIndex = ref(-1);
const lightboxScale = ref(1);
const lightboxFitScale = ref(1);
const lightboxNaturalSize = ref({ width:0, height:0 });
const lightboxOffset = ref({ x:0, y:0 });
const lightboxDragging = ref(false);
let lightboxDragStart = { x:0, y:0, offsetX:0, offsetY:0 };

function closeFloatingMenus(event: PointerEvent) {
  const target = event.target as Element | null;
  if (!target?.closest(".project-selector")) projectMenuOpen.value = false;
  if (!target?.closest(".sidebar-account")) accountMenuOpen.value = false;
  if (!target?.closest(".episode-selector")) episodeMenuOpen.value = false;
  if (!target?.closest(".resource-selector")) resourceMenuOpen.value = "";
  if (!target?.closest(".model-selector")) modelMenuOpen.value = false;
  if (!target?.closest(".regenerate-popover") && !target?.closest(".image-regenerate")) regenerateTarget.value = undefined;
  if (assetIntroOpen.value && !target?.closest(".asset-intro-panel") && !target?.closest('[aria-label="图片简介"]') && !target?.closest('[aria-label="视频简介"]')) assetIntroOpen.value = "";
}

function blockBackgroundZoom(event: KeyboardEvent) {
  if (lightboxIndex.value < 0) return;
  if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); turnLightbox(event.key === "ArrowLeft" ? -1 : 1); return; }
  if (event.key === "Escape") { event.preventDefault(); lightboxIndex.value = -1; return; }
  if (!(event.ctrlKey || event.metaKey)) return;
  if (!["+", "-", "=", "0"].includes(event.key)) return;
  event.preventDefault();
  if (event.key === "0") resetLightboxZoom();
  else zoomLightbox(event.key === "-" ? -1 : 1);
}

onMounted(async () => {
  document.addEventListener("pointerdown", closeFloatingMenus);
  document.addEventListener("pointerdown", closeLightboxOnDocumentPointer, true);
  document.addEventListener("keydown", blockBackgroundZoom);
  window.addEventListener("resize", syncViewportWidth);
  try {
    await loadLocalLoraStyles();
    const inviteToken = new URLSearchParams(window.location.search).get("invite");
    if (inviteToken) {
      try {
        await assistantService.resolveInvitation(inviteToken);
        await assistantService.redeemInvitation({ token:inviteToken, user_id:projectIdentity.user_id });
        const cleanUrl = new URL(window.location.href); cleanUrl.searchParams.delete("invite"); window.history.replaceState({}, "", cleanUrl);
      } catch (error) { notify(error instanceof Error ? error.message : "邀请链接处理失败"); }
    }
    const result = await projectService.list(projectIdentity, true);
    projectRecords.value = result.projects.filter(project => !project.archived);
    archivedProjects.value = result.projects.filter(project => project.archived);
    projects.value = projectRecords.value.map(project => project.name);
    activeTab.value = projects.value.includes(activeTab.value) ? activeTab.value : projects.value[0] || "";
    appRuntime.projectStore.replace(projectRecords.value, projectRecords.value.find(project => project.name === activeTab.value)?.id || "");
    isolateChatProject(activeProjectRecord.value);
    if (activeProjectRecord.value) {
      const context = assistantContext(activeProjectRecord.value);
      try {
        const capabilities = await assistantService.capabilities<{ models:Array<{ name:string; selected:boolean }> }>();
        selectedAssistantModel.value = capabilities.models.find(model => model.selected)?.name || capabilities.models[0]?.name || "";
        await assistantService.sessions({ action:"create", session_id:assistantSessionId, context });
      } catch (error) { notify(error instanceof Error ? error.message : "助手服务暂不可用"); }
    }
    if (activeTab.value) await loadProjectFlowState();
    await Promise.all([loadResources(), loadTasks(), loadProjectVersions()]);
    await nextTick();
    if (chatScroll.value) chatScroll.value.scrollTop = Math.max(0, restoredUiState.chatScrollTop || 0);
  } catch (error) {
    notify(error instanceof Error ? error.message : "项目列表加载失败");
  }
});
onBeforeUnmount(() => {
  window.clearInterval(thinkingTimer);
  window.clearInterval(generationTimer);
  window.clearInterval(workflowTimingTimer);
  workflowTimingTimer = 0;
  window.clearTimeout(chatHistorySaveTimer);
  window.clearTimeout(assistantDraftSaveTimer);
  window.clearTimeout(productionLedgerSaveTimer);
  window.clearInterval(taskRefreshTimer);
  window.clearInterval(localLoraStyleTimer);
  window.cancelAnimationFrame(assetCarouselMomentumFrame);
  cancelAssetCarouselDrag();
  document.removeEventListener("pointerdown", closeFloatingMenus);
  document.removeEventListener("pointerdown", closeLightboxOnDocumentPointer, true);
  document.removeEventListener("keydown", blockBackgroundZoom);
  window.removeEventListener("resize", syncViewportWidth);
  document.documentElement.style.overflow = "";
  document.body.style.overflow = "";
  abortProjectWork();
});
watch(newProjectOpen, open => {
  window.clearInterval(localLoraStyleTimer);
  localLoraStyleTimer = 0;
  if (!open) return;
  void loadLocalLoraStyles().catch(error => notify(error instanceof Error ? error.message : "LoRA 风格索引失败"));
  localLoraStyleTimer = window.setInterval(() => {
    void loadLocalLoraStyles().catch(error => notify(error instanceof Error ? error.message : "LoRA 风格索引失败"));
  }, 2000);
});
watch(leftPanelWidth, (width) => window.localStorage.setItem("yingxu:left-panel-width", String(Math.round(width))));
watch(rightPanelWidth, (width) => window.localStorage.setItem("yingxu:right-panel-width", String(Math.round(width))));
const overlayOpen = computed(() => newProjectOpen.value || Boolean(workspaceDialog.value) || Boolean(accountDialog.value) || lightboxIndex.value >= 0);
watch(overlayOpen, (open) => {
  document.documentElement.style.overflow = open ? "hidden" : "";
  document.body.style.overflow = open ? "hidden" : "";
});
watch(workspaceDialog, dialog => {
  window.clearInterval(taskRefreshTimer);
  taskRefreshTimer = 0;
  if (dialog === "Skill") { void loadProductionCapabilities(); return; }
  if (dialog !== "任务") return;
  void Promise.all([loadTasks(), loadRuntimeTasks(), loadProjectVersions(), loadProductionVersions(), loadProductionWorkflow()]);
  taskRefreshTimer = window.setInterval(() => { void Promise.all([loadTasks(), loadRuntimeTasks()]); }, 2_000);
});
watch([selectedEpisode, workflowEpisode], () => { void loadResources(); });
const chats = ref<ChatItem[]>([]);
const chatCache = createProjectScopedCache<ChatItem>();
const chatProjectId = ref("");
const chatHistoryLoading = ref(false);
let chatHistorySaveTimer = 0;
let assistantDraftSaveTimer = 0;
let restoringChatHistory = false;

function isolateChatProject(project:StoredProject | null) {
  window.clearTimeout(chatHistorySaveTimer);
  window.clearTimeout(assistantDraftSaveTimer);
  restoringChatHistory = true;
  if (chatProjectId.value) {
    composerStateByProject.set(chatProjectId.value, {
      input:input.value,
      uploadedAssets:uploadedAssets.value.filter(asset => asset.scope === "临时参考").map(asset => ({ ...asset })),
      stagedAssets:stagedAssets.value.map(asset => ({ ...asset })),
      lastBatch:lastBatch.value.map(asset => ({ ...asset })),
    });
  }
  const isolatedChats = chatCache.switchProject(chatProjectId.value, chats.value.map(chat => ({ ...chat })), project?.id || "");
  chatProjectId.value = project?.id || "";
  chats.value = isolatedChats;
  const composer = project ? composerStateByProject.get(project.id) : undefined;
  input.value = composer?.input || "";
  uploadedAssets.value = composer?.uploadedAssets.map(asset => ({ ...asset })) || [];
  stagedAssets.value = composer?.stagedAssets.map(asset => ({ ...asset })) || [];
  lastBatch.value = composer?.lastBatch.map(asset => ({ ...asset })) || [];
  chatHistoryLoading.value = Boolean(project);
  queueMicrotask(() => { restoringChatHistory = false; });
}

function assistantContext(project = activeProjectRecord.value) {
  return {
    ...projectIdentity,
    session_id:assistantSessionId,
    scope:"project_chat",
    current_project:project?.id || "",
    selected_episode:selectedEpisode.value || "all",
    selected_resource:selectedNode.value,
    enabled_skills:[...new Set(enabledSkills.value.flatMap(name => skillRobotIds[name] || []))],
    available_resources:storedResources.value.slice(0, 100).map(resource => ({ id:resource.id, name:resource.name, type:resource.kind, scope:resource.scope, episode:resource.episode, metadata:resource.metadata })),
  };
}

async function loadChatHistory(project:StoredProject, session:number) {
  const controller = new AbortController();
  assistantController.value?.abort();
  assistantController.value = controller;
  try {
    const result = await assistantService.history<{ messages:Array<{ role:"user" | "assistant"; content:string; status?:string; media?:UploadAsset[]; created_at?:number; duration_seconds?:number }> }>({
      context:assistantContext(project), page_size:100, legacy_selected_episodes:["all", ...projectEpisodeOptions.value],
    }, controller.signal);
    if (!isCurrentProjectSession(project.id, session)) return;
    restoringChatHistory = true;
    chats.value = (result.messages || []).map(message => ({
      side:message.role === "user" ? "right" : "left",
      text:message.content,
      status:message.status,
      media:message.media,
      createdAt:message.created_at,
      durationSeconds:message.duration_seconds,
      typing:false,
    }));
    chatCache.replace(project.id, chats.value.map(chat => ({ ...chat })));
    const draftResult = await assistantService.draft<{ draft:null | { content:string } }>({ action:"read", context:assistantContext(project) }, controller.signal);
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!input.value && draftResult.draft?.content) input.value = draftResult.draft.content;
    await nextTick();
    if (chatScroll.value) chatScroll.value.scrollTop = chatScroll.value.scrollHeight;
  } catch (error) {
    if (!controller.signal.aborted) notify(error instanceof Error ? error.message : "聊天记录恢复失败");
  } finally {
    restoringChatHistory = false;
    if (isCurrentProjectSession(project.id, session)) chatHistoryLoading.value = false;
    if (assistantController.value === controller) assistantController.value = undefined;
    if (isCurrentProjectSession(project.id, session)) window.setTimeout(() => void resumeUnansweredChat(project, session), 0);
  }
}

async function resumeUnansweredChat(project:StoredProject, session:number) {
  const lastAssistant = chats.value.map(item => item.side).lastIndexOf("left");
  const pending = chats.value.slice(lastAssistant + 1).filter(item => item.side === "right");
  const meaningful = pending.map(item => item.text.trim()).filter(text => text && !/^[？?]+$/u.test(text));
  if (!meaningful.length || !isCurrentProjectSession(project.id, session)) return;
  const startedAt = pending[0]?.createdAt || Date.now();
  await processAssistantMessage(meaningful.join("\n"), [], project, session, startedAt);
}

function persistAssistantDraft() {
  window.clearTimeout(assistantDraftSaveTimer);
  const project = activeProjectRecord.value;
  if (!project || chatProjectId.value !== project.id || chatHistoryLoading.value) return;
  const content = input.value;
  assistantDraftSaveTimer = window.setTimeout(() => {
    void assistantService.draft({ action:"save", content, context:assistantContext(project) }).catch(error => notify(error instanceof Error ? error.message : "草稿保存失败"));
  }, 500);
}

function persistChatHistory() {
  if (restoringChatHistory || chatHistoryLoading.value) return;
  window.clearTimeout(chatHistorySaveTimer);
  const project = activeProjectRecord.value;
  if (!project || chatProjectId.value !== project.id) return;
  chatHistorySaveTimer = window.setTimeout(() => {
    const messages = chats.value.filter(chat => !chat.notice).map(chat => ({
      role:chat.side === "right" ? "user" : "assistant",
      content:chat.text,
      status:chat.status,
      created_at:chat.createdAt,
      duration_seconds:chat.durationSeconds,
      media:chat.media?.filter(asset => !asset.url.startsWith("blob:")).map(asset => ({ ...asset, file:undefined })),
    }));
    void assistantService.saveHistory({ context:assistantContext(project), messages }).catch(error => notify(error instanceof Error ? error.message : "聊天记录保存失败"));
  }, 400);
}

function persistUiState() {
  const state: PersistedUiState = {
    selectedNode:selectedNode.value, selectedEpisode:selectedEpisode.value, activeTab:activeTab.value,
    input:input.value, page:page.value, selectedImage:selectedImage.value,
    rightPanelTitle:rightPanelTitle.value, rightPanelMode:rightPanelMode.value, previewCollapsed:previewCollapsed.value,
    activeWorkflowNavigation:activeWorkflowNavigation.value, workflowEpisode:workflowEpisode.value,
    workflowPersonAsset:workflowPersonAsset.value, workflowPropAsset:workflowPropAsset.value, workflowSceneAsset:workflowSceneAsset.value,
    publicResourcesExpanded:publicResourcesExpanded.value, projectResourcesExpanded:projectResourcesExpanded.value,
    chatScrollTop:chatScroll.value?.scrollTop || restoredUiState.chatScrollTop || 0,
  };
  window.localStorage.setItem(uiStateStorageKey, JSON.stringify(state));
}
watch([
  selectedNode, selectedEpisode, activeTab, input, page, selectedImage, rightPanelTitle, rightPanelMode,
  previewCollapsed, activeWorkflowNavigation, workflowEpisode, workflowPersonAsset, workflowPropAsset,
  workflowSceneAsset, publicResourcesExpanded, projectResourcesExpanded,
], persistUiState, { deep:true });
watch(chats, persistChatHistory, { deep:true });
watch(input, persistAssistantDraft);

watch([outlinePlan, outlineEpisodes, scripts, storyboardShots], () => {
  appRuntime.narrativeStore.replace({
    outlineGeneral:outlinePlan.value?.general_outline || "",
    outlinePlan:outlinePlan.value,
    outlineEpisodes:outlineEpisodes.value,
    scriptSections:scripts.value.map(script => ({ title:script.title, type:`episode-${script.episode}`, content:script.content })),
    storyboardShots:storyboardShots.value,
  });
}, { deep:true, immediate:true });

function startThinkingTimer() {
  window.clearInterval(thinkingTimer);
  thinkingElapsedSeconds.value = 0;
  thinkingTimer = window.setInterval(() => { thinkingElapsedSeconds.value += 1; }, 1000);
}

function stopThinkingTimer() {
  window.clearInterval(thinkingTimer);
  thinkingTimer = 0;
}

async function pushAssistantTyped(text: string, durationSeconds: number) {
  chats.value.push({ side:"left", text:"", createdAt:Date.now(), durationSeconds, typing:true });
  const target = chats.value[chats.value.length - 1];
  const characters = Array.from(text);
  for (let index = 0; index < characters.length; index += 1) {
    target.text += characters[index];
    if (index % 8 === 0) await scrollChat();
    await new Promise<void>(resolve => window.setTimeout(resolve, 14));
  }
  target.typing = false;
  await scrollChat();
}

const treeGroups = [
  ["人物定妆公共"],
  ["场景公共", "姿态管理"],
  ["姿态管理", "特效素材"],
];
const episodeNodes = [
  ["剧本", "分镜"],
  ["定妆素材", "定妆素材"],
  ["场景素材", "生图输出"],
  ["分镜视频", "合成视频"],
  ["合成视频", "本集日志"],
  ["本集日志"],
];
const hiddenAssetIds = ref<string[]>([]);
const allPreviewAssets = computed(() => uploadedAssets.value.filter((asset) => !hiddenAssetIds.value.includes(asset.id)));
const visibleImages = computed(() => allPreviewAssets.value.slice(0, page.value === 1 ? 10 : 7));
const generatedPreviewAssets = computed<UploadAsset[]>(() => [
  ...[...characterProfiles.value, ...sceneProfiles.value, ...propProfiles.value].flatMap(item => [
    ...(item.image_url ? [{ id:`asset:${item.name}`, name:item.name, url:item.image_url, mediaType:"image" as const, scope:"全局公共" as const, label:item.name }] : []),
    ...(item.detail_assets || []).filter(variant => variant.image_url).map(variant => ({ id:`asset:${item.name}:${variant.id}`, name:`${item.name}${variant.label}`, url:variant.image_url!, mediaType:"image" as const, scope:"全局公共" as const, label:variant.label })),
    ...(item.model3d_result?.renders || []).map(render => ({ id:`asset:${item.name}:3d:${render.label}`, name:`${item.name}3D${render.label}`, url:render.url, mediaType:"image" as const, scope:"全局公共" as const, label:`3D ${render.label}` })),
  ]),
  ...shotImages.value.filter(item => item.image_url).map(item => ({ id:`shot:${item.episode}:${item.shot_number}`, name:`第${item.episode}集镜头${item.shot_number}`, url:item.image_url!, mediaType:"image" as const, scope:"本集私有" as const, label:`镜头${item.shot_number}` })),
  ...shotVideos.value.filter(item => item.video_url).map(item => ({ id:`shot-video:${item.episode}:${item.shot_number}`, name:`第${item.episode}集镜头${item.shot_number}视频`, url:item.video_url!, mediaType:"video" as const, scope:"本集私有" as const, label:`镜头${item.shot_number}视频` })),
  ...episodeMasters.value.filter(item => item.video_url).map(item => ({ id:`episode-master:${item.episode}`, name:`第${item.episode}集成片`, url:item.video_url!, mediaType:"video" as const, scope:"本集私有" as const, label:`第${item.episode}集成片` })),
  ...enhancedEpisodes.value.filter(item => item.video_url).map(item => ({ id:`episode-enhanced:${item.episode}`, name:`第${item.episode}集增强成片`, url:item.video_url!, mediaType:"video" as const, scope:"本集私有" as const, label:`第${item.episode}集增强成片` })),
]);
const chatPreviewAssets = computed<UploadAsset[]>(() => chats.value.flatMap((chat, chatIndex) => (chat.media || []).filter(asset => asset.url).map((asset, mediaIndex) => ({ ...asset, id:`chat:${chatIndex}:${mediaIndex}` }))));
const lightboxAssets = computed(() => {
  const assets = [...generatedPreviewAssets.value, ...allPreviewAssets.value.filter((asset) => asset.id !== "add" && asset.url), ...stagedAssets.value.filter(asset => asset.url), ...chatPreviewAssets.value];
  return assets.filter((asset, index) => assets.findIndex(candidate => candidate.id === asset.id) === index);
});
const lightboxAsset = computed(() => lightboxIndex.value >= 0 ? lightboxAssets.value[lightboxIndex.value] : undefined);

function setLightboxScale(scale: number) {
  lightboxScale.value = Math.min(5, Math.max(0.1, Math.round(scale * 100) / 100));
  if (lightboxScale.value <= lightboxFitScale.value) lightboxOffset.value = { x:0, y:0 };
}

function zoomLightboxByWheel(event: WheelEvent) {
  if (lightboxAsset.value?.mediaType !== "image") return;
  zoomLightbox(event.deltaY < 0 ? 1 : -1);
}

function zoomLightbox(direction:number) {
  const factor = direction > 0 ? 1.2 : 1 / 1.2;
  setLightboxScale(lightboxScale.value * factor);
}

function resetLightboxZoom() {
  lightboxScale.value = lightboxFitScale.value;
  lightboxOffset.value = { x:0, y:0 };
}

function fitLightboxImage(event:Event) {
  const image = event.currentTarget as HTMLImageElement;
  lightboxNaturalSize.value = { width:image.naturalWidth, height:image.naturalHeight };
  const availableWidth = Math.max(1, window.innerWidth - 96);
  const availableHeight = Math.max(1, window.innerHeight - 150);
  lightboxFitScale.value = Math.min(1, availableWidth / image.naturalWidth, availableHeight / image.naturalHeight);
  resetLightboxZoom();
}

function startLightboxDrag(event:PointerEvent) {
  if (lightboxAsset.value?.mediaType !== "image" || lightboxScale.value <= lightboxFitScale.value) return;
  lightboxDragging.value = true;
  lightboxDragStart = { x:event.clientX, y:event.clientY, offsetX:lightboxOffset.value.x, offsetY:lightboxOffset.value.y };
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function moveLightboxDrag(event:PointerEvent) {
  if (!lightboxDragging.value) return;
  lightboxOffset.value = {
    x:lightboxDragStart.offsetX + event.clientX - lightboxDragStart.x,
    y:lightboxDragStart.offsetY + event.clientY - lightboxDragStart.y,
  };
}

function endLightboxDrag() {
  lightboxDragging.value = false;
}

function closeLightboxOutsideMedia(event:MouseEvent) {
  const target = event.target as Element | null;
  if (target?.closest("button, .lightbox-zoom-controls")) return;
  const overlay = event.currentTarget as HTMLElement | null;
  const media = overlay?.querySelector(".lightbox-stage img, .lightbox-stage video") as HTMLElement | null;
  if (media) {
    const rect = media.getBoundingClientRect();
    if (event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom) return;
  }
  lightboxIndex.value = -1;
}

function closeLightboxFromPointer(event:PointerEvent) {
  const target = event.target as Element | null;
  if (target?.closest(".lightbox-arrow, .lightbox-zoom-controls")) return;
  const overlay = event.currentTarget as HTMLElement | null;
  const media = overlay?.querySelector(".lightbox-stage img, .lightbox-stage video") as HTMLElement | null;
  if (media) {
    const rect = media.getBoundingClientRect();
    if (event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom) return;
  }
  lightboxIndex.value = -1;
}

function closeLightboxOnDocumentPointer(event:PointerEvent) {
  if (lightboxIndex.value < 0) return;
  const target = event.target as Element | null;
  if (target?.closest(".lightbox-arrow, .lightbox-zoom-controls")) return;
  const media = document.querySelector(".media-lightbox .lightbox-stage img, .media-lightbox .lightbox-stage video") as HTMLElement | null;
  if (media) {
    const rect = media.getBoundingClientRect();
    if (event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom) return;
  }
  lightboxIndex.value = -1;
}

function toggleLightboxZoom() {
  if (lightboxScale.value > lightboxFitScale.value) resetLightboxZoom();
  else setLightboxScale(Math.max(1, lightboxFitScale.value * 2));
}

function notify(message: string, duration = 1800) {
  const text = String(message || "").trim();
  if (!text) return;
  const last = chats.value.at(-1);
  if (last?.notice && last.text === text) return;
  chats.value.push({ side:"left", text, status:"系统提示", createdAt:Date.now(), notice:true });
  void nextTick(() => {
    if (chatScroll.value) chatScroll.value.scrollTop = chatScroll.value.scrollHeight;
  });
}

async function writeClipboardText(text:string) {
  try {
    await navigator.clipboard.writeText(text);
    return;
  } catch {
    const fallback = document.createElement("textarea");
    fallback.value = text;
    fallback.setAttribute("readonly", "");
    fallback.style.position = "fixed";
    fallback.style.opacity = "0";
    document.body.appendChild(fallback);
    fallback.select();
    const copied = document.execCommand("copy");
    fallback.remove();
    if (!copied) throw new Error("浏览器未授权剪贴板写入");
  }
}

async function copyChatText(text:string, index:number) {
  await writeClipboardText(text);
  copiedChatIndex.value = index;
  window.setTimeout(() => { if (copiedChatIndex.value === index) copiedChatIndex.value = null; }, 1600);
}

async function copyEpisodeText(text:string, key:string) {
  await writeClipboardText(text);
  copiedEpisodeKey.value = key;
  window.setTimeout(() => { if (copiedEpisodeKey.value === key) copiedEpisodeKey.value = ""; }, 1600);
}

function allOutlineText() {
  const plan = outlineDisplayPlan.value;
  if (!plan) return "";
  const episodes = [...outlineVisibleEpisodes.value].sort((left, right) => left.episode - right.episode);
  return [
    plan.title || "全剧故事大纲",
    plan.general_outline || "",
    ...episodes.map(episode => `第${String(episode.episode).padStart(2, "0")}集 · ${episode.title}\n${episode.synopsis}`),
  ].filter(Boolean).join("\n\n");
}

function allScriptText() {
  return [
    outlinePlan.value?.title || activeProjectRecord.value?.name || "全剧剧本",
    ...[...scripts.value].sort((left, right) => left.episode - right.episode)
      .map(script => `第${String(script.episode).padStart(2, "0")}集 · ${script.title}\n${humanReadableScriptContent(script.content)}`),
  ].join("\n\n");
}

function allStoryboardText() {
  return [
    outlinePlan.value?.title || activeProjectRecord.value?.name || "全剧分镜脚本",
    ...storyboardEpisodeGroups.value.map(group => `第${String(group.episode).padStart(2, "0")}集 · ${group.title}\n${group.shots.map(shot => `镜头${String(shot.shot_number).padStart(2, "0")} ${shot.start_second}–${shot.end_second}s\n画面：${shot.visual}\n动作：${shot.action}\n台词/旁白：${shot.dialogue || "无"}\n情绪：${shot.emotion || "自然"}\n声音：${shot.sound || "无"}`).join("\n\n")}`),
  ].join("\n\n");
}

function storyboardEpisodeText(shots:StoryboardShot[]) {
  return shots.map(shot => `镜头${String(shot.shot_number).padStart(2, "0")} ${shot.start_second}–${shot.end_second}s\n画面：${shot.visual}\n动作：${shot.action}\n台词/旁白：${shot.dialogue || "无"}\n情绪：${shot.emotion || "自然"}\n声音：${shot.sound || "无"}`).join("\n\n");
}

async function deleteOutlineSummary() {
  if (!outlinePlan.value || outlineStatus.value === "generating") return;
  outlinePlan.value = { ...outlinePlan.value, general_outline:"" };
  outlineTypedPlan.value = "";
  outlineStatus.value = "idle";
  outlineAudit.value = null;
  outlineRevisions.value = [];
  await persistOutlineState();
}

async function deleteOutlineEpisode(episode:number) {
  if (outlineStatus.value === "generating") return;
  outlineEpisodes.value = outlineEpisodes.value.filter(item => item.episode !== episode);
  delete outlineTypedEpisodes.value[episode];
  generatedEpisodeCount.value = outlineEpisodes.value.length;
  outlineStatus.value = "idle";
  outlineAudit.value = null;
  outlineRevisions.value = [];
  await persistOutlineState();
}

async function deleteScriptEpisode(episode:number) {
  if (scriptStatus.value === "generating") return;
  scripts.value = scripts.value.filter(item => item.episode !== episode);
  scriptStatus.value = "idle";
  scriptAudits.value = [];
  await persistScriptState();
}

async function deleteStoryboardEpisode(episode:number) {
  if (storyboardStatus.value === "generating") return;
  storyboardShots.value = storyboardShots.value.filter(item => item.episode !== episode);
  storyboardStatus.value = "idle";
  storyboardAudits.value = [];
  await persistStoryboardState();
}

function setChatFeedback(index:number, value:"up" | "down") {
  chatFeedback.value = { ...chatFeedback.value, [index]:chatFeedback.value[index] === value ? "" : value };
}

async function shareChatText(text:string) {
  if (navigator.share) await navigator.share({ text }).catch(() => undefined);
  else { await writeClipboardText(text); notify("内容已复制，可直接分享"); }
}

function quoteChatText(text:string) {
  input.value = `${input.value ? `${input.value}\n` : ""}> ${text.replace(/\n/g, "\n> ")}\n`;
  nextTick(() => document.querySelector<HTMLTextAreaElement>(".composer-shell > textarea")?.focus());
}

const taskGroups = computed(() => {
  const groups = new Map<string, Map<string, PlatformTask[]>>();
  for (const task of platformTasks.value) {
    const stage = task.label.split("·")[0]?.trim() || "其他任务";
    const episode = task.episode ? `第${String(task.episode).padStart(2, "0")}集` : "项目任务";
    if (!groups.has(stage)) groups.set(stage, new Map());
    const episodes = groups.get(stage)!;
    if (!episodes.has(episode)) episodes.set(episode, []);
    episodes.get(episode)!.push(task);
  }
  return [...groups.entries()].map(([stage, episodes]) => ({ stage, episodes:[...episodes.entries()].map(([episode, items]) => ({ episode, items })) }));
});

function taskIdentity(project = activeProjectRecord.value) {
  return { ...projectIdentity, project_id:project?.id || "" };
}

async function loadTasks(project = activeProjectRecord.value, session = projectSession) {
  if (!project) { platformTasks.value = []; taskFault.value = ""; return; }
  try {
    const result = await taskService.list(taskIdentity(project));
    if (!isCurrentProjectSession(project.id, session)) return;
    platformTasks.value = result.tasks;
    taskFault.value = result.fault?.message || "";
  } catch (error) {
    taskFault.value = error instanceof Error ? error.message : "任务列表加载失败";
  }
}

async function loadRuntimeTasks(project = activeProjectRecord.value, session = projectSession) {
  if (!project) { runtimeTasks.value = []; return; }
  try {
    const result = await taskService.runtime(taskIdentity(project));
    if (isCurrentProjectSession(project.id, session)) runtimeTasks.value = result.tasks;
  } catch { runtimeTasks.value = []; }
}

async function loadProductionCapabilities() {
  try {
    const result = await productionLedgerService.capabilities();
    productionCapabilities.value = result.capabilities;
    productionExtensions.value = result.extensions;
  } catch { productionCapabilities.value = []; productionExtensions.value = []; }
}

async function stopPlatformTask(task:PlatformTask) {
  try { await taskService.stop({ ...taskIdentity(), operation_key:task.operation_key }); await loadTasks(); notify("任务已停止，完成进度已保留"); }
  catch (error) { notify(error instanceof Error ? error.message : "任务停止失败"); }
}

async function resumePlatformTask(task:PlatformTask) {
  try { await taskService.resume({ ...taskIdentity(), operation_key:task.operation_key }); await loadTasks(); notify("任务已恢复"); }
  catch (error) { notify(error instanceof Error ? error.message : "任务恢复失败"); }
}

async function receivePlatformTaskResult(task:PlatformTask) {
  try {
    const received = await taskService.result<unknown>({ ...taskIdentity(), operation_key:task.operation_key });
    if (received.result !== null) await loadProjectFlowState();
    notify("任务结果已领取并保留在对应流程");
  }
  catch (error) { notify(error instanceof Error ? error.message : "任务结果领取失败"); }
}

function toggleTaskStage(stage:string) {
  expandedTaskStages.value = expandedTaskStages.value.includes(stage) ? expandedTaskStages.value.filter(item => item !== stage) : [...expandedTaskStages.value, stage];
}

function toggleTaskEpisode(stage:string, episode:string) {
  const key = `${stage}:${episode}`;
  expandedTaskEpisodes.value = expandedTaskEpisodes.value.includes(key) ? expandedTaskEpisodes.value.filter(item => item !== key) : [...expandedTaskEpisodes.value, key];
}

async function loadResources(project = activeProjectRecord.value, session = projectSession) {
  if (!project) { storedResources.value = []; dynamicGlobalNodes.value = []; dynamicEpisodeNodes.value = []; return; }
  try {
    const episode = Number(selectedEpisode.value.replace(/\D/g, "")) || workflowEpisode.value;
    const [globalResult, projectResult, episodeResult] = await Promise.all([
      resourceService.list({ ...projectIdentity, scope:"tenant_global" }),
      resourceService.list({ ...projectIdentity, scope:"project", project_id:project.id }),
      resourceService.list({ ...projectIdentity, scope:"project_episode", project_id:project.id, episode }),
    ]);
    if (!isCurrentProjectSession(project.id, session)) return;
    storedResources.value = [...globalResult.resources, ...projectResult.resources, ...episodeResult.resources];
    dynamicGlobalNodes.value = globalResult.resources.map(item => item.name);
    dynamicEpisodeNodes.value = episodeResult.resources.map(item => item.name);
    const persistentAssets = storedResources.value.map((item):UploadAsset => ({
      id:item.id, name:item.name, url:resourceService.mediaUrl(item, projectIdentity),
      mediaType:item.kind === "video" ? "video" : "image",
      scope:item.scope === "tenant_global" ? "全局公共" : "本集私有", label:item.scope === "tenant_global" ? "全局" : item.scope === "project" ? "项目" : "本集",
    }));
    const temporary = uploadedAssets.value.filter(item => item.scope === "临时参考");
    uploadedAssets.value = [...temporary, ...persistentAssets];
  } catch (error) { notify(error instanceof Error ? error.message : "资源列表加载失败"); }
}

async function persistAssetResource(asset:UploadAsset, scope:"tenant_global" | "project" | "project_episode") {
  const project = activeProjectRecord.value;
  if (!project) throw new Error("请先选择项目");
  const session = projectSession;
  const episode = Number(selectedEpisode.value.replace(/\D/g, "")) || workflowEpisode.value;
  const result = await resourceService.save({
    ...projectIdentity, id:storedResources.value.some(item => item.id === asset.id) ? asset.id : undefined,
    scope, project_id:scope === "tenant_global" ? undefined : project.id, episode:scope === "project_episode" ? episode : undefined,
    kind:asset.mediaType, name:asset.name, url:asset.url.startsWith("data:") ? undefined : asset.url,
    data_url:asset.url.startsWith("data:") ? asset.url : undefined,
    metadata:{ source:"assistant", original_id:asset.id },
  });
  if (!isCurrentProjectSession(project.id, session)) throw new DOMException("项目已切换，忽略旧项目资源写回", "AbortError");
  asset.id = result.resource.id;
  asset.url = resourceService.mediaUrl(result.resource, projectIdentity);
  return result.resource;
}

type SkillBindingStage = { enabled:string[]; audit_enabled?:string[]; robots:Record<string, IndustryRobot[]>; model_policy:"automatic"|"per_skill"; model_bindings?:Record<string,string>; review_model_bindings?:Record<string,string>; audit_config?:{ plan:AuditPlan; advanced:boolean; models:Record<string,string> } };
const normalizedSkillName = (name:string) => {
  const normalized = name.replaceAll("机" + "器" + "人", "");
  return normalized === "稽查" ? "审核" : normalized;
};
const normalizeSkillRecord = <T>(record:Record<string,T> = {}) => Object.fromEntries(Object.entries(record).map(([name,value]) => [normalizedSkillName(name), value]));
async function loadSkillBindings(project = activeProjectRecord.value, session = projectSession) {
  enabledSkills.value = [...allDefaultSkills, "审核"]; auditEnabledSkills.value = [...allDefaultSkills]; skillRobots.value = {}; skillModelBindings.value = {};
  if (!project) return;
  try {
    const result = await projectService.readStage<SkillBindingStage>({ ...projectIdentity, id:project.id, stage:"skill_bindings" });
    if (!isCurrentProjectSession(project.id, session) || !result.stage) return;
    enabledSkills.value = [...allDefaultSkills];
    auditEnabledSkills.value = [...new Set((result.stage.data.audit_enabled || []).map(normalizedSkillName))].filter(name => allDefaultSkills.includes(name as never));
    if (auditEnabledSkills.value.length) enabledSkills.value.push("审核");
    skillRobots.value = normalizeSkillRecord(result.stage.data.robots || {});
    skillModelBindings.value = normalizeSkillRecord(result.stage.data.model_bindings || {});
    skillReviewModelBindings.value = normalizeSkillRecord(result.stage.data.review_model_bindings || {});
    auditPlan.value = result.stage.data.audit_config?.plan || "balanced";
    auditAdvancedOpen.value = result.stage.data.audit_config?.advanced || false;
    auditModelBindings.value = { ...auditModelBindings.value, ...(result.stage.data.audit_config?.models || {}) };
  } catch (error) { notify(error instanceof Error ? error.message : "Skill 配置加载失败"); }
}
async function persistSkillBindings(project:StoredProject) {
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"skill_bindings", data:{ enabled:[...allDefaultSkills], audit_enabled:auditEnabledSkills.value, robots:skillRobots.value, model_policy:Object.keys(skillModelBindings.value).length || Object.keys(skillReviewModelBindings.value).length ? "per_skill" : "automatic", model_bindings:skillModelBindings.value, review_model_bindings:skillReviewModelBindings.value, audit_config:{ plan:auditPlan.value, advanced:auditAdvancedOpen.value, models:auditModelBindings.value } } satisfies SkillBindingStage });
}
async function stopDisabledNarrativeAudits(project:StoredProject) {
  if (outlinePhase.value === "audit" || outlinePhase.value === "repair") {
    outlineController.value?.abort(); outlinePhase.value = ""; outlineAudit.value = null; outlineAuditStopped.value = false;
    outlineStatus.value = outlineEpisodesComplete.value ? "confirmed" : "failed";
    outlineError.value = outlineEpisodesComplete.value ? "" : "审核关闭，生成内容尚未完整";
    await persistOutlineState(project);
  }
  if (scriptPhase.value === "initial_audit" || scriptPhase.value === "final_audit") {
    scriptController.value?.abort(); scriptPhase.value = ""; scriptAudits.value = [];
    scriptStatus.value = scripts.value.length >= project.episode_count ? "confirmed" : "failed";
    scriptError.value = scriptStatus.value === "failed" ? "审核关闭，生成内容尚未完整" : "";
    await persistScriptState(project);
  }
}
function requireEnabledRobot(name:string) {
  return enabledSkills.value.includes(name);
}
function auditEnabled(skill:string) { return auditEnabledSkills.value.includes(skill); }
async function toggleSkillAudit(skill: string) {
  const project = activeProjectRecord.value;
  if (!project || skillChanging.value) return notify(project ? "审核正在配置" : "请先选择项目");
  skillChanging.value = skill;
  try {
    const enabling = !auditEnabledSkills.value.includes(skill);
    auditEnabledSkills.value = enabling ? [...auditEnabledSkills.value, skill] : auditEnabledSkills.value.filter(item => item !== skill);
    enabledSkills.value = [...allDefaultSkills, ...(auditEnabledSkills.value.length ? ["审核"] : [])];
    await persistSkillBindings(project);
    if (!enabling && ["项目策划", "编剧"].includes(skill)) await stopDisabledNarrativeAudits(project);
    notify(`${skill}审核已${enabling ? "开启" : "关闭"}`);
  } catch (error) { notify(error instanceof Error ? error.message : "Skill 配置失败"); }
  finally { skillChanging.value = ""; }
}
function capabilityList(value:string) {
  return [...new Set(value.split(",").map(item => item.trim()).filter(Boolean))];
}
async function openSkillConfiguration(skill:string) {
  configuringSkill.value = skill;
  modelRole.value = "main";
  selectedSkillModel.value = skillModelBindings.value[skill] || "automatic";
  modelSource.value = selectedSkillModel.value.startsWith("cloud-") ? "cloud" : "local";
  syncModelFormFromBinding();
  try {
    const [models, providers] = await Promise.all([agentConfigurationService.listModels(), providerService.list()]);
    availableModels.value = models.items.filter(item => item.enabled);
    availableProviders.value = providers.items.filter(item => item.enabled);
  } catch (error) { notify(error instanceof Error ? error.message : "模型配置加载失败"); }
}
function syncModelFormFromBinding() {
  const binding = activeRoleModel.value;
  const draftKey = `${configuringSkill.value}:${modelRole.value}:${modelSource.value}`;
  if (binding.startsWith("local-")) {
    modelSource.value = "local";
    const preset = localModelPresets.find(item => binding.endsWith(`:${item.id}`));
    if (preset) { modelCategory.value = preset.category; localModelForm.value.model_id = preset.id; }
  } else if (binding.startsWith("cloud-")) {
    modelSource.value = "cloud";
    const platform = Object.keys(cloudModelPresets).find(key => binding.startsWith(`cloud-${key}:`));
    if (platform) {
      cloudModelForm.value.platform = platform;
      cloudModelForm.value.endpoint = cloudModelPresets[platform].endpoint;
      const preset = cloudModelPresets[platform].models.find(item => binding.endsWith(`:${item.id}`));
      if (preset) { modelCategory.value = preset.category; cloudModelForm.value.model_id = preset.id; }
    }
  } else if (modelSource.value === "local") {
    localModelForm.value.model_id = roleModelDrafts.value[draftKey] || defaultLocalModelForRole();
    modelCategory.value = localModelPresets.find(model => model.id === localModelForm.value.model_id)?.category || "text";
  } else {
    cloudModelForm.value.model_id = roleModelDrafts.value[draftKey] || selectedCloudPlatform.value.models[0].id;
  }
}
function defaultLocalModelForRole() {
  if (["视觉资产","视频制作"].includes(configuringSkill.value)) return "llava:latest";
  if (modelRole.value === "initial") return "qwen3:32b";
  if (modelRole.value === "final") return "deepseek-r1:70b";
  return "qwen2.5:72b";
}
function selectModelCategory(category:ModelCategory) {
  modelCategory.value = category;
  if (category === "automatic") { activeRoleModel.value = "automatic"; return; }
  const local = localModelPresets.find(model => model.category === category && model.available !== false);
  const cloud = selectedCloudPlatform.value.models.find(model => model.category === category);
  if (local) localModelForm.value.model_id = local.id;
  if (cloud) cloudModelForm.value.model_id = cloud.id;
  rememberRoleModelDraft();
}
function rememberRoleModelDraft() {
  const key = `${configuringSkill.value}:${modelRole.value}:${modelSource.value}`;
  roleModelDrafts.value[key] = modelSource.value === "local" ? localModelForm.value.model_id : cloudModelForm.value.model_id;
}
function selectModelSource(source:"local"|"cloud") {
  if (modelSource.value === source) return;
  rememberRoleModelDraft();
  modelSource.value = source;
  activeRoleModel.value = "automatic";
  syncModelFormFromBinding();
}
function selectModelRole(role:"main"|"initial"|"final") {
  rememberRoleModelDraft();
  modelRole.value = role;
  modelSource.value = activeRoleModel.value.startsWith("cloud-") ? "cloud" : "local";
  syncModelFormFromBinding();
}
function applyCloudPlatformDefaults() {
  const preset = selectedCloudPlatform.value;
  cloudModelForm.value.endpoint = preset.endpoint;
  cloudModelForm.value.model_id = preset.models[0].id;
}
async function registerCloudModel() {
  skillConfigurationSaving.value = true;
  try {
    const preset = selectedCloudPlatform.value;
    const modelPreset = preset.models.find(item => item.id === cloudModelForm.value.model_id) || preset.models[0];
    const providerId = `cloud-${cloudModelForm.value.platform}`;
    let provider = availableProviders.value.find(item => item.provider_id === providerId);
    if (!provider) {
      const providerCapabilities = [...new Set(preset.models.flatMap(item => item.capabilities))];
      provider = await providerService.register({ provider_id:providerId, display_name:preset.name, kind:"model", endpoint:cloudModelForm.value.endpoint, secret_reference:preset.secret, capabilities:providerCapabilities, enabled:true, timeout_seconds:120, settings:{ platform:cloudModelForm.value.platform } });
      availableProviders.value = [...availableProviders.value, provider];
    }
    const modelId = `${providerId}:${modelPreset.id}`;
    const item = await agentConfigurationService.registerModel({ model_id:modelId, provider_id:providerId, display_name:modelPreset.name, context_window:modelPreset.context, capabilities:modelPreset.capabilities });
    availableModels.value = [...availableModels.value.filter(model => model.model_id !== item.model_id), item];
    activeRoleModel.value = item.model_id;
    notify("云端模型已接入并选中");
  } catch (error) { notify(error instanceof Error ? error.message : "云端模型接入失败"); }
  finally { skillConfigurationSaving.value = false; }
}
async function registerLocalModel() {
  skillConfigurationSaving.value = true;
  try {
    const modelPreset = localModelPresets.find(item => item.id === localModelForm.value.model_id) || localModelPresets[0];
    if (modelPreset.available === false) throw new Error("该本地模型尚未安装");
    const suffix = modelPreset.id.toLowerCase().replace(/[^a-z0-9._-]+/g, "-");
    const providerId = `local-${localModelForm.value.runtime.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${suffix}`;
    const capabilities = modelPreset.capabilities;
    let provider = availableProviders.value.find(item => item.provider_id === providerId);
    if (!provider) {
      provider = await providerService.register({ provider_id:providerId, display_name:`${localModelForm.value.runtime} 本地服务`, kind:"model", endpoint:localModelForm.value.endpoint, secret_reference:"env://LOCAL_MODEL_API_KEY", capabilities, enabled:true, timeout_seconds:120, settings:{ runtime:localModelForm.value.runtime, local:true } });
      availableProviders.value = [...availableProviders.value, provider];
    }
    const model = await agentConfigurationService.registerModel({ model_id:`${providerId}:${modelPreset.id}`, provider_id:providerId, display_name:modelPreset.name, context_window:modelPreset.context, capabilities });
    availableModels.value = [...availableModels.value, model];
    activeRoleModel.value = model.model_id;
    notify("本地模型已注册并选中");
  } catch (error) { notify(error instanceof Error ? error.message : "本地模型注册失败"); }
  finally { skillConfigurationSaving.value = false; }
}
async function saveSkillModelBinding() {
  const project = activeProjectRecord.value;
  const skill = configuringSkill.value;
  if (!project || !skill) return notify("请先选择项目和 Skill");
  skillConfigurationSaving.value = true;
  try {
    if (modelCategory.value === "automatic") {
      activeRoleModel.value = "automatic";
      if (modelRole.value === "main") delete skillModelBindings.value[skill];
      else delete skillReviewModelBindings.value[`${skill}:${modelRole.value}`];
      await persistSkillBindings(project);
      notify(`${skill}${modelRole.value === "main" ? "" : modelRole.value === "initial" ? "初审" : "终审"}已设为 AI 自动判断`);
      return;
    }
    if (activeRoleModel.value === "automatic" || !availableModels.value.some(model => model.model_id === activeRoleModel.value)) {
      if (modelSource.value === "local") await registerLocalModel();
      else await registerCloudModel();
      if (activeRoleModel.value === "automatic") throw new Error("模型接入失败");
    }
    if (modelRole.value !== "main") {
      if (activeRoleModel.value === "automatic") delete skillReviewModelBindings.value[`${skill}:${modelRole.value}`];
      else skillReviewModelBindings.value[`${skill}:${modelRole.value}`] = activeRoleModel.value;
      await persistSkillBindings(project);
      notify(`${skill}${modelRole.value === "initial" ? "初审" : "终审"}模型已保存`);
      return;
    }
    if (selectedSkillModel.value === "automatic") delete skillModelBindings.value[skill];
    else {
      skillModelBindings.value[skill] = selectedSkillModel.value;
      await persistSkillBindings(project);
      const robots:IndustryRobot[] = [];
      for (const skillId of skillRobotIds[skill] || []) robots.push(await industryAgentService.robot(skillId, project.id));
      skillRobots.value[skill] = robots;
      for (const robot of robots) {
        try {
          const current = await agentConfigurationService.getConfiguration(robot.robot_id);
          await agentConfigurationService.updateConfiguration(current, selectedSkillModel.value);
        } catch {
          try { await agentConfigurationService.createConfiguration(robot.robot_id, selectedSkillModel.value); }
          catch { /* 项目级绑定已保存；不兼容子流程继续使用能力自动路由。 */ }
        }
      }
    }
    await persistSkillBindings(project);
    configuringSkill.value = "";
    notify(`${skill}模型配置已生效`);
  } catch (error) { notify(error instanceof Error ? error.message : "Skill 模型配置失败"); }
  finally { skillConfigurationSaving.value = false; }
}
async function saveAuditConfiguration() {
  const project = activeProjectRecord.value;
  if (!project) return notify("请先选择项目");
  skillConfigurationSaving.value = true;
  try {
    auditEnabledSkills.value = [...allDefaultSkills];
    await persistSkillBindings(project);
    notify("审核方案已保存");
  } catch (error) { notify(error instanceof Error ? error.message : "审核方案保存失败"); }
  finally { skillConfigurationSaving.value = false; }
}

function selectComposerResource(kind: "文本" | "图集" | "分镜" | "视频", option: string) {
  selectedResourceLabels.value[kind] = option;
  if ((kind === "分镜" || kind === "视频") && option !== "全部") selectedEpisode.value = option;
  resourceMenuOpen.value = "";
  notify(`${kind}：${option}`);
}

function selectWorkflowNavigation(kind: WorkflowNavigation) {
  activeWorkflowNavigation.value = kind;
  markWorkflowCompletionRead(kind);
  if (kind === "大纲") {
    rightPanelMode.value = "outline";
    selectedNode.value = "故事大纲";
  } else if (kind === "剧本") {
    rightPanelMode.value = "script";
    selectedNode.value = "剧本";
  } else if (kind === "分镜脚本") {
    rightPanelMode.value = "storyboard";
    selectedNode.value = "分镜";
  } else if (kind === "资产" || kind === "分镜画面") {
    rightPanelMode.value = kind === "资产" ? "assets" : "images";
    selectedNode.value = kind === "资产" ? "人物素材" : "生图输出";
  } else {
    rightPanelMode.value = "video";
    selectedNode.value = kind;
  }
}

function syncWorkflowEpisode() {
  selectedEpisode.value = workflowEpisode.value === 0 ? "" : `第${String(workflowEpisode.value).padStart(2, "0")}集`;
  selectWorkflowNavigation(activeWorkflowNavigation.value);
}
function selectWorkflowEpisode(episode:number) {
  workflowEpisode.value = episode;
  syncWorkflowEpisode();
}

function syncWorkflowAsset(category: "人物" | "道具" | "场景") {
  activeAssetCategory.value = category;
  selectedNode.value = `${category}素材`;
}

async function deletePreviewAsset(asset: UploadAsset) {
  if (storedResources.value.some(item => item.id === asset.id)) {
    try { await resourceService.remove({ ...projectIdentity, id:asset.id }); }
    catch (error) { return notify(error instanceof Error ? error.message : "资源删除失败"); }
  }
  hiddenAssetIds.value.push(asset.id);
  uploadedAssets.value = uploadedAssets.value.filter((item) => item.id !== asset.id);
  notify(`已删除：${asset.name}`);
}

function openPreviewAsset(asset: UploadAsset) {
  lightboxScale.value = 1;
  lightboxFitScale.value = 1;
  lightboxOffset.value = { x:0, y:0 };
  lightboxIndex.value = lightboxAssets.value.findIndex((item) => item.id === asset.id);
}

function openGeneratedImage(id:string) {
  const asset = lightboxAssets.value.find(item => item.id === id);
  if (asset) openPreviewAsset(asset);
}

function openPreviewUrl(url:string) {
  const asset = lightboxAssets.value.find(item => item.url === url);
  if (asset) openPreviewAsset(asset);
}

type AssetPhotoSlide = { key:string; label:string; imageUrl?:string; previewId?:string; status:AssetStatus; variant?:AssetVariant; readOnly?:boolean };
function assetPhotoSlides(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile):AssetPhotoSlide[] {
  const variants = [...(item.detail_assets || [])];
  const takeVariant = (matcher:RegExp) => {
    const index = variants.findIndex(variant => matcher.test(variant.label));
    return index >= 0 ? variants.splice(index, 1)[0] : undefined;
  };
  const variantSlide = (label:string, variant?:AssetVariant):AssetPhotoSlide => ({
    key:variant?.id || `placeholder:${label}`,
    label,
    imageUrl:variant?.image_url,
    previewId:variant?.image_url ? `asset:${item.name}:${variant.id}` : undefined,
    status:variant?.status || "pending",
    variant,
  });
  if (kind === "character") {
    const left45 = takeVariant(/左\s*45\s*[°度]|left[_\s-]*45/u);
    const front = takeVariant(/0\s*[°度].*正面全身|front[_\s-]*full/u);
    const right45 = takeVariant(/右\s*45\s*[°度]|right[_\s-]*45/u);
    const side = takeVariant(/侧面|90\s*度|侧视/u);
    const back = takeVariant(/背面|后视/u);
    const half = takeVariant(/半身|front[_\s-]*half/u);
    return [
      variantSlide("0°正面半身", half),
      { key:"baseline:front", label:"0°正面全身", imageUrl:item.image_url, previewId:item.image_url ? `asset:${item.name}` : undefined, status:item.status || "pending" },
      variantSlide("左45°全身", left45),
      variantSlide("右45°全身", right45),
      variantSlide("90°侧面全身", side),
      variantSlide("180°背面全身", back),
    ];
  }
  const angleDefinitions = fixedAssetAngles[kind];
  const slides:AssetPhotoSlide[] = [
    { key:"baseline", label:angleDefinitions[0].label, imageUrl:item.image_url, previewId:item.image_url ? `asset:${item.name}` : undefined, status:item.status || "pending" },
  ];
  for (const render of item.model3d_result?.renders || []) slides.push({
    key:`3d:${render.label}`, label:`3D ${render.label}`, imageUrl:render.url,
    previewId:`asset:${item.name}:3d:${render.label}`, status:"confirmed", readOnly:true,
  });
  return slides;
}

function unifiedAssetSlides(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile):UnifiedAssetSlide[] {
  return assetPhotoSlides(kind, item).map(slide => ({
    ...slide,
    generating:isAssetSlideGenerating(kind, item.name, slide.key),
    showAccept:!slide.readOnly && ((slide.key === baselineSlideKey(kind) && canAcceptAssetBaseline(item)) || slide.variant?.status === "waiting_confirmation"),
  }));
}

function assetSlide(value:UnifiedAssetSlide):AssetPhotoSlide {
  return value as AssetPhotoSlide;
}

function toggleUnifiedAssetIntro(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, slide:UnifiedAssetSlide) {
  const key = `${kind}:${item.name}:${slide.key}`;
  assetIntroOpen.value = assetIntroOpen.value === key ? "" : key;
}

function regenerateUnifiedAssetSlide(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, slide:UnifiedAssetSlide) {
  if (slide.generating) return stopAssetGeneration(kind, item);
  return regenerateAssetPhotoSlide(kind, item, assetSlide(slide));
}

function acceptUnifiedAssetSlide(item:CharacterProfile | SceneProfile | PropProfile, slide:UnifiedAssetSlide) {
  const variant = assetSlide(slide).variant;
  return variant?.status === "waiting_confirmation" ? confirmAssetVariant(item, variant) : confirmAsset(item);
}

const fixedAssetAngles = {
  character:[
    { label:"0°正面全身", prompt:"严格0度正面平视完整全身基准照。脸、双肩、胸口、骨盆、双膝和双脚全部正对镜头，头部偏航角与翻滚角均接近0度；人物居中自然A-Pose，从完整发顶到完整鞋底全部入画，双手自然下垂且可见；发顶上方纯背景留白至少为画高8%，鞋底下方纯背景留白至少为画高3%，两者都是最低值而非固定值。纯中性灰无缝背景，中性表情，禁止左45度、右45度、侧面、背面、近照、半身、俯拍、仰拍、动作、道具、多人、拼图、文字和裁切" },
    { label:"左45°全身", prompt:"基于已确认0度正面全身基准图，将同一人物相对镜头只向人物左侧旋转45度；脸部偏航角必须为正30至60度，同时展示正面和人物左侧结构。保持平视、自然A-Pose和完整全身构图，发顶上方纯背景留白至少8%、鞋底下方纯背景留白至少3%（均为最低值而非固定值），身份、五官、发型、体型、服装、鞋履与配饰完全一致。禁止0度正面、右45度、90度侧面、背面、近照、半身、镜像、动作、道具、多人、拼图和裁切" },
    { label:"右45°全身", prompt:"基于已确认0度正面全身基准图，将同一人物相对镜头只向人物右侧旋转45度；脸部偏航角必须为负30至负60度，同时展示正面和人物右侧结构。保持平视、自然A-Pose和完整全身构图，发顶上方纯背景留白至少8%、鞋底下方纯背景留白至少3%（均为最低值而非固定值），身份、五官、发型、体型、服装、鞋履与配饰完全一致。禁止0度正面、左45度、90度侧面、背面、近照、半身、镜像、动作、道具、多人、拼图和裁切" },
    { label:"90°侧面全身", prompt:"基于已确认人物档案生成严格90度纯侧面平视完整全身照；脸部、鼻梁、胸口、骨盆和双脚朝向同一侧，脸部只保留侧面轮廓，不得出现正面双眼。保持自然A-Pose、完整发顶至鞋底，发顶上方纯背景留白至少8%、鞋底下方纯背景留白至少3%（均为最低值而非固定值），身份、妆发、体型、服装与配饰一致。禁止0度正面、45度斜侧、背面、近照、半身、动作、道具、多人、拼图和裁切" },
    { label:"180°背面全身", prompt:"基于已确认人物档案生成严格180度纯背面平视完整全身照；后脑、后颈、双肩背面、服装背部、双腿后侧和鞋跟正对镜头，脸和五官必须完全不可见。保持自然A-Pose、完整发顶至鞋底，发顶上方纯背景留白至少8%、鞋底下方纯背景留白至少3%（均为最低值而非固定值），体型、发型背部、服装和配饰一致。禁止正面脸、侧脸、回头、45度、90度、近照、半身、动作、道具、多人、拼图和裁切" },
    { label:"0°正面半身", prompt:"基于已确认0度正面全身基准图生成严格0度正面平视半身照；脸和双肩正对镜头，偏航角与翻滚角均接近0度。人物居中，从完整发顶到腰部裁切，头顶仅微小留白，双手完全出画，头部至腰部约占画高75%，双肩不触边；身份、五官、妆发、肤色、年龄、领口、服装和配饰完全一致，纯中性灰背景。禁止全身远景、左45度、右45度、侧面、背面、俯仰角、动作、道具、多人和拼图" },
  ],
  scene:[
    { label:"45°空场景全景", prompt:"正常人眼高度45度空场景全景，完整展示空间纵深、入口、墙地关系、固定陈设和主要遮挡，画面内严格无人、无人体、无文字、无拼图、无鱼眼畸变" },
  ],
  prop:[
    { label:"45°三分之二视图", prompt:"单一完整道具45度三分之二视图，同时清晰展示正面、顶面和侧面三维结构，所有边缘、厚度、把手和底部结构尽量可见，纯中性灰背景，严格无人、无手、无支架、无文字" },
  ],
} as const;

function hasCompleteAssetVariants(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile) {
  if (kind === "scene" || kind === "prop") return Boolean(item.image_url && item.baseline_confirmed_at);
  if (item.upload_view_mode === "single") return Boolean(item.image_url);
  return fixedAssetAngles[kind].slice(1).every(definition =>
    item.detail_assets?.some(variant => variant.label === definition.label && variant.status === "confirmed" && Boolean(variant.image_url)),
  );
}

function assetCategoryImageTotal(category:AssetCategory) {
  if (category === "人物") return characterProfiles.value.length;
  if (category === "道具") return propProfiles.value.length;
  return sceneProfiles.value.length;
}

function baselineIdentityPrompt(prompt:string) {
  return prompt
    .replace(/(?:分别|依次|同时)?生成[^。；\n]*(?:正面|侧面|背面|全身|近照|视图)[^。；\n]*/gu, "")
    .replace(/(?:单人物\s*)?(?:(?:0\s*[°度]\s*)?正面|左\s*45\s*[°度]?|右\s*45\s*[°度]?|90\s*[°度]?\s*侧面|侧面\s*90\s*[°度]?|180\s*[°度]?\s*背面|背面\s*180\s*[°度]?)\s*(?:完整\s*)?(?:近照|半身\s*(?:照)?|全身\s*(?:照|视图)?|视图)?/gu, "")
    .replace(/(?:单人物\s*)?(?:完整\s*)?(?:近照|半身\s*照|全身\s*(?:照|视图)|多角度\s*视图)/gu, "")
    .replace(/(?:多视图|多角度|四视图|三视图|拼图|宫格|分栏|接触表)/gu, "")
    .replace(/，{2,}/gu, "，")
    .replace(/^，|，$/gu, "")
    .replace(/[。；\s]+$/u, "")
    .trim();
}

function assetSlideGenerationKey(kind:"character" | "scene" | "prop", name:string, slideKey:string) {
  return `${kind}:${name}:${slideKey}`;
}

function baselineSlideKey(kind:"character" | "scene" | "prop") {
  return kind === "character" ? "baseline:front" : "baseline";
}

function canAcceptAssetBaseline(item:CharacterProfile | SceneProfile | PropProfile) {
  return Boolean(item.image_url) && item.status !== "confirmed" && item.status !== "generating";
}

let assetOperationTail:Promise<void> = Promise.resolve();
let assetOperationEpoch = 0;
const queuedAssetOperationOwners = new Map<string, string>();
const queuedAssetOperationCount = ref(0);

function enqueueAssetOperation(key:string, label:string, operation:() => void | Promise<void>) {
  const project = activeProjectRecord.value;
  if (!project || queuedAssetOperationOwners.has(key)) return assetOperationTail;
  const session = projectSession;
  const epoch = assetOperationEpoch;
  const ownerToken = crypto.randomUUID();
  const queuedBehindAnother = queuedAssetOperationCount.value > 0 || assetImagesRunning.value;
  queuedAssetOperationOwners.set(key, ownerToken);
  queuedAssetOperationCount.value += 1;
  if (queuedBehindAnother) notify(`${label}已加入任务队列，将按顺序执行`);
  const scheduled = assetOperationTail.catch(() => undefined).then(async () => {
    if (epoch !== assetOperationEpoch || !isCurrentProjectSession(project.id, session)) return;
    while (assetImagesRunning.value) {
      await new Promise(resolve => window.setTimeout(resolve, 250));
      if (epoch !== assetOperationEpoch || !isCurrentProjectSession(project.id, session)) return;
    }
    await operation();
  }).catch(error => {
    if (epoch === assetOperationEpoch && isCurrentProjectSession(project.id, session)) notify(error instanceof Error ? error.message : `${label}执行失败`);
  }).finally(() => {
    if (queuedAssetOperationOwners.get(key) === ownerToken) {
      queuedAssetOperationOwners.delete(key);
      queuedAssetOperationCount.value = Math.max(0, queuedAssetOperationCount.value - 1);
    }
  });
  assetOperationTail = scheduled.then(() => undefined, () => undefined);
  return scheduled;
}

function queueGenerateAllAssetImages() {
  const project = activeProjectRecord.value;
  if (!project) return;
  const session = projectSession;
  return enqueueAssetOperation(`${project.id}:generate-all`, "生成资产图片", () => generateAllAssetImages(project, session));
}

function queueAssetSlideAcceptance(item:CharacterProfile | SceneProfile | PropProfile, slide:UnifiedAssetSlide) {
  const project = activeProjectRecord.value;
  if (!project) return;
  return enqueueAssetOperation(`${project.id}:accept:${item.name}:${slide.key}`, `确认${item.name}${slide.label}`, () => acceptUnifiedAssetSlide(item, slide));
}

function queueAssetBaselineAcceptance(item:CharacterProfile | SceneProfile | PropProfile) {
  const project = activeProjectRecord.value;
  if (!project) return;
  return enqueueAssetOperation(`${project.id}:accept:${item.name}:baseline`, `确认${item.name}定位基准图`, () => confirmAsset(item));
}

function queueAssetSlideRegeneration(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, slide:UnifiedAssetSlide) {
  const project = activeProjectRecord.value;
  if (!project) return;
  return enqueueAssetOperation(`${project.id}:regenerate:${kind}:${item.name}:${slide.key}`, `重做${item.name}${slide.label}`, () => regenerateUnifiedAssetSlide(kind, item, slide));
}

function queueAssetSlideRepair(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, slide:UnifiedAssetSlide) {
  const project = activeProjectRecord.value;
  if (!project) return;
  return enqueueAssetOperation(`${project.id}:repair:${kind}:${item.name}:${slide.key}`, `修复${item.name}${slide.label}`, () => repairAssetPhotoSlide(kind, item, assetSlide(slide)));
}

function queueAsset3D(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile) {
  const project = activeProjectRecord.value;
  if (!project) return;
  return enqueueAssetOperation(`${project.id}:3d:${kind}:${item.name}`, `生成${item.name} 3D资产`, () => generateAsset3D(kind, item));
}

function queueAsset3DConfirmation(item:CharacterProfile | SceneProfile | PropProfile) {
  const project = activeProjectRecord.value;
  if (!project) return;
  return enqueueAssetOperation(`${project.id}:confirm-3d:${item.name}`, `确认${item.name} 3D资产`, () => confirmAsset3D(item));
}

function queueAssetUpscale(name:string, imageUrl?:string) {
  const project = activeProjectRecord.value;
  if (!project) return;
  return enqueueAssetOperation(`${project.id}:upscale:${name}`, `${name}图片超分`, () => upscaleWorkflowImage(name, imageUrl));
}

function isAssetSlideGenerating(kind:"character" | "scene" | "prop", name:string, slideKey:string) {
  if (activeAssetGenerationKey.value) return activeAssetGenerationKey.value === assetSlideGenerationKey(kind, name, slideKey);
  const items = kind === "character" ? characterProfiles.value : kind === "prop" ? propProfiles.value : sceneProfiles.value;
  const item = items.find(value => value.name === name);
  if (!item || item.status !== "generating") return false;
  const generatingVariant = item.detail_assets?.find(variant => variant.status === "generating");
  return generatingVariant ? generatingVariant.id === slideKey : slideKey === baselineSlideKey(kind);
}

let assetCarouselDraggedUntil = 0;
let assetCarouselDrag:{ element:HTMLElement; pointerId:number; startX:number; scrollLeft:number; moved:boolean; lastX:number; lastTime:number; velocity:number; previewId?:string } | undefined;
function startAssetCarouselDrag(event:PointerEvent) {
  if (event.button !== 0) return;
  if ((event.target as HTMLElement | null)?.closest("button")) return;
  window.cancelAnimationFrame(assetCarouselMomentumFrame);
  assetCarouselMomentumFrame = 0;
  const element = event.currentTarget as HTMLElement;
  const previewId = (event.target as HTMLElement | null)?.closest<HTMLElement>("[data-preview-id]")?.dataset.previewId;
  assetCarouselDrag = { element, pointerId:event.pointerId, startX:event.clientX, scrollLeft:element.scrollLeft, moved:false, lastX:event.clientX, lastTime:performance.now(), velocity:0, previewId };
  element.setPointerCapture(event.pointerId);
  window.addEventListener("pointerup", endAssetCarouselDrag);
  window.addEventListener("pointercancel", endAssetCarouselDrag);
  window.addEventListener("blur", cancelAssetCarouselDrag);
}
function moveAssetCarouselDrag(event:PointerEvent) {
  const drag = assetCarouselDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  const now = performance.now();
  const elapsed = Math.max(1, now - drag.lastTime);
  const movement = event.clientX - drag.lastX;
  const distance = event.clientX - drag.startX;
  if (Math.abs(distance) > 5) drag.moved = true;
  drag.element.scrollLeft = drag.scrollLeft - distance;
  const instantVelocity = -movement / elapsed;
  drag.velocity = drag.velocity * 0.68 + instantVelocity * 0.32;
  drag.lastX = event.clientX;
  drag.lastTime = now;
}
function endAssetCarouselDrag(event:PointerEvent) {
  const drag = assetCarouselDrag;
  if (!drag || drag.pointerId !== event.pointerId) return;
  if (drag.moved) assetCarouselDraggedUntil = Date.now() + 300;
  if (drag.element.hasPointerCapture(event.pointerId)) drag.element.releasePointerCapture(event.pointerId);
  assetCarouselDrag = undefined;
  window.removeEventListener("pointerup", endAssetCarouselDrag);
  window.removeEventListener("pointercancel", endAssetCarouselDrag);
  window.removeEventListener("blur", cancelAssetCarouselDrag);
  if (!drag.moved && drag.previewId) {
    openGeneratedImage(drag.previewId);
    return;
  }
  const idleTime = performance.now() - drag.lastTime;
  const releaseVelocity = idleTime > 90 ? 0 : drag.velocity;
  if (!drag.moved || Math.abs(releaseVelocity) < 0.035) return;
  const start = drag.element.scrollLeft;
  const maximum = Math.max(0, drag.element.scrollWidth - drag.element.clientWidth);
  const travel = releaseVelocity * Math.min(320, 150 + Math.abs(releaseVelocity) * 110);
  const destination = Math.max(0, Math.min(maximum, start + travel));
  const duration = Math.max(160, Math.min(520, 190 + Math.abs(releaseVelocity) * 150));
  const startedAt = performance.now();
  const animateMomentum = (now:number) => {
    const progress = Math.min(1, (now - startedAt) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    drag.element.scrollLeft = start + (destination - start) * eased;
    if (progress < 1) assetCarouselMomentumFrame = window.requestAnimationFrame(animateMomentum);
    else assetCarouselMomentumFrame = 0;
  };
  assetCarouselMomentumFrame = window.requestAnimationFrame(animateMomentum);
}
function cancelAssetCarouselDrag() {
  const drag = assetCarouselDrag;
  if (drag?.element.hasPointerCapture(drag.pointerId)) drag.element.releasePointerCapture(drag.pointerId);
  assetCarouselDrag = undefined;
  window.removeEventListener("pointerup", endAssetCarouselDrag);
  window.removeEventListener("pointercancel", endAssetCarouselDrag);
  window.removeEventListener("blur", cancelAssetCarouselDrag);
}
function openAssetCarouselImage(previewId?:string) {
  if (previewId && Date.now() > assetCarouselDraggedUntil) openGeneratedImage(previewId);
}

function turnLightbox(step: number) {
  const total = lightboxAssets.value.length;
  if (!total) return;
  lightboxScale.value = 1;
  lightboxFitScale.value = 1;
  lightboxOffset.value = { x:0, y:0 };
  lightboxIndex.value = (lightboxIndex.value + step + total) % total;
}

function runSearch() {
  notify(searchTerm.value.trim() ? `正在搜索：${searchTerm.value.trim()}` : "请输入搜索内容");
}

async function sendMessage() {
  const value = input.value.trim();
  if ((!value && !stagedAssets.value.length) || chatHistoryLoading.value) return;
  const project = activeProjectRecord.value;
  if (!project || chatProjectId.value !== project.id) return;
  const session = projectSession;
  const requestStartedAt = Date.now();
  const assets = [...stagedAssets.value];
  chats.value.push({ side: "right", text: value || `发送 ${assets.length} 个素材`, media: assets.length ? assets : undefined, createdAt:requestStartedAt });
  input.value = "";
  stagedAssets.value = [];
  await scrollChat();
  void processAssistantMessage(value, assets, project, session, requestStartedAt);
}

async function waitForAgentJob(jobId:string, controller:AbortController, label:string) {
  const deadline = Date.now() + 31 * 60 * 1000;
  while (Date.now() < deadline) {
    if (controller.signal.aborted) throw new DOMException("Aborted", "AbortError");
    const job = await assistantService.agentStatus<AgentJobResponse>(jobId, controller.signal);
    if (job.status === "completed" && job.result) return job.result;
    if (job.status === "failed") throw new Error(job.error || `${label}执行失败`);
    thinking.value = `${label}正在${job.status === "queued" ? "排队" : "执行"}·心跳正常`;
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(resolve, 2000);
      controller.signal.addEventListener("abort", () => { window.clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); }, { once:true });
    });
  }
  throw new Error(`${label}执行超过31分钟，任务已释放`);
}

async function processAssistantMessage(value:string, assets:UploadAsset[], project:StoredProject, session:number, requestStartedAt:number) {
  if (!isCurrentProjectSession(project.id, session)) return;
  const controller = new AbortController();
  assistantController.value = controller;
  thinking.value = assets.length ? "正在识别图片和视频" : "正在理解指令并匹配当前项目资源";
  startThinkingTimer();
  if (assets.length) {
    try {
      const descriptions = [];
      for (const asset of assets) descriptions.push(await inspectAsset(asset, value, controller.signal));
      if (project && !isCurrentProjectSession(project.id, session)) return;
      thinking.value = "";
      stopThinkingTimer();
      await pushAssistantTyped(descriptions.join("\n\n"), (Date.now() - requestStartedAt) / 1000);
    } catch (error) {
      if (controller.signal.aborted) return;
      thinking.value = "";
      stopThinkingTimer();
      await pushAssistantTyped(`识别失败：${error instanceof Error ? error.message : "本地识别服务异常"}`, (Date.now() - requestStartedAt) / 1000);
    } finally {
      thinking.value = "";
      stopThinkingTimer();
      await scrollChat();
      if (assistantController.value === controller) assistantController.value = undefined;
    }
    return;
  }
  const explicitlyMentionedAgent = mentionAgents.find(agent => value.includes(`@${agent.label}`));
  const requestsLocalProjectFiles = /(?:(?:调取|读取|查看|检查|分析|搜索|打开|修改|修复).*(?:本地|项目).*(?:文件|代码)|(?:本地|项目).*(?:文件|代码).*(?:调取|读取|查看|检查|分析|搜索|打开|修改|修复)|能否?.*(?:调取|读取|访问).*(?:本地|项目).*(?:文件|代码))/u.test(value);
  let mentionedAgent = explicitlyMentionedAgent || (requestsLocalProjectFiles ? mentionAgents[0] : undefined);
  if (!mentionedAgent) {
    try {
      const route = await assistantService.route<AgentRouteResponse>({
        message:value,
        context:{
          ...assistantContext(project),
          recent_messages:chats.value.slice(0, -1).slice(-16).map(chat => ({ role:chat.side === "right" ? "user" : "assistant", text:chat.text })),
        },
      }, controller.signal);
      if (route.execute) mentionedAgent = mentionAgents.find(agent => agent.id === route.agent);
    } catch {
      mentionedAgent = undefined;
    }
  }
  if (mentionedAgent) {
    thinking.value = mentionedAgent.id === "main_developer" ? "主力开发正在执行任务" : mentionedAgent.id === "software_tester" ? "软件测试正在执行增量测试" : "代码稽查正在只读检查";
    startThinkingTimer();
    try {
      const task = value.replace(new RegExp(`@${mentionedAgent.label}`, "g"), "").trim();
      if (!task) throw new Error(`请输入要交给${mentionedAgent.label}的任务`);
      const started = await assistantService.startAgent<AgentJobResponse>({
        agent:mentionedAgent.id,
        task,
        request_id:`${project.id}:${requestStartedAt}`,
        context:{
          ...assistantContext(project),
          recent_messages:chats.value.slice(0, -1).slice(-16).map(chat => ({ role:chat.side === "right" ? "user" : "assistant", text:chat.text })),
        },
      }, controller.signal);
      const result = await waitForAgentJob(started.job_id, controller, mentionedAgent.label);
      if (!isCurrentProjectSession(project.id, session)) return;
      await pushAssistantTyped(`@${result.agent}\n${result.reply}`, (Date.now() - requestStartedAt) / 1000);
    } catch (error) {
      if (controller.signal.aborted) return;
      await pushAssistantTyped(`执行失败：${error instanceof Error ? error.message : "系统 AI 执行异常"}`, (Date.now() - requestStartedAt) / 1000);
    } finally {
      thinking.value = "";
      stopThinkingTimer();
      await scrollChat();
      if (assistantController.value === controller) assistantController.value = undefined;
    }
    return;
  }
  const localDuration = (Date.now() - requestStartedAt) / 1000;
  thinking.value = "";
  stopThinkingTimer();
  if (await applyImageGenerationInstruction(value, project, controller.signal, requestStartedAt)) return scrollChat();
  if (await applyScopeInstruction(value, localDuration)) return scrollChat();
  if (await applyResourceQuery(value, localDuration)) return scrollChat();
  const localContextQuestion = /(?:当前|现在)(?:项目|资源|分镜|任务|剧本|大纲|卡片|页面|生成)/i.test(value);
  const needsWebSearch = webSearchEnabled.value || /(?:联网|网上|全网|搜索|搜一下|查一下|查找|官网|网页|新闻|来源|网址)/i.test(value) || (/(?:最新|最近|今天|截至|价格|版本|许可|授权|商用)/i.test(value) && !localContextQuestion);
  thinking.value = needsWebSearch ? "正在联网搜索并核验来源" : "正在理解指令并匹配当前项目资源";
  startThinkingTimer();
  try {
    const result = await assistantService.understand<AssistantResponse>({
      message: value,
      ...(webSearchEnabled.value ? { web_search:true } : {}),
      model:selectedAssistantModel.value || undefined,
      context: {
        ...assistantContext(project),
        recent_messages: chats.value.slice(0, -1).slice(-16).map((chat) => ({ role: chat.side === "right" ? "user" : "assistant", text:`${chat.text}${chat.media?.length ? `（包含${chat.media.length}个${chat.media.some(asset => asset.mediaType === "image") ? "图片" : "视频"}素材）` : ""}` })),
      },
    }, controller.signal);
    if (project && !isCurrentProjectSession(project.id, session)) return;
    thinking.value = "";
    stopThinkingTimer();
    await pushAssistantTyped(result.reply || "本地 AI 未返回内容", (Date.now() - requestStartedAt) / 1000);
  } catch (error) {
    if (controller.signal.aborted) return;
    thinking.value = "";
    stopThinkingTimer();
    await pushAssistantTyped(`回复失败：${error instanceof Error ? error.message : "本地 AI 服务异常"}`, (Date.now() - requestStartedAt) / 1000);
  } finally {
    thinking.value = "";
    stopThinkingTimer();
    await scrollChat();
    if (assistantController.value === controller) assistantController.value = undefined;
  }
}

function isExplicitImageGenerationInstruction(value:string) {
  const compact = value.replace(/\s+/g, "");
  if (/(?:查看|打开|调取|放大|分析|识别|删除|替换|修改|修复).*(?:图|图片|图像)/.test(compact)) return false;
  return /(?:生成|画|做|来)(?:一|个|张|幅|点|些|随便|随机|任意)*(?:图|图片|图像)|(?:图|图片|图像).*(?:生成|画|做)/.test(compact);
}

function assistantImagePrompt(value:string, project:StoredProject) {
  const cleaned = value
    .replace(/(?:请|麻烦|帮我|给我|随便|随机|任意|生成|画|做|来|一张|一个|一幅|图片|图像|图)/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return cleaned || `${project.style || "电影感"}短剧画面，主体明确，构图完整，光影自然，高清细节，9:16竖幅，无文字、商标、二维码和水印`;
}

function latestGeneratedImageContext() {
  for (let index = chats.value.length - 1; index >= 0; index -= 1) {
    const chat = chats.value[index];
    const image = chat.side === "left" ? chat.media?.find(asset => asset.mediaType === "image") : undefined;
    if (!image) continue;
    const sourceRequest = [...chats.value.slice(0, index)].reverse().find(item => item.side === "right" && item.text.trim());
    return { image, sourceRequest:sourceRequest?.text.trim() || "" };
  }
  return null;
}

function isImageContinuationInstruction(value:string, context:ReturnType<typeof latestGeneratedImageContext>) {
  if (!context) return false;
  const compact = value.replace(/\s+/g, "");
  return /(?:脸|脸型|五官|眼睛|鼻子|嘴|头发|发型|身材|体型|胖|瘦|衣服|服装|背景|光线|色彩|颜色|姿势|构图|人物).*(?:太|更|改|换|调整|修|一点|一些|不对|不像|不好)|(?:太胖|太瘦|胖了|瘦了|大了|小了|不好看|不像|不对)/.test(compact);
}

async function applyImageGenerationInstruction(value:string, project:StoredProject, signal:AbortSignal, requestStartedAt:number) {
  const continuation = latestGeneratedImageContext();
  const continuingImage = isImageContinuationInstruction(value, continuation);
  if (!isExplicitImageGenerationInstruction(value) && !continuingImage) return false;
  thinking.value = "正在生成图片";
  startThinkingTimer();
  try {
    const plan = continuingImage
      ? { count:1, shared_prompt:`基于上一张已生成图片继续修改。原始生成要求：${assistantImagePrompt(continuation?.sourceRequest || "", project)}。当前唯一修改要求：${value.trim()}。必须保持同一人物身份、服装、姿势、构图、背景和画面风格，只修改用户本次明确指出的部分。`, views:["保持上一张视角和构图"], negative_prompt:"文字、商标、二维码、水印、拼图、多视图" }
      : await assistantService.imagePlan<{ count:number; shared_prompt:string; views:string[]; negative_prompt:string }>({ message:value, project_style:project.style }, signal);
    const views = plan.views.slice(0, Math.max(1, Math.min(8, plan.count || plan.views.length || 1)));
    const generatedAssets:UploadAsset[] = [];
    let baselineUrl = continuingImage && continuation ? continuation.image.url : "";
    for (let index = 0; index < views.length; index += 1) {
      thinking.value = views.length > 1 ? `正在生成第 ${index + 1}/${views.length} 张图片` : "正在生成图片";
      const view = views[index];
      const prompt = `${plan.shared_prompt}。本次只生成一张独立图片，当前唯一视角：${view}。画面内只能出现一个连续完整画面，禁止拼图、分屏、接触表、多宫格、多视角并列、局部裁切和额外人物。9:16竖幅，主体完整，严格遵循用户描述。负面约束：${plan.negative_prompt || "文字、商标、二维码、水印、畸变"}。`;
      const jobName = `chat_${project.id}_${Date.now()}_${index + 1}`;
      const references = baselineUrl ? [{ name:index === 0 ? "上一张生成图" : "首张人物基准图", url:baselineUrl }] : [];
      const result = await generateAssistantImageWithRecovery({
        ...productionTaskContext(project), name:jobName, prompt, orientation:"portrait", width:928, height:1664,
        references, reference_strategy:references.length ? "identity_and_pose" : "none",
      }, jobName, signal);
      if (!baselineUrl) baselineUrl = result.image.url;
      generatedAssets.push({ id:`chat-image-${crypto.randomUUID()}`, name:`生成的图片-${index + 1}`, url:result.image.url, mediaType:"image", scope:"临时参考", label:view, aspect:"portrait" });
    }
    uploadedAssets.value = [...uploadedAssets.value, ...generatedAssets];
    lastBatch.value = generatedAssets;
    chats.value.push({ side:"left", text:`已按要求生成 ${generatedAssets.length} 张独立图片。`, media:generatedAssets, createdAt:Date.now(), durationSeconds:(Date.now() - requestStartedAt) / 1000 });
  } catch (error) {
    if (signal.aborted) return true;
    await pushAssistantTyped(`图片生成失败：${error instanceof Error ? error.message : "本地图片服务异常"}`, (Date.now() - requestStartedAt) / 1000);
  } finally {
    thinking.value = "";
    stopThinkingTimer();
    await scrollChat();
  }
  return true;
}

async function generateAssistantImageWithRecovery(payload:Record<string, unknown>, jobName:string, signal:AbortSignal) {
  type ImageResult = { image:{ url:string } };
  let directResult:ImageResult | undefined;
  let directError:unknown;
  let directSettled = false;
  void assetService.generateAssistantImage<ImageResult>(payload, signal, "图片生成失败")
    .then(result => { directResult = result; directSettled = true; })
    .catch(error => { directError = error; directSettled = true; });
  const deadline = Date.now() + 15 * 60 * 1000;
  while (Date.now() < deadline) {
    if (signal.aborted) throw new DOMException("图片生成已停止", "AbortError");
    if (directResult) return directResult;
    const claimed = await assetService.characterResult<ImageResult & { status?:string; error?:string }>(jobName).catch(() => null);
    if (claimed?.ok && claimed.status === 200 && claimed.data.image?.url) return claimed.data;
    if (claimed && claimed.status >= 500) throw new Error(claimed.data.error || "图片生成失败");
    if (directSettled && directError && claimed?.status === 404) throw directError;
    await new Promise<void>(resolve => window.setTimeout(resolve, 2_000));
  }
  if (directError) throw directError;
  throw new Error("图片生成超过15分钟，任务已退出等待，可从任务中心领取结果");
}

function handleComposerKeydown(event:KeyboardEvent) {
  if (mentionMenuOpen.value) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const direction = event.key === "ArrowDown" ? 1 : -1;
      activeMentionIndex.value = (activeMentionIndex.value + direction + mentionCandidates.value.length) % mentionCandidates.value.length;
      return;
    }
    if ((event.key === "Enter" || event.key === "Tab") && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      selectMentionAgent(mentionCandidates.value[activeMentionIndex.value] || mentionCandidates.value[0]);
      return;
    }
    if (event.key === "Escape") { event.preventDefault(); input.value = input.value.replace(/@[^\s@]*$/, ""); return; }
  }
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  void sendMessage();
}

function selectMentionAgent(agent:MentionAgent) {
  input.value = input.value.replace(/@[^\s@]*$/, `@${agent.label} `);
  activeMentionIndex.value = 0;
  nextTick(() => document.querySelector<HTMLTextAreaElement>(".composer-shell > textarea")?.focus());
}

function seekVideo(video: HTMLVideoElement, time: number, timeoutMs = 15_000) {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(() => { cleanup(); reject(new Error("视频定位读取超时")); }, timeoutMs);
    const cleanup = () => { window.clearTimeout(timer); video.removeEventListener("seeked", done); video.removeEventListener("error", failed); };
    const done = () => { cleanup(); resolve(); };
    const failed = () => { cleanup(); reject(new Error("视频抽帧失败")); };
    video.addEventListener("seeked", done, { once: true });
    video.addEventListener("error", failed, { once: true });
    video.currentTime = time;
  });
}

async function extractVideoFrames(file: File) {
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.preload = "metadata";
  video.muted = true;
  video.src = url;
  try {
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => { video.onloadedmetadata = null; video.onerror = null; reject(new Error(`视频读取超过 30 秒：${file.name}`)); }, 30_000);
      video.onloadedmetadata = () => { window.clearTimeout(timer); resolve(); };
      video.onerror = () => { window.clearTimeout(timer); reject(new Error(`无法读取视频 ${file.name}`)); };
    });
    if (!Number.isFinite(video.duration) || video.duration <= 0 || !video.videoWidth || !video.videoHeight) throw new Error("视频时长或画面尺寸无效");
    const scale = Math.min(1, 1280 / Math.max(video.videoWidth, video.videoHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
    canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("浏览器不支持视频抽帧");
    const frames: string[] = [];
    for (const ratio of [0.1, 0.35, 0.65, 0.9]) {
      await seekVideo(video, Math.min(video.duration - 0.01, Math.max(0, video.duration * ratio)));
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      frames.push(canvas.toDataURL("image/jpeg", 0.82));
    }
    return frames;
  } finally {
    URL.revokeObjectURL(url);
    video.removeAttribute("src");
    video.load();
  }
}

async function inspectAsset(asset: UploadAsset, instruction: string, signal?:AbortSignal) {
  if (!asset.file) throw new Error(`无法读取 ${asset.name} 的原始文件`);
  if (asset.mediaType === "audio") {
    const audio = await assistantService.transcribe<{ transcript:string }>(asset.file, signal);
    return `${asset.name}（音频）\n声音转写：${audio.transcript}`;
  }
  const images = asset.mediaType === "video" ? await extractVideoFrames(asset.file) : [await readFileAsDataUrl(asset.file)];
  const vision = await assistantService.vision<VisionResponse>({ media_type:asset.mediaType, filename:asset.name, prompt:instruction || "请识别人物、场景、动作、文字和关键细节。", images }, signal);
  const audio = asset.mediaType === "video"
    ? await assistantService.transcribe<{ transcript:string }>(asset.file, signal).catch(error => ({ transcript:`无法识别声音：${error instanceof Error ? error.message : "声音识别失败"}` }))
    : undefined;
  return `${asset.name}（${asset.mediaType === "video" ? "视频" : "图片"}）\n画面识别：${vision.description}${audio ? `\n声音转写：${audio.transcript}` : ""}`;
}

async function scrollChat() {
  await nextTick();
  chatScroll.value?.scrollTo({ top: chatScroll.value.scrollHeight, behavior: "smooth" });
}

async function applyScopeInstruction(value: string, durationSeconds: number) {
  if (!lastBatch.value.length) return false;
  const assets = /全部|这些|本批/.test(value) ? lastBatch.value : [lastBatch.value[lastBatch.value.length - 1]];
  if (/全局|所有项目/.test(value)) {
    await Promise.all(assets.map(asset => persistAssetResource(asset, "tenant_global")));
    assets.forEach((asset) => { asset.scope = "全局公共"; asset.label = "全局"; });
    dynamicGlobalNodes.value = [...new Set([...dynamicGlobalNodes.value, ...assets.map((asset) => asset.name)])];
    await loadResources();
    await pushAssistantTyped(`已保存至全局公共素材 > 人物定妆公共，共 ${assets.length} 项，后续所有项目均可调用。`, durationSeconds);
    selectedNode.value = "人物定妆公共";
    rightPanelTitle.value = "全局公共素材 · 人物定妆公共";
    return true;
  }
  if (/本项目/.test(value) && /保存|素材|定妆|场景/.test(value)) {
    await Promise.all(assets.map(asset => persistAssetResource(asset, "project")));
    assets.forEach((asset) => { asset.scope = "本集私有"; asset.label = "项目"; });
    await loadResources();
    await pushAssistantTyped(`已保存至【${activeProjectRecord.value?.name || "当前项目"}】项目资源，共 ${assets.length} 项。`, durationSeconds);
    selectedNode.value = activeProjectRecord.value?.name || "项目";
    rightPanelTitle.value = `项目资源｜${activeProjectRecord.value?.name || "当前项目"}`;
    return true;
  }
  if (/本集|第\s*0?\d+集/.test(value) && /保存|素材|定妆|场景/.test(value)) {
    await Promise.all(assets.map(asset => persistAssetResource(asset, "project_episode")));
    assets.forEach((asset) => { asset.scope = "本集私有"; asset.label = "本集"; });
    dynamicEpisodeNodes.value = [...new Set([...dynamicEpisodeNodes.value, ...assets.map((asset) => asset.name)])];
    await pushAssistantTyped(`已保存至【${activeProjectRecord.value?.name || "当前项目"} - 第${String(workflowEpisode.value).padStart(2, "0")}集】> 定妆素材，共 ${assets.length} 项。`, durationSeconds);
    selectedNode.value = "定妆素材";
    rightPanelTitle.value = `本集素材｜${activeProjectRecord.value?.name || "当前项目"} · 第${String(workflowEpisode.value).padStart(2, "0")}集`;
    await loadResources();
    return true;
  }
  if (/仅本次|不要存|临时/.test(value)) {
    assets.forEach((asset) => { asset.scope = "临时参考"; asset.label = "临时"; });
    await pushAssistantTyped("已设为临时参考，仅本次对话生成使用，不存入素材库。", durationSeconds);
    return true;
  }
  return false;
}

async function applyResourceQuery(value: string, durationSeconds: number) {
  if (!/(看看|查看|调取|给我看)/.test(value)) return false;
  if (/全局.*人物|人物.*全局/.test(value)) {
    selectedNode.value = "人物定妆公共"; rightPanelMode.value = "images"; rightPanelTitle.value = "全局公共素材 · 人物定妆公共";
    await pushAssistantTyped(`已为你调取全局人物定妆库，共 ${Math.max(1, dynamicGlobalNodes.value.length)} 项，右侧已切换预览。`, durationSeconds);
  } else if (/剧本/.test(value)) {
    selectedNode.value = "剧本"; rightPanelMode.value = "script"; rightPanelTitle.value = `剧本｜${activeProjectRecord.value?.name || "当前项目"} · 第${String(workflowEpisode.value).padStart(2, "0")}集`;
    await pushAssistantTyped(`已打开【${activeProjectRecord.value?.name || "当前项目"} - 第${String(workflowEpisode.value).padStart(2, "0")}集】剧本，右侧可查看和编辑。`, durationSeconds);
  } else if (/分镜/.test(value) && !/视频/.test(value)) {
    selectedNode.value = "分镜"; rightPanelMode.value = "storyboard"; rightPanelTitle.value = `分镜脚本｜${activeProjectRecord.value?.name || "当前项目"} · 第${String(workflowEpisode.value).padStart(2, "0")}集`;
    await pushAssistantTyped(`已调取第${String(workflowEpisode.value).padStart(2, "0")}集分镜，右侧已切换分镜表格。`, durationSeconds);
  } else if (/视频/.test(value)) {
    selectedNode.value = "分镜视频"; rightPanelMode.value = "video"; rightPanelTitle.value = `分镜视频｜${activeProjectRecord.value?.name || "当前项目"} · 第${String(workflowEpisode.value).padStart(2, "0")}集`;
    await pushAssistantTyped(`已调取第${String(workflowEpisode.value).padStart(2, "0")}集分镜视频，右侧已切换视频预览。`, durationSeconds);
  } else if (/图|图片|生图/.test(value)) {
    selectedNode.value = "生图输出"; rightPanelMode.value = "images"; rightPanelTitle.value = `生图输出｜${activeProjectRecord.value?.name || "当前项目"} · 第${String(workflowEpisode.value).padStart(2, "0")}集`;
    await pushAssistantTyped(`已调取【${activeProjectRecord.value?.name || "当前项目"} - 第${String(workflowEpisode.value).padStart(2, "0")}集】生图输出。`, durationSeconds);
  } else return false;
  selectedEpisode.value = `第${String(workflowEpisode.value).padStart(2, "0")}集`;
  return true;
}

function inferScopeFromText(): AssetScope {
  if (/全局|所有项目/.test(input.value)) return "全局公共";
  if (/本集|第0?3集|只给本集/.test(input.value)) return "本集私有";
  return "临时参考";
}

function detectAssetAspect(file: File): Promise<"portrait" | "landscape"> {
  return new Promise((resolve) => {
    if (file.type.startsWith("audio/")) { resolve("landscape"); return; }
    const url = URL.createObjectURL(file);
    const media = file.type.startsWith("video/") ? document.createElement("video") : new Image();
    const finish = (width: number, height: number) => { URL.revokeObjectURL(url); resolve(width >= height ? "landscape" : "portrait"); };
    if (media instanceof HTMLVideoElement) {
      media.onloadedmetadata = () => finish(media.videoWidth, media.videoHeight);
      media.onerror = () => finish(9, 16);
      media.src = url;
    } else {
      media.onload = () => finish(media.naturalWidth, media.naturalHeight);
      media.onerror = () => finish(9, 16);
      media.src = url;
    }
  });
}

async function handleFiles(files: FileList | File[]) {
  const accepted:File[] = [];
  for (const file of Array.from(files)) {
    const validationError = await validateMediaFile(file);
    if (validationError) { notify(validationError); continue; }
    accepted.push(file);
  }
  if (!accepted.length) return;
  const scope = inferScopeFromText();
  const aspects = await Promise.all(accepted.map(detectAssetAspect));
  const persistentUrls = await Promise.all(accepted.map(file => file.type.startsWith("image/") ? readFileAsDataUrl(file) : Promise.resolve(URL.createObjectURL(file))));
  const batch = accepted.map((file, index): UploadAsset => ({
    id: `upload-${Date.now()}-${index}`,
    name: file.name,
    url: persistentUrls[index],
    mediaType: file.type.startsWith("video/") ? "video" : file.type.startsWith("audio/") ? "audio" : "image",
    scope,
    label: scope === "临时参考" ? "临时" : scope === "全局公共" ? "全局" : "本集",
    aspect: aspects[index],
    file,
  }));
  stagedAssets.value.push(...batch);
  lastBatch.value = batch;
  const message = scope === "临时参考"
    ? "上传完成｜附件仅显示在当前对话，可指定：加入全局库 / 保存为本集素材。"
    : scope === "全局公共"
      ? "已保存至全局公共素材 > 人物定妆公共，后续所有项目均可调用。"
      : `已保存至【${activeProjectRecord.value?.name || "当前项目"} - 第${String(workflowEpisode.value).padStart(2, "0")}集】> 定妆素材。`;
  notify(message);
  if (scope === "全局公共") dynamicGlobalNodes.value.push(...batch.map((asset) => asset.name));
  if (scope === "本集私有") dynamicEpisodeNodes.value.push(...batch.map((asset) => asset.name));
  void scrollChat();
}

async function onFileInputChange(event: Event) {
  const target = event.target as HTMLInputElement;
  const files = target.files ? Array.from(target.files) : [];
  target.value = "";
  if (files.length) await handleFiles(files);
}

function onDrop(event: DragEvent) {
  isDragging.value = false;
  if (event.dataTransfer?.files.length) handleFiles(event.dataTransfer.files);
}

function onPaste(event: ClipboardEvent) {
  const files = Array.from(event.clipboardData?.files ?? []);
  if (files.length) { event.preventDefault(); handleFiles(files); }
}

function regenerate() {
  selectedImage.value = 0;
  notify("已重新提交生图任务");
}

function markAssetPassed(asset: UploadAsset) {
  if (asset.label !== "通过") return;
  asset.label = "OK";
  notify("该图片已标记为通过");
}

function regenerateAsset(asset: UploadAsset, event?: Event) {
  const card = (event?.currentTarget as Element | null)?.closest(".preview-card");
  const popupWidth = Math.min(660, window.innerWidth - 32);
  const popupHeight = 112;
  if (card) {
    const rect = card.getBoundingClientRect();
    const right = rect.right + 14;
    const left = rect.left - popupWidth - 14;
    regeneratePosition.value = {
      left:right + popupWidth <= window.innerWidth - 16 ? right : Math.max(16, left),
      top:Math.max(16, Math.min(window.innerHeight - popupHeight - 16, rect.top + (rect.height - popupHeight) / 2)),
    };
  }
  regenerateTarget.value = asset;
  regeneratePrompt.value = "";
  regenerateReference.value = undefined;
}

async function onRegenerateFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  const validationError = await validateMediaFile(file);
  if (validationError) return notify(validationError);
  regenerateReference.value = { name:file.name, url:await readFileAsDataUrl(file) };
}

function submitRegenerate() {
  if (!regenerateTarget.value || (!regeneratePrompt.value.trim() && !regenerateReference.value)) return;
  notify(`已重新提交：${regenerateTarget.value.name}`);
  regenerateTarget.value = undefined;
  regeneratePrompt.value = "";
  regenerateReference.value = undefined;
}

function collapsePreview() {
  previewClosing.value = true;
  window.setTimeout(() => {
    previewCollapsed.value = true;
    previewClosing.value = false;
  }, 220);
}

async function expandPreview() {
  previewOpening.value = true;
  previewCollapsed.value = false;
  await nextTick();
  requestAnimationFrame(() => {
    previewOpening.value = false;
  });
}

const workspaceColumns = computed(() => {
  const available = Math.max(320, viewportWidth.value);
  const previewHidden = previewCollapsed.value || previewClosing.value || previewOpening.value || available <= 760;
  if (previewHidden) {
    const left = Math.min(leftPanelWidth.value, Math.max(180, available * 0.3));
    return `${Math.round(left)}px minmax(0, 1fr) 0px`;
  }
  const right = Math.min(rightPanelWidth.value, Math.max(240, available * 0.32));
  const left = Math.min(leftPanelWidth.value, Math.max(180, available - right - 320));
  return `${Math.round(left)}px minmax(0, 1fr) ${Math.round(right)}px`;
});

function startPanelResize(side: "left" | "right", event: PointerEvent) {
  event.preventDefault();
  const startX = event.clientX;
  const startLeft = leftPanelWidth.value;
  const startRight = rightPanelWidth.value;
  resizingPanel.value = side;
  const move = (moveEvent: PointerEvent) => {
    if (side === "left") leftPanelWidth.value = Math.min(420, Math.max(220, startLeft + moveEvent.clientX - startX));
    else rightPanelWidth.value = Math.min(560, Math.max(260, startRight + startX - moveEvent.clientX));
  };
  const stop = () => {
    resizingPanel.value = null;
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", stop);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", stop, { once: true });
}

function startProjectTabsDrag(event: PointerEvent) {
  const element = projectTabs.value;
  if (!element) return;
  const startX = event.clientX;
  const startScrollLeft = element.scrollLeft;
  let moved = false;
  element.setPointerCapture(event.pointerId);
  element.classList.add("dragging");
  const move = (moveEvent: PointerEvent) => {
    const delta = moveEvent.clientX - startX;
    if (Math.abs(delta) > 3) moved = true;
    element.scrollLeft = startScrollLeft - delta;
  };
  const stop = () => {
    element.classList.remove("dragging");
    element.removeEventListener("pointermove", move);
    element.removeEventListener("pointerup", stop);
    element.removeEventListener("pointercancel", stop);
    if (moved) element.dataset.justDragged = "true";
    window.setTimeout(() => delete element.dataset.justDragged, 0);
  };
  element.addEventListener("pointermove", move);
  element.addEventListener("pointerup", stop);
  element.addEventListener("pointercancel", stop);
}

function selectProjectTab(tab: string) {
  if (projectTabs.value?.dataset.justDragged) return;
  selectProject(tab);
}

function selectProject(projectName:string) {
  abortProjectWork();
  activeTab.value = projectName;
  const project = projectRecords.value.find(item => item.name === projectName);
  if (project) appRuntime.projectStore.select(project.id);
  isolateChatProject(project || null);
  if (project && !projectEpisodeOptions.value.includes(selectedEpisode.value)) selectedEpisode.value = projectEpisodeOptions.value[0] || "";
  rightPanelTitle.value = project ? `${activeWorkflowNavigation.value}｜${project.name}${selectedEpisode.value ? ` · ${selectedEpisode.value}` : ""}` : "";
  void loadProjectFlowState();
  const session = projectSession;
  void Promise.all([loadResources(project, session), loadTasks(project, session), loadProjectVersions(project, session)]);
}

function resetProjectFlowProjection(session:number) {
  void loadOutlineState(null, session);
  void loadScriptState(null, session);
  void loadStoryboardState(null, session);
  void loadAssetState(null, session);
  void loadShotImageState(null, session);
  void loadShotVideoState(null, session);
  void loadMergeState(null, session);
  void loadFinalAuditState(null, session);
  void loadUpscaleState(null, session);
  void loadExportState(null, session);
}

async function loadProjectFlowState() {
  const project = activeProjectRecord.value;
  if (!project) return;
  const session = projectSession;
  resetProjectFlowProjection(session);
  projectLoadIsolation.begin(project.id, session);
  if (chatProjectId.value !== project.id) isolateChatProject(project);
  await loadSkillBindings(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadOutlineState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadScriptState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadStoryboardState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadAssetState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadShotImageState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadShotVideoState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadMergeState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadFinalAuditState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadUpscaleState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadExportState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await loadChatHistory(project, session);
  if (storyboardStatus.value === "confirmed" && storyboardShots.value.length && !characterProfiles.value.length && !sceneProfiles.value.length && !propProfiles.value.length) {
    await seedAssetCardsFromStoryboard(project, storyboardShots.value, session);
    if (!isCurrentProjectSession(project.id, session)) return;
    assetError.value = "资产框架已恢复，请点击提取完整人物、道具和场景档案";
  }
  const resumeStages = projectLoadIsolation.consume(project.id, session);
  applyInterruptedStageRecovery(resumeStages);
}

function applyInterruptedStageRecovery(stages:string[]) {
  const interrupted = new Set(stages);
  if (interrupted.has("outline")) { outlineStatus.value = "failed"; outlineError.value = "上次大纲任务已中断，请点击继续生成"; }
  if (interrupted.has("script")) { scriptStatus.value = "failed"; scriptError.value = "上次剧本任务已中断，请点击继续生成"; }
  if (interrupted.has("storyboard")) { storyboardStatus.value = "failed"; storyboardError.value = "上次分镜任务已中断，请点击继续生成"; }
  if (interrupted.has("assets")) { assetStatus.value = "pending"; assetError.value = "上次资产任务已中断，请点击生成图片继续"; }
  if (interrupted.has("shot_images")) { shotImageStatus.value = "pending"; shotImageError.value = "上次分镜画面任务已中断，请点击继续生成"; }
  if (interrupted.has("shot_videos")) { shotVideoStatus.value = "pending"; shotVideoError.value = "上次分镜视频任务已中断，请点击继续生成"; }
  if (interrupted.has("merged_episodes")) { mergeStatus.value = "pending"; mergeError.value = "上次合片任务已中断，请点击继续合片"; }
  if (interrupted.has("final_audit")) { finalAuditStatus.value = "pending"; finalAuditError.value = "上次成片审核已中断，请点击继续审核"; }
  if (interrupted.has("upscale")) { upscaleStatus.value = "pending"; upscaleError.value = "上次超分任务已中断，请点击继续超分"; }
  if (interrupted.has("export")) { exportStatus.value = "pending"; exportError.value = "上次导出任务已中断，请点击继续导出"; }
}

type OutlineStageData = { plan:OutlinePlan | null; episodes:EpisodeOutline[]; status:"idle" | "generating" | "waiting_confirmation" | "confirmed" | "failed"; error:string; audit:OutlineAudit | null; audit_stopped?:boolean; generation_id?:string; phase?:typeof outlinePhase.value; revisions?:OutlineRevision[]; review_plan?:OutlinePlan | null; review_episodes?:EpisodeOutline[]; generation_started_at?:number; generation_elapsed_seconds?:number };

async function loadOutlineState(project = activeProjectRecord.value, session = projectSession) {
  resetGenerationTimerState();
  generatedEpisodeCount.value = 0;
  outlinePlan.value = null;
  outlineEpisodes.value = [];
  outlineStatus.value = "idle";
  outlineError.value = "";
  outlineAudit.value = null;
  outlineAuditStopped.value = false;
  outlineGenerationId.value = "";
  outlinePhase.value = "";
  outlineRevisions.value = [];
  outlineReviewPlan.value = null;
  outlineReviewEpisodes.value = [];
  outlineThinking.value = false;
  outlineTypedTitle.value = "";
  outlineTypedPlan.value = "";
  outlineTypedEpisodes.value = {};
  outlinePendingEpisode.value = null;
  if (!project) return;
  try {
    const result = await projectService.readStage<OutlineStageData>({ ...projectIdentity, id:project.id, stage:"outline" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    outlinePlan.value = result.stage.data.plan;
    outlineEpisodes.value = result.stage.data.episodes || [];
    outlineGenerationId.value = result.stage.data.generation_id || "";
    outlinePhase.value = result.stage.data.phase || (result.stage.data.status === "generating" ? "generating" : "");
    outlineRevisions.value = result.stage.data.revisions || [];
    outlineReviewPlan.value = result.stage.data.review_plan || null;
    outlineReviewEpisodes.value = result.stage.data.review_episodes || [];
    const restoredClock = restoreGenerationClock(
      result.stage.data.generation_started_at,
      result.stage.data.generation_elapsed_seconds,
      result.stage.data.status === "generating",
    );
    generationStartedAt.value = restoredClock.generationStartedAt;
    generationElapsedSeconds.value = restoredClock.generationElapsedSeconds;
    if (result.stage.data.status === "generating") {
      if (!generationStartedAt.value) generationStartedAt.value = Date.now() - generationElapsedSeconds.value * 1000;
      startGenerationTimer(false);
    }
    outlineTypedTitle.value = outlinePlan.value?.title || "";
    outlineTypedPlan.value = outlinePlan.value?.general_outline || "";
    outlineTypedEpisodes.value = Object.fromEntries(outlineEpisodes.value.map(episode => [episode.episode, { title:episode.title, synopsis:episode.synopsis }]));
    projectLoadIsolation.mark(project.id, session, "outline", result.stage.data.status === "generating");
    outlineAudit.value = result.stage.data.audit ? normalizeOutlineAudit(result.stage.data.audit) : null;
    outlineAuditStopped.value = Boolean(result.stage.data.audit_stopped) || /审核已停止/.test(result.stage.data.error || "");
    const completedSuccessfully = Boolean(outlinePlan.value)
      && outlineEpisodes.value.length === project.episode_count
      && outlineAudit.value?.status === "pass";
    outlineStatus.value = result.stage.data.status === "generating" ? "failed" : completedSuccessfully && ["failed", "waiting_confirmation"].includes(result.stage.data.status) ? "confirmed" : result.stage.data.status;
    outlineError.value = result.stage.data.status === "generating" ? "正在恢复未完成的大纲任务" : completedSuccessfully ? "" : result.stage.data.error || "";
    generatedEpisodeCount.value = outlineEpisodes.value.length;
  } catch (error) {
    outlineError.value = error instanceof Error ? error.message : "故事大纲加载失败";
  }
}

async function persistOutlineState(project = activeProjectRecord.value) {
  if (!project) return;
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"outline", data:{ plan:outlinePlan.value, episodes:outlineEpisodes.value, status:outlineStatus.value, error:outlineError.value, audit:outlineAudit.value, audit_stopped:outlineAuditStopped.value, generation_id:outlineGenerationId.value, phase:outlinePhase.value, revisions:outlineRevisions.value, review_plan:outlineReviewPlan.value, review_episodes:outlineReviewEpisodes.value, generation_started_at:generationStartedAt.value, generation_elapsed_seconds:generationElapsedSeconds.value } satisfies OutlineStageData });
}

let outlineProjectNameSyncToken = 0;
async function syncProjectNameFromOutline(rawTitle:string) {
  const title = rawTitle.trim();
  const project = activeProjectRecord.value;
  if (!title || !project || project.name === title) return;
  const token = ++outlineProjectNameSyncToken;
  const previousName = project.name;
  try {
    const result = await projectService.update({ ...project, name:title });
    if (token !== outlineProjectNameSyncToken || activeProjectRecord.value?.id !== project.id) return;
    const index = projectRecords.value.findIndex(item => item.id === project.id);
    if (index >= 0) projectRecords.value[index] = result.project;
    projectRecords.value = [...projectRecords.value];
    projects.value = projectRecords.value.map(item => item.name);
    activeTab.value = title;
    if (selectedNode.value === previousName) selectedNode.value = title;
    appRuntime.projectStore.replace(projectRecords.value, project.id);
    rightPanelTitle.value = `${activeWorkflowNavigation.value}｜${title}${selectedEpisode.value ? ` · ${selectedEpisode.value}` : ""}`;
  } catch (error) {
    notify(error instanceof Error ? error.message : "项目名称同步失败");
  }
}

async function commitOutlineTitle(event:FocusEvent) {
  const element = event.currentTarget as HTMLElement;
  const title = element.textContent?.trim() || "";
  if (!title || !outlinePlan.value) {
    element.textContent = outlinePlan.value?.title || "全剧故事大纲";
    return;
  }
  updateNarrativeDraft("outline", "outline:project:title", outlinePlan.value.title || "全剧故事大纲", { stage:"outline", scope_type:"project", scope_id:activeProjectRecord.value?.id || "" }, event);
}

watch(() => outlinePlan.value?.title || "", title => {
  if (title) void syncProjectNameFromOutline(title);
});

async function generateOutline(_resumeExisting = false) {
  if (!requireEnabledRobot("项目策划")) return;
  const project = activeProjectRecord.value;
  if (!project || outlineStatus.value === "generating") return;
  const controller = new AbortController(); outlineController.value?.abort(); outlineController.value = controller;
  outlineStatus.value = "generating"; outlinePhase.value = "generating"; outlineError.value = ""; outlineGenerationId.value = crypto.randomUUID(); startGenerationTimer(true);
  try {
    const duration = Math.round((project.duration_min + project.duration_max) / 2);
    const response = await productionLedgerService.runStage<{ plan:OutlinePlan; episodes:EpisodeOutline[]; audit:OutlineAudit | null }>({
      ...productionTaskContext(project), stage:"outline", audit_enabled:narrativeAuditEnabled.value, batch_size:NARRATIVE_AUDIT_BATCH_SIZE,
      context:{ ...productionTaskContext(project), generation_id:outlineGenerationId.value, topic:project.topic, style:project.style, language:project.language, episode_count:project.episode_count, duration },
    }, controller.signal);
    outlinePlan.value = response.result.plan; outlineEpisodes.value = response.result.episodes; outlineAudit.value = response.result.audit ? normalizeOutlineAudit(response.result.audit) : null;
    outlineTypedTitle.value = outlinePlan.value.title || ""; outlineTypedPlan.value = outlinePlan.value.general_outline; outlineTypedEpisodes.value = Object.fromEntries(outlineEpisodes.value.map(episode => [episode.episode, { title:episode.title, synopsis:episode.synopsis }])); generatedEpisodeCount.value = outlineEpisodes.value.length;
    outlineStatus.value = "waiting_confirmation"; outlinePhase.value = ""; stopGenerationTimer(); await persistOutlineState(project); notify("故事大纲已生成，请确认后生成剧本");
  } catch (error) {
    if (controller.signal.aborted) return;
    outlineStatus.value = "failed"; outlinePhase.value = ""; outlineError.value = error instanceof Error ? error.message : "故事大纲生成失败"; stopGenerationTimer(); await persistOutlineState(project).catch(() => undefined);
  } finally { if (outlineController.value === controller) outlineController.value = undefined; }
}

async function confirmOutline():Promise<boolean> {
  const project = activeProjectRecord.value;
  if (!project || !outlinePlan.value || outlineEpisodes.value.length !== project.episode_count) return false;
  outlineStatus.value = "confirmed";
  outlineError.value = "";
  await persistOutlineState(project);
  await syncProductionLedger(project);
  notify("故事大纲已确认");
  return true;
}

async function generateScriptsFromOutline() {
  const project = activeProjectRecord.value;
  if (!project || !outlineHasCompleteEpisode.value) return;
  if (outlineStatus.value !== "confirmed") {
    const confirmed = await confirmOutline();
    if (!confirmed) {
      outlineError.value = "故事大纲尚未完整，无法自动确认并生成剧本";
      return;
    }
  }
  scriptController.value?.abort();
  scripts.value = [];
  scriptAudits.value = [];
  scriptStatus.value = "idle";
  scriptPhase.value = "";
  scriptError.value = "";
  await persistScriptState(project);
  selectWorkflowNavigation("剧本");
  await nextTick();
  await generateScripts();
}

function importCurrentWorkflow() { fileInput.value?.click(); }

async function enterStoryboardGeneration() {
  const project = activeProjectRecord.value;
  if (!project || !scriptHasCompleteEpisode.value) return;
  storyboardController.value?.abort();
  storyboardShots.value = [];
  storyboardAudits.value = [];
  storyboardStatus.value = "idle";
  storyboardError.value = "";
  await persistStoryboardState(project);
  selectWorkflowNavigation("分镜脚本");
  await nextTick();
  await generateStoryboards();
}

let assetEntryPromise:Promise<void> | undefined;
let assetEntryPromiseKey = "";
function enterAssetGeneration():Promise<void> {
  const project = activeProjectRecord.value;
  const session = projectSession;
  if (!project || !storyboardHasCompleteEpisode.value) return Promise.resolve();
  const entryKey = `${project.id}:${session}`;
  if (assetEntryPromise && assetEntryPromiseKey === entryKey) return assetEntryPromise;
  const transaction = (async () => {
    if (storyboardStatus.value !== "confirmed") {
      const confirmed = await confirmStoryboards();
      if (!confirmed || String(storyboardStatus.value) !== "confirmed") return;
    }
    if (!isCurrentProjectSession(project.id, session)) return;
    let authoritativeAssets = await projectService.readStage<AssetStageData>({ ...projectIdentity, id:project.id, stage:"assets" }).catch(() => null);
    let authoritativeWorkflow = await productionLedgerService.workflow(productionTaskContext(project)).catch(() => null);
    if (!isCurrentProjectSession(project.id, session)) return;
    const assetAuthorityReady = () => successfulAssetStageStatuses.has(String(authoritativeAssets?.stage?.data.status || ""))
      && ["pending_confirmation", "completed"].includes(String(authoritativeWorkflow?.workflow.stages.assets || ""));
    if (!allAssetProfiles.value.length || !assetAuthorityReady()) {
      await prepareAssetProfilesFromStoryboard(project);
      if (!isCurrentProjectSession(project.id, session)) return;
      authoritativeAssets = await projectService.readStage<AssetStageData>({ ...projectIdentity, id:project.id, stage:"assets" }).catch(() => null);
      authoritativeWorkflow = await productionLedgerService.workflow(productionTaskContext(project)).catch(() => null);
    }
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!assetAuthorityReady()) {
      assetError.value ||= "资产权威阶段尚未完成，请先重试资产提取";
      await persistAssetState(project, session);
      return;
    }
    assetIntroOpen.value = "";
    await persistAssetState(project, session);
    selectWorkflowNavigation("资产");
    await nextTick();
    notify("已根据分镜脚本创建资产卡片，系统将按队列自动生成缺失的人物、道具和场景基准图，无需手动上传");
    if (!isCurrentProjectSession(project.id, session)) return;
    await enqueueAssetOperation(`${project.id}:generate-all`, "生成资产图片", () => generateAllAssetImages(project, session));
  })();
  const singleFlight = transaction.finally(() => {
    if (assetEntryPromise === singleFlight && assetEntryPromiseKey === entryKey) {
      assetEntryPromise = undefined;
      assetEntryPromiseKey = "";
    }
  });
  assetEntryPromise = singleFlight;
  assetEntryPromiseKey = entryKey;
  return singleFlight;
}

async function stopAllAssetGeneration() {
  const project = activeProjectRecord.value;
  const session = projectSession;
  assetBatchPaused.value = true;
  assetOperationEpoch += 1;
  queuedAssetOperationOwners.clear();
  queuedAssetOperationCount.value = 0;
  assetController.value?.abort();
  reclaimAssetBatchProjection(assetBatchFlight, assetBatchController.value, activeAssetBatchToken);
  const stopEpoch = ++assetBatchEpoch;
  if (project) await assetService.stopImages({ ...productionTaskContext(project), stage:"assets", all:true }).catch(() => undefined);
  if (!project || !isCurrentProjectSession(project.id, session) || assetBatchEpoch !== stopEpoch) return;
  for (const item of [...characterProfiles.value, ...sceneProfiles.value, ...propProfiles.value]) {
    if (item.status === "generating") item.status = item.image_url ? "waiting_confirmation" : "pending";
  }
  assetBatchGenerating.value = false;
  assetStatus.value = "pending";
  assetError.value = "已暂停，可继续生成";
  await persistAssetState(project, session);
}

async function stopOutline() {
  const project = activeProjectRecord.value;
  const clientGenerationId = outlineGenerationId.value;
  outlineController.value?.abort();
  await narrativeService.stop("outline", { ...productionTaskContext(project), client_generation_id:clientGenerationId }).catch(() => undefined);
  outlineStatus.value = "failed";
  outlineAuditStopped.value = false;
  outlinePhase.value = "";
  outlineError.value = "已停止生成，可保留现有内容后重新生成";
  stopGenerationTimer();
  await persistOutlineState();
}

async function stopOutlineAudit() {
  const project = activeProjectRecord.value;
  const clientGenerationId = outlineGenerationId.value;
  outlineController.value?.abort();
  await Promise.allSettled([narrativeService.stopAudit(), narrativeService.stop("outline", { ...productionTaskContext(project), client_generation_id:clientGenerationId })]);
  outlineStatus.value = "failed";
  outlineAuditStopped.value = true;
  outlinePhase.value = "";
  outlineError.value = "审核已停止";
  stopGenerationTimer();
  await persistOutlineState();
}

async function continueOutlineAudit() {
  if (!outlineAuditStopped.value || !outlineEpisodesComplete.value) return;
  outlineError.value = "";
  await generateOutline(true);
}

type ScriptStageData = {
  scripts:ScriptItem[]; status:typeof scriptStatus.value; error:string; audits:OutlineAudit[]; phase?:typeof scriptPhase.value;
  generation_id?:string; generation_started_at?:number; heartbeat_at?:number;
};
function stableTextHash(value:string) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
  return hash >>> 0;
}
function episodeTargetDuration(project:StoredProject, episodeIndex:number) {
  const minimum = Math.max(60, Math.min(70, Math.round(project.duration_min)));
  const maximum = Math.max(minimum, Math.min(70, Math.round(project.duration_max)));
  const outline = outlineEpisodes.value[episodeIndex];
  const seed = `${project.id}|${episodeIndex + 1}|${outline?.title || ""}|${outline?.synopsis || project.topic}`;
  return minimum + stableTextHash(seed) % (maximum - minimum + 1);
}
function scriptTargetDuration(project:StoredProject, script:ScriptItem) {
  const stored = Number(script.target_duration);
  return Number.isInteger(stored) && stored >= 60 && stored <= 70 ? stored : episodeTargetDuration(project, Math.max(0, script.episode - 1));
}
function variableShotDurations(targetDuration:number, count:number, seed:string) {
  const pattern = [3, 5, 4, 2, 6, 3, 4, 5, 2, 4, 6, 3, 5, 4, 2, 5, 3, 6, 4, 2, 5, 4, 3];
  const offset = stableTextHash(seed) % pattern.length;
  const durations = Array.from({ length:count }, (_, index) => pattern[(index + offset) % pattern.length]);
  while (durations.reduce((sum, value) => sum + value, 0) < targetDuration) {
    const candidate = durations.map((value, index) => ({ value, index })).filter(item => item.value < 9)
      .sort((left, right) => left.value - right.value || ((left.index + offset) % count) - ((right.index + offset) % count))[0];
    if (!candidate) break;
    durations[candidate.index] += 1;
  }
  while (durations.reduce((sum, value) => sum + value, 0) > targetDuration) {
    const candidate = durations.map((value, index) => ({ value, index })).filter(item => item.value > 2)
      .sort((left, right) => right.value - left.value || ((left.index + offset) % count) - ((right.index + offset) % count))[0];
    if (!candidate) break;
    durations[candidate.index] -= 1;
  }
  return durations;
}
function storyboardTimingPlan(project:StoredProject, script:ScriptItem) {
  const targetDuration = scriptTargetDuration(project, script);
  const shotCount = Math.max(15, Math.min(23, Math.round(targetDuration / 4)));
  const durations = variableShotDurations(targetDuration, shotCount, `${project.id}|${script.episode}|${script.title}`);
  let cursor = 0;
  return durations.map((duration, index) => {
    const timing = { shot_number:index + 1, start_second:cursor, end_second:cursor + duration };
    cursor += duration;
    return timing;
  });
}
function resumableStoryboardPrefix(project:StoredProject, script:ScriptItem, input:StoryboardShot[]) {
  const plan = storyboardTimingPlan(project, script);
  const shots = [...input].sort((left, right) => left.shot_number - right.shot_number);
  if (!shots.length || shots.length >= plan.length) return [];
  const signatures = new Set<string>();
  for (let index = 0; index < shots.length; index += 1) {
    const shot = shots[index];
    const expected = plan[index];
    const signature = storyboardShotSignature(shot);
    if (shot.shot_number !== expected.shot_number || Math.abs(shot.start_second - expected.start_second) > 0.05 || Math.abs(shot.end_second - expected.end_second) > 0.05 || !signature || signatures.has(signature)) return [];
    signatures.add(signature);
  }
  return shots;
}
function humanReadableScriptContent(content:unknown) {
  if (typeof content === "string") return content.trim()
    .replace(/\s*[｜|]\s*/g, "\n");
  if (!Array.isArray(content)) return String(content || "").trim();
  return content.map((raw, index) => {
    if (!raw || typeof raw !== "object") return `段落${String(index + 1).padStart(2, "0")}\n${String(raw || "")}`;
    const item = Object.fromEntries(Object.entries(raw as Record<string, unknown>).map(([key, value]) => [key.replace(/[^\p{L}\p{N}]+/gu, ""), value]));
    const timeRange = String(item["时间段"] || item["时间"] || "").trim();
    return [`段落${String(index + 1).padStart(2, "0")}`, ...(timeRange ? [timeRange] : []), ...["画面", "动作", "台词", "旁白", "情绪"].map(label => `${label}：${String(item[label] || "无")}`)].join("\n");
  }).join("\n\n");
}

async function loadScriptState(project = activeProjectRecord.value, session = projectSession) {
  scripts.value = [];
  scriptStatus.value = "idle";
  scriptError.value = "";
  scriptAudits.value = [];
  scriptPhase.value = "";
  scriptGenerationId.value = "";
  scriptGenerationStartedAt.value = 0;
  scriptHeartbeatAt.value = 0;
  if (!project) return;
  try {
    const result = await projectService.readStage<ScriptStageData>({ ...projectIdentity, id:project.id, stage:"script" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    scripts.value = (result.stage.data.scripts || []).map(script => ({ ...script, target_duration:scriptTargetDuration(project, script), content:humanReadableScriptContent(script.content) }));
    const interrupted = result.stage.data.status === "generating";
    scriptPhase.value = interrupted ? "" : result.stage.data.phase || "";
    scriptGenerationId.value = interrupted ? "" : result.stage.data.generation_id || "";
    scriptGenerationStartedAt.value = interrupted ? 0 : Number(result.stage.data.generation_started_at || 0);
    scriptHeartbeatAt.value = interrupted ? 0 : Number(result.stage.data.heartbeat_at || 0);
    projectLoadIsolation.mark(project.id, session, "script", false);
    scriptAudits.value = (result.stage.data.audits || []).map(normalizeOutlineAudit);
    const completedSuccessfully = scripts.value.length === project.episode_count
      && scripts.value.every(script => script.title?.trim() && humanReadableScriptContent(script.content))
      && (!narrativeAuditEnabled.value || narrativeAuditsPassed(scriptAudits.value));
    scriptStatus.value = interrupted ? "failed" : completedSuccessfully && ["failed", "waiting_confirmation"].includes(result.stage.data.status) ? "confirmed" : result.stage.data.status;
    scriptError.value = interrupted ? "剧本任务已中断，已回收；可从缺失集数继续生成" : completedSuccessfully ? "" : result.stage.data.error || "";
    if (interrupted) await persistScriptState(project);
  } catch (error) {
    scriptError.value = error instanceof Error ? error.message : "剧本加载失败";
  }
}

async function persistScriptState(project = activeProjectRecord.value) {
  if (!project) return;
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"script", data:{
    scripts:scripts.value, status:scriptStatus.value, error:scriptError.value, audits:scriptAudits.value, phase:scriptPhase.value,
    generation_id:scriptGenerationId.value, generation_started_at:scriptGenerationStartedAt.value, heartbeat_at:scriptHeartbeatAt.value,
  } satisfies ScriptStageData });
}

async function auditScriptBatch(project:StoredProject, batch:ScriptItem[], controller:AbortController, mode:"both" | "final" = "both", priorAudit:OutlineAudit | null = null, batchId = ""):Promise<OutlineAudit> {
  const response:ApiJsonResult<{ audit:OutlineAudit }> = await narrativeService.audit<{ audit:OutlineAudit }>({
    ...productionTaskContext(project),
    stage:"script", audit_mode:mode, range:`第${batch[0].episode}–${batch[batch.length - 1].episode}集`,
    project_requirements:stableProjectRequirements(project), upstream_context:{ outline_plan:outlinePlan.value, episode_outlines:outlineEpisodes.value },
    content:{ scripts:batch }, prior_audit:priorAudit,
  }, controller.signal, { invalid:status => `剧本审核返回异常（HTTP ${status}）` });
  if (!response.ok) throw new Error((response.data as { error?:string }).error || "剧本审核失败");
  return { ...normalizeOutlineAudit(response.data.audit), phase:mode === "final" ? "final" : "initial", batch_id:batchId };
}

async function generateScripts() {
  if (!requireEnabledRobot("编剧")) return;
  const project = activeProjectRecord.value;
  if (!project || !outlinePlan.value || !outlineEpisodes.value.length || scriptStatus.value === "generating") return;
  const controller = new AbortController(); scriptController.value?.abort(); scriptController.value = controller;
  scriptStatus.value = "generating"; scriptPhase.value = "generating"; scriptError.value = ""; scriptGenerationId.value = crypto.randomUUID();
  try {
    const response = await productionLedgerService.runStage<{ scripts:ScriptItem[]; audits:OutlineAudit[] }>({
      ...productionTaskContext(project), stage:"script", audit_enabled:narrativeAuditEnabled.value, plan:outlinePlan.value, episodes:outlineEpisodes.value,
      context:{ ...productionTaskContext(project), generation_id:scriptGenerationId.value, topic:project.topic, style:project.style, language:project.language, duration:Math.round((project.duration_min + project.duration_max) / 2) },
    }, controller.signal);
    scripts.value = response.result.scripts.map(script => ({ ...script, target_duration:scriptTargetDuration(project, script), content:humanReadableScriptContent(script.content) })); scriptAudits.value = (response.result.audits || []).map(normalizeOutlineAudit);
    scriptStatus.value = "waiting_confirmation"; scriptPhase.value = ""; scriptGenerationId.value = ""; await persistScriptState(project); notify("全剧剧本已生成，请确认后生成分镜脚本");
  } catch (error) {
    if (controller.signal.aborted) return;
    scriptStatus.value = "failed"; scriptPhase.value = ""; scriptError.value = error instanceof Error ? error.message : "剧本生成失败"; scriptGenerationId.value = ""; await persistScriptState(project).catch(() => undefined);
  } finally { if (scriptController.value === controller) scriptController.value = undefined; }
}

async function runScriptPrimaryAction() {
  const project = activeProjectRecord.value;
  if (!project) return;
  if (scriptStatus.value === "confirmed") {
    await projectService.createVersion({ ...projectIdentity, project_id:project.id, project_name:project.name, stage:"before-script-regenerate", reason:"重新生成全剧剧本前归档" });
    scripts.value = [];
    scriptAudits.value = [];
    scriptStatus.value = "idle";
    scriptPhase.value = "";
    scriptError.value = "";
    await persistScriptState(project);
  }
  await generateScripts();
}

async function confirmScripts() {
  const project = activeProjectRecord.value;
  if (!project || scripts.value.length !== project.episode_count
    || scripts.value.some(script => !script.title?.trim() || !humanReadableScriptContent(script.content))
    || narrativeAuditEnabled.value && !narrativeAuditsPassed(scriptAudits.value)) return;
  scriptStatus.value = "confirmed";
  await persistScriptState(project);
  await syncProductionLedger(project);
  notify("全剧剧本已确认");
}

async function stopScripts() {
  const project = activeProjectRecord.value;
  const generationId = scriptGenerationId.value;
  scriptController.value?.abort();
  await narrativeService.stop("script", { ...productionTaskContext(project), client_generation_id:generationId }).catch(() => undefined);
  scriptStatus.value = "failed";
  scriptPhase.value = "";
  scriptError.value = "已停止生成，可从未完成集数继续";
  scriptGenerationId.value = "";
  scriptGenerationStartedAt.value = 0;
  scriptHeartbeatAt.value = 0;
  if (scriptHeartbeatTimer) window.clearInterval(scriptHeartbeatTimer);
  scriptHeartbeatTimer = undefined;
  await persistScriptState();
}

type StoryboardStageData = { shots:StoryboardShot[]; status:typeof storyboardStatus.value; error:string; audits:OutlineAudit[]; streaming_episode?:number };
function storyboardShotSignature(shot:Pick<StoryboardShot, "visual" | "action">) {
  return `${shot.visual}|${shot.action}`.replace(/[^\p{L}\p{N}]+/gu, "").toLowerCase();
}
function mergeStoryboardEpisodeResults(existingShots:StoryboardShot[], incomingShots:StoryboardShot[], replacedEpisodes:number[]) {
  const replace = new Set(replacedEpisodes);
  const preserved = existingShots.filter(shot => !replace.has(shot.episode));
  const replacements = incomingShots.filter(shot => replace.has(shot.episode));
  const merged = [...preserved, ...replacements].sort((left, right) => left.episode - right.episode || left.shot_number - right.shot_number);
  const keys = new Set<string>();
  for (const shot of merged) {
    if (!Number.isInteger(shot.episode) || shot.episode <= 0 || !Number.isInteger(shot.shot_number) || shot.shot_number <= 0) throw new Error("分镜响应包含非法镜头编号");
    const key = `${shot.episode}:${shot.shot_number}`;
    if (keys.has(key)) throw new Error(`分镜响应包含重复镜头：${key}`);
    keys.add(key);
  }
  return merged;
}
function storyboardEpisodeError(shots:StoryboardShot[], targetDuration:number) {
  if (shots.length < 15 || shots.length > 23) return `分镜数量必须为15-23个，当前为${shots.length}个`;
  let previousEnd = 0;
  const signatures = new Set<string>();
  for (const shot of [...shots].sort((a, b) => a.shot_number - b.shot_number)) {
    if (Math.abs(shot.start_second - previousEnd) > 0.05) return `镜头${shot.shot_number}时间轴不连续`;
    const duration = shot.end_second - shot.start_second;
    if (duration < 2 || duration > 9) return `镜头${shot.shot_number}时长必须为2-9秒`;
    const signature = storyboardShotSignature(shot);
    if (!signature || signatures.has(signature)) return `镜头${shot.shot_number}画面与动作重复或无效`;
    signatures.add(signature);
    previousEnd = shot.end_second;
  }
  return Math.abs(previousEnd - targetDuration) > 1 ? `分镜总时长必须覆盖${targetDuration}秒，当前为${previousEnd}秒` : "";
}

async function loadStoryboardState(project = activeProjectRecord.value, session = projectSession) {
  storyboardShots.value = [];
  storyboardStatus.value = "idle";
  storyboardError.value = "";
  storyboardAudits.value = [];
  if (!project) return;
  try {
    const result = await projectService.readStage<StoryboardStageData>({ ...projectIdentity, id:project.id, stage:"storyboard" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    storyboardShots.value = (result.stage.data.shots || []).filter(shot => Number.isInteger(shot.episode) && shot.episode > 0).map(shot => ({ ...shot, render_chunks:buildShotRenderChunks(shot) }));
    projectLoadIsolation.mark(project.id, session, "storyboard", result.stage.data.status === "generating");
    storyboardAudits.value = (result.stage.data.audits || []).map(normalizeOutlineAudit);
    const generatedEpisodes = new Set(storyboardShots.value.map(shot => shot.episode)).size;
    const completedSuccessfully = generatedEpisodes === project.episode_count
      && (!narrativeAuditEnabled.value || narrativeAuditsPassed(storyboardAudits.value));
    const invalidEpisode = Array.from({ length:project.episode_count }, (_, index) => index + 1).map(episode => {
      const script = scripts.value.find(item => item.episode === episode);
      const targetDuration = script ? scriptTargetDuration(project, script) : episodeTargetDuration(project, episode - 1);
      const shots = storyboardShots.value.filter(shot => shot.episode === episode);
      const expectedCount = script ? storyboardTimingPlan(project, script).length : 15;
      return shots.length && shots.length >= expectedCount ? storyboardEpisodeError(shots, targetDuration) : "";
    }).find(Boolean) || "";
    const partial = scripts.value.map(script => {
      const count = storyboardShots.value.filter(shot => shot.episode === script.episode).length;
      const expected = storyboardTimingPlan(project, script).length;
      return count > 0 && count < expected ? `第${script.episode}集已完成${count}/${expected}个镜头` : "";
    }).find(Boolean) || "";
    const interrupted = result.stage.data.status === "generating";
    storyboardStatus.value = invalidEpisode || partial || interrupted ? "failed" : completedSuccessfully && ["failed", "waiting_confirmation"].includes(result.stage.data.status) ? "confirmed" : result.stage.data.status;
    storyboardError.value = invalidEpisode || (partial ? `${partial}，点击继续生成将从断点补齐` : interrupted ? "分镜任务曾中断，点击继续生成将从断点恢复" : completedSuccessfully ? "" : result.stage.data.error || "");
  } catch (error) { storyboardError.value = error instanceof Error ? error.message : "分镜脚本加载失败"; }
}

async function persistStoryboardState(project = activeProjectRecord.value) {
  if (!project) return;
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"storyboard", data:{ shots:storyboardShots.value, status:storyboardStatus.value, error:storyboardError.value, audits:storyboardAudits.value } satisfies StoryboardStageData });
}

async function auditStoryboardBatch(project:StoredProject, shots:StoryboardShot[], controller:AbortController, mode:"both" | "final" = "both", priorAudit:OutlineAudit | null = null, batchId = ""):Promise<OutlineAudit> {
  const episodes = [...new Set(shots.map(shot => shot.episode))];
  const response:ApiJsonResult<{ audit:OutlineAudit }> = await narrativeService.audit<{ audit:OutlineAudit }>({
    ...productionTaskContext(project),
    stage:"storyboard", audit_mode:mode, range:`第${episodes[0]}–${episodes[episodes.length - 1]}集`, project_requirements:stableProjectRequirements(project),
    upstream_context:{ outline:outlinePlan.value, scripts:scripts.value.filter(script => episodes.includes(script.episode)) }, content:{ shots }, prior_audit:priorAudit,
  }, controller.signal, { invalid:status => `分镜审核返回异常（HTTP ${status}）` });
  if (!response.ok) throw new Error((response.data as { error?:string }).error || "分镜审核失败");
  return { ...normalizeOutlineAudit(response.data.audit), phase:mode === "final" ? "final" : "initial", batch_id:batchId };
}

async function generateStoryboards(_recovering:boolean | Event = false) {
  if (!requireEnabledRobot("编剧")) return;
  const project = activeProjectRecord.value;
  if (!project || !scripts.value.length || storyboardStatus.value === "generating") return;
  const session = projectSession;
  const existingShots:StoryboardShot[] = [...storyboardShots.value];
  const controller = new AbortController(); storyboardController.value?.abort(); storyboardController.value = controller;
  const watchController = new AbortController();
  const stopWatch = () => watchController.abort();
  controller.signal.addEventListener("abort", stopWatch, { once:true });
  storyboardStatus.value = "generating"; storyboardError.value = "";
  let polling = true;
  let observedRevision = 0;
  let activeWatchRequestId = "";
  const cancelActiveWatch = async () => {
    const requestId = activeWatchRequestId;
    watchController.abort();
    if (requestId) await projectService.cancelStageWatch({ ...projectIdentity, id:project.id, stage:"storyboard", request_id:requestId }).catch(() => undefined);
  };
  const progressPoll = (async () => {
    while (polling && isCurrentProjectSession(project.id, session) && !controller.signal.aborted) {
      const requestId = crypto.randomUUID(); activeWatchRequestId = requestId;
      const partial = await projectService.watchStage<StoryboardStageData>({ ...projectIdentity, id:project.id, stage:"storyboard", after_revision:observedRevision, timeout_seconds:20, request_id:requestId }, watchController.signal).catch(() => null);
      if (activeWatchRequestId === requestId) activeWatchRequestId = "";
      if (!polling || controller.signal.aborted || watchController.signal.aborted || !isCurrentProjectSession(project.id, session)) break;
      if (!partial?.changed || !partial.stage) continue;
      observedRevision = Math.max(observedRevision, Number(partial.stage.revision || 0));
      if (partial.stage.data.status !== "generating") continue;
      const incoming = (partial.stage.data.shots || []).filter(shot => Number.isInteger(shot.episode) && shot.episode > 0);
      if (incoming.length <= storyboardShots.value.length) continue;
      if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) break;
      storyboardShots.value = incoming.map(shot => ({ ...shot, render_chunks:buildShotRenderChunks(shot) }));
      await seedAssetCardsFromStoryboard(project, incoming, session, controller.signal);
      if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) break;
      for (const episode of [...completeStoryboardEpisodes.value].sort((a, b) => a - b)) {
        queueStoryboardAssetExtraction(project, session, episode);
      }
    }
  })();
  try {
    const response = await productionLedgerService.runStage<{ shots:StoryboardShot[]; audits:OutlineAudit[]; generated_episodes:number[] }>({
      ...productionTaskContext(project), stage:"storyboard", audit_enabled:narrativeAuditEnabled.value, scripts:scripts.value, characters:outlinePlan.value?.characters || [],
      shots:existingShots, audits:storyboardAudits.value,
      context:{ ...productionTaskContext(project), topic:project.topic, style:project.style, language:project.language, duration:Math.round((project.duration_min + project.duration_max) / 2), aspect:"9:16" },
    }, controller.signal);
    polling = false;
    await cancelActiveWatch();
    await progressPoll.catch(() => undefined);
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    storyboardShots.value = mergeStoryboardEpisodeResults(existingShots, response.result.shots, response.result.generated_episodes || []);
    storyboardAudits.value = (response.result.audits || []).map(normalizeOutlineAudit);
    storyboardStatus.value = !narrativeAuditEnabled.value || narrativeAuditsPassed(storyboardAudits.value) ? "confirmed" : "waiting_confirmation";
    await persistStoryboardState(project);
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    if (storyboardStatus.value === "confirmed") {
      await syncProductionLedger(project);
      if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
      await prepareAssetProfilesFromStoryboard(project);
      notify("全剧分镜脚本已完成，资产页已自动提取人物、道具和场景框架");
    } else {
      notify("全剧分镜脚本已生成，请确认后提取资产框架");
    }
  } catch (error) {
    if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) return;
    storyboardStatus.value = "failed"; storyboardError.value = error instanceof Error ? error.message : "分镜脚本生成失败"; await persistStoryboardState(project).catch(() => undefined);
  } finally {
    polling = false;
    await cancelActiveWatch();
    controller.signal.removeEventListener("abort", stopWatch);
    await progressPoll.catch(() => undefined);
    if (storyboardController.value === controller) storyboardController.value = undefined;
  }
}

async function runStoryboardPrimaryAction() {
  const project = activeProjectRecord.value;
  if (!project) return;
  if (storyboardStatus.value === "confirmed") {
    await projectService.createVersion({ ...projectIdentity, project_id:project.id, project_name:project.name, stage:"before-storyboard-regenerate", reason:"重新生成全剧分镜脚本前归档" });
    storyboardShots.value = [];
    storyboardAudits.value = [];
    storyboardStatus.value = "idle";
    storyboardError.value = "";
    await persistStoryboardState(project);
  }
  await generateStoryboards();
}

async function confirmStoryboards():Promise<boolean> {
  if (!storyboardShots.value.length || narrativeAuditEnabled.value && !narrativeAuditsPassed(storyboardAudits.value)) return false;
  const project = activeProjectRecord.value;
  if (!project) return false;
  storyboardStatus.value = "confirmed";
  try {
    await persistStoryboardState(project);
    await syncProductionLedger(project);
    if (activeProjectRecord.value?.id !== project.id) return false;
    await prepareAssetProfilesFromStoryboard(project);
    notify("全剧分镜脚本已确认，资产简介已自动填入");
    return true;
  } catch (error) {
    storyboardStatus.value = "waiting_confirmation";
    storyboardError.value = error instanceof Error ? error.message : "分镜确认失败";
    await persistStoryboardState(project).catch(() => undefined);
    return false;
  }
}

async function stopStoryboards() {
  const project = activeProjectRecord.value;
  if (!project) return;
  const session = projectSession;
  storyboardController.value?.abort();
  await narrativeService.stop("storyboard", productionTaskContext(project)).catch(() => undefined);
  if (!isCurrentProjectSession(project.id, session)) return;
  storyboardStatus.value = "failed";
  storyboardError.value = "已停止生成，可从未完成集数继续";
  await persistStoryboardState(project);
}

type AssetStageData = { characters:CharacterProfile[]; scenes:SceneProfile[]; props:PropProfile[]; status:AssetStatus; error:string; source_episodes?:number[]; census_version?:number };

const successfulAssetStageStatuses = new Set(["waiting_confirmation", "confirmed", "completed"]);
const deferredAssetConfirmationError = "previous stage is not completed: storyboard";
const circularAssetConstructionError = "previous stage is not completed: assets";
const isDeferredAssetConfirmationError = (value:unknown) => {
  const message = String(value || "").trim();
  return [deferredAssetConfirmationError, circularAssetConstructionError].some(error => (
    message === error || message.endsWith(`：${error}`) || message.endsWith(`: ${error}`)
  ));
};

function clearResolvedAssetStageConflict<T extends CharacterProfile | SceneProfile | PropProfile>(item:T, authoritativeSuccess = false) {
  const itemError = String(item.error || "").trim();
  if (authoritativeSuccess && itemError === "production stage is already running: assets") {
    item.status = item.image_url ? "waiting_confirmation" : "pending";
    item.error = "";
  } else if (isDeferredAssetConfirmationError(itemError)) {
    item.status = item.image_url ? "waiting_confirmation" : "pending";
    item.error = "";
  }
  for (const variant of item.detail_assets || []) {
    if (!isDeferredAssetConfirmationError(variant.error)) continue;
    variant.status = variant.image_url ? "waiting_confirmation" : "pending";
    variant.error = "";
  }
  return item;
}

function isReusableSceneAssetName(value:unknown) {
  const name = String(value || "").trim();
  const characterNames = new Set([
    ...(outlinePlan.value?.characters || []).map(character => String(character.name || "").trim()),
    ...characterProfiles.value.map(character => String(character.name || "").trim()),
  ].filter(Boolean));
  if (!name || !/(?:试炼场|练武场|广场|大殿|殿内|殿外|庭院|院落|房间|卧室|书房|藏经阁|阁楼|楼阁|大厅|走廊|山门|后山|山谷|树林|街道|巷道|地牢|牢房|擂台|秘境|洞府|城门|村落|湖畔|河岸|桥上|厨房|客厅|餐厅|饭店|卫生间|浴室|医院|诊所|病房|学校|教室|办公室|会议室|公司|商场|超市|酒店|旅馆|车站|候车室|机场|候机厅|码头|仓库|工厂|车间|寺庙|道观|教堂|咖啡馆|图书馆|博物馆|体育馆|停车场|公园|花园|游乐园|电影院|剧院|舞台|摄影棚|实验室|工作室|店铺|住宅|公寓|别墅|宿舍|天台|屋顶|地下室|电梯间|楼梯间|前台|操场|球场|海滩|沙漠|草原|雪原)$/.test(name) || [...characterNames].some(character => name.includes(character)) || /(?:弟子|众人|人群|长老|侍卫|士兵|百姓|村民|男人|女人|男子|女子|孩童|全宗门)/.test(name) || /(?:被(?:夺走|抢走|推进|带进|送进|关进|困在|藏进|打伤|杀死|击倒)|(?:藏|推|冲|闯|逃|跑|走|驶|搬|抬|送|带)(?:进|入|向|到)|失控|夺走|抢走|打斗|追逐|爆炸|起火|坍塌|倒塌|发生|后(?:藏|走|进入|来到))/.test(name)) return false;
  return !/(?:跪(?:下|在|着)|坐(?:下|在|着)|躺(?:下|在|着)|站立|倒地|转身|回头|低头|抬头|走(?:进|出|向|到)|跑(?:进|出|向|到)|冲(?:进|出|向)|追赶|挥(?:手|剑)|抱住|看向|望向|哭泣|大笑|说话|喊道|进入|离开)/.test(name);
}

function sceneLocationFromShot(shot:StoryboardShot) {
  if (isReusableSceneAssetName(shot.scene)) return String(shot.scene).trim();
  const text = `${shot.visual || ""}，${shot.action || ""}，${shot.image_prompt || ""}`;
  const background = text.match(/(?:背景(?:是|为)|地点(?:在|是|为|[:：]))([^，。；]{2,24})/)?.[1] || "";
  const candidates = [background, ...(text.match(/[\u4e00-\u9fff]{0,10}(?:试炼场|练武场|广场|大殿|殿内|殿外|庭院|院落|房间|卧室|书房|藏经阁|阁楼|楼阁|大厅|走廊|山门|后山|山谷|树林|街道|巷道|地牢|牢房|擂台|秘境|洞府|城门|村落|湖畔|河岸|桥上|厨房|客厅|餐厅|饭店|卫生间|浴室|医院|诊所|病房|学校|教室|办公室|会议室|公司|商场|超市|酒店|旅馆|车站|候车室|机场|候机厅|码头|仓库|工厂|车间|寺庙|道观|教堂|咖啡馆|图书馆|博物馆|体育馆|停车场|公园|花园|游乐园|电影院|剧院|舞台|摄影棚|实验室|工作室|店铺|住宅|公寓|别墅|宿舍|天台|屋顶|地下室|电梯间|楼梯间|前台|操场|球场|海滩|沙漠|草原|雪原)/g) || [])];
  for (const candidate of candidates) {
    const cleaned = candidate.replace(/^(?:一座|一处|古色古香的|宏伟的|昏暗的|宽阔的|空旷的|远处的)+/, "").trim();
    if (isReusableSceneAssetName(cleaned)) return cleaned;
  }
  return "";
}

function normalizeEmptySceneProfiles(items:SceneProfile[]) {
  return items.filter(item => isReusableSceneAssetName(item.name)).map(item => ({
    ...item,
    location:String(item.location || item.name).trim(),
    image_prompt:[item.location || item.name, item.layout, item.lighting, ...(item.fixed_elements || [])].filter(Boolean).join("，") + "，45度空场景全景，纯环境与建筑，无人物、无人形、无人体、无文字",
  }));
}

function assetBaselineJobName(projectId:string, kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile) {
  return `${projectId}_${item.generation_nonce || "legacy"}_${kind}_${item.name}_baseline`;
}

async function loadAssetState(project = activeProjectRecord.value, session = projectSession) {
  characterProfiles.value = [];
  sceneProfiles.value = [];
  propProfiles.value = [];
  assetSourceEpisodes.value = [];
  assetStatus.value = "pending";
  assetError.value = "";
  if (!project) return;
  try {
    const result = await projectService.readStage<AssetStageData>({ ...projectIdentity, id:project.id, stage:"assets" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    assetSourceEpisodes.value = result.stage.data.source_episodes || [];
    const storedProfiles = [...(result.stage.data.characters || []), ...(result.stage.data.scenes || []), ...(result.stage.data.props || [])];
    const authoritativeSuccess = successfulAssetStageStatuses.has(String(result.stage.data.status));
    const resolvedStageConflict = storedProfiles.some(item => (
      (authoritativeSuccess && String(item.error || "").trim() === "production stage is already running: assets")
      || isDeferredAssetConfirmationError(item.error)
      || (item.detail_assets || []).some(variant => isDeferredAssetConfirmationError(variant.error))
    ));
    const storedCharacters = (result.stage.data.characters || []).map(item => clearResolvedAssetStageConflict(item, authoritativeSuccess));
    characterProfiles.value = storedCharacters;
    const storedScenes = (result.stage.data.scenes || []).map(item => clearResolvedAssetStageConflict(item, authoritativeSuccess));
    sceneProfiles.value = normalizeEmptySceneProfiles(storedScenes);
    const removedInvalidScenes = sceneProfiles.value.length !== storedScenes.length;
    propProfiles.value = (result.stage.data.props || []).map(item => clearResolvedAssetStageConflict(item, authoritativeSuccess));
    let recovered = resolvedStageConflict || removedInvalidScenes;
    for (const group of [
      { kind:"character", items:characterProfiles.value },
      { kind:"scene", items:sceneProfiles.value },
      { kind:"prop", items:propProfiles.value },
    ] as const) for (const item of group.items) {
      if (group.kind === "character" && item.image_url && item.view_contract !== characterViewContract) {
        item.image_url = undefined;
        item.detail_assets = [];
        item.generation_nonce = crypto.randomUUID();
        item.confirmation_phase = undefined;
        item.status = "pending";
        item.error = "人物视图规范已更新，请重新生成0°正面全身基准图";
        recovered = true;
      }
      if (item.image_url && item.status === "failed" && String(item.error || "").includes("not_found")) {
        item.status = "waiting_confirmation"; item.error = ""; recovered = true;
      }
      if (!item.image_url) {
        const jobName = assetBaselineJobName(project.id, group.kind, item);
        const completed = await assetService.characterResult<{ status:string; image?:{ url:string }; error?:string }>(jobName).catch(() => null);
        if (!isCurrentProjectSession(project.id, session)) return;
        if (completed?.ok && completed.data.status === "completed" && completed.data.image?.url) {
          item.image_url = completed.data.image.url; item.status = "waiting_confirmation"; item.error = ""; recovered = true;
        } else if (completed?.ok && completed.data.status === "failed") {
          item.status = "failed"; item.error = userFacingGenerationError(completed.data.error); recovered = true;
        } else if (!completed?.ok && item.status === "generating") {
          item.status = "pending"; item.error = "上次生成任务已中断，请继续生成"; recovered = true;
        }
      }
      if (!item.image_url || item.confirmation_phase !== "baseline") continue;
      for (const [variantIndex, variant] of (item.detail_assets || []).entries()) {
        if (variant.image_url) continue;
        const variantJobName = `${project.id}_${item.generation_nonce || "legacy"}_${group.kind}_${item.name}_angle_${variantIndex + 2}`;
        const completed = await assetService.characterResult<{ status:string; image?:{ url:string }; error?:string }>(variantJobName).catch(() => null);
        if (!isCurrentProjectSession(project.id, session)) return;
        if (completed?.ok && completed.data.status === "completed" && completed.data.image?.url) {
          variant.image_url = completed.data.image.url;
          variant.status = "waiting_confirmation";
          variant.error = "";
          recovered = true;
        } else if (completed?.ok && completed.data.status === "failed") {
          variant.status = "failed";
          variant.error = userFacingGenerationError(completed.data.error);
          recovered = true;
        } else if (variant.status === "generating") {
          variant.status = "pending";
          variant.error = "上次角度任务已中断，请继续生成";
          recovered = true;
        }
      }
      const failedVariant = item.detail_assets?.find(variant => variant.status === "failed");
      item.status = hasCompleteAssetVariants(group.kind, item) ? "confirmed" : failedVariant ? "failed" : "waiting_confirmation";
      item.error = failedVariant ? "部分固定角度图片生成失败，可继续生成" : "";
    }
    projectLoadIsolation.mark(project.id, session, "assets", result.stage.data.status === "generating");
    const profiles = [...characterProfiles.value, ...sceneProfiles.value, ...propProfiles.value];
    assetStatus.value = profiles.length && profiles.every(item => item.status === "confirmed") ? "confirmed" : profiles.some(item => item.status === "generating") ? "generating" : profiles.some(item => item.image_url) ? "waiting_confirmation" : result.stage.data.status === "generating" ? "failed" : result.stage.data.status || "pending";
    const failedProfile = profiles.find(item => item.status === "failed" && !item.image_url);
    assetError.value = failedProfile ? `${failedProfile.name}：${failedProfile.error || "定位基准图生成失败，请继续生成"}` : "";
    const firstCompleteEpisode = completeStoryboardEpisodes.value[0];
    const censusStale = Boolean(firstCompleteEpisode) && (result.stage.data.census_version !== 2 || !assetSourceEpisodes.value.includes(firstCompleteEpisode));
    if (censusStale) {
      characterProfiles.value = [];
      sceneProfiles.value = [];
      propProfiles.value = [];
      assetSourceEpisodes.value = [];
      assetStatus.value = "pending";
      assetError.value = "旧资产清单已失效，请点击重新提取完整资产档案";
      await persistAssetState();
      await seedAssetCardsFromStoryboard(project, storyboardShots.value, session);
      return;
    }
    if (recovered) await persistAssetState();
    if (removedInvalidScenes && storyboardShots.value.length) await seedAssetCardsFromStoryboard(project, storyboardShots.value, session);
  } catch (error) { assetError.value = error instanceof Error ? error.message : "资产数据加载失败"; }
}

let assetPersistQueue:Promise<void> = Promise.resolve();
async function persistAssetState(project = activeProjectRecord.value, session = projectSession) {
  if (!project || !isCurrentProjectSession(project.id, session)) return;
  const data = JSON.parse(JSON.stringify({ characters:characterProfiles.value, scenes:sceneProfiles.value, props:propProfiles.value, status:assetStatus.value, error:assetError.value, source_episodes:assetSourceEpisodes.value, census_version:2 } satisfies AssetStageData)) as AssetStageData;
  const write = async () => {
    let lastError:unknown;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      if (!isCurrentProjectSession(project.id, session)) return;
      try {
        await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"assets", data });
        return;
      } catch (error) {
        lastError = error;
        if (attempt < 2) await new Promise(resolve => window.setTimeout(resolve, 250 * (attempt + 1)));
      }
    }
    throw lastError;
  };
  const current = assetPersistQueue.catch(() => undefined).then(write);
  assetPersistQueue = current.then(() => undefined, () => undefined);
  await current;
}

async function prepareAssetProfilesFromStoryboard(project:StoredProject) {
  if (!storyboardShots.value.length) return;
  const session = projectSession;
  await seedAssetCardsFromStoryboard(project, storyboardShots.value, session);
  await storyboardAssetExtractionQueue.catch(() => undefined);
  if (!isCurrentProjectSession(project.id, session)) return;
  const episodes = completeStoryboardEpisodes.value;
  if (episodes.length) await runProductionAssetExtraction("manual", project, session, episodes, true);
}

let assetResultRecoveryRunning = false;
const autoResumedInterruptedAssetJobs = new Set<string>();
async function recoverCompletedAssetImages() {
  const project = activeProjectRecord.value;
  if (!project || assetResultRecoveryRunning) return;
  const session = projectSession;
  assetResultRecoveryRunning = true;
  let recovered = false;
  let shouldResumeInterruptedJob = false;
  try {
    for (const group of [
      { kind:"character", items:characterProfiles.value },
      { kind:"prop", items:propProfiles.value },
      { kind:"scene", items:sceneProfiles.value },
    ] as const) for (const item of group.items) {
      if (!item.image_url) {
        const jobName = assetBaselineJobName(project.id, group.kind, item);
        const completed = await assetService.characterResult<{ status:string; image?:{ url:string }; error?:string }>(jobName).catch(() => null);
        if (!isCurrentProjectSession(project.id, session)) return;
        if (completed?.ok && completed.data.status === "completed" && completed.data.image?.url) {
          item.image_url = completed.data.image.url;
          item.status = "waiting_confirmation";
          item.error = "";
          recovered = true;
          await revealCompletedUnit();
        } else if (completed?.ok && completed.data.status === "failed" && item.status === "generating") {
          // A completed backend failure is a real terminal result. Keep it
          // visible until the user explicitly retries; presenting it as pending
          // hides the quality-gate reason and makes a stopped batch look idle.
          item.status = "failed";
          item.error = userFacingGenerationError(completed.data.error);
          recovered = true;
          const interrupted = String(completed.data.error || "").includes("图片任务已中断");
          if (interrupted && !autoResumedInterruptedAssetJobs.has(jobName)) {
            autoResumedInterruptedAssetJobs.add(jobName);
            shouldResumeInterruptedJob = true;
          }
        }
      }
      if (!item.image_url) continue;
      for (const [variantIndex, variant] of (item.detail_assets || []).entries()) {
        if (variant.image_url || variant.status !== "generating") continue;
        const variantJobName = `${project.id}_${item.generation_nonce || "legacy"}_${group.kind}_${item.name}_angle_${variantIndex + 2}`;
        const completed = await assetService.characterResult<{ status:string; image?:{ url:string }; error?:string }>(variantJobName).catch(() => null);
        if (!isCurrentProjectSession(project.id, session)) return;
        if (completed?.ok && completed.data.status === "completed" && completed.data.image?.url) {
          variant.image_url = completed.data.image.url;
          variant.status = "waiting_confirmation";
          variant.error = "";
          recovered = true;
          await revealCompletedUnit();
        } else if (completed?.ok && completed.data.status === "failed") {
          variant.status = "failed";
          variant.error = userFacingGenerationError(completed.data.error);
          item.status = "failed";
          item.error = `部分固定角度图片生成失败，可继续生成`;
          recovered = true;
        }
      }
    }
    if (recovered) {
      const profiles = [...characterProfiles.value, ...sceneProfiles.value, ...propProfiles.value];
      assetStatus.value = profiles.every(item => item.status === "confirmed") ? "confirmed" : profiles.some(item => item.status === "generating") ? "generating" : profiles.some(item => item.image_url) ? "waiting_confirmation" : "pending";
      const failedProfile = profiles.find(item => item.status === "failed");
      assetError.value = profiles.some(item => item.status === "generating") ? "" : failedProfile ? `${failedProfile.name}：${failedProfile.error || "定位基准图生成失败，请继续生成"}` : "";
      await persistAssetState(project, session);
    }
  } finally {
    assetResultRecoveryRunning = false;
  }
  if (shouldResumeInterruptedJob && isCurrentProjectSession(project.id, session)) {
    assetStatus.value = "pending";
    assetError.value = "上次资产图片任务已中断，请点击生成图片继续";
    await persistAssetState(project, session);
  }
}
const assetResultRecoveryTimer = window.setInterval(() => {
  const needsReconciliation = [...characterProfiles.value, ...sceneProfiles.value, ...propProfiles.value].some(item => (
    !item.image_url || item.status === "generating" || (item.detail_assets || []).some(variant => variant.status === "generating")
  ));
  if (rightPanelMode.value === "assets" && needsReconciliation) void recoverCompletedAssetImages();
}, 2000);
onBeforeUnmount(() => window.clearInterval(assetResultRecoveryTimer));

function mergeAssetProfiles<T extends CharacterProfile | SceneProfile | PropProfile>(existing:T[], incoming:T[], authoritativeSuccess = false) {
  const key = (item:T) => item.name.trim().replace(/\s+/g, "").toLocaleLowerCase("zh-CN");
  const oldByName = new Map(existing.map(item => [key(item), item]));
  const merged = incoming.map(item => {
    const old = oldByName.get(key(item));
    if (!old) return { ...item, status:"pending", generation_nonce:crypto.randomUUID() } as T;
    oldByName.delete(key(item));
    return clearResolvedAssetStageConflict({
      ...old,
      ...item,
      status:old.status || "pending",
      image_url:old.image_url,
      error:old.error,
      ...("episodes" in item ? { episodes:[...new Set([...(Array.isArray((old as SceneProfile | PropProfile).episodes) ? (old as SceneProfile | PropProfile).episodes : []), ...(Array.isArray((item as SceneProfile | PropProfile).episodes) ? (item as SceneProfile | PropProfile).episodes : [])])].sort((a, b) => a - b) } : {}),
    } as T, authoritativeSuccess);
  });
  return [...merged, ...oldByName.values()];
}

function normalizeAssetName(name:string) {
  return name.trim().replace(/\s+/g, "").toLocaleLowerCase("zh-CN");
}

function outlineCharacterProfile(character:NonNullable<OutlinePlan["characters"]>[number]):CharacterProfile {
  const role = character.identity || character.role || "核心角色";
  const personality = character.personality || "";
  const motivation = character.core_motivation || character.goal || "";
  const gender = /女主|女二|女性|女人|母亲|妻子|姐姐|妹妹/.test(role)
    ? "女性"
    : /男主|男二|男性|男人|父亲|丈夫|哥哥|弟弟/.test(role) ? "男性" : "";
  return {
    name:character.name,
    role,
    gender,
    age:"",
    appearance:"",
    hair:"",
    makeup:"",
    costume:"",
    temperament:personality,
    expression:"",
    identity_keywords:[role, personality].filter(Boolean),
    image_prompt:[role, personality, motivation, "中国人，自然东亚面孔，中国影视角色，单人物正面近照"].filter(Boolean).join("，"),
    status:"pending",
    generation_nonce:crypto.randomUUID(),
  };
}

async function seedAssetCardsFromStoryboard(project:StoredProject, shots:StoryboardShot[], session = projectSession, signal?:AbortSignal) {
  if (!isCurrentProjectSession(project.id, session) || signal?.aborted || !shots.length) return;
  const sourceText = shots.flatMap(shot => [shot.scene, shot.visual, shot.action, shot.dialogue, shot.image_prompt]).join("\n");
  const characters = (outlinePlan.value?.characters || [])
    .filter(character => character.name?.trim() && sourceText.includes(character.name.trim()))
    .map(outlineCharacterProfile);
  const firstEpisodeByScene = new Map<string, number>();
  for (const shot of shots) {
    const name = sceneLocationFromShot(shot);
    if (isReusableSceneAssetName(name) && !firstEpisodeByScene.has(name)) firstEpisodeByScene.set(name, shot.episode);
  }
  const scenes:SceneProfile[] = [...firstEpisodeByScene].map(([name, firstEpisode]) => ({
    name,
    location:name,
    period:"",
    first_episode:firstEpisode,
    episodes:[...new Set(shots.filter(shot => String(shot.scene || "").trim() === name).map(shot => shot.episode))].sort((a, b) => a - b),
    layout:"等待资产提取补全",
    lighting:"按分镜与项目风格锁定",
    fixed_elements:[],
    continuity_rules:"保持场景布局、时空和光影连续",
    image_prompt:`${name}，${project.style}，纯空场景，无人物`,
    status:"pending",
    generation_nonce:crypto.randomUUID(),
  }));
  characterProfiles.value = mergeAssetProfiles(characterProfiles.value, characters);
  sceneProfiles.value = mergeAssetProfiles(sceneProfiles.value, scenes);
  if (allAssetProfiles.value.length && assetStatus.value !== "generating") assetStatus.value = "pending";
  if (!isCurrentProjectSession(project.id, session) || signal?.aborted) return;
  await persistAssetState(project, session);
}

const queuedStoryboardAssetEpisodes = new Set<string>();
let storyboardAssetExtractionQueue:Promise<void> = Promise.resolve();
function queueStoryboardAssetExtraction(project:StoredProject, session:number, episode:number) {
  const key = `${project.id}:${session}:${episode}`;
  if (queuedStoryboardAssetEpisodes.has(key) || assetSourceEpisodes.value.includes(episode)) return;
  queuedStoryboardAssetEpisodes.add(key);
  storyboardAssetExtractionQueue = storyboardAssetExtractionQueue.catch(() => undefined).then(async () => {
    if (!isCurrentProjectSession(project.id, session)) return;
    await runProductionAssetExtraction("manual", project, session, [episode], false);
    if (!isCurrentProjectSession(project.id, session) || assetStatus.value === "failed") return;
    // A completed episode must immediately continue from asset-card extraction to
    // baseline generation. The shared promise keeps episodes and heavy image work
    // strictly serial while the storyboard producer may continue in parallel.
    await enqueueAssetOperation(`${project.id}:generate-all`, "生成资产图片", () => generateAllAssetImages(project, session));
  }).finally(() => queuedStoryboardAssetEpisodes.delete(key));
}

function reconcileOutlineCharacters(extracted:CharacterProfile[], requiredNames = (outlinePlan.value?.characters || []).map(character => character.name)) {
  const extractedByName = new Map(extracted.map(item => [normalizeAssetName(item.name), item]));
  const required = new Set(requiredNames.map(normalizeAssetName));
  const reconciled = (outlinePlan.value?.characters || []).filter(character => character.name?.trim() && required.has(normalizeAssetName(character.name))).map(character => {
    const fallback = outlineCharacterProfile(character);
    const matched = extractedByName.get(normalizeAssetName(character.name));
    if (!matched) return fallback;
    extractedByName.delete(normalizeAssetName(character.name));
    return {
      ...fallback,
      ...matched,
      name:character.name,
      role:matched.role || fallback.role,
      image_prompt:matched.image_prompt || fallback.image_prompt,
    };
  });
  return [...reconciled, ...extractedByName.values()];
}

const assetExtractionPromises = new Map<string, Promise<void>>();
function extractProductionAssets(source:"outline" | "script" | "manual" = "manual"):Promise<void> {
  const project = activeProjectRecord.value;
  if (!project) return Promise.resolve();
  const session = projectSession;
  const key = `${project.id}:${session}`;
  const active = assetExtractionPromises.get(key);
  if (active) return active;
  const transaction = runProductionAssetExtraction(source, project, session);
  const singleFlight = transaction.finally(() => { if (assetExtractionPromises.get(key) === singleFlight) assetExtractionPromises.delete(key); });
  assetExtractionPromises.set(key, singleFlight);
  return singleFlight;
}

async function runProductionAssetExtraction(source:"outline" | "script" | "manual", project:StoredProject, session:number, targetEpisodeOverride:number[] = [], commitStage = true) {
  if (!requireEnabledRobot("视觉资产")) return;
  if (!isCurrentProjectSession(project.id, session) || assetStatus.value === "generating") return;
  const completeEpisodes = completeStoryboardEpisodes.value;
  const targetEpisodes = targetEpisodeOverride.length ? targetEpisodeOverride.filter(episode => completeEpisodes.includes(episode)) : workflowEpisode.value > 0 && completeEpisodes.includes(workflowEpisode.value)
    ? [workflowEpisode.value]
    : completeEpisodes.length ? [completeEpisodes[0]] : [];
  if (source !== "outline" && !targetEpisodes.length) return;
  const targetEpisodeSet = new Set(targetEpisodes);
  const targetShots = storyboardShots.value.filter(shot => targetEpisodeSet.has(shot.episode));
  const targetScripts = scripts.value.filter(script => targetEpisodeSet.has(script.episode));
  const scopedText = [
    ...targetScripts.map(script => script.content),
    ...targetShots.flatMap(shot => [shot.scene, shot.visual, shot.action, shot.dialogue, shot.image_prompt]),
  ].join("\n");
  const requiredCharacters = (outlinePlan.value?.characters || []).filter(character => character.name?.trim() && scopedText.includes(character.name.trim())).map(character => character.name.trim());
  assetController.value?.abort();
  const controller = new AbortController();
  const extractionIdentity = { ...projectIdentity, id:project.id };
  assetController.value = controller;
  assetStatus.value = "generating";
  assetError.value = "";
  await persistAssetState(project, session);
  if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
  try {
    const extractionRequest = {
      ...productionTaskContext(project),
      outline:[
        "核心人物简介：",
        ...(outlinePlan.value?.characters || []).map(character => `${character.name}｜${character.identity || character.role || "核心角色"}｜${character.personality || ""}｜${character.core_motivation || character.goal || ""}`),
        "故事总纲：",
        outlinePlan.value?.general_outline || "",
        ...outlineEpisodes.value.filter(episode => source === "outline" || targetEpisodeSet.has(episode.episode)).map(episode => `第${episode.episode}集 ${episode.title}\n${episode.synopsis}`),
      ].join("\n\n"),
      scripts:source === "outline" ? "" : [
        ...targetScripts.map(script => `第${script.episode}集 ${script.title}\n${script.content}`),
        ...targetShots.map(shot => `第${shot.episode}集镜头${shot.shot_number}｜场景：${shot.scene}｜画面：${shot.visual}｜动作：${shot.action}｜人物服装：${(shot.characters || []).map(character => `${character.id}=${character.costume_id}@${character.costume_version}`).join("、") || "无"}｜道具与人物：${shot.image_prompt}`),
      ].join("\n\n"),
      extraction_phase:source,
      target_episodes:targetEpisodes,
      required_characters:requiredCharacters,
      style:project.style,
      max_characters:12,
      context:{ ...productionTaskContext(project), topic:project.topic, style:project.style, language:project.language, duration:Math.round((project.duration_min + project.duration_max) / 2), aspect:"9:16" },
    };
    const result = commitStage
      ? (await productionLedgerService.runStage<{ characters:CharacterProfile[]; scenes:SceneProfile[]; props:PropProfile[] }>({ ...extractionRequest, stage:"assets", audit_enabled:false }, controller.signal)).result
      : await assetService.extractCharacters<{ characters:CharacterProfile[]; scenes:SceneProfile[]; props:PropProfile[] }>({ ...extractionRequest, extraction_phase:"storyboard_preview" }, controller.signal);
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    if (characterProfiles.value.length || sceneProfiles.value.length || propProfiles.value.length) {
      await projectService.createVersion({ ...projectIdentity, project_id:project.id, project_name:project.name, stage:"before-assets-merge", reason:"全剧资产增量合并前归档" });
    }
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    characterProfiles.value = mergeAssetProfiles(characterProfiles.value, reconcileOutlineCharacters(result.characters || [], requiredCharacters), commitStage);
    sceneProfiles.value = mergeAssetProfiles(sceneProfiles.value, normalizeEmptySceneProfiles(result.scenes || []), commitStage);
    propProfiles.value = mergeAssetProfiles(propProfiles.value, result.props || [], commitStage);
    assetSourceEpisodes.value = [...new Set([...assetSourceEpisodes.value, ...targetEpisodes])].sort((a, b) => a - b);
    assetStatus.value = commitStage ? "waiting_confirmation" : "pending";
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    await persistAssetState(project, session);
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    if (commitStage) notify("人物、场景、道具档案已提取，等待确认");
  } catch (error) {
    if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) return;
    if (error instanceof Error && error.message.includes("production stage is already running: assets")) {
      for (let attempt = 0; attempt < 240; attempt += 1) {
        if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) return;
        await new Promise(resolve => window.setTimeout(resolve, 500));
        if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) return;
        const running = await projectService.readStage<AssetStageData>({ ...extractionIdentity, stage:"assets" }).catch(() => null);
        if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) return;
        if (!running?.stage) continue;
        const data = running.stage.data;
        if (data.status === "generating") continue;
        if (!["waiting_confirmation", "confirmed", "completed"].includes(data.status)) {
          assetStatus.value = "failed";
          assetError.value = data.error || "资产提取任务未完成，请重新生成";
          await persistAssetState(project, session).catch(() => undefined);
          return;
        }
        if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) return;
        characterProfiles.value = mergeAssetProfiles(characterProfiles.value, data.characters || [], true);
        sceneProfiles.value = mergeAssetProfiles(sceneProfiles.value, normalizeEmptySceneProfiles(data.scenes || []), true);
        propProfiles.value = mergeAssetProfiles(propProfiles.value, data.props || [], true);
        assetSourceEpisodes.value = [...new Set([...(assetSourceEpisodes.value || []), ...(data.source_episodes || [])])].sort((left, right) => left - right);
        assetStatus.value = data.status || "waiting_confirmation";
        assetError.value = data.error || "";
        await persistAssetState(project, session);
        return;
      }
      assetStatus.value = "failed";
      assetError.value = "资产提取任务仍在运行，请稍后继续生成图片";
      await persistAssetState(project, session).catch(() => undefined);
      return;
    }
    assetStatus.value = "failed";
    assetError.value = error instanceof Error ? error.message : "资产档案提取失败";
    await persistAssetState(project, session).catch(() => undefined);
  } finally { if (assetController.value === controller) assetController.value = undefined; }
}

async function generateAssetBaseline(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, project = activeProjectRecord.value, session = projectSession, signal?:AbortSignal) {
  if (item.status === "generating") return;
  if (!project || !isCurrentProjectSession(project.id, session) || signal?.aborted) return;
  item.generation_nonce = crypto.randomUUID();
  const generationNonce = item.generation_nonce;
  const jobName = assetBaselineJobName(project.id, kind, item);
  const generationKey = assetSlideGenerationKey(kind, item.name, baselineSlideKey(kind));
  // A regeneration is a new immutable media generation.  Keep the currently
  // published image alive until the replacement has completed and its URL is
  // durably projected; purge-first made completed jobs and snapshots point at
  // deleted files when a queued regeneration followed a batch generation.
  const previousImageUrl = item.image_url;
  activeAssetGenerationKey.value = generationKey;
  item.baseline_confirmed_at = undefined;
  item.status = "generating";
  item.error = "";
  assetStatus.value = "generating";
  assetError.value = "";
  try {
    await persistAssetState(project, session);
    if (!isCurrentProjectSession(project.id, session) || signal?.aborted) return;
    const angles = fixedAssetAngles[kind];
    const subjectRule = kind === "character"
      ? "首张定位基准图，只生成一张独立图片且画面内只能有一个人物；严格0度正面平视完整全身照，脸、双肩、胸口、骨盆、双膝和双脚全部正对镜头，头部偏航角与翻滚角均接近0度，中性无表情，从完整发顶到完整鞋底全部入画，双手自然下垂，纯净中性灰背景；严禁左45度、右45度、侧面、背面、近照、半身、俯拍、仰拍、裁切头脚、多人、多姿势、多视角、拼图、宫格、分栏、接触表和同图重复人物"
      : kind === "scene" ? "只生成一张正常人眼高度45度空场景全景，展示空间纵深、墙地关系和固定陈设；人物数量严格为零，禁止人体、剪影、倒影中的人、镜中人、照片人物、海报人物、屏幕人物、雕像人形、文字、水印、拼图和鱼眼畸变" : "只生成一张单一完整道具45度三分之二视图，同时展示正面、顶面和侧面结构；纯中性灰背景，禁止人物、手、支架、文字、水印和额外物体";
    const identityPrompt = kind === "character" ? baselineIdentityPrompt(item.image_prompt) : item.image_prompt;
    const character = kind === "character" ? item as CharacterProfile : undefined;
    const result = await assetService.generateCharacter<{ image:{ url:string; character_lora?:{ id:string; path:string; sha256:string; base_model:string } } }>({ ...productionTaskContext(project), name:jobName, asset_kind:kind, asset_subject:item.name, asset_phase:"baseline", identity_prompt:kind === "character" ? identityPrompt : "", character_gender:character?.gender || "", character_lora_id:character?.character_lora_id || "", prompt:`${subjectRule}。${angles[0].prompt}。${identityPrompt}`, orientation:"portrait", width:928, height:1664, lora_mode:project.lora_mode, lora_id:project.lora_id }, signal);
    if (!isCurrentProjectSession(project.id, session) || signal?.aborted || item.generation_nonce !== generationNonce) return;
    item.image_url = result.image.url;
    if (character) item.view_contract = characterViewContract;
    if (character && result.image.character_lora) {
      character.character_lora_id = result.image.character_lora.id;
      character.character_lora_path = result.image.character_lora.path;
      character.character_lora_sha256 = result.image.character_lora.sha256;
      character.character_lora_base_model = result.image.character_lora.base_model;
    }
    item.detail_assets = angles.slice(1).map((angle, index) => ({ id:`${kind}-angle-${index + 2}`, label:angle.label, prompt:angle.prompt, status:"pending" }));
    item.confirmation_phase = "baseline";
    item.status = "waiting_confirmation";
    item.error = "";
    await persistAssetState(project, session);
    if (!isCurrentProjectSession(project.id, session) || signal?.aborted) return;
    await revealCompletedUnit();
  } catch (error) {
    if (!isCurrentProjectSession(project.id, session) || signal?.aborted) return;
    const payload = error && typeof error === "object" && "payload" in error ? (error as { payload?:unknown }).payload : null;
    const activeJob = payload && typeof payload === "object" && "active_job" in payload ? String((payload as { active_job?:unknown }).active_job || "") : "";
    const noncePrefix = `${project.id}_`;
    const nonceSuffix = `_${kind}_${item.name}_baseline`;
    if (activeJob.startsWith(noncePrefix) && activeJob.endsWith(nonceSuffix)) {
      item.generation_nonce = activeJob.slice(noncePrefix.length, -nonceSuffix.length);
      item.status = "generating";
      item.error = "";
      assetStatus.value = "generating";
      assetError.value = "";
      await persistAssetState(project, session).catch(() => undefined);
      return;
    }
    item.status = previousImageUrl ? "waiting_confirmation" : "failed";
    item.error = userFacingGenerationError(error instanceof Error ? error.message : "资产图生成失败");
    await persistAssetState(project, session).catch(() => undefined);
  } finally {
    if (isCurrentProjectSession(project.id, session) && !signal?.aborted && activeAssetGenerationKey.value === generationKey) activeAssetGenerationKey.value = "";
  }
}

async function generateAsset3D(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile) {
  const project = activeProjectRecord.value;
  if (!project || item.model3d_status === "generating") return;
  const session = projectSession;
  if (!item.image_url || !item.baseline_confirmed_at) {
    notify(`请先确认${kind === "character" ? "人物0°正面全身" : kind === "prop" ? "道具45°三分之二" : "场景45°空场景全景"}基准图，再生成3D资产`);
    return;
  }
  item.model3d_status = "generating";
  item.model3d_error = "";
  await persistAssetState(project, session);
  try {
    const accepted = await assetService.generate3D<{ job_id:string; status:string; phase:string }>({
      ...productionTaskContext(project),
      project_id:project.id,
      asset_kind:kind,
      asset_name:item.name,
      asset_prompt:item.image_prompt,
      source_baseline_url:item.image_url || "",
      reference_angle:kind === "character" ? "front_full" : "three_quarter_45",
      baseline_confirmed:Boolean(item.baseline_confirmed_at),
      dimensions:kind === "character" ? { height_m:1.7, inferred:true }
        : kind === "prop" ? { width_m:0.3, depth_m:0.3, height_m:0.3, inferred:true, category:(item as PropProfile).category }
        : { width_m:12, depth_m:12, height_m:4, inferred:true },
      ...(kind === "prop" ? {
        asset_type:(item as PropProfile).category === "服装" || (item as PropProfile).asset_type === "costume" ? "costume" : "prop",
        costume_owner:(item as PropProfile).owner || "",
        costume_id:(item as PropProfile).costume_id || "",
        costume_version:(item as PropProfile).costume_version || "v1",
        tags:Array.isArray((item as PropProfile).tags) ? (item as PropProfile).tags : [],
      } : {}),
      scene_layout:kind === "scene" ? { layout:(item as SceneProfile).layout, fixed_elements:(item as SceneProfile).fixed_elements } : undefined,
    });
    if (!isCurrentProjectSession(project.id, session)) return;
    item.model3d_job_id = accepted.job_id;
    await persistAssetState(project, session);
    let result:Asset3DResult | undefined;
    while (item.model3d_status === "generating") {
      await new Promise(resolve => window.setTimeout(resolve, 1500));
      if (!isCurrentProjectSession(project.id, session)) return;
      const job = await assetService.status3D<{ status:string; error?:string; result?:Asset3DResult }>(accepted.job_id, projectIdentity);
      if (!isCurrentProjectSession(project.id, session)) return;
      if (job.status === "completed" && job.result) { result = job.result; break; }
      if (job.status === "failed") throw new Error(job.error || "3D资产生成失败");
    }
    if (!result || item.model3d_status !== "generating") return;
    if (!isCurrentProjectSession(project.id, session)) return;
    item.model3d_result = result;
    item.model3d_status = "waiting_confirmation";
    item.model3d_error = "";
    await persistAssetState(project, session);
  } catch (error) {
    if (!isCurrentProjectSession(project.id, session)) return;
    const payload = error && typeof error === "object" && "payload" in error ? (error as { payload?:unknown }).payload : undefined;
    if (payload && typeof payload === "object" && "job_id" in payload) item.model3d_job_id = String((payload as { job_id?:unknown }).job_id || "");
    item.model3d_status = "failed";
    item.model3d_error = error instanceof Error ? error.message : "3D资产生成失败";
    await persistAssetState(project, session).catch(() => undefined);
  }
}

async function confirmAsset3D(item:CharacterProfile | SceneProfile | PropProfile) {
  const project = activeProjectRecord.value;
  if (!project || !item.model3d_result || !item.model3d_job_id) return;
  const session = projectSession;
  const kind = characterProfiles.value.includes(item as CharacterProfile) ? "character" : sceneProfiles.value.includes(item as SceneProfile) ? "scene" : "prop";
  const result = await assetService.confirm3D<Asset3DResult>({ project_id:project.id, asset_kind:kind, asset_name:item.name, job_id:item.model3d_job_id });
  if (!isCurrentProjectSession(project.id, session)) return;
  item.model3d_result = result;
  item.model3d_status = "confirmed";
  await persistAssetState(project, session);
}

async function stopAsset3D(item:CharacterProfile | SceneProfile | PropProfile) {
  const project = activeProjectRecord.value;
  if (!project) return;
  if (item.model3d_job_id) await assetService.stop3D(item.model3d_job_id, productionTaskContext(project)).catch(() => undefined);
  item.model3d_status = "failed";
  item.model3d_error = "3D资产任务已停止";
  await persistAssetState().catch(() => undefined);
}

async function generateAssetVariantsFromConfirmedBaseline(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, onlyVariant?:AssetVariant) {
  const project = activeProjectRecord.value;
  if (!project || !item.image_url || item.confirmation_phase !== "baseline") return;
  const session = projectSession;
  const controllerKey = `${project.id}:${kind}:${item.name}`;
  assetVariantControllers.get(controllerKey)?.abort();
  const controller = new AbortController();
  assetVariantControllers.set(controllerKey, controller);
  const stillCurrent = () => isCurrentProjectSession(project.id, session) && !controller.signal.aborted;
  const angles = fixedAssetAngles[kind];
  const currentVariants = item.detail_assets || [];
  const variants = angles.slice(1).map((angle, index) => currentVariants.find(variant => variant.label === angle.label) || ({
    id:`${kind}-angle-${index + 2}`, label:angle.label, prompt:angle.prompt, status:"pending" as const,
  }));
  item.detail_assets = variants;
  if (onlyVariant && !variants.includes(onlyVariant)) onlyVariant = variants.find(variant => variant.label === onlyVariant?.label);
  item.status = "generating";
  await persistAssetState(project, session);
  try {
    for (const [index, variant] of variants.entries()) {
      if (!stillCurrent()) return;
      if (onlyVariant && variant !== onlyVariant) continue;
      if (variant.image_url) {
        if (variant.status === "confirmed") continue;
        item.status = "waiting_confirmation";
        item.error = "";
        assetStatus.value = "waiting_confirmation";
        await persistAssetState(project, session);
        return;
      }
      variant.status = "generating";
      const generationKey = assetSlideGenerationKey(kind, item.name, variant.id);
      activeAssetGenerationKey.value = generationKey;
      await persistAssetState(project, session);
      if (!stillCurrent()) return;
      let targetPose = "";
      try {
      const angleIndex = angles.findIndex(angle => angle.label === variant.label);
      const angle = angles[angleIndex > 0 ? angleIndex : index + 1];
      targetPose = kind === "character"
        ? angle.label === "左45°全身" ? "left_45_full" : angle.label === "右45°全身" ? "right_45_full" : angle.label === "90°侧面全身" ? "side_90_full" : angle.label === "180°背面全身" ? "back_full" : angle.label === "0°正面半身" ? "front_half" : ""
        : "";
      const clothingReferenceUrl = kind === "character"
        ? (item as CharacterProfile).clothing_reference_url || item.image_url
        : "";
      const identityReferenceUrl = item.image_url;
      const result = await assetService.generateCharacter<{ image:{ url:string } }>({
        ...productionTaskContext(project),
        name:`${project.id}_${item.generation_nonce || "legacy"}_${kind}_${item.name}_angle_${angleIndex + 1}`,
        asset_kind:kind,
        asset_subject:`${item.name}:${angle.label}`,
        asset_phase:"variant",
        character_gender:kind === "character" ? (item as CharacterProfile).gender : "",
        character_lora_id:kind === "character" ? (item as CharacterProfile).character_lora_id || "" : "",
        prompt:`以已确认的0度正面全身基准图及当前已确认角度共同锁定同一人物。Maintain consistent character identity and costume details across all angles using only the confirmed front baseline and confirmed angle references.${kind === "character" ? (targetPose === "front_half" ? "严格0度正面平视、特写型半身构图；人物居中，从完整头顶到腰部裁切，头顶仅微小留白，手部完全出画；头部至腰部占画高约75%，双肩不触碰左右边缘且两侧留白适中；锁定眼型、眉形、鼻型、嘴型、脸型、耳形、发际线、妆容、发型、发色、肤色、年龄、体型、领口、服装和配饰；完全纯色无杂物背景。" : "必须是同一个人：眼型、眉形、鼻型、嘴型、脸型、耳形、发际线、发型、发色、肤色、年龄、服装、领口、领带及身体比例全部与正面基准图完全一致；严格从头顶到鞋底完整入画，双手、双腿、双脚完整；发顶上方纯背景留白至少8%，鞋底下方纯背景留白至少3%，两者均为最低值而非固定值；不得坐下、倚靠、手持物品或执行剧情动作；纯净单色背景，禁止场景、家具、道具和其他人物。") : "严格锁定主体身份、材质、颜色、布局和全部可见细节，只改变镜头角度。"}${kind === "scene" ? "必须保持纯空场景，人物数量为零，禁止任何真人、人形、人体局部、剪影、倒影、照片、海报或屏幕中的人物。" : ""}${angle.prompt}。${kind === "character" ? baselineIdentityPrompt(item.image_prompt) : item.image_prompt}`,
        orientation:"portrait", width:928, height:1664,
        references:[
          { name:`${item.name}-已确认0度正面全身基准图`, url:identityReferenceUrl },
          ...(kind === "character" ? (item.detail_assets || []).filter(asset => asset.image_url && asset.status === "confirmed" && asset !== variant).map(asset => ({ name:`${item.name}-${asset.label}`, url:asset.image_url! })) : []),
        ],
        clothing_reference_url:clothingReferenceUrl,
        reference_strategy:"locked_confirmed_baseline",
        target_pose:targetPose,
      }, controller.signal);
      if (!stillCurrent()) return;
      variant.image_url = result.image.url;
      variant.status = "waiting_confirmation";
      variant.error = "";
      } catch (error) {
        if (!stillCurrent()) return;
        variant.status = "failed";
        variant.error = error instanceof Error ? error.message : `${variant.label}生成失败`;
      }
      if (!stillCurrent()) return;
      if (variant.status === "waiting_confirmation") {
        item.status = "waiting_confirmation";
        item.error = "";
        assetStatus.value = "waiting_confirmation";
        if (activeAssetGenerationKey.value === generationKey) activeAssetGenerationKey.value = "";
      }
      await persistAssetState(project, session);
      if (!stillCurrent()) return;
      await revealCompletedUnit();
      if (variant.status === "waiting_confirmation") return;
      if (stillCurrent() && activeAssetGenerationKey.value === generationKey) activeAssetGenerationKey.value = "";
    }
    if (!stillCurrent()) return;
    const hasFailedVariant = variants.some(variant => variant.status === "failed");
    const firstFailedVariant = variants.find(variant => variant.status === "failed");
    item.status = hasCompleteAssetVariants(kind, item) ? "confirmed" : hasFailedVariant ? "failed" : "waiting_confirmation";
    item.error = firstFailedVariant
      ? `${firstFailedVariant.label}：${userFacingGenerationError(firstFailedVariant.error || "生成失败")}`
      : "";
    if (item.error) assetError.value = `${item.name}：${item.error}`;
    if (allAssetProfiles.value.every(value => value.status === "confirmed")) assetStatus.value = "confirmed";
    else assetStatus.value = "waiting_confirmation";
    await persistAssetState(project, session);
  } finally {
    if (assetVariantControllers.get(controllerKey) === controller) assetVariantControllers.delete(controllerKey);
  }
}

async function regenerateAssetPhotoSlide(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, slide:AssetPhotoSlide) {
  if (slide.key.startsWith("baseline")) return generateAssetBaseline(kind, item);
  const project = activeProjectRecord.value;
  if (!project) return;
  const session = projectSession;
  const variant = ensureAssetPhotoVariant(kind, item, slide);
  variant.image_url = undefined;
  variant.status = "pending";
  variant.error = "";
  item.confirmation_phase = "baseline";
  await persistAssetState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  await generateAssetVariantsFromConfirmedBaseline(kind, item, variant);
}

async function repairAssetPhotoSlide(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, slide:AssetPhotoSlide) {
  const project = activeProjectRecord.value;
  if (!project || !slide.imageUrl || item.status === "generating") return;
  const session = projectSession;
  const issue = window.prompt("请输入需要局部修复的瑕疵，例如：修复左手手指，其他区域保持不变", "仅修复瑕疵区域，人物身份、发型、服装、姿势、构图和背景保持不变");
  if (!issue?.trim()) return;
  const variant = slide.key.startsWith("baseline") ? undefined : ensureAssetPhotoVariant(kind, item, slide);
  const generationKey = assetSlideGenerationKey(kind, item.name, slide.key);
  activeAssetGenerationKey.value = generationKey;
  item.status = "generating";
  if (variant) variant.status = "generating";
  await persistAssetState(project, session);
  try {
    const result = await assetService.generateCharacter<{ image:{ url:string } }>({
      ...productionTaskContext(project),
      name:`${project.id}_${item.generation_nonce || "legacy"}_${kind}_${item.name}_${slide.key}_repair`,
      asset_kind:kind,
      asset_subject:`${item.name}:${slide.label}:局部修复`,
      asset_phase:"repair",
      prompt:`主动局部修复：${issue.trim()}。只允许修改瑕疵区域，禁止重画未遮罩区域，禁止改变人物身份、脸型、发型、服装、姿势、构图、背景与画风。`,
      references:[{ name:`${item.name}-${slide.label}`, url:slide.imageUrl }],
      orientation:"portrait", width:928, height:1664,
    });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (variant) { variant.image_url = result.image.url; variant.status = "confirmed"; variant.error = ""; }
    else { item.image_url = result.image.url; item.baseline_confirmed_at = undefined; item.confirmation_phase = "baseline"; item.status = "waiting_confirmation"; }
    item.error = "";
  } catch (error) {
    if (!isCurrentProjectSession(project.id, session)) return;
    if (variant) { variant.status = "failed"; variant.error = error instanceof Error ? error.message : "局部修复失败"; }
    item.status = "failed";
    item.error = error instanceof Error ? error.message : "局部修复失败";
  } finally {
    if (isCurrentProjectSession(project.id, session)) {
      if (activeAssetGenerationKey.value === generationKey) activeAssetGenerationKey.value = "";
      await persistAssetState(project, session);
    }
  }
}

function ensureAssetPhotoVariant(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, slide:AssetPhotoSlide):AssetVariant {
  const definitions = fixedAssetAngles[kind];
  const angleIndex = definitions.findIndex(definition => definition.label === slide.label);
  if (angleIndex <= 0) throw new Error(`无效的资产角度：${slide.label}`);
  const variants = item.detail_assets || (item.detail_assets = []);
  let variant = variants.find(candidate => candidate.label === slide.label);
  if (!variant) {
    variant = { id:`${kind}-angle-${angleIndex + 1}`, label:slide.label, prompt:definitions[angleIndex].prompt, status:"pending" };
    variants.push(variant);
    variants.sort((left, right) => definitions.findIndex(definition => definition.label === left.label) - definitions.findIndex(definition => definition.label === right.label));
  }
  return variant;
}

function openAssetPhotoReplacement(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile, slide:AssetPhotoSlide) {
  openAssetReplacement(item, slide.key.startsWith("baseline") ? undefined : ensureAssetPhotoVariant(kind, item, slide));
}

function generateAllAssetImages(project = activeProjectRecord.value, session = projectSession) {
  if (!project || !isCurrentProjectSession(project.id, session)) return;
  const flightKey = `${project.id}:${session}`;
  if (assetBatchFlight && assetBatchFlightKey === flightKey) return assetBatchFlight;
  if (assetBatchFlight && assetBatchFlightKey !== flightKey) reclaimAssetBatchProjection(assetBatchFlight, assetBatchController.value, activeAssetBatchToken);
  if (assetImagesRunning.value) return;
  const controller = new AbortController(); assetBatchController.value?.abort(); assetBatchController.value = controller;
  assetBatchEpoch += 1;
  const batchToken = crypto.randomUUID(); activeAssetBatchToken = batchToken; assetBatchFlightKey = flightKey;
  const transaction = runAssetImageBatch(project, session, controller, batchToken);
  const singleFlight = transaction.finally(async () => {
    const ownsProjection = assetBatchFlight === singleFlight && assetBatchController.value === controller && activeAssetBatchToken === batchToken;
    if (ownsProjection && isCurrentProjectSession(project.id, session)) {
      assetBatchGenerating.value = false; activeAssetGenerationKey.value = ""; activeAssetBatchToken = "";
      await persistAssetState(project, session).catch(() => undefined);
    }
    if (assetBatchFlight === singleFlight) { assetBatchFlight = undefined; assetBatchFlightKey = ""; }
    if (assetBatchController.value === controller) assetBatchController.value = undefined;
  });
  assetBatchFlight = singleFlight;
  return singleFlight;
}

async function runAssetImageBatch(project:StoredProject, session:number, controller:AbortController, batchToken:string) {
  const isCurrentBatch = () => isCurrentProjectSession(project.id, session) && !controller.signal.aborted && activeAssetBatchToken === batchToken;
  if (!isCurrentBatch()) return;
  assetBatchGenerating.value = true;
  const authoritativeAssetStageReady = async () => {
    const [projection, workflow] = await Promise.all([
      projectService.readStage<AssetStageData>({ ...projectIdentity, id:project.id, stage:"assets" }).catch(() => null),
      productionLedgerService.workflow(productionTaskContext(project)).catch(() => null),
    ]);
    return successfulAssetStageStatuses.has(String(projection?.stage?.data.status || ""))
      && ["pending_confirmation", "completed"].includes(String(workflow?.workflow.stages.assets || ""));
  };
  if (!await authoritativeAssetStageReady()) {
    await runProductionAssetExtraction("manual", project, session);
    if (!isCurrentBatch()) return;
    if (!await authoritativeAssetStageReady()) {
      assetBatchGenerating.value = false;
      assetStatus.value = "failed";
      assetError.value ||= "资产权威阶段尚未完成，请先重试资产提取";
      await persistAssetState(project, session).catch(() => undefined);
      return;
    }
  }
  if (String(assetError.value || "").trim() === "production stage is already running: assets") {
      const authoritative = await projectService.readStage<AssetStageData>({ ...projectIdentity, id:project.id, stage:"assets" }).catch(() => null);
      if (!isCurrentBatch()) return;
      const stage = authoritative?.stage?.data;
      if (stage && stage.status !== "generating" && !String(stage.error || "").trim()) {
        if (!isCurrentBatch()) return;
        characterProfiles.value = mergeAssetProfiles(characterProfiles.value, stage.characters || [], successfulAssetStageStatuses.has(stage.status));
        sceneProfiles.value = mergeAssetProfiles(sceneProfiles.value, normalizeEmptySceneProfiles(stage.scenes || []), successfulAssetStageStatuses.has(stage.status));
        propProfiles.value = mergeAssetProfiles(propProfiles.value, stage.props || [], successfulAssetStageStatuses.has(stage.status));
        if (!isCurrentBatch()) return;
        assetStatus.value = stage.status || "pending";
        assetError.value = "";
        if (!isCurrentBatch()) return;
        await persistAssetState(project, session).catch(() => undefined);
      }
  }
  if (!allAssetProfiles.value.length) {
    await runProductionAssetExtraction("manual", project, session);
    if (!isCurrentBatch()) return;
    if (assetStatus.value === "failed") return;
    if (!allAssetProfiles.value.length) return;
  }
  assetBatchPaused.value = false;
  if (!isCurrentBatch()) return;
  assetStatus.value = "generating";
  assetError.value = "";
  if (!isCurrentBatch()) return;
  await persistAssetState(project, session).catch(() => undefined);
  if (!isCurrentBatch()) return;
  // The page-level action is resumable only: preserve every completed asset.
  // A destructive replacement is allowed exclusively through the individual card regenerate action.
  // The generation queue must be identical to the order rendered on the asset page.
  // Do not reprioritize by role, gender or any model-derived metadata.
  const targets:Array<{ kind:"character" | "scene" | "prop"; item:CharacterProfile | SceneProfile | PropProfile }> = [
    ...characterProfiles.value.map(item => ({ kind:"character" as const, item })),
    ...propProfiles.value.map(item => ({ kind:"prop" as const, item })),
    ...sceneProfiles.value.map(item => ({ kind:"scene" as const, item })),
  ].filter(({ item }) => !item.image_url);
  for (const { item } of targets) {
    if (!item.image_url) { item.status = "pending"; item.error = ""; }
  }
  if (!isCurrentBatch()) return;
  await persistAssetState(project, session);
  try {
    for (const target of targets) {
      if (assetBatchPaused.value || !isCurrentBatch()) break;
      if (!isCurrentBatch()) return;
      await generateAssetBaseline(target.kind, target.item, project, session, controller.signal);
      if (!isCurrentBatch()) return;
      if (!target.item.image_url) {
        assetBatchPaused.value = true;
        assetError.value = `${target.item.name}：${target.item.error || "定位基准图生成失败，请继续生成"}`;
        break;
      }
    }
    if (!assetBatchPaused.value) {
      const missingBaselines = allAssetProfiles.value.filter(item => !item.image_url);
      assetStatus.value = missingBaselines.length ? "failed" : "waiting_confirmation";
      assetError.value = missingBaselines.length ? `${missingBaselines[0].name}：${missingBaselines[0].error || "定位基准图生成失败，请继续生成"}` : "全部定位基准图已生成，请统一人工确认";
    } else {
      assetStatus.value = "waiting_confirmation";
    }
  } finally {
    if (isCurrentBatch()) {
      assetBatchGenerating.value = false;
      activeAssetGenerationKey.value = "";
      activeAssetBatchToken = "";
      await persistAssetState(project, session).catch(() => undefined);
    }
  }
}

async function confirmAsset(item:CharacterProfile | SceneProfile | PropProfile) {
  if (!canAcceptAssetBaseline(item)) { notify("当前定位基准图状态不可确认"); return; }
  const project = activeProjectRecord.value;
  if (!project) { notify("当前项目尚未加载完成"); return; }
  const session = projectSession;
  // A failed sibling remains on its own card. Clear only a card-scoped error;
  // real stage errors must survive confirmation of an unrelated character.
  const currentAssetError = String(assetError.value || "").trim();
  if (allAssetProfiles.value.some(profile => currentAssetError.startsWith(`${profile.name}：`))) assetError.value = "";
  const character = characterProfiles.value.includes(item as CharacterProfile);
  const scene = sceneProfiles.value.includes(item as SceneProfile);
  const kind = character ? "character" : scene ? "scene" : "prop";
  if (character) (item as CharacterProfile).clothing_reference_url = item.image_url;
  const identity = { ...projectIdentity, project_id:project.id };
  const baselineFingerprint = compactFingerprint({ profile:item, image_url:item.image_url });
  const scopeId = `${kind}:${item.name}`;
  item.confirmation_phase = "baseline";
  const currentVariants = item.detail_assets || [];
  item.detail_assets = fixedAssetAngles[kind].slice(1).map((angle, index) => currentVariants.find(variant => variant.label === angle.label) || ({
    id:`${kind}-angle-${index + 2}`, label:angle.label, prompt:angle.prompt, status:"pending",
  }));
  item.status = "generating";
  item.error = "";
  const firstPendingVariant = item.detail_assets.find(variant => !variant.image_url);
  if (firstPendingVariant) {
    firstPendingVariant.status = "generating";
    activeAssetGenerationKey.value = assetSlideGenerationKey(kind, item.name, firstPendingVariant.id);
  }
  assetIntroOpen.value = "";
  notify(`已确认${item.name}定位基准图，正在生成其余角度`);
  await persistAssetState(project, session);
  try {
    await productionLedgerService.upsert({ ...identity, stage:"assets", scope_type:"asset", scope_id:scopeId, lifecycle:"pending_confirmation", stage_substate:"baseline_pending_confirmation", content_fingerprint:baselineFingerprint, audit_batch_id:"manual-confirmation", progress:{ completed:1, total:1 } });
    if (!isCurrentProjectSession(project.id, session)) return;
    await productionLedgerService.confirmAsset({ ...identity, scope_id:scopeId, phase:"baseline" });
  } catch (error) {
    if (!isCurrentProjectSession(project.id, session)) return;
    item.status = "waiting_confirmation";
    for (const variant of item.detail_assets) if (!variant.image_url) variant.status = "pending";
    item.error = error instanceof Error ? error.message : "基准图确认同步失败";
    assetError.value = `${item.name}：${item.error}`;
    await persistAssetState(project, session).catch(() => undefined);
    return;
  }
  if (!isCurrentProjectSession(project.id, session)) return;
  item.baseline_confirmed_at = new Date().toISOString();
  await persistAssetState(project, session).catch(() => undefined);
  if (kind === "scene" || kind === "prop") {
    item.detail_assets = [];
    item.status = "confirmed";
    await persistAssetState(project, session).catch(() => undefined);
    if (!isCurrentProjectSession(project.id, session)) return;
    await generateAsset3D(kind, item);
    return;
  }
  if (!isCurrentProjectSession(project.id, session)) return;
  await generateAssetVariantsFromConfirmedBaseline(kind, item).catch(async error => {
    if (!isCurrentProjectSession(project.id, session)) return;
    item.status = "waiting_confirmation";
    item.error = error instanceof Error ? error.message : "固定角度图片生成失败";
    assetError.value = `${item.name}：${userFacingGenerationError(item.error)}`;
    await persistAssetState(project, session).catch(() => undefined);
  });
}

async function confirmAssetVariant(item:CharacterProfile | SceneProfile | PropProfile, variant:AssetVariant) {
  if (variant.status !== "waiting_confirmation" || !variant.image_url) return;
  const project = activeProjectRecord.value;
  if (!project) return;
  const session = projectSession;
  variant.status = "confirmed";
  const kind = characterProfiles.value.includes(item as CharacterProfile) ? "character" : sceneProfiles.value.includes(item as SceneProfile) ? "scene" : "prop";
  item.status = hasCompleteAssetVariants(kind, item) ? "confirmed" : "waiting_confirmation";
  await persistAssetState(project, session);
  if (!isCurrentProjectSession(project.id, session)) return;
  if (item.status !== "confirmed") await generateAssetVariantsFromConfirmedBaseline(kind, item);
}

async function upscaleWorkflowImage(name:string, imageUrl?:string) {
  if (!imageUrl) return;
  const project = activeProjectRecord.value;
  if (!project) return;
  const session = projectSession;
  try {
    const result = await mediaService.imageUpscale<{ image_url:string; path:string }>({ name, image_url:imageUrl });
    if (!isCurrentProjectSession(project.id, session)) return;
    window.open(result.image_url, "_blank", "noopener,noreferrer");
    notify(`${name}增强版已生成，原图保持不变`);
  } catch (error) { if (isCurrentProjectSession(project.id, session)) notify(error instanceof Error ? error.message : "图片超分失败"); }
}

async function refineShotIdentity(item:ShotImageItem, mode:"pulid"|"reactor") {
  const shot = storyboardShots.value.find(value => value.episode === item.episode && value.shot_number === item.shot_number);
  const text = `${shot?.visual || ""}${shot?.action || ""}`;
  const character = characterProfiles.value.find(value => value.image_url && text.includes(value.name));
  if (!item.image_url || !character?.image_url) return notify("当前镜头没有可用的人物正面参考图");
  try {
    const result = await mediaService.identityRefine<{ image_url:string; mode:string }>({ name:`第${item.episode}集-镜头${item.shot_number}`, image_url:item.image_url, face_reference_url:character.image_url, mode });
    item.image_url = result.image_url; item.status = "waiting_confirmation"; await persistShotImageState();
    notify(`${mode === "pulid" ? "PuLID" : "ReActor"}身份修正完成`);
  } catch (error) { notify(error instanceof Error ? error.message : "人物身份修正失败"); }
}

function openAssetReplacement(item:CharacterProfile | SceneProfile | PropProfile, variant?:AssetVariant) {
  assetReplaceTarget.value = { item, variant };
  assetReplaceInput.value?.click();
}

async function onAssetReplacement(event:Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0]; input.value = "";
  const target = assetReplaceTarget.value; assetReplaceTarget.value = undefined;
  const project = activeProjectRecord.value;
  if (!file || !target || !project) return;
  const session = projectSession;
  const validationError = await validateMediaFile(file);
  if (!isCurrentProjectSession(project.id, session)) return;
  if (validationError || !file.type.startsWith("image/")) return notify(validationError || "只能替换为图片文件");
  return enqueueAssetOperation(`${project.id}:import:${target.item.name}:${target.variant?.id || "baseline"}`, `导入${target.item.name}图片`, async () => {
   try {
    const dataUrl = await readFileAsDataUrl(file);
    if (!isCurrentProjectSession(project.id, session)) return;
    const saved = await resourceService.save({ ...productionTaskContext(project), plugin_key:"short-video-drama", scope:"project", project_id:project.id, kind:target.variant ? "asset_variant" : "asset_baseline", name:file.name, data_url:dataUrl, metadata:{ asset_name:target.item.name, variant_id:target.variant?.id || "baseline" } });
    if (!isCurrentProjectSession(project.id, session)) return;
    const imageUrl = resourceService.mediaUrl(saved.resource, projectIdentity);
    const expected = target.variant?.prompt || target.item.image_prompt;
    const applyUploadedImage = (auditSummary = "") => {
      if (target.variant) {
        target.variant.image_url = imageUrl; target.variant.audit_summary = auditSummary; target.variant.status = "waiting_confirmation"; target.variant.error = "";
        if (characterProfiles.value.includes(target.item as CharacterProfile) && target.variant.label === "全身") (target.item as CharacterProfile).clothing_reference_url = imageUrl;
      } else {
        target.item.image_url = imageUrl; target.item.baseline_confirmed_at = undefined; target.item.error = ""; target.item.confirmation_phase = "baseline";
      }
      const kind = characterProfiles.value.includes(target.item as CharacterProfile) ? "character" : sceneProfiles.value.includes(target.item as SceneProfile) ? "scene" : "prop";
      if (kind === "character" && !target.variant) target.item.view_contract = characterViewContract;
      target.item.status = assetUploadComplete(target.item) ? "confirmed" : "waiting_confirmation";
    };
    if (!enabledSkills.value.includes("审核")) {
      applyUploadedImage();
      await persistAssetState(project, session); return;
    }
    const audit = await assetService.semanticAudit<{ passed:boolean; summary:string }>({ ...productionTaskContext(project), image_url:imageUrl, expected_visual:expected, expected_characters:characterProfiles.value.includes(target.item as CharacterProfile) ? [target.item.name] : [] });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (audit.passed) applyUploadedImage(audit.summary);
    else if (target.variant) { target.variant.image_url = imageUrl; target.variant.audit_summary = audit.summary; target.variant.status = "failed"; target.variant.error = `替换图审核未通过：${audit.summary}`; }
    else { target.item.image_url = imageUrl; target.item.status = "failed"; target.item.error = `替换图审核未通过：${audit.summary}`; target.item.confirmation_phase = "baseline"; }
    await persistAssetState(project, session);
   } catch (error) { if (isCurrentProjectSession(project.id, session)) notify(error instanceof Error ? error.message : "替换图片失败"); }
  });
}

async function stopAssetGeneration(kind:"character" | "scene" | "prop", item:CharacterProfile | SceneProfile | PropProfile) {
  const project = activeProjectRecord.value;
  if (!project) return;
  const generatingVariantIndex = (item.detail_assets || []).findIndex(variant => variant.status === "generating");
  const jobName = generatingVariantIndex >= 0
    ? `${project.id}_${item.generation_nonce || "legacy"}_${kind}_${item.name}_angle_${generatingVariantIndex + 2}`
    : assetBaselineJobName(project.id, kind, item);
  await assetService.stopCharacter(jobName, productionTaskContext(project)).catch(() => undefined);
  if (generatingVariantIndex >= 0 && item.detail_assets) item.detail_assets[generatingVariantIndex].status = "pending";
  item.status = "failed";
  item.error = "已停止生成";
  activeAssetGenerationKey.value = "";
  await persistAssetState();
}

type ShotImageStageData = { items:ShotImageItem[]; status:AssetStatus; error:string };
const shotImageWorkflowVersion = "single-face-v2-anatomy-gate";

async function loadShotImageState(project = activeProjectRecord.value, session = projectSession) {
  window.clearTimeout(shotImageRefreshTimer);
  shotImages.value = [];
  shotImageStatus.value = "pending";
  shotImageError.value = "";
  if (!project) return;
  try {
    const result = await projectService.readStage<ShotImageStageData>({ ...projectIdentity, id:project.id, stage:"shot_images" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    const invalidatedLegacyImages = (result.stage.data.items || []).some(item => item.image_url && item.status === "confirmed" && item.workflow_version !== shotImageWorkflowVersion);
    shotImages.value = (result.stage.data.items || []).map(item => item.image_url && item.status === "confirmed" && item.workflow_version !== shotImageWorkflowVersion
      ? { ...item, status:"pending", error:"旧版分镜未经过人脸与人体结构专项验收，请重新生成", audit_summary:"" }
      : item);
    projectLoadIsolation.mark(project.id, session, "shot_images", result.stage.data.status === "generating");
    shotImageStatus.value = result.stage.data.status || "pending";
    shotImageError.value = result.stage.data.error || "";
    if (invalidatedLegacyImages) await persistShotImageState();
    if (result.stage.data.status === "generating") {
      shotImageRefreshTimer = window.setTimeout(() => { void loadShotImageState(project, session); }, 2000);
    }
  } catch (error) { shotImageError.value = error instanceof Error ? error.message : "镜头画面加载失败"; }
}

async function persistShotImageState() {
  const project = activeProjectRecord.value;
  if (!project) return;
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"shot_images", data:{ items:shotImages.value, status:shotImageStatus.value, error:shotImageError.value } satisfies ShotImageStageData });
}

function confirmedAssetReferences() {
  return [...characterProfiles.value, ...sceneProfiles.value, ...propProfiles.value]
    .filter(item => item.status === "confirmed" && item.image_url)
    .slice(0, 6)
    .map(item => ({
      name:item.name,
      url:item.image_url!,
      ...(characterProfiles.value.includes(item as CharacterProfile)
        ? { clothing_url:(item as CharacterProfile).clothing_reference_url || (item as CharacterProfile).detail_assets?.find(asset => asset.label === "全身" && asset.image_url)?.image_url || item.image_url! }
        : {}),
    }));
}

async function generateOneShotImage(shot:StoryboardShot, controller:AbortController) {
  const project = activeProjectRecord.value;
  if (!project) throw new Error("请先选择项目");
  if ((shot.characters || []).some(character => character.change_type === "change")) throw new Error("capability_not_implemented：独立服装穿衣蒙皮链尚未完成，换装镜头已阻断");
  let item = shotImages.value.find(value => value.episode === shot.episode && value.shot_number === shot.shot_number);
  if (!item) {
    item = { episode:shot.episode, shot_number:shot.shot_number, status:"pending", repair_count:0 };
    shotImages.value.push(item);
  }
  item.status = "generating"; item.error = ""; item.audit_summary = "";
  await persistShotImageState();
  const prompt = item.prompt_override || `${shot.image_prompt || shot.visual}\n动作：${shot.action}\n场景：${shot.scene}；景别：${shot.shot_size}；镜头：${shot.camera}；声音：${shot.sound}`;
  const shotDescription = `${shot.scene} ${shot.visual} ${shot.action} ${shot.image_prompt}`;
  const exactScenes = sceneProfiles.value.filter(scene => scene.image_url && shotDescription.includes(scene.name));
  const broadScenes = sceneProfiles.value.filter(scene => scene.image_url && (shot.scene.includes(scene.name) || scene.name.includes(shot.scene)));
  const selectedScenes = exactScenes.length ? exactScenes : broadScenes.length <= 1 ? broadScenes : broadScenes.filter(scene =>
    /破碎|碎裂|崩塌|裂开|爆开/u.test(shotDescription) ? /破碎/u.test(scene.name)
      : /外部|门外|走向|进入/u.test(shotDescription) ? /外部/u.test(scene.name)
        : /内部/u.test(scene.name),
  ).slice(0, 1);
  const shotReferences = [
    ...selectedScenes.map(scene => ({ name:scene.name, kind:"scene", angle:"主场景", url:scene.image_url! })),
    ...propProfiles.value.filter(prop => prop.image_url && shotDescription.includes(prop.name)).map(prop => ({ name:prop.name, kind:"prop", angle:"道具", url:prop.image_url! })),
    ...characterProfiles.value.filter(character => character.image_url && shotDescription.includes(character.name)).flatMap(character => [
      { name:character.name, kind:"character", angle:"0°正面全身", usage:"clothing_body", url:character.image_url! },
      ...(character.detail_assets || []).filter(asset => asset.image_url).map(asset => ({ name:character.name, kind:"character", angle:asset.label, usage:asset.label === "0°正面半身" ? "face_primary" : "angle_continuity", url:asset.image_url! })),
    ]),
    ...[...selectedScenes, ...propProfiles.value.filter(prop => shotDescription.includes(prop.name)), ...characterProfiles.value.filter(character => shotDescription.includes(character.name))]
      .filter(asset => asset.model3d_status === "confirmed" && asset.model3d_result?.renders?.length)
      .flatMap(asset => {
        const render = asset.model3d_result!.renders.find(value => value.label === "front_0") || asset.model3d_result!.renders[0];
        return [
          { name:`${asset.name}-3D结构`, kind:"3d", angle:render.label, usage:"spatial_structure", url:render.url },
          ...(render.depth_url ? [{ name:`${asset.name}-3D深度`, kind:"3d", angle:render.label, usage:"depth_control", url:render.depth_url }] : []),
          ...(render.normal_url ? [{ name:`${asset.name}-3D法线`, kind:"3d", angle:render.label, usage:"normal_control", url:render.normal_url }] : []),
          ...(render.mask_url ? [{ name:`${asset.name}-3D蒙版`, kind:"3d", angle:render.label, usage:"mask_control", url:render.mask_url }] : []),
        ];
      }),
  ];
  let generated = await assetService.generateShot<{ image:{ url:string } }>({ ...productionTaskContext(project), episode:shot.episode, shot_number:shot.shot_number, characters:shot.characters || [], prompt, references:shotReferences, identity_lock:"multi_reference_asset_lock", orientation:"portrait", width:928, height:1664 }, controller.signal);
  item.image_url = generated.image.url;
  const expectedCharacters = characterProfiles.value.filter(character => shot.visual.includes(character.name) || shot.action.includes(character.name)).map(character => character.name);
  let audit = await assetService.semanticAudit<{ passed:boolean; summary:string; missing_subjects:string[]; contradictions:string[] }>({ ...productionTaskContext(project), image_url:item.image_url, expected_visual:`${shot.visual}；${shot.action}`, expected_characters:expectedCharacters, references:shotReferences });
  if (!audit.passed && item.repair_count < 1) {
    item.repair_count += 1;
    const issue = [...audit.missing_subjects, ...audit.contradictions, audit.summary].filter(Boolean).join("；");
    generated = await assetService.repairShot<{ image:{ url:string } }>({ ...productionTaskContext(project), episode:shot.episode, shot_number:shot.shot_number, original_url:item.image_url, issue, prompt, references:shotReferences, width:928, height:1664 }, controller.signal);
    item.image_url = generated.image.url;
    audit = await assetService.semanticAudit({ ...productionTaskContext(project), image_url:item.image_url, expected_visual:`${shot.visual}；${shot.action}`, expected_characters:expectedCharacters, references:shotReferences });
  }
  item.audit_summary = audit.summary;
  item.status = audit.passed ? "confirmed" : "failed";
  item.workflow_version = audit.passed ? shotImageWorkflowVersion : undefined;
  item.error = audit.passed ? "" : `复检未通过：${audit.summary}`;
  await persistShotImageState();
  await revealCompletedUnit();
}

function shotImageServerCommand(project:StoredProject, shot:StoryboardShot) {
  const item = shotImages.value.find(value => value.episode === shot.episode && value.shot_number === shot.shot_number);
  const prompt = item?.prompt_override || `${shot.image_prompt || shot.visual}\n动作：${shot.action}\n场景：${shot.scene}；景别：${shot.shot_size}；镜头：${shot.camera}；声音：${shot.sound}`;
  const description = `${shot.scene} ${shot.visual} ${shot.action} ${shot.image_prompt}`;
  const references = [
    ...sceneProfiles.value.filter(asset => asset.image_url && description.includes(asset.name)).map(asset => ({ name:asset.name, kind:"scene", angle:"主场景", url:asset.image_url! })),
    ...propProfiles.value.filter(asset => asset.image_url && description.includes(asset.name)).map(asset => ({ name:asset.name, kind:"prop", angle:"道具", url:asset.image_url! })),
    ...characterProfiles.value.filter(asset => asset.image_url && description.includes(asset.name)).flatMap(asset => [{ name:asset.name, kind:"character", angle:"0°正面全身", usage:"clothing_body", url:asset.image_url! }, ...(asset.detail_assets || []).filter(detail => detail.image_url).map(detail => ({ name:asset.name, kind:"character", angle:detail.label, usage:detail.label === "0°正面半身" ? "face_primary" : "angle_continuity", url:detail.image_url! }))]),
  ];
  return { ...productionTaskContext(project), identity:productionTaskContext(project), episode:shot.episode, shot_number:shot.shot_number, characters:shot.characters || [], prompt, references, expected_visual:`${shot.visual}；${shot.action}`, expected_characters:characterProfiles.value.filter(character => description.includes(character.name)).map(character => character.name), identity_lock:"multi_reference_asset_lock", orientation:"portrait", width:928, height:1664 };
}

async function generateShotImages() {
  if (!requireEnabledRobot("视觉资产")) return;
  const project = activeProjectRecord.value;
  if (!project || !storyboardShots.value.length || shotImageStatus.value === "generating" || !assetsReadyForShotImages.value) return;
  const controller = new AbortController(); shotImageController.value?.abort(); shotImageController.value = controller; shotImageStatus.value = "generating"; shotImageError.value = "";
  try {
    if (storyboardShots.value.some(shot => (shot.characters || []).some(character => character.change_type === "change"))) throw new Error("capability_not_implemented：独立服装穿衣蒙皮链尚未完成，换装镜头已阻断");
    const eligibleEpisodes = new Set(completeStoryboardEpisodes.value.filter(episode => requiredAssetsForEpisode(episode).every(assetUploadComplete)));
    const commands = storyboardShots.value.filter(shot => eligibleEpisodes.has(shot.episode) && !shotImages.value.some(item => item.episode === shot.episode && item.shot_number === shot.shot_number && item.status === "confirmed")).map(shot => shotImageServerCommand(project, shot));
    const response = await productionLedgerService.runStage<{ items:ShotImageItem[] }>({ ...productionTaskContext(project), stage:"image", context:productionTaskContext(project), commands }, controller.signal);
    const replaced = new Set(response.result.items.map(item => `${item.episode}:${item.shot_number}`)); shotImages.value = [...shotImages.value.filter(item => !replaced.has(`${item.episode}:${item.shot_number}`)), ...response.result.items].sort((a, b) => a.episode - b.episode || a.shot_number - b.shot_number);
    shotImageStatus.value = shotImages.value.length === storyboardShots.value.length && shotImages.value.every(item => item.status === "confirmed") ? "confirmed" : "waiting_confirmation"; await persistShotImageState();
  } catch (error) {
    if (controller.signal.aborted) return;
    shotImageStatus.value = "failed"; shotImageError.value = error instanceof Error ? error.message : "镜头画面生成失败"; await persistShotImageState().catch(() => undefined);
  } finally { if (shotImageController.value === controller) shotImageController.value = undefined; }
}

async function enterShotImageGeneration() {
  if (!storyboardHasCompleteEpisode.value) {
    shotImageError.value = "请先生成至少一集完整分镜脚本";
    notify(shotImageError.value);
    return;
  }
  const episode = readyAssetEpisode.value;
  if (episode === undefined) {
    shotImageError.value = "资产图片数量不够：至少完成一集实际引用的全部人物、道具和场景资产";
    notify(shotImageError.value, 3200);
    return;
  }
  for (const item of requiredAssetsForEpisode(episode)) item.status = "confirmed";
  assetStatus.value = allAssetProfiles.value.every(item => item.status === "confirmed") ? "confirmed" : "waiting_confirmation";
  await persistAssetState();
  shotImageController.value?.abort();
  shotImages.value = [];
  shotImageStatus.value = "pending";
  shotImageError.value = "";
  await persistShotImageState();
  selectWorkflowNavigation("分镜画面");
  await nextTick();
  shotImageError.value = "";
  await generateShotImages();
}

async function enterShotVideoGeneration() {
  const episode = readyShotImageEpisode.value;
  if (episode === undefined) {
    shotImageError.value = "请先完成至少一集的全部分镜画面";
    notify(shotImageError.value);
    return;
  }
  const completedImages = shotImages.value.filter(item => item.episode === episode && item.image_url);
  for (const item of completedImages) item.status = "confirmed";
  shotImageStatus.value = completedImages.length === storyboardShots.value.filter(shot => shot.episode === episode).length ? "waiting_confirmation" : shotImageStatus.value;
  await persistShotImageState();
  shotVideoController.value?.abort();
  shotVideos.value = [];
  shotVideoStatus.value = "pending";
  shotVideoError.value = "";
  await persistShotVideoState();
  selectWorkflowNavigation("分镜视频");
  await nextTick();
  await generateShotVideos();
}

async function confirmShotImage(item:ShotImageItem) {
  if (!item.image_url || item.status !== "waiting_confirmation") return;
  item.status = "confirmed";
  if (shotImages.value.length === storyboardShots.value.length && shotImages.value.every(value => value.status === "confirmed")) shotImageStatus.value = "confirmed";
  await persistShotImageState();
}

async function regenerateShotImage(item:ShotImageItem, editPrompt = false) {
  const shot = storyboardShots.value.find(value => value.episode === item.episode && value.shot_number === item.shot_number);
  if (!shot || shotImageStatus.value === "generating") return;
  if (editPrompt) {
    const current = item.prompt_override || shot.image_prompt || shot.visual;
    const changed = window.prompt("修改当前镜头提示词", current);
    if (changed === null || !changed.trim()) return;
    item.prompt_override = changed.trim();
  }
  const controller = new AbortController(); shotImageController.value?.abort(); shotImageController.value = controller;
  try { await generateOneShotImage(shot, controller); }
  catch (error) { item.status = "failed"; item.error = error instanceof Error ? error.message : "单镜头重生失败"; await persistShotImageState(); }
  finally { if (shotImageController.value === controller) shotImageController.value = undefined; }
}

async function replaceShotImage(item:ShotImageItem, file:File) {
  const project = activeProjectRecord.value;
  const validationError = await validateMediaFile(file);
  if (!project || validationError || !file.type.startsWith("image/")) return notify(validationError || "请选择图片文件");
  const saved = await resourceService.save({ ...projectIdentity, plugin_key:"short-video-drama", scope:"project_episode", project_id:project.id, episode:item.episode, kind:"shot_image", name:file.name, data_url:await readFileAsDataUrl(file), metadata:{ shot_number:item.shot_number } });
  item.image_url = resourceService.mediaUrl(saved.resource, projectIdentity);
  if (!enabledSkills.value.includes("审核")) { item.audit_summary = ""; item.status = "waiting_confirmation"; item.error = ""; await persistShotImageState(); return; }
  const shot = storyboardShots.value.find(value => value.episode === item.episode && value.shot_number === item.shot_number);
  const audit = await assetService.semanticAudit<{ passed:boolean; summary:string }>({ ...productionTaskContext(project), image_url:item.image_url, expected_visual:shot ? `${shot.visual}；${shot.action}` : item.prompt_override || "", expected_characters:[] });
  item.audit_summary = audit.summary; item.status = audit.passed ? "waiting_confirmation" : "failed"; item.error = audit.passed ? "" : `替换图复检未通过：${audit.summary}`;
  await persistShotImageState();
}
function openShotImageReplacement(item:ShotImageItem) { shotImageReplaceTarget.value = item; shotImageReplaceInput.value?.click(); }
async function onShotImageReplacement(event:Event) {
  const input = event.target as HTMLInputElement; const file = input.files?.[0]; input.value = "";
  const item = shotImageReplaceTarget.value; shotImageReplaceTarget.value = undefined;
  if (item && file) await replaceShotImage(item, file).catch(error => notify(error instanceof Error ? error.message : "替换镜头图失败"));
}

function openStandardImport(stage:StandardImportStage) {
  standardImportStage.value = stage;
  if (standardImportInput.value) {
    standardImportInput.value.accept = ["outline", "script", "storyboard", "assets"].includes(stage) ? ".json,application/json" : stage === "shot_images" ? "image/*" : "video/*";
    standardImportInput.value.click();
  }
}

async function onStandardImport(event:Event) {
  const input = event.target as HTMLInputElement; const file = input.files?.[0]; input.value = "";
  const stage = standardImportStage.value; standardImportStage.value = undefined;
  const project = activeProjectRecord.value;
  if (!file || !stage || !project) return;
  try {
    if (["outline", "script", "storyboard", "assets"].includes(stage)) {
      if (file.size > 10 * 1024 * 1024 || !/\.json$/i.test(file.name)) throw new Error("标准文本素材必须是 10MB 以内 JSON 文件");
      const parsed = JSON.parse(await file.text()) as Record<string, unknown>;
      if (stage === "outline") {
        const plan = parsed.plan as OutlinePlan; const episodes = parsed.episodes as EpisodeOutline[];
        if (!plan?.general_outline || !Array.isArray(episodes) || episodes.length !== project.episode_count) throw new Error("大纲素材缺少 plan 或完整 episodes");
        outlinePlan.value = plan; outlineEpisodes.value = episodes;
        if (enabledSkills.value.includes("审核")) {
          const response = await narrativeService.audit<{ audit:OutlineAudit }>({ ...productionTaskContext(project), stage:"outline", audit_mode:"both", range:"导入全剧", project_requirements:stableProjectRequirements(project), content:{ plan, episodes } }, undefined, { invalid:status => `导入大纲审核异常（HTTP ${status}）` });
          if (!response.ok) throw new Error("导入大纲审核失败");
          outlineAudit.value = normalizeOutlineAudit(response.data.audit); outlineStatus.value = outlineAudit.value.status === "pass" ? "confirmed" : "failed";
        } else { outlineAudit.value = null; outlineStatus.value = "confirmed"; }
        await persistOutlineState(project);
      } else if (stage === "script") {
        const imported = (Array.isArray(parsed.scripts) ? parsed.scripts : Array.isArray(parsed) ? parsed : []) as ScriptItem[];
        if (!imported.length || imported.some(item => !Number.isInteger(item.episode) || !item.content?.trim())) throw new Error("剧本素材缺少有效 scripts");
        const importedEpisodes = [...new Set(imported.map(item => item.episode))].sort((a, b) => a - b);
        if (importedEpisodes.length !== project.episode_count || importedEpisodes.some((episode, index) => episode !== index + 1)) throw new Error("剧本素材必须完整覆盖项目全部集数且不得重复");
        scripts.value = imported; scriptAudits.value = [];
        if (enabledSkills.value.includes("审核")) for (const batch of createStoryArcBatches(outlinePlan.value?.arcs || [], project.episode_count)) scriptAudits.value.push(await auditScriptBatch(project, imported.filter(item => batch.episodes.includes(item.episode)), new AbortController(), "final", null, batch.id));
        scriptStatus.value = !enabledSkills.value.includes("审核") || narrativeAuditsPassed(scriptAudits.value) ? "confirmed" : "failed"; await persistScriptState(project);
      } else if (stage === "storyboard") {
        const imported = (Array.isArray(parsed.shots) ? parsed.shots : Array.isArray(parsed) ? parsed : []) as StoryboardShot[];
        if (!imported.length || imported.some(item => !Number.isInteger(item.episode) || !Number.isInteger(item.shot_number) || item.end_second <= item.start_second)) throw new Error("分镜素材缺少有效 shots 或时间轴错误");
        const importedEpisodes = [...new Set(imported.map(item => item.episode))].sort((a, b) => a - b);
        const duplicateKeys = new Set<string>();
        if (importedEpisodes.length !== project.episode_count || importedEpisodes.some((episode, index) => episode !== index + 1)) throw new Error("分镜素材必须完整覆盖项目全部集数");
        if (imported.some(item => { const key = `${item.episode}:${item.shot_number}`; if (duplicateKeys.has(key)) return true; duplicateKeys.add(key); return false; })) throw new Error("分镜素材存在重复镜头编号");
        storyboardShots.value = imported; storyboardAudits.value = [];
        if (enabledSkills.value.includes("审核")) for (const batch of createStoryArcBatches(outlinePlan.value?.arcs || [], project.episode_count)) storyboardAudits.value.push(await auditStoryboardBatch(project, imported.filter(item => batch.episodes.includes(item.episode)), new AbortController(), "final", null, batch.id));
        storyboardStatus.value = !enabledSkills.value.includes("审核") || narrativeAuditsPassed(storyboardAudits.value) ? "confirmed" : "failed"; await persistStoryboardState(project);
      } else {
        const importedCharacters = Array.isArray(parsed.characters) ? parsed.characters as CharacterProfile[] : [];
        const importedScenes = Array.isArray(parsed.scenes) ? parsed.scenes as SceneProfile[] : [];
        const importedProps = Array.isArray(parsed.props) ? parsed.props as PropProfile[] : [];
        if (!importedCharacters.length && !importedScenes.length && !importedProps.length) throw new Error("资产素材缺少 characters、scenes 或 props");
        characterProfiles.value = mergeAssetProfiles(characterProfiles.value, importedCharacters); sceneProfiles.value = mergeAssetProfiles(sceneProfiles.value, normalizeEmptySceneProfiles(importedScenes)); propProfiles.value = mergeAssetProfiles(propProfiles.value, importedProps); assetStatus.value = "waiting_confirmation"; await persistAssetState();
      }
      notify(enabledSkills.value.includes("审核") ? "标准素材已导入，当前范围等待审核确认" : "标准素材已导入，等待人工确认");
      return;
    }
    const validationError = await validateMediaFile(file);
    if (validationError) throw new Error(validationError);
    const expectsImage = stage === "shot_images";
    if (expectsImage !== file.type.startsWith("image/")) throw new Error(expectsImage ? "当前节点只接受图片" : "当前节点只接受视频");
    const episode = Math.max(1, workflowEpisode.value || 1);
    const saved = await resourceService.save({ ...projectIdentity, plugin_key:"short-video-drama", scope:"project_episode", project_id:project.id, episode, kind:`import_${stage}`, name:file.name, data_url:await readFileAsDataUrl(file), metadata:{ stage, imported:true } });
    const url = resourceService.mediaUrl(saved.resource, projectIdentity);
    if (stage === "shot_images") {
      const shot = storyboardShots.value.find(item => item.episode === episode);
      if (!shot) throw new Error("当前集没有可对应的镜头");
      const audit = enabledSkills.value.includes("审核") ? await assetService.semanticAudit<{ passed:boolean; summary:string }>({ ...productionTaskContext(project), image_url:url, expected_visual:`${shot.visual}；${shot.action}`, expected_characters:characterProfiles.value.filter(character => shot.visual.includes(character.name) || shot.action.includes(character.name)).map(character => character.name) }) : null;
      if (audit && !audit.passed) throw new Error(`导入镜头画面审核未通过：${audit.summary}`);
      let item = shotImages.value.find(value => value.episode === episode && value.shot_number === shot.shot_number);
      if (!item) { item = { episode, shot_number:shot.shot_number, status:"pending", repair_count:0 }; shotImages.value.push(item); }
      item.image_url = url; item.audit_summary = audit?.summary || ""; item.status = "waiting_confirmation"; await persistShotImageState();
    } else if (stage === "shot_videos") {
      const shot = storyboardShots.value.find(item => item.episode === episode);
      if (!shot) throw new Error("当前集没有可对应的镜头");
      const importedAudit = await mediaService.importedMediaAudit<{ path:string; video_url:string }>({ ...productionTaskContext(project), resource_id:saved.resource.id, stage, max_duration_seconds:10 });
      let item = shotVideos.value.find(value => value.episode === episode && value.shot_number === shot.shot_number);
      if (!item) { item = { episode, shot_number:shot.shot_number, status:"pending" }; shotVideos.value.push(item); }
      item.video_url = importedAudit.video_url; item.path = importedAudit.path; item.audit_evidence = { speaker:"not_applicable", emotion:"not_applicable", lipsync:"not_applicable", face:"not_applicable", continuity:"not_applicable" };
      const references = characterProfiles.value.filter(character => character.status === "confirmed" && character.image_url && (shot.visual.includes(character.name) || shot.action.includes(character.name))).map(character => character.image_url as string);
      if (references.length && enabledSkills.value.includes("审核")) {
        const faceAudit = await mediaService.faceAudit<{ status:string; errors?:Array<{ message:string }> }>({ ...productionTaskContext(project), episode, video_url:importedAudit.video_url, reference_urls:references });
        if (faceAudit.status !== "pass") throw new Error(faceAudit.errors?.map(value => value.message).join("；") || "导入视频人物一致性审核未通过");
        item.audit_evidence.face = "pass";
      }
      const previousShot = storyboardShots.value.filter(value => value.episode === episode && value.shot_number < shot.shot_number).sort((a, b) => b.shot_number - a.shot_number)[0];
      const previousVideo = previousShot && shotVideos.value.find(value => value.episode === episode && value.shot_number === previousShot.shot_number && value.video_url);
      if (previousVideo?.video_url && enabledSkills.value.includes("审核")) {
        const continuity = await mediaService.continuityAudit<{ status:string; summary:string }>({ ...productionTaskContext(project), previous_video_url:previousVideo.video_url, video_url:importedAudit.video_url, previous_expected:`${previousShot.visual}；${previousShot.action}`, current_expected:`${shot.visual}；${shot.action}` });
        if (continuity.status !== "pass") throw new Error(`导入视频连续性审核未通过：${continuity.summary}`);
        item.audit_evidence.continuity = "pass";
      }
      item.status = "waiting_confirmation"; await persistShotVideoState();
      if (hasSpokenDialogue(shot.dialogue)) {
        await repairShotAudio(item);
        const refreshed = shotVideos.value.find(value => value.episode === item.episode && value.shot_number === item.shot_number);
        if (refreshed?.status === "failed") throw new Error(refreshed.error || "导入视频音频和口型审核未通过");
      }
    } else if (stage === "merged_episodes") {
      const importedAudit = await mediaService.importedMediaAudit<{ path:string; video_url:string; production_evidence:string }>({ ...productionTaskContext(project), resource_id:saved.resource.id, stage, require_audio:true });
      let item = episodeMasters.value.find(value => value.episode === episode);
      if (!item) { item = { episode, status:"pending" }; episodeMasters.value.push(item); }
      item.video_url = importedAudit.video_url; item.path = importedAudit.path; item.clean_path = importedAudit.path; item.production_evidence = importedAudit.production_evidence; item.status = "waiting_confirmation"; mergeStatus.value = "waiting_confirmation"; await persistMergeState();
    } else {
      const importedAudit = await mediaService.importedMediaAudit<{ path:string; video_url:string; production_evidence:string }>({ ...productionTaskContext(project), resource_id:saved.resource.id, stage, require_audio:true });
      let master = episodeMasters.value.find(value => value.episode === episode);
      if (!master) { master = { episode, status:"pending" }; episodeMasters.value.push(master); }
      master.video_url = importedAudit.video_url; master.path = importedAudit.path; master.clean_path = importedAudit.path; master.production_evidence = importedAudit.production_evidence; master.status = "confirmed"; await persistMergeState();
      if (!enabledSkills.value.includes("审核")) { finalAuditStatus.value = "pending"; finalAuditError.value = ""; await persistFinalAuditState(); notify("替代成片已导入，审核已关闭"); return; }
      const subtitles = episodeSubtitles(episode);
      let importedOcrStatus = "not_applicable";
      if (subtitles.length) {
        const ocrAudit = await mediaService.subtitleOcrAudit<{ status:string; errors:Array<{ message:string }> }>({ ...productionTaskContext(project), path:master.path, subtitles });
        if (ocrAudit.status !== "pass") throw new Error(`导入成片字幕审核未通过：${(ocrAudit.errors || []).map(value => value.message).join("；")}`);
        importedOcrStatus = "pass";
      }
      const audit = await mediaService.finalAudit<{ status:"pass" | "needs_fix"; issues:string[] }>({
        ...productionTaskContext(project), episode, path:master.path, subtitles,
        process_audits:shotVideos.value.filter(item => item.episode === episode).map(item => ({ shot_number:item.shot_number, ...item.audit_evidence })),
        ocr_status:importedOcrStatus, content_compliance_status:"not_audited",
      });
      if (audit.status !== "pass") throw new Error(`导入成片审核未通过：${audit.issues.join("；")}`);
      const existingAudit = episodeAudits.value.find(value => value.episode === episode);
      const record = { episode, status:"pass", issues:[], attempts:0, confirmed:false } satisfies EpisodeAudit;
      if (existingAudit) Object.assign(existingAudit, record); else episodeAudits.value.push(record);
      finalAuditStatus.value = "waiting_confirmation"; await persistFinalAuditState();
    }
    notify(enabledSkills.value.includes("审核") ? "替代素材已导入，等待当前范围审核确认" : "替代素材已导入，等待人工确认");
  } catch (error) { notify(error instanceof Error ? error.message : "标准素材导入失败"); }
}

async function stopShotImages() {
  shotImageController.value?.abort();
  await assetService.stopImages({ ...productionTaskContext(), all:true }).catch(() => undefined);
  shotImageStatus.value = "failed";
  shotImageError.value = "已停止生成，可从未完成镜头继续";
  await persistShotImageState();
}

type ShotVideoStageData = { items:ShotVideoItem[]; status:AssetStatus; error:string };
const hasSpokenDialogue = (dialogue?:string) => Boolean(dialogue?.trim() && !/^(无|无对白|无台词|旁白无)$/u.test(dialogue.trim()));
async function loadShotVideoState(project = activeProjectRecord.value, session = projectSession) {
  shotVideos.value = []; shotVideoStatus.value = "pending"; shotVideoError.value = "";
  if (!project) return;
  try {
    const result = await projectService.readStage<ShotVideoStageData>({ ...projectIdentity, id:project.id, stage:"shot_videos" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    shotVideos.value = result.stage.data.items || [];
    const resumeInterruptedBatch = result.stage.data.status === "generating";
    let recovered = false;
    for (const item of shotVideos.value) {
      if (item.video_url && (item.status === "generating" || item.status === "failed" || item.status === "waiting_confirmation")) {
        item.status = "confirmed"; item.error = ""; recovered = true;
      }
    }
    projectLoadIsolation.mark(project.id, session, "shot_videos", result.stage.data.status === "generating");
    const legacyNotFound = String(result.stage.data.error || "").includes("not_found");
    shotVideoStatus.value = shotVideos.value.length === storyboardShots.value.length && shotVideos.value.every(item => item.status === "confirmed") ? "confirmed" : recovered || legacyNotFound || resumeInterruptedBatch ? "pending" : result.stage.data.status || "pending";
    shotVideoError.value = recovered || legacyNotFound || resumeInterruptedBatch ? "" : result.stage.data.error || "";
    if (recovered || legacyNotFound || resumeInterruptedBatch) await persistShotVideoState();
  } catch (error) { shotVideoError.value = error instanceof Error ? error.message : "分镜视频加载失败"; }
}
async function persistShotVideoState() {
  const project = activeProjectRecord.value;
  if (!project) return;
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"shot_videos", data:{ items:shotVideos.value, status:shotVideoStatus.value, error:shotVideoError.value } satisfies ShotVideoStageData });
}
function shotVideoServerCommand(project:StoredProject, shot:StoryboardShot, image:ShotImageItem) {
  const description = `${shot.visual}；${shot.action}`;
  const matchedCharacter = characterProfiles.value.find(character => description.includes(character.name) && character.status === "confirmed" && character.image_url);
  const characterShot = Boolean(matchedCharacter);
  const matched3DAsset = [
    ...sceneProfiles.value.filter(asset => description.includes(asset.name)),
    ...propProfiles.value.filter(asset => description.includes(asset.name)),
    ...characterProfiles.value.filter(asset => description.includes(asset.name)),
  ].find(asset => asset.model3d_status === "confirmed" && asset.model3d_result?.source_video_url);
  const h3References = matchedCharacter && matched3DAsset ? {
    engine:"minimax-h3-ref2va",
    source_video_url:matched3DAsset.model3d_result!.source_video_url,
    identity_reference_url:matchedCharacter.image_url,
  } : {};
  const voicePlan = hasSpokenDialogue(shot.dialogue) ? dialogueVoicePlan(shot, characterProfiles.value.map(character => character.name)) : null;
  return {
    identity:productionTaskContext(project), episode:shot.episode, shot_number:shot.shot_number,
    video:{ episode:shot.episode, shot_number:shot.shot_number, image_url:image.image_url, ...h3References, business_duration:Math.max(1, shot.end_second - shot.start_second), render_chunks:shot.render_chunks, orientation:"portrait", fps:30, motion_strategy:{ camera_movement_ratio:characterShot ? 0.35 : 0.55, subject_action_ratio:characterShot ? 0.65 : 0.45, instruction:`人物与场景身份锁定；镜头：${shot.camera}；画面：${shot.visual}；动作：${shot.action}` } },
    voice:voicePlan ? { text:voicePlan.spokenText, speaker:voicePlan.speaker, emotion_instruction:voicePlan.emotionInstruction, character_name:voicePlan.characterName, emotion:voicePlan.expectedEmotion } : null,
  };
}

async function generateShotVideos(target?:ShotVideoItem) {
  if (!requireEnabledRobot("视频制作")) return;
  const project = activeProjectRecord.value;
  if (!project || shotVideoStatus.value === "generating") return;
  const controller = new AbortController(); shotVideoController.value?.abort(); shotVideoController.value = controller; shotVideoStatus.value = "generating"; shotVideoError.value = "";
  try {
    const commands = storyboardShots.value.filter(shot => (!target || target.episode === shot.episode && target.shot_number === shot.shot_number) && !shotVideos.value.some(item => item.episode === shot.episode && item.shot_number === shot.shot_number && item.status === "confirmed")).map(shot => ({ shot, image:shotImages.value.find(item => item.episode === shot.episode && item.shot_number === shot.shot_number && item.status === "confirmed") })).filter((entry):entry is { shot:StoryboardShot; image:ShotImageItem & { image_url:string } } => Boolean(entry.image?.image_url)).map(entry => shotVideoServerCommand(project, entry.shot, entry.image));
    const response = await productionLedgerService.runStage<{ items:ShotVideoItem[] }>({ ...productionTaskContext(project), stage:"video", context:productionTaskContext(project), commands }, controller.signal);
    const replaced = new Set(response.result.items.map(item => `${item.episode}:${item.shot_number}`)); shotVideos.value = [...shotVideos.value.filter(item => !replaced.has(`${item.episode}:${item.shot_number}`)), ...response.result.items].sort((a, b) => a.episode - b.episode || a.shot_number - b.shot_number);
    shotVideoStatus.value = shotVideos.value.length === storyboardShots.value.length && shotVideos.value.every(item => item.status === "confirmed") ? "confirmed" : "pending"; await persistShotVideoState(); if (shotVideoStatus.value === "confirmed") await syncProductionLedger(project);
  } catch (error) {
    if (controller.signal.aborted) return;
    shotVideoStatus.value = "failed"; shotVideoError.value = error instanceof Error ? error.message : "分镜视频生成失败"; await persistShotVideoState().catch(() => undefined);
  } finally { if (shotVideoController.value === controller) shotVideoController.value = undefined; }
}

function retryShotVideo(item:ShotVideoItem) {
  item.status = "failed"; item.error = "";
  void generateShotVideos(item);
}
function openShotVideoReplacement(item:ShotVideoItem) { shotVideoReplaceTarget.value = item; shotVideoReplaceInput.value?.click(); }

async function toggleShotVideoPlayback(event:MouseEvent) {
  const button = event.currentTarget as HTMLButtonElement | null;
  const video = button?.closest(".shot-video-frame")?.querySelector("video");
  if (!button || !video) return;
  if (video.paused) await video.play(); else video.pause();
  button.classList.toggle("playing", !video.paused);
}
async function referenceWorkflowMedia(name:string, url:string | undefined, mediaType:"image" | "video") {
  if (!url) return notify("当前素材尚未生成");
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const extension = mediaType === "video" ? "mp4" : "png";
    const file = new File([blob], `${name}.${extension}`, { type:blob.type || (mediaType === "video" ? "video/mp4" : "image/png") });
    stagedAssets.value.push({ id:`reference-${Date.now()}`, name:file.name, url, mediaType, scope:"临时参考", label:"引用", file });
    notify(`已引用：${name}`);
    await scrollChat();
  } catch (error) {
    notify(`引用失败：${error instanceof Error ? error.message : "素材读取失败"}`);
  }
}
async function onShotVideoReplacement(event:Event) {
  const input = event.target as HTMLInputElement; const file = input.files?.[0]; input.value = "";
  const item = shotVideoReplaceTarget.value; shotVideoReplaceTarget.value = undefined;
  const project = activeProjectRecord.value;
  if (!item || !file || !project) return;
  try {
    const validationError = await validateMediaFile(file);
    if (validationError || !file.type.startsWith("video/")) throw new Error(validationError || "请选择视频文件");
    const saved = await resourceService.save({ ...projectIdentity, plugin_key:"short-video-drama", scope:"project_episode", project_id:project.id, episode:item.episode, kind:"shot_video_replacement", name:file.name, data_url:await readFileAsDataUrl(file), metadata:{ shot_number:item.shot_number, replacement:true } });
    await mediaService.importedMediaAudit({ ...productionTaskContext(project), resource_id:saved.resource.id, stage:"shot_videos", max_duration_seconds:10 });
    item.video_url = resourceService.mediaUrl(saved.resource, projectIdentity); item.path = undefined; item.status = "waiting_confirmation"; item.error = "";
    await persistShotVideoState();
  } catch (error) { notify(error instanceof Error ? error.message : "替换分镜视频失败"); }
}
async function confirmShotVideo(item:ShotVideoItem) {
  if (!item.video_url || item.status !== "waiting_confirmation") return;
  item.status = "confirmed";
  if (item.audio_url && item.speaker) {
    const character = characterProfiles.value.find(value => value.name === item.speaker);
    if (character && !character.voice_reference_url) { character.voice_reference_url = item.audio_url; character.voice_status = "confirmed"; await persistAssetState(); }
  }
  if (shotVideos.value.length === storyboardShots.value.length && shotVideos.value.every(value => value.status === "confirmed")) shotVideoStatus.value = "confirmed";
  await persistShotVideoState();
}
async function repairShotAudio(item:ShotVideoItem) {
  const project = activeProjectRecord.value;
  const shot = storyboardShots.value.find(value => value.episode === item.episode && value.shot_number === item.shot_number);
  if (!project || !shot || !hasSpokenDialogue(shot.dialogue) || !item.video_url) return notify("当前镜头没有可修复对白");
  try {
    const voicePlan = dialogueVoicePlan(shot, characterProfiles.value.map(character => character.name));
    const speaker = voicePlan.characterName;
    const tts = await mediaService.tts<{ audio:{ url:string } }>({ ...productionTaskContext(project), episode:item.episode, shot_number:item.shot_number, text:voicePlan.spokenText, speaker:voicePlan.speaker, emotion_instruction:voicePlan.emotionInstruction });
    const character = characterProfiles.value.find(value => value.name === speaker);
    if (character?.voice_reference_url && enabledSkills.value.includes("审核")) {
      const speakerAudit = await mediaService.speakerAudit<{ status:string; errors?:Array<{ message:string }> }>({ ...productionTaskContext(project), items:[{ id:`${item.episode}:${item.shot_number}`, speaker, audio_url:tts.audio.url }], references:{ [speaker]:character.voice_reference_url } });
      if (speakerAudit.status !== "pass") throw new Error(speakerAudit.errors?.map(error => error.message).join("；") || "角色声纹复检未通过");
    }
    if (enabledSkills.value.includes("审核")) {
      const emotionAudit = await mediaService.emotionAudit<{ status:string; errors?:Array<{ message:string }> }>({ ...productionTaskContext(project), items:[{ id:`${item.episode}:${item.shot_number}`, audio_url:tts.audio.url, expected_emotion:`${shot.action}；${shot.dialogue}` }] });
      if (emotionAudit.status !== "pass") throw new Error(emotionAudit.errors?.map(error => error.message).join("；") || "对白情绪复检未通过");
    }
    const sourceVideoUrl = item.source_video_url || resultMediaUrl(`episode_${item.episode}_shot_${item.shot_number}.mp4`, "videos");
    const synced = await mediaService.latentSync<{ video_url:string; path:string }>({ ...productionTaskContext(project), episode:item.episode, shot_number:item.shot_number, video_url:sourceVideoUrl, audio_url:tts.audio.url, inference_steps:8 }, "LatentSync 口型生成失败");
    if (enabledSkills.value.includes("审核")) {
      const lipAudit = await mediaService.lipSyncAudit<{ status:string; errors?:Array<{ message:string }> }>({ ...productionTaskContext(project), episode:item.episode, shot_number:item.shot_number, path:synced.path });
      if (lipAudit.status !== "pass") throw new Error(lipAudit.errors?.map(error => error.message).join("；") || "口型复检未通过");
    }
    item.audio_url = tts.audio.url; item.speaker = speaker; item.voice_preset = voicePlan.speaker; item.voice_cast_version = "qwen-1.7b-role-cast-v3"; item.emotion = voicePlan.expectedEmotion; item.video_url = synced.video_url; item.path = synced.path; item.lip_sync_model = "LatentSync-1.6"; item.lip_sync_version = "raw-source-latentsync-v2";
    item.voice_status = "completed"; item.lip_sync_status = "completed"; item.subtitle_status = "completed";
    item.audit_evidence = { ...(item.audit_evidence || { face:"not_applicable", speaker:"not_applicable", emotion:"not_applicable", lipsync:"not_applicable" }), speaker:enabledSkills.value.includes("审核") && character?.voice_reference_url ? "pass" : "not_applicable", emotion:enabledSkills.value.includes("审核") ? "pass" : "not_applicable", lipsync:enabledSkills.value.includes("审核") ? "pass" : "not_applicable" };
    item.status = "waiting_confirmation"; item.error = ""; await persistShotVideoState();
  } catch (error) { item.status = "failed"; item.voice_status = "failed"; item.lip_sync_status = "failed"; item.error = error instanceof Error ? error.message : "音频修复失败"; await persistShotVideoState(); }
}
async function stopShotVideos() {
  shotVideoController.value?.abort();
  await mediaService.stopVideos({ ...productionTaskContext(), keys:shotVideos.value.filter(item => item.status === "generating").map(item => `${item.episode}:${item.shot_number}`) }).catch(() => undefined);
  shotVideoStatus.value = "failed"; shotVideoError.value = "已停止生成，可继续未完成镜头"; await persistShotVideoState();
}

type MergeStageData = { episodes:EpisodeMaster[]; status:AssetStatus; error:string };
async function loadMergeState(project = activeProjectRecord.value, session = projectSession) {
  episodeMasters.value = []; mergeStatus.value = "pending"; mergeError.value = "";
  if (!project) return;
  try {
    const result = await projectService.readStage<MergeStageData>({ ...projectIdentity, id:project.id, stage:"merged_episodes" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    episodeMasters.value = result.stage.data.episodes || [];
    projectLoadIsolation.mark(project.id, session, "merged_episodes", result.stage.data.status === "generating");
    mergeStatus.value = result.stage.data.status === "generating" ? "failed" : result.stage.data.status || "pending";
    mergeError.value = result.stage.data.status === "generating" ? "上次合片未完成，请重新执行对应集" : result.stage.data.error || "";
  } catch (error) { mergeError.value = error instanceof Error ? error.message : "成片数据加载失败"; }
}
async function persistMergeState(project = activeProjectRecord.value, session = projectSession) {
  if (!project || !isCurrentProjectSession(project.id, session)) return;
  const data = JSON.parse(JSON.stringify({ episodes:episodeMasters.value, status:mergeStatus.value, error:mergeError.value } satisfies MergeStageData)) as MergeStageData;
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"merged_episodes", data });
}
function episodeMergePayload(project:StoredProject, episode:number) {
  const shots = storyboardShots.value.filter(shot => shot.episode === episode).sort((a, b) => a.shot_number - b.shot_number);
  const videos = shots.map(shot => {
    const video = shotVideos.value.find(item => item.episode === episode && item.shot_number === shot.shot_number && item.status === "confirmed");
    if (!video?.video_url) throw new Error(`第${episode}集镜头${shot.shot_number}缺少已确认视频`);
    return { url:video.video_url, audio_url:video.audio_url, sound:shot.sound, shot_number:shot.shot_number, has_dialogue:hasSpokenDialogue(shot.dialogue), voice_ready:!hasSpokenDialogue(shot.dialogue) || Boolean(video.audio_url), lip_sync_ready:!hasSpokenDialogue(shot.dialogue) || Boolean(video.path), subtitle_ready:!hasSpokenDialogue(shot.dialogue) || episodeSubtitles(episode).some(subtitle => subtitle.shot_id === `${episode}:${shot.shot_number}` && subtitle.text.trim()) };
  });
  return { ...productionTaskContext(project), episode, videos, subtitles:episodeSubtitles(episode), bgm:{ mode:"auto", source:"generated", license:"project-generated" }, bgm_volume:0.14, subtitle_style:{ font:subtitleFont.value, font_size:subtitleFontSize.value, color:subtitleColor.value, stroke_color:subtitleStrokeColor.value, stroke_width:subtitleStrokeWidth.value, opacity:subtitleOpacity.value } };
}
function episodeSubtitles(episode:number) {
  return storyboardShots.value
    .filter(shot => shot.episode === episode && shot.dialogue && shot.dialogue !== "无")
    .sort((a, b) => a.shot_number - b.shot_number)
    .map((shot, index) => ({ index:index + 1, shot_id:`${episode}:${shot.shot_number}`, start:shot.start_second, end:shot.end_second, text:shot.dialogue }));
}
function episodeReadyToMerge(episode:number) {
  const shots = storyboardShots.value.filter(shot => shot.episode === episode);
  return shots.length > 0 && shots.every(shot => {
    const item = shotVideos.value.find(video => video.episode === episode && video.shot_number === shot.shot_number);
    if (!item || !["confirmed", "waiting_confirmation"].includes(item.status) || !item.video_url) return false;
    if (!hasSpokenDialogue(shot.dialogue)) return true;
    const subtitlePrepared = episodeSubtitles(episode).some(subtitle => subtitle.shot_id === `${episode}:${shot.shot_number}` && subtitle.text.trim());
    return Boolean(item.audio_url && item.path && item.voice_status !== "failed" && item.lip_sync_status !== "failed" && item.subtitle_status !== "failed" && subtitlePrepared);
  });
}
const mergePrerequisiteMessage = computed(() => {
  for (const shot of storyboardShots.value) {
    const item = shotVideos.value.find(video => video.episode === shot.episode && video.shot_number === shot.shot_number);
    if (!item?.video_url || !["confirmed", "waiting_confirmation"].includes(item.status)) return `第${shot.episode}集镜头${shot.shot_number}尚未完成分镜视频`;
    if (!hasSpokenDialogue(shot.dialogue)) continue;
    if (!item.audio_url || item.voice_status === "failed") return `第${shot.episode}集镜头${shot.shot_number}尚未完成配音`;
    if (!item.path || item.lip_sync_status === "failed") return `第${shot.episode}集镜头${shot.shot_number}尚未完成口型同步`;
    if (!episodeSubtitles(shot.episode).some(subtitle => subtitle.shot_id === `${shot.episode}:${shot.shot_number}` && subtitle.text.trim()) || item.subtitle_status === "failed") return `第${shot.episode}集镜头${shot.shot_number}尚未完成字幕`;
  }
  return "";
});
const hasMergeableEpisode = computed(() => {
  const count = activeProjectRecord.value?.episode_count || 0;
  return Array.from({ length:count }, (_, index) => index + 1).some(episode => episodeReadyToMerge(episode) && !episodeMasters.value.some(item => item.episode === episode && ["confirmed", "waiting_confirmation", "generating"].includes(item.status)));
});
async function mergeEpisode(project:StoredProject, episode:number, controller:AbortController) {
  let master = episodeMasters.value.find(item => item.episode === episode);
  if (!master) { master = { episode, status:"pending" }; episodeMasters.value.push(master); }
  master.status = "generating"; master.error = ""; await persistMergeState(); await revealCompletedUnit();
  const result = await mediaService.merge<{ video_url:string; path:string; clean_path:string; bgm_url:string; bgm_path:string; bgm_volume:number; production_evidence:string }>(episodeMergePayload(project, episode), controller.signal);
  master.video_url = result.video_url; master.path = result.path; master.clean_path = result.clean_path; master.production_evidence = result.production_evidence; master.status = "waiting_confirmation";
  await persistMergeState();
  await revealCompletedUnit();
  return master;
}
async function mergeEpisodes() {
  if (!requireEnabledRobot("后期制作")) return;
  const project = activeProjectRecord.value;
  if (!project || !hasMergeableEpisode.value || mergeStatus.value === "generating") return;
  const session = projectSession;
  const controller = new AbortController(); mergeController.value?.abort(); mergeController.value = controller;
  mergeStatus.value = "generating"; mergeError.value = ""; await persistMergeState(project, session);
  try {
    await syncProductionLedger(project);
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    const commands = Array.from({ length:project.episode_count }, (_, index) => index + 1)
      .filter(episode => episodeReadyToMerge(episode) && !episodeMasters.value.some(item => item.episode === episode && ["confirmed", "waiting_confirmation"].includes(item.status)))
      .map(episode => episodeMergePayload(project, episode));
    const response = await productionLedgerService.runStage<{ items:Array<EpisodeMaster & { clean_path?:string; production_evidence?:string }> }>({
      ...productionTaskContext(project), stage:"composition", context:productionTaskContext(project), commands,
    }, controller.signal);
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    const replaced = new Set(response.result.items.map(item => item.episode));
    episodeMasters.value = [
      ...episodeMasters.value.filter(item => !replaced.has(item.episode)),
      ...response.result.items.map(item => ({ ...item, status:"waiting_confirmation" as const })),
    ].sort((a, b) => a.episode - b.episode);
    await persistMergeState(project, session);
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    mergeStatus.value = episodeMasters.value.length === project.episode_count && episodeMasters.value.every(item => item.status === "confirmed") ? "confirmed" : "waiting_confirmation"; await persistMergeState(project, session);
  } catch (error) {
    if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) return;
    mergeStatus.value = "failed"; mergeError.value = error instanceof Error ? error.message : "合并成片失败"; await persistMergeState(project, session).catch(() => undefined);
  } finally { if (mergeController.value === controller) mergeController.value = undefined; }
}
async function generateFinalVideo() {
  if (shotVideoStatus.value === "generating" || mergeStatus.value === "generating") return;
  mergeController.value?.abort();
  episodeMasters.value = [];
  mergeStatus.value = "pending";
  mergeError.value = "";
  await persistMergeState();
  selectWorkflowNavigation("成片");
  await nextTick();
  shotVideoStatus.value = "generating";
  shotVideoError.value = "";
  await persistShotVideoState();
  for (const shot of storyboardShots.value) {
    const item = shotVideos.value.find(video => video.episode === shot.episode && video.shot_number === shot.shot_number);
    if (!item?.video_url) {
      shotVideoStatus.value = "failed";
      shotVideoError.value = `第${shot.episode}集镜头${shot.shot_number}缺少分镜视频`;
      await persistShotVideoState();
      return;
    }
    if (!hasSpokenDialogue(shot.dialogue)) {
      item.voice_status = "not_applicable";
      item.lip_sync_status = "not_applicable";
      item.subtitle_status = "not_applicable";
      continue;
    }
    if (!item.audio_url || !item.path || item.lip_sync_model !== "LatentSync-1.6" || item.voice_cast_version !== "qwen-1.7b-role-cast-v3" || item.lip_sync_version !== "raw-source-latentsync-v2" || item.voice_status !== "completed" || item.lip_sync_status !== "completed" || item.subtitle_status !== "completed") {
      await repairShotAudio(item);
      if (item.status === "failed") {
        shotVideoStatus.value = "failed";
        shotVideoError.value = item.error || `第${shot.episode}集镜头${shot.shot_number}配音或口型同步失败`;
        await persistShotVideoState();
        return;
      }
    }
  }
  shotVideoStatus.value = "confirmed";
  await persistShotVideoState();
  episodeMasters.value = [];
  mergeStatus.value = "pending";
  mergeError.value = "";
  await persistMergeState();
  if (!hasMergeableEpisode.value) {
    shotVideoStatus.value = "failed";
    shotVideoError.value = mergePrerequisiteMessage.value || "配音、口型同步或字幕尚未完成";
    await persistShotVideoState();
    return;
  }
  await mergeEpisodes();
}
async function confirmEpisodeMaster(item:EpisodeMaster) {
  if (!item.video_url || item.status !== "waiting_confirmation") return;
  item.status = "confirmed";
  if (episodeMasters.value.length === activeProjectRecord.value?.episode_count && episodeMasters.value.every(value => value.status === "confirmed")) mergeStatus.value = "confirmed";
  await persistMergeState();
  if (mergeStatus.value === "confirmed" && activeProjectRecord.value) await syncProductionLedger(activeProjectRecord.value);
}
function importEpisodeMaster(item:EpisodeMaster) {
  workflowEpisode.value = item.episode;
  openStandardImport("merged_episodes");
}
async function regenerateEpisodeMaster(item:EpisodeMaster) {
  item.status = "pending";
  item.video_url = undefined;
  item.path = undefined;
  item.clean_path = undefined;
  mergeStatus.value = "pending";
  await persistMergeState();
  await mergeEpisodes();
}
async function stopMerge() {
  mergeController.value?.abort(); mergeStatus.value = "failed"; mergeError.value = "已停止合片"; await persistMergeState();
}

type FinalAuditStageData = { audits:EpisodeAudit[]; status:AssetStatus; error:string };
async function loadFinalAuditState(project = activeProjectRecord.value, session = projectSession) {
  episodeAudits.value = []; finalAuditStatus.value = "pending"; finalAuditError.value = "";
  if (!project) return;
  try {
    const result = await projectService.readStage<FinalAuditStageData>({ ...projectIdentity, id:project.id, stage:"final_audit" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    episodeAudits.value = result.stage.data.audits || [];
    projectLoadIsolation.mark(project.id, session, "final_audit", result.stage.data.status === "generating");
    finalAuditStatus.value = result.stage.data.status === "generating" ? "failed" : result.stage.data.status || "pending";
    finalAuditError.value = result.stage.data.status === "generating" ? "上次成片审核未完成，请重新审核" : result.stage.data.error || "";
  } catch (error) { finalAuditError.value = error instanceof Error ? error.message : "成片审核数据加载失败"; }
}
async function persistFinalAuditState() {
  const project = activeProjectRecord.value;
  if (!project) return;
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"final_audit", data:{ audits:episodeAudits.value, status:finalAuditStatus.value, error:finalAuditError.value } satisfies FinalAuditStageData });
}
const hasAuditableEpisode = computed(() => episodeMasters.value.some(master => master.status === "confirmed" && master.path && !episodeAudits.value.some(audit => audit.episode === master.episode && audit.status === "pass" && audit.confirmed)));
async function autoRepairFinalEpisode(project:StoredProject, master:EpisodeMaster, issues:string[], attempts:number, controller:AbortController) {
  const planned = await mediaService.repairPlan<{ plan:Array<{ target:string; shot_id?:string | null; disposition:string }> }>({
    ...productionTaskContext(project), attempts,
    errors:issues.map((issue, index) => ({ id:`final-${master.episode}-${index}`, episode:master.episode, shot_id:issue.match(/镜头(\d+)/)?.[1] ? `${master.episode}:${Number(issue.match(/镜头(\d+)/)?.[1])}` : null, error_type:issue })),
  });
  let repaired = false;
  for (const action of planned.plan || []) {
    if (action.disposition !== "auto_repair" || !action.shot_id) continue;
    const [, shotNumberText] = action.shot_id.split(":");
    const item = shotVideos.value.find(value => value.episode === master.episode && value.shot_number === Number(shotNumberText));
    if (!item) continue;
    if (["audio_segment", "mouth_time_window"].includes(action.target)) await repairShotAudio(item);
    else if (action.target === "problem_shot") { item.status = "failed"; item.error = ""; await generateShotVideos(item); }
    else continue;
    if (item.status !== "waiting_confirmation") continue;
    await confirmShotVideo(item); repaired = true;
  }
  if (!repaired) return false;
  master.status = "failed";
  const repairedMaster = await mergeEpisode(project, master.episode, controller);
  repairedMaster.status = "confirmed";
  await persistMergeState();
  return true;
}
async function auditFinalEpisodes() {
  if (!requireEnabledRobot("审核")) return;
  const project = activeProjectRecord.value;
  if (!project || !hasAuditableEpisode.value || finalAuditStatus.value === "generating") return;
  const session = projectSession;
  const controller = new AbortController(); finalAuditController.value?.abort(); finalAuditController.value = controller;
  finalAuditStatus.value = "generating"; finalAuditError.value = ""; await persistFinalAuditState();
  try {
    const commands:Array<Record<string, unknown>> = [];
    for (const master of episodeMasters.value.filter(value => value.status === "confirmed" && value.path && !episodeAudits.value.some(audit => audit.episode === value.episode && audit.status === "pass" && audit.confirmed)).sort((a, b) => a.episode - b.episode)) {
      if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
      const payload = episodeMergePayload(project, master.episode);
      let subtitles = payload.subtitles.map(item => ({ ...item }));
      let ocrStatus = subtitles.length ? "pending" : "not_applicable";
      if (subtitles.length) {
        const textAudit = await mediaService.subtitleTextAudit<{ status:string; errors:Array<{ subtitle_index:number; suggestion:string }> }>({ ...productionTaskContext(project), subtitles }, controller.signal);
        if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
        for (const issue of textAudit.errors || []) {
          const subtitle = subtitles.find(item => item.index === issue.subtitle_index);
          if (subtitle && issue.suggestion) subtitle.text = issue.suggestion;
        }
        const speechAudit = await mediaService.subtitleSpeechAudit<{ status:string; alignments:Array<{ subtitle_index:number; matched:boolean; speech_start?:number; speech_end?:number; start_offset_ms?:number; end_offset_ms?:number }> }>({ ...productionTaskContext(project), path:master.path || master.clean_path, subtitles }, controller.signal);
        if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
        for (const alignment of speechAudit.alignments || []) {
          const subtitle = subtitles.find(item => item.index === alignment.subtitle_index);
          if (!subtitle || !alignment.matched) continue;
          if (Math.abs(alignment.start_offset_ms || 0) > 300 && Number.isFinite(alignment.speech_start)) subtitle.start = Number(alignment.speech_start);
          if (Math.abs(alignment.end_offset_ms || 0) > 500 && Number.isFinite(alignment.speech_end)) subtitle.end = Number(alignment.speech_end);
        }
        const subtitlesChanged = compactFingerprint(subtitles) !== compactFingerprint(payload.subtitles);
        if (subtitlesChanged) {
          const repaired = await mediaService.reburnSubtitles<{ video_url:string; path:string; clean_path:string }>({ ...productionTaskContext(project), episode:master.episode, clean_path:master.clean_path, subtitles, subtitle_style:payload.subtitle_style });
          if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
          master.video_url = repaired.video_url; master.path = repaired.path; master.clean_path = repaired.clean_path; await persistMergeState();
        }
        const ocrAudit = await mediaService.subtitleOcrAudit<{ status:string; errors:Array<{ message:string }> }>({ ...productionTaskContext(project), path:master.path || master.clean_path, subtitles }, controller.signal);
        if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
        if (ocrAudit.status !== "pass") throw new Error(`第${master.episode}集字幕画面复检未通过：${(ocrAudit.errors || []).map(item => item.message).join("；")}`);
        ocrStatus = "pass";
      }
      commands.push({
        episode:master.episode, path:master.path || master.clean_path, subtitles, max_attempts:2,
        process_audits:shotVideos.value.filter(item => item.episode === master.episode).map(item => ({ shot_number:item.shot_number, ...item.audit_evidence })),
        ocr_status:ocrStatus,
        content_compliance_status:outlineAudit.value?.status === "pass" && narrativeAuditsPassed(scriptAudits.value) && narrativeAuditsPassed(storyboardAudits.value) ? "pass" : "needs_fix",
      });
    }
    if (!commands.length || !isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    const auditResponse = await productionLedgerService.runStage<{ items:Array<{ episode:number; status:"pass" | "needs_fix"; issues:string[]; attempts:number }> }>({
      ...productionTaskContext(project), stage:"review_export", operation:"audit", context:productionTaskContext(project), commands,
    }, controller.signal);
    if (!isCurrentProjectSession(project.id, session) || controller.signal.aborted) return;
    for (const audit of auditResponse.result.items) {
      const existingAudit = episodeAudits.value.find(value => value.episode === audit.episode);
      const auditRecord = { episode:audit.episode, status:audit.status, issues:audit.issues || [], attempts:audit.attempts || 0, confirmed:false } satisfies EpisodeAudit;
      if (existingAudit) Object.assign(existingAudit, auditRecord); else episodeAudits.value.push(auditRecord);
    }
    await persistFinalAuditState();
    const failed = auditResponse.result.items.filter(audit => audit.status !== "pass");
    if (failed.length) throw new Error(failed.map(audit => `第${audit.episode}集未通过：${(audit.issues || []).join("；")}`).join(" | "));
    finalAuditStatus.value = episodeAudits.value.length === project.episode_count && episodeAudits.value.every(value => value.confirmed) ? "confirmed" : "waiting_confirmation"; await persistFinalAuditState();
  } catch (error) {
    if (controller.signal.aborted || !isCurrentProjectSession(project.id, session)) return;
    finalAuditStatus.value = "failed"; finalAuditError.value = error instanceof Error ? error.message : "成片审核失败"; await persistFinalAuditState().catch(() => undefined);
  } finally { if (finalAuditController.value === controller) finalAuditController.value = undefined; }
}
async function confirmEpisodeAudit(item:EpisodeAudit) {
  if (item.status !== "pass") return;
  item.confirmed = true;
  if (episodeAudits.value.length === activeProjectRecord.value?.episode_count && episodeAudits.value.every(value => value.confirmed)) finalAuditStatus.value = "confirmed";
  await persistFinalAuditState();
  if (finalAuditStatus.value === "confirmed" && activeProjectRecord.value) await syncProductionLedger(activeProjectRecord.value);
}

type UpscaleStageData = { episodes:EnhancedEpisode[]; status:AssetStatus | "skipped"; error:string };
async function loadUpscaleState(project = activeProjectRecord.value, session = projectSession) {
  enhancedEpisodes.value = []; upscaleStatus.value = "pending"; upscaleError.value = "";
  if (!project) return;
  try {
    const result = await projectService.readStage<UpscaleStageData>({ ...projectIdentity, id:project.id, stage:"upscale" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    enhancedEpisodes.value = result.stage.data.episodes || [];
    projectLoadIsolation.mark(project.id, session, "upscale", result.stage.data.status === "generating");
    upscaleStatus.value = result.stage.data.status === "generating" ? "failed" : result.stage.data.status || "pending"; upscaleError.value = result.stage.data.status === "generating" ? "上次增强任务未完成，正在恢复" : result.stage.data.error || "";
  } catch (error) { upscaleError.value = error instanceof Error ? error.message : "增强数据加载失败"; }
}
async function persistUpscaleState(project = activeProjectRecord.value, session = projectSession) {
  if (!project || !isCurrentProjectSession(project.id, session)) return;
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"upscale", data:{ episodes:enhancedEpisodes.value, status:upscaleStatus.value, error:upscaleError.value } satisfies UpscaleStageData });
}
const hasUpscalableEpisode = computed(() => episodeMasters.value.some(master => master.status === "confirmed" && master.path && episodeAudits.value.some(audit => audit.episode === master.episode && audit.status === "pass" && audit.confirmed) && !enhancedEpisodes.value.some(item => item.episode === master.episode && ["confirmed", "waiting_confirmation", "generating", "skipped"].includes(item.status))));
function runUpscale() {
  if (!requireEnabledRobot("后期制作")) return;
  const project = activeProjectRecord.value;
  if (!project || !hasUpscalableEpisode.value) return;
  const session = projectSession;
  const flightKey = `${project.id}:${session}`;
  if (upscaleFlight && upscaleFlightKey === flightKey) return upscaleFlight;
  if (upscaleStatus.value === "generating") return;
  if (upscaleFlight) { upscaleController.value?.abort(); upscaleFlightEpoch += 1; }
  const controller = new AbortController(); upscaleController.value?.abort(); upscaleController.value = controller;
  const epoch = ++upscaleFlightEpoch;
  upscaleFlightKey = flightKey;
  const flight = runUpscaleTransaction(project, session, controller, epoch);
  upscaleFlight = flight;
  void flight.finally(() => {
    if (upscaleFlight === flight && upscaleController.value === controller && upscaleFlightEpoch === epoch) {
      upscaleFlight = undefined; upscaleFlightKey = ""; upscaleController.value = undefined;
    }
  }).catch(() => undefined);
  return flight;
}
async function runUpscaleTransaction(project:StoredProject, session:number, controller:AbortController, epoch:number) {
  const isCurrentUpscale = () => upscaleFlightEpoch === epoch && isCurrentProjectSession(project.id, session) && !controller.signal.aborted && upscaleController.value === controller;
  const eligibleMasters = episodeMasters.value.filter(master => master.status === "confirmed" && master.path && episodeAudits.value.some(audit => audit.episode === master.episode && audit.status === "pass" && audit.confirmed));
  if (project.upscale === "不超分") {
    enhancedEpisodes.value = eligibleMasters.map(item => ({ episode:item.episode, video_url:item.video_url, path:item.path || item.clean_path, production_evidence:item.production_evidence, status:"skipped" }));
    upscaleStatus.value = "skipped"; upscaleError.value = ""; await persistUpscaleState(project, session); return;
  }
  const quote = await mediaService.upscaleQuote<{ duration_seconds:number; points:number; estimated_seconds:number }>({ ...productionTaskContext(project), paths:eligibleMasters.map(item => item.path || item.clean_path).filter(Boolean) });
  if (!isCurrentUpscale()) return;
  notify(`预计消耗 ${quote.points} 积分，处理约 ${quote.estimated_seconds} 秒`, 5000);
  if (!window.confirm(`已按真实视频时长 ${quote.duration_seconds.toFixed(1)} 秒试算\n预计消耗 ${quote.points} 积分，处理约 ${quote.estimated_seconds} 秒\n确认执行超分降噪？`)) return;
  if (!isCurrentUpscale()) return;
  upscaleStatus.value = "generating"; upscaleError.value = ""; await persistUpscaleState(project, session);
  try {
    const faceReferences = characterProfiles.value.filter(character => character.status === "confirmed" && character.image_url).map(character => character.image_url as string);
    const commands = eligibleMasters.filter(master => !enhancedEpisodes.value.some(item => item.episode === master.episode && ["confirmed", "waiting_confirmation"].includes(item.status))).map(master => {
      const mergePayload = episodeMergePayload(project, master.episode);
      return { episode:master.episode, path:master.path || master.clean_path, source_version:"base", target:{ width:1080, height:1920, fps:30, mode:"quality" }, subtitles:mergePayload.subtitles, reference_urls:faceReferences, content_compliance_status:"not_audited", process_audits:shotVideos.value.filter(value => value.episode === master.episode).map(value => ({ shot_number:value.shot_number, ...value.audit_evidence })) };
    });
    const response = await productionLedgerService.runStage<{ items:EnhancedEpisode[] }>({ ...productionTaskContext(project), stage:"review_export", operation:"upscale", context:productionTaskContext(project), commands }, controller.signal);
    if (!isCurrentUpscale()) return;
    const replaced = new Set(response.result.items.map(item => item.episode));
    enhancedEpisodes.value = [...enhancedEpisodes.value.filter(item => !replaced.has(item.episode)), ...response.result.items].sort((a, b) => a.episode - b.episode);
    upscaleStatus.value = "waiting_confirmation"; await persistUpscaleState(project, session);
  } catch (error) {
    if (!isCurrentUpscale()) return;
    upscaleStatus.value = "failed"; upscaleError.value = error instanceof Error ? error.message : "超分降噪失败"; await persistUpscaleState(project, session).catch(() => undefined);
  }
}
async function stopUpscale() {
  const project = activeProjectRecord.value; if (!project) return;
  const session = projectSession;
  upscaleFlightEpoch += 1;
  upscaleController.value?.abort(); upscaleController.value = undefined;
  upscaleFlight = undefined; upscaleFlightKey = "";
  await productionLedgerService.stopStage({ ...productionTaskContext(project), stage:"review_export" });
  if (!isCurrentProjectSession(project.id, session)) return;
  upscaleStatus.value = "failed"; upscaleError.value = "增强任务已停止，可重新执行";
  await persistUpscaleState(project, session);
}
async function confirmEnhancedEpisode(item:EnhancedEpisode) {
  if (item.status !== "waiting_confirmation") return;
  const project = activeProjectRecord.value; if (!project || !item.content_fingerprint || !item.audit_batch_id || !item.generation) return;
  await productionLedgerService.confirm({ ...productionTaskContext(project), stage:"review_export", scope_type:"episode", scope_id:`upscale:${item.episode}`, content_fingerprint:item.content_fingerprint, audit_batch_id:item.audit_batch_id, generation:item.generation });
  item.status = "confirmed";
  if (enhancedEpisodes.value.length === activeProjectRecord.value?.episode_count && enhancedEpisodes.value.every(value => value.status === "confirmed")) upscaleStatus.value = "confirmed";
  await persistUpscaleState();
}
function importEnhancedEpisode(item:EnhancedEpisode) {
  workflowEpisode.value = item.episode;
  openStandardImport("final_audit");
}
async function regenerateEnhancedEpisode(item:EnhancedEpisode) {
  enhancedEpisodes.value = enhancedEpisodes.value.filter(value => value.episode !== item.episode);
  upscaleStatus.value = "pending";
  await persistUpscaleState();
  await runUpscale();
}

type ExportStageData = { files:ExportFile[]; manifest_url:string; status:AssetStatus; error:string };
async function loadExportState(project = activeProjectRecord.value, session = projectSession) {
  exportFiles.value = []; exportManifestUrl.value = ""; exportStatus.value = "pending"; exportError.value = "";
  if (!project) return;
  try {
    const result = await projectService.readStage<ExportStageData>({ ...projectIdentity, id:project.id, stage:"export" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!result.stage) return;
    exportFiles.value = result.stage.data.files || []; exportManifestUrl.value = result.stage.data.manifest_url || "";
    projectLoadIsolation.mark(project.id, session, "export", result.stage.data.status === "generating");
    exportStatus.value = result.stage.data.status === "generating" ? "failed" : result.stage.data.status || "pending"; exportError.value = result.stage.data.status === "generating" ? "上次导出任务未完成，正在恢复" : result.stage.data.error || "";
  } catch (error) { exportError.value = error instanceof Error ? error.message : "导出记录加载失败"; }
}
async function persistExportState(project = activeProjectRecord.value, session = projectSession) {
  if (!project || !isCurrentProjectSession(project.id, session)) return;
  await projectService.writeStage({ ...projectIdentity, id:project.id, stage:"export", data:{ files:exportFiles.value, manifest_url:exportManifestUrl.value, status:exportStatus.value, error:exportError.value } satisfies ExportStageData });
}
function exportSourceItems() {
  return exportSourceVersion.value === "enhanced"
    ? enhancedEpisodes.value.filter(item => item.path && item.status === "confirmed")
    : episodeMasters.value.filter(item => item.path && item.status === "confirmed");
}
function exportModeEpisodes(mode:"single" | "batch" | "all", project:StoredProject) {
  if (mode === "single") return [workflowEpisode.value || 1];
  if (mode === "batch") return createEpisodeBatches(project.episode_count).find(batch => batch.episodes.includes(workflowEpisode.value || 1))?.episodes || [];
  return Array.from({ length:project.episode_count }, (_, index) => index + 1);
}
function canCreateExports(mode:"single" | "batch" | "all") {
  const project = activeProjectRecord.value;
  if (!project || exportStatus.value === "generating") return false;
  const requiredEpisodes = exportModeEpisodes(mode, project);
  const sourceEpisodes = new Set(exportSourceItems().map(item => item.episode));
  const confirmedAudits = new Set(episodeAudits.value.filter(audit => audit.status === "pass" && audit.confirmed).map(audit => audit.episode));
  const auditRequired = enabledSkills.value.includes("审核");
  return requiredEpisodes.length > 0 && requiredEpisodes.every(episode => sourceEpisodes.has(episode) && (!auditRequired || confirmedAudits.has(episode)));
}
async function createAvailableExports() {
  if (canCreateExports("all")) return createExports("all");
  if (canCreateExports("single")) return createExports("single");
  if (canCreateExports("batch")) return createExports("batch");
}
function createExports(mode:"single" | "batch" | "all" = "all") {
  if (!requireEnabledRobot("后期制作")) return;
  const project = activeProjectRecord.value;
  if (project && exportFlight && exportFlightProjectId === project.id) return exportFlight;
  if (!project || !canCreateExports(mode)) return;
  const session = projectSession;
  const controller = new AbortController(); exportController.value?.abort(); exportController.value = controller;
  const epoch = ++exportFlightEpoch;
  const isCurrentExport = () => epoch === exportFlightEpoch && isCurrentProjectSession(project.id, session) && !controller.signal.aborted;
  exportFlightProjectId = project.id;
  const flight = (async () => {
  if (!isCurrentExport()) return;
  exportStatus.value = "generating"; exportError.value = ""; await persistExportState(project, session);
  if (!isCurrentExport()) return;
  try {
    const requiredEpisodes = new Set(exportModeEpisodes(mode, project));
    const selected = exportSourceItems().filter(item => requiredEpisodes.has(item.episode));
    if (!isCurrentExport()) return;
    const response = await productionLedgerService.runStage<{ files:ExportFile[]; manifest_url:string }>({
      ...productionTaskContext(project), stage:"review_export", operation:"export", context:productionTaskContext(project), command:{
      project_name:project.name, mode, source_version:exportSourceVersion.value,
      items:selected.map(item => ({ episode:item.episode, path:item.path, content_fingerprint:exportSourceVersion.value === "enhanced" && "content_fingerprint" in item ? item.content_fingerprint : compactFingerprint(item.path), audit_batch_id:exportSourceVersion.value === "enhanced" && "audit_batch_id" in item ? item.audit_batch_id : undefined, generation:exportSourceVersion.value === "enhanced" && "generation" in item ? item.generation : undefined, production_evidence:item.production_evidence, subtitles:episodeSubtitles(item.episode) })),
      production_parameters:{ aspect:project.topic.includes("16:9") ? "16:9" : "9:16", duration_min:project.duration_min, duration_max:project.duration_max, language:project.language, subtitle:project.subtitle, upscale:project.upscale, fps:30, color_space:"Rec.709", audio:"48000Hz/16bit/-16LUFS" },
      ai_watermark:{ enabled:metadataAiLabel.value, text:aiWatermarkText.value, color:aiWatermarkColor.value, opacity:aiWatermarkOpacity.value, size:aiWatermarkSize.value, x:aiWatermarkX.value, y:aiWatermarkY.value },
      task_timings:{ outline_seconds:generationElapsedSeconds.value },
      audit_results:episodeAudits.value.map(audit => { const evidence = finalAuditLedgerEvidence(audit); return { episode:audit.episode, status:audit.status, confirmed:audit.confirmed, content_fingerprint:compactFingerprint(evidence), audit_batch_id:compactFingerprint(evidence) }; }),
      audit_required:enabledSkills.value.includes("审核"),
      source_assets:[...characterProfiles.value, ...sceneProfiles.value, ...propProfiles.value].map(asset => ({ name:asset.name, image_url:asset.image_url || "", status:asset.status || "pending" })),
    } }, controller.signal);
    if (!isCurrentExport()) return;
    const result = response.result;
    exportFiles.value = result.files; exportManifestUrl.value = result.manifest_url; exportStatus.value = "confirmed";
    if (!isCurrentExport()) return;
    await persistExportState(project, session);
  } catch (error) {
    if (!isCurrentExport()) return;
    exportStatus.value = "failed"; exportError.value = error instanceof Error ? error.message : "成果导出失败";
    if (!isCurrentExport()) return;
    await persistExportState(project, session).catch(() => undefined);
  }
  })().finally(() => {
    if (exportFlight === flight) { exportFlight = undefined; exportFlightProjectId = ""; }
    if (exportController.value === controller) exportController.value = undefined;
  });
  exportFlight = flight;
  return flight;
}

async function stopExports() {
  const project = activeProjectRecord.value;
  if (!project || exportStatus.value !== "generating") return;
  const session = projectSession;
  const controller = exportController.value;
  exportFlightEpoch += 1;
  controller?.abort();
  if (exportController.value === controller) exportController.value = undefined;
  exportFlight = undefined; exportFlightProjectId = "";
  try {
    const stopped = await productionLedgerService.stopStage({ ...productionTaskContext(project), stage:"review_export" });
    if (!isCurrentProjectSession(project.id, session)) return;
    if (!stopped.stopped || !stopped.stage_cancelled) throw new Error("服务端未确认停止审核导出阶段");
    exportStatus.value = "failed"; exportError.value = "已停止导出，可重新提交";
    await persistExportState(project, session);
  } catch (error) {
    if (!isCurrentProjectSession(project.id, session)) return;
    exportError.value = error instanceof Error ? `停止导出失败：${error.message}` : "停止导出失败";
    await persistExportState(project, session).catch(() => undefined);
  }
}

async function downloadExportBatch() {
  const downloads = [...exportFiles.value.map(file => ({ filename:file.filename, url:file.url })), ...(exportManifestUrl.value ? [{ filename:"manifest.json", url:exportManifestUrl.value }] : [])];
  for (const file of downloads) {
    let lastError:unknown;
    for (let attempt = 1; attempt <= 2; attempt += 1) {
      try {
        const blob = await requestBlobOk(file.url, undefined, `${file.filename} 下载失败`);
        const anchor = document.createElement("a"); anchor.href = URL.createObjectURL(blob); anchor.download = file.filename; anchor.click();
        window.setTimeout(() => URL.revokeObjectURL(anchor.href), 10_000); lastError = undefined; break;
      } catch (error) { lastError = error; }
    }
    if (lastError) return notify(`${file.filename} 下载失败：${lastError instanceof Error ? lastError.message : "未知错误"}`);
  }
  notify("已提交全部交付文件到系统下载目录");
}
function exportKindLabel(kind:string) {
  return kind === "master_h265" ? "H.265 母版" : kind === "distribution_h264" ? "H.264 分发版" : kind === "subtitle_srt" ? "独立 SRT" : "交付文件";
}

function projectPayload() {
  return {
    ...projectIdentity,
    name:newProjectName.value.trim(), category:newProjectGenre.value, topic:newProjectPrompt.value.trim(), style:newProjectGenre.value,
    episode_count:newProjectEpisodes.value, duration_min:newProjectDurationMin.value, duration_max:newProjectDurationMax.value,
    upscale:newProjectUpscale.value, language:newProjectLanguage.value, subtitle:newProjectSubtitle.value, ai_label:newProjectAiLabel.value,
    lora_mode:newProjectLoraMode.value,lora_id:newProjectLoraId.value,lora_exploration_seed:newProjectLoraMode.value==='exploration'?newProjectLoraSeed.value:null,
  };
}

function stableProjectRequirements(project:StoredProject) {
  return { id:project.id, name:project.name, category:project.category, topic:project.topic, style:project.style, language:project.language, episode_count:project.episode_count, duration_min:project.duration_min, duration_max:project.duration_max, upscale:project.upscale };
}

function productionTaskContext(project = activeProjectRecord.value) {
  return { ...projectIdentity, project_id:project?.id || "", plugin_key:"short-video-drama" };
}

async function saveProject() {
  if (!newProjectName.value.trim() || !localLoraStyles.value.some(style => style.id === newProjectGenre.value) || newProjectDurationMin.value > newProjectDurationMax.value) return;
  try {
    const existing = projectRecords.value.find(project => project.name === editingProjectName.value);
    const result = existing
      ? await projectService.update({ ...projectPayload(), id:existing.id })
      : await projectService.create(projectPayload());
    const requirementsChanged = Boolean(existing) && compactFingerprint(stableProjectRequirements(existing!)) !== compactFingerprint(stableProjectRequirements(result.project));
    if (existing && requirementsChanged) {
      await productionLedgerService.invalidate({ ...projectIdentity, project_id:existing.id, source:{ stage:"requirements", scope_type:"project", scope_id:existing.id }, change_type:"semantic", reason:"项目需求已修改" });
    }
    const index = projectRecords.value.findIndex(project => project.id === result.project.id);
    if (index >= 0) projectRecords.value[index] = result.project;
    else projectRecords.value.push(result.project);
    projectRecords.value = [...projectRecords.value].sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.updated_at.localeCompare(a.updated_at));
    projects.value = projectRecords.value.map(project => project.name);
    abortProjectWork();
    activeTab.value = result.project.name;
    appRuntime.projectStore.replace(projectRecords.value, result.project.id);
    selectedNode.value = result.project.name;
    newProjectOpen.value = false;
    await loadProjectFlowState();
    if (!isCurrentProjectSession(result.project.id, projectSession)) return;
    await Promise.all([loadResources(result.project, projectSession), loadTasks(result.project, projectSession), loadProjectVersions(result.project, projectSession)]);
    notify(`项目“${result.project.name}”已${existing ? "保存设置" : "创建"}`);
    newProjectName.value = "";
    editingProjectName.value = "";
  } catch (error) {
    notify(error instanceof Error ? error.message : "项目保存失败");
  }
}

async function deleteProject(projectName: string) {
  const project = projectRecords.value.find(item => item.name === projectName);
  if (!project || !window.confirm(`确认删除项目“${projectName}”？`)) return;
  try {
    await projectService.remove({ ...projectIdentity, id:project.id });
    projectRecords.value = projectRecords.value.filter(item => item.id !== project.id);
    projects.value = projectRecords.value.map(item => item.name);
    if (activeTab.value === projectName) {
      abortProjectWork();
      activeTab.value = projects.value[0] || "";
    }
    appRuntime.projectStore.replace(projectRecords.value, activeProjectRecord.value?.id || "");
    if (activeTab.value) void loadProjectFlowState();
    notify(`项目“${projectName}”已删除`);
  } catch (error) {
    notify(error instanceof Error ? error.message : "项目删除失败");
  }
}

function replaceProjectCollections(records:StoredProject[], preferredProjectId = activeProjectRecord.value?.id || "") {
  projectRecords.value = records.filter(project => !project.archived);
  archivedProjects.value = records.filter(project => project.archived);
  projects.value = projectRecords.value.map(project => project.name);
  appRuntime.projectStore.replace(projectRecords.value, preferredProjectId);
}

async function refreshProjectCollections(preferredProjectId = activeProjectRecord.value?.id || "") {
  const result = await projectService.list(projectIdentity, true);
  replaceProjectCollections(result.projects, preferredProjectId);
}

async function archiveProject(projectName:string) {
  const project = projectRecords.value.find(item => item.name === projectName);
  if (!project || !window.confirm(`归档项目“${projectName}”？项目数据和产物会保留，可随时恢复。`)) return;
  try {
    await projectService.archiveProject({ ...projectIdentity, id:project.id });
    abortProjectWork();
    await refreshProjectCollections();
    activeTab.value = projects.value[0] || "";
    if (activeTab.value) selectProject(activeTab.value);
    notify(`项目“${projectName}”已归档`);
  } catch (error) { notify(error instanceof Error ? error.message : "项目归档失败"); }
}

async function restoreArchivedProject(project:StoredProject) {
  try {
    await projectService.restoreProject({ ...projectIdentity, id:project.id });
    await refreshProjectCollections(project.id);
    activeTab.value = project.name;
    selectProject(project.name);
    notify(`项目“${project.name}”已恢复`);
  } catch (error) { notify(error instanceof Error ? error.message : "项目恢复失败"); }
}

async function loadProjectVersions(project = activeProjectRecord.value, session = projectSession) {
  if (!project) { projectVersions.value = []; return; }
  try {
    const versions = (await projectService.versions({ ...projectIdentity, project_id:project.id })).versions;
    if (isCurrentProjectSession(project.id, session)) projectVersions.value = versions;
  }
  catch (error) { notify(error instanceof Error ? error.message : "项目版本加载失败"); }
}

async function loadProductionVersions(project = activeProjectRecord.value, session = projectSession) {
  if (!project) { productionVersions.value = []; return; }
  try {
    const result = await productionLedgerService.versions({ ...projectIdentity, project_id:project.id });
    if (isCurrentProjectSession(project.id, session)) productionVersions.value = result.versions;
  } catch (error) { notify(error instanceof Error ? error.message : "生产历史版本加载失败"); }
}

async function loadProductionWorkflow(project = activeProjectRecord.value, session = projectSession) {
  if (!project) { productionWorkflow.value = null; return; }
  try {
    const result = await productionLedgerService.workflow({ ...projectIdentity, project_id:project.id });
    if (isCurrentProjectSession(project.id, session)) productionWorkflow.value = result.workflow;
  } catch { if (isCurrentProjectSession(project.id, session)) productionWorkflow.value = null; }
}

async function createProjectVersion() {
  const project = activeProjectRecord.value;
  if (!project) return;
  try {
    await projectService.createVersion({ ...projectIdentity, project_id:project.id, project_name:project.name, stage:"manual", reason:"手动版本" });
    await loadProjectVersions();
    notify("项目版本已创建");
  } catch (error) { notify(error instanceof Error ? error.message : "项目版本创建失败"); }
}

async function rollbackProject(version:ProjectVersion) {
  const project = activeProjectRecord.value;
  if (!project || !window.confirm(`回滚到 ${new Date(version.created_at).toLocaleString("zh-CN")} 的版本？当前状态会先自动归档。`)) return;
  try {
    abortProjectWork();
    const result = await projectService.rollback({ ...projectIdentity, project_id:project.id, version_id:version.version_id });
    await refreshProjectCollections(result.project.id);
    activeTab.value = result.project.name;
    selectProject(result.project.name);
    await loadProjectVersions();
    notify("项目已回滚，回滚前状态已自动归档");
  } catch (error) { notify(error instanceof Error ? error.message : "项目回滚失败"); }
}

function exportProjectData() {
  const project = activeProjectRecord.value;
  if (!project) return;
  const anchor = document.createElement("a");
  anchor.href = projectService.exportUrl({ ...projectIdentity, id:project.id });
  anchor.download = "";
  anchor.click();
}

async function pinProject(projectName: string) {
  const project = projectRecords.value.find(item => item.name === projectName);
  if (!project) return;
  try {
    await projectService.pin({ ...projectIdentity, id:project.id });
    projectRecords.value = projectRecords.value.map(item => ({ ...item, pinned:item.id === project.id }));
    projects.value = [projectName, ...projects.value.filter(item => item !== projectName)];
    appRuntime.projectStore.replace(projectRecords.value, activeProjectRecord.value?.id || "");
    notify(`项目“${projectName}”已置顶`);
  } catch (error) {
    notify(error instanceof Error ? error.message : "项目置顶失败");
  }
}

function openAccountDialog(dialog: Exclude<AccountDialog, "">) {
  accountMenuOpen.value = false;
  accountDialog.value = dialog;
}

async function copyInviteLink() {
  const project = activeProjectRecord.value;
  if (!project) return notify("请先选择项目");
  try {
    const result = await assistantService.createInvitation<{ invitation:{ url:string } }>({ ...projectIdentity, project_id:project.id, role:"editor" });
    await navigator.clipboard.writeText(result.invitation.url);
    notify("邀请链接已复制");
  } catch (error) { notify(error instanceof Error ? error.message : "邀请链接创建失败"); }
}

function openNewProjectDialog() {
  editingProjectName.value = "";
  newProjectName.value = "";
  newProjectPrompt.value = "";
  if (!localLoraStyles.value.some(style => style.id === newProjectGenre.value)) newProjectGenre.value = localLoraStyles.value[0]?.id || "";
  newProjectStyle.value = newProjectGenre.value;
  newProjectUpscale.value = "不超分";
  subtitleExpanded.value = true;
  aiLabelExpanded.value = false;
  newProjectOpen.value = true;
}

function openProjectSettings(projectName: string) {
  const project = projectRecords.value.find(item => item.name === projectName);
  if (!project) return;
  editingProjectName.value = projectName;
  newProjectName.value = project.name;
  newProjectGenre.value = project.category;
  newProjectPrompt.value = project.topic;
  newProjectStyle.value = project.category;
  newProjectEpisodes.value = project.episode_count;
  newProjectDurationMin.value = project.duration_min;
  newProjectDurationMax.value = project.duration_max;
  newProjectUpscale.value = project.upscale;
  newProjectLanguage.value = project.language;
  newProjectSubtitle.value = project.subtitle;
  newProjectAiLabel.value = project.ai_label;
  subtitleExpanded.value = true;
  aiLabelExpanded.value = false;
  projectMenuOpen.value = false;
  newProjectOpen.value = true;
}

function startWatermarkDrag(event: PointerEvent) {
  const preview = (event.currentTarget as HTMLElement).parentElement;
  if (!preview) return;
  const rect = preview.getBoundingClientRect();
  const move = (moveEvent: PointerEvent) => {
    aiWatermarkX.value = Math.min(94, Math.max(6, ((moveEvent.clientX - rect.left) / rect.width) * 100));
    aiWatermarkY.value = Math.min(94, Math.max(6, ((moveEvent.clientY - rect.top) / rect.height) * 100));
  };
  const stop = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", stop);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", stop, { once: true });
}
</script>

<template>
  <div :class="['app-shell', { 'rail-collapsed': railCollapsed }]">
    <svg class="shared-icon-defs" aria-hidden="true">
      <defs>
        <symbol id="icon-trash-simple" viewBox="0 0 24 24"><path d="M5 7h14M9 7V4.8h6V7M7.5 7l.8 12h7.4l.8-12M10 10.5v5M14 10.5v5" /></symbol>
        <symbol id="icon-model-bolt" viewBox="0 0 24 24"><path d="M10.2 2.7 3.8 13.1c-.5.8.1 1.9 1.1 1.9h4.2l-1 5c-.2 1.1 1.2 1.7 1.9.8l9.8-12.2c.6-.8.1-1.9-.9-1.9h-5l.2-3.2c.1-1.2-1.9-1.8-2.5-.8Z" /></symbol>
        <symbol id="icon-chevron-down" viewBox="0 0 24 24"><path d="m5 8.5 7 7 7-7" /></symbol>
        <symbol id="icon-pin-simple" viewBox="0 0 24 24"><path d="m8 4 8 0-1.6 5 2.6 3H7l2.6-3L8 4ZM12 12v8" /></symbol>
        <symbol id="icon-project-edit" viewBox="0 0 24 24"><path d="M12 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6"/><path d="m13 11 5.2-5.2a2 2 0 0 1 2.8 2.8L15.8 13.8 12 15l1-4Z"/></symbol>
        <symbol id="icon-sidebar-task" viewBox="0 0 24 24"><circle cx="7" cy="18" r="2"/><circle cx="17" cy="6" r="2"/><circle cx="17" cy="18" r="2"/><path d="M7 16v-5a3 3 0 0 1 3-3h5M10 8a3 3 0 0 1 3 3v5"/></symbol>
        <symbol id="icon-sidebar-skill" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></symbol>
        <symbol id="icon-sidebar-tools" viewBox="0 0 24 24"><path d="M8.2 7.2A6 6 0 0 1 18 9h-3M15.8 16.8A6 6 0 0 1 6 15h3"/><path d="m15 6 3 3-3 3M9 18l-3-3 3-3"/><circle cx="12" cy="12" r="8.5"/></symbol>
        <symbol id="icon-canvas-outline" viewBox="0 0 24 24"><path d="M6 5h14l-4 14H2L6 5Z" /></symbol>
        <symbol id="icon-progress-clock-outline" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M12 3v9l7.8 4.5" /></symbol>
        <symbol id="icon-material-outline" viewBox="0 0 24 24"><path d="m12 3 9 9-9 9-9-9 9-9Z" /></symbol>
        <symbol id="icon-accelerate-outline" viewBox="0 0 24 24"><path d="M13.5 2 5 13h6l-.5 9L19 10h-6l.5-8Z" /></symbol>
        <symbol id="icon-edit-outline" viewBox="0 0 24 24"><path d="m4 20 4.2-1 10.6-10.6a2.1 2.1 0 0 0-3-3L5.2 16 4 20Z" /><path d="m14.5 6.7 2.8 2.8" /></symbol>
        <symbol id="icon-cycle-outline" viewBox="0 0 24 24"><path d="M7 7h10l-2.8-2.8M17 17H7l2.8 2.8" /><path d="M19 7a7 7 0 0 1 0 10M5 17A7 7 0 0 1 5 7" /></symbol>
        <symbol id="icon-grid-outline" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="1.5" /><path d="M9 3v18M15 3v18M3 9h18M3 15h18" /></symbol>
        <symbol id="icon-history-outline" viewBox="0 0 24 24"><path d="M4.2 8.2V4.5M4.2 8.2h3.7" /><path d="M4.8 7.2A9 9 0 1 1 3 13" /><path d="M12 7v5l3.5 2" /></symbol>
        <symbol id="icon-sync-outline" viewBox="0 0 24 24"><path d="M20 7v5h-5M4 17v-5h5" /><path d="M18.2 10A7 7 0 0 0 6.3 6.5L4 9M5.8 14A7 7 0 0 0 17.7 17.5L20 15" /></symbol>
        <symbol id="icon-copy-outline" viewBox="0 0 24 24"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></symbol>
        <symbol id="icon-check-outline" viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></symbol>
        <symbol id="icon-thumb-up-outline" viewBox="0 0 24 24"><path d="M7 10v10H4V10h3ZM7 18h9.2a2 2 0 0 0 2-1.6l1.2-6A2 2 0 0 0 17.4 8H14l.5-3.1A2.5 2.5 0 0 0 12 2l-1 4-4 4"/></symbol>
        <symbol id="icon-thumb-down-outline" viewBox="0 0 24 24"><path d="M7 14V4H4v10h3ZM7 6h9.2a2 2 0 0 1 2 1.6l1.2 6a2 2 0 0 1-2 2.4H14l.5 3.1A2.5 2.5 0 0 1 12 22l-1-4-4-4"/></symbol>
        <symbol id="icon-share-outline" viewBox="0 0 24 24"><circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.5M8.2 13.2l7.6 4.5"/></symbol>
        <symbol id="icon-quote-outline" viewBox="0 0 24 24"><path d="M6 7h5v5a5 5 0 0 1-5 5M14 7h5v5a5 5 0 0 1-5 5"/></symbol>
      </defs>
    </svg>
    <header class="topbar">
      <div class="topbar-tools">
        <button class="toolbar-button" aria-label="预览设置" title="预览设置" @click="notify('已打开预览显示设置')"><span class="sliders-icon"><i></i><i></i><i></i></span></button>
        <button class="toolbar-button" :aria-label="previewCollapsed ? '展开预览面板' : '向右收起预览面板'" :title="previewCollapsed ? '展开预览面板' : '向右收起预览面板'" @click="previewCollapsed ? expandPreview() : collapsePreview()"><span :class="['panel-icon', { reversed: previewCollapsed }]"></span></button>
      </div>
    </header>

    <main :class="['workspace', { 'preview-collapsed': previewCollapsed || previewClosing || previewOpening, resizing: resizingPanel }]" :style="{ gridTemplateColumns: workspaceColumns }">
      <section class="resource-panel">
        <nav class="sidebar-main" aria-label="资源管理导航">
          <button :class="{ selected: selectedNode === '新项目' }" @click="selectedNode = '新项目'; openNewProjectDialog()"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-project-edit" /></svg>新项目</button>
          <button :class="{ selected: selectedNode === '任务' }" @click="selectedNode = '任务'; workspaceDialog = '任务'"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-sidebar-task" /></svg>任务</button>
          <button :class="{ selected: selectedNode === 'Skill' }" @click="selectedNode = 'Skill'; workspaceDialog = 'Skill'"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-sidebar-skill" /></svg>Skill</button>
          <button :class="{ selected: selectedNode === '工具' }" @click="selectedNode = '工具'; workspaceDialog = '工具'"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-sidebar-tools" /></svg>工具</button>
        </nav>
        <div class="sidebar-projects">
          <div v-for="project in projects" :key="project" :class="['sidebar-project-row', { active: activeTab === project }]">
            <button class="sidebar-project-main" @click="selectProject(project)">
              <span></span><strong>{{ project }}</strong>
            </button>
            <div class="sidebar-project-actions">
              <button aria-label="置顶项目" title="置顶项目" @click.stop="pinProject(project)">
                <svg class="shared-action-icon" aria-hidden="true"><use href="#icon-pin-simple" /></svg>
              </button>
              <button aria-label="编辑项目" title="编辑项目" @click.stop="openProjectSettings(project)">
                <svg class="shared-action-icon" aria-hidden="true"><use href="#icon-project-edit" /></svg>
              </button>
              <button class="danger" aria-label="删除项目" title="删除项目" @click.stop="deleteProject(project)">
                <svg class="shared-action-icon" aria-hidden="true"><use href="#icon-trash-simple" /></svg>
              </button>
            </div>
          </div>
        </div>
        <div class="sidebar-scroll">
          <button class="sidebar-heading collapsible-heading" @click="publicResourcesExpanded = !publicResourcesExpanded"><span :class="{ collapsed: !publicResourcesExpanded }">⌄</span>公共资源</button>
          <div :class="['sidebar-group-content', { collapsed: !publicResourcesExpanded }]">
            <button v-for="node in ['人物定妆公共', '场景公共', '姿态管理', '特效素材']" :key="node" class="sidebar-item" :class="{ selected: selectedNode === node }" @click="selectedNode = node">{{ node }}</button>
            <button v-for="name in dynamicGlobalNodes" :key="name" class="sidebar-item nested" @click="selectedNode = name">图片 · {{ name }}</button>
          </div>

          <div class="sidebar-heading projects-heading">项目</div>
          <button v-if="activeTab" class="sidebar-item project-title" :class="{ selected: selectedNode === activeTab }" @click="selectedNode = activeTab; projectResourcesExpanded = !projectResourcesExpanded"><span :class="['group-chevron', { collapsed: !projectResourcesExpanded }]">⌄</span>{{ activeTab }}</button>
          <div v-if="activeTab" :class="['sidebar-group-content project-content', { collapsed: !projectResourcesExpanded }]">
            <div class="episode-pills">
              <button v-for="episode in projectEpisodeOptions" :key="episode" :class="{ selected: selectedEpisode === episode }" @click="selectedEpisode = episode">{{ episode }}</button>
            </div>
            <button v-for="node in ['剧本', '分镜', '定妆素材', '场景素材', '生图输出', '分镜视频', '合成视频', '本集日志']" :key="node" class="sidebar-item nested" :class="{ selected: selectedNode === node }" @click="selectedNode = node; node === '生图输出' && (rightPanelMode = 'images', rightPanelTitle = `生图输出｜${activeTab}${selectedEpisode ? ` · ${selectedEpisode}` : ''}`)">{{ node }}</button>
            <button v-for="name in dynamicEpisodeNodes" :key="name" class="sidebar-item nested" @click="selectedNode = name">本集 · {{ name }}</button>
          </div>
        </div>
        <div class="sidebar-account">
          <div v-if="accountMenuOpen" class="account-menu">
            <div class="account-menu-profile"><span class="account-avatar">AO</span><strong>aoo</strong></div>
            <div class="account-menu-divider"></div>
            <button @click="openAccountDialog('剩余用量')"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-edit-outline" /></svg>剩余用量<i>›</i></button>
            <button @click="openAccountDialog('显示宠物')"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-cycle-outline" /></svg>显示宠物</button>
            <button @click="openAccountDialog('邀请好友')"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-grid-outline" /></svg>邀请好友</button>
            <button @click="openAccountDialog('设置')"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-history-outline" /></svg>设置<small>⌘,</small></button>
            <button @click="openAccountDialog('退出登录')"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-sync-outline" /></svg>退出登录</button>
          </div>
          <button class="account-profile-button" @click="accountMenuOpen = !accountMenuOpen"><span class="account-avatar">AO</span><strong>aoo</strong></button>
          <button class="account-download-button" aria-label="Update" @click="notify('已打开导出任务')"><svg class="download-icon" viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3.25v8.5m0 0L6.75 8.5M10 11.75l3.25-3.25M4.5 12.25v1.5a2 2 0 0 0 2 2h7a2 2 0 0 0 2-2v-1.5" /></svg><span>Update</span></button>
        </div>
      </section>

      <div class="panel-splitter left-splitter" :style="{ left: `${leftPanelWidth - 4}px` }" role="separator" aria-label="调整左侧栏宽度" @pointerdown="startPanelResize('left', $event)" @dblclick="leftPanelWidth = 280"><span>↔</span></div>

      <section class="panel chat-panel" :class="{ dragging: isDragging }" @dragenter.prevent="isDragging = true" @dragover.prevent="isDragging = true" @dragleave.prevent="isDragging = false" @drop.prevent="onDrop">
        <div ref="chatScroll" class="chat-body" @scroll="persistUiState">
          <article v-for="(chat, index) in chats" :key="index" :class="['message-row', chat.side]">
            <div :class="[chat.side === 'right' ? 'user-bubble' : 'assistant-response', { 'has-media':chat.media?.length }]">
              <div v-if="chat.media?.length" class="message-media"><template v-for="(asset, mediaIndex) in chat.media" :key="asset.id"><img v-if="asset.mediaType === 'image'" :src="asset.url" :alt="asset.name" role="button" tabindex="0" @click.stop="openGeneratedImage(`chat:${index}:${mediaIndex}`)" @keyup.enter="openGeneratedImage(`chat:${index}:${mediaIndex}`)" /><video v-else-if="asset.mediaType === 'video'" :src="asset.url" muted role="button" tabindex="0" title="点击放大预览" @click.stop="openGeneratedImage(`chat:${index}:${mediaIndex}`)" @keyup.enter="openGeneratedImage(`chat:${index}:${mediaIndex}`)" /><audio v-else :src="asset.url" controls /></template></div>
              <p class="message-text"><span class="message-content">{{ chat.text }}</span><span class="message-actions"><time class="message-action-time" :datetime="new Date(chat.createdAt || chatFallbackCreatedAt).toISOString()">{{ formatChatClock(chat.createdAt) }}</time><button :aria-label="copiedChatIndex === index ? '已复制' : '复制'" title="复制" @click="copyChatText(chat.text, index)"><svg aria-hidden="true"><use :href="copiedChatIndex === index ? '#icon-check-outline' : '#icon-copy-outline'" /></svg></button><button :class="{ active: chatFeedback[index] === 'up' }" aria-label="赞" title="赞" @click="setChatFeedback(index, 'up')"><svg aria-hidden="true"><use href="#icon-thumb-up-outline" /></svg></button><button :class="{ active: chatFeedback[index] === 'down' }" aria-label="踩" title="踩" @click="setChatFeedback(index, 'down')"><svg aria-hidden="true"><use href="#icon-thumb-down-outline" /></svg></button><button aria-label="分享" title="分享" @click="shareChatText(chat.text)"><svg aria-hidden="true"><use href="#icon-share-outline" /></svg></button><button aria-label="引用" title="引用" @click="quoteChatText(chat.text)"><svg aria-hidden="true"><use href="#icon-quote-outline" /></svg></button></span></p><p v-if="chat.status" class="activity-line">{{ chat.status }}</p>
            </div>
          </article>
          <div v-if="thinking" class="assistant-response thinking-response"><div class="message-time-row"><span>Time: {{ formatChatDuration(thinkingElapsedSeconds) }}</span></div><StatusPulse /></div>
        </div>
        <div class="composer">
          <input ref="fileInput" class="file-input" type="file" accept="image/*,video/*,audio/*" multiple @change="onFileInputChange" />
          <input ref="assetReplaceInput" class="file-input" type="file" accept="image/*" @change="onAssetReplacement" />
          <input ref="shotImageReplaceInput" class="file-input" type="file" accept="image/*" @change="onShotImageReplacement" />
          <input ref="shotVideoReplaceInput" class="file-input" type="file" accept="video/*" @change="onShotVideoReplacement" />
          <input ref="standardImportInput" class="file-input" type="file" @change="onStandardImport" />
          <div :class="['composer-shell', { 'has-staged-assets': stagedAssets.length }]">
            <div v-if="stagedAssets.length" class="staged-assets">
              <div v-for="asset in stagedAssets" :key="asset.id" class="staged-asset">
                <img v-if="asset.mediaType === 'image'" :src="asset.url" :alt="asset.name" role="button" tabindex="0" title="点击放大预览" @click="openPreviewAsset(asset)" @keyup.enter="openPreviewAsset(asset)" />
                <video v-else-if="asset.mediaType === 'video'" :src="asset.url" muted role="button" tabindex="0" title="点击放大预览" @click="openPreviewAsset(asset)" @keyup.enter="openPreviewAsset(asset)"></video><audio v-else :src="asset.url" controls></audio>
                <button aria-label="移除素材" @click="stagedAssets = stagedAssets.filter((item) => item.id !== asset.id)">×</button>
              </div>
            </div>
            <div v-if="mentionMenuOpen" class="mention-menu" role="listbox" aria-label="选择系统 AI">
              <button v-for="(agent, index) in mentionCandidates" :key="agent.id" :class="{ active:index === activeMentionIndex }" type="button" role="option" :aria-selected="index === activeMentionIndex" @mousedown.prevent="selectMentionAgent(agent)"><strong>@{{ agent.label }}</strong><span>{{ agent.description }}</span></button>
            </div>
            <textarea v-model="input" rows="4" @input="activeMentionIndex = 0" @paste="onPaste" @keydown="handleComposerKeydown" placeholder="输入指令，输入 @ 可选择主力开发、软件测试或代码稽查"></textarea>
            <div class="composer-footer">
              <button class="composer-icon" aria-label="上传图片或视频" @click="fileInput?.click()">＋</button>
              <div class="model-selector">
                <button class="model-chip" :aria-expanded="modelMenuOpen" aria-haspopup="menu" :aria-label="`模型：${modelDisplayName}，推理强度${modelEffort}`" @click.stop="modelMenuOpen = !modelMenuOpen"><svg class="model-bolt" aria-hidden="true"><use href="#icon-model-bolt" /></svg><span class="model-name">{{ modelDisplayName }}</span><span class="model-effort">{{ modelEffort }}</span><svg class="model-chevron" aria-hidden="true"><use href="#icon-chevron-down" /></svg></button>
                <div v-if="modelMenuOpen" class="model-selector-menu" role="menu">
                  <button class="model-setting-row"><strong>模型</strong><span>{{ modelDisplayName }}</span><svg aria-hidden="true"><use href="#icon-chevron-down" /></svg></button>
                  <button class="model-setting-row active"><strong>推理强度</strong><span>{{ modelEffort }}</span><svg aria-hidden="true"><use href="#icon-chevron-down" /></svg></button>
                  <button class="model-setting-row"><strong>速度</strong><span>快速</span><svg aria-hidden="true"><use href="#icon-chevron-down" /></svg></button>
                  <button class="model-advanced-row"><strong>高级</strong><svg aria-hidden="true"><use href="#icon-chevron-down" /></svg></button>
                  <section class="model-effort-panel" aria-label="推理强度">
                    <h3>推理强度</h3>
                    <button v-for="effort in ['轻度', '中', '高', '极高'] as const" :key="effort" :class="{ active: modelEffort === effort }" @click="modelEffort = effort"><span><strong>{{ effort }}</strong><small v-if="effort === '极高'">更快消耗使用额度</small></span><svg v-if="modelEffort === effort" aria-hidden="true"><use href="#icon-check-outline" /></svg></button>
                  </section>
                </div>
              </div>
              <span class="composer-spacer"></span>
              <button :class="['mode-chip', { active:webSearchEnabled }]" type="button" :aria-pressed="webSearchEnabled" title="开启后本条消息强制联网搜索并附来源" @click="webSearchEnabled = !webSearchEnabled">联网</button>
              <nav class="workflow-navigation" aria-label="生产内容导航">
                <button v-for="kind in workflowDockNavigation" :key="kind" :class="['mode-chip', 'workflow-dock-chip', { active: activeWorkflowNavigation === kind }]" @click="selectWorkflowNavigation(kind)">{{ workflowDockLabel(kind) }}<span v-if="workflowUnread[kind]" class="workflow-unread-dot" aria-label="有已完成内容"></span></button>
              </nav>
              <button class="composer-icon" aria-label="语音输入" @click="notify('语音输入交互示意')"><span class="mic-icon" aria-hidden="true"></span></button>
              <button class="send-button" aria-label="发送" :disabled="(!input.trim() && !stagedAssets.length) || chatHistoryLoading" @click="sendMessage">
                <span class="send-arrow-icon" aria-hidden="true"></span>
              </button>
            </div>
          </div>
        </div>
        <div v-if="isDragging" class="drop-overlay">松开即可上传图片或视频</div>
      </section>

      <div v-show="!previewCollapsed && !previewClosing && !previewOpening" class="panel-splitter right-splitter" :style="{ right: `${rightPanelWidth - 4}px` }" role="separator" aria-label="调整右侧栏宽度" @pointerdown="startPanelResize('right', $event)" @dblclick="rightPanelWidth = 340"><span>↔</span></div>

      <section v-show="!previewCollapsed" :class="['panel preview-panel', { 'sliding-right': previewClosing || previewOpening }]">
        <WorkflowStatusHeader class="panel-header workflow-panel-header" :title="workflowHeaderTitle" :current="workflowProgress.current" :total="workflowProgress.total" :elapsed-seconds="workflowElapsedSeconds">
          <template #actions><div v-if="rightPanelMode === 'assets'" class="asset-category-tabs asset-category-tabs-header" role="tablist" aria-label="资产分类"><button v-for="category in (['人物', '道具', '场景'] as const)" :key="category" :class="{ active:activeAssetCategory === category }" role="tab" :aria-label="`${category}，共${assetCategoryImageTotal(category)}项资产`" :aria-selected="activeAssetCategory === category" @click="syncWorkflowAsset(category)"><span>{{ category }}</span><b>{{ assetCategoryImageTotal(category) }}</b></button></div><WorkflowEpisodeSelector :model-value="workflowEpisode" :episode-count="activeProjectRecord?.episode_count || 0" @update:model-value="selectWorkflowEpisode" /></template>
        </WorkflowStatusHeader>
        <div v-if="rightPanelMode === 'assets'" class="content-preview outline-preview asset-production-preview">
          <WorkflowActionBar :running="assetImagesRunning || queuedAssetOperationCount > 0" :primary-label="assetImageActionLabel" :primary-disabled="!assetGenerationReady" :next-label="assetsReadyForShotImages ? '生成分镜画面' : undefined" @import="importCurrentWorkflow" @primary="queueGenerateAllAssetImages" @pause="stopAllAssetGeneration" @next="enterShotImageGeneration" />
          <p v-if="!assetGenerationReady" class="outline-error">请先生成分镜脚本</p><p v-if="assetStageError && !allAssetProfiles.some(item => item.status === 'generating')" class="outline-error">{{ userFacingGenerationError(assetStageError) }}</p>
          <section v-for="group in visibleAssetGroups" :key="group.kind" :class="['asset-profile-group', `asset-profile-group-${group.kind}`]">
            <UnifiedAssetCard v-for="item in group.items" :key="item.name" :kind="group.kind" :item="item" :slides="unifiedAssetSlides(group.kind, item)" :intro-open="assetIntroOpen" :can-accept-baseline="canAcceptAssetBaseline(item)" :user-error="userFacingGenerationError(item.error)" @pointer-down="startAssetCarouselDrag" @pointer-move="moveAssetCarouselDrag" @pointer-up="endAssetCarouselDrag" @pointer-cancel="endAssetCarouselDrag" @toggle-intro="slide => toggleUnifiedAssetIntro(group.kind, item, slide)" @close-intro="assetIntroOpen = ''" @preview="slide => openAssetCarouselImage(slide.previewId)" @import="slide => openAssetPhotoReplacement(group.kind, item, assetSlide(slide))" @regenerate="slide => queueAssetSlideRegeneration(group.kind, item, slide)" @repair="slide => queueAssetSlideRepair(group.kind, item, slide)" @reference="slide => referenceWorkflowMedia(`${item.name}-${slide.label}`, slide.imageUrl, 'image')" @accept="slide => queueAssetSlideAcceptance(item, slide)" @confirm-baseline="queueAssetBaselineAcceptance(item)" @generate3d="queueAsset3D(group.kind, item)" @confirm3d="queueAsset3DConfirmation(item)" @stop3d="stopAsset3D(item)" @upscale="queueAssetUpscale(`${item.name}-基准图`, item.image_url)" />
          </section>
        </div>
        <div v-else-if="rightPanelMode === 'images'" class="preview-grid">
          <WorkflowActionBar v-if="activeWorkflowNavigation === '分镜画面'" :running="shotImageStatus === 'generating'" :primary-label="shotImages.some(item => item.image_url) ? (shotImages.filter(item => item.image_url).length === storyboardShots.length ? '重新生成分镜画面' : '继续生成分镜画面') : '生成分镜画面'" :primary-disabled="!assetsReadyForShotImages" :next-label="shotImagesReadyForVideo ? '生成分镜视频' : undefined" @import="importCurrentWorkflow" @primary="generateShotImages" @pause="stopShotImages" @next="enterShotVideoGeneration"><template #status><StatusPulse v-if="shotImageStatus === 'generating'" class="script-stage-indicator" text="分镜画面生成中......" /></template><p v-if="shotImageError">{{ shotImageError }}</p><p v-else-if="missingAssetsForShotImages.length">请先上传完整资产：{{ missingAssetsForShotImages.join('、') }}</p></WorkflowActionBar>
          <article v-for="item in (activeWorkflowNavigation === '分镜画面' ? visibleShotImages : [])" :key="`${item.episode}-${item.shot_number}`" class="preview-card portrait shot-production-card">
            <img v-if="item.image_url" :src="item.image_url" :alt="`第${item.episode}集镜头${item.shot_number}`" class="clickable-preview-image" role="button" tabindex="0" @click="openGeneratedImage(`shot:${item.episode}:${item.shot_number}`)" @keyup.enter="openGeneratedImage(`shot:${item.episode}:${item.shot_number}`)" /><span v-else class="upload-hint">第{{ item.episode }}集 · 镜头{{ item.shot_number }}</span><small>第{{ item.episode }}集 · 镜头{{ item.shot_number }} · {{ item.status === 'confirmed' || item.status === 'waiting_confirmation' ? '已生成' : item.status === 'generating' ? '生成中' : item.status === 'pending' ? '待重新生成' : '失败' }}</small><MediaOverlayControls media-type="image" :generating="item.status === 'generating'" :can-reference="Boolean(item.image_url)" @intro="assetIntroOpen = assetIntroOpen === `shot-image:${item.episode}:${item.shot_number}` ? '' : `shot-image:${item.episode}:${item.shot_number}`" @import="openShotImageReplacement(item)" @regenerate="regenerateShotImage(item)" @reference="referenceWorkflowMedia(`第${item.episode}集-镜头${item.shot_number}`, item.image_url, 'image')" /><div v-if="assetIntroOpen === `shot-image:${item.episode}:${item.shot_number}`" class="shot-media-intro-panel"><strong>第{{ item.episode }}集 · 镜头{{ item.shot_number }}</strong><p>{{ storyboardShots.find(shot => shot.episode === item.episode && shot.shot_number === item.shot_number)?.visual || item.prompt_override || '暂无画面简介' }}</p><p>{{ storyboardShots.find(shot => shot.episode === item.episode && shot.shot_number === item.shot_number)?.action || '' }}</p></div>
            <div v-if="item.image_url" class="shot-identity-actions"><button type="button" @click="upscaleWorkflowImage(`第${item.episode}集-镜头${item.shot_number}`, item.image_url)">AI图片超分</button><button type="button" @click="refineShotIdentity(item, 'pulid')">PuLID修正</button><button type="button" @click="refineShotIdentity(item, 'reactor')">ReActor修正</button></div>
          </article>
          <div v-for="(asset, index) in (activeWorkflowNavigation === '分镜画面' ? [] : visibleImages)" :key="asset.id" class="preview-card" :class="[{ selected: selectedImage === index }, asset.aspect || 'portrait']" role="button" tabindex="0" @click="asset.id === 'add' ? fileInput?.click() : (selectedImage = index, openPreviewAsset(asset))" @keyup.enter="asset.id === 'add' ? fileInput?.click() : (selectedImage = index, openPreviewAsset(asset))">
            <template v-if="!asset.url"><span class="plus">＋</span><span class="upload-hint">点击添加或拖到此处</span></template>
            <img v-else-if="asset.mediaType === 'image'" :src="asset.url" :alt="asset.name" />
            <video v-else :src="asset.url" muted controls></video>
            <span v-if="asset.id !== 'add'" class="image-delete" role="button" tabindex="0" aria-label="删除图片" title="删除" @click.stop="deletePreviewAsset(asset)" @keyup.enter.stop="deletePreviewAsset(asset)"><svg class="shared-action-icon" aria-hidden="true"><use href="#icon-trash-simple" /></svg></span>
            <span v-if="asset.id !== 'add'" class="image-regenerate" role="button" tabindex="0" @click.stop="regenerateAsset(asset, $event)" @keyup.enter.stop="regenerateAsset(asset, $event)">重新生成</span>
          </div>
        </div>
        <div v-else-if="rightPanelMode === 'outline'" class="content-preview outline-preview">
          <WorkflowActionBar
            :running="outlineStatus === 'generating'"
            :primary-label="outlinePlan ? '重新生成大纲' : '生成大纲'"
            :primary-disabled="!activeProjectRecord"
            :next-label="outlineHasCompleteEpisode ? '生成剧本' : undefined"
            @import="importCurrentWorkflow"
            @primary="generateOutline()"
            @pause="outlinePhase === 'audit' || outlinePhase === 'repair' ? stopOutlineAudit() : stopOutline()"
            @next="generateScriptsFromOutline"
          >
            <template #status>
            <StatusPulse v-if="outlineStatus === 'generating' && outlineThinking" class="outline-thinking-label" />
            <strong v-else-if="outlineStatus === 'generating' || outlineStatus === 'waiting_confirmation'" class="narrative-progress"></strong>
            <strong v-else-if="outlineStatus !== 'confirmed'">{{ outlineStatus === 'failed' ? '生成失败' : '未生成' }}</strong>
            <StatusPulse v-if="outlineStatus === 'generating' && outlinePhaseText" class="script-stage-indicator" :text="outlinePhaseText" />
            </template>
            <button v-if="narrativeStageHasDrafts('outline')" :disabled="narrativeEditSubmitting" @click="submitNarrativeEdits('outline')">提交修改</button>
            <button v-if="outlineAuditStopped && outlineStatus !== 'generating'" @click="continueOutlineAudit">继续审核</button>
          </WorkflowActionBar>
          <p v-if="outlineError && !outlineAuditStopped" class="outline-error">{{ outlineError }}</p>
          <template v-if="outlineDisplayPlan">
            <NarrativeCollectionHeader title="全剧故事大纲" :copied="copiedEpisodeKey === 'outline-all'" copy-label="复制全部剧集" @copy="copyEpisodeText(allOutlineText(), 'outline-all')" @quote="quoteChatText(allOutlineText())"><template #title><h3 class="outline-drama-title" :contenteditable="outlineStatus !== 'generating'" :aria-label="outlineStatus !== 'generating' ? '编辑剧名' : '剧名'" @blur="commitOutlineTitle" @keydown.enter.prevent="($event.currentTarget as HTMLElement).blur()">{{ outlineShowingReviewSnapshot ? outlineDisplayPlan.title : outlineStatus === 'generating' ? outlineTypedTitle : outlineDisplayPlan.title || '全剧故事大纲' }}</h3></template></NarrativeCollectionHeader>
            <section v-if="outlineCoreCharacters.length" class="outline-core-characters" :class="{ expanded:outlineCharactersExpanded }">
              <button class="outline-core-characters-toggle" type="button" :aria-expanded="outlineCharactersExpanded" @click="outlineCharactersExpanded = !outlineCharactersExpanded"><span>核心人物简介（{{ outlineCoreCharacters.length }}）</span><span class="outline-core-characters-chevron" aria-hidden="true">⌄</span></button>
              <ol v-show="outlineCharactersExpanded"><li v-for="character in outlineCoreCharacters" :key="character.name"><strong>{{ character.name }}</strong>｜{{ character.identity }}｜{{ character.personality }}｜{{ character.coreMotivation }}</li></ol>
            </section>
            <p :contenteditable="outlineStatus !== 'generating'" @input="updateNarrativeDraft('outline', 'outline:project:general', outlineDisplayPlan.general_outline, { stage:'outline', scope_type:'project', scope_id:activeProjectRecord?.id || '' }, $event)">{{ outlineShowingReviewSnapshot ? outlineDisplayPlan.general_outline : outlineStatus === 'generating' ? outlineTypedPlan : outlineDisplayPlan.general_outline }}<NarrativeItemActions :disabled="outlineStatus === 'generating'" :copied="copiedEpisodeKey === 'outline-summary'" delete-label="删除大纲" @delete="deleteOutlineSummary" @copy="copyEpisodeText(`${outlineDisplayPlan.title}\n${outlineShowingReviewSnapshot ? outlineDisplayPlan.general_outline : outlineStatus === 'generating' ? outlineTypedPlan : outlineDisplayPlan.general_outline}`, 'outline-summary')" @quote="quoteChatText(`${outlineDisplayPlan.title}\n${outlineShowingReviewSnapshot ? outlineDisplayPlan.general_outline : outlineStatus === 'generating' ? outlineTypedPlan : outlineDisplayPlan.general_outline}`)" /></p>
            <section v-for="episode in outlineVisibleEpisodes" v-show="outlineShowingReviewSnapshot || outlineStatus !== 'generating' || outlineTypedEpisodes[episode.episode]" :key="episode.episode" class="outline-episode">
              <strong>第{{ String(episode.episode).padStart(2, '0') }}集 · {{ outlineShowingReviewSnapshot ? episode.title : outlineStatus === 'generating' ? outlineTypedEpisodes[episode.episode]?.title : episode.title }}</strong>
              <p :contenteditable="outlineStatus !== 'generating'" @input="updateNarrativeDraft('outline', `outline:episode:${episode.episode}:synopsis`, episode.synopsis, { stage:'outline', scope_type:'episode', scope_id:String(episode.episode) }, $event)">{{ outlineShowingReviewSnapshot ? episode.synopsis : outlineStatus === 'generating' ? outlineTypedEpisodes[episode.episode]?.synopsis : episode.synopsis }}<NarrativeItemActions :disabled="outlineStatus === 'generating'" :copied="copiedEpisodeKey === `outline-${episode.episode}`" @delete="deleteOutlineEpisode(episode.episode)" @copy="copyEpisodeText(`${outlineShowingReviewSnapshot ? episode.title : outlineStatus === 'generating' ? outlineTypedEpisodes[episode.episode]?.title : episode.title}\n${outlineShowingReviewSnapshot ? episode.synopsis : outlineStatus === 'generating' ? outlineTypedEpisodes[episode.episode]?.synopsis : episode.synopsis}`, `outline-${episode.episode}`)" @quote="quoteChatText(`${outlineShowingReviewSnapshot ? episode.title : outlineStatus === 'generating' ? outlineTypedEpisodes[episode.episode]?.title : episode.title}\n${outlineShowingReviewSnapshot ? episode.synopsis : outlineStatus === 'generating' ? outlineTypedEpisodes[episode.episode]?.synopsis : episode.synopsis}`)" /></p>
            </section>
            <section v-if="outlineStatus === 'generating' && !outlineShowingReviewSnapshot && outlinePendingEpisode !== null" class="outline-episode outline-episode-thinking" role="status" aria-live="polite">
              <StatusPulse class="outline-thinking-label" />
            </section>
          </template>
          <p v-else-if="!activeProjectRecord">请先创建并选择项目</p>
        </div>
        <div v-else-if="rightPanelMode === 'script'" class="content-preview outline-preview">
          <WorkflowActionBar :running="scriptStatus === 'generating'" :primary-label="scripts.length ? (scriptStatus === 'confirmed' ? '重新生成剧本' : '继续生成剧本') : '生成剧本'" :primary-disabled="!outlineHasCompleteEpisode" :next-label="scripts.length ? '生成分镜脚本' : undefined" :next-disabled="!scriptHasCompleteEpisode" @import="importCurrentWorkflow" @primary="runScriptPrimaryAction" @pause="stopScripts" @next="enterStoryboardGeneration"><template #status><StatusPulse v-if="scriptStatus === 'generating' && scriptPhaseText" class="script-stage-indicator" :text="scriptPhaseText" /></template><button v-if="narrativeStageHasDrafts('script')" :disabled="narrativeEditSubmitting" @click="submitNarrativeEdits('script')">提交修改</button></WorkflowActionBar>
          <p v-if="outlineStatus !== 'confirmed'" class="outline-error">请先完成人工确认故事大纲</p><p v-if="scriptError" class="outline-error">{{ scriptError }}</p>
          <NarrativeCollectionHeader v-if="scripts.length" :title="outlinePlan?.title || activeProjectRecord?.name || '全剧剧本'" :copied="copiedEpisodeKey === 'script-all'" copy-label="复制全部剧集" @copy="copyEpisodeText(allScriptText(), 'script-all')" @quote="quoteChatText(allScriptText())" />
          <section v-for="script in visibleScripts" :key="script.episode" class="outline-episode">
            <h3>第{{ String(script.episode).padStart(2, '0') }}集 · {{ script.title }}</h3>
            <p class="script-content" :contenteditable="scriptStatus !== 'generating'" @input="updateNarrativeDraft('script', `script:episode:${script.episode}:content`, humanReadableScriptContent(script.content), { stage:'script', scope_type:'episode', scope_id:String(script.episode) }, $event)">{{ humanReadableScriptContent(script.content) }}<NarrativeItemActions :disabled="scriptStatus === 'generating'" :copied="copiedEpisodeKey === `script-${script.episode}`" @delete="deleteScriptEpisode(script.episode)" @copy="copyEpisodeText(`${script.title}\n${humanReadableScriptContent(script.content)}`, `script-${script.episode}`)" @quote="quoteChatText(`${script.title}\n${humanReadableScriptContent(script.content)}`)" /></p>
          </section>
        </div>
        <div v-else-if="rightPanelMode === 'storyboard'" class="content-preview outline-preview">
          <WorkflowActionBar :running="storyboardStatus === 'generating'" :primary-label="storyboardShots.length ? (storyboardStatus === 'confirmed' ? '重新生成分镜脚本' : '继续生成分镜脚本') : '生成分镜脚本'" :primary-disabled="!scriptHasCompleteEpisode" :next-label="storyboardHasCompleteEpisode ? '生成图片' : undefined" @import="importCurrentWorkflow" @primary="runStoryboardPrimaryAction" @pause="stopStoryboards" @next="enterAssetGeneration"><template #status><StatusPulse v-if="storyboardStatus === 'generating'" class="script-stage-indicator" text="分镜脚本生成中......" /></template><button v-if="narrativeStageHasDrafts('storyboard')" :disabled="narrativeEditSubmitting" @click="submitNarrativeEdits('storyboard')">提交修改</button></WorkflowActionBar>
          <p v-if="!scripts.length" class="outline-error">请先生成至少一集剧本</p><p v-if="storyboardError" class="outline-error">{{ storyboardError }}</p>
          <NarrativeCollectionHeader v-if="storyboardShots.length" :title="outlinePlan?.title || activeProjectRecord?.name || '全剧分镜脚本'" :copied="copiedEpisodeKey === 'storyboard-all'" copy-label="复制全部剧集" @copy="copyEpisodeText(allStoryboardText(), 'storyboard-all')" @quote="quoteChatText(allStoryboardText())" />
          <section v-for="group in storyboardEpisodeGroups" :key="group.episode" class="outline-episode">
            <h3>第{{ String(group.episode).padStart(2, '0') }}集 · {{ group.title }}</h3>
            <p class="script-content"><template v-for="shot in group.shots" :key="shot.shot_number"><strong>镜头{{ String(shot.shot_number).padStart(2, '0') }} · {{ shot.start_second }}–{{ shot.end_second }}s</strong><br><span :contenteditable="storyboardStatus !== 'generating'" @input="updateNarrativeDraft('storyboard', `storyboard:shot:${shot.episode}:${shot.shot_number}:visual`, shot.visual, { stage:'storyboard', scope_type:'shot', scope_id:`${shot.episode}:${shot.shot_number}` }, $event)">画面：{{ shot.visual }}</span><br><span :contenteditable="storyboardStatus !== 'generating'" @input="updateNarrativeDraft('storyboard', `storyboard:shot:${shot.episode}:${shot.shot_number}:action`, shot.action, { stage:'storyboard', scope_type:'shot', scope_id:`${shot.episode}:${shot.shot_number}` }, $event)">动作：{{ shot.action }}</span><br><span>台词/旁白：{{ shot.dialogue || '无' }}</span><br><span>情绪：{{ shot.emotion || '自然' }}</span><br><span>声音：{{ shot.sound || '无' }}</span><br><br></template><NarrativeItemActions :disabled="storyboardStatus === 'generating'" :copied="copiedEpisodeKey === `storyboard-${group.episode}`" @delete="deleteStoryboardEpisode(group.episode)" @copy="copyEpisodeText(storyboardEpisodeText(group.shots), `storyboard-${group.episode}`)" @quote="quoteChatText(storyboardEpisodeText(group.shots))" /></p>
          </section>
        </div>
        <div v-else-if="rightPanelMode === 'video'" class="content-preview video-preview">
          <template v-if="activeWorkflowNavigation === '分镜视频'">
            <WorkflowActionBar :running="shotVideoStatus === 'generating'" :primary-label="shotVideos.length ? (shotVideoStatus === 'confirmed' ? '重新生成分镜视频' : '继续生成分镜视频') : '生成分镜视频'" :primary-disabled="!shotImagesReadyForVideo" :next-label="hasMergeableEpisode ? '生成成片' : undefined" @import="importCurrentWorkflow" @primary="generateShotVideos()" @pause="stopShotVideos" @next="generateFinalVideo"><template #status><StatusPulse v-if="shotVideoStatus === 'generating'" class="script-stage-indicator" text="分镜视频、配音、口型和字幕处理中......" /></template></WorkflowActionBar><p v-if="!shotImagesReadyForVideo" class="outline-error">请先完成至少一集的全部分镜画面</p><p v-else-if="mergePrerequisiteMessage && shotVideos.some(item => item.video_url)" class="outline-error">{{ mergePrerequisiteMessage }}</p><p v-if="shotVideoError" class="outline-error">{{ shotVideoError }}</p>
            <div class="shot-video-grid"><article v-for="item in visibleShotVideos" :key="`${item.episode}-${item.shot_number}`" class="shot-video-card"><div class="shot-video-frame"><video v-if="item.video_url" :src="item.video_url" title="点击放大预览" @click.prevent="openGeneratedImage(`shot-video:${item.episode}:${item.shot_number}`)"></video><div v-else class="shot-video-placeholder">{{ item.status === 'generating' ? '生成中' : '待生成' }}</div><strong class="shot-video-title">第{{ item.episode }}集 · 镜头{{ item.shot_number }}</strong><MediaOverlayControls media-type="video" :generating="item.status === 'generating'" :show-play="Boolean(item.video_url)" :can-reference="Boolean(item.video_url)" @intro="assetIntroOpen = assetIntroOpen === `shot-video:${item.episode}:${item.shot_number}` ? '' : `shot-video:${item.episode}:${item.shot_number}`" @import="openShotVideoReplacement(item)" @regenerate="item.status === 'generating' ? stopShotVideos() : retryShotVideo(item)" @play="toggleShotVideoPlayback" @reference="referenceWorkflowMedia(`第${item.episode}集-镜头${item.shot_number}`, item.video_url, 'video')" /><div v-if="assetIntroOpen === `shot-video:${item.episode}:${item.shot_number}`" class="shot-media-intro-panel"><strong>第{{ item.episode }}集 · 镜头{{ item.shot_number }}</strong><p>{{ storyboardShots.find(shot => shot.episode === item.episode && shot.shot_number === item.shot_number)?.visual || '暂无视频简介' }}</p><p>{{ storyboardShots.find(shot => shot.episode === item.episode && shot.shot_number === item.shot_number)?.action || '' }}</p></div></div><small>{{ item.status === 'confirmed' || item.status === 'waiting_confirmation' ? '已生成' : item.status === 'generating' ? '生成中' : item.error ? userFacingGenerationError(item.error) : '待生成' }}</small></article></div>
          </template>
          <template v-else-if="activeWorkflowNavigation === '成片'">
            <WorkflowActionBar :running="mergeStatus === 'generating' || shotVideoStatus === 'generating'" :primary-label="episodeMasters.length ? (mergeStatus === 'confirmed' ? '重新生成成片' : '继续生成成片') : '生成成片'" :primary-disabled="!hasMergeableEpisode" :next-label="episodeMasters.some(item => item.video_url) ? '前往导出' : undefined" @import="importCurrentWorkflow" @primary="mergeEpisodes" @pause="mergeStatus === 'generating' ? stopMerge() : stopShotVideos()" @next="selectWorkflowNavigation('导出')"><template #status><StatusPulse v-if="shotVideoStatus === 'generating'" class="script-stage-indicator" text="配音、口型和字幕处理中......" /><StatusPulse v-else-if="mergeStatus === 'generating'" class="script-stage-indicator" text="成片生成中......" /></template></WorkflowActionBar><p v-if="!hasMergeableEpisode && !episodeMasters.length && shotVideoStatus !== 'generating'" class="outline-error">{{ mergePrerequisiteMessage || '请先完成分镜视频、配音、口型同步和字幕' }}</p><p v-if="shotVideoError" class="outline-error">{{ shotVideoError }}</p><p v-if="mergeError" class="outline-error">{{ mergeError }}</p>
            <div class="shot-video-grid final-video-grid"><article v-for="item in visibleEpisodeMasters" :key="item.episode" class="shot-video-card"><div class="shot-video-frame"><video v-if="item.video_url" :src="item.video_url" title="点击放大预览" @click.prevent="openGeneratedImage(`episode-master:${item.episode}`)"></video><div v-else class="shot-video-placeholder">{{ item.status === 'generating' ? '生成中' : '待生成' }}</div><strong class="shot-video-title">第{{ item.episode }}集 · 基础成片</strong><MediaOverlayControls media-type="video" :generating="item.status === 'generating'" :show-play="Boolean(item.video_url)" :can-reference="Boolean(item.video_url)" @intro="assetIntroOpen = assetIntroOpen === `episode-master:${item.episode}` ? '' : `episode-master:${item.episode}`" @import="importEpisodeMaster(item)" @regenerate="regenerateEpisodeMaster(item)" @play="toggleShotVideoPlayback" @reference="referenceWorkflowMedia(`第${item.episode}集-基础成片`, item.video_url, 'video')" /><div v-if="assetIntroOpen === `episode-master:${item.episode}`" class="shot-media-intro-panel"><strong>第{{ item.episode }}集基础成片</strong><p>由本集全部分镜视频、配音、口型同步和字幕合并生成。</p></div></div><small>{{ item.status === 'confirmed' ? '已确认' : item.status === 'waiting_confirmation' ? '待确认' : item.status === 'generating' ? '生成中' : item.error || '待生成' }}</small></article></div>
          </template>
          <template v-else-if="activeWorkflowNavigation === '导出'">
            <WorkflowActionBar :running="exportStatus === 'generating'" :primary-label="exportStatus === 'confirmed' ? '重新导出' : '导出可用成片'" :primary-disabled="!canCreateExports('all') && !canCreateExports('single') && !canCreateExports('batch')" @import="importCurrentWorkflow" @primary="createAvailableExports" @pause="stopExports"><template #status><StatusPulse v-if="exportStatus === 'generating'" class="script-stage-indicator" text="导出生成中......" /></template><button :disabled="exportStatus === 'generating'" @click="exportSourceVersion = 'base'">基础母版</button><button :disabled="!enhancedEpisodes.some(item => item.status === 'confirmed') || exportStatus === 'generating'" @click="exportSourceVersion = 'enhanced'">增强版</button><button :disabled="!canCreateExports('single')" @click="createExports('single')">导出本集</button><button :disabled="!canCreateExports('batch')" @click="createExports('batch')">导出已确认批次</button><button v-if="exportStatus === 'confirmed'" @click="downloadExportBatch">批量下载</button></WorkflowActionBar><p v-if="exportError" class="outline-error">{{ exportError }}</p>
            <article v-for="file in exportFiles" :key="file.path" class="shot-video-card"><strong>第{{ file.episode }}集 · {{ exportKindLabel(file.kind) }}</strong><a :href="file.url" download>{{ file.filename }}</a></article><a v-if="exportManifestUrl" :href="exportManifestUrl" download>下载交付清单</a>
          </template>
          <p v-else>该阶段将在对应主任务中接入真实产物</p>
        </div>
        <div v-else class="content-preview empty-preview">暂无素材，请生成图片</div>
      </section>
    </main>
    <div v-if="workspaceDialog" class="modal-backdrop compact-backdrop" @click.self="workspaceDialog = ''" @wheel.stop @touchmove.stop>
      <section :class="['workspace-dialog', { 'task-dialog': workspaceDialog === '任务', 'skill-dialog': workspaceDialog === 'Skill' }]" role="dialog" aria-modal="true" :aria-label="workspaceDialog">
        <header><div><h2>{{ workspaceDialog }}</h2><p>{{ workspaceDialog === '任务' ? '查看和安排当前项目任务' : workspaceDialog === 'Skill' ? '管理当前项目可用的 Skill' : '查看当前项目可用工具' }}</p></div><DialogCloseButton @close="workspaceDialog = ''" /></header>
        <div v-if="workspaceDialog === '任务'" class="workspace-dialog-body">
          <div class="dialog-section-title">当前任务</div>
          <div v-if="productionWorkflow" class="task-tree-history"><strong>LangGraph 统一编排 · {{ productionWorkflow.status }}</strong><small>当前 {{ productionWorkflow.current_stage || '未开始' }} · 下一步 {{ productionWorkflow.next_stage || '等待确认' }} · {{ productionWorkflow.decision.action || 'wait' }}</small></div>
          <div v-for="task in runtimeTasks" :key="task.job_id" class="task-tree-history"><strong>{{ task.task_class }} · {{ task.stage }} · {{ task.status }}</strong><small>任务 UUID {{ task.job_id }} · PID {{ task.pid || '未启动' }} · 心跳 {{ task.heartbeat_at ? new Date(task.heartbeat_at).toLocaleString('zh-CN') : '无' }}</small></div>
          <div class="task-tree"><TaskTreeNode v-for="node in taskTreeDemo" :key="node.id" :node="node" /></div>
          <div class="dialog-section-title">历史版本</div>
          <div v-if="productionVersions.length" class="task-tree">
            <div v-for="version in productionVersions" :key="`${version.id}:${version.versioned_at}`" class="task-tree-history">
              <strong>{{ versionDisplayLabel(version) }}</strong>
              <small>{{ versionStatusLabel(version.version_status) }} · {{ new Date(version.versioned_at).toLocaleString('zh-CN') }}</small>
            </div>
          </div>
          <p v-else>暂无历史版本</p>
        </div>
        <div v-else-if="workspaceDialog === 'Skill'" class="workspace-dialog-body skill-dialog-body">
          <nav class="skill-category-list" aria-label="Skill 分类">
            <button v-for="category in skillCategories" :key="category.name" :class="{ active: activeSkillCategory === category.name }" @click="activeSkillCategory = category.name"><span>{{ category.name }}</span><small>{{ category.skills.length }}</small></button>
          </nav>
          <section class="skill-category-content">
            <div class="skill-category-heading"><div><h3>{{ visibleSkillCategory.name }}</h3><p>模型由系统按流程自动配置</p></div></div>
            <div class="skill-list">
              <article v-for="skill in visibleSkillCategory.skills" :key="skill" class="skill-card enabled">
                <div class="skill-card-main"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-material-outline" /></svg><strong>{{ skill }}</strong><small>{{ skillChanging === skill ? '正在配置审核' : `Skill 默认开启 · 审核${auditEnabled(skill) ? '开启' : '关闭'}` }}</small></div>
                <button class="skill-toggle" type="button" role="switch" :aria-checked="auditEnabled(skill)" :aria-label="`${auditEnabled(skill) ? '关闭' : '开启'}${skill}审核`" :disabled="Boolean(skillChanging)" @click="toggleSkillAudit(skill)"><span></span></button>
              </article>
            </div>
            <div class="dialog-section-title">可插拔生产能力</div>
            <div class="skill-list"><article v-for="capability in productionCapabilities" :key="capability.capability" :class="['skill-card', { enabled:capability.enabled }]"><div class="skill-card-main"><strong>{{ capability.capability }}</strong><small>{{ capability.provider_id }} · {{ capability.enabled ? '已启用' : '已停用' }}</small></div></article></div>
            <div class="dialog-section-title">可插拔基础设施</div>
            <div class="skill-list"><article v-for="extension in productionExtensions" :key="extension.extension_point" :class="['skill-card', { enabled:extension.enabled }]"><div class="skill-card-main"><strong>{{ extension.extension_point }}</strong><small>{{ extension.provider_id }} · {{ extension.enabled ? '已启用' : '已停用' }}</small></div></article></div>
          </section>
          </div>
        <div v-else class="workspace-dialog-body">
          <div class="dialog-section-title">可用工具</div>
          <div class="skill-list">
            <button v-for="tool in ['图片上传', '素材归档', '剧本检查', '分镜预览', '视频导出']" :key="tool" @click="notify(`已打开${tool}`)"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-accelerate-outline" /></svg><strong>{{ tool }}</strong><small>打开</small></button>
          </div>
        </div>
      </section>
    </div>
    <div v-if="regenerateTarget" class="regenerate-popover" :style="{ top: `${regeneratePosition.top}px`, left: `${regeneratePosition.left}px` }" role="dialog" aria-label="重新生成图片">
      <input ref="regenerateFileInput" class="file-input" type="file" accept="image/*,video/*" @change="onRegenerateFileChange" />
      <div :class="['regenerate-command', { 'has-reference': regenerateReference }]">
        <button class="regenerate-add" aria-label="选取电脑本地文件" @click="regenerateFileInput?.click()">＋</button>
        <img v-if="regenerateReference" class="regenerate-reference-thumb clickable-preview-image" :src="regenerateReference.url" :alt="regenerateReference.name" role="button" tabindex="0" title="点击放大预览" @click="openPreviewUrl(regenerateReference.url)" @keyup.enter="openPreviewUrl(regenerateReference.url)" />
        <input v-model="regeneratePrompt" autofocus :placeholder="regenerateReference ? regenerateReference.name : '描述你的修改'" @keyup.enter="submitRegenerate" />
        <button class="regenerate-submit" aria-label="提交重新生成" :disabled="!regeneratePrompt.trim() && !regenerateReference" @click="submitRegenerate">↑</button>
      </div>
    </div>
    <div v-if="accountDialog" class="modal-backdrop compact-backdrop" @click.self="accountDialog = ''" @wheel.stop @touchmove.stop>
      <section class="workspace-dialog account-dialog" role="dialog" aria-modal="true" :aria-label="accountDialog">
        <header><div><h2>{{ accountDialog }}</h2><p>账户与工作台设置</p></div><DialogCloseButton @close="accountDialog = ''" /></header>
        <div class="workspace-dialog-body account-dialog-body">
          <template v-if="accountDialog === '剩余用量'">
            <div class="account-summary"><span class="account-avatar">AO</span><div><strong>个人工作台</strong><small>本地部署</small></div></div>
            <div class="usage-card"><div><strong>本月剩余用量</strong><b>未接入</b></div><p>用量服务接通后显示真实数据。</p></div>
          </template>
          <template v-else-if="accountDialog === '显示宠物'">
            <div class="pet-preview"><span>👩🏻‍💻</span><strong>AI 助手宠物</strong><p>显示在工作区右下角，可提示任务进度和异常。</p></div>
            <label class="account-toggle-row"><span><strong>显示宠物</strong><small>在工作区展示助手头像</small></span><input v-model="petVisible" type="checkbox" /></label>
          </template>
          <template v-else-if="accountDialog === '邀请好友'">
            <div class="invite-hero"><strong>邀请朋友加入影序工作台</strong><p>复制专属链接并发送给好友。</p></div>
            <div class="invite-link"><input readonly value="邀请服务尚未接通" /><button @click="copyInviteLink">获取链接</button></div>
          </template>
          <template v-else-if="accountDialog === '设置'">
            <label class="account-toggle-row"><span><strong>桌面通知</strong><small>任务完成或失败时提醒</small></span><input v-model="desktopNotifications" type="checkbox" /></label>
            <label class="account-toggle-row"><span><strong>自动保存</strong><small>持续保存当前工作台状态</small></span><input v-model="autoSave" type="checkbox" /></label>
            <label class="account-select-row"><span><strong>界面主题</strong><small>当前使用浅色主题</small></span><select><option>浅色</option><option>跟随系统</option></select></label>
          </template>
          <template v-else>
            <div class="logout-warning"><svg class="nav-line-icon" aria-hidden="true"><use href="#icon-sync-outline" /></svg><strong>确认退出当前账户？</strong><p>退出后需要重新登录，项目数据仍会保留。</p><div class="logout-inline-actions"><button class="account-secondary" @click="accountDialog = ''">取消</button><button @click="notify('退出登录服务尚未接通')">退出登录</button></div></div>
          </template>
        </div>
      </section>
    </div>
    <div v-if="newProjectOpen" class="modal-backdrop" @click.self="newProjectOpen = false" @wheel.stop @touchmove.stop>
      <section class="new-project-dialog" role="dialog" aria-modal="true" aria-label="新建项目">
        <DialogCloseButton @close="newProjectOpen = false" />
        <div class="dialog-body project-requirements-form">
          <div class="project-form-grid">
            <label>项目名称<input v-model="newProjectName" autofocus placeholder="请输入项目名称" @keyup.enter="saveProject" /></label>
            <label>视觉风格<select v-model="newProjectGenre" :disabled="!localLoraStyles.length" @change="newProjectStyle = newProjectGenre"><option v-for="style in localLoraStyles" :key="style.id" :value="style.id">{{ style.name }}</option></select></label>
            <label v-if="newProjectLoraMode!=='automatic'">LoRA<select v-model="newProjectLoraId"><option value="cn-mythic">中文神话古风</option><option value="cn-romance">中文都市甜宠</option><option value="cn-suspense">中文悬疑电影</option><option value="cn-modern">中文现代写实</option></select></label>
            <label v-if="newProjectLoraMode==='exploration'">探索随机种子<input v-model.number="newProjectLoraSeed" type="number" min="0"></label>
            <label class="full-row">题材<textarea v-model="newProjectPrompt" rows="4"></textarea></label>
            <label>每集时长<div class="duration-range-input"><input v-model.number="newProjectDurationMin" type="number" min="1" aria-label="每集最短时长" /><span>-</span><input v-model.number="newProjectDurationMax" type="number" min="1" aria-label="每集最长时长" /><em>秒</em></div></label>
            <label>是否开启超分<select v-model="newProjectUpscale"><option>不超分</option><option>超分＋降噪</option></select></label>
            <label>集数<div class="unit-input"><input v-model.number="newProjectEpisodes" type="number" min="1" /><span>集</span></div></label>
            <label>内容语言<select v-model="newProjectLanguage"><option>简体中文</option><option>繁体中文</option><option>英文</option></select></label>
            <button type="button" :class="['option-card option-toggle', { active: subtitleExpanded }]" @click="subtitleExpanded = !subtitleExpanded; aiLabelExpanded = false"><strong>字幕</strong><span>{{ subtitleFont }} · {{ subtitleStrokeWidth }}px · 透明度 {{ subtitleOpacity }}%</span><i>{{ subtitleExpanded ? '⌃' : '⌄' }}</i></button>
            <button type="button" :class="['option-card option-toggle', { active: aiLabelExpanded }]" @click="aiLabelExpanded = !aiLabelExpanded; subtitleExpanded = false"><strong>AI 内容标识</strong><span>思源黑体 · 2px · 透明度 100%</span><i>{{ aiLabelExpanded ? '⌃' : '⌄' }}</i></button>
            <div v-if="subtitleExpanded" class="subtitle-settings full-row">
              <div class="subtitle-preview-column">
                <div class="subtitle-preview-image"><strong :style="{ color: subtitleColor, opacity: subtitleOpacity / 100, fontSize: `${subtitleFontSize * 0.49}px`, WebkitTextStroke: `${subtitleStrokeWidth * 0.49}px ${subtitleStrokeColor}` }">{{ subtitlePreviewText }}</strong><span>字幕样式预览</span></div>
                <button type="button" @click="notify('已打开字幕大图预览')">预览</button>
              </div>
              <div class="subtitle-controls">
                <label>字幕预览文案<input v-model="subtitlePreviewText" /></label>
                <label>字幕字体（免费可商用）<select v-model="subtitleFont"><option>思源黑体</option><option>思源宋体</option><option>阿里巴巴普惠体</option></select></label>
                <label>字幕颜色与字号<div class="inline-settings"><input v-model="subtitleColor" type="color" /><code>{{ subtitleColor }}</code><select v-model.number="subtitleFontSize"><option :value="14">小号 14px</option><option :value="16">中号 16px</option><option :value="18">大号 18px</option></select></div><ColorPresetPicker v-model="subtitleColor" :colors="['#FFFFFF', '#DDE3EB', '#FFD36B', '#5AA5F5', '#54D58A', '#17191C']" /></label>
                <label>描边颜色与粗细<div class="inline-settings"><input v-model="subtitleStrokeColor" type="color" /><code>{{ subtitleStrokeColor }}</code><select v-model.number="subtitleStrokeWidth"><option :value="1">1px</option><option :value="2">2px</option><option :value="3">3px</option></select></div><ColorPresetPicker v-model="subtitleStrokeColor" :colors="['#000000', '#FFFFFF', '#DDE3EB', '#FFD36B', '#5AA5F5', '#54D58A']" /></label>
                <label class="opacity-control"><input v-model.number="subtitleOpacity" type="range" min="20" max="100" /><span>文字透明度　<strong>{{ subtitleOpacity }}%</strong></span></label>
              </div>
            </div>
            <div v-if="aiLabelExpanded" class="subtitle-settings ai-label-settings full-row">
              <div class="subtitle-preview-column">
                <div class="subtitle-preview-image"><strong v-if="visibleAiWatermark" class="draggable-watermark" :style="{ left: `${aiWatermarkX}%`, top: `${aiWatermarkY}%`, color: aiWatermarkColor, opacity: aiWatermarkOpacity / 100, fontSize: `${aiWatermarkSize * 0.49}px`, WebkitTextStroke: `${aiWatermarkStrokeWidth * 0.49}px ${aiWatermarkStrokeColor}` }" @pointerdown="startWatermarkDrag">{{ aiWatermarkText }}</strong><span>拖动文字调整位置</span></div>
                <button type="button" @click="notify('已打开 AI 标识大图预览')">预览</button>
              </div>
              <div class="subtitle-controls">
                <label>水印文案<input v-model="aiWatermarkText" /></label>
                <label>字号大小<select v-model.number="aiWatermarkSize"><option :value="10">小号 10px</option><option :value="12">小号 12px</option><option :value="14">中号 14px</option></select></label>
                <label>文字颜色<div class="inline-settings"><input v-model="aiWatermarkColor" type="color" /><code>{{ aiWatermarkColor }}</code></div><ColorPresetPicker v-model="aiWatermarkColor" :colors="['#FFFFFF', '#DDE3EB', '#FFD36B', '#5AA5F5', '#54D58A', '#17191C']" /></label>
                <label>描边颜色与粗细<div class="inline-settings"><input v-model="aiWatermarkStrokeColor" type="color" /><code>{{ aiWatermarkStrokeColor }}</code><select v-model.number="aiWatermarkStrokeWidth"><option :value="0">0px</option><option :value="1">1px</option><option :value="2">2px</option></select></div><ColorPresetPicker v-model="aiWatermarkStrokeColor" :colors="['#000000', '#FFFFFF', '#DDE3EB', '#FFD36B', '#5AA5F5', '#54D58A']" /></label>
                <label class="opacity-control"><input v-model.number="aiWatermarkOpacity" type="range" min="10" max="100" /><span>文字透明度　<strong>{{ aiWatermarkOpacity }}%</strong></span></label>
              </div>
            </div>
          </div>
        </div>
        <footer><button @click="newProjectOpen = false">取消</button><button class="dialog-primary" :disabled="!newProjectName.trim() || !newProjectPrompt.trim() || !localLoraStyles.some(style => style.id === newProjectGenre) || newProjectDurationMin > newProjectDurationMax" @click="saveProject">{{ editingProjectName ? '保存设置' : '创建项目' }}</button></footer>
      </section>
    </div>
    <div v-if="lightboxAsset" class="media-lightbox" role="dialog" aria-modal="true" :aria-label="lightboxAsset.mediaType === 'video' ? '视频放大预览' : '图片放大预览'" @pointerdown.capture="closeLightboxFromPointer" @click="closeLightboxOutsideMedia" @pointerdown.stop @touchmove.stop.prevent @gesturestart.stop.prevent @gesturechange.stop.prevent @gestureend.stop.prevent>
      <button class="lightbox-dismiss-layer" type="button" aria-label="关闭图片预览" @pointerdown.stop.prevent="lightboxIndex = -1" @click.stop.prevent="lightboxIndex = -1"></button>
      <div class="lightbox-stage" :class="{ dragging:lightboxDragging, zoomed:lightboxScale > lightboxFitScale }" @wheel.stop.prevent="zoomLightboxByWheel" @dblclick.stop.prevent="toggleLightboxZoom" @pointerdown="startLightboxDrag" @pointermove="moveLightboxDrag" @pointerup="endLightboxDrag" @pointercancel="endLightboxDrag">
        <button class="lightbox-arrow previous" aria-label="上一张" @click="turnLightbox(-1)">‹</button>
        <img v-if="lightboxAsset.mediaType === 'image'" :src="lightboxAsset.url" :alt="lightboxAsset.name" draggable="false" :style="{ width:`${lightboxNaturalSize.width || 1}px`, height:`${lightboxNaturalSize.height || 1}px`, transform:`translate3d(${lightboxOffset.x}px, ${lightboxOffset.y}px, 0) scale(${lightboxScale})` }" @load="fitLightboxImage" />
        <video v-else :src="lightboxAsset.url" controls autoplay></video>
        <button class="lightbox-arrow next" aria-label="下一张" @click="turnLightbox(1)">›</button>
      </div>
      <div class="lightbox-counter">{{ lightboxIndex + 1 }} / {{ lightboxAssets.length }}</div>
      <div v-if="lightboxAsset.mediaType === 'image'" class="lightbox-zoom-controls" aria-label="图片缩放控制">
        <button type="button" aria-label="缩小" :disabled="lightboxScale <= 0.1" @click="zoomLightbox(-1)">−</button>
        <button type="button" class="lightbox-zoom-value" aria-label="重置为适合窗口" @click="resetLightboxZoom">{{ Math.round(lightboxScale * 100) }}%</button>
        <button type="button" aria-label="放大" :disabled="lightboxScale >= 5" @click="zoomLightbox(1)">＋</button>
      </div>
    </div>
  </div>
</template>
