import type { ProductionStage } from "../types/production.ts";
import shortDramaWorkflow from "../../workflows/v1.pipeline.json" with { type:"json" };
import stageRegistrations from "../../workflows/stage.registrations.json" with { type:"json" };

const knownStages = new Set<ProductionStage>([
  "requirements", "outline", "script", "storyboard", "assets", "image",
  "video", "audio", "subtitle", "composition", "review_export",
]);

const configuredStages = shortDramaWorkflow.stages.map((item) => item.stage);
if (configuredStages.length !== knownStages.size || configuredStages.some((stage) => !knownStages.has(stage as ProductionStage))) {
  throw new Error("短剧插件流程配置与 ProductionStage 契约不一致");
}
const registeredStages = stageRegistrations.stages.map(item => item.stage);
if (registeredStages.length !== configuredStages.length || registeredStages.some((stage, index) => stage !== configuredStages[index])) {
  throw new Error("短剧生产阶段未完整登记启动恢复、LangGraph、项目投影和前端继续入口");
}
if (stageRegistrations.stages.some(item => !item.startup_recovery || item.langgraph_stage !== item.stage || !item.project_storage || !item.frontend_continue)) {
  throw new Error("短剧生产阶段登记字段不完整");
}
for (const key of ["langgraph_stage", "project_storage"] as const) {
  const values = stageRegistrations.stages.map(item => item[key]);
  if (new Set(values).size !== values.length) throw new Error(`短剧生产阶段 ${key} 登记必须唯一`);
}

export const productionStageOrder:readonly ProductionStage[] = Object.freeze(configuredStages as ProductionStage[]);
export const productionStageRegistrations = Object.freeze(stageRegistrations.stages);

export type AutomaticTransitionContext = {
  intended:boolean;
  targetConfirmed:boolean;
  prerequisiteConfirmed:boolean;
  contentRemaining?:boolean;
  requirementReady?:boolean;
  upscaleEnabled?:boolean;
  reviewConfirmed?:boolean;
  upscaleConfirmed?:boolean;
};

export function nextProductionStage(target:ProductionStage, _upscaleEnabled:boolean):ProductionStage | null {
  const index = productionStageOrder.indexOf(target);
  return index >= 0 && index < productionStageOrder.length - 1 ? productionStageOrder[index + 1] : null;
}

export function isAutomaticTransitionReady(target:ProductionStage, context:AutomaticTransitionContext) {
  if (!context.intended || context.targetConfirmed) return false;
  if (target === "outline") return Boolean(context.requirementReady);
  if (target === "script" || target === "storyboard") return context.prerequisiteConfirmed && Boolean(context.contentRemaining);
  if (["assets", "image", "video", "audio", "subtitle", "composition"].includes(target)) return context.prerequisiteConfirmed;
  if (target === "review_export") return Boolean(context.reviewConfirmed) && (!context.upscaleEnabled || Boolean(context.upscaleConfirmed));
  return false;
}
