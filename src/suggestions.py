# src/suggestions.py
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SUGGEST_SYSTEM = """You are an analytics copilot.

Generate 3 to 5 useful follow-up questions a business user might ask next.
Rules:
- Output ONLY a JSON array of strings (no markdown, no extra keys).
- Suggestions must be answerable using the same database.
- Prefer actionable follow-ups: filters, breakdowns, trends, comparisons, top-N.
- Avoid duplicates and avoid overly generic suggestions.
"""

def suggest_followups(
    question: str,
    sql: str,
    df: pd.DataFrame,
    model: str = "gpt-4o-mini",
) -> list[str]:
    if not os.getenv("OPENAI_API_KEY"):
        return []

    # Keep payload small
    preview = df.head(15).to_csv(index=False)
    cols = list(df.columns)

    prompt = f"""{SUGGEST_SYSTEM}

USER QUESTION:
{question}

SQL:
{sql}

RESULT COLUMNS:
{cols}

RESULT PREVIEW (CSV, first rows):
{preview}

JSON ARRAY:
"""

    resp = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=200,
    )

    text = (resp.output_text or "").strip()

    # Robust JSON parsing
    import json
    try:
        suggestions = json.loads(text)
        if isinstance(suggestions, list):
            # Keep only strings
            suggestions = [s for s in suggestions if isinstance(s, str)]
            # Limit
            return suggestions[:5]
    except Exception:
        pass

    return []
