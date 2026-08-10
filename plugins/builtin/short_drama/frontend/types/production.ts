export type ProductionStatus =
  | "idle"
  | "queued"
  | "running"
  | "auditing"
  | "repairing"
  | "rechecking"
  | "pending_confirmation"
  | "completed"
  | "paused"
  | "cancelled"
  | "failed"
  | "stale"
  | "skipped";

export type ProductionStage =
  | "requirements"
  | "outline"
  | "script"
  | "storyboard"
  | "assets"
  | "image"
  | "video"
  | "audio"
  | "subtitle"
  | "composition"
  | "review_export";

export type ProductionScopeType = "project" | "story_arc_batch" | "episode_batch" | "episode" | "scene" | "shot" | "line" | "asset";

export type ProductionScopeRecord = {
  project_id:string;
  stage:ProductionStage;
  scope_type:ProductionScopeType;
  scope_id:string;
  content_fingerprint:string;
  audit_batch_id:string;
  status:ProductionStatus;
  completed_count:number;
  total_count:number;
  confirmation_scope:{ scope_type:ProductionScopeType; scope_ids:string[] };
  impact_scope:Array<{ stage:ProductionStage; scope_type:ProductionScopeType; scope_id:string }>;
  checkpoint:string;
  error:string;
  created_at:string;
  updated_at:string;
};

export type AggregatedProductionStatus = "idle" | "running" | "pending_confirmation" | "completed" | "paused" | "failed" | "stale";
