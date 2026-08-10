export class ApiResponseError extends Error {
  readonly status:number;
  readonly payload:unknown;

  constructor(message:string, status:number, payload:unknown = null) {
    super(message);
    this.name = "ApiResponseError";
    this.status = status;
    this.payload = payload;
  }
}

export type ApiJsonResult<T> = {
  data:T;
  ok:boolean;
  status:number;
};

export type ApiResponseMessages = {
  empty?:string | ((status:number) => string);
  invalid?:string | ((status:number) => string);
  allowEmpty?:boolean;
};

function resolveResponseMessage(message:ApiResponseMessages["empty"], status:number, fallback:string) {
  return typeof message === "function" ? message(status) : message || fallback;
}

function messageFromPayload(payload:unknown, fallback:string) {
  if (payload && typeof payload === "object" && "message" in payload) {
    const message = (payload as { message?:unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  if (payload && typeof payload === "object" && "error" in payload) {
    const error = (payload as { error?:unknown }).error;
    if (typeof error === "string" && error.trim()) return error;
  }
  return fallback;
}

export async function requestJson<T>(input:RequestInfo | URL, init?:RequestInit, messages:ApiResponseMessages = {}):Promise<ApiJsonResult<T>> {
  const response = await fetch(input, init);
  const responseText = await response.text();
  if (!responseText) {
    if (messages.allowEmpty) return { data:{} as T, ok:response.ok, status:response.status };
    throw new ApiResponseError(resolveResponseMessage(messages.empty, response.status, `服务连接中断（HTTP ${response.status}）`), response.status);
  }
  let data:unknown;
  try {
    data = JSON.parse(responseText);
  } catch {
    throw new ApiResponseError(resolveResponseMessage(messages.invalid, response.status, `服务返回异常（HTTP ${response.status}）`), response.status, responseText);
  }
  return { data:data as T, ok:response.ok, status:response.status };
}

export async function requestJsonOk<T>(input:RequestInfo | URL, init?:RequestInit, fallback = "请求失败"):Promise<T> {
  const result = await requestJson<T>(input, init);
  if (!result.ok) throw new ApiResponseError(messageFromPayload(result.data, fallback), result.status, result.data);
  return result.data;
}

export async function requestBlobOk(input:RequestInfo | URL, init?:RequestInit, fallback = "文件下载失败"):Promise<Blob> {
  const response = await fetch(input, init);
  if (!response.ok) throw new ApiResponseError(fallback, response.status);
  return response.blob();
}

export async function postJson<T>(url:string, body:unknown, init:Omit<RequestInit, "method" | "body"> = {}, fallback = "请求失败"):Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return requestJsonOk<T>(url, {
    ...init,
    method:"POST",
    headers,
    body:JSON.stringify(body),
  }, fallback);
}

export async function postJsonIgnoringResponse(url:string, body:unknown):Promise<void> {
  const response = await fetch(url, {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body:JSON.stringify(body),
  });
  if (response.ok) return;
  const responseText = await response.text();
  let payload:unknown = responseText;
  try { payload = responseText ? JSON.parse(responseText) : null; } catch { /* 保留原始响应 */ }
  throw new ApiResponseError(messageFromPayload(payload, `请求失败（HTTP ${response.status}）`), response.status, payload);
}
