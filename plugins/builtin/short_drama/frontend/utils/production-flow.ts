import type { ProductionStage } from "../types/production.ts";
import shortDramaWorkflow from "../../workflows/v1.pipeline.json" with { type:"json" };

const knownStages = new Set<ProductionStage>([
  "requirements", "outline", "script", "storyboard", "assets", "image",
  "video", "audio", "subtitle", "composition", "review_export",
]);

const configuredStages = shortDramaWorkflow.stages.map((item) => item.stage);
if (configuredStages.length !== knownStages.size || configuredStages.some((stage) => !knownStages.has(stage as ProductionStage))) {
  throw new Error("短剧插件流程配置与 ProductionStage 契约不一致");
}

export const productionStageOrder:readonly ProductionStage[] = Object.freeze(configuredStages as ProductionStage[]);

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
