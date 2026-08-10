export const workflowNavigation = ["大纲", "剧本", "分镜脚本", "资产", "分镜画面", "分镜视频", "成片", "导出"] as const;

export type WorkflowNavigation = typeof workflowNavigation[number];

export interface UiPreferences {
  activeWorkflow: WorkflowNavigation;
  sidebarCollapsed: boolean;
  previewCollapsed: boolean;
  publicResourcesExpanded: boolean;
  projectResourcesExpanded: boolean;
}
