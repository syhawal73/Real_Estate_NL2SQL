"""Tests for the clarification gate (NEED_CLARIFICATION action).

Verifies the core requirement:
  • When conversation_action == "need_clarification", **no SQL is generated**
    and a clarification question is returned to the user.

Covers three layers:
  1. ``need_clarification.py`` — pure-logic handler
  2. ``extract_constraints_node`` — the gate inside the LangGraph node
  3. ``needs_clarification_node`` — belt-and-suspenders fallback
  4. ``_route_after_needs_clarification`` — graph routing

All tests are pure unit tests — no LLM, no database required.
"""

import pytest

from app.agents.free_chat.graph import _route_after_needs_clarification
from app.agents.free_chat.nodes.extract_constraints import extract_constraints_node
from app.agents.free_chat.nodes.needs_clarification import needs_clarification_node
from app.conversation.need_clarification import (
    apply_need_clarification,
    build_clarification_question,
)


# ===================================================================
# 1. Unit tests for build_clarification_question
# ===================================================================

class TestBuildClarificationQuestion:
    """Tests for the question-builder that inspects SearchContext gaps."""

    def test_all_fields_missing_returns_all_prompts(self):
        """Empty context → asks about rent/buy, city, and budget."""
        question, missing = build_clarification_question({})
        assert "rent" in question.lower() or "buy" in question.lower()
        assert "city" in question.lower()
        assert "budget" in question.lower()
        assert set(missing) == {"intent", "city", "max_price"}

    def test_city_known_asks_remaining(self):
        """City already set → should NOT ask about city again."""
        question, missing = build_clarification_question({"city": "London"})
        assert "city" not in [m for m in missing]
        assert "intent" in missing
        assert "max_price" in missing

    def test_intent_known_asks_remaining(self):
        """Rent/buy already set → should NOT ask about intent."""
        question, missing = build_clarification_question({"intent": "rent"})
        assert "intent" not in missing
        assert "city" in missing

    def test_all_essentials_present_returns_generic(self):
        """All essentials present → generic follow-up, no missing fields."""
        question, missing = build_clarification_question({
            "city": "Paris",
            "intent": "buy",
            "max_price": 500000,
        })
        assert missing == []
        assert "details" in question.lower() or "more" in question.lower()

    def test_none_context_treated_as_empty(self):
        """None context → same as empty dict."""
        question, missing = build_clarification_question(None)
        assert len(missing) == 3  # all essential fields missing

    def test_single_missing_field_no_bullet_list(self):
        """Only one field missing → simple single question, not a bullet list."""
        question, missing = build_clarification_question({
            "city": "Berlin",
            "intent": "rent",
        })
        assert missing == ["max_price"]
        assert "•" not in question  # single question, no bullets


# ===================================================================
# 2. Unit tests for apply_need_clarification
# ===================================================================

class TestApplyNeedClarification:
    """Tests for the handler that short-circuits the pipeline."""

    def test_returns_empty_constraints(self):
        """CRITICAL: constraints must be empty — no extraction performed."""
        ctx, constraints, question = apply_need_clarification(
            "Find me a property", {}
        )
        assert constraints == {}

    def test_returns_clarification_question(self):
        """Must return a non-empty question string."""
        _, _, question = apply_need_clarification("Find me a property", {})
        assert isinstance(question, str)
        assert len(question) > 0

    def test_preserves_existing_context(self):
        """Existing context must NOT be cleared."""
        original = {"city": "London", "intent": "rent"}
        ctx, _, _ = apply_need_clarification("something affordable", original)
        assert ctx["city"] == "London"
        assert ctx["intent"] == "rent"

    def test_does_not_mutate_original_context(self):
        """Handler must not mutate the input dict."""
        original = {"city": "London"}
        ctx, _, _ = apply_need_clarification("test", original)
        assert original == {"city": "London"}  # unchanged

    def test_vague_find_property(self):
        """'Find me a property' with no context → asks rent/buy + city + budget."""
        _, constraints, question = apply_need_clarification(
            "Find me a property", {}
        )
        assert constraints == {}
        assert "rent" in question.lower() or "buy" in question.lower()

    def test_vague_affordable(self):
        """'I want something affordable' with no context → asks essentials."""
        _, constraints, question = apply_need_clarification(
            "I want something affordable", {}
        )
        assert constraints == {}
        assert len(question) > 10  # non-trivial question


# ===================================================================
# 3. Integration: extract_constraints_node with need_clarification
# ===================================================================

