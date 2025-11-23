"""
Quick manual test runner for the triage pipeline.
- Pass --message "free text" to run the full LLM+rules+reply flow.
- Or pass --summary-file path/to/summary.json to skip LLM and feed a JSON
  SymptomSummary instead.
"""

import argparse
import json
from pathlib import Path

from triage.models import SymptomSummary
from triage.symptom_extraction import extract_symptoms_with_llm
from triage.risk_engine import assess_risk
from triage.response_builder import build_triage_reply


def load_summary_from_file(path: Path) -> SymptomSummary:
    data = json.loads(path.read_text())
    return SymptomSummary.model_validate(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual triage tester")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--message", help="Free-text user message to extract symptoms from")
    group.add_argument("--summary-file", type=Path, help="Path to JSON SymptomSummary")

    args = parser.parse_args()

    if args.summary_file:
        summary = load_summary_from_file(args.summary_file)
    else:
        summary = extract_symptoms_with_llm(args.message)

    risk = assess_risk(summary)
    # print(risk.model_dump_json(indent=2))
    # reply = build_triage_reply(summary, risk)

    print("\n=== Symptom Summary ===")
    print(summary.model_dump_json(indent=2))
    print("\n=== Risk Assessment ===")
    print(risk.model_dump_json(indent=2))
    # print("\n=== Reply ===")
    # print(reply)


if __name__ == "__main__":
    main()
