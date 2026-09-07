"""Conversation-level regression tests for context leakage across turns.

PURPOSE
-------
Node-level tests verify individual graph nodes in isolation but cannot catch
bugs where stale values survive across multiple conversation turns — the class
of failures that have caused production incidents.

These tests run the **full compiled graph** end-to-end, simulating real
multi-turn conversation flows.  Each scenario builds a chain of ``ainvoke``
calls, propagating the ``memory`` dict from one turn's output into the next
turn's input exactly as the production HTTP handler does.

NO DATABASE or LIVE LLM is required: a deterministic ``_ConversationMockLLM``
intercepts every LLM call and returns scripted responses based on the prompt
content.  ``db_engine=None`` is acceptable because the SQL execution node
skips the DB call when the engine is None (it raises, triggers handle_error,
and the test only inspects context/clarification state — not query results).

SCENARIOS
---------
1. Accumulate context over three turns (rent → add bedrooms → switch to buy).
2. City switch (Paris → Berlin) removes Paris from context.
3. Radius increase after city switch keeps Berlin, never resurfaces Paris.
4. Keyword-only NEW_SEARCH clears all structured filters.
5. Vague query ("Find me a property") triggers clarification; SQL not generated.
6. Affordability-only query ("I want something affordable") triggers
   clarification; SQL not generated.
7. Full multi-turn journey: Paris → Berlin → buy → radius increase.

SUCCESS CRITERIA
----------------
All scenarios pass with zero stale-context leaks.
Clarification gate blocks SQL generation for under-specified queries.
"""

from __future__ import annotations

import json
import logging

import pytest

from app.agents.free_chat.graph import build_graph
from app.agents.free_chat.state import AgentState
from app.infrastructure.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock DB engine
# ---------------------------------------------------------------------------

class _MockResult:
    """Minimal stand-in for SQLAlchemy CursorResult."""

    def keys(self):
        return ["id", "title", "city"]

    def fetchmany(self, n=50):
        return [{"id": 1, "title": "Test Property", "city": "TestCity"}]


class _MockConnection:
    async def execute(self, query):
        return _MockResult()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class _MockDBEngine:
    """Minimal async engine mock that allows execute_query_node to succeed.

    Without a working engine, execute_query_node raises, handle_error fires,
    and update_memory_node is skipped — so memory never gets search_context.
    This mock returns a single dummy row so the full success path runs:
    execute_query → summarize → update_memory → END.
    """

    def connect(self):
        return _MockConnection()


# ---------------------------------------------------------------------------
# Deterministic mock LLM
# ---------------------------------------------------------------------------

class _ConversationMockLLM(LLMProvider):
    """Scripted LLM for conversation-level regression tests.

    Routing logic mirrors the real prompts used in each node:
    - ``conversation classifier`` system prompt  → returns action JSON
    - ``query classifier`` system prompt         → returns intent JSON
    - ``parameter extractor`` system prompt      → returns constraints JSON
    - ``postgresql expert`` system prompt        → returns a minimal SQL string
    - Everything else (summarise, clarify, …)    → returns a safe plain string

    The constructor accepts per-category overrides so individual tests can
    inject specific responses without sub-classing.
    """

    def __init__(
        self,
        *,
        action: str = "refine_search",
        intent: str = "filter_search",
        constraints: dict | None = None,
        sql: str = "SELECT id, title, city FROM properties LIMIT 10",
    ) -> None:
        self._action = action
        self._intent = intent
        self._constraints = constraints or {}
        self._sql = sql

    async def invoke(self, messages: list, **kwargs) -> str:
        system: str = (messages[0]["content"] if messages else "").lower()

        if "conversation classifier" in system:
            return json.dumps({"action": self._action})
        if "query classifier" in system:
            return json.dumps({"intent": self._intent})
        if "parameter extractor" in system:
            return json.dumps(self._constraints)
        if "postgresql expert" in system:
            return self._sql
        # summarize / clarify / handle_error nodes
        return "Here are the results based on your search."

    async def invoke_json(self, messages: list, **kwargs) -> dict:
        raw = await self.invoke(messages, **kwargs)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_state(user_message: str, memory: dict | None = None) -> AgentState:
    """Build a minimal valid initial state for one graph turn."""
    return {
        "session_id": "conv-regression-test",
        "user_message": user_message,
        "memory": memory or {},
        "search_context": {},
        "constraints": {},
        "retry_count": 0,
        "sql_valid": False,
        "sql_error": "",
        "properties": [],
        "result_count": 0,
        "query_results": [],
    }


