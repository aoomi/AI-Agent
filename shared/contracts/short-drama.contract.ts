export const shortDramaNodeTypes = [
  "requirements", "outline", "script", "storyboard", "assets", "image",
  "video", "audio", "subtitle", "composition", "review_export",
] as const;
export type ShortDramaNodeType = typeof shortDramaNodeTypes[number];

export const shortDramaRunStatuses = [
  "pending", "running", "waiting_human", "completed", "failed", "cancelled",
] as const;
export type ShortDramaRunStatus = typeof shortDramaRunStatuses[number];
export const shortDramaProductionFrameRate = 30 as const;
export const shortDramaStageAliases = {
  requirement:"requirements", characters:"assets", shots:"image", shot_images:"image",
  shot_videos:"video", merge:"composition", merged_episodes:"composition",
  review:"review_export", final_audit:"review_export", upscale:"review_export", export:"review_export",
} as const;
export type ShortDramaLegacyStage = keyof typeof shortDramaStageAliases;
export const shortDramaNodeDependencies: Record<ShortDramaNodeType, readonly ShortDramaNodeType[]> = {
  requirements: [], outline:["requirements"], script:["outline"], storyboard:["script"], assets:["storyboard"], image:["assets"], video:["image"], audio:["video"], subtitle:["audio"], composition:["video","audio","subtitle"], review_export:["composition"],
};
export const shortDramaNodeExecutionStatuses=["pending","running","waiting_human","completed","failed","cancelled"]as const;
export interface ShortDramaNodeExecution{node_type:ShortDramaNodeType;status:typeof shortDramaNodeExecutionStatuses[number];dependencies:ShortDramaNodeType[];input_artifact_ids:string[];output_artifact_ids:string[];attempt:number;max_attempts:number;error_code:string|null}
export interface ShortDramaLangGraphCheckpoint{checkpoint_id:string;thread_id:string;run_id:string;current_nodes:ShortDramaNodeType[];next_nodes:ShortDramaNodeType[];node_executions:ShortDramaNodeExecution[];created_at:string;updated_at:string;contract_version:"1.0"}
export const shortDramaLoraModes=["automatic","fixed","manual","exploration"]as const;
export interface ShortDramaLoraSelection{mode:typeof shortDramaLoraModes[number];drama_genre:string;selected_lora_id:string;selected_lora_version:string;locked:boolean;match_reason:string;exploration_seed:number|null;contract_version:"1.0"}

export interface ShortDramaArtifactReference {
  artifact_id: string;
  artifact_version: number;
  node_type: ShortDramaNodeType;
  storage_key: string;
  media_type: string;
  checksum_sha256: string;
}

export interface ShortDramaPipelineRun {
  run_id: string;
  tenant_id: string;
  project_id: string;
  task_id: string;
  operation_key: string;
  status: ShortDramaRunStatus;
  current_node: ShortDramaNodeType;
  completed_nodes: ShortDramaNodeType[];
  artifacts: ShortDramaArtifactReference[];
  contract_version: "1.0";
}
