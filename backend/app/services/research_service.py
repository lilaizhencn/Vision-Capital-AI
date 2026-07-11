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
from ddgs import DDGS
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.file import ParseStage, ParseStatus, ProjectFile
from app.models.project import Project
from app.models.research import EvidenceRequirement, EvidenceStatus, ResearchSource, ResearchSourceStatus
from app.repositories.project_repository import ProjectRepository
from app.storage.storage_service import get_storage_service


EVIDENCE_CATEGORIES = (
    ("business", "商业模式与产品", ("business model", "product", "revenue model", "商业模式", "产品"), "高", "BP、产品手册或年度报告"),
    ("financial", "财务表现与现金流", ("revenue", "gross margin", "cash flow", "balance sheet", "收入", "毛利", "现金流"), "高", "近三年审计报告、月度财务报表和预测模型"),
    ("market", "市场空间与行业趋势", ("market size", "industry outlook", "tam", "市场规模", "行业趋势"), "中", "权威行业报告或政府统计数据"),
    ("competition", "竞争格局", ("competition", "competitor", "market share", "竞争", "市场份额"), "高", "竞品清单、市场份额及客户访谈"),
    ("team", "核心团队与治理", ("management", "director", "founder", "governance", "管理层", "创始人", "公司治理"), "高", "管理团队履历、组织架构和董事会材料"),
    ("legal", "法律合规与知识产权", ("litigation", "regulation", "patent", "compliance", "诉讼", "合规", "专利"), "高", "法律尽调报告、诉讼清单和知识产权清单"),
    ("customers", "客户与商业验证", ("customer", "contract", "retention", "客户", "合同", "留存"), "高", "客户明细、核心合同和访谈纪要"),
    ("valuation", "估值与交易条款", ("valuation", "enterprise value", "term sheet", "估值", "交易条款"), "高", "最新估值基准、可比公司数据和交易文件"),
)

TRUSTED_DOMAINS = (
    "sec.gov", "worldbank.org", "imf.org", "oecd.org", "who.int", "fda.gov", "europa.eu",
    "gov.cn", "stats.gov.cn", "samr.gov.cn", "cninfo.com.cn", "sse.com.cn", "szse.cn", "hkexnews.hk",
    "energy.gov", "nrel.gov", "iea.org", "irena.org",
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
