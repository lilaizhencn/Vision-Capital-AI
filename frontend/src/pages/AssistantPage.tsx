import { Button, Card, Empty, List, Spin, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getProjects } from "../api/services";
import type { Project } from "../types";

export function AssistantPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void getProjects()
      .then((items) => setProjects(Array.isArray(items) ? items : []))
      .catch((reason: any) => message.error(reason?.response?.data?.detail ?? "无法加载项目列表"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card className="glass-card">
      <Typography.Title level={2}>AI 问答入口</Typography.Title>
      <Typography.Paragraph>
        选择具体项目后即可基于知识库资料发起问答。
      </Typography.Paragraph>
      {loading ? <Spin /> : projects.length ? <List dataSource={projects} renderItem={(project) => <List.Item actions={[<Button type="link" onClick={() => navigate(`/projects/${project.id}`)}>进入项目问答</Button>]}><List.Item.Meta title={project.name} description={`${project.company_name} · ${project.industry}`} /></List.Item>} /> : <Empty description="请先创建投资项目" />}
    </Card>
  );
}
