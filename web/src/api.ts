import type {
  AiSettings,
  AuthUser,
  HistoryItem,
  Job,
  QuotaStatus,
  SavedSupplier,
  SupplierDraft,
  SupplierImportResult,
  SupplierMode,
  SupplierScope,
} from "./types";

const BASE = "/api";

/**
 * fetch wrapper that includes cookies and turns a 401 into a typed error so the
 * app can drop back to the login screen.
 */
async function request(input: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(input, { credentials: "include", ...init });
  if (res.status === 401) {
    throw new AuthError("Not authenticated");
  }
  return res;
}

/** Thrown when the session is missing or expired (HTTP 401). */
export class AuthError extends Error {}

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

  const res = await request(`${BASE}/jobs`, { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Upload failed (${res.status}): ${detail}`);
  }
  return (await res.json()) as Job;
}

/** Fetch the latest status and results for a job by id. */
export async function getJob(id: string): Promise<Job> {
  const res = await request(`${BASE}/jobs/${id}`);
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
  const res = await request(`${BASE}/jobs/${id}/files`, { method: "POST", body: form });
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

/** Start supplier search for a finished job. `mode="all"` batches every product
 *  into one search; ``mode="per_item"` runs one search per line item. */
export async function findSuppliers(id: string, mode: SupplierMode = "all"): Promise<Job> {
  const res = await request(`${BASE}/jobs/${id}/suppliers?mode=${mode}`, { method: "POST" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to start supplier search (${res.status}): ${detail}`);
  }
  return (await res.json()) as Job;
}

/** Build the CSV export URL for a job's supplier shortlists. */
export function suppliersCsvUrl(id: string): string {
  return `${BASE}/jobs/${id}/suppliers/download.csv`;
}

/** Fetch the Google-Search grounding quota state for the header. */
export async function getQuotaStatus(): Promise<QuotaStatus> {
  const res = await request(`${BASE}/quota`);
  if (!res.ok) {
    throw new Error(`Failed to load quota status (${res.status})`);
  }
  return (await res.json()) as QuotaStatus;
}

/** Fetch the saved history of finished ITB runs (newest first). */
export async function listHistory(): Promise<HistoryItem[]> {
  const res = await request(`${BASE}/history`);
  if (!res.ok) {
    throw new Error(`Failed to load history (${res.status})`);
  }
  const data = (await res.json()) as { jobs: HistoryItem[] };
  return data.jobs ?? [];
}

/** Delete a saved history entry and its stored workspace. */
export async function deleteHistory(id: string): Promise<void> {
  const res = await request(`${BASE}/history/${id}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`Failed to delete history entry (${res.status})`);
  }
}

/** Rename a saved history entry; returns the updated entry. */
export async function renameHistory(id: string, title: string): Promise<HistoryItem> {
  const res = await request(`${BASE}/history/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    throw new Error(`Failed to rename history entry (${res.status})`);
  }
  return (await res.json()) as HistoryItem;
}

/* ---------------------------------------------------------- supplier list */

/** Fetch suppliers in the master list. `scope="mine"` (default) is your own
 *  list (plus shared entries); `scope="all"` returns every user's suppliers. */
export async function listSuppliers(scope: SupplierScope = "mine"): Promise<SavedSupplier[]> {
  const res = await request(`${BASE}/suppliers?scope=${scope}`);
  if (!res.ok) {
    throw new Error(`Failed to load suppliers (${res.status})`);
  }
  const data = (await res.json()) as { suppliers: SavedSupplier[] };
  return data.suppliers ?? [];
}

/** Add one supplier to the master list. */
export async function createSupplier(draft: SupplierDraft): Promise<SavedSupplier> {
  const res = await request(`${BASE}/suppliers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Failed to add supplier (${res.status}): ${detail}`);
  }
  return (await res.json()) as SavedSupplier;
}

/** Update one supplier in the master list. */
export async function updateSupplier(id: string, draft: Partial<SupplierDraft>): Promise<SavedSupplier> {
  const res = await request(`${BASE}/suppliers/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!res.ok) {
    throw new Error(`Failed to update supplier (${res.status})`);
  }
  return (await res.json()) as SavedSupplier;
}

/** Remove one supplier from the master list. */
export async function deleteSupplier(id: string): Promise<void> {
  const res = await request(`${BASE}/suppliers/${id}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(`Failed to delete supplier (${res.status})`);
  }
}

/** Bulk-add suppliers (e.g. a run's shortlist) to the master list. */
export async function importSuppliers(drafts: SupplierDraft[]): Promise<SupplierImportResult> {
  const res = await request(`${BASE}/suppliers/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ suppliers: drafts }),
  });
  if (!res.ok) {
    throw new Error(`Failed to import suppliers (${res.status})`);
  }
  return (await res.json()) as SupplierImportResult;
}

