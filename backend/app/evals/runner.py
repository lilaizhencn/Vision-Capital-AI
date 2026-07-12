import argparse
import json
import sys
from pathlib import Path

from app.evals.professional_evaluator import ProfessionalInvestmentEvaluator


def run_suite() -> dict:
    cases_path = Path(__file__).with_name("cases.json")
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    results = []
    expectation_failures = []
    for case in cases:
        result = ProfessionalInvestmentEvaluator.evaluate(
            case_id=case["id"], stage=case["stage"], answer=case["answer"], evidence=case["evidence"]
        )
        row = result.to_dict() | {"expected_pass": case["expect_pass"]}
        results.append(row)
        if result.passed != case["expect_pass"]:
            expectation_failures.append(case["id"])
    passing_scores = [item["score"] for item in results if item["expected_pass"]]
    return {
        "suite": "institutional-investment-quality-v1",
        "case_count": len(results),
        "minimum_passing_score": min(passing_scores) if passing_scores else 0,
        "expectation_failures": expectation_failures,
        "passed": not expectation_failures,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = run_suite()
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(serialized + "\n", encoding="utf-8")
    sys.stdout.buffer.write((serialized + "\n").encode("utf-8"))
    if args.strict and not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
