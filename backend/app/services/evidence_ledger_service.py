from __future__ import annotations

import re
from collections import Counter

from app.schemas.chat import Citation, EvidenceClaim


CATEGORY_TERMS = {
    "financial": ("revenue", "sales", "income", "margin", "cash flow", "balance sheet", "debt", "收入", "利润", "现金流"),
    "business": ("business", "product", "segment", "service", "strategy", "dealer", "store", "业务", "产品", "战略"),
    "competition": ("competition", "competitor", "market share", "competitive", "竞争", "市场份额"),
    "customers": ("customer", "client", "retention", "contract", "member", "客户", "合同", "会员"),
    "governance": ("management", "director", "board", "governance", "executive", "管理层", "董事", "治理"),
    "legal": ("regulation", "regulatory", "litigation", "legal", "compliance", "patent", "监管", "诉讼", "合规"),
    "risk": ("risk", "uncertainty", "exposure", "cybersecurity", "风险", "不确定性"),
    "market": ("industry", "market", "economy", "consumer spending", "financial stability", "manufacturing", "行业", "市场", "经济"),
}

BOILERPLATE_MARKERS = (
    "table of contents",
    "documents incorporated by reference",
    "annual meeting proxy statement",
    "exact name of registrant",
    "united states securities and exchange commission",
    "market for registrant's common equity",
    "quantitative and qualitative disclosures about market risk",
    "management's discussion and analysis of financial condition",
    "this publication is available free of charge",
    "cover image",
    "how to cite this",
    "publication identifier syntax",
    "does not imply recommendation or endorsement",
    "forward-looking statements",
    "the following table is a reconciliation",
    "basic principles and strategies",
    "working paper (",
)

LEADING_HEADER_MARKERS = (
    "annual report",
    "form 10-k",
    "financial stability report",
    "board of governors of the federal reserve system",
    "nist advanced manufacturing series",
    "nist ams",
    "department of commerce",
    "bureau of economic analysis1 contact",
    "corporate headquarters",
)

METRIC_PATTERNS = (
    r"Total net revenue\s+\$?[\d ,.$()%A-Za-z]+?(?=\s+Total noninterest expense)",
    r"Net income\s+\$\s*\d[\d ,]*\s+\$\s*\d[\d ,]*(?:\s+\([a-z]\))?\s+\$\s*\d[\d ,]*",
    r"Cash and cash equivalents of\s+\$[\d.,]+\s+(?:million|billion)",
    r"Total debt of\s+\$[\d.,]+\s+(?:million|billion)",
    r"Operating cash flow of\s+\$[\d.,]+\s+(?:million|billion)(?:,\s+an increase of\s+\$[\d.,]+\s+(?:million|billion))?",
    r"Free cash flow\s+\d*\s*of\s+\$[\d.,]+\s+(?:million|billion)(?:,\s+an increase of\s+\$[\d.,]+\s+(?:million|billion))?",
    r"Revenue growth of\s+[\d.]+%(?:,\s+up\s+[\d.]+%\s+in constant currency\s*\([^)]*\))?",
    r"Operating income decreased\s+[\d.]+%(?:,\s+up\s+[\d.]+%\s+adjusted\s*\([^)]*\))?",
    r"eCommerce up\s+[\d.]+%\s+globally",
    r"GAAP EPS of\s+\$[\d.]+",
    r"(?:With\s+)?20\d{2}\s+sales and revenues of\s+\$[\d.]+\s+billion",
    r"(?:Total|Consolidated|[A-Z][A-Za-z&.'-]+(?:\s+(?:[A-Z][A-Za-z&.'-]+|U\.S\.)){0,3})\s+Net sales\s+\$?\s*[\d,]+\s+\$?\s*[\d,]+\s+\$?\s*[\d,]+",
    r"(?:Total|Consolidated|[A-Z][A-Za-z&.'-]+(?:\s+(?:[A-Z][A-Za-z&.'-]+|U\.S\.)){0,3})\s+Operating income\s+\$?\s*[\d,]+\s+\$?\s*[\d,]+\s+\$?\s*[\d,]+",
    r"Net income attributable to [A-Za-z&.' ]+\s+\$?\s*[\d,]+\s+\$?\s*[\d,]+\s+\$?\s*[\d,]+",
    r"Net cash provided by operating activities\s+\$?\s*[\d,]+\s+\$?\s*[\d,]+\s+\$?\s*[\d,]+",
)


