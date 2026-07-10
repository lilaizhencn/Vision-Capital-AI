import client from "./client";
import type { ChatResponse, DashboardSummary, FileBatch, Project, ProjectFile, Report, User } from "../types";

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
  const { data } = await client.post<FileBatch>(`/api/projects/${projectId}/file-batches`, {
    files: files.map((file) => ({ filename: file.name, size: file.size, content_type: file.type || "application/octet-stream" })),
  });
  return data;
}

export async function completeFileBatch(batchId: string) {
  const { data } = await client.post<FileBatch>(`/api/file-batches/${batchId}/complete`);
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

export async function completeMultipart(batchId: string, fileId: string, parts: Array<{ part_number: number; etag: string }>) {
  await client.post(`/api/file-batches/${batchId}/files/${fileId}/complete-multipart`, { parts });
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