/* --------------------------------------------------------------- auth */

/** Sign in with a username/password; sets the session cookie on success. */
export async function login(username: string, password: string): Promise<AuthUser> {
  const res = await request(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Login failed (${res.status})`);
  }
  const data = (await res.json()) as { user: AuthUser };
  return data.user;
}

/** Clear the session cookie. */
export async function logout(): Promise<void> {
  await request(`${BASE}/auth/logout`, { method: "POST" });
}

/** Return the current user, or null when not signed in. */
export async function getCurrentUser(): Promise<AuthUser | null> {
  try {
    const res = await request(`${BASE}/auth/me`);
    if (!res.ok) return null;
    const data = (await res.json()) as { user: AuthUser };
    return data.user;
  } catch {
    return null;
  }
}

/** Whether any account exists yet (drives first-run hints on the login screen). */
export async function getAuthStatus(): Promise<{ has_users: boolean }> {
  try {
    const res = await request(`${BASE}/auth/status`);
    if (!res.ok) return { has_users: true };
    return (await res.json()) as { has_users: boolean };
  } catch {
    return { has_users: true };
  }
}

/** List all accounts (admin only). */
export async function listUsers(): Promise<AuthUser[]> {
  const res = await request(`${BASE}/users`);
  if (!res.ok) {
    throw new Error(`Failed to load users (${res.status})`);
  }
  const data = (await res.json()) as { users: AuthUser[] };
  return data.users ?? [];
}

/** Create a new account (admin only). */
export async function createUser(input: {
  username: string;
  password: string;
  display_name?: string;
  role?: string;
}): Promise<AuthUser> {
  const res = await request(`${BASE}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Failed to create user (${res.status})`);
  }
  return (await res.json()) as AuthUser;
}

/** Reset a user's password (admin only). */
export async function setUserPassword(id: string, password: string): Promise<AuthUser> {
  const res = await request(`${BASE}/users/${id}/password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Failed to set password (${res.status})`);
  }
  return (await res.json()) as AuthUser;
}

/** Delete an account (admin only). */
export async function deleteUser(id: string): Promise<void> {
  const res = await request(`${BASE}/users/${id}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Failed to delete user (${res.status})`);
  }
}

/* ----------------------------------------------------------- AI settings */

/** Fetch the caller's AI settings (key is returned masked only). */
export async function getAiSettings(): Promise<AiSettings> {
  const res = await request(`${BASE}/settings/ai`);
  if (!res.ok) {
    throw new Error(`Failed to load settings (${res.status})`);
  }
  return (await res.json()) as AiSettings;
}

/** Save the caller's AI provider/key/model; clears the key when requested. */
export async function updateAiSettings(input: {
  provider?: string;
  supplierSearchProvider?: boolean;
  apiKey?: string;
  clearKey?: boolean;
  model?: string | null;
}): Promise<AiSettings> {
  const body: Record<string, unknown> = {};
  if (input.provider !== undefined) body.provider = input.provider;
  if (input.supplierSearchProvider !== undefined) body.supplier_search_provider = input.supplierSearchProvider;
  if (input.apiKey !== undefined) body.api_key = input.apiKey;
  if (input.clearKey) body.clear_key = true;
  if (input.model !== undefined) body.model = input.model;
  const res = await request(`${BASE}/settings/ai`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `Failed to save settings (${res.status})`);
  }
  return (await res.json()) as AiSettings;
}
