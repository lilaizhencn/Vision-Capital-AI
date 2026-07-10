import { Alert, Card, Col, Empty, List, Row, Statistic, Tag, Typography, message } from "antd";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";

import { getMonitoringUpdates, getProjects } from "../api/services";
import type { MonitoringUpdate, Project } from "../types";

export function RiskMonitoringPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [updates, setUpdates] = useState<Array<MonitoringUpdate & { project: Project }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void getProjects().then(async (items) => {
      const nextProjects = Array.isArray(items) ? items : [];
      setProjects(nextProjects);
      const entries = await Promise.all(nextProjects.map(async (project) => (await getMonitoringUpdates(project.id)).map((item) => ({ ...item, project }))));
      setUpdates(entries.flat().sort((left, right) => right.created_at.localeCompare(left.created_at)));
    }).catch((error: any) => message.error(error?.response?.data?.detail ?? "无法加载风险监控")).finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-stack">
      <div className="section-heading"><div><span className="eyebrow">PORTFOLIO SIGNALS</span><Typography.Title level={1}>风险监控</Typography.Title><Typography.Paragraph type="secondary">跨项目追踪投资组合中的异常信号、待确认事项和关键变化。</Typography.Paragraph></div></div>
      <Row gutter={[14, 14]}>
        <Col xs={24} sm={8}><Card className="metric-card"><Statistic title="高风险项目" value={new Set(updates.filter((item) => item.risk_level === "high").map((item) => item.project_id)).size} suffix="个" /></Card></Col>
        <Col xs={24} sm={8}><Card className="metric-card"><Statistic title="待确认风险" value={updates.filter((item) => item.risk_level === "watch").length} suffix="项" /></Card></Col>
        <Col xs={24} sm={8}><Card className="metric-card"><Statistic title="监控记录" value={updates.length} suffix="条" /></Card></Col>
      </Row>
      <Card className="workspace-panel" title="风险事件">
        {!loading && !projects.length ? <Empty description="创建项目后,风险信号会在这里汇总" /> : <List dataSource={updates.slice(0, 10)} locale={{ emptyText: "还没有投后监控记录" }} renderItem={(item) => <List.Item actions={[<Link to={`/projects/${item.project.id}`}>查看项目</Link>]}><List.Item.Meta title={<SpaceRiskTitle project={item.project} risk={item.risk_level} />} description={`${item.metric_name}: ${item.metric_value}${item.metric_unit} · ${item.note || "暂无备注"}`} /></List.Item>} />}
      </Card>
      <Alert type="info" showIcon message="风险中心会随着项目资料、AI 分析和报告更新自动刷新。" />
    </div>
  );
}

function SpaceRiskTitle({ project, risk }: { project: Project; risk: MonitoringUpdate["risk_level"] }) {
  return <span><Tag color={risk === "high" ? "red" : risk === "watch" ? "gold" : "green"}>{risk === "high" ? "高" : risk === "watch" ? "关注" : "正常"}</Tag>{project.name} · 投后监控记录</span>;
}
