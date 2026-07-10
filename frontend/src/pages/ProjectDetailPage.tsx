import { ArrowRightOutlined, CheckCircleOutlined, FileTextOutlined, RobotOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Descriptions, Input, List, Progress, Row, Space, Tabs, Tag, Typography, Upload, message } from "antd";
import type { UploadFile, UploadProps } from "antd";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { askProject, completeFileBatch, completeMultipart, createFileBatch, generateReport, getFileBatch, getMultipartPartUrl, getProject, getProjectFiles, getReports, getUploadedParts, retryFile, uploadBatchFileContent, uploadMultipartPartContent } from "../api/services";
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
  const [resumableBatch, setResumableBatch] = useState<Awaited<ReturnType<typeof createFileBatch>> | null>(null);
  const [batchProgress, setBatchProgress] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [chatting, setChatting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [retryingFileId, setRetryingFileId] = useState<string | null>(null);
  const [tasks, setTasks] = useState([
    { id: "team", label: "补充核心团队履历与分工", done: false },
    { id: "market", label: "确认市场规模与竞争格局假设", done: false },
    { id: "finance", label: "复核最新一版财务预测", done: true },
  ]);

  const load = async () => {
    try {
      const [nextProject, nextFiles, nextReports] = await Promise.all([
        getProject(projectId),
        getProjectFiles(projectId),
        getReports(projectId),
      ]);
      setProject(nextProject);
      setFiles(Array.isArray(nextFiles) ? nextFiles : []);
      setReports(Array.isArray(nextReports) ? nextReports : []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "无法加载项目详情");
    } finally {
      setLoading(false);
    }
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
      try {
        const payload = JSON.parse(event.data) as { progress: number; status: string };
        setBatchProgress(payload.progress);
        if (payload.status === "completed" || payload.status === "failed") void load();
      } catch {
        message.warning("实时进度消息格式无效,页面将继续刷新状态");
      }
    };
    socket.onerror = () => message.warning("实时进度连接中断,页面仍会刷新获取状态");
    return () => socket.close();
  }, [batchId]);

  const uploadProps: UploadProps = {
    multiple: true,
    beforeUpload: () => false,
    fileList: selectedFiles,
    onChange: ({ fileList }) => {
      setSelectedFiles(fileList);
      setResumableBatch(null);
      void findResumableBatch(fileList.map((item) => item.originFileObj).filter(Boolean) as File[]);
    },
    showUploadList: true,
  };

  const findResumableBatch = async (localFiles: File[]) => {
    if (!localFiles.length) return;
    const expected = localFiles.map((file) => `${file.name}:${file.size}:${file.lastModified}`).sort().join("|");
    setResuming(true);
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index);
      if (!key?.startsWith("vision-capital-ai:batch:") || !key.endsWith(":manifest")) continue;
      try {
        const manifest = JSON.parse(localStorage.getItem(key) ?? "") as { batchId: string; files: string[] };
        if (manifest.files.slice().sort().join("|") !== expected) continue;
        const candidate = await getFileBatch(manifest.batchId);
        if (candidate.status === "uploading") {
          setBatchId(candidate.id);
          setResumableBatch(candidate);
          message.info("已恢复未完成的上传批次");
          setResuming(false);
          return;
        }
      } catch {
        localStorage.removeItem(key);
      }
    }
    setResuming(false);
  };

  const submitBatch = async () => {
    if (submitting || resuming) return;
    const localFiles = selectedFiles.map((item) => item.originFileObj).filter(Boolean) as File[];
    if (!localFiles.length) return;
    setSubmitting(true);
    try {
      const batch = resumableBatch ?? await createFileBatch(projectId, localFiles);
      if (!resumableBatch) {
        localStorage.setItem(`vision-capital-ai:batch:${batch.id}:manifest`, JSON.stringify({ batchId: batch.id, files: localFiles.map((file) => `${file.name}:${file.size}:${file.lastModified}`) }));
      }
      setBatchId(batch.id);
      const availableFiles = new Map<string, typeof batch.files>();
      for (const fileRecord of batch.files) {
        const key = `${fileRecord.filename}:${fileRecord.size}`;
        availableFiles.set(key, [...(availableFiles.get(key) ?? []), fileRecord]);
      }
      for (let index = 0; index < localFiles.length; index += 1) {
        const localFile = localFiles[index];
        const key = `${localFile.name}:${localFile.size}`;
        const matchingFiles = availableFiles.get(key) ?? [];
        const matchingFile = matchingFiles.shift();
        const session = matchingFile ? batch.upload_sessions.find((item) => item.file_id === matchingFile.id) : undefined;
        if (!session || !localFile) throw new Error("上传会话与文件数量不一致");
        if (session.upload_mode === "direct" && session.upload_url) {
          try {
            const response = await fetch(session.upload_url, { method: "PUT", body: localFile, headers: { "Content-Type": localFile.type || "application/octet-stream" } });
            if (!response.ok) throw new Error(`直传失败: ${localFile.name}`);
          } catch {
            await uploadBatchFileContent(batch.id, session.file_id, localFile);
          }
        } else if (session.upload_mode === "multipart" && session.part_size) {
          const resumeKey = `vision-capital-ai:batch:${batch.id}:file:${session.file_id}:parts`;
          let storedParts: Record<string, string> = {};
          try {
            storedParts = JSON.parse(localStorage.getItem(resumeKey) ?? "{}") as Record<string, string>;
          } catch {
            localStorage.removeItem(resumeKey);
          }
          const serverParts = await getUploadedParts(batch.id, session.file_id);
          for (const part of serverParts) storedParts[String(part.part_number)] = part.etag;
          const parts: Array<{ part_number: number; etag: string }> = Object.entries(storedParts).map(([partNumber, etag]) => ({ part_number: Number(partNumber), etag }));
          for (let offset = 0, partNumber = 1; offset < localFile.size; offset += session.part_size, partNumber += 1) {
            if (storedParts[String(partNumber)]) continue;
            const url = await getMultipartPartUrl(batch.id, session.file_id, partNumber);
            const chunk = localFile.slice(offset, offset + session.part_size);
            let etag = "";
            try {
              const response = await fetch(url, { method: "PUT", body: chunk });
              if (!response.ok) throw new Error(`分片上传失败: ${localFile.name}`);
              etag = response.headers.get("ETag")?.replace(/"/g, "") ?? "";
              if (!etag) throw new Error("R2 未返回 ETag");
            } catch {
              etag = (await uploadMultipartPartContent(batch.id, session.file_id, partNumber, chunk)).etag;
            }
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
      localStorage.removeItem(`vision-capital-ai:batch:${batch.id}:manifest`);
      setSelectedFiles([]);
      setResumableBatch(null);
      message.success("批次已提交,解析正在后台进行");
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "批量上传失败");
    } finally {
      setSubmitting(false);
    }
  };

  const submitQuestion = async () => {
    if (!question.trim() || chatting) return;
    setChatting(true);
    try {
      setChatResult(await askProject(projectId, question.trim()));
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "问答请求失败");
    } finally {
      setChatting(false);
    }
  };

  const submitReport = async () => {
    if (generating) return;
    setGenerating(true);
    try {
      await generateReport(projectId);
      await load();
      message.success("报告已生成");
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "报告生成失败");
    } finally {
      setGenerating(false);
    }
  };

  const retryParse = async (fileId: string) => {
    setRetryingFileId(fileId);
    try {
      await retryFile(fileId);
      await load();
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "重试解析失败");
    } finally {
      setRetryingFileId(null);
    }
  };

  const submitPreset = (value: string) => { setQuestion(value); void submitQuestion(); };
  const toggleTask = (id: string) => setTasks((items) => items.map((item) => item.id === id ? { ...item, done: !item.done } : item));
  const statusLabel = project ? ({ pre_investment: "投前", in_progress: "投中", post_investment: "投后", rejected: "已放弃", exited: "已退出" } as Record<string, string>)[project.investment_status] ?? project.stage : "投前";
  const overview = <div className="detail-stack"><Row gutter={[16, 16]}><Col xs={24} md={8}><Metric icon={<FileTextOutlined />} label="项目阶段" value={statusLabel} /></Col><Col xs={24} md={8}><Metric icon={<SafetyCertificateOutlined />} label="资料完整度" value={(files.length ? Math.round(files.filter((file) => file.parse_status === "completed").length / files.length * 100) : 0) + "%"} /></Col><Col xs={24} md={8}><Metric icon={<RobotOutlined />} label="AI 洞察" value={chatResult ? "已生成" : "待研究"} /></Col></Row><Card className="workspace-panel" title="项目摘要"><Descriptions column={{ xs: 1, md: 2 }} items={[{ key: "company", label: "公司", children: project?.company_name }, { key: "industry", label: "行业", children: project?.industry }, { key: "stage", label: "当前轮次", children: project?.stage }, { key: "status", label: "投资状态", children: statusLabel }]} /><Typography.Paragraph className="project-description">{project?.description || "还没有项目摘要。上传 BP 或补充项目介绍后,AI 会自动建立项目画像。"}</Typography.Paragraph></Card></div>;
  const materials = <div className="detail-stack"><Card className="workspace-panel material-upload" title="资料中心" extra={<Space><Upload {...uploadProps} disabled={submitting || resuming}><Button disabled={submitting || resuming}>选择文件</Button></Upload><Button type="primary" loading={submitting || resuming} disabled={!selectedFiles.length || submitting || resuming} onClick={() => void submitBatch()}>开始解析</Button></Space>}><Typography.Paragraph type="secondary">支持 BP、财报、合同、尽调报告、行业研究、新闻和图片扫描件。上传后会自动进入 OCR、表格提取和 AI 结构化流程。</Typography.Paragraph>{batchId && <div className="batch-progress"><Progress percent={batchProgress} status={batchProgress === 100 ? "success" : "active"} /><span>解析进度实时同步</span></div>}<List dataSource={files} locale={{ emptyText: "还没有项目资料" }} renderItem={(file) => <List.Item><List.Item.Meta avatar={<span className="file-type-icon"><FileTextOutlined /></span>} title={file.filename} description={file.parse_stage + " · " + file.content_type + (file.parse_error ? " · " + file.parse_error : "")} /><Space><Tag color={file.parse_status === "completed" ? "green" : file.parse_status === "failed" ? "red" : "gold"}>{file.parse_status}</Tag><Progress percent={file.progress} size="small" className="file-progress" />{file.parse_status === "failed" && <Button type="link" loading={retryingFileId === file.id} onClick={() => void retryParse(file.id)}>重试</Button>}</Space></List.Item>} /></Card></div>;
  const analysis = <div className="detail-stack"><Card className="workspace-panel analysis-panel" title="AI 分析" extra={<Tag color="cyan">基于项目资料</Tag>}><div className="preset-grid"><Button onClick={() => submitPreset("总结这家公司的核心投资亮点、商业模式和主要风险")}>投资亮点与风险 <ArrowRightOutlined /></Button><Button onClick={() => submitPreset("分析公司的市场空间、竞争格局和增长驱动")}>市场与竞争格局 <ArrowRightOutlined /></Button><Button onClick={() => submitPreset("从财务、团队和合规角度列出尽调问题")}>生成尽调问题清单 <ArrowRightOutlined /></Button></div><Input.TextArea rows={4} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="也可以直接问项目,例如:这家公司是否值得进入下一轮尽调?" /><Button type="primary" loading={chatting} disabled={!question.trim()} onClick={() => void submitQuestion()} className="analysis-submit">发起分析</Button>{chatResult && <div className="analysis-result"><span className="eyebrow">AI 研究结论</span><Typography.Paragraph>{chatResult.answer}</Typography.Paragraph><Typography.Title level={5}>引用资料</Typography.Title><List dataSource={chatResult.citations} renderItem={(citation) => <List.Item><List.Item.Meta title={citation.filename} description={citation.content} /></List.Item>} /></div>}</Card></div>;
  const diligence = <div className="detail-stack"><Alert message="尽调清单会随着 AI 分析和资料解析结果持续更新" description="先完成关键资料上传,再按优先级推进待办事项。" type="info" showIcon /><Card className="workspace-panel" title="尽调与任务"><List dataSource={tasks} renderItem={(task) => <List.Item actions={[<Button type="link" onClick={() => toggleTask(task.id)}>{task.done ? "标记未完成" : "完成"}</Button>]}><List.Item.Meta avatar={task.done ? <CheckCircleOutlined className="task-complete" /> : <span className="task-number">!</span>} title={<span className={task.done ? "task-done" : ""}>{task.label}</span>} description={task.done ? "已完成" : "等待你的确认"} /></List.Item>} /></Card></div>;
  const reportsPanel = <div className="detail-stack"><Card className="workspace-panel" title="报告与决策" extra={<Button type="primary" loading={generating} onClick={() => void submitReport()}>生成投研报告</Button>}><Typography.Paragraph type="secondary">将项目资料、AI 分析、风险和尽调问题汇总为一份可供决策会使用的报告。</Typography.Paragraph><List dataSource={reports} locale={{ emptyText: "暂时没有报告" }} renderItem={(report) => <List.Item><List.Item.Meta avatar={<span className="report-icon"><FileTextOutlined /></span>} title={report.title} description={report.content.slice(0, 280)} /><Button type="link">查看报告</Button></List.Item>} /></Card></div>;
  const monitoring = <div className="detail-stack"><Row gutter={[16, 16]}><Col xs={24} md={8}><Metric label="经营状态" value="持续跟踪" /></Col><Col xs={24} md={8}><Metric label="本期风险" value="待更新" /></Col><Col xs={24} md={8}><Metric label="下次跟进" value="本周" /></Col></Row><Card className="workspace-panel" title="投后监控"><Alert message="投后监控即将开始" description="当前项目还没有经营数据或定期回访记录。完成投资决策后,可在这里持续跟踪经营、财务和风险变化。" type="warning" showIcon /><div className="monitoring-placeholder"><SafetyCertificateOutlined /><span>经营数据、关键指标和风险预警会集中展示在这里</span></div></Card></div>;
  return <div className="page-stack project-detail-page"><Card className="project-hero" loading={loading}><div><span className="eyebrow">INVESTMENT PROJECT</span><Typography.Title level={1}>{project?.name ?? "项目详情"}</Typography.Title><Typography.Paragraph>{project?.company_name} · {project?.industry}</Typography.Paragraph></div><Tag color="blue">{statusLabel}</Tag></Card><Tabs className="project-tabs" items={[{ key: "overview", label: "项目总览", children: overview }, { key: "materials", label: "资料中心", children: materials }, { key: "analysis", label: "AI 分析", children: analysis }, { key: "diligence", label: "尽调与任务", children: diligence }, { key: "reports", label: "报告与决策", children: reportsPanel }, { key: "monitoring", label: "投后监控", children: monitoring }]} /></div>;
}

function Metric({ icon, label, value }: { icon?: React.ReactNode; label: string; value: string }) { return <Card className="metric-card detail-metric"><div className="detail-metric-icon">{icon}</div><Typography.Text type="secondary">{label}</Typography.Text><Typography.Title level={3}>{value}</Typography.Title></Card>; }