def _memory_from(result: dict) -> dict:
    """Extract the serialised memory dict that the next turn should receive.

    In production, the HTTP handler persists ``result["memory"]`` to the DB
    then passes it back on the next request.  We replicate that here.
    """
    return result.get("memory") or {}


def _ctx(result: dict) -> dict:
    """Shorthand: get the search_context dict from a graph result."""
    return result.get("search_context") or {}


def _active(result: dict) -> dict:
    """Shorthand: get the active_search dict from a graph result."""
    return result.get("active_search") or {}


# ---------------------------------------------------------------------------
# SCENARIO 1 — Accumulate context across three turns
#
# Turn 1: "Show apartments in Paris to rent"
# Turn 2: "Only 2 bedrooms"
# Turn 3: "For buy under 400k"
#
# After turn 3 expected:
#   city=Paris, intent=buy, property_type=apartment, bedrooms=2, budget=400_000
# ---------------------------------------------------------------------------

class TestScenario1AccumulateContext:
    """Verify that successive refinements accumulate correctly in context."""

    @pytest.mark.asyncio
    async def test_full_three_turn_accumulation(self):
        graph = build_graph()

        # ── Turn 1: initial search ────────────────────────────────────────
        t1_llm = _ConversationMockLLM(
            action="new_search",
            intent="filter_search",
            constraints={"city": "Paris", "intent": "rent", "property_type": "apartment"},
        )
        t1_state = _base_state("Show apartments in Paris to rent")
        t1 = await graph.ainvoke(t1_state, config={"configurable": {"llm": t1_llm, "db_engine": _MockDBEngine()}})

        ctx1 = _ctx(t1)
        assert ctx1.get("city") == "Paris", f"Turn 1: city expected 'Paris', got {ctx1.get('city')}"
        assert ctx1.get("intent") == "rent", f"Turn 1: intent expected 'rent', got {ctx1.get('intent')}"
        assert ctx1.get("property_type") == "apartment", "Turn 1: property_type must be 'apartment'"

        # ── Turn 2: refine with bedrooms ──────────────────────────────────
        t2_llm = _ConversationMockLLM(
            action="refine_search",
            intent="filter_search",
            constraints={"bedrooms": 2},
        )
        t2_state = _base_state("Only 2 bedrooms", memory=_memory_from(t1))
        t2 = await graph.ainvoke(t2_state, config={"configurable": {"llm": t2_llm, "db_engine": _MockDBEngine()}})

        ctx2 = _ctx(t2)
        assert ctx2.get("city") == "Paris", f"Turn 2: city must persist, got {ctx2.get('city')}"
        assert ctx2.get("intent") == "rent", f"Turn 2: intent must persist, got {ctx2.get('intent')}"
        assert ctx2.get("bedrooms") == 2, f"Turn 2: bedrooms expected 2, got {ctx2.get('bedrooms')}"

        # ── Turn 3: switch to buy + add budget ────────────────────────────
        t3_llm = _ConversationMockLLM(
            action="modify_search",
            intent="filter_search",
            constraints={"intent": "buy", "max_price": 400_000},
        )
        t3_state = _base_state("For buy under 400k", memory=_memory_from(t2))
        t3 = await graph.ainvoke(t3_state, config={"configurable": {"llm": t3_llm, "db_engine": _MockDBEngine()}})

        ctx3 = _ctx(t3)
        assert ctx3.get("city") == "Paris", f"Turn 3: city must persist, got {ctx3.get('city')}"
        assert ctx3.get("intent") == "buy", f"Turn 3: intent expected 'buy', got {ctx3.get('intent')}"
        assert ctx3.get("bedrooms") == 2, f"Turn 3: bedrooms must persist, got {ctx3.get('bedrooms')}"
        assert ctx3.get("max_price") == 400_000, f"Turn 3: max_price expected 400000, got {ctx3.get('max_price')}"

        # active_search dual-write check
        active3 = _active(t3)
        assert active3.get("city") == "Paris"
        assert active3.get("intent") == "buy"
        assert active3.get("bedrooms") == 2
        assert active3.get("budget") == 400_000


