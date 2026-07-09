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
  filename: string;
  content_type: string;
  size: number;
  r2_bucket?: string | null;
  r2_object_key: string;
  parse_status: string;
  parse_error?: string | null;
  created_at: string;
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

