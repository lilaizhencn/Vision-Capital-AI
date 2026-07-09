import { Button, Card, Form, Input, Modal, Select, Space, Table, Tag, message } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createProject, getProjects } from "../api/services";
import type { Project } from "../types";

const statusOptions = [
  { value: "pre_investment", label: "投前" },
  { value: "in_progress", label: "投中" },
  { value: "post_investment", label: "投后" },
  { value: "rejected", label: "已放弃" },
  { value: "exited", label: "已退出" },
];

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();

  const load = async () => setProjects(await getProjects());

  useEffect(() => {
    void load();
  }, []);

  const onCreate = async (values: Partial<Project>) => {
    try {
      await createProject(values);
      setOpen(false);
      await load();
      message.success("项目已创建");
    } catch (error: any) {
      message.error(error.response?.data?.detail ?? "创建失败");
    }
  };

  return (
    <div className="page-stack">
      <Space style={{ justifyContent: "space-between", width: "100%" }}>
        <h2>投资项目</h2>
        <Button type="primary" onClick={() => setOpen(true)}>
          新建项目
        </Button>
      </Space>
      <Card className="glass-card">
        <Table
          rowKey="id"
          dataSource={projects}
          columns={[
            { title: "项目名称", dataIndex: "name" },
            { title: "公司", dataIndex: "company_name" },
            { title: "行业", dataIndex: "industry" },
            { title: "阶段", dataIndex: "stage" },
            {
              title: "状态",
              dataIndex: "investment_status",
              render: (value: string) => <Tag color="blue">{value}</Tag>,
            },
            {
              title: "操作",
              render: (_, record: Project) => (
                <Button type="link" onClick={() => navigate(`/projects/${record.id}`)}>
                  查看详情
                </Button>
              ),
            },
          ]}
        />
      </Card>
      <Modal title="新建投资项目" open={open} footer={null} onCancel={() => setOpen(false)}>
        <Form layout="vertical" onFinish={onCreate}>
          <Form.Item name="name" label="项目名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="company_name" label="公司名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="industry" label="行业" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="stage" label="轮次 / 阶段" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="描述"><Input.TextArea rows={4} /></Form.Item>
          <Form.Item name="investment_status" label="投资状态" initialValue="pre_investment">
            <Select options={statusOptions} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>保存项目</Button>
        </Form>
      </Modal>
    </div>
  );
}

