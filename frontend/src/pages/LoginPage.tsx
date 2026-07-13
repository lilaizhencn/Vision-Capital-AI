import { ArrowLeftOutlined, ArrowRightOutlined, LockOutlined, MailOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";

import { login } from "../api/services";

const EVALUATION_ACCOUNT = {
  email: "cross-industry-5443fce457@example.com",
  password: "VisionQA#2026!",
};

export function LoginPage() {
  const navigate = useNavigate();

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      const data = await login(values);
      localStorage.setItem("vision_capital_ai_token", data.access_token);
      navigate("/workspace");
    } catch (error: any) {
      message.error(error.response?.data?.detail ?? "登录失败，请检查账号信息");
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-backdrop" aria-hidden="true"><span className="auth-orbit auth-orbit-one" /><span className="auth-orbit auth-orbit-two" /><span className="auth-grid" /></div>
      <div className="auth-shell">
        <section className="auth-story">
          <button className="auth-brand" type="button" onClick={() => navigate("/")}><span className="auth-brand-mark">V</span><span><strong>Vision Capital AI</strong><small>投资智能工作台</small></span></button>
          <div className="auth-story-copy"><p className="auth-kicker">A CLEARER INVESTMENT SIGNAL</p><Typography.Title>让每一次判断，<em>都有依据。</em></Typography.Title><Typography.Paragraph>把资料、研究与团队协作放进同一条投资主线，让重要信息在正确的时刻被看见。</Typography.Paragraph></div>
          <div className="auth-proof"><span><strong>01</strong> 资料可追溯</span><span><strong>02</strong> 研究可协作</span><span><strong>03</strong> 决策可复盘</span></div>
        </section>
        <Card className="auth-card" variant="borderless">
          <button className="auth-return" type="button" onClick={() => navigate("/")}><ArrowLeftOutlined /> 返回官网</button>
          <div className="auth-heading"><p className="auth-kicker">WELCOME BACK</p><Typography.Title level={2}>回到你的研究现场</Typography.Title><Typography.Paragraph>登录后继续推进正在发生的投资判断。</Typography.Paragraph></div>
          <Form layout="vertical" initialValues={EVALUATION_ACCOUNT} onFinish={onFinish} requiredMark={false} size="large">
            <Form.Item label="工作邮箱" name="email" rules={[{ required: true, type: "email", message: "请输入有效的工作邮箱" }]}><Input prefix={<MailOutlined />} placeholder="name@firm.com" /></Form.Item>
            <Form.Item label="登录密码" name="password" rules={[{ required: true, message: "请输入密码" }]}><Input.Password prefix={<LockOutlined />} placeholder="输入你的密码" /></Form.Item>
            <Button type="primary" htmlType="submit" block icon={<ArrowRightOutlined />} iconPlacement="end">进入工作台</Button>
          </Form>
          <Typography.Text className="evaluation-account-note">体验账号已预填，可直接进入工作台。</Typography.Text>
          <div className="auth-switch"><span>还没有工作空间？</span><Button type="link" onClick={() => navigate("/register")}>申请体验</Button></div>
        </Card>
      </div>
    </div>
  );
}
