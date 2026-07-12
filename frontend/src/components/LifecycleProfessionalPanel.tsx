import { DeleteOutlined, PlusOutlined, ReloadOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Collapse, Form, Input, InputNumber, List, Modal, Progress, Row, Select, Space, Switch, Tag, Typography, message } from "antd";
import { useEffect, useState } from "react";

import {
  createDataSourceSubscription,
  createLifecycleMetric,
  createMetricObservation,
  getLifecycleSummary,
  refreshInvestmentOpinion,
  runDataSourceSubscription,
  saveTransactionExecution,
  updateDataSourceSubscription,
  updateLifecycleRisk,
} from "../api/services";
import type { LifecycleSummary, MonitoringMetricDefinition, ProjectFile } from "../types";

const EMPTY_SUMMARY: LifecycleSummary = { transaction: null, metrics: [], observations: [], risks: [], opinions: [], data_sources: [] };

function errorText(error: any, fallback: string) {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item?.msg ?? String(item)).join("；");
  return fallback;
}

const recommendationLabel: Record<string, string> = {
  insufficient_evidence: "证据不足",
  proceed_to_diligence: "进入下一轮尽调",
  hold_execution: "暂停交易执行",
  proceed_with_controls: "在控制条件下推进",
  escalate: "升级投委处理",
  enhanced_monitoring: "增强监控",
  monitor: "持续监控",
};

const opinionSectionClass: Record<string, string> = {
  "已核验事实": "facts",
  "分析师推断": "inference",
  "核验动作": "action",
  "投委门槛": "gate",
  "无法判断": "boundary",
};

function opinionSections(thesis: string) {
  return thesis.split("\n").map((line) => {
    const separator = line.indexOf("：");
    return separator > 0
      ? { label: line.slice(0, separator), content: line.slice(separator + 1) }
      : { label: "投资意见", content: line };
  });
}

function formatNumber(value?: string | null) {
  if (value === null || value === undefined || value === "") return "未设";
  const parsed = Number(value);
  return Number.isFinite(parsed) ? new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 4 }).format(parsed) : value;
}