# ---------------------------------------------------------------------------
# SCENARIO 2 — City switch removes Paris
#
# Prior context: city=Paris (from scenario 1 end-state)
# Turn: "Switch to Berlin"
# Expected: city=Berlin, Paris removed
# ---------------------------------------------------------------------------

class TestScenario2CitySwitch:
    """Switching city must cleanly replace the old city — no Paris remnant."""

    @pytest.mark.asyncio
    async def test_paris_replaced_by_berlin(self):
        graph = build_graph()

        prior_memory = {
            "search_context": {
                "city": "Paris",
                "intent": "buy",
                "property_type": "apartment",
                "bedrooms": 2,
                "max_price": 400_000.0,
            }
        }

        llm = _ConversationMockLLM(
            action="modify_search",
            intent="filter_search",
            constraints={"city": "Berlin"},
        )
        state = _base_state("Switch to Berlin", memory=prior_memory)
        result = await graph.ainvoke(state, config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}})

        ctx = _ctx(result)
        assert ctx.get("city") == "Berlin", f"Expected 'Berlin', got {ctx.get('city')}"
        assert ctx.get("city") != "Paris", "LEAK: Paris must not appear after switching to Berlin"

        # Paris must not appear anywhere in the context string
        context_str = str(ctx).lower()
        assert "paris" not in context_str, f"LEAK: 'paris' found in context after city switch: {ctx}"

    @pytest.mark.asyncio
    async def test_non_city_fields_survive_city_switch(self):
        """Switching city should not wipe bedrooms/intent/budget."""
        graph = build_graph()

        prior_memory = {
            "search_context": {
                "city": "Paris",
                "intent": "buy",
                "bedrooms": 2,
                "max_price": 400_000.0,
            }
        }

        llm = _ConversationMockLLM(
            action="modify_search",
            intent="filter_search",
            constraints={"city": "Berlin"},
        )
        state = _base_state("Switch to Berlin", memory=prior_memory)
        result = await graph.ainvoke(state, config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}})

        ctx = _ctx(result)
        assert ctx.get("city") == "Berlin"
        assert ctx.get("intent") == "buy", "intent must survive city switch"
        assert ctx.get("bedrooms") == 2, "bedrooms must survive city switch"
        assert ctx.get("max_price") == 400_000.0, "budget must survive city switch"


# ---------------------------------------------------------------------------
# SCENARIO 3 — Radius increase after city switch; Paris never resurfaces
#
# Turn 1: city=Paris established
# Turn 2: "Switch to Berlin" → city=Berlin
# Turn 3: "Increase radius to 15km" → radius=15, city stays Berlin
# ---------------------------------------------------------------------------

