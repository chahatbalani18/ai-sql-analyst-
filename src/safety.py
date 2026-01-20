import re

FORBIDDEN = [
    "insert", "update", "delete", "drop", "alter", "create", "pragma", "attach", "detach", "truncate"
]

def ensure_safe_select(sql: str) -> str:
    if not sql or not sql.strip():
        raise ValueError("Empty SQL generated.")

    cleaned = sql.strip().rstrip(";").strip()

    # must start with SELECT
    if not re.match(r"(?is)^\s*select\b", cleaned):
        raise ValueError("Only SELECT statements are allowed.")

    lowered = cleaned.lower()
    for kw in FORBIDDEN:
        if re.search(rf"(?is)\b{re.escape(kw)}\b", lowered):
            raise ValueError(f"Forbidden keyword detected: {kw}")

    # enforce LIMIT 50 if missing
    if not re.search(r"(?is)\blimit\s+\d+\b", cleaned):
        cleaned = cleaned + " LIMIT 50"

    return cleaned
