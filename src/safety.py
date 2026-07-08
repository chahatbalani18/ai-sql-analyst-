from __future__ import annotations
import sqlglot
from sqlglot import exp

# Expression types that write or mutate data/schema. If any node of these
# types appears anywhere in the parsed tree, the query is rejected.
WRITE_EXPRESSIONS = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter,
    exp.Create, exp.TruncateTable, exp.Command,
)

DEFAULT_LIMIT = 50


class UnsafeSQLError(ValueError):
    """Raised when generated SQL fails read-only safety validation."""
    pass


def ensure_safe_select(sql: str, dialect: str = "sqlite", enforce_limit: bool = True) -> str:
    if not sql or not sql.strip():
        raise UnsafeSQLError("Empty SQL generated.")

    cleaned = sql.strip().rstrip(';').strip()

    # Parse into a list of statements. More than one = stacked-query attempt.
    try:
        statements = sqlglot.parse(cleaned, read=dialect)
    except Exception as e:
        raise UnsafeSQLError(f"Could not parse SQL: {e}")

    statements = [s for s in statements if s is not None]
    if len(statements) == 0:
        raise UnsafeSQLError("No statement found.")
    if len(statements) > 1:
        raise UnsafeSQLError("Multiple statements are not allowed.")

    tree = statements[0]

    # Top-level must be a SELECT (or a WITH/CTE that wraps a SELECT).
    root = tree
    if isinstance(root, exp.With):
        root = root.this
    if not isinstance(root, (exp.Select, exp.Union)):
        raise UnsafeSQLError(f"Only SELECT statements are allowed, got {type(tree).__name__}.")

    # Walk the ENTIRE tree; reject if any write/DDL node exists anywhere
    # (covers writes hidden inside CTEs or subqueries).
    for node in tree.walk():
        if isinstance(node, WRITE_EXPRESSIONS):
            raise UnsafeSQLError(f"Forbidden operation detected: {type(node).__name__}.")

    # Enforce a row limit if none present (prevents runaway result sets).
    if enforce_limit and not tree.find(exp.Limit):
        tree = tree.limit(DEFAULT_LIMIT)

    return tree.sql(dialect=dialect)