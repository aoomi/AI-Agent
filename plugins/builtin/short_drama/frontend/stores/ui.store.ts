import { reactive } from "vue";

export type WorkflowNavigation = "大纲" | "剧本" | "分镜脚本" | "资产" | "分镜画面" | "分镜视频" | "成片" | "导出";
export type RightPanelMode = "images" | "outline" | "script" | "storyboard" | "assets" | "video" | "empty";
export type UiStoreSnapshot = {
  selectedNode:string; selectedEpisode:string; activeTab:string; input:string; page:number; selectedImage:number;
  rightPanelTitle:string; rightPanelMode:RightPanelMode; previewCollapsed:boolean;
  activeWorkflowNavigation:WorkflowNavigation; workflowEpisode:number;
  workflowPersonAsset:string; workflowPropAsset:string; workflowSceneAsset:string;
  publicResourcesExpanded:boolean; projectResourcesExpanded:boolean;
};

const workflowNavigation:readonly WorkflowNavigation[] = ["大纲", "剧本", "分镜脚本", "资产", "分镜画面", "分镜视频", "成片", "导出"];
const panelModes:readonly RightPanelMode[] = ["images", "outline", "script", "storyboard", "assets", "video", "empty"];
const defaults = ():UiStoreSnapshot => ({
  selectedNode:"人物定妆公共", selectedEpisode:"第03集", activeTab:"", input:"", page:1, selectedImage:1,
  rightPanelTitle:"暂无项目", rightPanelMode:"images", previewCollapsed:false,
  activeWorkflowNavigation:"分镜画面", workflowEpisode:0,
  workflowPersonAsset:"人物", workflowPropAsset:"道具", workflowSceneAsset:"场景",
  publicResourcesExpanded:true, projectResourcesExpanded:true,
});

export function createUiStore(seed:Partial<UiStoreSnapshot> = {}) {
  const state = reactive(defaults()) as UiStoreSnapshot;
  function replace(snapshot:Partial<UiStoreSnapshot>) {
    const fallback = defaults();
    state.selectedNode = typeof snapshot.selectedNode === "string" ? snapshot.selectedNode : state.selectedNode;
    state.selectedEpisode = typeof snapshot.selectedEpisode === "string" ? snapshot.selectedEpisode : state.selectedEpisode;
    state.activeTab = typeof snapshot.activeTab === "string" ? snapshot.activeTab : state.activeTab;
    state.input = typeof snapshot.input === "string" ? snapshot.input : state.input;
    state.page = Number.isInteger(snapshot.page) && Number(snapshot.page) > 0 ? Number(snapshot.page) : state.page;
    state.selectedImage = Number.isInteger(snapshot.selectedImage) && Number(snapshot.selectedImage) > 0 ? Number(snapshot.selectedImage) : state.selectedImage;
    state.rightPanelTitle = typeof snapshot.rightPanelTitle === "string" ? snapshot.rightPanelTitle : state.rightPanelTitle;
    state.rightPanelMode = panelModes.includes(snapshot.rightPanelMode as RightPanelMode) ? snapshot.rightPanelMode as RightPanelMode : state.rightPanelMode;
    state.previewCollapsed = typeof snapshot.previewCollapsed === "boolean" ? snapshot.previewCollapsed : state.previewCollapsed;
    state.activeWorkflowNavigation = workflowNavigation.includes(snapshot.activeWorkflowNavigation as WorkflowNavigation) ? snapshot.activeWorkflowNavigation as WorkflowNavigation : state.activeWorkflowNavigation;
    state.workflowEpisode = Number.isInteger(snapshot.workflowEpisode) && Number(snapshot.workflowEpisode) >= 0 ? Number(snapshot.workflowEpisode) : state.workflowEpisode;
    state.workflowPersonAsset = typeof snapshot.workflowPersonAsset === "string" ? snapshot.workflowPersonAsset : state.workflowPersonAsset;
    state.workflowPropAsset = typeof snapshot.workflowPropAsset === "string" ? snapshot.workflowPropAsset : state.workflowPropAsset;
    state.workflowSceneAsset = typeof snapshot.workflowSceneAsset === "string" ? snapshot.workflowSceneAsset : state.workflowSceneAsset;
    state.publicResourcesExpanded = typeof snapshot.publicResourcesExpanded === "boolean" ? snapshot.publicResourcesExpanded : state.publicResourcesExpanded;
    state.projectResourcesExpanded = typeof snapshot.projectResourcesExpanded === "boolean" ? snapshot.projectResourcesExpanded : state.projectResourcesExpanded;
    return state;
  }
  function reset() { Object.assign(state, defaults()); }
  function snapshot():UiStoreSnapshot { return { ...state }; }
  replace(seed);
  return { state, replace, reset, snapshot };
}

export type UiStore = ReturnType<typeof createUiStore>;
