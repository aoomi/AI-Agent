import type { InjectionKey } from "vue";
import { createNarrativeStore } from "./stores/narrative.store";
import { createProductionStore } from "./stores/production.store";
import { createProjectStore } from "./stores/project.store";
import { createAssetStore } from "./stores/asset.store";
import { createUiStore } from "./stores/ui.store";
import { productionStageOrder } from "./utils/production-flow";

export function createAppRuntime() {
  const projectStore = createProjectStore([], "");
  const productionStore = createProductionStore();
  const narrativeStore = createNarrativeStore({
    outlineGeneral:"", outlinePlan:null, outlineEpisodes:[], scriptSections:[], storyboardShots:[],
    scriptSourceKey:"", storyboardSourceKey:"", narrativeAudits:[], stageAuditChanges:[], narrativeStageTimings:{},
  });
  const assetStore = createAssetStore();
  const uiStore = createUiStore();
  return { projectStore, productionStore, narrativeStore, assetStore, uiStore, productionStageOrder };
}

export type AppRuntime = ReturnType<typeof createAppRuntime>;
export const appRuntimeKey:InjectionKey<AppRuntime> = Symbol("drama-app-runtime");
