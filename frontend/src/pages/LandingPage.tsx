import { ApartmentOutlined, ArrowRightOutlined, CheckCircleOutlined, FileSearchOutlined, SafetyCertificateOutlined } from "@ant-design/icons";
import { Button } from "antd";
import { useNavigate } from "react-router-dom";

const capabilities = [
  { icon: <FileSearchOutlined />, title: "把资料变成判断", text: "上传 BP、财报、合同与行业材料，自动完成 OCR、表格提取、结构化归档与可追溯引用。" },
  { icon: <ApartmentOutlined />, title: "沿一条投资主线协作", text: "从初筛、尽调到投后跟踪，项目状态、任务、报告和关键变化在同一个工作空间里连续沉淀。" },
  { icon: <SafetyCertificateOutlined />, title: "让机构知识可复用", text: "将研究方法、风险信号和决策记录沉淀为团队资产，减少重复劳动，保持判断口径一致。" },
];

export function LandingPage() {
  const navigate = useNavigate();
  return (
    <main className="landing-page">
      <nav className="landing-nav">
        <button className="landing-brand" onClick={() => navigate("/")}><span className="landing-mark">V</span><span><strong>Vision Capital AI</strong><small>投资智能工作台</small></span></button>
        <div className="landing-nav-links"><a href="#workflow">投资流程</a><a href="#capabilities">研究能力</a><a href="#institution">机构协作</a></div>
        <div className="landing-nav-actions"><Button type="link" onClick={() => navigate("/login")}>登录</Button><Button type="primary" onClick={() => navigate("/register")}>申请体验 <ArrowRightOutlined /></Button></div>
      </nav>

      <section className="landing-hero">
        <div className="landing-hero-copy">
          <p className="landing-kicker">FOR INVESTMENT TEAMS</p>
          <h1>把每一份信息，<br /><em>变成更好的判断。</em></h1>
          <p className="landing-lead">Vision Capital AI 为投资机构打造一套从资料进入、研究展开到投后复盘的智能工作台，让团队在复杂信息中更快看见真正重要的信号。</p>
          <div className="landing-hero-actions"><Button type="primary" size="large" onClick={() => navigate("/register")}>开始构建你的投资系统 <ArrowRightOutlined /></Button><a href="#workflow">了解工作方式 <ArrowRightOutlined /></a></div>
          <div className="landing-proof"><span><CheckCircleOutlined /> 资料可追溯</span><span><CheckCircleOutlined /> 团队可协作</span><span><CheckCircleOutlined /> 决策可复盘</span></div>
        </div>
        <div className="landing-hero-visual"><div className="hero-image-frame"><img src="/assets/satellite-research.jpg" alt="卫星通信设备研究图片" /><div className="hero-image-caption"><span>研究视野</span><strong>从数据的远方，看见增长的方向。</strong></div></div><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" /></div>
      </section>

      <section className="landing-signal"><span>为认真做判断的团队而生</span><strong>研究效率 × 判断质量 × 组织记忆</strong><span>一个工作台，连接投前、投中与投后</span></section>

      <section className="landing-section landing-workflow" id="workflow"><div className="landing-section-heading"><p className="landing-kicker">ONE CONTINUOUS WORKFLOW</p><h2>从资料到决策，<br />每一步都留下依据。</h2><p>不是一个聊天框，也不是一套孤立的后台菜单。我们把投资项目作为核心对象，让信息、协作和判断围绕项目自然流动。</p></div><div className="workflow-rail"><div className="workflow-step"><span>01</span><strong>收集资料</strong><p>多格式上传，自动解析并建立项目资料底座。</p></div><div className="workflow-step"><span>02</span><strong>AI 研究</strong><p>围绕项目提问，快速定位风险、亮点和待尽调事项。</p></div><div className="workflow-step"><span>03</span><strong>决策协作</strong><p>生成报告、分配任务，让决策会有共同上下文。</p></div><div className="workflow-step"><span>04</span><strong>投后跟踪</strong><p>记录经营指标和风险变化，让投资组合持续被看见。</p></div></div></section>

      <section className="landing-section capabilities-section" id="capabilities"><div className="landing-section-heading compact"><p className="landing-kicker">BUILT FOR THE FULL PICTURE</p><h2>研究深度，最终服务于<br /><em>机构的长期判断。</em></h2></div><div className="capability-grid">{capabilities.map((item) => <article className="capability-item" key={item.title}><div className="capability-icon">{item.icon}</div><h3>{item.title}</h3><p>{item.text}</p><a href="#institution">查看能力 <ArrowRightOutlined /></a></article>)}</div></section>

      <section className="landing-institution" id="institution"><div><p className="landing-kicker">A CALMER COMMAND CENTER</p><h2>让团队把时间<br />用在真正重要的地方。</h2></div><div><p>面向投资机构、家族办公室与企业投资团队，Vision Capital AI 将分散在文件、对话和会议里的知识，变成一套可持续积累的判断系统。</p><Button size="large" onClick={() => navigate("/register")}>进入 Vision Capital AI <ArrowRightOutlined /></Button></div></section>

      <footer className="landing-footer"><div className="landing-brand"><span className="landing-mark">V</span><span><strong>Vision Capital AI</strong><small>投资智能工作台</small></span></div><span>研究创造认知，认知创造价值。</span><span>© 2026 Vision Capital AI</span></footer>
    </main>
  );
}
