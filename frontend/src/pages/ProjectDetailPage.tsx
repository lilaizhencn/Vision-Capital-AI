import { ArrowRightOutlined, CheckCircleOutlined, CloudDownloadOutlined, FileTextOutlined, LinkOutlined, RobotOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Descriptions, Form, Input, List, Modal, Progress, Row, Select, Space, Switch, Tabs, Tag, Typography, Upload, message } from "antd";
import type { UploadFile, UploadProps } from "antd";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { askProject, completeFileBatch, completeMultipart, createFileBatch, createMonitoringUpdate, enrichProjectResearch, generateReport, getFileBatch, getMonitoringUpdates, getMultipartPartUrl, getProject, getProjectFiles, getProjectTasks, getReports, getResearchWorkspace, getUploadedParts, retryFile, updateProjectTask, updateResearchSettings, uploadBatchFileContent, uploadMultipartPartContent } from "../api/services";
import type { ChatResponse, MonitoringUpdate, Project, ProjectFile, ProjectTask, Report, ResearchWorkspace } from "../types";

type BatchProgressPayload = {
  progress: number;
  status: string;
  files?: Array<{
    id: string;
    filename: string;
    status: string;
    stage: string;
    progress: number;
    error?: string | null;
  }>;
};

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [monitoring, setMonitoring] = useState<MonitoringUpdate[]>([]);
  const [monitoringOpen, setMonitoringOpen] = useState(false);
  const [savingMonitoring, setSavingMonitoring] = useState(false);
  const [reportPreview, setReportPreview] = useState<Report | null>(null);
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
  const [tasks, setTasks] = useState<ProjectTask[]>([]);
  const [research, setResearch] = useState<ResearchWorkspace>({ requirements: [], sources: [], enrichment_running: false, auto_enabled: true, status: "idle" });
  const [researching, setResearching] = useState(false);

  const load = async () => {
    try {
      const [nextProject, nextFiles, nextReports, nextMonitoring, nextTasks, nextResearch] = await Promise.all([
        getProject(projectId),
        getProjectFiles(projectId),
        getReports(projectId),
        getMonitoringUpdates(projectId),
        getProjectTasks(projectId),
        getResearchWorkspace(projectId),
      ]);
      setProject(nextProject);
      setFiles(Array.isArray(nextFiles) ? nextFiles : []);
      setReports(Array.isArray(nextReports) ? nextReports : []);
      setMonitoring(Array.isArray(nextMonitoring) ? nextMonitoring : []);
      setTasks(Array.isArray(nextTasks) ? nextTasks : []);
      setResearch(nextResearch);
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "无法加载项目详情");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [projectId]);

  useEffect(() => {
    if (!research.enrichment_running) return;
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [projectId, research.enrichment_running]);

  const applyBatchProgress = (payload: BatchProgressPayload, activeBatchId: string) => {
    if (!payload.files?.length) return;
    setFiles((currentFiles) => {
      const nextFiles = [...currentFiles];
      const indexById = new Map(nextFiles.map((file, index) => [file.id, index]));
      for (const update of payload.files ?? []) {
        const existingIndex = indexById.get(update.id);
        if (existingIndex === undefined) {
          indexById.set(update.id, nextFiles.length);
          nextFiles.push({
            id: update.id,
            project_id: projectId,
            batch_id: activeBatchId,
            filename: update.filename,
            content_type: "application/octet-stream",
            size: 0,
            r2_object_key: "",
            parse_status: update.status,
            parse_stage: update.stage,
            progress: update.progress,
            parse_error: update.error ?? null,
            retry_count: 0,
            created_at: new Date().toISOString(),
          });
          continue;
        }
        nextFiles[existingIndex] = {
          ...nextFiles[existingIndex],
          parse_status: update.status,
          parse_stage: update.stage,
          progress: update.progress,
          parse_error: update.error ?? null,
        };
      }
      return nextFiles;
    });
  };

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
        const payload = JSON.parse(event.data) as BatchProgressPayload;
        setBatchProgress(payload.progress);
        applyBatchProgress(payload, batchId);
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
          setFiles((currentFiles) => [...currentFiles.filter((file) => file.batch_id !== candidate.id), ...candidate.files]);
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
      setFiles((currentFiles) => [...currentFiles.filter((file) => file.batch_id !== batch.id), ...batch.files]);
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

  const submitQuestion = async (override?: string) => {
    const nextQuestion = (override ?? question).trim();
    if (!nextQuestion || chatting) return;
    setChatting(true);
    try {
      setQuestion(nextQuestion);
      setChatResult(await askProject(projectId, nextQuestion));
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

  const submitMonitoring = async (values: Omit<MonitoringUpdate, "id" | "project_id" | "created_at">) => {
    if (savingMonitoring) return;
    setSavingMonitoring(true);
    try {
      await createMonitoringUpdate(projectId, values);
      setMonitoringOpen(false);
      await load();
      message.success("监控记录已保存");
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "监控记录保存失败");
    } finally {
      setSavingMonitoring(false);
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

  const submitPreset = (value: string) => { void submitQuestion(value); };
  const runResearch = async () => {
    if (researching) return;
    setResearching(true);
    try {
      await enrichProjectResearch(projectId);
      message.success("公开资料补全任务已启动，可信来源会自动进入解析流程");
      window.setTimeout(() => void load(), 2500);
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "公开资料检索启动失败");
    } finally {
      setResearching(false);
    }
  };
  const toggleResearchAutoUpdate = async (enabled: boolean) => {
    setResearch((current) => ({ ...current, auto_enabled: enabled }));
    try {
      setResearch(await updateResearchSettings(projectId, enabled));
      message.success(enabled ? "已开启每周自动研究更新" : "已暂停自动研究更新");
    } catch (error: any) {
      setResearch((current) => ({ ...current, auto_enabled: !enabled }));
      message.error(error?.response?.data?.detail ?? "自动更新设置保存失败");
    }
  };
  const toggleTask = async (task: ProjectTask) => {
    const nextDone = !task.done;
    setTasks((items) => items.map((item) => item.id === task.id ? { ...item, done: nextDone } : item));
    try {
      await updateProjectTask(projectId, task.id, nextDone);
    } catch (error: any) {
      setTasks((items) => items.map((item) => item.id === task.id ? { ...item, done: task.done } : item));
      message.error(error?.response?.data?.detail ?? "任务状态保存失败");
    }
  };
  const statusLabel = project ? ({ pre_investment: "投前", in_progress: "投中", post_investment: "投后", rejected: "已放弃", exited: "已退出" } as Record<string, string>)[project.investment_status] ?? project.stage : "投前";
  const overview = <div className="detail-stack"><Row gutter={[16, 16]}><Col xs={24} md={8}><Metric icon={<FileTextOutlined />} label="项目阶段" value={statusLabel} /></Col><Col xs={24} md={8}><Metric icon={<SafetyCertificateOutlined />} label="资料完整度" value={(files.length ? Math.round(files.filter((file) => file.parse_status === "completed").length / files.length * 100) : 0) + "%"} /></Col><Col xs={24} md={8}><Metric icon={<RobotOutlined />} label="AI 洞察" value={chatResult ? "已生成" : "待研究"} /></Col></Row><Card className="workspace-panel" title="项目摘要"><Descriptions column={{ xs: 1, md: 2 }} items={[{ key: "company", label: "公司", children: project?.company_name }, { key: "industry", label: "行业", children: project?.industry }, { key: "stage", label: "当前轮次", children: project?.stage }, { key: "status", label: "投资状态", children: statusLabel }]} /><Typography.Paragraph className="project-description">{project?.description || "还没有项目摘要。上传 BP 或补充项目介绍后,AI 会自动建立项目画像。"}</Typography.Paragraph></Card></div>;
  const materials = <div className="detail-stack"><Card className="workspace-panel material-upload" title="资料中心" extra={<Space><Upload {...uploadProps} disabled={submitting || resuming}><Button disabled={submitting || resuming}>选择文件</Button></Upload><Button type="primary" loading={submitting || resuming} disabled={!selectedFiles.length || submitting || resuming} onClick={() => void submitBatch()}>开始解析</Button></Space>}><Typography.Paragraph type="secondary">支持 BP、财报、合同、尽调报告、行业研究、新闻和图片扫描件。上传后会自动进入 OCR、表格提取和 AI 结构化流程。</Typography.Paragraph>{batchId && <div className="batch-progress"><Progress percent={batchProgress} status={batchProgress === 100 ? "success" : "active"} /><span>解析进度实时同步</span></div>}<List dataSource={files} locale={{ emptyText: "还没有项目资料" }} renderItem={(file) => <List.Item><List.Item.Meta avatar={<span className="file-type-icon"><FileTextOutlined /></span>} title={<Space>{file.filename}{file.source_kind === "public_research" && <Tag color="blue">公开研究</Tag>}</Space>} description={<Space direction="vertical" size={2}><span>{file.parse_stage + " · " + file.content_type + (file.parse_error ? " · " + file.parse_error : "")}</span>{file.source_url && <a href={file.source_url} target="_blank" rel="noreferrer"><LinkOutlined /> 查看原始来源</a>}</Space>} /><Space><Tag color={file.parse_status === "completed" ? "green" : file.parse_status === "failed" ? "red" : "gold"}>{file.parse_status}</Tag><Progress percent={file.progress} size="small" className="file-progress" />{file.parse_status === "failed" && <Button type="link" loading={retryingFileId === file.id} onClick={() => void retryParse(file.id)}>重试</Button>}</Space></List.Item>} /></Card></div>;
  const analysis = <div className="detail-stack"><Card className="workspace-panel analysis-panel" title="AI 分析" extra={<Tag color="cyan">综合项目资料与可信公开来源</Tag>}><div className="preset-grid"><Button onClick={() => submitPreset("总结这家公司的核心投资亮点、商业模式和主要风险")}>投资亮点与风险 <ArrowRightOutlined /></Button><Button onClick={() => submitPreset("分析公司的市场空间、竞争格局和增长驱动")}>市场与竞争格局 <ArrowRightOutlined /></Button><Button onClick={() => submitPreset("从财务、团队和合规角度列出尽调问题")}>生成尽调问题清单 <ArrowRightOutlined /></Button></div><Input.TextArea rows={4} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="也可以直接问项目,例如:这家公司是否值得进入下一轮尽调?" /><Button type="primary" loading={chatting} disabled={!question.trim()} onClick={() => void submitQuestion()} className="analysis-submit">发起分析</Button>{chatResult && <div className="analysis-result"><Space wrap><span className="eyebrow">AI 研究结论</span><Tag color={chatResult.confidence === "high" ? "green" : chatResult.confidence === "medium" ? "gold" : "red"}>置信度 {chatResult.confidence === "high" ? "高" : chatResult.confidence === "medium" ? "中" : "低"}</Tag>{chatResult.evidence_control_passed === true && <Tag color="green">证据门禁已通过</Tag>}{chatResult.evidence_control_passed === false && <Tag color="orange">未通过，已保守降级</Tag>}</Space><Typography.Paragraph className="analysis-answer">{chatResult.answer}</Typography.Paragraph>{chatResult.missing_evidence.length > 0 && <Alert type="warning" showIcon message="结论仍受资料缺口限制" description={<ul className="evidence-missing-list">{chatResult.missing_evidence.map((item) => <li key={item}>{item}</li>)}</ul>} />}<Typography.Title level={5}>引用资料</Typography.Title><List dataSource={chatResult.citations} renderItem={(citation) => <List.Item><List.Item.Meta title={<Space>{citation.filename}{citation.source_quality && <Tag>{citation.source_quality}</Tag>}</Space>} description={<><div>{citation.content}</div>{citation.source_url && <a href={citation.source_url} target="_blank" rel="noreferrer"><LinkOutlined /> 原始公开来源</a>}</>} /></List.Item>} /></div>}</Card></div>;
  const diligence = <div className="detail-stack"><Alert message="尽调清单会随着 AI 分析和资料解析结果持续更新" description="先完成关键资料上传,再按优先级推进待办事项。" type="info" showIcon /><Card className="workspace-panel" title="尽调与任务"><List dataSource={tasks} locale={{ emptyText: "暂无尽调任务" }} renderItem={(task) => <List.Item actions={[<Button type="link" onClick={() => void toggleTask(task)}>{task.done ? "标记未完成" : "完成"}</Button>]}><List.Item.Meta avatar={task.done ? <CheckCircleOutlined className="task-complete" /> : <span className="task-number">!</span>} title={<span className={task.done ? "task-done" : ""}>{task.label}</span>} description={task.done ? "已完成" : "等待你的确认"} /></List.Item>} /></Card></div>;
  const researchPanel = <div className="detail-stack"><Card className="workspace-panel research-summary" title="资料完整性" extra={<Space wrap><Space size={6}><Typography.Text type="secondary">每周自动更新</Typography.Text><Switch size="small" checked={research.auto_enabled} onChange={(checked) => void toggleResearchAutoUpdate(checked)} /></Space><Button type="primary" icon={<CloudDownloadOutlined />} loading={researching || research.enrichment_running} disabled={research.enrichment_running} onClick={() => void runResearch()}>联网补全可信资料</Button></Space>}><Typography.Paragraph type="secondary">系统会从权威监管、交易所、政府和国际机构检索公开资料。无法可靠补全的内容会保留在缺口清单，等待人工上传。</Typography.Paragraph><Space wrap className="research-runtime"><Tag color={research.status === "failed" ? "red" : research.enrichment_running ? "processing" : "green"}>{research.status === "running" ? "正在研究" : research.status === "queued" ? "等待执行" : research.status === "failed" ? "上次运行失败" : "运行正常"}</Tag>{research.last_research_at && <Typography.Text type="secondary">最近更新 {new Date(research.last_research_at).toLocaleString("zh-CN")}</Typography.Text>}{research.next_research_at && research.auto_enabled && <Typography.Text type="secondary">下次计划 {new Date(research.next_research_at).toLocaleString("zh-CN")}</Typography.Text>}</Space>{research.last_error && <Alert type="error" showIcon message="公开研究任务未完成" description={research.last_error} />}<div className="evidence-grid">{research.requirements.map((item) => <div className={`evidence-card evidence-${item.status}`} key={item.id}><div className="evidence-card-head"><strong>{item.label}</strong><Tag color={item.status === "covered" ? "green" : item.status === "partial" ? "gold" : "red"}>{item.status === "covered" ? "已覆盖" : item.status === "partial" ? "部分覆盖" : "资料缺失"}</Tag></div><p>{item.reason}</p><span>建议资料：{item.suggested_document}</span></div>)}</div></Card><Card className="workspace-panel" title="公开研究来源"><List dataSource={research.sources} locale={{ emptyText: "尚未执行公开资料检索" }} renderItem={(source) => <List.Item actions={[<a href={source.url} target="_blank" rel="noreferrer">查看来源</a>]}><List.Item.Meta avatar={<span className="file-type-icon"><LinkOutlined /></span>} title={<Space>{source.title}<Tag color={source.status === "ingested" ? "green" : source.status === "failed" ? "red" : "gold"}>{source.status === "ingested" ? "已入库" : source.status === "review_required" ? "待人工复核" : source.status === "failed" ? "抓取失败" : "已发现"}</Tag></Space>} description={`${source.publisher} · ${source.evidence_category}${source.error ? ` · ${source.error}` : ""}`} /></List.Item>} /></Card></div>;
  const reportsPanel = <div className="detail-stack"><Card className="workspace-panel" title="报告与决策" extra={<Button type="primary" loading={generating} onClick={() => void submitReport()}>生成投研报告</Button>}><Typography.Paragraph type="secondary">将项目资料、AI 分析、风险和尽调问题汇总为一份可供决策会使用的报告。</Typography.Paragraph><List dataSource={reports} locale={{ emptyText: "暂时没有报告" }} renderItem={(report) => <List.Item><List.Item.Meta avatar={<span className="report-icon"><FileTextOutlined /></span>} title={report.title} description={report.content.slice(0, 280)} /><Button type="link" onClick={() => setReportPreview(report)}>查看报告</Button></List.Item>} /></Card></div>;
  const latestRisk = monitoring.find((item) => item.risk_level !== "normal");
  const monitoringPanel = <div className="detail-stack"><Row gutter={[16, 16]}><Col xs={24} md={8}><Metric label="监控记录" value={`${monitoring.length} 条`} /></Col><Col xs={24} md={8}><Metric label="本期风险" value={latestRisk ? (latestRisk.risk_level === "high" ? "高风险" : "需关注") : "正常"} /></Col><Col xs={24} md={8}><Metric label="最近更新" value={monitoring[0] ? new Date(monitoring[0].created_at).toLocaleDateString("zh-CN") : "暂无"} /></Col></Row><Card className="workspace-panel" title="投后监控" extra={<Button type="primary" onClick={() => setMonitoringOpen(true)}>新增监控记录</Button>}><List dataSource={monitoring} locale={{ emptyText: "还没有监控记录，请先录入经营指标或风险变化" }} renderItem={(item) => <List.Item><List.Item.Meta title={<Space><span>{item.metric_name}</span><Tag color={item.risk_level === "high" ? "red" : item.risk_level === "watch" ? "gold" : "green"}>{item.risk_level === "high" ? "高风险" : item.risk_level === "watch" ? "需关注" : "正常"}</Tag></Space>} description={`${item.metric_value}${item.metric_unit} · ${item.note || "暂无备注"}`} /><Typography.Text type="secondary">{new Date(item.created_at).toLocaleDateString("zh-CN")}</Typography.Text></List.Item>} /></Card></div>;
  return <div className="page-stack project-detail-page"><Card className="project-hero" loading={loading}><div><span className="eyebrow">INVESTMENT PROJECT</span><Typography.Title level={1}>{project?.name ?? "项目详情"}</Typography.Title><Typography.Paragraph>{project?.company_name} · {project?.industry}</Typography.Paragraph></div><Tag color="blue">{statusLabel}</Tag></Card><Tabs className="project-tabs" items={[{ key: "overview", label: "项目总览", children: overview }, { key: "materials", label: "资料中心", children: materials }, { key: "research", label: "研究与缺口", children: researchPanel }, { key: "analysis", label: "AI 分析", children: analysis }, { key: "diligence", label: "尽调与任务", children: diligence }, { key: "reports", label: "报告与决策", children: reportsPanel }, { key: "monitoring", label: "投后监控", children: monitoringPanel }]} /><Modal title="新增投后监控记录" open={monitoringOpen} onCancel={() => setMonitoringOpen(false)} footer={null}><Form layout="vertical" onFinish={(values) => void submitMonitoring(values)}><Form.Item name="metric_name" label="指标名称" rules={[{ required: true, message: "请输入指标名称" }]}><Input placeholder="例如：月度收入" /></Form.Item><Form.Item name="metric_value" label="指标值" rules={[{ required: true, message: "请输入指标值" }]}><Input placeholder="例如：320" /></Form.Item><Form.Item name="metric_unit" label="单位"><Input placeholder="例如：万元" /></Form.Item><Form.Item name="risk_level" label="风险状态" initialValue="normal"><Select options={[{ value: "normal", label: "正常" }, { value: "watch", label: "需关注" }, { value: "high", label: "高风险" }]} /></Form.Item><Form.Item name="note" label="备注"><Input.TextArea rows={3} /></Form.Item><Button type="primary" htmlType="submit" loading={savingMonitoring} block>保存记录</Button></Form></Modal><Modal title={reportPreview?.title} open={Boolean(reportPreview)} onCancel={() => setReportPreview(null)} footer={null}><Typography.Paragraph style={{ whiteSpace: "pre-wrap" }}>{reportPreview?.content}</Typography.Paragraph></Modal></div>;
}

function Metric({ icon, label, value }: { icon?: React.ReactNode; label: string; value: string }) { return <Card className="metric-card detail-metric"><div className="detail-metric-icon">{icon}</div><Typography.Text type="secondary">{label}</Typography.Text><Typography.Title level={3}>{value}</Typography.Title></Card>; }
