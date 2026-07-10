import { Button, Card, Col, Input, List, Progress, Row, Tabs, Typography, Upload, message } from "antd";
import type { UploadFile, UploadProps } from "antd";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { askProject, completeFileBatch, completeMultipart, createFileBatch, generateReport, getMultipartPartUrl, getProject, getProjectFiles, getReports, getUploadedParts, retryFile, uploadBatchFileContent } from "../api/services";
import type { ChatResponse, Project, ProjectFile, Report } from "../types";

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [question, setQuestion] = useState("");
  const [chatResult, setChatResult] = useState<ChatResponse | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<UploadFile[]>([]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batchProgress, setBatchProgress] = useState(0);

  const load = async () => {
    setProject(await getProject(projectId));
    setFiles(await getProjectFiles(projectId));
    setReports(await getReports(projectId));
  };

  useEffect(() => { void load(); }, [projectId]);

  useEffect(() => {
    if (!batchId) return;
    const token = localStorage.getItem("vision_capital_ai_token");
    const configuredBase = import.meta.env.VITE_API_BASE_URL;
    const base = configuredBase
      ? configuredBase.replace(/^http/, "ws")
      : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;
    const socket = new WebSocket(`${base}/api/ws/batches/${batchId}?token=${encodeURIComponent(token ?? "")}`);
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { progress: number; status: string };
      setBatchProgress(payload.progress);
      if (payload.status === "completed" || payload.status === "failed") void load();
    };
    socket.onerror = () => message.warning("实时进度连接中断，页面仍会刷新获取状态");
    return () => socket.close();
  }, [batchId]);

  const uploadProps: UploadProps = {
    multiple: true,
    beforeUpload: () => false,
    fileList: selectedFiles,
    onChange: ({ fileList }) => setSelectedFiles(fileList),
    showUploadList: true,
  };

  const submitBatch = async () => {
    const localFiles = selectedFiles.map((item) => item.originFileObj).filter(Boolean) as File[];
    if (!localFiles.length) return;
    try {
      const batch = await createFileBatch(projectId, localFiles);
      setBatchId(batch.id);
      for (let index = 0; index < localFiles.length; index += 1) {
        const localFile = localFiles[index];
        const session = batch.upload_sessions[index];
        if (!session || !localFile) throw new Error("上传会话与文件数量不一致");
        if (session.upload_mode === "direct" && session.upload_url) {
          const response = await fetch(session.upload_url, { method: "PUT", body: localFile, headers: { "Content-Type": localFile.type || "application/octet-stream" } });
          if (!response.ok) throw new Error(`直传失败: ${localFile.name}`);
        } else if (session.upload_mode === "multipart" && session.part_size) {
          const resumeKey = `vision-capital-ai:batch:${batch.id}:file:${session.file_id}:parts`;
          const storedParts = JSON.parse(localStorage.getItem(resumeKey) ?? "{}") as Record<string, string>;
          const serverParts = await getUploadedParts(batch.id, session.file_id);
          for (const part of serverParts) storedParts[String(part.part_number)] = part.etag;
          const parts: Array<{ part_number: number; etag: string }> = Object.entries(storedParts).map(([partNumber, etag]) => ({ part_number: Number(partNumber), etag }));
          for (let offset = 0, partNumber = 1; offset < localFile.size; offset += session.part_size, partNumber += 1) {
            if (storedParts[String(partNumber)]) continue;
            const url = await getMultipartPartUrl(batch.id, session.file_id, partNumber);
            const response = await fetch(url, { method: "PUT", body: localFile.slice(offset, offset + session.part_size) });
            if (!response.ok) throw new Error(`分片上传失败: ${localFile.name}`);
            const etag = response.headers.get("ETag")?.replace(/"/g, "") ?? "";
            if (!etag) throw new Error("R2 未返回 ETag，请检查对象存储 CORS 的 expose_headers 配置");
            storedParts[String(partNumber)] = etag;
            parts.push({ part_number: partNumber, etag });
            localStorage.setItem(resumeKey, JSON.stringify(storedParts));
          }
          await completeMultipart(batch.id, session.file_id, Object.entries(storedParts).map(([partNumber, etag]) => ({ part_number: Number(partNumber), etag })));
          localStorage.removeItem(resumeKey);
        } else {
          await uploadBatchFileContent(batch.id, session.file_id, localFile);
        }
      }
      await completeFileBatch(batch.id);
      setSelectedFiles([]);
      message.success("批次已提交，解析正在后台进行");
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "批量上传失败");
    }
  };

  return (
    <div className="page-stack">
      <Card className="glass-card"><Typography.Title level={2}>{project?.name}</Typography.Title><Typography.Paragraph>{project?.description}</Typography.Paragraph></Card>
      <Tabs items={[
        { key: "overview", label: "项目概览", children: <Row gutter={[16, 16]}><Col span={8}><Card className="glass-card" title="公司">{project?.company_name}</Card></Col><Col span={8}><Card className="glass-card" title="行业">{project?.industry}</Card></Col><Col span={8}><Card className="glass-card" title="阶段">{project?.stage}</Card></Col></Row> },
        { key: "files", label: "文档资料", children: <Card className="glass-card" extra={<><Upload {...uploadProps}><Button>选择文件</Button></Upload><Button type="primary" disabled={!selectedFiles.length} onClick={() => void submitBatch()}>开始批量解析</Button></>}>
          {batchId && <Progress percent={batchProgress} status={batchProgress === 100 ? "success" : "active"} />}
          <List dataSource={files} renderItem={(file) => <List.Item><List.Item.Meta title={file.filename} description={`${file.parse_status} · ${file.parse_stage} · ${file.content_type}${file.parse_error ? ` · ${file.parse_error}` : ""}`} /><Progress percent={file.progress} size="small" style={{ width: 180 }} status={file.parse_status === "failed" ? "exception" : undefined} />{file.parse_status === "failed" && <Button type="link" onClick={async () => { await retryFile(file.id); await load(); }}>重试解析</Button>}</List.Item>} />
        </Card> },
        { key: "chat", label: "AI 问答", children: <Card className="glass-card"><Input.TextArea rows={4} value={question} onChange={(event) => setQuestion(event.target.value)} /><Button type="primary" style={{ marginTop: 12 }} onClick={async () => setChatResult(await askProject(projectId, question))}>发起分析</Button>{chatResult && <div style={{ marginTop: 16 }}><Typography.Title level={4}>回答</Typography.Title><Typography.Paragraph>{chatResult.answer}</Typography.Paragraph><List dataSource={chatResult.citations} renderItem={(citation) => <List.Item><List.Item.Meta title={citation.filename} description={citation.content} /></List.Item>} /></div>}</Card> },
        { key: "reports", label: "投研报告", children: <Card className="glass-card" extra={<Button type="primary" onClick={async () => { await generateReport(projectId); await load(); }}>生成报告</Button>}><List dataSource={reports} renderItem={(report) => <List.Item><List.Item.Meta title={report.title} description={report.content.slice(0, 280)} /></List.Item>} /></Card> },
      ]} />
    </div>
  );
}
