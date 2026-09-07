"""Utility functions for the free-chat agent (Phase 4.1).

Phase 4.1 changes:
- Schema-aware column validation (_ALLOWED_COLUMNS)
- SQL hardening: UNION, information_schema, pg_catalog, pg_stat, COPY
- Block mid-query semicolons and SQL comments
"""

import re

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DDL, DML


# Keywords that must never appear in generated SQL
_BLOCKED_KEYWORDS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "MERGE", "EXECUTE", "EXEC", "CALL",
    "GRANT", "REVOKE", "ATTACH", "DETACH", "COPY",
})

# Patterns that must never appear in generated SQL (case-insensitive)
_BLOCKED_PATTERNS = frozenset({
    "information_schema",
    "pg_catalog",
    "pg_stat",
})

# Only these tables may appear in queries
_ALLOWED_TABLES = frozenset({"properties", "city_centers"})

# Schema-aware column validation (Phase 4.1 Step 7)
# Sourced from SQLAlchemy ORM models in app/domain/property/models.py
_ALLOWED_COLUMNS = {
    "properties": frozenset({
        "id", "title", "city", "neighbourhood", "intent", "price",
        "bedrooms", "bathrooms", "size_sqm", "property_type",
        "distance_from_city_km", "description",
    }),
    "city_centers": frozenset({
        "city", "latitude", "longitude",
    }),
}

# All valid columns across all tables (for queries without explicit table prefix)
_ALL_VALID_COLUMNS = frozenset().union(*_ALLOWED_COLUMNS.values())


def validate_sql(sql: str) -> tuple[bool, str]:
    """Validate that the SQL is safe to execute.

    Returns (is_valid, error_message). error_message is empty if valid.

    Phase 4.1 hardening:
    - Block UNION, information_schema, pg_catalog, pg_stat
    - Block mid-query semicolons and SQL comments
    - Schema-aware column validation
    """
    if not sql or not sql.strip():
        return False, "Empty SQL."

    # Strip trailing semicolons, normalise whitespace
    sql_clean = sql.strip().rstrip(";")

    # --- Phase 4.1: Block mid-query semicolons (multiple statements) ---
    if ";" in sql_clean:
        return False, "Multiple statements detected. Only single SELECT statements are allowed."

    # --- Phase 4.1: Block SQL comments ---
    if "--" in sql_clean or "/*" in sql_clean:
        return False, "SQL comments are not allowed."

    parsed = sqlparse.parse(sql_clean)
    if not parsed:
        return False, "Could not parse SQL."

    stmt: Statement = parsed[0]

    # Must be a SELECT statement
    stmt_type = stmt.get_type()
    if stmt_type != "SELECT":
        return False, f"Only SELECT statements are allowed. Got: {stmt_type or 'unknown'}."

    # Flat token scan for blocked keywords
    upper_tokens = {t.normalized.upper() for t in stmt.flatten()}
    blocked_found = _BLOCKED_KEYWORDS & upper_tokens
    if blocked_found:
        return False, f"Blocked keyword(s) detected: {', '.join(sorted(blocked_found))}."

    # --- Phase 4.1: Block UNION ---
    if "UNION" in upper_tokens or "union" in sql_clean.lower():
        return False, "UNION queries are not allowed."

    # --- Phase 4.1: Block system catalog access ---
    text_lower = sql_clean.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern in text_lower:
            return False, f"Access to '{pattern}' is not allowed."

    # Check only allowed tables are referenced (simple heuristic)
    # Extract table-like identifiers after FROM / JOIN
    table_refs = re.findall(r"(?:from|join)\s+([a-z_][a-z0-9_]*)", text_lower)
    bad_tables = [t for t in table_refs if t not in _ALLOWED_TABLES]
    if bad_tables:
        return False, f"Query references disallowed table(s): {bad_tables}."

    # --- Phase 4.1: Schema-aware column validation ---
    col_error = _validate_columns(sql_clean)
    if col_error:
        return False, col_error

    return True, ""


def _validate_columns(sql: str) -> str | None:
    """Check that all column references exist in the allowed schema.

    Returns an error message string if invalid, or None if valid.
    """
    text_lower = sql.lower()

    # Extract column identifiers from SELECT clause and WHERE clause
    # Strategy: find identifiers that look like column references
    # Match table.column patterns
    qualified_cols = re.findall(r"([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)", text_lower)
    for table_alias_or_name, col in qualified_cols:
        # Resolve table alias to actual table name
        actual_table = _resolve_table(table_alias_or_name, text_lower)
        if actual_table and actual_table in _ALLOWED_COLUMNS:
            if col not in _ALLOWED_COLUMNS[actual_table]:
                valid = ", ".join(sorted(_ALLOWED_COLUMNS[actual_table]))
                return (
                    f"Column '{col}' does not exist in table '{actual_table}'. "
                    f"Available columns: {valid}."
                )

    # Check for obviously hallucinated columns (common patterns)
    _KNOWN_BAD_COLUMNS = {
        "school_distance", "university_name", "hospital_distance",
        "amenities", "school_name", "university_distance",
        "hospital_name", "rating", "reviews", "transport_distance",
        "parking", "garden", "pool",
    }
    for bad_col in _KNOWN_BAD_COLUMNS:
        # Check if the column appears as a standalone reference in the SQL
        pattern = rf"\b{re.escape(bad_col)}\b"
        if re.search(pattern, text_lower):
            return (
                f"Column '{bad_col}' does not exist in any table. "
                f"Available columns in 'properties': "
                f"{', '.join(sorted(_ALLOWED_COLUMNS['properties']))}."
            )

    return None


def _resolve_table(alias_or_name: str, sql_lower: str) -> str | None:
    """Try to resolve a table alias to the actual table name."""
    if alias_or_name in _ALLOWED_TABLES:
        return alias_or_name

    # Look for alias definitions: FROM properties p, JOIN city_centers cc
    for table in _ALLOWED_TABLES:
        # Match "table alias" or "table AS alias" patterns
        pattern = rf"(?:from|join)\s+{re.escape(table)}\s+(?:as\s+)?({re.escape(alias_or_name)})\b"
        if re.search(pattern, sql_lower):
            return table

    return None


def clean_sql(sql: str) -> str:
    """Strip markdown fences and trailing semicolons."""
    sql = sql.strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    return sql.strip().rstrip(";")


def rows_to_dicts(rows, keys) -> list[dict]:
    """Convert SQLAlchemy result rows to plain dicts."""
    return [dict(zip(keys, row)) for row in rows]


def truncate_sample(results: list[dict], max_items: int = 3) -> str:
    """Return a short string representation of results for the LLM summary prompt."""
    sample = results[:max_items]
    lines = []
    for r in sample:
        parts = []
        for key in ("title", "city", "price", "bedrooms", "intent", "property_type"):
            if key in r:
                parts.append(f"{key}={r[key]!r}")
        lines.append("{" + ", ".join(parts) + "}")
    if len(results) > max_items:
        lines.append(f"... and {len(results) - max_items} more")
    return "; ".join(lines)

