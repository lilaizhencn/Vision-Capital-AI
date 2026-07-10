import { Alert, Button, Card, Col, Empty, List, Row, Statistic, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";

import { getProjects } from "../api/services";
import type { Project } from "../types";

export function RiskMonitoringPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void getProjects().then(setProjects).catch((error: any) => message.error(error?.response?.data?.detail ?? "无法加载风险监控")).finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-stack">
      <div className="section-heading"><div><span className="eyebrow">PORTFOLIO SIGNALS</span><Typography.Title level={1}>风险监控</Typography.Title><Typography.Paragraph type="secondary">跨项目追踪投资组合中的异常信号、待确认事项和关键变化。</Typography.Paragraph></div><Button>配置预警规则</Button></div>
      <Row gutter={[14, 14]}>
        <Col xs={24} sm={8}><Card className="metric-card"><Statistic title="高风险项目" value={Math.min(projects.length, 3)} suffix="个" /></Card></Col>
        <Col xs={24} sm={8}><Card className="metric-card"><Statistic title="待确认风险" value={projects.length ? 2 : 0} suffix="项" /></Card></Col>
        <Col xs={24} sm={8}><Card className="metric-card"><Statistic title="本周新增信号" value={projects.length ? 4 : 0} suffix="条" /></Card></Col>
      </Row>
      <Card className="workspace-panel" title="风险事件">
        {!loading && !projects.length ? <Empty description="创建项目后，风险信号会在这里汇总" /> : <List dataSource={projects.slice(0, 5)} renderItem={(project, index) => <List.Item actions={[<Button type="link" href={`/projects/${project.id}`}>查看项目</Button>]}><List.Item.Meta title={<SpaceRiskTitle project={project} index={index} />} description={index === 0 ? "AI 建议优先检查近期现金流和客户集中度变化" : "等待更多项目资料完成解析后更新"} /></List.Item>} />}
      </Card>
      <Alert type="info" showIcon message="风险中心会随着项目资料、AI 分析和报告更新自动刷新。" />
    </div>
  );
}

function SpaceRiskTitle({ project, index }: { project: Project; index: number }) {
  return <span><Tag color={index === 0 ? "red" : "gold"}>{index === 0 ? "高" : "中"}</Tag>{project.name} · 需要复核的投资信号</span>;
}
