export type ResumeStage = "outline" | "script" | "storyboard" | "assets" | "shot_images" | "shot_videos" | "merged_episodes" | "final_audit" | "upscale" | "export";

export function createProjectLoadIsolation() {
  let current = { projectId:"", session:-1, stages:new Set<ResumeStage>() };
  return {
    begin(projectId:string, session:number) {
      current = { projectId, session, stages:new Set<ResumeStage>() };
    },
    clear() {
      current = { projectId:"", session:-1, stages:new Set<ResumeStage>() };
    },
    mark(projectId:string, session:number, stage:ResumeStage, enabled:boolean) {
      if (current.projectId !== projectId || current.session !== session) return false;
      if (enabled) current.stages.add(stage);
      else current.stages.delete(stage);
      return true;
    },
    consume(projectId:string, session:number) {
      if (current.projectId !== projectId || current.session !== session) return [] as ResumeStage[];
      const stages = [...current.stages];
      current.stages.clear();
      return stages;
    },
  };
}

export function createProjectScopedCache<T>() {
  const values = new Map<string, T[]>();
  return {
    switchProject(currentProjectId:string, currentItems:T[], nextProjectId:string) {
      if (currentProjectId) values.set(currentProjectId, [...currentItems]);
      return nextProjectId ? [...(values.get(nextProjectId) || [])] : [];
    },
    replace(projectId:string, items:T[]) {
      if (projectId) values.set(projectId, [...items]);
    },
  };
}
