import { Button, Card, Col, Input, List, Row, Tabs, Typography, Upload, message } from "antd";
import type { UploadProps } from "antd";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { askProject, generateReport, getProject, getProjectFiles, getReports, uploadProjectFile } from "../api/services";
import type { ChatResponse, Project, ProjectFile, Report } from "../types";

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [question, setQuestion] = useState("");
  const [chatResult, setChatResult] = useState<ChatResponse | null>(null);

  const load = async () => {
    setProject(await getProject(projectId));
    setFiles(await getProjectFiles(projectId));
    setReports(await getReports(projectId));
  };

  useEffect(() => {
    void load();
  }, [projectId]);

  const uploadProps: UploadProps = {
    customRequest: async ({ file, onSuccess, onError }) => {
      try {
        await uploadProjectFile(projectId, file as File);
        message.success("文件已上传");
        await load();
        onSuccess?.({}, new XMLHttpRequest());
      } catch (error) {
        onError?.(error as Error);
      }
    },
    showUploadList: false,
  };

  return (
    <div className="page-stack">
      <Card className="glass-card">
        <Typography.Title level={2}>{project?.name}</Typography.Title>
        <Typography.Paragraph>{project?.description}</Typography.Paragraph>
      </Card>
      <Tabs
        items={[
          {
            key: "overview",
            label: "项目概览",
            children: (
              <Row gutter={[16, 16]}>
                <Col span={8}><Card className="glass-card" title="公司">{project?.company_name}</Card></Col>
                <Col span={8}><Card className="glass-card" title="行业">{project?.industry}</Card></Col>
                <Col span={8}><Card className="glass-card" title="阶段">{project?.stage}</Card></Col>
              </Row>
            ),
          },
          {
            key: "files",
            label: "文档资料",
            children: (
              <Card className="glass-card" extra={<Upload {...uploadProps}><Button type="primary">上传文件</Button></Upload>}>
                <List
                  dataSource={files}
                  renderItem={(file) => (
                    <List.Item>
                      <List.Item.Meta title={file.filename} description={`${file.parse_status} · ${file.content_type}`} />
                    </List.Item>
                  )}
                />
              </Card>
            ),
          },
          {
            key: "chat",
            label: "AI 问答",
            children: (
              <Card className="glass-card">
                <Input.TextArea rows={4} value={question} onChange={(event) => setQuestion(event.target.value)} />
                <Button
                  type="primary"
                  style={{ marginTop: 12 }}
                  onClick={async () => setChatResult(await askProject(projectId, question))}
                >
                  发起分析
                </Button>
                {chatResult && (
                  <div style={{ marginTop: 16 }}>
                    <Typography.Title level={4}>回答</Typography.Title>
                    <Typography.Paragraph>{chatResult.answer}</Typography.Paragraph>
                    <Typography.Title level={5}>引用片段</Typography.Title>
                    <List
                      dataSource={chatResult.citations}
                      renderItem={(citation) => (
                        <List.Item>
                          <List.Item.Meta title={citation.filename} description={citation.content} />
                        </List.Item>
                      )}
                    />
                  </div>
                )}
              </Card>
            ),
          },
          {
            key: "reports",
            label: "投研报告",
            children: (
              <Card
                className="glass-card"
                extra={
                  <Button type="primary" onClick={async () => { await generateReport(projectId); await load(); }}>
                    生成报告
                  </Button>
                }
              >
                <List
                  dataSource={reports}
                  renderItem={(report) => (
                    <List.Item>
                      <List.Item.Meta title={report.title} description={report.content.slice(0, 280)} />
                    </List.Item>
                  )}
                />
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}