class TestScenario3RadiusIncreaseKeepsBerlin:
    """Radius update should not resurrect stale Paris context."""

    @pytest.mark.asyncio
    async def test_radius_update_keeps_berlin(self):
        graph = build_graph()

        # Simulate memory after a Paris→Berlin city switch
        berlin_memory = {
            "search_context": {
                "city": "Berlin",
                "intent": "buy",
                "bedrooms": 2,
                "max_price": 400_000.0,
                "radius_km": None,
            }
        }

        llm = _ConversationMockLLM(
            action="modify_search",
            intent="radius_search",
            constraints={"radius_km": 15.0},
        )
        state = _base_state("Increase radius to 15km", memory=berlin_memory)
        result = await graph.ainvoke(state, config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}})

        ctx = _ctx(result)
        assert ctx.get("city") == "Berlin", f"Expected 'Berlin', got {ctx.get('city')}"
        assert ctx.get("radius_km") == 15.0, f"Expected radius_km=15.0, got {ctx.get('radius_km')}"

        # Paris must never appear
        context_str = str(ctx).lower()
        assert "paris" not in context_str, f"LEAK: 'paris' surfaced after radius update: {ctx}"

    @pytest.mark.asyncio
    async def test_full_three_turn_paris_berlin_radius(self):
        """End-to-end: Paris turn, Berlin turn, radius turn — Paris never returns."""
        graph = build_graph()

        # Turn 1: Paris
        t1_llm = _ConversationMockLLM(
            action="new_search",
            intent="filter_search",
            constraints={"city": "Paris", "intent": "rent"},
        )
        t1 = await graph.ainvoke(
            _base_state("Show apartments in Paris to rent"),
            config={"configurable": {"llm": t1_llm, "db_engine": _MockDBEngine()}},
        )

        # Turn 2: Switch to Berlin
        t2_llm = _ConversationMockLLM(
            action="modify_search",
            intent="filter_search",
            constraints={"city": "Berlin"},
        )
        t2 = await graph.ainvoke(
            _base_state("Switch to Berlin", memory=_memory_from(t1)),
            config={"configurable": {"llm": t2_llm, "db_engine": _MockDBEngine()}},
        )
        assert _ctx(t2).get("city") == "Berlin"

        # Turn 3: Increase radius
        t3_llm = _ConversationMockLLM(
            action="modify_search",
            intent="radius_search",
            constraints={"radius_km": 15.0},
        )
        t3 = await graph.ainvoke(
            _base_state("Increase radius to 15km", memory=_memory_from(t2)),
            config={"configurable": {"llm": t3_llm, "db_engine": _MockDBEngine()}},
        )

        ctx3 = _ctx(t3)
        assert ctx3.get("city") == "Berlin", f"Expected Berlin, got {ctx3.get('city')}"
        assert ctx3.get("radius_km") == 15.0, f"Expected radius_km=15, got {ctx3.get('radius_km')}"
        assert "paris" not in str(ctx3).lower(), f"LEAK: Paris surfaced in turn 3: {ctx3}"


# ---------------------------------------------------------------------------
# SCENARIO 4 — Pattern/keyword search is a NEW_SEARCH, wipes all filters
#
# Prior context: city=Paris, intent=buy, bedrooms=2, budget=400k
# Turn: "Properties with modern in title"
# Expected: fresh search — city/intent/bedrooms/budget all None
# ---------------------------------------------------------------------------

