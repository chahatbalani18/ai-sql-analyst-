from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.db import run_query
from src.safety import ensure_safe_select, UnsafeSQLError

DATASET = Path(__file__).resolve().parent / "questions.json"


def load_cases():
    data = json.loads(DATASET.read_text(encoding="utf-8-sig"))
    return data["cases"]


def result_signature(df):
    # Order-insensitive comparison of a result set: sort rows by their
    # stringified values so two equivalent queries with different ORDER BY
    # still compare equal. Column names are ignored (aliases vary).
    rows = [tuple(str(v) for v in row) for row in df.itertuples(index=False, name=None)]
    return sorted(rows)


def candidate_sql(question: str, reference_sql: str | None) -> str | None:
    # SWAP POINT: today the candidate IS the reference (machinery check).
    # On a machine with an API key, replace the line below with:
    #   from src.llm_sql import generate_sql
    #   from src.schema import build_schema_summary
    #   return generate_sql(question, build_schema_summary())
    return reference_sql


def evaluate():
    cases = load_cases()
    by_category = {}
    failures = []

    for c in cases:
        cat = c["category"]
        by_category.setdefault(cat, {"passed": 0, "total": 0})
        by_category[cat]["total"] += 1

        is_adversarial = cat == "adversarial"
        cand = candidate_sql(c["question"], c["reference_sql"])

        if is_adversarial:
            # Pass = candidate is safely refused or blocked.
            if cand is None:
                by_category[cat]["passed"] += 1
                continue
            try:
                safe = ensure_safe_select(cand)
                run_query(safe)
                # It ran -> the guardrail failed to stop a dangerous request.
                failures.append((c["id"], "adversarial query executed instead of being blocked"))
            except (UnsafeSQLError, Exception):
                by_category[cat]["passed"] += 1
            continue

        # Structural / ambiguity: compare result sets.
        try:
            ref_safe = ensure_safe_select(c["reference_sql"])
            ref_sig = result_signature(run_query(ref_safe))

            cand_safe = ensure_safe_select(cand)
            cand_sig = result_signature(run_query(cand_safe))

            if ref_sig == cand_sig:
                by_category[cat]["passed"] += 1
            else:
                failures.append((c["id"], "result set did not match reference"))
        except Exception as e:
            failures.append((c["id"], f"error: {e}"))

    # Report
    print("=" * 48)
    print("EVAL RESULTS")
    print("=" * 48)
    total_p = total_t = 0
    for cat, s in by_category.items():
        total_p += s["passed"]
        total_t += s["total"]
        print(f"  {cat:12s} {s['passed']}/{s['total']}")
    print("-" * 48)
    print(f"  {'OVERALL':12s} {total_p}/{total_t}  ({100*total_p/total_t:.0f}%)")

    if failures:
        print("\nFailures:")
        for cid, reason in failures:
            print(f"  [{cid}] {reason}")
    print()


if __name__ == "__main__":
    evaluate()