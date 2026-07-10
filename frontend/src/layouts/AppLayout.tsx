import {
  AppstoreOutlined,
  BarChartOutlined,
  ExperimentOutlined,
  FileTextOutlined,
  SafetyCertificateOutlined,
  SearchOutlined,
  SettingOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { Button, Drawer, Input, Layout, Menu, Select, Space, Typography, message } from "antd";
import { PropsWithChildren, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { askProject, getProjects } from "../api/services";
import type { Project } from "../types";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/", icon: <BarChartOutlined />, label: "工作台" },
  { key: "/projects", icon: <AppstoreOutlined />, label: "投资项目" },
  { key: "/assistant", icon: <ExperimentOutlined />, label: "AI 研究室" },
  { key: "/reports", icon: <FileTextOutlined />, label: "报告中心" },
  { key: "/risk", icon: <SafetyCertificateOutlined />, label: "风险监控" },
  { key: "/settings", icon: <SettingOutlined />, label: "数据与设置" },
];

function GlobalAssistant({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<string>();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string>();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    void getProjects().then((items) => {
      const nextProjects = Array.isArray(items) ? items : [];
      setProjects(nextProjects);
      if (!projectId && nextProjects[0]) setProjectId(nextProjects[0].id);
    });
  }, [open, projectId]);

  const submit = async () => {
    if (!projectId || !question.trim() || loading) return;
    setLoading(true);
    try {
      const result = await askProject(projectId, question.trim());
      setAnswer(result.answer);
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "AI 助手暂时无法回答");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Drawer open={open} onClose={onClose} width={420} title="AI 投研助手" className="assistant-drawer">
      <div className="drawer-intro">
        <span className="eyebrow">CONTEXTUAL RESEARCH</span>
        <Typography.Title level={3}>把问题变成下一步行动</Typography.Title>
        <Typography.Paragraph type="secondary">选择一个项目,AI 会基于项目资料回答,并返回可追溯的分析上下文。</Typography.Paragraph>
      </div>
      <Space direction="vertical" size={14} style={{ width: "100%" }}>
        <Select
          value={projectId}
          onChange={setProjectId}
          placeholder="选择项目上下文"
          style={{ width: "100%" }}
          options={projects.map((project) => ({ value: project.id, label: `${project.name} · ${project.company_name}` }))}
        />
        <Input.TextArea
          rows={5}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="例如:这个项目当前最大的现金流风险是什么?"
        />
        <Button type="primary" block loading={loading} disabled={!projectId || !question.trim()} onClick={() => void submit()}>
          开始分析
        </Button>
        {answer && <div className="assistant-answer"><Typography.Text strong>AI 回答</Typography.Text><Typography.Paragraph>{answer}</Typography.Paragraph></div>}
      </Space>
    </Drawer>
  );
}

export function AppLayout({ children }: PropsWithChildren) {
  const navigate = useNavigate();
  const location = useLocation();
  const [assistantOpen, setAssistantOpen] = useState(false);

  const searchProjects = async (value: string) => {
    const query = value.trim().toLowerCase();
    if (!query) return;
    try {
      const projects = await getProjects();
      const match = (Array.isArray(projects) ? projects : []).find((project) => `${project.name} ${project.company_name}`.toLowerCase().includes(query));
      if (match) navigate(`/projects/${match.id}`);
      else message.info("没有找到匹配的项目");
    } catch (error: any) {
      message.error(error?.response?.data?.detail ?? "搜索项目失败");
    }
  };

  const logout = () => {
    localStorage.removeItem("vision_capital_ai_token");
    navigate("/login");
  };

  return (
    <Layout className="app-shell">
      <Sider width={232} className="app-sider" breakpoint="lg" collapsedWidth={0}>
        <div className="brand-block" onClick={() => navigate("/")} role="button" tabIndex={0}>
          <div className="brand-mark">V</div>
          <div>
            <Typography.Title level={3}>Vision Capital</Typography.Title>
            <Typography.Text>Investment intelligence</Typography.Text>
          </div>
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[location.pathname === "/" ? "/" : `/${location.pathname.split("/")[1]}`]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
        <div className="sider-footer"><div className="sider-status"><span className="status-dot" />AI 系统运行正常</div><Typography.Text>© 2026 Vision Capital AI</Typography.Text></div>
      </Sider>
      <Layout>
        <Header className="app-header">
          <div className="breadcrumb-line"><span>投研工作台</span><span className="breadcrumb-slash">/</span><strong>{location.pathname === "/" ? "今日概览" : menuItems.find((item) => item.key === `/${location.pathname.split("/")[1]}`)?.label ?? "项目空间"}</strong></div>
          <div className="header-actions">
            <Input.Search className="global-search" prefix={<SearchOutlined />} placeholder="搜索项目、公司、报告" enterButton={false} onSearch={(value) => void searchProjects(value)} />
            <Button type="text" icon={<UserOutlined />} className="user-button" onClick={logout}>退出登录</Button>
          </div>
        </Header>
        <Content className="app-content">{children}</Content>
      </Layout>
      <Button className="floating-assistant" type="primary" icon={<ExperimentOutlined />} onClick={() => setAssistantOpen(true)}>AI 助手</Button>
      <GlobalAssistant open={assistantOpen} onClose={() => setAssistantOpen(false)} />
    </Layout>
  );
}
