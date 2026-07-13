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

export interface AIUsage {
  usage_date: string;
  limit: number;
  used: number;
  remaining: number;
  reset_at: string;
  timezone: string;
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
  research_auto_enabled: boolean;
  research_status: string;
  last_research_at?: string | null;
  next_research_at?: string | null;
  research_last_error?: string | null;
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
  source_kind?: "upload" | "public_research";
  source_url?: string | null;
  source_quality?: string | null;
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
  source_kind: string;
  source_url?: string | null;
  source_quality?: string | null;
  document_role: "company_disclosure" | "industry_context" | "uploaded_evidence";
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  confidence: "low" | "medium" | "high";
  missing_evidence: string[];
  evidence_control_passed?: boolean | null;
  quality_issues: string[];
  claim_ledger: EvidenceClaim[];
}

export interface EvidenceClaim {
  claim_id: string;
  claim: string;
  source_filename: string;
  document_role: "company_disclosure" | "industry_context" | "uploaded_evidence";
  evidence_quote: string;
  category: string;
}

export interface EvidenceRequirement {
  id: string;
  project_id: string;
  category: string;
  label: string;
  status: "missing" | "partial" | "covered";
  priority: string;
  reason: string;
  suggested_document: string;
  updated_at: string;
}

export interface RequirementField {
  key: string;
  label: string;
  status: "found" | "missing";
  evidence_excerpt: string;
  source_file_id?: string | null;
  source_filename?: string | null;
}

export interface RequirementFile {
  id: string;
  filename: string;
  content_type: string;
  parse_status: string;
  source_kind: string;
  created_at: string;
}

export interface ResearchSource {
  id: string;
  project_id: string;
  file_id?: string | null;
  evidence_category: string;
  title: string;
  publisher: string;
  domain: string;
  url: string;
  snippet: string;
  quality: string;
  status: "discovered" | "ingested" | "review_required" | "failed";
  error?: string | null;
  discovered_at: string;
  fetched_at?: string | null;
}

export interface ResearchWorkspace {
  requirements: EvidenceRequirement[];
  sources: ResearchSource[];
  enrichment_running: boolean;
  auto_enabled: boolean;
  status: string;
  last_research_at?: string | null;
  next_research_at?: string | null;
  last_error?: string | null;
}

export interface RequirementDetail {
  requirement: EvidenceRequirement;
  fields: RequirementField[];
  related_files: RequirementFile[];
  related_sources: ResearchSource[];
}

export interface Report {
  id: string;
  project_id: string;
  title: string;
  content: string;
  created_at: string;
}

export interface MonitoringUpdate {
  id: string;
  project_id: string;
  metric_name: string;
  metric_value: string;
  metric_unit: string;
  risk_level: "normal" | "watch" | "high";
  note: string;
  created_at: string;
}

export interface ProjectTask {
  id: string;
  project_id: string;
  label: string;
  done: boolean;
  status: "todo" | "in_progress" | "completed";
  description: string;
  assignee: string;
  due_date?: string | null;
  result: string;
  related_requirement_id?: string | null;
  evidence_file_ids: string[];
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectTaskInput {
  label?: string;
  status?: "todo" | "in_progress" | "completed";
  description?: string;
  assignee?: string;
  due_date?: string | null;
  result?: string;
  related_requirement_id?: string | null;
  evidence_file_ids?: string[];
}

export interface ClosingCondition {
  id: string;
  label: string;
  status: "pending" | "satisfied" | "waived" | "failed";
  owner: string;
  due_date?: string | null;
  evidence_file_id?: string | null;
  waiver_reason: string;
}

export interface TransactionExecution {
  id: string;
  project_id: string;
  transaction_type: string;
  currency: string;
  committed_amount?: string | null;
  entry_valuation?: string | null;
  ownership_pct?: string | null;
  status: "drafting" | "ic_review" | "signing" | "closing" | "closed" | "aborted";
  approval_status: "pending" | "conditional" | "approved" | "rejected";
  decision_rationale: string;
  conditions_precedent: ClosingCondition[];
  evidence_file_ids: string[];
  approved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MonitoringMetricDefinition {
  id: string;
  project_id: string;
  code: string;
  name: string;
  unit: string;
  frequency: string;
  direction: "higher_better" | "lower_better";
  baseline_value?: string | null;
  target_value?: string | null;
  watch_threshold?: string | null;
  breach_threshold?: string | null;
  owner: string;
  source_description: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MonitoringObservation {
  id: string;
  project_id: string;
  metric_id: string;
  period_end: string;
  value: string;
  status: "normal" | "watch" | "high";
  variance_from_target?: string | null;
  source_file_id?: string | null;
  note: string;
  created_at: string;
}

export interface LifecycleRisk {
  id: string;
  project_id: string;
  observation_id?: string | null;
  category: string;
  title: string;
  severity: "watch" | "high" | "critical";
  status: "open" | "monitoring" | "resolved";
  description: string;
  trigger_source: string;
  evidence_file_ids: string[];
  detected_at: string;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvestmentOpinionVersion {
  id: string;
  project_id: string;
  version: number;
  stage: string;
  recommendation: string;
  confidence: "low" | "medium" | "high";
  quality_score: string;
  thesis: string;
  change_summary: string;
  evidence_hash: string;
  evidence_file_ids: string[];
  source_count: number;
  created_at: string;
}

export interface DataSourceSubscription {
  id: string;
  project_id: string;
  name: string;
  source_type: string;
  category: string;
  url: string;
  cadence_hours: number;
  active: boolean;
  status: string;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LifecycleSummary {
  transaction?: TransactionExecution | null;
  metrics: MonitoringMetricDefinition[];
  observations: MonitoringObservation[];
  risks: LifecycleRisk[];
  opinions: InvestmentOpinionVersion[];
  data_sources: DataSourceSubscription[];
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
