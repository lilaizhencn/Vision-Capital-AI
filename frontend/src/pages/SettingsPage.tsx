import { Card, Descriptions } from "antd";

export function SettingsPage() {
  return (
    <Card className="glass-card" title="系统设置">
      <Descriptions column={1}>
        <Descriptions.Item label="API Base URL">{import.meta.env.VITE_API_BASE_URL}</Descriptions.Item>
        <Descriptions.Item label="存储策略">默认优先 Cloudflare R2,未配置时回退到本地存储。</Descriptions.Item>
        <Descriptions.Item label="模型接入">兼容 OpenAI / DeepSeek 等 OpenAI-compatible API。</Descriptions.Item>
      </Descriptions>
    </Card>
  );
}
