export function resultMediaUrl(filename:string, subfolder = "") {
  const query = new URLSearchParams({ filename });
  if (subfolder) query.set("subfolder", subfolder);
  return `/api/result-media?${query}`;
}