class TestScenario4KeywordSearchClearsContext:
    """A keyword-only NEW_SEARCH must discard all structured filters."""

    @pytest.mark.asyncio
    async def test_all_structured_filters_cleared(self):
        graph = build_graph()

        rich_prior = {
            "search_context": {
                "city": "Paris",
                "intent": "buy",
                "property_type": "apartment",
                "bedrooms": 2,
                "max_price": 400_000.0,
                "radius_km": 10.0,
            }
        }

        llm = _ConversationMockLLM(
            action="new_search",
            intent="pattern_search",
            constraints={},  # keyword search extracts no structured constraints
            sql="SELECT * FROM properties WHERE title ILIKE '%modern%' LIMIT 20",
        )
        state = _base_state("Properties with modern in title", memory=rich_prior)
        result = await graph.ainvoke(state, config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}})

        ctx = _ctx(result)

        # All structured filters must be cleared
        assert ctx.get("city") is None, f"LEAK: city should be cleared, got {ctx.get('city')}"
        assert ctx.get("intent") is None, f"LEAK: intent should be cleared, got {ctx.get('intent')}"
        assert ctx.get("bedrooms") is None, f"LEAK: bedrooms should be cleared, got {ctx.get('bedrooms')}"
        assert ctx.get("max_price") is None, f"LEAK: max_price should be cleared, got {ctx.get('max_price')}"
        assert ctx.get("property_type") is None, f"LEAK: property_type should be cleared, got {ctx.get('property_type')}"

        # active_search dual-write check
        active = _active(result)
        assert active.get("city") is None
        assert active.get("intent") is None
        assert active.get("bedrooms") is None
        assert active.get("budget") is None

    @pytest.mark.asyncio
    async def test_new_search_id_generated(self):
        """A NEW_SEARCH must produce a fresh search_id (different from prior)."""
        graph = build_graph()

        prior_memory = {
            "search_context": {"city": "Paris"},
            "active_search": {
                "search_id": "original-search-id-12345",
                "city": "Paris",
            },
        }

        llm = _ConversationMockLLM(
            action="new_search",
            intent="pattern_search",
            constraints={},
        )
        state = _base_state("Properties with modern in title", memory=prior_memory)
        result = await graph.ainvoke(state, config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}})

        new_search_id = _active(result).get("search_id")
        assert new_search_id is not None
        assert new_search_id != "original-search-id-12345", (
            "NEW_SEARCH must generate a fresh search_id"
        )


# ---------------------------------------------------------------------------
# SCENARIO 5 — Vague query triggers clarification; SQL not generated
#
# Turn: "Find me a property"
# Expected: clarification_needed=True, generated_sql absent/None
# ---------------------------------------------------------------------------

class TestScenario5VagueQueryClarification:
    """Vague queries with no filters must be caught before SQL generation."""

    @pytest.mark.asyncio
    async def test_clarification_triggered_no_sql(self):
        graph = build_graph()

        llm = _ConversationMockLLM(
            action="need_clarification",
            intent="clarification_needed",
            constraints={},
        )
        state = _base_state("Find me a property")
        result = await graph.ainvoke(state, config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}})

        assert result.get("clarification_needed") is True, (
            "FAIL: clarification_needed must be True for vague query"
        )
        assert result.get("clarification_question"), (
            "FAIL: clarification_question must be non-empty"
        )

        # SQL must NOT be generated when clarification is needed
        sql = result.get("generated_sql")
        assert not sql, f"FAIL: SQL generated when clarification was needed: {sql!r}"

    @pytest.mark.asyncio
    async def test_clarification_gate_blocks_execution(self):
        """Graph must route to clarify node, not generate_sql, for vague input."""
        graph = build_graph()

        llm = _ConversationMockLLM(
            action="need_clarification",
            intent="clarification_needed",
            constraints={},
        )
        state = _base_state("Find me a property")
        result = await graph.ainvoke(state, config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}})

        # query_results must be empty (execution never ran)
        assert result.get("query_results") in (None, []), (
            "FAIL: query_results should be empty when clarification requested"
        )
        # result_count should be 0
        assert result.get("result_count", 0) == 0


# ---------------------------------------------------------------------------
# SCENARIO 6 — Affordability-only query triggers clarification; SQL not generated
#
# Turn: "I want something affordable"
# Expected: clarification_needed=True, SQL not executed
# ---------------------------------------------------------------------------

