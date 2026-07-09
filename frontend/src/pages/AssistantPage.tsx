import { Card, Typography } from "antd";

export function AssistantPage() {
  return (
    <Card className="glass-card">
      <Typography.Title level={2}>AI 问答入口</Typography.Title>
      <Typography.Paragraph>
        选择具体项目后即可基于知识库资料发起问答，这个页面作为系统级入口提示用户先进入项目视图。
      </Typography.Paragraph>
    </Card>
  );
}

