import { Button, Card, Form, Input, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";

import { login } from "../api/services";

export function LoginPage() {
  const navigate = useNavigate();

  const onFinish = async (values: { email: string; password: string }) => {
    try {
      const data = await login(values);
      localStorage.setItem("vision_capital_ai_token", data.access_token);
      navigate("/");
    } catch (error: any) {
      message.error(error.response?.data?.detail ?? "Login failed");
    }
  };

  return (
    <div className="auth-page">
      <Card className="auth-card">
        <Typography.Title level={2}>欢迎回来</Typography.Title>
        <Typography.Paragraph>登录 Vision Capital AI,继续你的投研工作流。</Typography.Paragraph>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item label="Email" name="email" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Password" name="password" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>
            登录
          </Button>
          <Button type="link" block onClick={() => navigate("/register")}>
            创建新账号
          </Button>
        </Form>
      </Card>
    </div>
  );
}
