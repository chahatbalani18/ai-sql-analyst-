import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.safety import ensure_safe_select, UnsafeSQLError


def expect_ok(sql):
    try:
        result = ensure_safe_select(sql)
        print(f"  PASS (allowed): {sql[:60]}")
        return True
    except UnsafeSQLError as e:
        print(f"  FAIL (should have allowed): {sql[:60]} -> {e}")
        return False


def expect_blocked(sql):
    try:
        ensure_safe_select(sql)
        print(f"  FAIL (should have blocked): {sql[:60]}")
        return False
    except UnsafeSQLError:
        print(f"  PASS (blocked): {sql[:60]}")
        return True


def main():
    results = []

    print("Legitimate queries (should be ALLOWED):")
    results.append(expect_ok("SELECT * FROM Customer"))
    results.append(expect_ok("SELECT Name FROM Artist LIMIT 10"))
    results.append(expect_ok("WITH t AS (SELECT * FROM Invoice) SELECT * FROM t"))
    # 'deleted' as a column name must NOT trigger the old keyword filter
    results.append(expect_ok("SELECT deleted_at FROM Customer WHERE deleted_at IS NULL"))
    results.append(expect_ok("SELECT COUNT(*) AS updates FROM Track"))

    print("\nDangerous queries (should be BLOCKED):")
    results.append(expect_blocked("DELETE FROM Customer"))
    results.append(expect_blocked("DROP TABLE Customer"))
    results.append(expect_blocked("UPDATE Customer SET Name = 'x'"))
    results.append(expect_blocked("INSERT INTO Customer VALUES (1)"))
    # Stacked query: a SELECT followed by a destructive statement
    results.append(expect_blocked("SELECT * FROM Customer; DROP TABLE Customer"))
    results.append(expect_blocked("ALTER TABLE Customer ADD COLUMN x INT"))
    results.append(expect_blocked("CREATE TABLE evil (id INT)"))

    passed = sum(results)
    total = len(results)
    print(f"\n{passed}/{total} safety checks passed.")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()