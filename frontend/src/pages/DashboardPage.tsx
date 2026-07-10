import { ArrowRightOutlined, CheckCircleOutlined, ClockCircleOutlined, FileTextOutlined, PlusOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Button, Card, Col, Empty, List, Progress, Row, Statistic, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDashboardSummary } from "../api/services";
import type { DashboardSummary, Project } from "../types";

const statusLabel: Record<string, string> = { pre_investment: "投前", in_progress: "投中", post_investment: "投后", rejected: "已放弃", exited: "已退出" };

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    void getDashboardSummary().then(setSummary).catch((reason: any) => message.error(reason?.response?.data?.detail ?? "无法加载工作台"));
  }, []);

  const projects = summary?.recent_projects ?? [];
  const featured = projects[0];
  const needsAttention = summary ? Math.max(summary.total_files - summary.completed_files, 0) : 0;

  return (
    <div className="page-stack workspace-page">
      <section className="workspace-welcome">
        <div><span className="eyebrow">TUESDAY · 20 MAY 2025</span><Typography.Title level={1}>下午好，李正宇</Typography.Title><Typography.Paragraph>把握信息优势，做更好的投资决策。</Typography.Paragraph></div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate("/projects")}>新建投资项目</Button>
      </section>
      <Row gutter={[14, 14]} className="metric-row">
        <Col xs={24} sm={12} lg={6}><Card className="metric-card"><Statistic title="在投项目" value={summary?.total_projects ?? 0} prefix={<FileTextOutlined />} /><span className="metric-note">全部项目组合</span></Card></Col>
        <Col xs={24} sm={12} lg={6}><Card className="metric-card"><Statistic title="待决策事项" value={needsAttention} prefix={<ClockCircleOutlined />} /><span className="metric-note accent-note">需要你的关注</span></Card></Col>
        <Col xs={24} sm={12} lg={6}><Card className="metric-card"><Statistic title="本月新增项目" value={projects.length} prefix={<PlusOutlined />} /><span className="metric-note">来自最近项目</span></Card></Col>
        <Col xs={24} sm={12} lg={6}><Card className="metric-card"><Statistic title="已解析资料" value={summary?.completed_files ?? 0} prefix={<SafetyCertificateOutlined />} /><span className="metric-note success-note">知识库持续更新</span></Card></Col>
      </Row>
      <Row gutter={[18, 18]}>
        <Col xs={24} xl={16}>
          <Card className="workspace-panel stage-panel" title="投资全流程概览" extra={<Button type="link" onClick={() => navigate("/projects")}>查看全部项目 <ArrowRightOutlined /></Button>}>
            <div className="stage-line">
              <StageItem label="Pre-投资" sub="初筛与尽调" value={summary?.pre_investment_projects ?? 0} active />
              <StageItem label="投资中" sub="跟踪与决策" value={summary?.in_progress_projects ?? 0} />
              <StageItem label="投后管理" sub="经营与监控" value={summary?.post_investment_projects ?? 0} />
              <StageItem label="已退出" sub="复盘与归档" value={0} />
            </div>
          </Card>
          <Card className="workspace-panel featured-project-panel" title="重点项目" extra={<Button type="link" onClick={() => navigate("/projects")}>查看全部 <ArrowRightOutlined /></Button>}>
            {featured ? <FeaturedProject project={featured} onOpen={() => navigate(`/projects/${featured.id}`)} /> : <Empty description="创建第一个投资项目，开始构建你的投研工作台" />} 
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card className="workspace-panel insight-panel" title="AI 今日洞察" extra={<Button type="link" onClick={() => navigate("/assistant")}>更多 <ArrowRightOutlined /></Button>}>
            <List size="small" dataSource={projects.slice(0, 3)} locale={{ emptyText: "项目资料解析后，AI 洞察会出现在这里" }} renderItem={(project, index) => <List.Item><List.Item.Meta avatar={<span className={`insight-icon insight-${index}`}>{index === 0 ? "◒" : index === 1 ? "⌁" : "!"}</span>} title={index === 0 ? `${project.name} 资料解析完成` : `${project.name} 需要补充信息`} description={index === 0 ? "2 小时前 · 已建立知识索引" : "等待更多资料进入项目空间"} /></List.Item>} />
          </Card>
          <Card className="workspace-panel todo-panel" title="待办事项" extra={<Button type="link">更多</Button>}>
            <TodoRow done={false} text={featured ? `查看 ${featured.name} 的项目资料` : "创建第一个投资项目"} />
            <TodoRow done={needsAttention === 0} text={needsAttention ? "确认待解析的项目资料" : "确认本周投资报告"} />
            <TodoRow done={false} text="准备下一次投资决策会议" />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

function StageItem({ label, sub, value, active = false }: { label: string; sub: string; value: number; active?: boolean }) {
  return <div className={`stage-item ${active ? "stage-active" : ""}`}><div className="stage-icon">{active ? "↗" : "·"}</div><Typography.Text strong>{label}</Typography.Text><Typography.Text type="secondary">{sub}</Typography.Text><strong className="stage-value">{value}<small> 项目</small></strong></div>;
}

function FeaturedProject({ project, onOpen }: { project: Project; onOpen: () => void }) {
  return <div className="featured-project"><div className="project-avatar">{project.company_name.slice(0, 1)}</div><div className="featured-main"><div className="project-kicker"><Tag color="cyan">{statusLabel[project.investment_status] ?? project.investment_status}</Tag><span>{project.stage}</span></div><Typography.Title level={2}>{project.name}</Typography.Title><Typography.Paragraph ellipsis={{ rows: 2 }}>{project.description || `${project.company_name} · ${project.industry}`}</Typography.Paragraph><div className="project-facts"><span><small>公司</small>{project.company_name}</span><span><small>行业</small>{project.industry}</span><span><small>更新</small>{new Date(project.updated_at).toLocaleDateString()}</span></div><Button type="primary" onClick={onOpen}>进入项目工作区 <ArrowRightOutlined /></Button></div><div className="featured-score"><Typography.Text type="secondary">研究进度</Typography.Text><div className="score-number">{project.investment_status === "post_investment" ? "82" : "68"}<small>%</small></div><Progress percent={project.investment_status === "post_investment" ? 82 : 68} showInfo={false} strokeColor="#3aa99b" /><Typography.Text type="secondary">综合评分 · 待 AI 更新</Typography.Text></div></div>;
}

function TodoRow({ done, text }: { done: boolean; text: string }) {
  return <div className={`todo-row ${done ? "todo-done" : ""}`}><span className="todo-check">{done ? <CheckCircleOutlined /> : ""}</span><span>{text}</span><span className="todo-date">{done ? "已完成" : "今天"}</span></div>;
}
