from __future__ import annotations

import hashlib
import ipaddress
import mimetypes
import re
import socket
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx
import fitz
from ddgs import DDGS
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.file import ParseStage, ParseStatus, ProjectFile
from app.models.chunk import DocumentChunk
from app.models.project import Project
from app.models.research import EvidenceRequirement, EvidenceStatus, ResearchSource, ResearchSourceStatus
from app.repositories.project_repository import ProjectRepository
from app.storage.storage_service import get_storage_service


EVIDENCE_CATEGORIES = (
    ("business", "商业模式与产品", ("business model", "product", "revenue model", "商业模式", "产品"), "高", "产品级收入拆分、定价与单位经济性、管理层访谈纪要"),
    ("financial", "财务表现与现金流", ("revenue", "gross margin", "cash flow", "balance sheet", "收入", "毛利", "现金流"), "高", "最新季度报表、预算差异、债务与现金流明细、预测模型"),
    ("market", "市场空间与行业趋势", ("market size", "industry outlook", "tam", "市场规模", "行业趋势"), "中", "公司细分市场定义、第三方规模数据与市场份额映射"),
    ("competition", "竞争格局", ("competition", "competitor", "market share", "竞争", "市场份额"), "高", "产品级竞品对标、可比公司口径、市场份额与客户访谈"),
    ("team", "核心团队与治理", ("management", "director", "founder", "governance", "管理层", "创始人", "公司治理"), "高", "关键管理层履历、组织职责、董事会与激励约束材料"),
    ("legal", "法律合规与知识产权", ("litigation", "regulation", "patent", "compliance", "诉讼", "合规", "专利"), "高", "重大诉讼进展、监管检查、许可与核心知识产权清单"),
    ("customers", "客户与商业验证", ("customer", "contract", "retention", "客户", "合同", "留存"), "高", "客户集中度、留存与续约、核心合同及独立客户访谈"),
    ("valuation", "估值与交易条款", ("valuation", "enterprise value", "term sheet", "估值", "交易条款"), "高", "实时市场价格、可比公司口径、投资授权与拟议交易条款"),
)

TRUSTED_DOMAINS = (
    "sec.gov", "worldbank.org", "imf.org", "oecd.org", "who.int", "fda.gov", "europa.eu",
    "gov.cn", "stats.gov.cn", "samr.gov.cn", "cninfo.com.cn", "sse.com.cn", "szse.cn", "hkexnews.hk",
    "energy.gov", "nrel.gov", "iea.org", "irena.org", "federalreserve.gov", "nist.gov",
    "census.gov", "bea.gov", "bls.gov", "ftc.gov",
)

SEARCH_TERMS = {
    "business": "business model products annual report",
    "financial": "financial statements cash flow annual report",
    "market": "industry outlook market report",
    "competition": "competition market share annual report",
    "team": "management governance proxy statement",
    "legal": "regulatory litigation patents filing",
    "customers": "customers contracts retention annual report",
    "valuation": "valuation transaction filing",
}

CATEGORY_RELEVANCE_TERMS = {
    "business": ("business model", "product", "revenue model", "产品", "商业模式"),
    "financial": ("financial", "revenue", "cash flow", "balance sheet", "财务", "现金流"),
    "competition": ("competition", "competitor", "market share", "竞争", "市场份额"),
    "team": ("management", "director", "governance", "管理层", "治理"),
    "legal": ("regulation", "litigation", "patent", "compliance", "合规", "诉讼", "专利"),
    "customers": ("customer", "contract", "retention", "客户", "合同"),
    "valuation": ("valuation", "transaction", "offering", "enterprise value", "估值", "交易"),
}

INDUSTRY_STOP_WORDS = {"and", "the", "with", "industry", "sector", "company", "services"}

