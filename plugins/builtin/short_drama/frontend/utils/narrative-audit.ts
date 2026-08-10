type AuditIssueLike = { location:string; description:string };
type AuditRecordLike = {
  id:string;
  stage:"outline" | "script" | "storyboard";
  status:"pass" | "needs_fix";
  auditedAt:string;
  firstIssues?:AuditIssueLike[];
  finalIssues?:AuditIssueLike[];
  firstChanges?:unknown[];
  finalChanges?:unknown[];
};

export function selectNarrativeAuditRecords<T extends AuditRecordLike>(records:readonly T[], target:T["stage"], totalEpisodes:number) {
  const stageRecords = records.filter(item => item.stage === target);
  const fullRecord = stageRecords.find(item => item.id === `${target}-1-${totalEpisodes}-global`)
    || stageRecords.find(item => item.id === `${target}-1-${totalEpisodes}`);
  return fullRecord ? [fullRecord] : stageRecords;
}

export function narrativeAuditCompleted<T extends AuditRecordLike>(records:readonly T[], target:T["stage"], totalEpisodes:number) {
  const selected = new Map(records.filter(item => item.stage === target).map(record => [record.id, record]));
  const record = selected.get(`${target}-1-${totalEpisodes}-global`) || selected.get(`${target}-1-${totalEpisodes}`);
  return Boolean(record && Array.isArray(record.firstIssues) && Array.isArray(record.finalIssues) && record.auditedAt);
}

export function narrativeAuditPassed(records:readonly AuditRecordLike[]) {
  return records.length > 0 && records.every(item => item.status === "pass");
}

export function narrativeAuditModificationCount(records:readonly AuditRecordLike[]) {
  return records.reduce((total, record) => total + (record.firstChanges?.length || 0) + (record.finalChanges?.length || 0), 0);
}

export function conciseAuditLocations(issues:readonly AuditIssueLike[]) {
  const values = [...new Set(issues.map(item => String(item.location || item.description || "").trim()).filter(Boolean))];
  return values.length ? values.slice(0, 8).join("、") + (values.length > 8 ? `等${values.length}处` : "") : "未发现需要改动的位置";
}

export function auditIssueAffectsEpisode(issue:AuditIssueLike, episodeNumber:number) {
  const location = String(issue.location || "");
  const ranges = [...location.matchAll(/第?\s*(\d+)\s*(?:[-–—~至到]\s*(\d+)\s*)?集/g)];
  return ranges.some(match => {
    const start = Number(match[1]);
    const end = Number(match[2] || match[1]);
    return episodeNumber >= Math.min(start, end) && episodeNumber <= Math.max(start, end);
  });
}