class TestScenario6AffordabilityOnlyClarification:
    """Under-specified queries with only budget intent must trigger clarification."""

    @pytest.mark.asyncio
    async def test_affordable_triggers_clarification_no_sql(self):
        graph = build_graph()

        llm = _ConversationMockLLM(
            action="need_clarification",
            intent="clarification_needed",
            constraints={},
        )
        state = _base_state("I want something affordable")
        result = await graph.ainvoke(state, config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}})

        assert result.get("clarification_needed") is True, (
            "FAIL: affordability-only query must trigger clarification"
        )
        assert result.get("clarification_question"), (
            "FAIL: a clarification question must be returned"
        )

        sql = result.get("generated_sql")
        assert not sql, f"FAIL: SQL generated for affordability-only query: {sql!r}"

    @pytest.mark.asyncio
    async def test_affordable_clarification_asks_for_city(self):
        """The clarification question must ask for missing required context."""
        graph = build_graph()

        llm = _ConversationMockLLM(
            action="need_clarification",
            intent="clarification_needed",
            constraints={},
        )
        state = _base_state("I want something affordable")
        result = await graph.ainvoke(state, config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}})

        question = result.get("clarification_question") or ""
        # The clarification must ask for city and/or intent — the two
        # highest-priority missing essentials.
        has_city_ask = "city" in question.lower()
        has_intent_ask = (
            "buy" in question.lower()
            or "rent" in question.lower()
            or "looking for" in question.lower()
        )
        assert has_city_ask or has_intent_ask, (
            f"FAIL: clarification question should ask for city/intent, got: {question!r}"
        )


# ---------------------------------------------------------------------------
# SCENARIO 7 — Full multi-turn journey
#
# Turn 1: "Show apartments in Paris"        → city=Paris, type=apartment
# Turn 2: "Switch to Berlin"                → city=Berlin (Paris removed)
# Turn 3: "Now I want to buy"              → intent=buy
# Turn 4: "Increase radius to 15km"        → radius=15
#
# Final expected: city=Berlin, intent=buy, radius=15
# Invariants: Paris never returns; search_id updated where appropriate
# ---------------------------------------------------------------------------

