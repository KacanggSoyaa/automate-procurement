import type { HistoryItem, Job } from "./types";

const BASE = "/api";

/** Options that control how the backend processes an uploaded job. */
export interface CreateJobOptions {
  model?: string;
  includeImages?: boolean;
  pattern?: string;
  skipFiles?: string[];
}

/** Upload the given files as a folder and start a new processing job. */
export async function createJob(files: File[], opts: CreateJobOptions = {}): Promise<Job> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
  }
  if (opts.model) form.append("model", opts.model);
  form.append("include_images", String(opts.includeImages ?? true));
  form.append("pattern", opts.pattern ?? "*");
  if (opts.skipFiles && opts.skipFiles.length) {
    form.append("skip_files", opts.skipFiles.join("\n"));
  }

  const res = await fetch(`${BASE}/jobs`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Upload failed (${res.status}): ${detail}`);
  }
  return (await res.json()) as Job;
}

/** Fetch the latest status and results for a job by id. */
export async function getJob(id: string): Promise<Job> {
  const res = await fetch(`${BASE}/jobs/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch job (${res.status})`);
  }
  return (await res.json()) as Job;
}

/** Append files to a finished job and reprocess only the new ones. */
export async function addJobFiles(id: string, files: File[]): Promise<Job> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
  }
  const res = await fetch(`${BASE}/jobs/${id}/files`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to add files (${res.status}): ${detail}`);
  }
  return (await res.json()) as Job;
}

/** Build the download URL for a finished job's specification sheet. */
export function downloadUrl(id: string): string {
  return `${BASE}/jobs/${id}/download`;
}

/** Build the download URL for one historical version snapshot (zip). */
export function downloadVersionUrl(id: string, version: number): string {
  return `${BASE}/jobs/${id}/versions/${version}/download`;
}

/** Fetch the saved history of finished ITB runs (newest first). */
export async function listHistory(): Promise<HistoryItem[]> {
  const res = await fetch(`${BASE}/history`);
  if (!res.ok) {
    throw new Error(`Failed to load history (${res.status})`);
  }
  const data = (await res.json()) as { jobs: HistoryItem[] };
  return data.jobs ?? [];
}

/** Delete a saved history entry and its stored workspace. */
export async function deleteHistory(id: string): Promise<void> {
  const res = await fetch(`${BASE}/history/${id}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`Failed to delete history entry (${res.status})`);
  }
}

/** Rename a saved history entry; returns the updated entry. */
export async function renameHistory(id: string, title: string): Promise<HistoryItem> {
  const res = await fetch(`${BASE}/history/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    throw new Error(`Failed to rename history entry (${res.status})`);
  }
  return (await res.json()) as HistoryItem;
}
