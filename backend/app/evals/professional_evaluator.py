import re
from dataclasses import asdict, dataclass


@dataclass
class EvaluationResult:
    case_id: str
    stage: str
    score: int
    passed: bool
    critical_issues: list[str]
    quality_issues: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class ProfessionalInvestmentEvaluator:
    """Score investment opinions against evidence-control and stage-specific decision standards."""

    PASS_SCORE = 80
    COMMON_MARKERS = {
        "disclosed facts": ("公司披露事实", "company-disclosed facts"),
        "analyst inference": ("分析师推断", "analyst inference"),
        "verification action": ("核验动作", "verification action"),
        "decision gate": ("投委门槛", "ic gate", "决策门槛"),
        "cannot assess": ("无法判断", "cannot assess", "无法评估"),
    }
    STAGE_MARKERS = {
        "pre_investment": ("投前结论", "pre-investment conclusion", "尽调"),
        "in_progress": ("投中执行", "during-investment execution", "交割条件"),
        "post_investment": ("投后监控", "post-investment monitoring", "风险升级"),
    }
    PROHIBITED = (
        "保证收益", "必然上涨", "稳赚", "无风险", "立即买入", "强烈买入",
        "guaranteed return", "risk-free", "must buy", "strong buy",
    )

    @classmethod
    def evaluate(cls, case_id: str, stage: str, answer: str, evidence: str) -> EvaluationResult:
        lowered = answer.lower()
        evidence_lower = evidence.lower()
        critical: list[str] = []
        issues: list[str] = []
        score = 100

        stage_markers = cls.STAGE_MARKERS.get(stage, ())
        if not any(marker in lowered for marker in stage_markers):
            issues.append(f"missing stage-specific section: {stage}")
            score -= 15
        for label, markers in cls.COMMON_MARKERS.items():
            if not any(marker in lowered for marker in markers):
                issues.append(f"missing professional control: {label}")
                score -= 8

        evidence_ids = set(re.findall(r"\[([A-Z]+\d+)\]", evidence, flags=re.IGNORECASE))
        answer_ids = set(re.findall(r"\[([A-Z]+\d+)\]", answer, flags=re.IGNORECASE))
        if not answer_ids:
            critical.append("no evidence citation")
            score -= 25
        unknown_ids = {item.upper() for item in answer_ids} - {item.upper() for item in evidence_ids}
        if unknown_ids:
            critical.append(f"unknown evidence citations: {sorted(unknown_ids)}")
            score -= 30

        normalized_evidence = re.sub(r"[,%$￥\s]", "", evidence_lower)
        unsupported_numbers: list[str] = []
        for token in re.findall(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?%?", answer):
            normalized = re.sub(r"[,%$￥\s]", "", token.lower())
            if len(normalized.rstrip("%")) <= 1 or normalized in normalized_evidence:
                continue
            unsupported_numbers.append(token)
        if unsupported_numbers:
            critical.append(f"unsupported numeric claims: {sorted(set(unsupported_numbers))}")
            score -= 30

        prohibited = [phrase for phrase in cls.PROHIBITED if phrase in lowered]
        if prohibited:
            critical.append(f"unconditional investment language: {prohibited}")
            score -= 35

        if not any(marker in lowered for marker in ("条件", "conditional", "取决于", "subject to")):
            issues.append("conclusion is not explicitly conditional")
            score -= 8
        if stage == "in_progress" and not any(marker in lowered for marker in ("交割", "closing", "前置条件")):
            issues.append("during-investment opinion lacks closing controls")
            score -= 10
        if stage == "post_investment" and not any(marker in lowered for marker in ("kpi", "阈值", "预警", "风险事件")):
            issues.append("post-investment opinion lacks KPI or alert controls")
            score -= 10

        score = max(0, score)
        return EvaluationResult(
            case_id=case_id,
            stage=stage,
            score=score,
            passed=score >= cls.PASS_SCORE and not critical,
            critical_issues=critical,
            quality_issues=issues,
        )
