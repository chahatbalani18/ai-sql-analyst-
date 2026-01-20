from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def explain_results(question: str, sql: str, df: pd.DataFrame, model: str = "gpt-4o-mini") -> str:
    # Keep token usage low: send only first 20 rows
    preview = df.head(20).to_csv(index=False)

    prompt = f"""
You are a senior data analyst. Explain query results to a business user.

User question:
{question}

SQL executed:
{sql}

Result preview (CSV, first rows):
{preview}

Write:
1) A 2-4 sentence summary of what the results show
2) One key insight
3) One caveat (if any, e.g. limited rows, time range not specified)
Keep it concise.
"""

    resp = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=250,
    )
    return (resp.output_text or "").strip()