class TestExtractConstraintsGate:
    """Verify extract_constraints_node short-circuits for NEED_CLARIFICATION."""

    @pytest.mark.asyncio
    async def test_need_clarification_action_skips_extraction(self):
        """When conversation_action='need_clarification', node must:
        - Return clarification_needed=True
        - Return a clarification question
        - Return empty constraints (no extraction)
        - NOT call the LLM (config has no 'llm' key — would crash if called)
        """
        state = {
            "user_message": "Find me a property",
            "conversation_action": "need_clarification",
            "search_context": {},
            "constraints": {},
            "intent": "clarification_needed",
        }
        # No LLM in config — proves the gate fires BEFORE any LLM call
        config = {"configurable": {}}

        result = await extract_constraints_node(state, config)

        assert result["clarification_needed"] is True
        assert result["clarification_question"]  # non-empty
        assert result["constraints"] == {}
        # No generated_sql key — SQL generation never happened
        assert "generated_sql" not in result

    @pytest.mark.asyncio
    async def test_need_clarification_preserves_context(self):
        """Existing search_context must survive the gate unchanged."""
        state = {
            "user_message": "I want something affordable",
            "conversation_action": "need_clarification",
            "search_context": {"city": "London", "intent": "rent"},
            "constraints": {},
        }
        config = {"configurable": {}}

        result = await extract_constraints_node(state, config)

        assert result["search_context"]["city"] == "London"
        assert result["search_context"]["intent"] == "rent"
        assert result["clarification_needed"] is True
        assert result["constraints"] == {}

    @pytest.mark.asyncio
    async def test_non_clarification_action_not_affected(self):
        """refine_search action must NOT trigger the clarification gate.

        We verify this indirectly: since config has no 'llm', the default
        path would attempt to access it and fail. If the gate wrongly fires,
        this test passes (which would be incorrect). So we check that a
        KeyError is raised, proving the gate was skipped.
        """
        state = {
            "user_message": "Show houses in Paris",
            "conversation_action": "refine_search",
            "search_context": {},
            "constraints": {},
        }
        config = {"configurable": {}}  # no LLM

        with pytest.raises(KeyError):
            await extract_constraints_node(state, config)


# ===================================================================
# 4. Integration: needs_clarification_node with conversation_action
# ===================================================================

