import { Card, Typography } from "antd";

export function ReportsPage() {
  return (
    <Card className="glass-card">
      <Typography.Title level={2}>投研报告中心</Typography.Title>
      <Typography.Paragraph>在项目详情页生成的 AI 报告会成为这里的统一内容来源。</Typography.Paragraph>
    </Card>
  );
}

