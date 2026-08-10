import { reactive } from "vue";

export type AssetStatus = "pending" | "generating" | "waiting_confirmation" | "confirmed" | "failed";
export type AssetVariant = { id:string; label:string; prompt:string; image_url?:string; production_evidence?:string; status:AssetStatus; audit_summary?:string; error?:string };
export type Asset3DRender = { label:string; angle:number; url:string; mask_url?:string; depth_url?:string; normal_url?:string; channels?:string[] };
export type Asset3DResult = { job_id:string; status:"pending_confirmation" | "completed"; reference_url:string; model_url:string; blend_url:string; report_url:string; source_video_url?:string; renders:Asset3DRender[]; vertex_count?:number; face_count?:number; workflow:string; identity_policy:string; candidate_path?:string; archive_path?:string; archive_version?:string; metadata_path?:string; confirmed_at?:string };
type ConfirmableAsset = { status?:AssetStatus; image_url?:string; detail_image_urls?:string[]; detail_generation_evidence?:string[]; detail_assets?:AssetVariant[]; confirmation_phase?:"baseline" | "details"; baseline_confirmed_at?:string; generation_nonce?:string; error?:string; upload_view_mode?:"standard" | "single"; view_contract?:string; model3d_status?:AssetStatus; model3d_job_id?:string; model3d_error?:string; model3d_result?:Asset3DResult };
export type CharacterProfile = ConfirmableAsset & { name:string; role:string; gender:string; age:string; appearance:string; hair:string; makeup:string; costume:string; temperament:string; expression:string; identity_keywords:string[]; image_prompt:string; character_lora_id?:string; character_lora_path?:string; character_lora_sha256?:string; character_lora_base_model?:string; clothing_reference_url?:string; voice_reference_url?:string; voice_status?:"pending" | "confirmed" };
export type SceneProfile = ConfirmableAsset & { name:string; location:string; period:string; first_episode:number; episodes:number[]; layout:string; lighting:string; fixed_elements:string[]; continuity_rules:string; image_prompt:string };
export type PropProfile = ConfirmableAsset & { name:string; category:string; owner:string; first_episode:number; episodes:number[]; appearance:string; continuity_rules:string; image_prompt:string; asset_type?:"prop"|"costume"; costume_id?:string; costume_version?:string; tags?:string[] };
export type ShotImageItem = { episode:number; shot_number:number; image_url?:string; prompt_override?:string; status:AssetStatus; audit_summary?:string; error?:string; repair_count:number; workflow_version?:string };
export type ShotVideoItem = { episode:number; shot_number:number; video_url?:string; source_video_url?:string; path?:string; audio_url?:string; speaker?:string; voice_preset?:string; voice_cast_version?:string; lip_sync_version?:string; emotion?:string; lip_sync_model?:"LatentSync-1.6" | "MuseTalk"; voice_status?:"pending" | "completed" | "not_applicable" | "failed"; lip_sync_status?:"pending" | "completed" | "not_applicable" | "failed"; subtitle_status?:"pending" | "completed" | "not_applicable" | "failed"; audit_evidence?:{ speaker:string; emotion:string; lipsync:string; face:string; continuity?:string }; status:AssetStatus; error?:string };
export type EpisodeMaster = { episode:number; video_url?:string; path?:string; clean_path?:string; production_evidence?:string; status:AssetStatus; error?:string };
export type EpisodeAudit = { episode:number; status:"pass" | "needs_fix"; issues:string[]; attempts:number; confirmed:boolean };
export type EnhancedEpisode = { episode:number; video_url?:string; path?:string; production_evidence?:string; status:AssetStatus | "skipped"; error?:string };
export type ExportFile = { episode:number; kind:string; filename:string; path:string; url:string };

export type AssetStoreSnapshot = {
  characterProfiles:CharacterProfile[]; sceneProfiles:SceneProfile[]; propProfiles:PropProfile[];
  assetStatus:AssetStatus; assetError:string;
  shotImages:ShotImageItem[]; shotImageStatus:AssetStatus; shotImageError:string;
  shotVideos:ShotVideoItem[]; shotVideoStatus:AssetStatus; shotVideoError:string;
  episodeMasters:EpisodeMaster[]; mergeStatus:AssetStatus; mergeError:string;
  episodeAudits:EpisodeAudit[]; finalAuditStatus:AssetStatus; finalAuditError:string;
  enhancedEpisodes:EnhancedEpisode[]; upscaleStatus:AssetStatus | "skipped"; upscaleError:string;
  exportFiles:ExportFile[]; exportManifestUrl:string; exportStatus:AssetStatus; exportError:string;
};

const emptySnapshot = ():AssetStoreSnapshot => ({
  characterProfiles:[], sceneProfiles:[], propProfiles:[], assetStatus:"pending", assetError:"",
  shotImages:[], shotImageStatus:"pending", shotImageError:"",
  shotVideos:[], shotVideoStatus:"pending", shotVideoError:"",
  episodeMasters:[], mergeStatus:"pending", mergeError:"",
  episodeAudits:[], finalAuditStatus:"pending", finalAuditError:"",
  enhancedEpisodes:[], upscaleStatus:"pending", upscaleError:"",
  exportFiles:[], exportManifestUrl:"", exportStatus:"pending", exportError:"",
});

function clone<T>(value:T):T { return JSON.parse(JSON.stringify(value)) as T; }

export function createAssetStore(seed:Partial<AssetStoreSnapshot> = {}) {
  const state = reactive({ ...emptySnapshot(), ...clone(seed) }) as AssetStoreSnapshot;

  function replace(snapshot:Partial<AssetStoreSnapshot>) {
    for (const key of Object.keys(emptySnapshot()) as Array<keyof AssetStoreSnapshot>) {
      if (!(key in snapshot)) continue;
      const value = snapshot[key];
      if (Array.isArray(value)) (state[key] as unknown[]) = clone(value);
      else if (value !== undefined) (state as unknown as Record<string, unknown>)[key] = value;
    }
  }

  function reset(seedOverride:Partial<AssetStoreSnapshot> = {}) { replace({ ...emptySnapshot(), ...seedOverride }); }
  function snapshot():AssetStoreSnapshot { return clone(state); }

  return { state, replace, reset, snapshot };
}

export type AssetStore = ReturnType<typeof createAssetStore>;
