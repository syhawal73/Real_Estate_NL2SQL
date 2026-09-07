"""Unit tests for SQL validation and utility functions (Phase 4.1).

These tests do not require a database or running LLM.

Phase 4.1 additions:
- UNION rejection
- information_schema / pg_catalog / pg_stat rejection
- COPY keyword rejection
- SQL comment rejection
- Semicolon chaining rejection
- Schema-aware column validation
"""

import pytest

from app.agents.free_chat.utils import clean_sql, truncate_sample, validate_sql


class TestValidateSql:
    def test_valid_select(self):
        ok, err = validate_sql("SELECT * FROM properties LIMIT 10")
        assert ok is True
        assert err == ""

    def test_valid_select_with_filters(self):
        ok, err = validate_sql(
            "SELECT id, title, price FROM properties "
            "WHERE city = 'London' AND intent = 'rent' LIMIT 20"
        )
        assert ok is True

    def test_valid_aggregation(self):
        ok, err = validate_sql(
            "SELECT city, AVG(price) FROM properties GROUP BY city"
        )
        assert ok is True

    def test_rejects_insert(self):
        ok, err = validate_sql("INSERT INTO properties (title) VALUES ('bad')")
        assert ok is False
        assert "SELECT" in err

    def test_rejects_update(self):
        ok, err = validate_sql("UPDATE properties SET price = 0")
        assert ok is False

    def test_rejects_delete(self):
        ok, err = validate_sql("DELETE FROM properties")
        assert ok is False

    def test_rejects_drop(self):
        ok, err = validate_sql("DROP TABLE properties")
        assert ok is False
        assert "DROP" in err

    def test_rejects_unknown_table(self):
        ok, err = validate_sql("SELECT * FROM schools")
        assert ok is False
        assert "schools" in err

    def test_rejects_empty(self):
        ok, err = validate_sql("")
        assert ok is False

    def test_rejects_none_like(self):
        ok, err = validate_sql("   ")
        assert ok is False

    def test_allows_join_city_centers(self):
        ok, err = validate_sql(
            "SELECT p.title, cc.latitude FROM properties p "
            "JOIN city_centers cc ON p.city = cc.city LIMIT 10"
        )
        assert ok is True

    def test_strips_trailing_semicolon(self):
        ok, err = validate_sql("SELECT * FROM properties;")
        assert ok is True


class TestSqlHardening:
    """Phase 4.1 SQL validator hardening tests."""

    # --- UNION ---
    def test_rejects_union(self):
        ok, err = validate_sql(
            "SELECT * FROM properties UNION SELECT * FROM properties"
        )
        assert ok is False
        assert "UNION" in err

    def test_rejects_union_all(self):
        ok, err = validate_sql(
            "SELECT id FROM properties UNION ALL SELECT id FROM properties"
        )
        assert ok is False

    # --- System catalogs ---
    def test_rejects_information_schema(self):
        ok, err = validate_sql("SELECT * FROM information_schema.tables")
        assert ok is False
        assert "information_schema" in err

    def test_rejects_pg_catalog(self):
        ok, err = validate_sql("SELECT * FROM pg_catalog.pg_tables")
        assert ok is False
        assert "pg_catalog" in err

    def test_rejects_pg_stat(self):
        ok, err = validate_sql("SELECT * FROM pg_stat_activity")
        assert ok is False
        assert "pg_stat" in err

    # --- COPY ---
    def test_rejects_copy(self):
        ok, err = validate_sql("COPY properties TO '/tmp/data.csv'")
        assert ok is False

    # --- Multiple statements ---
    def test_rejects_semicolon_chaining(self):
        ok, err = validate_sql(
            "SELECT * FROM properties; DROP TABLE properties"
        )
        assert ok is False
        assert "Multiple statements" in err

    def test_rejects_mid_query_semicolon(self):
        ok, err = validate_sql(
            "SELECT * FROM properties WHERE city = 'London'; SELECT 1"
        )
        assert ok is False

    # --- SQL comments ---
    def test_rejects_line_comment(self):
        ok, err = validate_sql(
            "SELECT * FROM properties -- this is a comment"
        )
        assert ok is False
        assert "comment" in err.lower()

    def test_rejects_block_comment(self):
        ok, err = validate_sql(
            "SELECT * FROM properties /* hidden query */"
        )
        assert ok is False
        assert "comment" in err.lower()

    # --- Other blocked keywords ---
    def test_rejects_truncate(self):
        ok, err = validate_sql("TRUNCATE TABLE properties")
        assert ok is False

    def test_rejects_alter(self):
        ok, err = validate_sql("ALTER TABLE properties ADD COLUMN x INT")
        assert ok is False

    def test_rejects_create(self):
        ok, err = validate_sql("CREATE TABLE evil (id INT)")
        assert ok is False


class TestColumnValidation:
    """Phase 4.1 schema-aware column validation tests."""

    def test_rejects_school_distance(self):
        ok, err = validate_sql(
            "SELECT school_distance FROM properties"
        )
        assert ok is False
        assert "school_distance" in err
        assert "properties" in err  # should mention available columns

    def test_rejects_university_name(self):
        ok, err = validate_sql(
            "SELECT university_name FROM properties"
        )
        assert ok is False
        assert "university_name" in err

    def test_rejects_hospital_distance(self):
        ok, err = validate_sql(
            "SELECT hospital_distance FROM properties"
        )
        assert ok is False
        assert "hospital_distance" in err

    def test_rejects_amenities(self):
        ok, err = validate_sql(
            "SELECT amenities FROM properties"
        )
        assert ok is False
        assert "amenities" in err

    def test_rejects_rating(self):
        ok, err = validate_sql(
            "SELECT rating FROM properties"
        )
        assert ok is False

    def test_allows_valid_columns(self):
        ok, err = validate_sql(
            "SELECT id, title, city, price, bedrooms, bathrooms, size_sqm, "
            "property_type, distance_from_city_km, description "
            "FROM properties LIMIT 10"
        )
        assert ok is True

    def test_allows_valid_city_centers_columns(self):
        ok, err = validate_sql(
            "SELECT city, latitude, longitude FROM city_centers"
        )
        assert ok is True

    def test_rejects_qualified_bad_column(self):
        ok, err = validate_sql(
            "SELECT p.school_distance FROM properties p"
        )
        assert ok is False


class TestCleanSql:
    def test_strips_sql_fence(self):
        assert clean_sql("```sql\nSELECT 1\n```") == "SELECT 1"

    def test_strips_plain_fence(self):
        assert clean_sql("```\nSELECT 1\n```") == "SELECT 1"

    def test_strips_semicolon(self):
        assert clean_sql("SELECT 1;") == "SELECT 1"

    def test_no_change_needed(self):
        assert clean_sql("SELECT * FROM properties") == "SELECT * FROM properties"


class TestTruncateSample:
    def test_empty(self):
        assert truncate_sample([]) == ""

    def test_single(self):
        result = truncate_sample([{"title": "Nice flat", "city": "London", "price": 1200, "bedrooms": 2, "intent": "rent", "property_type": "apartment"}])
        assert "Nice flat" in result
        assert "London" in result

    def test_truncates_to_max(self):
        rows = [{"title": f"Flat {i}", "city": "Paris", "price": 1000, "bedrooms": 1, "intent": "rent", "property_type": "apartment"} for i in range(10)]
        result = truncate_sample(rows, max_items=3)
        assert "7 more" in result

