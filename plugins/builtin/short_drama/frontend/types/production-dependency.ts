import type { ProductionScopeType, ProductionStage } from "./production";

export type ProductionDependencyNode = {
  stage:ProductionStage;
  scope_type:ProductionScopeType;
  scope_id:string;
};

export type ProductionDependencyImpact = ProductionDependencyNode & {
  source_stage:ProductionStage;
  source_scope_id:string;
  reason:"direct" | "cross_episode_boundary" | "global";
};
