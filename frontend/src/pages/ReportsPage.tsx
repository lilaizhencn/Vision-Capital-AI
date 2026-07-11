import { Alert, Card, Empty, List, Spin, Typography, message } from "antd";
import { useEffect, useState } from "react";

import { getRecentReports } from "../api/services";
import type { Report } from "../types";

export function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void getRecentReports()
      .then((items) => setReports(Array.isArray(items) ? items : []))
      .catch((reason: any) => {
        const detail = reason?.response?.data?.detail ?? "无法加载报告列表";
        setError(detail);
        message.error(detail);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card className="glass-card">
      <Typography.Title level={2}>投研报告中心</Typography.Title>
      <Typography.Paragraph>在项目详情页生成的 AI 报告会成为这里的统一内容来源。</Typography.Paragraph>
      {error && <Alert type="error" showIcon title={error} />}
      {loading ? <Spin /> : reports.length ? (
        <List
          dataSource={reports}
          renderItem={(report) => <List.Item><List.Item.Meta title={report.title} description={<><Typography.Text type="secondary">{new Date(report.created_at).toLocaleString()}</Typography.Text><Typography.Paragraph ellipsis={{ rows: 3 }}>{report.content}</Typography.Paragraph></>} /></List.Item>}
        />
      ) : <Empty description="暂时没有投研报告" />}
    </Card>
  );
}