class EvidenceLedgerService:
    @classmethod
    def build(cls, citations: list[Citation], max_company_claims: int = 12, max_context_claims: int = 8) -> list[EvidenceClaim]:
        candidates: list[tuple[int, str, str, Citation, str]] = []
        seen_quotes: set[str] = set()
        for citation in citations:
            metric_claims = cls._metric_claims(citation.content)
            metric_quotes = [quote for _claim, quote in metric_claims]
            metric_norms = [cls._normalize(quote) for quote in metric_quotes]
            for claim, quote in metric_claims:
                normalized = cls._normalize(quote)
                if normalized not in seen_quotes:
                    seen_quotes.add(normalized)
                    candidates.append((30, claim, quote, citation, "financial"))
            for sentence in cls._sentences(citation.content):
                normalized = cls._normalize(sentence)
                if normalized in seen_quotes or any(metric_norm in normalized for metric_norm in metric_norms):
                    continue
                category, term_hits = cls._category(sentence)
                if term_hits == 0:
                    continue
                score = cls._quality_score(sentence, category, term_hits)
                if score < 5:
                    continue
                seen_quotes.add(normalized)
                candidates.append((score, sentence, sentence, citation, category))

        candidates.sort(key=lambda item: (-item[0], item[3].filename, item[1]))
        role_limits = {
            "company_disclosure": max_company_claims,
            "industry_context": max_context_claims,
            "uploaded_evidence": min(6, max_context_claims),
        }
        role_prefixes = {"company_disclosure": "C", "industry_context": "I", "uploaded_evidence": "U"}
        role_counts: Counter[str] = Counter()
        file_counts: Counter[str] = Counter()
        category_counts: Counter[tuple[str, str]] = Counter()
        claims: list[EvidenceClaim] = []

        # The first pass preserves coverage; the second fills capacity with the best remaining evidence.
        for require_new_category in (True, False):
            for _score, claim_text, evidence_quote, citation, category in candidates:
                role = citation.document_role
                per_file_limit = 12 if role == "company_disclosure" else 6
                if role_counts[role] >= role_limits.get(role, 0) or file_counts[citation.filename] >= per_file_limit:
                    continue
                if require_new_category and category_counts[(role, category)] >= 1:
                    continue
                if not require_new_category and any(
                    item.evidence_quote == evidence_quote and item.source_filename == citation.filename for item in claims
                ):
                    continue
                role_counts[role] += 1
                file_counts[citation.filename] += 1
                category_counts[(role, category)] += 1
                prefix = role_prefixes.get(role, "U")
                claims.append(EvidenceClaim(
                    claim_id=f"{prefix}{role_counts[role]}",
                    claim=claim_text,
                    source_filename=citation.filename,
                    document_role=role,
                    evidence_quote=evidence_quote,
                    category=category,
                ))
        return sorted(claims, key=lambda item: (item.claim_id[0], int(item.claim_id[1:])))

    @staticmethod
    def serialize(claims: list[EvidenceClaim]) -> str:
        return "\n".join(
            f"[{item.claim_id}] role={item.document_role}; category={item.category}; "
            f"source={item.source_filename}; verified_claim={item.claim}; verified_quote={item.evidence_quote}"
            for item in claims
        )

    @classmethod
    def reference_issues(cls, answer: str, claims: list[EvidenceClaim]) -> list[str]:
        valid_ids = {item.claim_id for item in claims}
        referenced = set(re.findall(r"\[([CIU]\d+)\]", answer))
        issues = [f"unknown claim reference {claim_id}" for claim_id in sorted(referenced - valid_ids)]
        company_ids = {item.claim_id for item in claims if item.document_role == "company_disclosure"}
        context_ids = {item.claim_id for item in claims if item.document_role == "industry_context"}
        if company_ids and not referenced.intersection(company_ids):
            issues.append("no verified company claim reference")
        if context_ids and not referenced.intersection(context_ids):
            issues.append("no verified industry-context claim reference")

        fact_pattern = re.compile(
            r"Company-disclosed facts[\"*\s]*[:：]\s*(.*?)(?="
            r"[\"*\s]*(?:Analyst inference|Verification action|IC gate|Cannot assess)[\"*\s]*[:：]|$)",
            re.IGNORECASE | re.DOTALL,
        )
        for value in fact_pattern.findall(answer):
            if cls._is_empty_value(value):
                continue
            if not re.search(r"\[C\d+\]", value):
                issues.append("company-disclosed fact lacks a verified C claim reference")
                break
        return issues

    @classmethod
    def anchor_references(cls, answer: str, claims: list[EvidenceClaim]) -> str:
        """Normalize model citation syntax and attach only high-confidence lexical claim matches."""
        answer = re.sub(r"[【(（]\s*([CIU]\d+)\s*[】)）]", r"[\1]", answer, flags=re.IGNORECASE)
        answer = re.sub(r"\[(?:claim\s+)?([CIU]\d+)\]", r"[\1]", answer, flags=re.IGNORECASE)
        anchored: list[str] = []
        for line in answer.splitlines():
            if re.search(r"\[[CIU]\d+\]", line):
                anchored.append(line)
                continue
            role = cls._line_evidence_role(line)
            if role is None or cls._is_empty_value(line.partition(":")[2] or line.partition("：")[2]):
                anchored.append(line)
                continue
            match = cls._best_claim_match(line, claims, role)
            anchored.append(f"{line} [{match.claim_id}]" if match else line)
        return "\n".join(anchored)

    @classmethod
    def _best_claim_match(
        cls, line: str, claims: list[EvidenceClaim], role: str
    ) -> EvidenceClaim | None:
        line_numbers = cls._number_tokens(line)
        line_words = cls._word_tokens(line)
        best: tuple[int, EvidenceClaim] | None = None
        for claim in claims:
            if claim.document_role != role:
                continue
            claim_numbers = cls._number_tokens(claim.claim)
            number_overlap = len(line_numbers.intersection(claim_numbers))
            word_overlap = len(line_words.intersection(cls._word_tokens(claim.claim)))
            filename_match = claim.source_filename.lower() in line.lower()
            score = number_overlap * 6 + min(word_overlap, 6) + (3 if filename_match else 0)
            if number_overlap == 0 and word_overlap < 4:
                continue
            if best is None or score > best[0]:
                best = (score, claim)
        return best[1] if best else None

    @staticmethod
    def _line_evidence_role(line: str) -> str | None:
        lowered = line.lower()
        if "company-disclosed facts" in lowered:
            return "company_disclosure"
        if any(marker in lowered for marker in ("industry context", "industry-context", "scenario baseline")):
            return "industry_context"
        return None

    @staticmethod
    def _number_tokens(value: str) -> set[str]:
        return {re.sub(r"[,\s]", "", token) for token in re.findall(r"\d[\d, ]*(?:\.\d+)?%?", value)}

    @staticmethod
    def _word_tokens(value: str) -> set[str]:
        stopwords = {
            "about", "after", "before", "company", "disclosed", "facts", "from", "into", "only",
            "source", "that", "their", "this", "through", "with", "以及", "公司", "披露", "事实",
        }
        return {
            word for word in re.findall(r"[a-z]{3,}|[\u4e00-\u9fff]{2,}", value.lower())
            if word not in stopwords
        }

    @classmethod
    def from_context_parts(cls, context_parts: list[str]) -> list[EvidenceClaim]:
        citations: list[Citation] = []
        for part in context_parts:
            match = re.match(r"\[([^\]]+)\]\s*(.*)", part, re.DOTALL)
            if not match:
                continue
            label, content = match.groups()
            filename, _, role = label.partition(" | role=")
            citations.append(Citation(
                file_id=filename,
                filename=filename,
                content=content,
                document_role=role or "company_disclosure",
            ))
        return cls.build(citations)

    @staticmethod
    def _sentences(content: str) -> list[str]:
        protected = content
        abbreviations = {"U.S.": "U<dot>S<dot>", "J.P.": "J<dot>P<dot>", "D.C.": "D<dot>C<dot>"}
        for abbreviation, placeholder in abbreviations.items():
            protected = protected.replace(abbreviation, placeholder)
        parts = re.split(r"(?<=[。！？.!?])\s+|\n+", protected)
        results: list[str] = []
        for part in parts:
            for abbreviation, placeholder in abbreviations.items():
                part = part.replace(placeholder, abbreviation)
            sentence = re.sub(r"\s+", " ", part).strip(" |-\t")
            sentence = re.sub(r"^\d+\s*(?=(?:The Company|Our |Walmart |We ))", "", sentence)
            if " Abstract " in sentence[:400]:
                sentence = sentence.split(" Abstract ", 1)[1].strip()
            lowered = sentence.lower()
            boilerplate = any(marker in lowered for marker in BOILERPLATE_MARKERS)
            leading_header = any(marker in lowered[:160] for marker in LEADING_HEADER_MARKERS)
            cross_reference = bool(re.search(r"ref\s*er\s+to.*pages?\s+\d", lowered))
            item_heading = bool(re.search(r"\bitem\s+\d+[a-z]?\.?\s*$", lowered))
            words = re.findall(r"[A-Za-z\u4e00-\u9fff]+|\d+(?:[.,]\d+)*%?", sentence)
            numeric_words = sum(bool(re.fullmatch(r"\d+(?:[.,]\d+)*%?", word)) for word in words)
            first_alpha = re.search(r"[A-Za-z\u4e00-\u9fff]", sentence)
            complete_sentence = bool(re.search(r"[。！？.!?][\"')\]]?$", sentence))
            extraction_noise = sentence.count("ï") >= 1 or sentence.count("�") >= 1 or ".indd" in lowered
            table_fragment = numeric_words >= 8
            if (
                35 <= len(sentence) <= 700
                and len(words) >= 7
                and not boilerplate
                and not leading_header
                and not cross_reference
                and not item_heading
                and not re.match(r"^\d", sentence)
                and first_alpha is not None
                and (not first_alpha.group().isascii() or first_alpha.group().isupper())
                and complete_sentence
                and not extraction_noise
                and not table_fragment
                and not re.fullmatch(r"[\d\s.|-]+", sentence)
            ):
                results.append(sentence)
        return results

    @classmethod
    def _category(cls, sentence: str) -> tuple[str, int]:
        lowered = sentence.lower()
        scored = [
            (category, sum(cls._term_matches(lowered, term) for term in terms))
            for category, terms in CATEGORY_TERMS.items()
        ]
        category, hits = max(scored, key=lambda item: item[1])
        return (category if hits else "general"), hits

    @staticmethod
    def _term_matches(lowered: str, term: str) -> bool:
        if re.search(r"[\u4e00-\u9fff]", term):
            return term in lowered
        return bool(re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", lowered))

    @staticmethod
    def _quality_score(sentence: str, category: str, term_hits: int) -> int:
        score = min(term_hits, 3) * 3
        has_number = bool(re.search(r"\d", sentence))
        if has_number:
            score += 2
        if 70 <= len(sentence) <= 420:
            score += 2
        if has_number and category in {"financial", "market", "customers"}:
            score += 2
        if re.search(r"\b(?:reported|generated|increased|decreased|grew|declined|was|were|is|are|has|have|serves|ranked)\b", sentence, re.I):
            score += 2
        return score

    @staticmethod
    def _metric_quotes(content: str) -> list[str]:
        return [quote for _claim, quote in EvidenceLedgerService._metric_claims(content)]

    @staticmethod
    def _metric_claims(content: str) -> list[tuple[str, str]]:
        quotes: list[tuple[str, str]] = []
        for pattern in METRIC_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                quote = match.group(0).strip(" |-")
                if 12 <= len(quote) <= 240:
                    preceding = content[max(0, match.start() - 2000):match.start()].lower()
                    has_explicit_unit = bool(re.search(r"\b(?:million|billion)\b", quote, re.IGNORECASE))
                    claim = quote
                    table_row_requires_scale = quote.count("$") >= 2
                    if table_row_requires_scale and not has_explicit_unit:
                        if "in millions" not in preceding and "amounts in millions" not in preceding:
                            continue
                        claim = f"{quote} (table unit: USD millions)"
                    quotes.append((claim, quote))
        return quotes

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())

    @staticmethod
    def _is_empty_value(value: str) -> bool:
        normalized = re.sub(r"[\s\"'*.,。；;:：-]+", "", value).lower()
        return normalized in {"", "none", "无", "暂无", "无法评估", "cannotassess"} or any(
            marker in normalized
            for marker in ("noneavailable", "notavailable", "noverifiedfact", "无可用事实", "暂无事实")
        )
