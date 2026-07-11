import { ArrowLeftOutlined, ArrowRightOutlined, LockOutlined, MailOutlined, UserOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";

import { register } from "../api/services";

export function RegisterPage() {
  const navigate = useNavigate();

  const onFinish = async (values: { email: string; username: string; password: string }) => {
    try {
      const data = await register(values);
      localStorage.setItem("vision_capital_ai_token", data.access_token);
      navigate("/workspace");
    } catch (error: any) {
      message.error(error.response?.data?.detail ?? "注册失败，请稍后重试");
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-backdrop" aria-hidden="true"><span className="auth-orbit auth-orbit-one" /><span className="auth-orbit auth-orbit-two" /><span className="auth-grid" /></div>
      <div className="auth-shell">
        <section className="auth-story auth-story-register">
          <button className="auth-brand" type="button" onClick={() => navigate("/")}><span className="auth-brand-mark">V</span><span><strong>Vision Capital AI</strong><small>投资智能工作台</small></span></button>
          <div className="auth-story-copy"><p className="auth-kicker">BUILD YOUR INVESTMENT SYSTEM</p><Typography.Title>从一份资料，<em>开始一条主线。</em></Typography.Title><Typography.Paragraph>创建你的机构工作空间，让投前、投中与投后研究拥有连续的上下文。</Typography.Paragraph></div>
          <div className="auth-register-note"><span className="auth-note-number">V</span><div><strong>为认真做判断的团队而生</strong><p>研究创造认知，认知创造价值。</p></div></div>
        </section>
        <Card className="auth-card" bordered={false}>
          <button className="auth-return" type="button" onClick={() => navigate("/")}><ArrowLeftOutlined /> 返回官网</button>
          <div className="auth-heading"><p className="auth-kicker">START WITH SIGNAL</p><Typography.Title level={2}>建立你的研究空间</Typography.Title><Typography.Paragraph>几分钟内，把团队的投资工作流放到同一张桌面上。</Typography.Paragraph></div>
          <Form layout="vertical" onFinish={onFinish} requiredMark={false} size="large">
            <Form.Item label="工作邮箱" name="email" rules={[{ required: true, type: "email", message: "请输入有效的工作邮箱" }]}><Input prefix={<MailOutlined />} placeholder="name@firm.com" /></Form.Item>
            <Form.Item label="你的称呼" name="username" rules={[{ required: true, message: "请输入你的称呼" }]}><Input prefix={<UserOutlined />} placeholder="例如：Alex Chen" /></Form.Item>
            <Form.Item label="设置密码" name="password" rules={[{ required: true, min: 8, message: "密码至少需要 8 位" }]}><Input.Password prefix={<LockOutlined />} placeholder="至少 8 位字符" /></Form.Item>
            <Button type="primary" htmlType="submit" block icon={<ArrowRightOutlined />} iconPosition="end">创建工作空间</Button>
          </Form>
          <div className="auth-switch"><span>已经有账号？</span><Button type="link" onClick={() => navigate("/login")}>返回登录</Button></div>
        </Card>
      </div>
    </div>
  );
}
