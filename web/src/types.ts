export interface SpecPair {
  parameter: string;
  value: string;
}

export interface LineItem {
  item_no?: string | null;
  item_name?: string | null;
  item_number?: string | null;
  description?: string | null;
  qty?: string | null;
  uom?: string | null;
  specs?: SpecPair[];
}

export interface JobResult {
  files_processed: number;
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

export type JobStatus = "queued" | "running" | "done" | "error";

export interface JobLog {
  ts: string;
  message: string;
}

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
