import json
import re

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.llm_service import LLMService
from app.repositories.chat_repository import ChatRepository
from app.repositories.file_repository import FileRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.chat import Citation, ChatResponse
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
            ))
            context_parts.append(f"[{filename}] {chunk.content}")

        requirements = ResearchService(self.db).requirements(project_id)
        missing_evidence = [
            f"{item.label}: {item.reason} 建议补充：{item.suggested_document}"
            for item in requirements if item.status.value != "covered"
        ]
        self.chat_repo.create(project_id=project_id, role="user", content=message)
        evidence_control_passed = None
        if is_strategy_question:
            answer, evidence_control_passed = self._ground_strategy_answer(project, message, context_parts, missing_evidence)
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
        )

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
Never invent numbers, market data, interviews, forecasts, valuation, or legal conclusions.

User question:
{message}

Known evidence gaps:
{chr(10).join(missing_evidence) or "No material gap detected by the automated coverage check; human verification is still required."}

Materials:
{chr(10).join(context_parts)}
""".strip()

    def _ground_strategy_answer(
        self, project, message: str, context_parts: list[str], missing_evidence: list[str]
    ) -> tuple[str, bool]:
        prompt = f"""
You are the final evidence-control analyst for an institutional investment committee. Generate the answer directly and
only from the evidence pack below. Do not use outside knowledge, memory, or assumptions about the company or industry.

Non-negotiable review rules:
1. Every number, named product, named competitor, customer concentration, pipeline code, market claim, and financial
   trend must be explicitly present in the evidence below. If not, delete it or move it to missing evidence as a question.
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
7. Keep the recommendation conditional and operational. Allowed actions are evidence requests, interviews, model checks,
   regulatory verification, scenario analysis, and IC gates grounded in stated missing information.
   When evidence for a requested dimension is absent, say it cannot be assessed; do not relabel the absence as a risk.
8. Return JSON only with this shape:
   {{"revised_answer":"...", "removed_or_reframed_claims":["..."], "evidence_control_passed":true}}
   Set evidence_control_passed to true only when every factual claim and number is supported by the evidence pack.

KNOWN GAPS:
{chr(10).join(missing_evidence)}

PROJECT:
{project.company_name}; {project.industry}; {project.stage}

USER QUESTION:
{message}

EVIDENCE PACK:
{chr(10).join(context_parts)}
""".strip()
        try:
            raw = self.llm_service.generate(prompt).strip()
            cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(cleaned)
            revised = result.get("revised_answer") if isinstance(result, dict) else None
            passed = result.get("evidence_control_passed") if isinstance(result, dict) else None
            if not isinstance(revised, str) or not revised.strip():
                raise RuntimeError("Evidence-controlled strategy response was malformed")
            if passed is not True:
                raise RuntimeError("Evidence control did not pass")
            guarded = self._remove_unsupported_numeric_lines(revised.strip(), context_parts)
            if not guarded:
                raise RuntimeError("Evidence control removed the complete response")
            return guarded, True
        except (RuntimeError, json.JSONDecodeError):
            return self._fallback_strategy_answer(missing_evidence), False

    @staticmethod
    def _fallback_strategy_answer(missing_evidence: list[str]) -> str:
        gaps = "\n".join(f"- {item}" for item in missing_evidence) or "- 当前自动检查未发现明显缺口，仍需人工复核原始来源。"
        return (
            "## 建议\n现有证据不足以形成可提交投委会的投资结论。建议仅进入资料补充与事实核验阶段，暂不设定估值、仓位或交易条件。\n\n"
            "## 待补充/待验证\n" + gaps + "\n\n"
            "## 下一步动作\n按上述清单补齐原始资料，完成来源交叉验证后重新运行投前分析。"
        )

    @staticmethod
    def _remove_unsupported_numeric_lines(answer: str, context_parts: list[str]) -> str:
        """Drop quantitative claims whose values do not occur in the retrieved evidence."""
        evidence = re.sub(r"[,$\s]", "", "\n".join(context_parts).lower())
        kept: list[str] = []
        for line in answer.splitlines():
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