class TestNeedsClarificationNodeGate:
    """Verify needs_clarification_node respects the conversation_action."""

    @pytest.mark.asyncio
    async def test_upstream_flag_passthrough(self):
        """If extract_constraints already set clarification_needed + question,
        needs_clarification_node must pass them through unchanged."""
        state = {
            "intent": "filter_search",
            "search_context": {},
            "constraints": {},
            "conversation_action": "need_clarification",
            "clarification_needed": True,
            "clarification_question": "Which city are you interested in?",
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is True
        assert result["clarification_question"] == "Which city are you interested in?"

    @pytest.mark.asyncio
    async def test_fallback_when_flag_not_set(self):
        """If conversation_action is need_clarification but the flag wasn't set
        upstream, the node must still catch it and generate a question."""
        state = {
            "intent": "filter_search",
            "search_context": {},
            "constraints": {},
            "conversation_action": "need_clarification",
            # clarification_needed NOT set
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is True
        assert result["clarification_question"]  # non-empty

    @pytest.mark.asyncio
    async def test_normal_action_not_intercepted(self):
        """refine_search with sufficient context → proceeds normally."""
        state = {
            "intent": "filter_search",
            "search_context": {"city": "Paris", "bedrooms": 3},
            "constraints": {"city": "Paris", "bedrooms": 3},
            "conversation_action": "refine_search",
        }
        result = await needs_clarification_node(state, {"configurable": {}})
        assert result["clarification_needed"] is False


# ===================================================================
# 5. Routing: _route_after_needs_clarification
# ===================================================================

class TestRoutingAfterClarification:
    """Verify the graph router sends clarification to 'clarify', not 'generate_sql'."""

    def test_clarification_needed_routes_to_clarify(self):
        """clarification_needed=True → 'clarify' (no SQL)."""
        state = {
            "intent": "clarification_needed",
            "clarification_needed": True,
        }
        assert _route_after_needs_clarification(state) == "clarify"

    def test_no_clarification_routes_to_sql(self):
        """clarification_needed=False, valid intent → 'generate_sql'."""
        state = {
            "intent": "filter_search",
            "clarification_needed": False,
        }
        assert _route_after_needs_clarification(state) == "generate_sql"

    def test_unsupported_routes_to_error(self):
        """unsupported intent → 'handle_error' (not SQL, not clarify)."""
        state = {
            "intent": "unsupported",
            "clarification_needed": False,
        }
        assert _route_after_needs_clarification(state) == "handle_error"


# ===================================================================
# 6. End-to-end scenario tests (no LLM, no DB)
# ===================================================================

class TestClarificationScenarios:
    """
    Test the exact scenarios from the requirements:
    - "Find me a property" → ask rent/buy + city
    - "I want something affordable" → ask budget + city + rent/buy
    """

    def test_find_me_a_property_scenario(self):
        """'Find me a property' with empty context:
        - No SQL executed (constraints empty)
        - Clarification asks about rent/buy and city
        """
        ctx, constraints, question = apply_need_clarification(
            "Find me a property", {}
        )
        # SUCCESS CRITERIA: No SQL executed (no constraints extracted)
        assert constraints == {}, "FAIL: constraints should be empty, no SQL should be generated"

        # SUCCESS CRITERIA: Clarification response returned
        assert question, "FAIL: clarification question must be returned"
        q_lower = question.lower()
        assert "rent" in q_lower or "buy" in q_lower, (
            f"FAIL: question should ask about rent/buy, got: {question}"
        )
        assert "city" in q_lower, (
            f"FAIL: question should ask about city, got: {question}"
        )

    def test_i_want_something_affordable_scenario(self):
        """'I want something affordable' with empty context:
        - No SQL executed (constraints empty)
        - Clarification asks about budget, city, rent/buy
        """
        ctx, constraints, question = apply_need_clarification(
            "I want something affordable", {}
        )
        # SUCCESS CRITERIA: No SQL executed
        assert constraints == {}, "FAIL: constraints should be empty, no SQL should be generated"

        # SUCCESS CRITERIA: Clarification response returned
        assert question, "FAIL: clarification question must be returned"
        q_lower = question.lower()
        assert "budget" in q_lower, (
            f"FAIL: question should ask about budget, got: {question}"
        )

    @pytest.mark.asyncio
    async def test_full_gate_find_property(self):
        """Full pipeline gate test: 'Find me a property'
        → extract_constraints short-circuits
        → needs_clarification confirms
        → router sends to 'clarify' (NOT 'generate_sql')
        """
        # Step 1: extract_constraints_node with need_clarification action
        state = {
            "user_message": "Find me a property",
            "conversation_action": "need_clarification",
            "search_context": {},
            "constraints": {},
            "intent": "clarification_needed",
        }
        config = {"configurable": {}}

        ec_result = await extract_constraints_node(state, config)
        assert ec_result["clarification_needed"] is True
        assert ec_result["constraints"] == {}

        # Step 2: needs_clarification_node receives the gated state
        state_after_ec = {**state, **ec_result}
        nc_result = await needs_clarification_node(state_after_ec, config)
        assert nc_result["clarification_needed"] is True

        # Step 3: Router must send to 'clarify', NOT 'generate_sql'
        routing_state = {**state_after_ec, **nc_result}
        route = _route_after_needs_clarification(routing_state)
        assert route == "clarify", f"FAIL: expected 'clarify', got '{route}' — SQL would be generated!"

    @pytest.mark.asyncio
    async def test_full_gate_affordable(self):
        """Full pipeline gate test: 'I want something affordable'"""
        state = {
            "user_message": "I want something affordable",
            "conversation_action": "need_clarification",
            "search_context": {},
            "constraints": {},
            "intent": "clarification_needed",
        }
        config = {"configurable": {}}

        ec_result = await extract_constraints_node(state, config)
        assert ec_result["clarification_needed"] is True
        assert ec_result["constraints"] == {}

        state_after_ec = {**state, **ec_result}
        nc_result = await needs_clarification_node(state_after_ec, config)
        assert nc_result["clarification_needed"] is True

        routing_state = {**state_after_ec, **nc_result}
        route = _route_after_needs_clarification(routing_state)
        assert route == "clarify"


# ===================================================================
# 7. Negative tests — ensure we DON'T block valid queries
# ===================================================================

class TestClarificationDoesNotBlockValidQueries:
    """Ensure the clarification gate does NOT fire for specific queries."""

    @pytest.mark.asyncio
    async def test_specific_query_not_blocked(self):
        """'3 bedroom houses in Paris to buy under 400k' should NOT trigger
        the clarification gate (conversation_action would be 'refine_search')."""
        state = {
            "user_message": "3 bedroom houses in Paris to buy under 400k",
            "conversation_action": "refine_search",
            "search_context": {},
            "constraints": {},
            "intent": "filter_search",
        }
        # If this were need_clarification, it would short-circuit.
        # Since it's refine_search, extract_constraints should proceed
        # to the default path and try to access the LLM (which we haven't
        # provided), proving the gate is NOT firing.
        config = {"configurable": {}}
        with pytest.raises(KeyError):
            await extract_constraints_node(state, config)

    @pytest.mark.asyncio
    async def test_modify_search_not_blocked(self):
        """modify_search action goes through its dedicated node, not clarification."""
        from app.agents.free_chat.graph import _route_after_classify_action
        from app.agents.free_chat.nodes.modify_search_context import modify_search_context_node

        # Verify routing sends modify_search to the dedicated node
        state = {
            "user_message": "Actually, show me Berlin instead",
            "conversation_action": "modify_search",
            "search_context": {"city": "London", "intent": "rent"},
            "constraints": {},
        }
        assert _route_after_classify_action(state) == "modify_search_context"

        # Verify the dedicated node works correctly
        config = {"configurable": {}}
        result = await modify_search_context_node(state, config)
        assert "clarification_needed" not in result
        assert result["search_context"]["city"] == "Berlin"

