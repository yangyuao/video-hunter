// Thin typed client over the FastAPI /api endpoints.
import type {
  AccountDetail,
  GraphPayload,
  RelationshipType,
  VideoDetail,
  VideoSummary,
} from "./types";

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return (await response.json()) as T;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await response.text());
  return (await response.json()) as T;
}

export async function fetchGraph(
  types: RelationshipType[],
  hideSingle: boolean,
): Promise<GraphPayload> {
  const params = new URLSearchParams();
  params.set("hide_single", String(hideSingle));
  params.set("types", types.join(","));
  return getJson<GraphPayload>(`/api/x/graph?${params.toString()}`);
}

export function fetchAccount(handle: string): Promise<AccountDetail> {
  return getJson<AccountDetail>(`/api/x/accounts/${encodeURIComponent(handle)}`);
}

export function labelAccount(
  handle: string,
  label: string,
  notes: string | null,
): Promise<AccountDetail> {
  return postJson<AccountDetail>(
    `/api/x/accounts/${encodeURIComponent(handle)}/label`,
    { label, notes },
  );
}

export function syncGraph(): Promise<Record<string, number>> {
  return postJson<Record<string, number>>("/api/import/x-graph", {});
}

export function fetchVideos(limit = 500): Promise<VideoSummary[]> {
  return getJson<VideoSummary[]>(`/api/videos?limit=${limit}`);
}

export function fetchVideoDetail(id: number): Promise<VideoDetail> {
  return getJson<VideoDetail>(`/api/videos/${id}`);
}

export function labelVideo(
  id: number,
  label: string,
  notes: string | null,
): Promise<VideoDetail> {
  return postJson<VideoDetail>(`/api/videos/${id}/label`, { label, notes });
}

export function downloadXVideos(
  limit: number,
  download: boolean,
): Promise<Record<string, number>> {
  return postJson<Record<string, number>>("/api/x/download-videos", { limit, download });
}

