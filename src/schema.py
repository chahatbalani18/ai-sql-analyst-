from pathlib import Path
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "chinook.sqlite"


def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}")


def get_tables(conn):
    rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")).fetchall()
    return [r[0] for r in rows]


def get_columns(conn, table: str):
    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
    rows = conn.execute(text(f"PRAGMA table_info('{table}');")).fetchall()
    cols = []
    for cid, name, col_type, notnull, dflt, pk in rows:
        cols.append(
            {
                "name": name,
                "type": col_type,
                "notnull": bool(notnull),
                "pk": bool(pk),
            }
        )
    return cols


def get_foreign_keys(conn, table: str):
    # PRAGMA foreign_key_list returns: id, seq, table, from, to, on_update, on_delete, match
    rows = conn.execute(text(f"PRAGMA foreign_key_list('{table}');")).fetchall()
    fks = []
    for _id, _seq, ref_table, from_col, to_col, on_update, on_delete, _match in rows:
        fks.append(
            {
                "from_col": from_col,
                "ref_table": ref_table,
                "ref_col": to_col,
                "on_delete": on_delete,
                "on_update": on_update,
            }
        )
    return fks


def build_schema_summary() -> str:
    engine = get_engine()
    lines = []
    with engine.connect() as conn:
        tables = get_tables(conn)

        for t in tables:
            cols = get_columns(conn, t)
            fks = get_foreign_keys(conn, t)

            col_parts = []
            for c in cols:
                tag = []
                if c["pk"]:
                    tag.append("PK")
                # SQLite stores type loosely; still useful
                col_parts.append(f"{c['name']} ({c['type']}{', ' + ','.join(tag) if tag else ''})")

            lines.append(f"Table: {t}")
            lines.append("  Columns: " + ", ".join(col_parts))

            if fks:
                fk_parts = [f"{fk['from_col']} -> {fk['ref_table']}.{fk['ref_col']}" for fk in fks]
                lines.append("  Foreign Keys: " + ", ".join(fk_parts))
            lines.append("")  # blank line

    return "\n".join(lines).strip()


if __name__ == "__main__":
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    summary = build_schema_summary()
    print(summary)
