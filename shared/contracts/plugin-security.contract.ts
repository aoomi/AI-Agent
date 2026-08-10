import type{ContractVersion,Identifier,IsoTimestamp}from"./domain.contract";
export const pluginSourceKinds=["builtin","marketplace","repository","private_upload"]as const;export type PluginSourceKind=typeof pluginSourceKinds[number];
export interface PluginSignatureContract{algorithm:"ed25519"|"rsa-pss-sha256";key_id:Identifier;signature_base64:string;signed_at:IsoTimestamp;manifest_sha256:string}
export interface PluginSourceContract{kind:PluginSourceKind;uri:string;publisher_id:Identifier;retrieved_at:IsoTimestamp;commit_sha?:string}
export interface SbomComponentContract{name:string;version:string;package_url:string;sha256:string;licenses:string[];dependencies:string[]}
export interface PluginSecurityManifestContract{plugin_id:Identifier;plugin_version:string;package_sha256:string;signature:PluginSignatureContract;source:PluginSourceContract;sbom_format:"CycloneDX-1.5";components:SbomComponentContract[];minimum_platform_version:string;generated_at:IsoTimestamp;contract_version:ContractVersion}
