# src/llm_sql.py
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_RULES = """You are an expert data analyst writing SQLite SQL.

Rules:
- Output ONLY a single SQLite SELECT statement (no markdown, no backticks, no explanation).
- Use only tables and columns that exist in the provided schema.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or PRAGMA.
- Prefer explicit JOINs with ON clauses.
- All selected output columns must have UNIQUE names (unique aliases). Never repeat an alias.
- Always include LIMIT 50 unless the user asks for a different limit.
- If the question is ambiguous, make the most reasonable assumption and write the query.
"""

def generate_sql(question: str, schema_context: str, model: str = "gpt-4o-mini") -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY not found. Put it in your .env file.")

    prompt = f"""{SYSTEM_RULES}

SCHEMA:
{schema_context}

QUESTION:
{question}

SQL:
"""

    resp = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=350,
    )

    sql = (resp.output_text or "").strip()
    sql = sql.strip().rstrip(";").strip()
    return sql


if __name__ == "__main__":
    # Run this as: python src\\llm_sql.py
    from schema import build_schema_summary

    schema_text = build_schema_summary()
    q = "Top 10 customers by total spending"
    print("QUESTION:", q)
    print("\nGENERATED SQL:\n", generate_sql(q, schema_text))
