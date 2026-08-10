import { reactive } from "vue";
import type { NarrativeStageTiming } from "../utils/narrative-timing.ts";

export type NarrativeStage = "outline" | "script" | "storyboard";
export type EpisodeOutline = { episode:number; title:string; synopsis:string };
export type OutlineCharacter = { name:string; identity:string; personality:string; core_motivation:string; appearance_count?:number; role?:string; goal?:string; conflict?:string; arc?:string };
export type OutlinePlan = { title?:string; general_outline:string; characters?:OutlineCharacter[]; arcs?:unknown[] };
export type ScriptSection = { title:string; type:string; content:string; durationMs?:number };
export type StoryboardCharacterCostume = {
  id:string; costume_id:string; costume_version:string; action?:string;
  change_type?:"initial"|"continue"|"change";
};
export type StoryboardShot = {
  episode:number; shot_number:number; start_second:number; end_second:number;
  scene:string; shot_size:string; camera:string; visual:string; action:string;
  dialogue:string; sound:string; emotion?:string; image_prompt:string;
  shot_type?:"reaction"|"action"|"dialog"|"atmosphere"|"performance";
  characters?:StoryboardCharacterCostume[];
  tts_real_duration?:number;
  render_chunks?:Array<{chunk_id:string; duration:number; overlap_seconds:number}>;
};
export type NarrativeAuditIssue = { severity:"low"|"medium"|"high"; category:string; location:string; description:string; suggestion:string };
export type NarrativeAuditChange = { id:string; title:string; location:string; originalText:string; revisedText:string };
export type NarrativeAuditRecord = {
  id:string; stage:NarrativeStage; range:string; status:"pass"|"needs_fix";
  model:string; escalated:boolean; complexityScore:number; summary:string;
  continuityScore:number; logicScore:number; fidelityScore:number; issues:NarrativeAuditIssue[]; auditedAt:string;
  firstIssues?:NarrativeAuditIssue[]; finalIssues?:NarrativeAuditIssue[];
  firstChanges?:NarrativeAuditChange[]; finalChanges?:NarrativeAuditChange[];
  firstAuditDurationMs?:number; finalAuditDurationMs?:number;
};
export type StageAuditChange<TStage extends string = string> = {
  id:string; stage:TStage; phase:"首次审核"|"最终审核"; location:string; errorType:string;
  original:string; revised:string; reason:string; modified:boolean; createdAt:string;
};

export type NarrativeStoreSeed<TStage extends string = string> = {
  outlineGeneral:string;
  outlinePlan:OutlinePlan | null;
  outlineEpisodes:EpisodeOutline[];
  scriptSections:ScriptSection[];
  storyboardShots:StoryboardShot[];
  scriptSourceKey:string;
  storyboardSourceKey:string;
  narrativeAudits:NarrativeAuditRecord[];
  stageAuditChanges:StageAuditChange<TStage>[];
  narrativeStageTimings:Partial<Record<NarrativeStage, NarrativeStageTiming>>;
};

export function createNarrativeStore<TStage extends string = string>(seed:NarrativeStoreSeed<TStage>) {
  const state = reactive({
    outlineGeneral:seed.outlineGeneral,
    outlinePlan:seed.outlinePlan,
    outlineEpisodes:[...seed.outlineEpisodes],
    scriptSections:[...seed.scriptSections],
    storyboardShots:[...seed.storyboardShots],
    scriptSourceKey:seed.scriptSourceKey,
    storyboardSourceKey:seed.storyboardSourceKey,
    narrativeAudits:[...seed.narrativeAudits],
    stageAuditChanges:[...seed.stageAuditChanges],
    narrativeStageTimings:{ ...seed.narrativeStageTimings },
  }) as NarrativeStoreSeed<TStage>;

  function replace(snapshot:Partial<NarrativeStoreSeed<TStage>>) {
    if (typeof snapshot.outlineGeneral === "string") state.outlineGeneral = snapshot.outlineGeneral;
    if (snapshot.outlinePlan === null || snapshot.outlinePlan?.general_outline) state.outlinePlan = snapshot.outlinePlan;
    if (Array.isArray(snapshot.outlineEpisodes)) state.outlineEpisodes = [...snapshot.outlineEpisodes];
    if (Array.isArray(snapshot.scriptSections)) state.scriptSections.splice(0, state.scriptSections.length, ...snapshot.scriptSections);
    if (Array.isArray(snapshot.storyboardShots)) state.storyboardShots = [...snapshot.storyboardShots];
    if (typeof snapshot.scriptSourceKey === "string") state.scriptSourceKey = snapshot.scriptSourceKey;
    if (typeof snapshot.storyboardSourceKey === "string") state.storyboardSourceKey = snapshot.storyboardSourceKey;
    if (Array.isArray(snapshot.narrativeAudits)) state.narrativeAudits = [...snapshot.narrativeAudits];
    if (Array.isArray(snapshot.stageAuditChanges)) state.stageAuditChanges = [...snapshot.stageAuditChanges];
    if (snapshot.narrativeStageTimings) {
      Object.keys(state.narrativeStageTimings).forEach(key => delete state.narrativeStageTimings[key as NarrativeStage]);
      Object.assign(state.narrativeStageTimings, snapshot.narrativeStageTimings);
    }
  }

  function reset(seedOverride:Partial<NarrativeStoreSeed<TStage>> = {}) {
    replace({
      outlineGeneral:"",
      outlinePlan:null,
      outlineEpisodes:[],
      scriptSections:[],
      storyboardShots:[],
      scriptSourceKey:"",
      storyboardSourceKey:"",
      narrativeAudits:[],
      stageAuditChanges:[],
      narrativeStageTimings:{},
      ...seedOverride,
    });
  }

  function snapshot():NarrativeStoreSeed<TStage> {
    return {
      outlineGeneral:state.outlineGeneral,
      outlinePlan:state.outlinePlan ? { ...state.outlinePlan } : null,
      outlineEpisodes:state.outlineEpisodes.map(item => ({ ...item })),
      scriptSections:state.scriptSections.map(item => ({ ...item })),
      storyboardShots:state.storyboardShots.map(item => ({ ...item, characters:item.characters?.map(character => ({ ...character })), render_chunks:item.render_chunks?.map(chunk => ({ ...chunk })) })),
      scriptSourceKey:state.scriptSourceKey,
      storyboardSourceKey:state.storyboardSourceKey,
      narrativeAudits:state.narrativeAudits.map(item => ({ ...item })),
      stageAuditChanges:state.stageAuditChanges.map(item => ({ ...item })),
      narrativeStageTimings:{ ...state.narrativeStageTimings },
    };
  }

  return { state, replace, reset, snapshot };
}

export type NarrativeStore = ReturnType<typeof createNarrativeStore>;
