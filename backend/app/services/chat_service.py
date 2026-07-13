import json
import re
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.llm_service import LLMService
from app.repositories.chat_repository import ChatRepository
from app.repositories.file_repository import FileRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.chat import Citation, ChatResponse, EvidenceClaim
from app.services.evidence_ledger_service import EvidenceLedgerService
from app.services.ai_usage_service import AIUsageService
from app.services.rag_service import RAGService
from app.services.research_service import ResearchService


class ChatService:
    def __init__(self, db: Session):
        self.db = db
        self.chat_repo = ChatRepository(db)
        self.file_repo = FileRepository(db)
        self.project_repo = ProjectRepository(db)
        self.rag_service = RAGService(db)
        self.llm_service = LLMService()

    def ask(self, project_id: str, message: str, user_id: str) -> ChatResponse:
        project = self.project_repo.get_for_owner(project_id, user_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        AIUsageService(self.db).consume(user_id, "chat", f"chat:{user_id}:{uuid.uuid4()}")

        is_strategy_question = self._is_strategy_question(message)
        chunks = (
            self.rag_service.investment_strategy_search(project_id=project_id, query=message)
            if is_strategy_question
            else self.rag_service.similarity_search(project_id=project_id, query=message)
        )
        citations: list[Citation] = []
        context_parts: list[str] = []
        for chunk in chunks:
            file = self.file_repo.get(chunk.file_id)
            filename = file.filename if file else "Unknown"
            citations.append(Citation(
                file_id=chunk.file_id,
                filename=filename,
                content=chunk.content,
                source_kind=file.source_kind if file else "upload",
                source_url=file.source_url if file else None,
                source_quality=file.source_quality if file else None,
                document_role=self._document_role(project, file),
            ))
            role = self._document_role(project, file)
            context_parts.append(f"[{filename} | role={role}] {chunk.content}")

        requirements = ResearchService(self.db).requirements(project_id)
        missing_evidence = [
            f"{item.label}: {item.reason} 建议补充：{item.suggested_document}"
            for item in requirements if item.status.value != "covered"
        ]
        self.chat_repo.create(project_id=project_id, role="user", content=message)
        evidence_control_passed = None
        quality_issues: list[str] = []
        claim_ledger: list[EvidenceClaim] = EvidenceLedgerService.build(citations) if is_strategy_question else []
        if is_strategy_question:
            answer, evidence_control_passed, quality_issues = self._ground_strategy_answer(
                project, message, context_parts, missing_evidence, claim_ledger
            )
        else:
            answer = self.llm_service.generate(self._standard_prompt(project, message, context_parts, missing_evidence))
        self.chat_repo.create(project_id=project_id, role="assistant", content=answer)
        confidence = "high" if len(citations) >= 8 and len(missing_evidence) <= 2 else "medium" if len(citations) >= 3 else "low"
        return ChatResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            missing_evidence=missing_evidence,
            evidence_control_passed=evidence_control_passed,
            quality_issues=quality_issues,
            claim_ledger=claim_ledger,
        )

    @staticmethod
    def _document_role(project, file) -> str:
        if not file:
            return "uploaded_evidence"
        extracted = file.extracted_data if isinstance(file.extracted_data, dict) else {}
        extracted_company = extracted.get("company")
        if isinstance(extracted_company, str) and RAGService._same_company(project.company_name, extracted_company):
            return "company_disclosure"
        if file.source_kind == "public_research" or not extracted_company:
            return "industry_context"
        return "uploaded_evidence"

    @staticmethod
    def _is_strategy_question(message: str) -> bool:
        lowered = message.lower()
        return any(keyword in lowered for keyword in (
            "\u6295\u524d", "\u6295\u4e2d", "\u6295\u540e", "\u5efa\u4ed3", "\u4ed3\u4f4d", "\u4f30\u503c",
            "\u9000\u51fa", "\u589e\u6301", "\u51cf\u6301", "\u6295\u59d4", "pre-investment",
            "during-investment", "post-investment", "strategy", "kpi",
        ))

    @staticmethod
    def _standard_prompt(project, message: str, context_parts: list[str], missing_evidence: list[str]) -> str:
        return f"""
You are a rigorous institutional investment research copilot. Answer in the user's language.

Project: {project.company_name}; industry: {project.industry}; stage: {project.stage}.

Synthesize the evidence instead of summarizing one document. Evaluate the relevant dimensions among business model,
market, competition, management, financial quality, cash flow, customers, regulation, valuation, and execution risk.
Clearly separate disclosed facts, cross-source inference, and unresolved evidence. Cite source filenames inline.
Public web materials are secondary evidence unless they are official filings or regulator/government publications.
Industry and macro sources provide context only. Never transfer an industry statistic, trend, or risk to the company
unless company-specific evidence establishes the connection.
Only role=company_disclosure supports company facts. role=industry_context is scenario context only, while
role=uploaded_evidence must be explicitly caveated unless independently verified.
Never invent numbers, market data, interviews, forecasts, valuation, or legal conclusions.

User question:
{message}

Known evidence gaps:
{chr(10).join(missing_evidence) or "No material gap detected by the automated coverage check; human verification is still required."}

Materials:
{chr(10).join(context_parts)}
""".strip()

    def _ground_strategy_answer(
        self,
        project,
        message: str,
        context_parts: list[str],
        missing_evidence: list[str],
        claim_ledger: list[EvidenceClaim] | None = None,
    ) -> tuple[str, bool, list[str]]:
        claim_ledger = claim_ledger if claim_ledger is not None else EvidenceLedgerService.from_context_parts(context_parts)
        ledger_text = EvidenceLedgerService.serialize(claim_ledger)
        prompt = f"""
You are the final evidence-control analyst for an institutional investment committee. Generate the answer directly and
only from the evidence pack below. Do not use outside knowledge, memory, or assumptions about the company or industry.

Non-negotiable review rules:
1. Every number, named product, named competitor, customer concentration, pipeline code, market claim, and financial
   trend must be explicitly present in the verified claim ledger below. If not, delete it or move it to missing evidence.
   Every company fact must cite its [C#] claim ID. Every industry scenario statement must cite its [I#] claim ID.
   Never create a factual statement by combining fragments from different claims.
2. Arithmetic derived from evidence is allowed only when you show the operands, calculation, source filename, and label
   it as analyst-derived rather than company-disclosed.
3. Do not turn risk-factor language into a statement that the risk has already occurred.
   Label company self-descriptions and management assertions as company-disclosed, not independently verified facts.
4. Do not introduce position sizes, stop losses, valuation multiples, target prices, hedge instruments, or numeric KPI
   thresholds unless the exact baseline and mandate are in evidence. State which data the IC must obtain instead.
5. Distinguish facts, cross-source inference, and missing evidence. Limit inference to direct logical implications of
   named evidence. Do not speculate that a company may benefit, has a moat, is near an inflection point, or faces a
   specific competitor response unless those propositions are explicit in evidence.
6. Cite source filenames next to material factual claims. Do not cite a source that is absent from the evidence pack.
   Macro and industry sources are context only; do not convert their statistics or trends into company facts.
   Do not claim a macro or regulator report is relevant to the company unless company evidence provides that link.
   Ledger entries carry a role. Only role=company_disclosure can support company facts. role=industry_context may
   support scenario context but never a claim about the company. role=uploaded_evidence requires explicit caveating.
   When both company_disclosure and industry_context entries are available, cite at least one filename from each role
   and state explicitly that the industry source is only a scenario baseline.
7. Keep the recommendation conditional and operational. Allowed actions are evidence requests, interviews, model checks,
   regulatory verification, scenario analysis, and IC gates grounded in stated missing information.
   When evidence for a requested dimension is absent, say it cannot be assessed; do not relabel the absence as a risk.
8. The revised answer must contain five clearly named sections: IC Summary, Pre-Investment, During-Investment,
   Post-Investment, and Evidence Gaps. In each investment-stage section include:
   - company-disclosed facts with filename citations;
   - direct evidence implications, explicitly labelled as analyst inference;
   - a precise verification action naming the field to obtain, the expected primary source, and the reconciliation;
   - an IC gate definition naming the decision variable but not inventing its numeric threshold; and
   - items that cannot currently be assessed.
   Use these exact field labels in every stage, even when the value is "none": Company-disclosed facts,
   Analyst inference, Verification action, IC gate, Cannot assess.
   Do not make generic requests for an annual report, filing, or industry report when that document is already in the
   evidence pack. Convert automated coverage gaps into field-level requests tailored to the cited evidence.
9. The answer must be a useful preliminary work plan, not a blanket refusal. Use available evidence to state what is
   known and what it means, while keeping any investment recommendation conditional on the unresolved gates.
10. Return JSON only with this shape:
   {{"revised_answer":"...", "removed_or_reframed_claims":["..."], "evidence_control_passed":true}}
   Set evidence_control_passed to true only when every factual claim and number is supported by the evidence pack.

KNOWN GAPS:
{chr(10).join(missing_evidence)}

PROJECT:
{project.company_name}; {project.industry}; {project.stage}

USER QUESTION:
{message}

VERIFIED CLAIM LEDGER:
{ledger_text}
""".strip()
        try:
            raw = self.llm_service.generate(prompt).strip()
            last_issues: list[str] = []
            for attempt in range(2):
                cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                result = json.loads(cleaned)
                revised = result.get("revised_answer") if isinstance(result, dict) else None
                passed = result.get("evidence_control_passed") if isinstance(result, dict) else None
                if not isinstance(revised, str) or not revised.strip():
                    raise RuntimeError("Evidence-controlled strategy response was malformed")
                guarded = self._remove_unsupported_numeric_lines(revised.strip(), context_parts)
                guarded = EvidenceLedgerService.anchor_references(guarded, claim_ledger)
                structure_issues = (
                    self._strategy_structure_issues(guarded, context_parts)
                    + EvidenceLedgerService.reference_issues(guarded, claim_ledger)
                    if guarded else ["empty answer"]
                )
                if passed is True and not structure_issues:
                    if attempt == 1:
                        return guarded, True, []
                    reviewed = self._run_strategy_critic(project, message, guarded, context_parts, claim_ledger)
                    if reviewed:
                        return reviewed, True, []
                    last_issues = ["independent evidence critic did not pass"]
                    raw = self.llm_service.generate(self._strategy_repair_prompt(
                        project, message, guarded, context_parts, missing_evidence, last_issues, claim_ledger
                    )).strip()
                    continue
                last_issues = (["model evidence self-check was false"] if passed is not True else []) + structure_issues
                if attempt == 1:
                    break
                raw = self.llm_service.generate(self._strategy_repair_prompt(
                    project, message, revised, context_parts, missing_evidence, last_issues, claim_ledger
                )).strip()
            return self._recover_strategy_answer(
                project, claim_ledger, context_parts, missing_evidence, last_issues or ["evidence control failed"]
            )
        except json.JSONDecodeError:
            return self._recover_strategy_answer(
                project, claim_ledger, context_parts, missing_evidence, ["malformed evidence-control response"]
            )
        except RuntimeError as exc:
            return self._recover_strategy_answer(project, claim_ledger, context_parts, missing_evidence, [str(exc)])

    def _run_strategy_critic(
        self,
        project,
        message: str,
        answer: str,
        context_parts: list[str],
        claim_ledger: list[EvidenceClaim],
    ) -> str | None:
        ledger_text = EvidenceLedgerService.serialize(claim_ledger)
        raw = self.llm_service.generate(f"""
You are an independent claim-level evidence critic. Review and, where necessary, edit the work plan below.
Use only the evidence pack. Return JSON only:
{{"revised_answer":"...","unsupported_or_overreaching_claims":["..."],"evidence_control_passed":true}}

Hard rules:
1. Every company fact and number must cite a valid [C#] ledger claim. Every industry scenario must cite a valid [I#].
2. role=industry_context supports scenario baselines only. Never transfer its trend, statistic, or risk to the company.
3. Analyst inference must be a direct logical implication. Delete causal or evaluative leaps such as "shows confidence",
   "proves resilience", "strategy is working", "stable profitability", "has a moat", or "will benefit" unless the
   exact proposition is explicit in company evidence.
4. Risk-factor wording does not prove an event occurred. A missing field is "cannot assess", not a company risk.
5. Verification actions and conditional IC procedures are analyst recommendations and are allowed, but must not invent
   company events, numeric thresholds, valuation, or available documents.
   Never add consecutive-quarter/month triggers, count-based exit rules, or spelled-out numeric gates.
6. Preserve the five-section structure and exact field labels. Preserve useful evidence-backed detail, filename
   citations, and every valid [C#]/[I#] reference; do not replace the answer with a generic refusal. If a sentence is
   removed, remove only its reference. Never return a company fact without a C reference or industry context without I.
7. Set evidence_control_passed true only after every unsupported company claim and overreaching inference is removed.

PROJECT: {project.company_name}; {project.industry}; {project.stage}
QUESTION: {message}
WORK PLAN:
{answer}
VERIFIED CLAIM LEDGER:
{ledger_text}
""".strip()).strip()
        try:
            cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(cleaned)
            revised = result.get("revised_answer") if isinstance(result, dict) else None
            if not isinstance(result, dict) or result.get("evidence_control_passed") is not True or not isinstance(revised, str):
                return None
            guarded = self._remove_unsupported_numeric_lines(revised.strip(), context_parts)
            guarded = EvidenceLedgerService.anchor_references(guarded, claim_ledger)
            issues = self._strategy_structure_issues(guarded, context_parts)
            issues.extend(EvidenceLedgerService.reference_issues(guarded, claim_ledger))
            return guarded if not issues else None
        except (json.JSONDecodeError, RuntimeError):
            return None

    @staticmethod
    def _strategy_repair_prompt(
        project,
        message: str,
        draft: str,
        context_parts: list[str],
        missing_evidence: list[str],
        failed_checks: list[str],
        claim_ledger: list[EvidenceClaim],
    ) -> str:
        ledger_text = EvidenceLedgerService.serialize(claim_ledger)
        return f"""
You are the second and final evidence-control reviewer. Repair the draft into a professionally usable institutional
investment work plan using only the evidence pack. Delete unsupported claims rather than rationalizing them.

The previous draft failed these checks: {', '.join(failed_checks)}.
The repaired answer must contain IC Summary, Pre-Investment, During-Investment, Post-Investment, and Evidence Gaps.
Each stage must explicitly label company-disclosed facts, analyst inference, verification action, IC gate, and cannot
assess items. Verification actions must name the exact field, primary source, and reconciliation. IC gates name decision
variables but never invent thresholds. Do not request documents already present in the evidence pack. Cite filenames.
Use these exact English field labels in every stage, even when a field has no supported content: Company-disclosed
facts, Analyst inference, Verification action, IC gate, Cannot assess. The values may be written in Chinese.
Only C claims support company facts. I claims are scenario context only. Every company fact must cite [C#], and every
industry-context statement must cite [I#]. Unknown claim IDs are prohibited.
When both company and industry roles are available, cite at least one filename from each and label the industry source
as a scenario baseline rather than evidence about the company.
Return JSON only:
{{"revised_answer":"...","removed_or_reframed_claims":["..."],"evidence_control_passed":true}}
Set evidence_control_passed true only if every factual claim and number is supported by the evidence pack.

PROJECT: {project.company_name}; {project.industry}; {project.stage}
USER QUESTION: {message}
KNOWN GAPS:
{chr(10).join(missing_evidence)}
DRAFT TO REPAIR:
{draft}
VERIFIED CLAIM LEDGER:
{ledger_text}
""".strip()

    @staticmethod
    def _fallback_strategy_answer(missing_evidence: list[str]) -> str:
        gaps = "\n".join(f"- {item}" for item in missing_evidence) or "- 当前自动检查未发现明显缺口，仍需人工复核原始来源。"
        return (
            "## 建议\n现有证据不足以形成可提交投委会的投资结论。建议仅进入资料补充与事实核验阶段，暂不设定估值、仓位或交易条件。\n\n"
            "## 待补充/待验证\n" + gaps + "\n\n"
            "## 下一步动作\n按上述清单补齐原始资料，完成来源交叉验证后重新运行投前分析。"
        )

    def _recover_strategy_answer(
        self,
        project,
        claims: list[EvidenceClaim],
        context_parts: list[str],
        missing_evidence: list[str],
        model_issues: list[str],
    ) -> tuple[str, bool, list[str]]:
        company_claims = [claim for claim in claims if claim.document_role == "company_disclosure"]
        if not company_claims:
            return self._fallback_strategy_answer(missing_evidence), False, model_issues

        def select(categories: tuple[str, ...], limit: int = 4) -> list[EvidenceClaim]:
            selected = [claim for claim in company_claims if claim.category in categories][:limit]
            return selected or company_claims[:limit]

        def facts(items: list[EvidenceClaim]) -> str:
            return "; ".join(
                f"{item.claim} [{item.claim_id}] ({item.source_filename})" for item in items
            )

        context_claims = [claim for claim in claims if claim.document_role == "industry_context"][:3]
        context_text = "; ".join(
            f"{item.claim} [{item.claim_id}] ({item.source_filename})" for item in context_claims
        ) or "No verified industry-context claim is available."
        gap_names = [item.split(":", 1)[0].strip() for item in missing_evidence if item.strip()]
        gap_text = ", ".join(gap_names) or "valuation, transaction terms, and independent source reconciliation"
        pre = select(("financial", "business", "market", "competition", "customers"))
        during = select(("risk", "legal", "governance", "financial"))
        post = select(("customers", "business", "risk", "financial"))
        answer = f"""
## IC Summary
The verified ledger for {project.company_name} supports a preliminary evidence work plan, not an unconditional investment recommendation. Company disclosures establish: {facts(pre[:3])}. Industry context is a scenario baseline only and is not evidence about the company: {context_text}. Valuation, position size, transaction terms, and causal forecasts remain unassessed until the named primary-source fields are reconciled.

## Pre-Investment
- **Company-disclosed facts**: {facts(pre)}.
- **Analyst inference**: Only the disclosed facts above are established. They do not by themselves establish valuation, persistence, causality, competitive advantage, or investability.
- **Verification action**: Reconcile revenue, earnings, cash flow, balance-sheet, segment, customer, and ownership fields from the cited source files to the audited primary statements and the transaction model; record every variance and source date.
- **IC gate**: Proceed only after the committee confirms source reconciliation, valuation inputs, transaction mandate, and decision-variable thresholds. No numeric threshold is inferred here.
- **Cannot assess**: {gap_text}; market pricing and recommendation strength cannot currently be assessed.

## During-Investment
- **Company-disclosed facts**: {facts(during)}.
- **Analyst inference**: The ledger supports monitoring these disclosed fields only; it does not prove a trend will persist or that an identified risk has occurred.
- **Verification action**: Reconcile each periodic KPI and covenant field to signed statements, bank or custodian evidence, and the approved transaction model; escalate unexplained differences to the investment committee.
- **IC gate**: Continue funding or execution only when reporting scope, covenant status, data lineage, and mandate-defined variance thresholds are confirmed by the committee.
- **Cannot assess**: Future performance, financing availability, legal outcome, and management execution cannot be assessed without current primary evidence.

## Post-Investment
- **Company-disclosed facts**: {facts(post)}.
- **Analyst inference**: These claims define an initial monitoring baseline only and do not establish exit timing, realized value, or attribution.
- **Verification action**: Reconcile periodic operating, liquidity, customer, governance, and risk fields to source systems and approved board reporting; preserve dated evidence for every change.
- **IC gate**: Escalate, hold, or exit only under mandate-approved decision variables after the underlying evidence is verified; no count-based or numeric trigger is invented here.
- **Cannot assess**: Exit value, return attribution, downside recovery, and post-investment trend persistence cannot currently be assessed.

## Evidence Gaps
{chr(10).join(f"- {item}" for item in missing_evidence) or "- Independent verification and transaction-specific inputs remain required."}
""".strip()
        issues = self._strategy_structure_issues(answer, context_parts)
        issues.extend(EvidenceLedgerService.reference_issues(answer, claims))
        if issues:
            return self._fallback_strategy_answer(missing_evidence), False, model_issues + issues
        return answer, True, ["model draft failed evidence gates; deterministic evidence plan used"]

    @staticmethod
    def _remove_unsupported_numeric_lines(answer: str, context_parts: list[str]) -> str:
        """Drop quantitative claims whose values do not occur in the retrieved evidence."""
        evidence = re.sub(r"[,$\s]", "", "\n".join(context_parts).lower())
        kept: list[str] = []
        for line in answer.splitlines():
            line = ChatService._remove_invented_period_triggers(line, evidence)
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "- **", "**")) and not re.search(r"\d", stripped):
                kept.append(line)
                continue
            tokens = re.findall(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?%?", line)
            unsupported = []
            for token in tokens:
                normalized = re.sub(r"[,$\s]", "", token.lower())
                if len(normalized.rstrip("%")) <= 1 or normalized in evidence:
                    continue
                unsupported.append(token)
            if not unsupported:
                kept.append(line)
        return "\n".join(kept).strip()

    @staticmethod
    def _remove_invented_period_triggers(line: str, normalized_evidence: str) -> str:
        parts = re.split(r"(?<=[。！？.!?])", line)
        kept: list[str] = []
        for part in parts:
            lowered = part.lower()
            has_period_count = bool(re.search(
                r"连续\s*[一二两三四五六七八九十\d]+\s*个?\s*(季度|月|周|年)|"
                r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+consecutive\s+(quarters?|months?|weeks?|years?)",
                lowered,
            ))
            is_gate = any(marker in lowered for marker in (
                "退出", "减持", "停止", "触发", "否决", "exit", "reduce", "stop", "trigger", "reject",
            ))
            normalized = re.sub(r"[,$\s]", "", lowered)
            if has_period_count and is_gate and normalized not in normalized_evidence:
                continue
            kept.append(part)
        return "".join(kept)

    @staticmethod
    def _strategy_structure_issues(answer: str, context_parts: list[str]) -> list[str]:
        lowered = answer.lower()
        required_sections = {
            "IC summary": ("ic summary", "投委会摘要", "投委摘要"),
            "pre-investment": ("pre-investment", "投前"),
            "during-investment": ("during-investment", "投中"),
            "post-investment": ("post-investment", "投后"),
            "evidence gaps": ("evidence gaps", "证据缺口", "资料缺口"),
        }
        issues = [label for label, markers in required_sections.items() if not any(marker in lowered for marker in markers)]
        semantic_markers = {
            "company-disclosed facts": ("company-disclosed", "公司披露"),
            "analyst inference": ("analyst inference", "分析师推断", "分析师判断", "分析推断", "直接推断", "直接推论", "证据含义"),
            "verification action": ("verification", "reconcile", "核验", "验证"),
            "IC gate": ("ic gate", "ic门", "决策门", "决策门槛", "投委门", "投委会门槛", "门槛条件", "决策条件", "通过条件", "批准条件", "触发条件"),
            "cannot assess": ("cannot assess", "无法判断", "暂不判断", "无法评估"),
        }
        issues.extend(label for label, markers in semantic_markers.items() if not any(marker in lowered for marker in markers))
        if any(marker in lowered for marker in ("may indicate", "could indicate", "may reflect", "could reflect")):
            issues.append("unsupported causal inference language")
        evidence = "\n".join(context_parts).lower()
        has_annual_filing = "annual report" in evidence or "form 10-k" in evidence or "form 10k" in evidence
        requests_annual_filing = bool(re.search(
            r"\b(?:obtain|request)\b.{0,100}\b(?:annual report|audited financial statements?|10-k|10k)\b",
            lowered,
            re.DOTALL,
        ))
        if has_annual_filing and requests_annual_filing:
            issues.append("requests an annual filing already present in evidence")
        if len(answer) < 800:
            issues.append("answer too short for a staged IC work plan")
        return issues