export default function LifecycleProfessionalPanel({ projectId, files, mode, onProjectChanged }: { projectId: string; files: ProjectFile[]; mode: "during" | "post"; onProjectChanged?: () => Promise<void> | void }) {
  const [summary, setSummary] = useState<LifecycleSummary>(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [metricOpen, setMetricOpen] = useState(false);
  const [observationMetric, setObservationMetric] = useState<MonitoringMetricDefinition | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [transactionForm] = Form.useForm();

  const load = async () => {
    setLoading(true);
    try {
      const data = await getLifecycleSummary(projectId);
      setSummary(data);
      if (mode === "during" && data.transaction) transactionForm.setFieldsValue(data.transaction);
    } catch (error: any) {
      message.error(errorText(error, "无法加载投资生命周期数据"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [projectId, mode]);

  const saveTransaction = async (values: any) => {
    setSaving(true);
    try {
      await saveTransactionExecution(projectId, {
        ...values,
        conditions_precedent: (values.conditions_precedent ?? []).map((item: any, index: number) => ({
          id: item.id || `condition_${index + 1}`,
          label: item.label,
          status: item.status ?? "pending",
          owner: item.owner ?? "",
          due_date: item.due_date || null,
          evidence_file_id: item.evidence_file_id || null,
          waiver_reason: item.waiver_reason ?? "",
        })),
        evidence_file_ids: values.evidence_file_ids ?? [],
      });
      message.success("交易执行台账与投委门禁已保存");
      await load();
      await onProjectChanged?.();
    } catch (error: any) {
      message.error(errorText(error, "交易执行信息保存失败"));
    } finally {
      setSaving(false);
    }
  };

  const createMetric = async (values: any) => {
    try {
      await createLifecycleMetric(projectId, values);
      setMetricOpen(false);
      message.success("投后指标与预警阈值已建立");
      await load();
    } catch (error: any) {
      message.error(errorText(error, "指标创建失败"));
    }
  };

  const createObservation = async (values: any) => {
    if (!observationMetric) return;
    try {
      await createMetricObservation(projectId, observationMetric.id, { ...values, source_file_id: values.source_file_id || null });
      setObservationMetric(null);
      message.success("周期观测已保存，风险与意见版本已自动重算");
      await load();
    } catch (error: any) {
      message.error(errorText(error, "观测值保存失败"));
    }
  };

  const createSource = async (values: any) => {
    try {
      await createDataSourceSubscription(projectId, values);
      setSourceOpen(false);
      message.success("持续数据源已加入调度");
      await load();
    } catch (error: any) {
      message.error(errorText(error, "数据源创建失败"));
    }
  };

  const latestOpinion = summary.opinions[0];
  const latestSections = latestOpinion ? opinionSections(latestOpinion.thesis) : [];
  const decisionSection = latestSections[0];
  const evidenceNames = latestOpinion?.evidence_file_ids.map((fileId, index) => `E${index + 1} · ${files.find((file) => file.id === fileId)?.filename ?? `证据 ${fileId.slice(0, 8)}`}`) ?? [];
  const opinionPanel = (
    <Card className="workspace-panel lifecycle-opinion" loading={loading} title="当前投资意见基线" extra={<Button icon={<ReloadOutlined />} loading={refreshing} onClick={async () => { setRefreshing(true); try { await refreshInvestmentOpinion(projectId); await load(); message.success("已基于最新证据完成复核"); } catch (error: any) { message.error(errorText(error, "投资意见复核失败")); } finally { setRefreshing(false); } }}>基于最新证据复核</Button>}>
      {latestOpinion ? <>
        <Alert className="opinion-reliability-note" type={Number(latestOpinion.quality_score) < 55 ? "warning" : "info"} showIcon title="可靠性说明" description="证据可靠度衡量资料覆盖、完整性、来源质量和阶段控制，不代表项目成功率或投资收益概率。最终决策必须经过原始凭证复核和投委授权。" />
        <Row gutter={[20, 20]} align="middle">
          <Col xs={24} md={6}><div className="opinion-score"><Progress type="dashboard" percent={Number(latestOpinion.quality_score)} size={100} strokeColor={Number(latestOpinion.quality_score) < 55 ? "#b85e54" : "#2b776b"} /><span>证据可靠度</span><small>{latestOpinion.confidence === "high" ? "证据基础较完整" : latestOpinion.confidence === "medium" ? "仍有关键缺口" : "仅供问题识别"}</small></div></Col>
          <Col xs={24} md={18}>
            <Space wrap><Tag color={latestOpinion.recommendation === "escalate" || latestOpinion.recommendation === "hold_execution" ? "red" : "blue"}>{recommendationLabel[latestOpinion.recommendation] ?? latestOpinion.recommendation}</Tag><Tag>V{latestOpinion.version}</Tag><Tag color={latestOpinion.confidence === "high" ? "green" : latestOpinion.confidence === "medium" ? "gold" : "red"}>证据置信度 {latestOpinion.confidence}</Tag></Space>
            <div className="opinion-decision"><span>阶段化结论</span><strong>{decisionSection?.content ?? latestOpinion.thesis}</strong></div>
            <Typography.Text type="secondary">{latestOpinion.change_summary}</Typography.Text>
          </Col>
        </Row>
        <div className="opinion-brief-grid">{latestSections.slice(1).map((section) => <div key={section.label} className={`opinion-brief-item opinion-${opinionSectionClass[section.label] ?? "general"}`}><span>{section.label}</span><p>{section.content}</p></div>)}</div>
        <div className="opinion-evidence"><span>本版证据 · {latestOpinion.source_count} 份</span><Space wrap>{evidenceNames.length ? evidenceNames.slice(0, 8).map((name) => <Tag key={name}>{name}</Tag>) : <Tag color="gold">暂无可引用证据</Tag>}{evidenceNames.length > 8 ? <Tag>另 {evidenceNames.length - 8} 份</Tag> : null}</Space></div>
      </> : <Alert type="info" showIcon title="尚未形成版本化意见" description="录入交易条件、投后指标或资料后，系统会生成第一版可追溯意见基线。" />}
    </Card>
  );

  const sourcePanel = (
    <Card className="workspace-panel" title="持续数据源" extra={<Button icon={<PlusOutlined />} onClick={() => setSourceOpen(true)}>新增来源</Button>}>
      <Alert className="lifecycle-inline-alert" type="info" showIcon title="受控持续摄取" description="仅抓取明确配置的 HTTPS 公网来源；每次重定向、内容相关性、文件解析与意见版本均保留审计链。" />
      <List dataSource={summary.data_sources} locale={{ emptyText: "尚未配置持续数据源" }} renderItem={(source) => <List.Item actions={[<Button key="run" type="link" onClick={async () => { await runDataSourceSubscription(projectId, source.id); message.success("数据源已进入抓取队列"); }}>立即抓取</Button>, <Switch key="active" size="small" checked={source.active} onChange={async (active) => { await updateDataSourceSubscription(projectId, source.id, { active }); await load(); }} />]}><List.Item.Meta title={<Space wrap><span>{source.name}</span><Tag color={source.status === "failed" ? "red" : source.active ? "green" : "default"}>{source.status}</Tag></Space>} description={<><div>{source.category} · 每 {source.cadence_hours} 小时</div><a href={source.url} target="_blank" rel="noreferrer">{source.url}</a>{source.last_error && <div className="source-error">{source.last_error}</div>}</>} /></List.Item>} />
    </Card>
  );

  const duringPanel = (
    <div className="detail-stack">
      {opinionPanel}
      <Card className="workspace-panel" title="投中交易执行与交割门禁" loading={loading}>
        <Alert className="lifecycle-inline-alert" type="warning" showIcon title="金融级交割控制" description="标记“已交割”前必须具备投委批准、全部前置条件完成或正式豁免，并关联至少一份签署证据。" />
        <Form form={transactionForm} layout="vertical" initialValues={{ transaction_type: "equity", currency: "CNY", status: "drafting", approval_status: "pending", conditions_precedent: [], evidence_file_ids: [] }} onFinish={(values) => void saveTransaction(values)}>
          <Row gutter={12}><Col xs={24} md={8}><Form.Item name="transaction_type" label="交易类型"><Select options={[{ value: "equity", label: "股权" }, { value: "debt", label: "债权" }, { value: "convertible", label: "可转债" }, { value: "secondary", label: "二手份额" }, { value: "other", label: "其他" }]} /></Form.Item></Col><Col xs={24} md={8}><Form.Item name="status" label="执行状态"><Select options={[{ value: "drafting", label: "条款拟定" }, { value: "ic_review", label: "投委审议" }, { value: "signing", label: "协议签署" }, { value: "closing", label: "交割中" }, { value: "closed", label: "已交割" }, { value: "aborted", label: "已终止" }]} /></Form.Item></Col><Col xs={24} md={8}><Form.Item name="approval_status" label="投委审批"><Select options={[{ value: "pending", label: "待审议" }, { value: "conditional", label: "附条件通过" }, { value: "approved", label: "已批准" }, { value: "rejected", label: "已否决" }]} /></Form.Item></Col></Row>
          <Row gutter={12}><Col xs={24} md={6}><Form.Item name="currency" label="币种"><Select options={["CNY", "USD", "HKD", "EUR"].map((value) => ({ value, label: value }))} /></Form.Item></Col><Col xs={24} md={6}><Form.Item name="committed_amount" label="承诺投资额"><InputNumber stringMode min="0" className="field-full" /></Form.Item></Col><Col xs={24} md={6}><Form.Item name="entry_valuation" label="投前估值"><InputNumber stringMode min="0" className="field-full" /></Form.Item></Col><Col xs={24} md={6}><Form.Item name="ownership_pct" label="持股比例 %"><InputNumber stringMode min="0" max="100" className="field-full" /></Form.Item></Col></Row>
          <Form.Item name="decision_rationale" label="投委决策理由" rules={[{ min: 20, message: "审批结论需记录至少 20 个字符的投委理由" }]}><Input.TextArea rows={4} placeholder="记录核心判断、异议、附加条件和授权边界" /></Form.Item>
          <Form.Item name="evidence_file_ids" label="交易与交割证据"><Select mode="multiple" options={files.map((file) => ({ value: file.id, label: file.filename }))} placeholder="选择投委决议、签署协议、付款或交割凭证" /></Form.Item>
          <Typography.Title level={5}>交割前置条件</Typography.Title>
          <Form.List name="conditions_precedent">{(fields, { add, remove }) => <Space orientation="vertical" className="field-full" size={12}>{fields.map((field) => <Card key={field.key} size="small"><Row gutter={8}><Col xs={24} md={7}><Form.Item {...field} name={[field.name, "label"]} label="条件" rules={[{ required: true }]}><Input placeholder="例如：核心牌照续期" /></Form.Item></Col><Col xs={12} md={4}><Form.Item {...field} name={[field.name, "status"]} label="状态" initialValue="pending"><Select options={[{ value: "pending", label: "待满足" }, { value: "satisfied", label: "已满足" }, { value: "waived", label: "已豁免" }, { value: "failed", label: "未通过" }]} /></Form.Item></Col><Col xs={12} md={4}><Form.Item {...field} name={[field.name, "owner"]} label="负责人"><Input /></Form.Item></Col><Col xs={20} md={7}><Form.Item {...field} name={[field.name, "evidence_file_id"]} label="条件证据"><Select allowClear options={files.map((file) => ({ value: file.id, label: file.filename }))} /></Form.Item></Col><Col xs={4} md={2}><Button danger type="text" icon={<DeleteOutlined />} onClick={() => remove(field.name)} /></Col></Row></Card>)}<Button type="dashed" icon={<PlusOutlined />} onClick={() => add({ status: "pending" })}>添加交割条件</Button></Space>}</Form.List>
          <Button className="lifecycle-submit" type="primary" htmlType="submit" loading={saving}>保存交易台账</Button>
        </Form>
      </Card>
      {sourcePanel}
    </div>
  );

  const postPanel = (
    <div className="detail-stack">
      {opinionPanel}
      <Card className="workspace-panel" title="投后 KPI 与阈值" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setMetricOpen(true)}>建立指标</Button>} loading={loading}>
        <List dataSource={summary.metrics} locale={{ emptyText: "尚未建立投后指标体系" }} renderItem={(metric) => {
          const latest = summary.observations.find((item) => item.metric_id === metric.id);
          return <List.Item actions={[<Button key="observation" type="link" onClick={() => setObservationMetric(metric)}>录入周期值</Button>]}><List.Item.Meta avatar={<span className={`risk-orb risk-${latest?.status ?? "normal"}`}><SafetyCertificateOutlined /></span>} title={<Space wrap><span>{metric.name}</span><Tag>{metric.frequency}</Tag>{latest && <Tag color={latest.status === "high" ? "red" : latest.status === "watch" ? "gold" : "green"}>{latest.status}</Tag>}</Space>} description={<Space wrap separator="·"><span>目标 {formatNumber(metric.target_value)} {metric.unit}</span><span>关注 {formatNumber(metric.watch_threshold)}</span><span>高风险 {formatNumber(metric.breach_threshold)}</span><span>{metric.owner || "未指定负责人"}</span>{latest && <strong>最新 {formatNumber(latest.value)} {metric.unit}</strong>}</Space>} /></List.Item>;
        }} />
      </Card>
      <Card className="workspace-panel" title="风险事件与处置">
        <List dataSource={summary.risks} locale={{ emptyText: "当前没有风险事件" }} renderItem={(risk) => <List.Item actions={risk.status !== "resolved" ? [<Button key="resolve" type="link" onClick={async () => { await updateLifecycleRisk(projectId, risk.id, { status: "resolved" }); await load(); }}>标记已解决</Button>] : []}><List.Item.Meta title={<Space wrap><Tag color={risk.severity === "critical" || risk.severity === "high" ? "red" : "gold"}>{risk.severity}</Tag><span>{risk.title}</span><Tag>{risk.status}</Tag></Space>} description={`${risk.description} · ${risk.trigger_source}`} /></List.Item>} />
      </Card>
      {sourcePanel}
      <Card className="workspace-panel" title="意见版本历史"><Collapse ghost items={summary.opinions.map((opinion) => ({ key: opinion.id, label: `V${opinion.version} · ${recommendationLabel[opinion.recommendation] ?? opinion.recommendation} · 可靠度 ${formatNumber(opinion.quality_score)} · ${new Date(opinion.created_at).toLocaleString("zh-CN")}`, children: <><Typography.Paragraph className="opinion-history-thesis">{opinion.thesis}</Typography.Paragraph><Typography.Text type="secondary">{opinion.change_summary}<br />证据哈希：{opinion.evidence_hash.slice(0, 16)}…</Typography.Text></> }))} /></Card>
    </div>
  );

  return <>
    {mode === "during" ? duringPanel : postPanel}
    <Modal title="建立投后指标" open={metricOpen} onCancel={() => setMetricOpen(false)} footer={null}><Form layout="vertical" onFinish={(values) => void createMetric(values)} initialValues={{ frequency: "monthly", direction: "higher_better", active: true }}><Row gutter={12}><Col span={12}><Form.Item name="code" label="指标代码" rules={[{ required: true, pattern: /^[a-z0-9_]+$/, message: "仅使用小写字母、数字和下划线" }]}><Input placeholder="monthly_revenue" /></Form.Item></Col><Col span={12}><Form.Item name="name" label="指标名称" rules={[{ required: true }]}><Input /></Form.Item></Col></Row><Row gutter={12}><Col span={8}><Form.Item name="unit" label="单位"><Input /></Form.Item></Col><Col span={8}><Form.Item name="frequency" label="频率"><Select options={[{ value: "weekly", label: "每周" }, { value: "monthly", label: "每月" }, { value: "quarterly", label: "每季度" }, { value: "annual", label: "每年" }, { value: "event", label: "事件触发" }]} /></Form.Item></Col><Col span={8}><Form.Item name="direction" label="风险方向"><Select options={[{ value: "higher_better", label: "越低越差" }, { value: "lower_better", label: "越高越差" }]} /></Form.Item></Col></Row><Row gutter={12}><Col span={8}><Form.Item name="baseline_value" label="基线"><InputNumber stringMode className="field-full" /></Form.Item></Col><Col span={8}><Form.Item name="target_value" label="目标"><InputNumber stringMode className="field-full" /></Form.Item></Col><Col span={8}><Form.Item name="watch_threshold" label="关注阈值"><InputNumber stringMode className="field-full" /></Form.Item></Col></Row><Form.Item name="breach_threshold" label="高风险阈值"><InputNumber stringMode className="field-full" /></Form.Item><Form.Item name="owner" label="负责人"><Input /></Form.Item><Form.Item name="source_description" label="数据口径与来源"><Input.TextArea rows={3} /></Form.Item><Button type="primary" htmlType="submit" block>创建指标</Button></Form></Modal>
    <Modal title={`录入周期值 · ${observationMetric?.name ?? ""}`} open={Boolean(observationMetric)} onCancel={() => setObservationMetric(null)} footer={null}><Form layout="vertical" onFinish={(values) => void createObservation(values)}><Form.Item name="period_end" label="周期截止日" rules={[{ required: true }]}><Input type="date" /></Form.Item><Form.Item name="value" label={`指标值 ${observationMetric?.unit ?? ""}`} rules={[{ required: true }]}><InputNumber stringMode className="field-full" /></Form.Item><Form.Item name="source_file_id" label="原始证据文件"><Select allowClear options={files.map((file) => ({ value: file.id, label: file.filename }))} /></Form.Item><Form.Item name="note" label="复核说明"><Input.TextArea rows={3} /></Form.Item><Button type="primary" htmlType="submit" block>保存并计算预警</Button></Form></Modal>
    <Modal title="新增持续数据源" open={sourceOpen} onCancel={() => setSourceOpen(false)} footer={null}><Form layout="vertical" onFinish={(values) => void createSource(values)} initialValues={{ source_type: "company_ir", category: "financial", cadence_hours: 168, active: true }}><Form.Item name="name" label="来源名称" rules={[{ required: true }]}><Input placeholder="公司投资者关系公告" /></Form.Item><Form.Item name="url" label="HTTPS 文件或页面地址" rules={[{ required: true, type: "url" }]}><Input placeholder="https://..." /></Form.Item><Row gutter={12}><Col span={12}><Form.Item name="source_type" label="来源类型"><Select options={[{ value: "official_filing", label: "法定披露" }, { value: "regulator", label: "监管机构" }, { value: "company_ir", label: "公司 IR" }, { value: "industry_data", label: "行业数据" }, { value: "news", label: "新闻" }, { value: "other", label: "其他" }]} /></Form.Item></Col><Col span={12}><Form.Item name="category" label="证据类别"><Select options={["business", "financial", "market", "competition", "team", "legal", "customers", "valuation"].map((value) => ({ value, label: value }))} /></Form.Item></Col></Row><Form.Item name="cadence_hours" label="抓取周期（小时）"><InputNumber min={1} max={8760} className="field-full" /></Form.Item><Button type="primary" htmlType="submit" block>加入持续调度</Button></Form></Modal>
  </>;
}
