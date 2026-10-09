import type { Job } from "./types";

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

/** Build the download URL for a finished job's specification sheet. */
export function downloadUrl(id: string): string {
  return `${BASE}/jobs/${id}/download`;
}
