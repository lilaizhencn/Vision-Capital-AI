export type InvestmentStatus =
  | "pre_investment"
  | "in_progress"
  | "post_investment"
  | "rejected"
  | "exited";

export interface User {
  id: string;
  email: string;
  username: string;
  created_at: string;
}

export interface Project {
  id: string;
  owner_id: string;
  name: string;
  company_name: string;
  industry: string;
  stage: string;
  description: string;
  investment_status: InvestmentStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectFile {
  id: string;
  project_id: string;
  batch_id?: string | null;
  filename: string;
  content_type: string;
  size: number;
  r2_bucket?: string | null;
  r2_object_key: string;
  parse_status: string;
  parse_error?: string | null;
  parse_stage: string;
  progress: number;
  retry_count: number;
  checksum_sha256?: string | null;
  expected_checksum_sha256?: string | null;
  virus_scan_status?: string;
  virus_scan_result?: string | null;
  extracted_data?: Record<string, unknown> | null;
  multipart_upload_id?: string | null;
  created_at: string;
}

export interface UploadSession {
  file_id: string;
  object_key: string;
  upload_url?: string | null;
  upload_mode: "direct" | "multipart" | "backend";
  part_size?: number | null;
  total_parts?: number | null;
  upload_id?: string | null;
}

export interface FileBatch {
  id: string;
  project_id: string;
  total_files: number;
  completed_files: number;
  failed_files: number;
  progress: number;
  status: string;
  files: ProjectFile[];
  upload_sessions: UploadSession[];
}

export interface Citation {
  file_id: string;
  filename: string;
  content: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
}

export interface Report {
  id: string;
  project_id: string;
  title: string;
  content: string;
  created_at: string;
}

export interface DashboardSummary {
  total_projects: number;
  pre_investment_projects: number;
  in_progress_projects: number;
  post_investment_projects: number;
  total_files: number;
  completed_files: number;
  recent_projects: Project[];
  recent_reports: Report[];
}
