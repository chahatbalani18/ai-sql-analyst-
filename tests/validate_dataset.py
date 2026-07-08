import json, sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from src.db import run_query
from src.safety import ensure_safe_select, UnsafeSQLError

cases = json.loads(Path("tests/questions.json").read_text(encoding="utf-8-sig"))["cases"]
print(f"Loaded {len(cases)} cases.\n")

ok = 0
for c in cases:
    ref = c["reference_sql"]
    if ref is None:
        print(f"[skip] {c['id']}: adversarial (no reference SQL)")
        ok += 1
        continue
    try:
        safe = ensure_safe_select(ref)
        df = run_query(safe)
        print(f"[ok]   {c['id']}: {len(df)} rows")
        ok += 1
    except Exception as e:
        print(f"[FAIL] {c['id']}: {e}")

print(f"\n{ok}/{len(cases)} reference queries valid.")