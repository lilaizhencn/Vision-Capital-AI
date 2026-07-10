import { Alert, Card, Col, List, Row, Typography, message } from "antd";
import { useEffect, useState } from "react";

import { getDashboardSummary } from "../api/services";
import { StatCard } from "../components/StatCard";
import type { DashboardSummary } from "../types";

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    void getDashboardSummary().then(setSummary).catch((reason: any) => message.error(reason?.response?.data?.detail ?? "无法加载 Dashboard"));
  }, []);

  return (
    <div className="page-stack">
      <div className="hero-strip">
        <Typography.Title level={2}>投资组合总览</Typography.Title>
        <Typography.Paragraph>
          从项目、文档、知识片段到 AI 洞察，把投前、投中、投后的研究信息放进同一个面板。
        </Typography.Paragraph>
      </div>
      {!summary && <Alert type="info" showIcon message="正在加载投资组合数据" />}
      <Row gutter={[16, 16]}>
        <Col span={6}><StatCard title="项目总数" value={summary?.total_projects ?? 0} /></Col>
        <Col span={6}><StatCard title="投前项目" value={summary?.pre_investment_projects ?? 0} /></Col>
        <Col span={6}><StatCard title="投中项目" value={summary?.in_progress_projects ?? 0} /></Col>
        <Col span={6}><StatCard title="投后项目" value={summary?.post_investment_projects ?? 0} /></Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card title="最近项目" className="glass-card">
            <List
              dataSource={summary?.recent_projects ?? []}
              renderItem={(project) => (
                <List.Item>
                  <List.Item.Meta title={project.name} description={`${project.company_name} · ${project.industry}`} />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="最近报告" className="glass-card">
            <List
              dataSource={summary?.recent_reports ?? []}
              renderItem={(report) => (
                <List.Item>
                  <List.Item.Meta title={report.title} description={new Date(report.created_at).toLocaleString()} />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
