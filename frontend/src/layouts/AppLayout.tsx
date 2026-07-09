import { BarChartOutlined, FileSearchOutlined, MessageOutlined, ProjectOutlined, SettingOutlined } from "@ant-design/icons";
import { Layout, Menu, Typography } from "antd";
import { useLocation, useNavigate } from "react-router-dom";
import { PropsWithChildren } from "react";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/", icon: <BarChartOutlined />, label: "Dashboard" },
  { key: "/projects", icon: <ProjectOutlined />, label: "投资项目" },
  { key: "/assistant", icon: <MessageOutlined />, label: "AI 问答" },
  { key: "/reports", icon: <FileSearchOutlined />, label: "投研报告" },
  { key: "/settings", icon: <SettingOutlined />, label: "系统设置" },
];

export function AppLayout({ children }: PropsWithChildren) {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout className="app-shell">
      <Sider width={260} className="app-sider">
        <div className="brand-block">
          <Typography.Title level={3}>Vision Capital AI</Typography.Title>
          <Typography.Paragraph>Enterprise-grade investment research workspace.</Typography.Paragraph>
        </div>
        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[location.pathname === "/" ? "/" : `/${location.pathname.split("/")[1]}`]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <div>
            <Typography.Title level={4} style={{ margin: 0 }}>
              Investment Intelligence Operating System
            </Typography.Title>
            <Typography.Text type="secondary">上传资料、构建知识库、生成研究洞察。</Typography.Text>
          </div>
        </Header>
        <Content className="app-content">{children}</Content>
      </Layout>
    </Layout>
  );
}

