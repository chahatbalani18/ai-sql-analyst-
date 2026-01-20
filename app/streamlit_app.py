# app/streamlit_app.py
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# --- Make project root importable so "src.*" works ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.db import run_query  # noqa: E402
from src.schema import build_schema_summary  # noqa: E402
from src.llm_sql import generate_sql  # noqa: E402
from src.llm_followup import rewrite_sql_followup  # noqa: E402
from src.safety import ensure_safe_select  # noqa: E402
from src.explain import explain_results  # noqa: E402
from src.memory import ConversationState  # noqa: E402
from src.suggestions import suggest_followups  # noqa: E402


st.set_page_config(page_title="AI SQL Analyst", layout="wide")
st.title("AI SQL Analyst (Chinook DB)")
st.caption("Ask questions in English → AI generates SQL → results from your database")


@st.cache_data(show_spinner=False)
def get_schema_text() -> str:
    return build_schema_summary()


def _dedup_names(names):
    """Return unique column names: a, a -> a, a_2"""
    seen = {}
    out = []
    for n in names:
        n = str(n).strip()
        if n not in seen:
            seen[n] = 1
            out.append(n)
        else:
            seen[n] += 1
            out.append(f"{n}_{seen[n]}")
    return out


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns + dedupe names."""
    df = df.copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["__".join(map(str, tup)).strip() for tup in df.columns]
    df.columns = _dedup_names(df.columns.tolist())
    return df


def try_chart(df: pd.DataFrame) -> None:
    """Auto chart: date+numeric line, else text+numeric bar, else manual pick."""
    try:
        if df is None or df.empty or df.shape[1] < 2 or df.shape[0] < 2:
            st.info("Not enough data to chart.")
            return

        df = normalize_df(df)

        col_info = []
        for i in range(df.shape[1]):
            s = df.iloc[:, i]
            is_num = pd.api.types.is_numeric_dtype(s)
            is_text_like = (s.dtype == "object") or pd.api.types.is_string_dtype(s)

            # Better date detection to avoid 1970 chart issue
            s_as_str = s.astype(str)
            looks_like_date = s_as_str.str.contains(r"[-/:]", regex=True).mean() >= 0.6

            parsed = pd.to_datetime(s, errors="coerce")
            parsed_ratio = parsed.notna().sum() / max(1, len(df))

            if parsed.notna().any():
                min_year = int(parsed.dropna().dt.year.min())
                max_year = int(parsed.dropna().dt.year.max())
                year_ok = (min_year >= 1990) and (max_year <= 2035)
            else:
                year_ok = False

            date_like = (parsed_ratio >= 0.6) and (looks_like_date or year_ok)

            col_info.append(
                {"idx": i, "name": df.columns[i], "is_num": is_num, "is_text": is_text_like, "is_date": date_like}
            )

        numeric = [c for c in col_info if c["is_num"]]
        text_like = [c for c in col_info if c["is_text"] and not c["is_num"]]
        date_like_cols = [c for c in col_info if c["is_date"]]

        # date + numeric => line
        if date_like_cols and numeric:
            x_idx = date_like_cols[0]["idx"]
            y_idx = numeric[0]["idx"]
            x = pd.to_datetime(df.iloc[:, x_idx], errors="coerce")
            y = df.iloc[:, y_idx]
            chart_df = pd.DataFrame({"x": x, "y": y}).dropna().sort_values("x")
            st.line_chart(chart_df.set_index("x")["y"])
            return

        # text + numeric => bar
        if text_like and numeric:
            x_idx = text_like[0]["idx"]
            y_idx = numeric[0]["idx"]
            chart_df = df.iloc[:, [x_idx, y_idx]].copy()
            chart_df.columns = ["x", "y"]
            chart_df = chart_df.dropna()
            chart_df = chart_df.groupby("x", as_index=False)["y"].sum()
            chart_df = chart_df.sort_values("y", ascending=False).head(20)
            st.bar_chart(chart_df.set_index("x")["y"])
            return

        # fallback manual
        st.info("Auto-chart couldn’t confidently choose axes. Pick X and Y below.")
        cols = list(df.columns)
        x_col = st.selectbox("X axis", cols, index=0)

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            st.info("No numeric columns available to chart.")
            return
        y_col = st.selectbox("Y axis (numeric)", numeric_cols, index=0)

        chart_type = st.radio("Chart type", ["Bar", "Line"], horizontal=True)
        if chart_type == "Line":
            x = pd.to_datetime(df[x_col], errors="coerce")
            chart_df = pd.DataFrame({"x": x, "y": df[y_col]}).dropna().sort_values("x")
            st.line_chart(chart_df.set_index("x")["y"])
        else:
            chart_df = df[[x_col, y_col]].dropna().copy()
            chart_df.columns = ["x", "y"]
            chart_df = chart_df.groupby("x", as_index=False)["y"].sum()
            chart_df = chart_df.sort_values("y", ascending=False).head(20)
            st.bar_chart(chart_df.set_index("x")["y"])

    except Exception as e:
        st.warning(f"Could not auto-chart this result: {e}")


schema_text = get_schema_text()
with st.expander("Show database schema context"):
    st.text(schema_text)

# --- Conversation memory init ---
if "conv" not in st.session_state:
    st.session_state.conv = ConversationState().to_dict()
conv = ConversationState.from_dict(st.session_state.conv)

# --- Persist last outputs so reruns never crash ---
st.session_state.setdefault("last_df", None)
st.session_state.setdefault("last_safe_sql", "")
st.session_state.setdefault("last_display_question", "")
st.session_state.setdefault("last_question_seen", "")

# --- Widget state init ---
st.session_state.setdefault("mode", "New question")
st.session_state.setdefault("question_input", "Top 10 customers by total spending")
st.session_state.setdefault("auto_run", False)

# --- PENDING values (this fixes your Streamlit session_state mutation error) ---
st.session_state.setdefault("pending_question", None)
st.session_state.setdefault("pending_mode", None)

# ✅ Apply pending values BEFORE widgets are created (CRITICAL)
if st.session_state.get("pending_mode") is not None:
    st.session_state["mode"] = st.session_state.pop("pending_mode")

if st.session_state.get("pending_question") is not None:
    st.session_state["question_input"] = st.session_state.pop("pending_question")

# ---------------- UI ----------------
st.markdown("### Ask")

mode = st.radio(
    "Mode",
    ["New question", "Follow-up (use last query context)"],
    horizontal=True,
    key="mode",
)

st.text_input(
    "Your question / follow-up instruction",
    key="question_input",
)

question = st.session_state["question_input"]

# Optional: show a clear hint if question changed but not run yet
if st.session_state.get("last_question_seen", "") != question:
    st.session_state["last_question_seen"] = question
    st.caption("Tip: Click Run (or click a suggestion) to execute this question.")

debug = st.checkbox("Debug mode (show stored memory + columns)", value=False)
if debug:
    st.caption(f"Memory last_question: {conv.last_question!r}")
    st.caption(f"Memory has last_safe_sql: {bool(conv.last_safe_sql)}")
    st.caption(f"Current mode: {st.session_state['mode']}")
    st.caption(f"Current question_input: {st.session_state['question_input']!r}")

run_clicked = st.button("Run")
auto_run = st.session_state.pop("auto_run", False)

# ---------------- Run logic ----------------
if run_clicked or auto_run:
    if st.session_state["mode"] == "Follow-up (use last query context)":
        if not conv.last_safe_sql:
            st.error("No previous query found. Run a New question first.")
            st.stop()

        with st.spinner("Updating previous SQL based on your follow-up..."):
            sql = rewrite_sql_followup(
                schema_context=schema_text,
                previous_question=conv.last_question,
                previous_sql=conv.last_safe_sql,
                followup_instruction=question,
            )
        display_question = f"Follow-up: {question}"
        question_to_store = conv.last_question  # keep base question
    else:
        with st.spinner("Generating SQL with OpenAI..."):
            sql = generate_sql(question, schema_text)
        display_question = question
        question_to_store = question

    st.subheader("Generated SQL")
    st.code(sql, language="sql")

    # Friendly clarification for "sales" in Chinook
    if "sales" in question.lower() or "revenue" in question.lower():
        st.info("Note: In this dataset, 'sales/revenue' is interpreted as SUM(Invoice.Total).")

    # Safety validation
    try:
        safe_sql = ensure_safe_select(sql)
    except Exception as e:
        st.error(f"SQL failed safety checks: {e}")
        st.stop()

    # Execute
    with st.spinner("Running query on database..."):
        try:
            df = run_query(safe_sql)
        except Exception as e:
            st.error(f"Database error: {e}")
            st.stop()

    df = normalize_df(df)

    # Save memory only after success
    conv.last_question = question_to_store
    conv.last_sql = sql
    conv.last_safe_sql = safe_sql
    conv.last_result_columns = list(df.columns)
    st.session_state.conv = conv.to_dict()

    # Persist outputs for reruns
    st.session_state["last_df"] = df
    st.session_state["last_safe_sql"] = safe_sql
    st.session_state["last_display_question"] = display_question

    if debug:
        st.caption(f"Columns: {list(df.columns)}")

    st.subheader("Results")
    st.dataframe(df, use_container_width=True)

    st.subheader("Quick Chart")
    try_chart(df)

# ---- Persisted sections (safe on rerun) ----
last_df = st.session_state.get("last_df")
last_safe_sql = st.session_state.get("last_safe_sql", "")
last_display_question = st.session_state.get("last_display_question", "")

if isinstance(last_df, pd.DataFrame) and not last_df.empty:
    st.subheader("Follow-up Suggestions")
    with st.spinner("Generating follow-up ideas..."):
        try:
            suggestions = suggest_followups(last_display_question, last_safe_sql, last_df)
            if suggestions:
                for i, s in enumerate(suggestions):
                    if st.button(s, key=f"sugg_{i}"):
                        # ✅ DO NOT set question_input directly here (widget already exists)
                        # ✅ Set pending values and rerun (safe)
                        st.session_state["pending_question"] = s
                        st.session_state["pending_mode"] = "Follow-up (use last query context)"
                        st.session_state["auto_run"] = True
                        st.rerun()
            else:
                st.info("No suggestions generated this time.")
        except Exception as e:
            st.warning(f"Could not generate suggestions: {e}")

    st.subheader("AI Explanation")
    with st.spinner("Writing explanation..."):
        try:
            explanation = explain_results(last_display_question, last_safe_sql, last_df)
            st.write(explanation)
        except Exception as e:
            st.warning(f"Could not generate explanation: {e}")

    st.download_button(
        "Download results as CSV",
        last_df.to_csv(index=False).encode("utf-8"),
        file_name="query_results.csv",
        mime="text/csv",
    )
else:
    st.info("Run a query to see follow-up suggestions, explanation, and download.")
