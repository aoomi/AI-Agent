import { postJson, requestJsonOk } from "./api-client";

export type ResourceScope = "tenant_global" | "project" | "project_episode";
export type StoredResource = {
  id:string; tenant_id:string; user_id:string; plugin_key:string; scope:ResourceScope; project_id:string; episode:number | null;
  kind:string; name:string; url:string; metadata:Record<string, unknown>; created_at:string; updated_at:string;
};

type ResourceIdentity = { tenant_id:string; user_id:string };

export const resourceService = {
  list(payload:ResourceIdentity & { scope?:ResourceScope; project_id?:string; episode?:number }) {
    const query = new URLSearchParams(Object.entries(payload).reduce<Record<string, string>>((result, [key, value]) => {
      if (value !== undefined) result[key] = String(value);
      return result;
    }, {}));
    return requestJsonOk<{ resources:StoredResource[] }>(`/api/resources?${query}`, { cache:"no-store" }, "资源列表加载失败");
  },
  save(payload:ResourceIdentity & { id?:string; plugin_key?:string; scope:ResourceScope; project_id?:string; episode?:number; kind:string; name:string; url?:string; data_url?:string; metadata?:Record<string, unknown> }) {
    return postJson<{ resource:StoredResource }>("/api/resources", payload, {}, "资源保存失败");
  },
  remove(payload:ResourceIdentity & { id:string }) {
    return postJson<{ resource:StoredResource }>("/api/resources/delete", payload, {}, "资源删除失败");
  },
  mediaUrl(resource:StoredResource, identity:ResourceIdentity) {
    if (!resource.url.startsWith("/api/resources/media?")) return resource.url;
    return `${resource.url}&${new URLSearchParams(identity)}`;
  },
};
