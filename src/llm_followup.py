# src/llm_followup.py
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

FOLLOWUP_SYSTEM = """You are a SQLite SQL editor.

You will be given:
- A database schema
- The previous user question
- The previous SQL query (SQLite)
- A NEW follow-up instruction from the user

Your job:
- Return ONLY an updated single SQLite SELECT query.
- Preserve the intent of the previous query and apply the follow-up instruction.
- Keep the query valid SQLite.
- Use only tables/columns from the schema.
- Never output markdown or explanations.
- Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or PRAGMA.
- Ensure output column aliases are UNIQUE.
- Keep LIMIT 50 unless the follow-up changes it.
"""

def rewrite_sql_followup(
    schema_context: str,
    previous_question: str,
    previous_sql: str,
    followup_instruction: str,
    model: str = "gpt-4o-mini",
) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY not found in .env file")

    prompt = f"""{FOLLOWUP_SYSTEM}

SCHEMA:
{schema_context}

PREVIOUS QUESTION:
{previous_question}

PREVIOUS SQL:
{previous_sql}

FOLLOW-UP INSTRUCTION:
{followup_instruction}

UPDATED SQL:
"""

    resp = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=350,
    )

    sql = (resp.output_text or "").strip()
    return sql.strip().rstrip(";").strip()
