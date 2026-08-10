export function validateImageFile(file?:File, maximumBytes?:number) {
  if (!file || !file.type.startsWith("image/")) return "请选择图片文件";
  if (maximumBytes && file.size > maximumBytes) return `图片不能超过 ${Math.round(maximumBytes / 1024 / 1024)}MB，请压缩后重试`;
  return "";
}

const allowedMediaTypes = new Map([
  ["png", ["image/png"]], ["jpg", ["image/jpeg"]], ["jpeg", ["image/jpeg"]], ["webp", ["image/webp"]], ["gif", ["image/gif"]],
  ["mp4", ["video/mp4"]], ["mov", ["video/quicktime"]], ["webm", ["video/webm"]],
  ["mp3", ["audio/mpeg"]], ["wav", ["audio/wav", "audio/x-wav"]], ["m4a", ["audio/mp4", "audio/x-m4a"]],
]);

function mediaMagicMatches(bytes:Uint8Array, extension:string) {
  const ascii = String.fromCharCode(...bytes);
  if (extension === "png") return bytes[0] === 0x89 && ascii.slice(1, 4) === "PNG";
  if (["jpg", "jpeg"].includes(extension)) return bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  if (extension === "gif") return ascii.startsWith("GIF87a") || ascii.startsWith("GIF89a");
  if (extension === "webp") return ascii.startsWith("RIFF") && ascii.slice(8, 12) === "WEBP";
  if (["mp4", "mov"].includes(extension)) return ascii.slice(4, 8) === "ftyp";
  if (extension === "webm") return bytes[0] === 0x1a && bytes[1] === 0x45 && bytes[2] === 0xdf && bytes[3] === 0xa3;
  if (extension === "mp3") return ascii.startsWith("ID3") || bytes[0] === 0xff;
  if (extension === "wav") return ascii.startsWith("RIFF") && ascii.slice(8, 12) === "WAVE";
  if (extension === "m4a") return ascii.slice(4, 8) === "ftyp";
  return false;
}

export async function validateMediaFile(file?:File, imageMaximumBytes = 20 * 1024 * 1024, videoMaximumBytes = 500 * 1024 * 1024) {
  if (!file) return "请选择图片、视频或音频文件";
  const extension = file.name.split(".").pop()?.toLowerCase() || "";
  const allowedMimeTypes = allowedMediaTypes.get(extension);
  if (!allowedMimeTypes || !allowedMimeTypes.includes(file.type)) return `不支持的文件类型：${file.name}`;
  const maximumBytes = file.type.startsWith("video/") || file.type.startsWith("audio/") ? videoMaximumBytes : imageMaximumBytes;
  if (!file.size || file.size > maximumBytes) return `${file.type.startsWith("video/") ? "视频" : file.type.startsWith("audio/") ? "音频" : "图片"}不能超过 ${Math.round(maximumBytes / 1024 / 1024)}MB`;
  try {
    const bytes = new Uint8Array(await file.slice(0, 16).arrayBuffer());
    if (!mediaMagicMatches(bytes, extension)) return `文件内容与扩展名不一致：${file.name}`;
  } catch {
    return `无法读取文件：${file.name}`;
  }
  return "";
}

export function readFileAsDataUrl(file:File, Reader:typeof FileReader = FileReader, timeoutMs = 30_000) {
  return new Promise<string>((resolve, reject) => {
    const reader = new Reader();
    const timeout = globalThis.setTimeout(() => {
      reader.abort();
      reject(new Error(`文件读取超过 ${Math.ceil(timeoutMs / 1000)} 秒`));
    }, timeoutMs);
    reader.onload = () => { globalThis.clearTimeout(timeout); resolve(String(reader.result || "")); };
    reader.onerror = () => { globalThis.clearTimeout(timeout); reject(new Error("图片读取失败")); };
    reader.onabort = () => { globalThis.clearTimeout(timeout); reject(new Error("文件读取已终止")); };
    reader.readAsDataURL(file);
  });
}
