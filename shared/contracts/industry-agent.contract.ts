import type{ContractVersion,Identifier,IsoTimestamp,JsonValue}from"./domain.contract";
export interface IndustryDefinitionContract{industry_id:Identifier;display_name:string;template_version:string;metadata:Record<string,JsonValue>;contract_version:ContractVersion}
export interface BusinessProcessContract{process_id:Identifier;industry_id:Identifier;display_name:string;input_schema:Record<string,JsonValue>;output_schema:Record<string,JsonValue>;contract_version:ContractVersion}
export interface ProcessSkillContract{skill_id:Identifier;process_id:Identifier;manifest_version:string;required_capabilities:string[];permissions:string[];entrypoint:string;contract_version:ContractVersion}
export interface ProcessRobotContract{robot_id:Identifier;skill_id:Identifier;tenant_id:Identifier;project_id:Identifier;model_id:Identifier;configuration_version:number;status:"idle"|"loading"|"running"|"waiting_human"|"completed"|"failed";created_at:IsoTimestamp;contract_version:ContractVersion}
export interface WorkflowTopologyEdgeContract{source_robot_id:Identifier;target_robot_id:Identifier;condition:string|null}
export interface IndustryWorkflowContract{workflow_id:Identifier;industry_id:Identifier;robot_ids:Identifier[];edges:WorkflowTopologyEdgeContract[];mode:"serial"|"parallel"|"branching";configuration_version:number;contract_version:ContractVersion}