class TestScenario7FullJourney:
    """End-to-end multi-turn conversation — no stale context anywhere."""

    @pytest.mark.asyncio
    async def test_full_four_turn_journey(self):
        graph = build_graph()
        memory: dict = {}

        # ── Turn 1: initial Paris search ─────────────────────────────────
        t1_llm = _ConversationMockLLM(
            action="new_search",
            intent="filter_search",
            constraints={"city": "Paris", "property_type": "apartment"},
        )
        t1 = await graph.ainvoke(
            _base_state("Show apartments in Paris", memory=memory),
            config={"configurable": {"llm": t1_llm, "db_engine": _MockDBEngine()}},
        )
        memory = _memory_from(t1)

        ctx1 = _ctx(t1)
        assert ctx1.get("city") == "Paris"
        assert ctx1.get("property_type") == "apartment"

        # ── Turn 2: switch to Berlin ──────────────────────────────────────
        t2_llm = _ConversationMockLLM(
            action="modify_search",
            intent="filter_search",
            constraints={"city": "Berlin"},
        )
        t2 = await graph.ainvoke(
            _base_state("Switch to Berlin", memory=memory),
            config={"configurable": {"llm": t2_llm, "db_engine": _MockDBEngine()}},
        )
        memory = _memory_from(t2)

        ctx2 = _ctx(t2)
        assert ctx2.get("city") == "Berlin", f"Turn 2: expected Berlin, got {ctx2.get('city')}"
        assert "paris" not in str(ctx2).lower(), f"LEAK turn 2: Paris in context {ctx2}"

        # ── Turn 3: switch intent to buy ──────────────────────────────────
        t3_llm = _ConversationMockLLM(
            action="modify_search",
            intent="filter_search",
            constraints={"intent": "buy"},
        )
        t3 = await graph.ainvoke(
            _base_state("Now I want to buy", memory=memory),
            config={"configurable": {"llm": t3_llm, "db_engine": _MockDBEngine()}},
        )
        memory = _memory_from(t3)

        ctx3 = _ctx(t3)
        assert ctx3.get("city") == "Berlin", f"Turn 3: city must stay Berlin, got {ctx3.get('city')}"
        assert ctx3.get("intent") == "buy", f"Turn 3: intent expected 'buy', got {ctx3.get('intent')}"
        assert "paris" not in str(ctx3).lower(), f"LEAK turn 3: Paris in context {ctx3}"

        # ── Turn 4: increase radius ───────────────────────────────────────
        t4_llm = _ConversationMockLLM(
            action="modify_search",
            intent="radius_search",
            constraints={"radius_km": 15.0},
        )
        t4 = await graph.ainvoke(
            _base_state("Increase radius to 15km", memory=memory),
            config={"configurable": {"llm": t4_llm, "db_engine": _MockDBEngine()}},
        )

        ctx4 = _ctx(t4)
        assert ctx4.get("city") == "Berlin", f"Final: city expected Berlin, got {ctx4.get('city')}"
        assert ctx4.get("intent") == "buy", f"Final: intent expected buy, got {ctx4.get('intent')}"
        assert ctx4.get("radius_km") == 15.0, f"Final: radius expected 15, got {ctx4.get('radius_km')}"
        assert "paris" not in str(ctx4).lower(), f"LEAK final: Paris in context {ctx4}"

    @pytest.mark.asyncio
    async def test_city_never_returns_after_switch(self):
        """Regression: Paris must not resurface in any turn after switching."""
        graph = build_graph()

        turns = [
            ("Show apartments in Paris", "new_search", "filter_search", {"city": "Paris", "property_type": "apartment"}),
            ("Switch to Berlin", "modify_search", "filter_search", {"city": "Berlin"}),
            ("Now I want to buy", "modify_search", "filter_search", {"intent": "buy"}),
            ("Increase radius to 15km", "modify_search", "radius_search", {"radius_km": 15.0}),
        ]

        memory: dict = {}
        for i, (message, action, intent, constraints) in enumerate(turns, start=1):
            llm = _ConversationMockLLM(action=action, intent=intent, constraints=constraints)
            result = await graph.ainvoke(
                _base_state(message, memory=memory),
                config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}},
            )
            memory = _memory_from(result)

            if i >= 2:  # After the Berlin switch, Paris must never return
                ctx = _ctx(result)
                assert ctx.get("city") != "Paris", (
                    f"LEAK at turn {i} ({message!r}): city reverted to Paris — {ctx}"
                )
                assert "paris" not in str(ctx).lower(), (
                    f"LEAK at turn {i} ({message!r}): 'paris' found in context — {ctx}"
                )

    @pytest.mark.asyncio
    async def test_active_search_consistent_with_search_context(self):
        """active_search (T22 canonical) must stay in sync with search_context."""
        graph = build_graph()
        memory: dict = {}

        turns = [
            ("Show apartments in Paris", "new_search", "filter_search", {"city": "Paris", "property_type": "apartment"}),
            ("Switch to Berlin", "modify_search", "filter_search", {"city": "Berlin"}),
            ("Now I want to buy", "modify_search", "filter_search", {"intent": "buy"}),
            ("Increase radius to 15km", "modify_search", "radius_search", {"radius_km": 15.0}),
        ]

        for message, action, intent, constraints in turns:
            llm = _ConversationMockLLM(action=action, intent=intent, constraints=constraints)
            result = await graph.ainvoke(
                _base_state(message, memory=memory),
                config={"configurable": {"llm": llm, "db_engine": _MockDBEngine()}},
            )
            memory = _memory_from(result)

            ctx = _ctx(result)
            active = _active(result)

            # Core search dimensions must match between both representations
            assert active.get("city") == ctx.get("city"), (
                f"active_search.city={active.get('city')!r} != "
                f"search_context.city={ctx.get('city')!r} after {message!r}"
            )
            assert active.get("intent") == ctx.get("intent"), (
                f"active_search.intent={active.get('intent')!r} != "
                f"search_context.intent={ctx.get('intent')!r} after {message!r}"
            )
