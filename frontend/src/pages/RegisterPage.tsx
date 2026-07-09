import { Button, Card, Form, Input, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";

import { register } from "../api/services";

export function RegisterPage() {
  const navigate = useNavigate();

  const onFinish = async (values: { email: string; username: string; password: string }) => {
    try {
      const data = await register(values);
      localStorage.setItem("vision_capital_ai_token", data.access_token);
      navigate("/");
    } catch (error: any) {
      message.error(error.response?.data?.detail ?? "Register failed");
    }
  };

  return (
    <div className="auth-page">
      <Card className="auth-card">
        <Typography.Title level={2}>创建账号</Typography.Title>
        <Typography.Paragraph>几分钟内搭起你的 AI 投资研究工作台。</Typography.Paragraph>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item label="Email" name="email" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Username" name="username" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Password" name="password" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            注册并进入系统
          </Button>
          <Button type="link" block onClick={() => navigate("/login")}>
            返回登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}

