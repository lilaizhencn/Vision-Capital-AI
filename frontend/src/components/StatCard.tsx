import { Card, Statistic } from "antd";

interface StatCardProps {
  title: string;
  value: number;
  suffix?: string;
}

export function StatCard({ title, value, suffix }: StatCardProps) {
  return (
    <Card className="glass-card">
      <Statistic title={title} value={value} suffix={suffix} />
    </Card>
  );
}

