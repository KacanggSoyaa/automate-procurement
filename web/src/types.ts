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

/** Trimmed result payload the API returns once a job is done. */
export interface JobResult {
  files_processed: number;
  source_files: string[];
  line_items_count: number;
  line_items: LineItem[];
  meta: {
    project_ref?: string | null;
    project_title?: string | null;
    delivery_location?: string | null;
    buyer?: string | null;
  };
  technical_count: number;
  submission_count: number;
  mandatory_count: number;
  has_output: boolean;
}

/** Lifecycle state of a processing job. */
export type JobStatus = "queued" | "running" | "done" | "error";

/** A timestamped progress message shown in the job log panel. */
export interface JobLog {
  ts: string;
  message: string;
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
  created_at: string;
}
