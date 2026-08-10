import type { ProductionDependencyImpact, ProductionDependencyNode } from "../types/production-dependency";
import { productionStageOrder } from "./production-flow.ts";

function stageScope(stage:ProductionDependencyNode["stage"], episode:string, original:ProductionDependencyNode):Pick<ProductionDependencyNode, "scope_type" | "scope_id"> {
  if (stage === "characters") return { scope_type:"asset", scope_id:episode === "*" ? "*" : `episode:${episode}` };
  if (stage === "shots" || stage === "video") {
    if (original.scope_type === "shot" && original.scope_id.includes("-")) return { scope_type:"shot", scope_id:original.scope_id };
    return { scope_type:"shot", scope_id:episode === "*" ? "*" : `${episode}-*` };
  }
  if (stage === "export" && episode === "*") return { scope_type:"project", scope_id:"project" };
  return { scope_type:episode === "*" ? "project" : "episode", scope_id:episode === "*" ? "project" : episode };
}

export function calculateProductionImpacts(source:ProductionDependencyNode, episodeCount:number):ProductionDependencyImpact[] {
  const sourceIndex = productionStageOrder.indexOf(source.stage);
  if (sourceIndex < 0) return [];
  const total = Math.max(1, Math.floor(episodeCount));
  const sourceEpisode = source.scope_type === "episode" ? Number(source.scope_id)
    : source.scope_type === "shot" ? Number(source.scope_id.split("-")[0])
    : NaN;
  const global = source.scope_type === "project" || !Number.isInteger(sourceEpisode) || sourceEpisode < 1;
  const episodeIds = global ? ["*"] : [String(sourceEpisode)];
  if (!global && ["outline", "script", "storyboard"].includes(source.stage) && sourceEpisode < total) episodeIds.push(String(sourceEpisode + 1));
  const impacts:ProductionDependencyImpact[] = [];
  for (const stage of productionStageOrder.slice(sourceIndex + 1)) {
    for (const episode of episodeIds) {
      const scope = stageScope(stage, episode, source);
      impacts.push({
        stage,
        ...scope,
        source_stage:source.stage,
        source_scope_id:source.scope_id,
        reason:global ? "global" : episode === String(sourceEpisode) ? "direct" : "cross_episode_boundary",
      });
    }
  }
  return impacts.filter((impact, index, all) => all.findIndex(item => item.stage === impact.stage && item.scope_type === impact.scope_type && item.scope_id === impact.scope_id) === index);
}
