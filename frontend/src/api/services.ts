import client from "./client";
import type { ChatResponse, DashboardSummary, FileBatch, MonitoringUpdate, Project, ProjectFile, ProjectTask, ProjectTaskInput, Report, RequirementDetail, ResearchWorkspace, User } from "../types";

export async function register(payload: { email: string; username: string; password: string }) {
  const { data } = await client.post("/api/auth/register", payload);
  return data;
}

export async function login(payload: { email: string; password: string }) {
  const { data } = await client.post("/api/auth/login", payload);
  return data;
}

export async function getMe() {
  const { data } = await client.get<User>("/api/auth/me");
  return data;
}

export async function getDashboardSummary() {
  const { data } = await client.get<DashboardSummary>("/api/dashboard/summary");
  return data;
}

export async function getProjects() {
  const { data } = await client.get<Project[]>("/api/projects");
  return data;
}

export async function createProject(payload: Partial<Project>) {
  const { data } = await client.post<Project>("/api/projects", payload);
  return data;
}

export async function getProject(projectId: string) {
  const { data } = await client.get<Project>(`/api/projects/${projectId}`);
  return data;
}

export async function updateProject(projectId: string, payload: Partial<Project>) {
  const { data } = await client.put<Project>(`/api/projects/${projectId}`, payload);
  return data;
}

export async function getProjectFiles(projectId: string) {
  const { data } = await client.get<ProjectFile[]>(`/api/projects/${projectId}/files`);
  return data;
}

export async function uploadProjectFile(projectId: string, file: File) {
  const formData = new FormData();
  formData.append("upload_file", file);
  const { data } = await client.post(`/api/projects/${projectId}/files/upload`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function createFileBatch(projectId: string, files: File[]) {
  // Hash sequentially and avoid buffering large files in the browser. The
  // worker always computes the authoritative checksum after upload.
  const checksums: (string | null)[] = [];
  for (const file of files) {
    if (!globalThis.crypto?.subtle || file.size > 64 * 1024 * 1024) {
      checksums.push(null);
      continue;
    }
    const digest = await globalThis.crypto.subtle.digest("SHA-256", await file.arrayBuffer());
    checksums.push(Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join(""));
  }
  const { data } = await client.post<FileBatch>(`/api/projects/${projectId}/file-batches`, {
    files: files.map((file, index) => ({ filename: file.name, size: file.size, content_type: file.type || "application/octet-stream", checksum_sha256: checksums[index] })),
  });
  return data;
}

export async function completeFileBatch(batchId: string) {
  const { data } = await client.post<FileBatch>(`/api/file-batches/${batchId}/complete`);
  return data;
}

export async function getFileBatch(batchId: string) {
  const { data } = await client.get<FileBatch>(`/api/file-batches/${batchId}`);
  return data;
}

export async function uploadBatchFileContent(batchId: string, fileId: string, file: File) {
  const formData = new FormData();
  formData.append("upload_file", file);
  const { data } = await client.post<ProjectFile>(`/api/file-batches/${batchId}/files/${fileId}/content`, formData);
  return data;
}

export async function getMultipartPartUrl(batchId: string, fileId: string, partNumber: number) {
  const { data } = await client.get<{ url: string }>(`/api/file-batches/${batchId}/files/${fileId}/parts/${partNumber}/url`);
  return data.url;
}

export async function getUploadedParts(batchId: string, fileId: string) {
  const { data } = await client.get<{ parts: Array<{ part_number: number; etag: string }> }>(`/api/file-batches/${batchId}/files/${fileId}/parts`);
  return data.parts;
}

export async function uploadMultipartPartContent(batchId: string, fileId: string, partNumber: number, file: Blob) {
  const formData = new FormData();
  formData.append("upload_file", file, `part-${partNumber}`);
  const { data } = await client.post<{ part_number: number; etag: string }>(`/api/file-batches/${batchId}/files/${fileId}/parts/${partNumber}/content`, formData);
  return data;
}

export async function completeMultipart(batchId: string, fileId: string, parts: Array<{ part_number: number; etag: string }>) {
  await client.post(`/api/file-batches/${batchId}/files/${fileId}/complete-multipart`, { parts });
}

export async function retryFile(fileId: string) {
  const { data } = await client.post<ProjectFile>(`/api/files/${fileId}/retry`);
  return data;
}

export async function askProject(projectId: string, message: string) {
  const { data } = await client.post<ChatResponse>(`/api/projects/${projectId}/chat`, { message });
  return data;
}

export async function getReports(projectId: string) {
  const { data } = await client.get<Report[]>(`/api/projects/${projectId}/reports`);
  return data;
}

export async function generateReport(projectId: string) {
  const { data } = await client.post<Report>(`/api/projects/${projectId}/reports/generate`);
  return data;
}

export async function getRecentReports() {
  const { data } = await client.get<Report[]>("/api/reports");
  return data;
}

export async function getMonitoringUpdates(projectId: string) {
  const { data } = await client.get<MonitoringUpdate[]>(`/api/projects/${projectId}/monitoring`);
  return data;
}

export async function createMonitoringUpdate(projectId: string, payload: Omit<MonitoringUpdate, "id" | "project_id" | "created_at">) {
  const { data } = await client.post<MonitoringUpdate>(`/api/projects/${projectId}/monitoring`, payload);
  return data;
}

export async function getProjectTasks(projectId: string) {
  const { data } = await client.get<ProjectTask[]>(`/api/projects/${projectId}/tasks`);
  return data;
}

export async function createProjectTask(projectId: string, payload: ProjectTaskInput & { label: string }) {
  const { data } = await client.post<ProjectTask>(`/api/projects/${projectId}/tasks`, payload);
  return data;
}

export async function updateProjectTask(projectId: string, taskId: string, payload: ProjectTaskInput) {
  const { data } = await client.patch<ProjectTask>(`/api/projects/${projectId}/tasks/${taskId}`, payload);
  return data;
}

export async function getResearchWorkspace(projectId: string) {
  const { data } = await client.get<ResearchWorkspace>(`/api/projects/${projectId}/research`);
  return data;
}

export async function getRequirementDetail(projectId: string, requirementId: string) {
  const { data } = await client.get<RequirementDetail>(`/api/projects/${projectId}/research/requirements/${requirementId}`);
  return data;
}

export async function downloadProjectFile(file: ProjectFile) {
  const response = await client.get<Blob>(`/api/files/${file.id}/download`, { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function enrichProjectResearch(projectId: string) {
  const { data } = await client.post<{ status: string; task_id?: string | null }>(`/api/projects/${projectId}/research/enrich`);
  return data;
}

export async function updateResearchSettings(projectId: string, autoEnabled: boolean) {
  const { data } = await client.patch<ResearchWorkspace>(`/api/projects/${projectId}/research/settings`, {
    auto_enabled: autoEnabled,
  });
  return data;
}
