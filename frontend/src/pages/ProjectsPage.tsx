import { AppstoreOutlined, BarsOutlined, PlusOutlined, RightOutlined } from "@ant-design/icons";
import { Button, Card, Empty, Form, Input, Modal, Segmented, Select, Table, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createProject, getProjects } from "../api/services";
import type { InvestmentStatus, Project } from "../types";

const statusOptions = [
  { value: "pre_investment", label: "投前" },
  { value: "in_progress", label: "投中" },
  { value: "post_investment", label: "投后" },
  { value: "rejected", label: "已放弃" },
  { value: "exited", label: "已退出" },
];
const statusColor: Record<InvestmentStatus, string> = { pre_investment: "cyan", in_progress: "blue", post_investment: "green", rejected: "default", exited: "default" };

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"list" | "board">("list");
  const [status, setStatus] = useState<InvestmentStatus | "all">("all");
  const navigate = useNavigate();
  const load = async () => { const data = await getProjects(); setProjects(Array.isArray(data) ? data : []); };
  useEffect(() => { void load().catch((error: any) => message.error(error?.response?.data?.detail ?? "无法加载投资项目")); }, []);
  const visibleProjects = useMemo(() => status === "all" ? projects : projects.filter((project) => project.investment_status === status), [projects, status]);
  const onCreate = async (values: Partial<Project>) => {
    try { await createProject(values); setOpen(false); await load(); message.success("项目已创建"); } catch (error: any) { message.error(error?.response?.data?.detail ?? "创建失败"); }
  };
  return <div className="page-stack">
    <div className="section-heading"><div><span className="eyebrow">PORTFOLIO</span><Typography.Title level={1}>投资项目</Typography.Title><Typography.Paragraph type="secondary">从初筛到投后监控,沿着一条投资主线推进所有项目。</Typography.Paragraph></div><Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>新建项目</Button></div>
    <div className="toolbar-row"><Select value={status} onChange={setStatus} options={[{ value: "all", label: "全部阶段" }, ...statusOptions]} style={{ minWidth: 140 }} /><Segmented value={view} onChange={(value) => setView(value as "list" | "board")} options={[{ value: "list", icon: <BarsOutlined />, label: "列表" }, { value: "board", icon: <AppstoreOutlined />, label: "看板" }]} /></div>
    {view === "list" ? <Card className="workspace-panel project-table-panel"><Table rowKey="id" dataSource={visibleProjects} locale={{ emptyText: <Empty description="还没有投资项目" /> }} columns={[{ title: "项目", dataIndex: "name", render: (value: string, record: Project) => <Button type="link" className="project-link" onClick={() => navigate("/projects/" + record.id)}><strong>{value}</strong><small>{record.company_name}</small></Button> }, { title: "行业", dataIndex: "industry" }, { title: "轮次 / 阶段", dataIndex: "stage" }, { title: "投资阶段", dataIndex: "investment_status", render: (value: InvestmentStatus) => <Tag color={statusColor[value]}>{statusOptions.find((item) => item.value === value)?.label ?? value}</Tag> }, { title: "更新时间", dataIndex: "updated_at", render: (value: string) => new Date(value).toLocaleDateString() }, { title: "", render: (_: unknown, record: Project) => <Button type="text" icon={<RightOutlined />} onClick={() => navigate("/projects/" + record.id)} /> }]} /></Card> : <div className="project-board">{statusOptions.slice(0, 3).map((stage) => <Card key={stage.value} className="board-column" title={<span>{stage.label}<small>{projects.filter((project) => project.investment_status === stage.value).length}</small></span>}><div className="board-items">{visibleProjects.filter((project) => project.investment_status === stage.value).map((project) => <button className="board-project" key={project.id} onClick={() => navigate("/projects/" + project.id)}><span className="project-avatar mini-avatar">{project.company_name.slice(0, 1)}</span><span><strong>{project.name}</strong><small>{project.company_name}</small></span><RightOutlined /></button>)}</div></Card>)}</div>}
    <Modal title="新建投资项目" open={open} footer={null} onCancel={() => setOpen(false)}><Form layout="vertical" onFinish={onCreate}><Form.Item name="name" label="项目名称" rules={[{ required: true }]}><Input placeholder="例如:星河机器人" /></Form.Item><Form.Item name="company_name" label="公司名称" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="industry" label="行业" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="stage" label="轮次 / 阶段" rules={[{ required: true }]}><Input placeholder="例如:A 轮" /></Form.Item><Form.Item name="description" label="项目简介"><Input.TextArea rows={4} /></Form.Item><Form.Item name="investment_status" label="投资阶段" initialValue="pre_investment"><Select options={statusOptions} /></Form.Item><Button type="primary" htmlType="submit" block>保存项目</Button></Form></Modal>
  </div>;
}
