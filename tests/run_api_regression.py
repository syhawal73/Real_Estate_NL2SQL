"""
backend/evals/run_api_regression.py

End-to-end regression suite.

Tests:

Client
  -> FastAPI /chat
  -> LangGraph
  -> LLM
  -> SQL generation
  -> Database
  -> Response

Produces:

evals/reports/api_regression_report.md
"""

from dataclasses import dataclass, field
from pathlib import Path
import requests
import json
import uuid

BASE_URL = "http://localhost:8000"


# ============================================================
# Scenarios
# ============================================================

@dataclass
class Scenario:
    id: str
    category: str
    conversation: list[str]

    sql_contains: list[str] = field(default_factory=list)
    sql_not_contains: list[str] = field(default_factory=list)

    response_contains: list[str] = field(default_factory=list)

    clarification_expected: bool | None = None


SCENARIOS = [

    # --------------------------------------------------------
    # Clarification
    # --------------------------------------------------------

    Scenario(
        id="clarify_property",
        category="clarification",
        conversation=[
            "Find me a property"
        ],
        clarification_expected=True,
    ),

    Scenario(
        id="clarify_affordable",
        category="clarification",
        conversation=[
            "I want something affordable"
        ],
        clarification_expected=True,
    ),

    # --------------------------------------------------------
    # Context
    # --------------------------------------------------------

    Scenario(
        id="city_switch",
        category="context",
        conversation=[
            "Show apartments in Paris to rent",
            "Only 2 bedrooms",
            "Switch to Berlin"
        ],
        response_contains=["Berlin"],
    ),

    # --------------------------------------------------------
    # Count
    # --------------------------------------------------------

    Scenario(
        id="count_rome",
        category="count",
        conversation=[
            "How many apartments are for rent in Rome?"
        ],
        sql_contains=["COUNT"],
    ),

    # --------------------------------------------------------
    # Aggregation
    # --------------------------------------------------------

    Scenario(
        id="avg_price",
        category="aggregation",
        conversation=[
            "What is the average price of houses in Rome?"
        ],
        sql_contains=["AVG"],
    ),

    # --------------------------------------------------------
    # Comparison
    # --------------------------------------------------------

    Scenario(
        id="comparison",
        category="comparison",
        conversation=[
            "Compare average sale prices in London vs Berlin"
        ],
    ),

    # --------------------------------------------------------
    # Ranking
    # --------------------------------------------------------

    Scenario(
        id="ranking_cheapest",
        category="ranking",
        conversation=[
            "Show the 5 cheapest apartments in Berlin"
        ],
        sql_contains=[
            "ORDER BY",
            "LIMIT 5"
        ],
        sql_not_contains=[
            "longitude",
            "latitude"
        ]
    ),

    Scenario(
        id="ranking_closest",
        category="ranking",
        conversation=[
            "Show me the closest properties to the city centre in Rome"
        ],
        sql_contains=[
            "distance_from_city_km"
        ],
        sql_not_contains=[
            "longitude",
            "latitude"
        ]
    ),

    # --------------------------------------------------------
    # Radius
    # --------------------------------------------------------

    Scenario(
        id="radius",
        category="radius",
        conversation=[
            "Homes within 20km of Amsterdam city centre"
        ],
        sql_contains=[
            "distance_from_city_km"
        ],
        sql_not_contains=[
            "longitude",
            "latitude"
        ]
    ),

    # --------------------------------------------------------
    # Pattern Search
    # --------------------------------------------------------

    Scenario(
        id="title_pattern",
        category="pattern",
        conversation=[
            "Properties with modern in title"
        ],
        sql_contains=["ILIKE"]
    ),

    Scenario(
        id="description_pattern",
        category="pattern",
        conversation=[
            "Properties with attractive in description"
        ],
        sql_contains=["ILIKE"]
    ),

    # --------------------------------------------------------
    # Listing
    # --------------------------------------------------------

    Scenario(
        id="top_5",
        category="listing",
        conversation=[
            "Show me top 5 properties"
        ],
        sql_contains=["LIMIT 5"]
    ),
]


# ============================================================
# Helpers
# ============================================================

def send_message(session_id, message):

    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "session_id": session_id,
            "message": message,
        },
        timeout=180,
    )

    response.raise_for_status()

    return response.json()


def run_conversation(messages):

    session_id = str(uuid.uuid4())

    last_response = None

    for msg in messages:
        last_response = send_message(
            session_id=session_id,
            message=msg,
        )

        session_id = last_response["session_id"]

    return last_response


# ============================================================
# Validation
# ============================================================

def validate(scenario, result):

    failures = []

    sql = result.get("generated_sql") or ""

    response = result.get("assistant_message") or ""

    clarification = result.get("clarification_needed")

    if scenario.clarification_expected is not None:
        if clarification != scenario.clarification_expected:
            failures.append(
                f"Expected clarification={scenario.clarification_expected}"
            )

    for token in scenario.sql_contains:
        if token.lower() not in sql.lower():
            failures.append(
                f"Missing SQL token: {token}"
            )

    for token in scenario.sql_not_contains:
        if token.lower() in sql.lower():
            failures.append(
                f"Forbidden SQL token: {token}"
            )

    for token in scenario.response_contains:
        if token.lower() not in response.lower():
            failures.append(
                f"Missing response token: {token}"
            )

    return failures


# ============================================================
# Markdown
# ============================================================

def generate_markdown(results):

    passed = sum(r["passed"] for r in results)
    failed = len(results) - passed

    lines = []

    lines.append("# API Regression Report")
    lines.append("")
    lines.append(f"Passed: {passed}")
    lines.append(f"Failed: {failed}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for result in results:

        lines.append(f"## {result['id']}")
        lines.append("")

        lines.append(
            f"Status: {'PASS' if result['passed'] else 'FAIL'}"
        )

        lines.append("")

        if result["failures"]:
            lines.append("### Failures")

            for failure in result["failures"]:
                lines.append(f"- {failure}")

            lines.append("")

        lines.append("### SQL")
        lines.append("```sql")
        lines.append(result["sql"] or "")
        lines.append("```")
        lines.append("")

        lines.append("### Response")
        lines.append("```text")
        lines.append(result["response"] or "")
        lines.append("```")
        lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# Main
# ============================================================

def main():

    results = []

    for scenario in SCENARIOS:

        try:

            result = run_conversation(
                scenario.conversation
            )

            failures = validate(
                scenario,
                result,
            )

            results.append({
                "id": scenario.id,
                "passed": len(failures) == 0,
                "failures": failures,
                "sql": result.get("generated_sql") or "",
                "response": result.get("assistant_message") or "",
            })

        except Exception as exc:

            results.append({
                "id": scenario.id,
                "passed": False,
                "failures": [str(exc)],
                "sql": "",
                "response": "",
            })

    report = generate_markdown(results)

    output_dir = Path("evals/reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "api_regression_report.md"

    output_file.write_text(
        report,
        encoding="utf-8",
    )

    print(f"Report written to {output_file}")


if __name__ == "__main__":
    main()