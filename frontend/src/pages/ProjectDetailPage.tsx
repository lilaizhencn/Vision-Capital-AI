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
    { id: "team", label: "Ã¨Â¡Â¥Ã¥â€¦â€¦Ã¦Â Â¸Ã¥Â¿Æ’Ã¥â€ºÂ¢Ã©ËœÅ¸Ã¥Â±Â¥Ã¥Å½â€ Ã¤Â¸Å½Ã¥Ë†â€ Ã¥Â·Â¥", done: false },
    { id: "market", label: "Ã§Â¡Â®Ã¨Â®Â¤Ã¥Â¸â€šÃ¥Å“ÂºÃ¨Â§â€žÃ¦Â¨Â¡Ã¤Â¸Å½Ã§Â«Å¾Ã¤Âºâ€°Ã¦Â Â¼Ã¥Â±â‚¬Ã¥Ââ€¡Ã¨Â®Â¾", done: false },
    { id: "finance", label: "Ã¥Â¤ÂÃ¦Â Â¸Ã¦Å“â‚¬Ã¦â€“Â°Ã¤Â¸â‚¬Ã§â€°Ë†Ã¨Â´Â¢Ã¥Å Â¡Ã©Â¢â€žÃ¦Âµâ€¹", done: true },
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
      message.error(error?.response?.data?.detail ?? "Ã¦â€”Â Ã¦Â³â€¢Ã¥Å Â Ã¨Â½Â½Ã©Â¡Â¹Ã§â€ºÂ®Ã¨Â¯Â¦Ã¦Æ’â€¦");
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
        message.warning("Ã¥Â®Å¾Ã¦â€”Â¶Ã¨Â¿â€ºÃ¥ÂºÂ¦Ã¦Â¶Ë†Ã¦ÂÂ¯Ã¦Â Â¼Ã¥Â¼ÂÃ¦â€”Â Ã¦â€¢Ë†Ã¯Â¼Å’Ã©Â¡ÂµÃ©ÂÂ¢Ã¥Â°â€ Ã§Â»Â§Ã§Â»Â­Ã¥Ë†Â·Ã¦â€“Â°Ã§Å Â¶Ã¦â‚¬Â");
      }
    };
    socket.onerror = () => message.warning("Ã¥Â®Å¾Ã¦â€”Â¶Ã¨Â¿â€ºÃ¥ÂºÂ¦Ã¨Â¿Å¾Ã¦Å½Â¥Ã¤Â¸Â­Ã¦â€“Â­Ã¯Â¼Å’Ã©Â¡ÂµÃ©ÂÂ¢Ã¤Â»ÂÃ¤Â¼Å¡Ã¥Ë†Â·Ã¦â€“Â°Ã¨Å½Â·Ã¥Ââ€“Ã§Å Â¶Ã¦â‚¬Â");
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
          message.info("Ã¥Â·Â²Ã¦ÂÂ¢Ã¥Â¤ÂÃ¦Å“ÂªÃ¥Â®Å’Ã¦Ë†ÂÃ§Å¡â€žÃ¤Â¸Å Ã¤Â¼Â Ã¦â€°Â¹Ã¦Â¬Â¡");
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
        if (!session || !localFile) throw new Error("Ã¤Â¸Å Ã¤Â¼Â Ã¤Â¼Å¡Ã¨Â¯ÂÃ¤Â¸Å½Ã¦â€“â€¡Ã¤Â»Â¶Ã¦â€¢Â°Ã©â€¡ÂÃ¤Â¸ÂÃ¤Â¸â‚¬Ã¨â€¡Â´");
        if (session.upload_mode === "direct" && session.upload_url) {
          try {
            const response = await fetch(session.upload_url, { method: "PUT", body: localFile, headers: { "Content-Type": localFile.type || "application/octet-stream" } });
            if (!response.ok) throw new Error(`Ã§â€ºÂ´Ã¤Â¼Â Ã¥Â¤Â±Ã¨Â´Â¥: ${localFile.name}`);
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
              if (!response.ok) throw new Error(`Ã¥Ë†â€ Ã§â€°â€¡Ã¤Â¸Å Ã¤Â¼Â Ã¥Â¤Â±Ã¨Â´Â¥: ${localFile.name}`);
              etag = response.headers.get("ETag")?.replace(/"/g, "") ?? "";
              if (!etag) throw new Error("R2 Ã¦Å“ÂªÃ¨Â¿â€Ã¥â€ºÅ¾ ETag");
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
      message.success("Ã¦â€°Â¹Ã¦Â¬Â¡Ã¥Â·Â²Ã¦ÂÂÃ¤ÂºÂ¤Ã¯Â¼Å’Ã¨Â§Â£Ã¦Å¾ÂÃ¦Â­Â£Ã¥Å“Â¨Ã¥ÂÅ½Ã¥ÂÂ°Ã¨Â¿â€ºÃ¨Â¡Å’");
      await load();
    } catch (error) {
      message.error(error instanceof Error ? error.message : "Ã¦â€°Â¹Ã©â€¡ÂÃ¤Â¸Å Ã¤Â¼Â Ã¥Â¤Â±Ã¨Â´Â¥");
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
      message.error(error?.response?.data?.detail ?? "Ã©â€”Â®Ã§Â­â€Ã¨Â¯Â·Ã¦Â±â€šÃ¥Â¤Â±Ã¨Â´Â¥");
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
      message.success("Ã¦Å Â¥Ã¥â€˜Å Ã¥Â·Â²Ã§â€Å¸Ã¦Ë†Â");
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "Ã¦Å Â¥Ã¥â€˜Å Ã§â€Å¸Ã¦Ë†ÂÃ¥Â¤Â±Ã¨Â´Â¥");
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
      message.error(error?.response?.data?.detail ?? "Ã©â€¡ÂÃ¨Â¯â€¢Ã¨Â§Â£Ã¦Å¾ÂÃ¥Â¤Â±Ã¨Â´Â¥");
    } finally {
      setRetryingFileId(null);
    }
  };

  const submitPreset = (value: string) => { setQuestion(value); void submitQuestion(); };
  const toggleTask = (id: string) => setTasks((items) => items.map((item) => item.id === id ? { ...item, done: !item.done } : item));
  const statusLabel = project ? ({ pre_investment: "æŠ•å‰", in_progress: "æŠ•ä¸­", post_investment: "æŠ•åŽ", rejected: "å·²æ”¾å¼ƒ", exited: "å·²é€€å‡º" } as Record<string, string>)[project.investment_status] ?? project.stage : "æŠ•å‰";
  const overview = <div className="detail-stack"><Row gutter={[16, 16]}><Col xs={24} md={8}><Metric icon={<FileTextOutlined />} label="é¡¹ç›®é˜¶æ®µ" value={statusLabel} /></Col><Col xs={24} md={8}><Metric icon={<SafetyCertificateOutlined />} label="èµ„æ–™å®Œæ•´åº¦" value={(files.length ? Math.round(files.filter((file) => file.parse_status === "completed").length / files.length * 100) : 0) + "%"} /></Col><Col xs={24} md={8}><Metric icon={<RobotOutlined />} label="AI æ´žå¯Ÿ" value={chatResult ? "å·²ç”Ÿæˆ" : "å¾…ç ”ç©¶"} /></Col></Row><Card className="workspace-panel" title="é¡¹ç›®æ‘˜è¦"><Descriptions column={{ xs: 1, md: 2 }} items={[{ key: "company", label: "å…¬å¸", children: project?.company_name }, { key: "industry", label: "è¡Œä¸š", children: project?.industry }, { key: "stage", label: "å½“å‰è½®æ¬¡", children: project?.stage }, { key: "status", label: "æŠ•èµ„çŠ¶æ€", children: statusLabel }]} /><Typography.Paragraph className="project-description">{project?.description || "è¿˜æ²¡æœ‰é¡¹ç›®æ‘˜è¦ã€‚ä¸Šä¼  BP æˆ–è¡¥å……é¡¹ç›®ä»‹ç»åŽï¼ŒAI ä¼šè‡ªåŠ¨å»ºç«‹é¡¹ç›®ç”»åƒã€‚"}</Typography.Paragraph></Card></div>;
  const materials = <div className="detail-stack"><Card className="workspace-panel material-upload" title="èµ„æ–™ä¸­å¿ƒ" extra={<Space><Upload {...uploadProps} disabled={submitting || resuming}><Button disabled={submitting || resuming}>é€‰æ‹©æ–‡ä»¶</Button></Upload><Button type="primary" loading={submitting || resuming} disabled={!selectedFiles.length || submitting || resuming} onClick={() => void submitBatch()}>å¼€å§‹è§£æž</Button></Space>}><Typography.Paragraph type="secondary">æ”¯æŒ BPã€è´¢æŠ¥ã€åˆåŒã€å°½è°ƒæŠ¥å‘Šã€è¡Œä¸šç ”ç©¶ã€æ–°é—»å’Œå›¾ç‰‡æ‰«æä»¶ã€‚ä¸Šä¼ åŽä¼šè‡ªåŠ¨è¿›å…¥ OCRã€è¡¨æ ¼æå–å’Œ AI ç»“æž„åŒ–æµç¨‹ã€‚</Typography.Paragraph>{batchId && <div className="batch-progress"><Progress percent={batchProgress} status={batchProgress === 100 ? "success" : "active"} /><span>è§£æžè¿›åº¦å®žæ—¶åŒæ­¥</span></div>}<List dataSource={files} locale={{ emptyText: "è¿˜æ²¡æœ‰é¡¹ç›®èµ„æ–™" }} renderItem={(file) => <List.Item><List.Item.Meta avatar={<span className="file-type-icon"><FileTextOutlined /></span>} title={file.filename} description={file.parse_stage + " Â· " + file.content_type + (file.parse_error ? " Â· " + file.parse_error : "")} /><Space><Tag color={file.parse_status === "completed" ? "green" : file.parse_status === "failed" ? "red" : "gold"}>{file.parse_status}</Tag><Progress percent={file.progress} size="small" className="file-progress" />{file.parse_status === "failed" && <Button type="link" loading={retryingFileId === file.id} onClick={() => void retryParse(file.id)}>é‡è¯•</Button>}</Space></List.Item>} /></Card></div>;
  const analysis = <div className="detail-stack"><Card className="workspace-panel analysis-panel" title="AI åˆ†æž" extra={<Tag color="cyan">åŸºäºŽé¡¹ç›®èµ„æ–™</Tag>}><div className="preset-grid"><Button onClick={() => submitPreset("æ€»ç»“è¿™å®¶å…¬å¸çš„æ ¸å¿ƒæŠ•èµ„äº®ç‚¹ã€å•†ä¸šæ¨¡å¼å’Œä¸»è¦é£Žé™©")}>æŠ•èµ„äº®ç‚¹ä¸Žé£Žé™© <ArrowRightOutlined /></Button><Button onClick={() => submitPreset("åˆ†æžå…¬å¸çš„å¸‚åœºç©ºé—´ã€ç«žäº‰æ ¼å±€å’Œå¢žé•¿é©±åŠ¨")}>å¸‚åœºä¸Žç«žäº‰æ ¼å±€ <ArrowRightOutlined /></Button><Button onClick={() => submitPreset("ä»Žè´¢åŠ¡ã€å›¢é˜Ÿå’Œåˆè§„è§’åº¦åˆ—å‡ºå°½è°ƒé—®é¢˜")}>ç”Ÿæˆå°½è°ƒé—®é¢˜æ¸…å• <ArrowRightOutlined /></Button></div><Input.TextArea rows={4} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="ä¹Ÿå¯ä»¥ç›´æŽ¥é—®é¡¹ç›®ï¼Œä¾‹å¦‚ï¼šè¿™å®¶å…¬å¸æ˜¯å¦å€¼å¾—è¿›å…¥ä¸‹ä¸€è½®å°½è°ƒï¼Ÿ" /><Button type="primary" loading={chatting} disabled={!question.trim()} onClick={() => void submitQuestion()} className="analysis-submit">å‘èµ·åˆ†æž</Button>{chatResult && <div className="analysis-result"><span className="eyebrow">AI ç ”ç©¶ç»“è®º</span><Typography.Paragraph>{chatResult.answer}</Typography.Paragraph><Typography.Title level={5}>å¼•ç”¨èµ„æ–™</Typography.Title><List dataSource={chatResult.citations} renderItem={(citation) => <List.Item><List.Item.Meta title={citation.filename} description={citation.content} /></List.Item>} /></div>}</Card></div>;
  const diligence = <div className="detail-stack"><Alert message="å°½è°ƒæ¸…å•ä¼šéšç€ AI åˆ†æžå’Œèµ„æ–™è§£æžç»“æžœæŒç»­æ›´æ–°" description="å…ˆå®Œæˆå…³é”®èµ„æ–™ä¸Šä¼ ï¼Œå†æŒ‰ä¼˜å…ˆçº§æŽ¨è¿›å¾…åŠžäº‹é¡¹ã€‚" type="info" showIcon /><Card className="workspace-panel" title="å°½è°ƒä¸Žä»»åŠ¡"><List dataSource={tasks} renderItem={(task) => <List.Item actions={[<Button type="link" onClick={() => toggleTask(task.id)}>{task.done ? "æ ‡è®°æœªå®Œæˆ" : "å®Œæˆ"}</Button>]}><List.Item.Meta avatar={task.done ? <CheckCircleOutlined className="task-complete" /> : <span className="task-number">!</span>} title={<span className={task.done ? "task-done" : ""}>{task.label}</span>} description={task.done ? "å·²å®Œæˆ" : "ç­‰å¾…ä½ çš„ç¡®è®¤"} /></List.Item>} /></Card></div>;
  const reportsPanel = <div className="detail-stack"><Card className="workspace-panel" title="æŠ¥å‘Šä¸Žå†³ç­–" extra={<Button type="primary" loading={generating} onClick={() => void submitReport()}>ç”ŸæˆæŠ•ç ”æŠ¥å‘Š</Button>}><Typography.Paragraph type="secondary">å°†é¡¹ç›®èµ„æ–™ã€AI åˆ†æžã€é£Žé™©å’Œå°½è°ƒé—®é¢˜æ±‡æ€»ä¸ºä¸€ä»½å¯ä¾›å†³ç­–ä¼šä½¿ç”¨çš„æŠ¥å‘Šã€‚</Typography.Paragraph><List dataSource={reports} locale={{ emptyText: "æš‚æ—¶æ²¡æœ‰æŠ¥å‘Š" }} renderItem={(report) => <List.Item><List.Item.Meta avatar={<span className="report-icon"><FileTextOutlined /></span>} title={report.title} description={report.content.slice(0, 280)} /><Button type="link">æŸ¥çœ‹æŠ¥å‘Š</Button></List.Item>} /></Card></div>;
  const monitoring = <div className="detail-stack"><Row gutter={[16, 16]}><Col xs={24} md={8}><Metric label="ç»è¥çŠ¶æ€" value="æŒç»­è·Ÿè¸ª" /></Col><Col xs={24} md={8}><Metric label="æœ¬æœŸé£Žé™©" value="å¾…æ›´æ–°" /></Col><Col xs={24} md={8}><Metric label="ä¸‹æ¬¡è·Ÿè¿›" value="æœ¬å‘¨" /></Col></Row><Card className="workspace-panel" title="æŠ•åŽç›‘æŽ§"><Alert message="æŠ•åŽç›‘æŽ§å³å°†å¼€å§‹" description="å½“å‰é¡¹ç›®è¿˜æ²¡æœ‰ç»è¥æ•°æ®æˆ–å®šæœŸå›žè®¿è®°å½•ã€‚å®ŒæˆæŠ•èµ„å†³ç­–åŽï¼Œå¯åœ¨è¿™é‡ŒæŒç»­è·Ÿè¸ªç»è¥ã€è´¢åŠ¡å’Œé£Žé™©å˜åŒ–ã€‚" type="warning" showIcon /><div className="monitoring-placeholder"><SafetyCertificateOutlined /><span>ç»è¥æ•°æ®ã€å…³é”®æŒ‡æ ‡å’Œé£Žé™©é¢„è­¦ä¼šé›†ä¸­å±•ç¤ºåœ¨è¿™é‡Œ</span></div></Card></div>;
  return <div className="page-stack project-detail-page"><Card className="project-hero" loading={loading}><div><span className="eyebrow">INVESTMENT PROJECT</span><Typography.Title level={1}>{project?.name ?? "é¡¹ç›®è¯¦æƒ…"}</Typography.Title><Typography.Paragraph>{project?.company_name} Â· {project?.industry}</Typography.Paragraph></div><Tag color="blue">{statusLabel}</Tag></Card><Tabs className="project-tabs" items={[{ key: "overview", label: "é¡¹ç›®æ€»è§ˆ", children: overview }, { key: "materials", label: "èµ„æ–™ä¸­å¿ƒ", children: materials }, { key: "analysis", label: "AI åˆ†æž", children: analysis }, { key: "diligence", label: "å°½è°ƒä¸Žä»»åŠ¡", children: diligence }, { key: "reports", label: "æŠ¥å‘Šä¸Žå†³ç­–", children: reportsPanel }, { key: "monitoring", label: "æŠ•åŽç›‘æŽ§", children: monitoring }]} /></div>;
}

function Metric({ icon, label, value }: { icon?: React.ReactNode; label: string; value: string }) { return <Card className="metric-card detail-metric"><div className="detail-metric-icon">{icon}</div><Typography.Text type="secondary">{label}</Typography.Text><Typography.Title level={3}>{value}</Typography.Title></Card>; }


