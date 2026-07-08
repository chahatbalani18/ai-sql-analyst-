# AI SQL Analyst

A natural-language interface to a relational database. Ask a question in plain English; the system generates SQL, validates it is safe to run, executes it against the database, and returns the results with an explanation.

The interesting part of this project is not the SQL generation — a modern LLM does that in one call. The interesting part is everything that makes an LLM's SQL **safe and reliable enough to run against a live database**: an AST-based safety layer and a category-tagged evaluation harness that measures correctness and catches regressions.

---

## Why this project

An LLM that writes SQL is easy to demo and hard to trust. The moment you let a generated query execute against a real database, you inherit real risks:

- The model can generate destructive SQL (`DELETE`, `DROP`, `UPDATE`).
- It can generate valid-but-wrong SQL (wrong join, misread filter, hallucinated column).
- It can be manipulated into stacked statements (`SELECT ...; DROP TABLE ...`).

Handling those failure modes — not the happy path — is the actual engineering. This project is built around two components that address them directly: a **safety validator** and an **evaluation harness**.

---

## Architecture

```
User question (English)
        │
        ▼
  Schema introspection ──► builds table/column/FK context for the prompt
        │
        ▼
  LLM SQL generation ────► single SELECT, schema-constrained
        │
        ▼
  Safety validation ─────► AST parse: single read-only SELECT, no writes anywhere
        │
        ▼
  Execution ─────────────► runs against the database (read-only)
        │
        ▼
  Results + explanation ─► table, auto-chart, natural-language summary
```

**Frontend:** Streamlit app with conversation memory (follow-up questions reuse prior context), auto-charting, result explanation, and follow-up suggestions.

**Backend modules** (`src/`):
- `schema.py` — introspects the database and builds a schema summary (tables, columns, foreign keys) that grounds the model so it can only reference real columns.
- `llm_sql.py` / `llm_followup.py` — SQL generation and follow-up rewriting.
- `safety.py` — AST-based read-only validation (see below).
- `db.py` — query execution.
- `explain.py` / `suggestions.py` — result explanation and follow-up generation.

---

## Safety layer (design decision)

The safety validator was deliberately built **twice**, and the change is worth explaining.

**First approach — keyword blocking.** Scan the SQL string for forbidden words (`delete`, `drop`, `update`, ...). This is the obvious approach and it is wrong in both directions:

- **Over-blocks:** a legitimate query like `SELECT deleted_at FROM Customer` is rejected because it contains the substring "delete."
- **Under-blocks:** keyword filters are bypassable, and a stacked query like `SELECT * FROM t; DROP TABLE t` can slip through depending on how the check is written.

**Second approach — AST validation** (`src/safety.py`). Parse the SQL into a syntax tree with `sqlglot` and inspect its structure:

1. Parse into statements — more than one statement means a stacked-query attempt; reject.
2. The top-level node must be a `SELECT` (or a CTE resolving to one).
3. Walk the **entire** tree and reject if any write/DDL node (`Insert`, `Update`, `Delete`, `Drop`, `Alter`, `Create`, ...) appears anywhere — including hidden inside a CTE or subquery.
4. Inject a `LIMIT` if none is present, to prevent runaway result sets.

This is both safer and more precise: it stops the stacked-query and hidden-write attacks that keyword filtering misses, and it stops falsely rejecting innocent queries whose column names happen to contain a keyword.

The adversarial test suite (`tests/test_safety.py`) encodes both directions — innocent queries that must be allowed, and dangerous queries that must be blocked — and all cases pass.

---

## Evaluation harness

The harness (`tests/evaluate.py`) is what lets the project make a **measurable claim** about correctness rather than a demo-based one.

**Dataset** (`tests/questions.json`) — a blended set of cases, each tagged with a category and difficulty:

- **Structural** (easy → hard): tests whether the model constructs correct SQL as query shape escalates — from single-table counts to nested subqueries comparing against a global average.
- **Ambiguity:** questions whose English is under-specified ("best-selling tracks," "most valuable customers"). Tests whether the model makes a *reasonable interpretation*, which is the failure mode that actually breaks in real deployments.
- **Adversarial:** requests that should not produce a runnable query at all ("delete all customers from Canada," "show me the passwords" against a schema with no password column). Tests the guardrails.

**Scoring by result-set equivalence.** Two different SQL strings can be equally correct — different `ORDER BY`, different aliases, different-but-equivalent joins. The harness therefore compares the **data returned**, not the SQL text: it runs the reference query and the candidate query, and compares their result sets order-insensitively. This credits the model for a correct answer even when its SQL differs from the reference.

**Adversarial scoring.** For adversarial cases, a "pass" means the candidate was correctly refused or blocked by the safety layer. A query that *executes* is a failure — the guardrail let something through.

**Decoupled design.** The harness evaluates a `candidate_sql` function. Swapping the model under test is a one-function change — the reference-vs-reference baseline validates the machinery (scores 100% by construction), and pointing `candidate_sql` at the live model measures real accuracy with the same code.

---

## Results

<!-- PLACEHOLDER: fill in after running the harness against the live model. -->

Baseline (reference-vs-reference, machinery check): **12/12** — confirms the scoring, comparison, and adversarial logic are correct.

Live model results (to be added):

| Category    | Score | Notes |
|-------------|-------|-------|
| Structural  | _/6   | |
| Ambiguity   | _/3   | |
| Adversarial | _/3   | |
| **Overall** | _/12  | |

_Failure analysis and the improvement iteration will be documented here once live evals are run._

---

## Running it

### Prerequisites
- Python 3.12+
- An OpenAI API key (for live generation and evaluation)

### Setup

```bash
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

Add a `.env` file with your key:

```
OPENAI_API_KEY=your-key-here
```

### Run the app

```bash
streamlit run app/streamlit_app.py
```

### Run the safety tests

```bash
python tests/test_safety.py
```

### Run the evaluation harness

```bash
python tests/evaluate.py
```

To evaluate the live model, point `candidate_sql` in `tests/evaluate.py` at `generate_sql` (see the comment in that function).

---

## What I would do next

- **Confidence signaling:** have the agent flag when a question is ambiguous rather than silently picking an interpretation.
- **Expanded eval set:** more cases per category, and multiple acceptable references for ambiguous questions.
- **Query cost guards:** static analysis to reject queries likely to be prohibitively expensive on large tables.
- **Schema-scoped access:** per-user table/column allowlists for multi-tenant use.

---

*A portfolio project exploring what it takes to deploy an LLM-to-SQL agent safely and measurably. Built against the Chinook sample database.*
