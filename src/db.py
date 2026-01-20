from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "chinook.sqlite"


def get_engine():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    return create_engine(f"sqlite:///{DB_PATH}")


def run_query(sql: str) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


if __name__ == "__main__":
    print("Database path:", DB_PATH)

    tables = run_query("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    print("\nTables:")
    print(tables.to_string(index=False))

    top_customers = run_query(
        """
        SELECT
            c.FirstName || ' ' || c.LastName AS CustomerName,
            ROUND(SUM(i.Total), 2) AS TotalSpent
        FROM Customer c
        JOIN Invoice i ON i.CustomerId = c.CustomerId
        GROUP BY 1
        ORDER BY TotalSpent DESC
        LIMIT 10;
        """
    )

    print("\nTop 10 customers by total spend:")
    print(top_customers.to_string(index=False))
