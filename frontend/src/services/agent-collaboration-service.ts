import type { AgentApiContext } from "./agent-configuration-service";
export interface CollaborationSession { session_id:string; project_id:string; root_task_id:string; developer_agent_id:string; inspector_agent_id:string; status:string; remediation_round:number; max_remediation_rounds:number }
export interface TaskHandoff { handoff_id:string; session_id:string; task_id:string; status:string; handoff_type:string }
export interface InspectionIssue { issue_id:string; title:string; description:string; severity:string; file_reference?:string }
export interface InspectionReport { report_id:string; verdict:string; read_only:true; issues:InspectionIssue[] }
export interface CollaborationCycle { handoff:TaskHandoff; report:InspectionReport; remediation?:{instruction_id:string;remediation_round:number;status:string} }
export class AgentCollaborationService {
  constructor(private context:AgentApiContext, private baseUrl="") {}
  open(input:{project_id:string;root_task_id:string;developer_agent_id:string;inspector_agent_id:string;max_remediation_rounds?:number}) { return this.request<CollaborationSession>("/api/v1/agent-collaborations","POST",input); }
  submit(sessionId:string,input:{task_id:string;context_reference:string;evidence?:unknown[]}) { return this.request<TaskHandoff>(`/api/v1/agent-collaborations/${encodeURIComponent(sessionId)}/handoffs`,"POST",input); }
  inspect(handoffId:string) { return this.request<InspectionReport>(`/api/v1/agent-handoffs/${encodeURIComponent(handoffId)}/inspect`,"POST",{}); }
  remediate(reportId:string) { return this.request(`/api/v1/inspection-reports/${encodeURIComponent(reportId)}/remediation`,"POST",{}); }
  cycle(sessionId:string,input:{task_id:string;context_reference:string;evidence?:unknown[]}) { return this.request<CollaborationCycle>(`/api/v1/agent-collaborations/${encodeURIComponent(sessionId)}/cycles`,"POST",input); }
  state(sessionId:string) { return this.request<CollaborationSession>(`/api/v1/agent-collaborations/${encodeURIComponent(sessionId)}`); }
  private async request<T>(path:string,method="GET",body?:unknown):Promise<T>{ const response=await fetch(this.baseUrl+path,{method,headers:{"Content-Type":"application/json","X-Request-Id":this.context.requestId,"X-Trace-Id":this.context.traceId,"X-Identity-Id":this.context.identityId,"X-Identity-Kind":this.context.identityKind,"X-Tenant-Id":this.context.tenantId},body:body===undefined?undefined:JSON.stringify(body)});const envelope=await response.json() as {data:T;msg:string};if(!response.ok)throw new Error(envelope.msg);return envelope.data; }
}