REQUIREMENT_FIELDS = {
    "business": (
        ("products", "产品与服务清单", ("product", "service", "产品", "服务")),
        ("revenue_model", "收入模式与定价", ("revenue model", "pricing", "subscription", "定价", "收入模式")),
        ("unit_economics", "单位经济性", ("unit economics", "gross margin", "contribution margin", "单位经济", "毛利率")),
        ("delivery", "交付与供应链", ("delivery", "supplier", "supply chain", "交付", "供应链")),
    ),
    "financial": (
        ("income", "收入、利润与增长", ("revenue", "net income", "operating income", "收入", "净利润")),
        ("cash_flow", "经营现金流与自由现金流", ("cash flow", "free cash flow", "经营现金流", "自由现金流")),
        ("balance_sheet", "现金、债务与资产负债", ("balance sheet", "cash and cash equivalents", "debt", "资产负债", "债务")),
        ("forecast", "预算、预测与实际差异", ("forecast", "guidance", "budget", "预测", "预算")),
    ),
    "market": (
        ("definition", "细分市场定义", ("addressable market", "market definition", "细分市场", "目标市场")),
        ("size", "市场规模与增速", ("market size", "tam", "cagr", "市场规模", "增速")),
        ("drivers", "行业驱动因素", ("industry trend", "growth driver", "行业趋势", "驱动因素")),
        ("regulation", "政策与监管环境", ("regulation", "policy", "监管", "政策")),
    ),
    "competition": (
        ("competitors", "主要竞争对手", ("competitor", "competition", "竞争对手", "竞争")),
        ("position", "市场份额与竞争位置", ("market share", "competitive position", "市场份额", "竞争地位")),
        ("differentiation", "产品差异化与壁垒", ("differentiation", "competitive advantage", "差异化", "竞争优势")),
        ("benchmark", "可比公司与指标口径", ("peer", "comparable", "benchmark", "可比公司", "对标")),
    ),
    "team": (
        ("roster", "管理层名单与职务", ("chief executive", "management", "executive", "管理层", "高管")),
        ("background", "核心成员履历与行业经验", ("served as", "previously served", "appointed", "joined the company", "履历", "曾任")),
        ("board", "董事会构成与独立性", ("independent director", "board composition", "board independence", "独立董事", "董事会构成")),
        ("incentives", "股权、薪酬与激励约束", ("executive compensation", "stock award", "long-term incentive", "compensation committee", "高管薪酬", "股权激励")),
        ("succession", "关键人依赖与继任计划", ("succession", "key person", "继任", "关键人")),
    ),
    "legal": (
        ("licenses", "资质许可与监管要求", ("license", "regulatory", "许可", "监管")),
        ("litigation", "重大诉讼与争议", ("litigation", "legal proceeding", "诉讼", "争议")),
        ("compliance", "合规体系与处罚记录", ("compliance", "penalty", "合规", "处罚")),
        ("ip", "知识产权与权属", ("patent", "trademark", "intellectual property", "专利", "知识产权")),
    ),
    "customers": (
        ("concentration", "客户集中度", ("customer concentration", "major customer", "客户集中", "主要客户")),
        ("retention", "留存、续约与流失", ("retention", "renewal", "churn", "留存", "续约")),
        ("contracts", "核心合同与剩余期限", ("customer contract", "contract term", "客户合同", "合同期限")),
        ("references", "客户访谈与满意度", ("customer survey", "satisfaction", "客户访谈", "满意度")),
    ),
    "valuation": (
        ("price", "当前价格与估值基准", ("market capitalization", "valuation", "估值", "市值")),
        ("multiples", "可比公司与估值倍数", ("multiple", "price earnings", "enterprise value", "估值倍数", "市盈率")),
        ("terms", "拟议交易条款", ("term sheet", "transaction terms", "交易条款", "投资协议")),
        ("mandate", "投资授权与仓位约束", ("investment mandate", "position limit", "投资授权", "仓位")),
    ),
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.ignored:
            self.ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored and data.strip():
            self.parts.append(data.strip())


class ResearchService:
    def __init__(self, db: Session):
        self.db = db
        self.project_repo = ProjectRepository(db)

    def workspace(self, project_id: str, owner_id: str) -> tuple[list[EvidenceRequirement], list[ResearchSource]]:
        self._project(project_id, owner_id)
        requirements = self.requirements(project_id)
        sources = list(self.db.scalars(
            select(ResearchSource).where(ResearchSource.project_id == project_id).order_by(ResearchSource.discovered_at.desc())
        ))
        return requirements, sources

    def requirements(self, project_id: str) -> list[EvidenceRequirement]:
        cached = list(self.db.scalars(
            select(EvidenceRequirement)
            .where(EvidenceRequirement.project_id == project_id)
            .order_by(EvidenceRequirement.priority, EvidenceRequirement.label)
        ))
        return cached or self.refresh_requirements(project_id)

    def requirement_detail(self, project_id: str, requirement_id: str, owner_id: str) -> dict:
        self._project(project_id, owner_id)
        requirement = self.db.scalar(select(EvidenceRequirement).where(
            EvidenceRequirement.id == requirement_id,
            EvidenceRequirement.project_id == project_id,
        ))
        if not requirement:
            raise ValueError("Evidence requirement not found")
        definitions = REQUIREMENT_FIELDS.get(requirement.category, ())
        all_keywords = tuple(dict.fromkeys(keyword for _key, _label, keywords in definitions for keyword in keywords))
        chunks = list(self.db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.project_id == project_id,
                or_(*(DocumentChunk.content.ilike(f"%{keyword}%") for keyword in all_keywords)),
            )
            .order_by(DocumentChunk.chunk_index)
            .limit(80)
        )) if all_keywords else []
        files = {item.id: item for item in self.db.scalars(
            select(ProjectFile).where(ProjectFile.project_id == project_id)
        )}
        fields: list[dict] = []
        used_file_ids: list[str] = []
        for key, label, keywords in definitions:
            ranked = sorted(
                chunks,
                key=lambda chunk: sum(keyword.lower() in chunk.content.lower() for keyword in keywords),
                reverse=True,
            )
            match = next((
                chunk for chunk in ranked
                if any(keyword.lower() in chunk.content.lower() for keyword in keywords)
                and self._is_substantive_evidence(chunk.content)
            ), None)
            source_file = files.get(match.file_id) if match else None
            if source_file and source_file.id not in used_file_ids:
                used_file_ids.append(source_file.id)
            fields.append({
                "key": key,
                "label": label,
                "status": "found" if match else "missing",
                "evidence_excerpt": self._evidence_excerpt(match.content, keywords) if match else "",
                "source_file_id": source_file.id if source_file else None,
                "source_filename": source_file.filename if source_file else None,
            })
        related_files = [files[file_id] for file_id in used_file_ids]
        related_sources = list(self.db.scalars(
            select(ResearchSource)
            .where(ResearchSource.project_id == project_id, ResearchSource.evidence_category == requirement.category)
            .order_by(ResearchSource.discovered_at.desc())
            .limit(20)
        ))
        return {
            "requirement": requirement,
            "fields": fields,
            "related_files": related_files,
            "related_sources": related_sources,
        }

    @staticmethod
    def _evidence_excerpt(content: str, keywords: tuple[str, ...], radius: int = 260) -> str:
        lowered = content.lower()
        positions = [lowered.find(keyword.lower()) for keyword in keywords]
        position = min((value for value in positions if value >= 0), default=0)
        start = max(0, position - radius)
        end = min(len(content), position + radius)
        excerpt = re.sub(r"\s+", " ", content[start:end]).strip()
        return ("..." if start else "") + excerpt + ("..." if end < len(content) else "")

    @staticmethod
    def _is_substantive_evidence(content: str) -> bool:
        """Reject filing indexes that mention topics without disclosing underlying facts."""
        lowered = content.lower()
        if "table of contents" in lowered:
            return False
        return len(re.findall(r"\bitem\s+\d+[a-z]?\b", lowered)) < 3

    def refresh_requirements(self, project_id: str) -> list[EvidenceRequirement]:
        rows = list(self.db.execute(
            select(ProjectFile.parsed_text, ProjectFile.table_text, ProjectFile.parse_status)
            .where(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.created_at.desc())
            .limit(50)
        ))
        # Coverage checks need representative evidence, not every byte of very large filings.
        # Capping each field avoids loading an unbounded corpus into an API request.
        corpus = "\n".join(
            item[:200_000] for row in rows for item in (row.parsed_text or "", row.table_text or "") if item
        ).lower()
        completed_count = sum(row.parse_status == ParseStatus.completed for row in rows)
        existing = {item.category: item for item in self.db.scalars(
            select(EvidenceRequirement).where(EvidenceRequirement.project_id == project_id)
        )}
        for category, label, keywords, priority, suggested in EVIDENCE_CATEGORIES:
            hits = sum(keyword in corpus for keyword in keywords)
            status = EvidenceStatus.covered if hits >= 3 else EvidenceStatus.partial if hits else EvidenceStatus.missing
            if not completed_count:
                reason = "项目尚无已解析资料，无法形成可核验结论。"
            elif status == EvidenceStatus.covered:
                reason = f"已在项目资料中识别到 {hits} 组相关证据，仍需人工复核来源时效。"
            elif status == EvidenceStatus.partial:
                reason = "现有资料仅有零散提及，缺少可交叉验证的完整证据。"
            else:
                reason = "现有项目资料未发现该维度的有效证据。"
            item = existing.get(category) or EvidenceRequirement(project_id=project_id, category=category)
            item.label = label
            item.status = status
            item.priority = priority
            item.reason = reason
            item.suggested_document = suggested
            self.db.add(item)
        self.db.commit()
        return list(self.db.scalars(
            select(EvidenceRequirement).where(EvidenceRequirement.project_id == project_id).order_by(EvidenceRequirement.priority, EvidenceRequirement.label)
        ))

    def enrich(self, project_id: str, owner_id: str) -> dict[str, int]:
        if not settings.research_enabled:
            raise RuntimeError("Public research enrichment is disabled")
        project = self._project(project_id, owner_id)
        gaps = [item for item in self.refresh_requirements(project_id) if item.status != EvidenceStatus.covered]
        discovered = ingested = failed = 0
        ranked_results: list[tuple[bool, EvidenceRequirement, dict]] = []
        for gap in gaps:
            trusted_query = self._trusted_query(project, gap.category)
            trusted_results = self._search(trusted_query, max_results=3)
            for result in trusted_results:
                ranked_results.append((True, gap, result))
            if not trusted_results:
                general_query = f'"{project.company_name}" {project.industry} {SEARCH_TERMS[gap.category]} filetype:pdf'
                for result in self._search(general_query, max_results=2):
                    ranked_results.append((False, gap, result))

        seen_urls: set[str] = set()
        for expected_trusted, gap, result in sorted(ranked_results, key=lambda item: not item[0]):
            if discovered >= settings.research_max_sources_per_run:
                break
            url = str(result.get("href") or result.get("url") or "")
            if not url or url in seen_urls or self._existing_source(project_id, url):
                continue
            seen_urls.add(url)
            title = str(result.get("title") or url)[:500]
            snippet = str(result.get("body") or "")[:4000]
            domain = (urlparse(url).hostname or "").lower()
            trusted = expected_trusted and self._is_trusted_domain(domain)
            if trusted and gap.category == "valuation" and self._is_sec_domain(domain):
                trusted = False
            if trusted and not self._result_is_relevant(project, gap.category, result):
                continue
            source = ResearchSource(
                project_id=project_id, evidence_category=gap.category, title=title,
                publisher=domain, domain=domain, url=url, url_hash=self._hash_url(url), snippet=snippet,
                quality="official" if trusted else "candidate",
                status=ResearchSourceStatus.discovered if trusted else ResearchSourceStatus.review_required,
            )
            self.db.add(source)
            self.db.commit()
            discovered += 1
            if not trusted:
                continue
            try:
                file = self._download_and_store(project, owner_id, source)
                source.file_id = file.id
                source.status = ResearchSourceStatus.ingested
                source.fetched_at = datetime.now(timezone.utc)
                self.db.commit()
                from app.workers.tasks import parse_uploaded_file_task
                parse_uploaded_file_task.delay(file.id)
                ingested += 1
            except Exception as exc:
                source.status = ResearchSourceStatus.failed
                source.error = str(exc)[:2000]
                self.db.commit()
                failed += 1
        return {"discovered": discovered, "ingested": ingested, "failed": failed}

    def _trusted_query(self, project: Project, category: str) -> str:
        industry = project.industry.lower()
        if category == "market":
            if any(term in industry for term in ("bank", "financial", "fintech", "insurance", "asset management")):
                return f'site:federalreserve.gov "financial stability" {project.industry} filetype:pdf'
            if any(term in industry for term in ("manufactur", "industrial", "machinery", "construction equipment")):
                return f'site:nist.gov "manufacturing economy" {project.industry} filetype:pdf'
            if any(term in industry for term in ("retail", "consumer", "commerce", "grocery")):
                return f'site:census.gov OR site:bea.gov "consumer spending" {project.industry}'
            if any(term in industry for term in ("bio", "pharma", "health")):
                return f'site:fda.gov "{project.company_name}" industry report filetype:pdf'
            if any(term in industry for term in ("energy", "solar", "power")):
                return f'site:energy.gov OR site:nrel.gov "{project.industry}" market report filetype:pdf'
            return f'site:worldbank.org "{project.industry}" industry report filetype:pdf'
        return f'site:sec.gov/Archives/edgar/data "{project.company_name}" {SEARCH_TERMS[category]}'

    @staticmethod
    def _search(query: str, max_results: int) -> list[dict]:
        try:
            return list(DDGS(timeout=settings.research_request_timeout_seconds).text(query, max_results=max_results) or [])
        except Exception:
            return []

    def _download_and_store(self, project: Project, owner_id: str, source: ResearchSource) -> ProjectFile:
        self._validate_public_url(source.url)
        headers = {"User-Agent": settings.research_user_agent, "Accept": "application/pdf,text/html,text/plain;q=0.9,*/*;q=0.1"}
        with httpx.Client(timeout=settings.research_request_timeout_seconds, follow_redirects=True, headers=headers) as client:
            response = client.get(source.url)
            response.raise_for_status()
            self._validate_public_url(str(response.url))
            content = response.content
        if not content or len(content) > settings.research_download_max_bytes:
            raise ValueError("Research document is empty or exceeds the download limit")
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        suffix = Path(urlparse(str(response.url)).path).suffix.lower()
        if content_type == "application/pdf" or suffix == ".pdf":
            readable_text = self._pdf_preview_text(content)
            filename = self._safe_filename(source.title, ".pdf")
            stored_content = content
            stored_type = "application/pdf"
        elif content_type.startswith("text/") or content_type in {"application/xhtml+xml", "application/xml"}:
            extractor = _TextExtractor()
            extractor.feed(content.decode(response.encoding or "utf-8", errors="replace"))
            text = "\n".join(extractor.parts)
            if len(text) < 200:
                raise ValueError("Research page contains insufficient readable text")
            filename = self._safe_filename(source.title, ".txt")
            stored_content = f"Source: {source.url}\nPublisher: {source.publisher}\n\n{text}".encode("utf-8")
            stored_type = "text/plain"
        else:
            raise ValueError(f"Unsupported research content type: {content_type or 'unknown'}")
        readable_content = readable_text if stored_type == "application/pdf" else text
        if not self._content_is_relevant(project, source.evidence_category, readable_content):
            raise ValueError("Official source does not contain enough project-relevant evidence")
        if self._is_sec_domain(source.domain) and not self._sec_document_is_current_filing(
            source.evidence_category, source.url, readable_content
        ):
            raise ValueError("SEC source is stale or is not a current company filing")
        key = f"tenants/{owner_id}/{project.id}/research/{uuid.uuid4()}{Path(filename).suffix}"
        stored = get_storage_service().upload_file(key, stored_content, stored_type)
        file = ProjectFile(
            project_id=project.id, filename=filename, content_type=stored_type, size=len(stored_content),
            r2_bucket=stored.bucket, r2_object_key=stored.object_key, parse_status=ParseStatus.pending,
            parse_stage=ParseStage.validate, progress=10, source_kind="public_research",
            source_url=source.url, source_quality=source.quality,
        )
        self.db.add(file)
        self.db.commit()
        self.db.refresh(file)
        return file

    def _project(self, project_id: str, owner_id: str) -> Project:
        project = self.project_repo.get_for_owner(project_id, owner_id)
        if not project:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    def _existing_source(self, project_id: str, url: str) -> bool:
        return self.db.scalar(select(ResearchSource.id).where(
            ResearchSource.project_id == project_id, ResearchSource.url_hash == self._hash_url(url)
        )) is not None

    @classmethod
    def _result_is_relevant(cls, project: Project, category: str, result: dict) -> bool:
        haystack = " ".join(str(result.get(key) or "") for key in ("title", "body", "href", "url"))
        normalized = cls._normalize_relevance_text(haystack)
        if category == "market":
            return cls._market_content_is_relevant(project.industry, normalized)
        return any(alias in normalized for alias in cls._company_aliases(project.company_name))

    @classmethod
    def _content_is_relevant(cls, project: Project, category: str, content: str) -> bool:
        normalized = cls._normalize_relevance_text(content)
        if category != "market":
            aliases = cls._company_aliases(project.company_name)
            company_mentions = max((normalized.count(alias) for alias in aliases), default=0)
            category_terms = CATEGORY_RELEVANCE_TERMS.get(category, ())
            category_match = any(cls._normalize_relevance_text(term) in normalized for term in category_terms)
            return company_mentions >= 2 and category_match
        return cls._market_content_is_relevant(project.industry, normalized)

    @classmethod
    def _market_content_is_relevant(cls, industry: str, normalized_content: str) -> bool:
        terms = {
            cls._normalize_relevance_text(term)
            for term in re.split(r"[\s,/&|()-]+", industry)
            if len(cls._normalize_relevance_text(term)) >= 4 and term.lower() not in INDUSTRY_STOP_WORDS
        }
        required_matches = min(2, len(terms))
        return bool(terms) and sum(term in normalized_content for term in terms) >= required_matches

    @staticmethod
    def _normalize_relevance_text(value: str) -> str:
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())

    @classmethod
    def _company_aliases(cls, company_name: str) -> set[str]:
        base = re.sub(
            r"\b(incorporated|corporation|company|limited|holdings?|group|inc|corp|co|ltd|llc|plc)\.?\b",
            " ",
            company_name,
            flags=re.IGNORECASE,
        )
        return {
            alias for alias in (cls._normalize_relevance_text(company_name), cls._normalize_relevance_text(base))
            if len(alias) >= 4
        }

    @staticmethod
    def _pdf_preview_text(content: bytes) -> str:
        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                return "\n".join(document.load_page(index).get_text("text") for index in range(min(20, document.page_count)))
        except Exception as exc:
            raise ValueError("Official PDF could not be inspected for relevance") from exc

    @staticmethod
    def _is_sec_domain(domain: str) -> bool:
        return domain == "sec.gov" or domain.endswith(".sec.gov")

    @staticmethod
    def _sec_document_is_current_filing(category: str, url: str, content: str) -> bool:
        if category == "valuation":
            return False
        lowered = content.lower()
        allowed_filing = any(marker in lowered for marker in (
            "form 10-k", "form 10-q", "annual report", "proxy statement", "earnings release",
        ))
        current_year = datetime.now(timezone.utc).year
        recent = any(str(year) in url or str(year) in lowered[:50_000] for year in range(current_year - 2, current_year + 1))
        return allowed_filing and recent

    @staticmethod
    def _hash_url(url: str) -> str:
        return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()

    @staticmethod
    def _is_trusted_domain(domain: str) -> bool:
        return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in TRUSTED_DOMAINS)

    @classmethod
    def _validate_public_url(cls, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or not cls._is_trusted_domain(parsed.hostname.lower()):
            raise ValueError("Research URL is not on the trusted HTTPS allowlist")
        for result in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(result[4][0])
            if not address.is_global:
                raise ValueError("Research URL resolves to a non-public address")

    @staticmethod
    def _safe_filename(title: str, suffix: str) -> str:
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-.")[:120] or "public-research"
        return f"{stem}{suffix}"
