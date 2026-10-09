import type { Job } from "./types";

const BASE = "/api";

export interface CreateJobOptions {
  model?: string;
  includeImages?: boolean;
  pattern?: string;
}

export async function createJob(files: File[], opts: CreateJobOptions = {}): Promise<Job> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
  }
  if (opts.model) form.append("model", opts.model);
  form.append("include_images", String(opts.includeImages ?? true));
  form.append("pattern", opts.pattern ?? "*");

  const res = await fetch(`${BASE}/jobs`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Upload failed (${res.status}): ${detail}`);
  }
  return (await res.json()) as Job;
}

export async function getJob(id: string): Promise<Job> {
  const res = await fetch(`${BASE}/jobs/${id}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch job (${res.status})`);
  }
  return (await res.json()) as Job;
}

export function downloadUrl(id: string): string {
  return `${BASE}/jobs/${id}/download`;
}
