/** A single technical specification (parameter -> value) for an item. */
export interface SpecPair {
  parameter: string;
  value: string;
}

/** A purchasable line item extracted from the ITB. */
export interface LineItem {
  item_no?: string | null;
  item_name?: string | null;
  item_number?: string | null;
  description?: string | null;
  qty?: string | null;
  uom?: string | null;
  specs?: SpecPair[];
}

/** Manually editable text fields for one line item. */
export interface LineItemEdit {
  item_no: string;
  item_name: string;
  item_number: string;
  description: string;
  qty: string;
  uom: string;
}

/** A copy-ready request-for-quotation email generated for one line item. */
export interface RfqEmail {
  subject: string;
  body: string;
}

/** One shortlisted supplier found via a live, grounded web search. */
export interface Supplier {
  company_name: string;
  website: string;
  email: string;
  contact: string;
  source: string;
}

/** Supplier shortlist state for one product (line item). */
export interface ProductSuppliers {
  item_no?: string | null;
  item_name?: string | null;
  status: "pending" | "searching" | "done" | "error";
  message?: string;
  backend?: "search_grounding" | "web_search" | null;
  suppliers: Supplier[];
}

/** How supplier search is run: one batched search for all items, or per item. */
export type SupplierMode = "all" | "per_item";

/** Which set of curated suppliers to view: just yours, or everyone's. */
export type SupplierScope = "mine" | "all";

/** A supplier saved in the user-curated master list (independent of any run). */
export interface SavedSupplier {
  id: string;
  company_name: string;
  website: string;
  email: string;
  contact: string;
  source: string;
  notes: string;
  tags: string;
  owner?: string;
  created_at: string;
  updated_at: string;
}

/** Fields a user can set/edit for a curated supplier. */
export type SupplierDraft = Pick<
  SavedSupplier,
  "company_name" | "website" | "email" | "contact" | "source" | "notes" | "tags"
>;

/** Result of bulk-importing suppliers into the master list. */
export interface SupplierImportResult {
  added: number;
  skipped: number;
  total: number;
}

/** Google-Search grounding quota state shown in the header. */
export interface QuotaStatus {
  state: "ok" | "exhausted" | "unknown";
  model: string | null;
  ts: string | null;
  detail: string | null;
  link: string;
}

/** Trimmed result payload the API returns once a job is done. */
export interface JobResult {
  files_processed: number;
  source_files: string[];
  line_items_count: number;
  line_items: LineItem[];
  rfq_emails: RfqEmail[];
  meta: {
    project_ref?: string | null;
    project_title?: string | null;
    delivery_location?: string | null;
    buyer?: string | null;
  };
  technical_count: number;
  submission_count: number;
  mandatory_count: number;
  suppliers: ProductSuppliers[];
  has_output: boolean;
}

/** Lifecycle state of a processing job. */
export type JobStatus = "queued" | "running" | "done" | "error";

/** A timestamped progress message shown in the job log panel. */
export interface JobLog {
  ts: string;
  message: string;
}

/** A versioned, immutable snapshot of a finished run's output files. */
export interface VersionInfo {
  id: number;
  tag: string;
  ts: string;
  reason: "run" | "reprocess" | "edit" | "delete";
  files: string[];
  files_processed: number;
  line_items_count: number;
}

/** One immutable entry in a job's audit trail. */
export interface AuditEvent {
  ts: string;
  actor: string;
  action: string;
  detail: string;
  version?: number | null;
}

/** Full job state as returned by the backend API. */
export interface Job {
  id: string;
  status: JobStatus;
  stage: string;
  current: number;
  total: number;
  message: string;
  logs: JobLog[];
  error?: string | null;
  files: string[];
  result: JobResult | null;
  versions: VersionInfo[];
  audit: AuditEvent[];
  created_at: string;
}

/** One saved ITB run shown in the history sidebar. */
export interface HistoryItem {
  id: string;
  status: JobStatus;
  created_at: string;
  title: string;
  subtitle: string;
  line_items_count: number;
  files_count: number;
  project_ref?: string | null;
  buyer?: string | null;
}

/** One user's saved runs, as listed in the admin's user-activity view. */
export interface AdminHistoryOwner {
  owner_id: string;
  username: string;
  display_name: string;
  role: string;
  jobs: HistoryItem[];
}

/** An authenticated account (admin-created). */
export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  role: "admin" | "user";
  created_at?: string;
  ai_provider?: string;
  supplier_search_provider?: boolean;
  keys?: Record<string, { has_api_key: boolean; api_key_hint: string | null }>;
  has_api_key?: boolean;
}

/** One supported AI provider as exposed by the settings API. */
export interface AiProviderInfo {
  id: string;
  label: string;
  default_model: string;
  models: string[];
  key_url?: string;
  env_key?: string;
  env_key_available?: boolean;
  has_api_key?: boolean;
  api_key_hint?: string | null;
  model?: string | null;
}

/** A user's AI settings (keys are only ever returned masked). */
export interface AiSettings {
  provider: string;
  supplier_search_provider: boolean;
  providers: AiProviderInfo[];
  has_api_key?: boolean;
  api_key_hint?: string | null;
  model?: string | null;
  env_key_available?: boolean;
  fallback_models?: string[];
  default_model?: string;
}
