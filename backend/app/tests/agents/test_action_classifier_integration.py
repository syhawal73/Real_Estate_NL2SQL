"""Integration tests for the action classifier in the agent graph.

Validates that:
1. The classify_action node runs within the graph pipeline
2. conversation_action appears in final state
3. The classifier's decision is visible in logs
4. Execution flow is unchanged — downstream nodes still behave identically

These tests use a mock LLM so they do NOT require a running model or database.
"""

import json
import logging

import pytest

from app.agents.free_chat.graph import build_graph
from app.agents.free_chat.state import AgentState
from app.conversation.action_classifier import ConversationAction
from app.infrastructure.llm.base import LLMProvider


# ---------------------------------------------------------------------------
# Deterministic mock LLM
# ---------------------------------------------------------------------------

class _MockLLM(LLMProvider):
    """Returns canned responses to drive the graph deterministically.

    Intent classification  → filter_search
    Constraint extraction  → {"city": "London"}
    SQL generation         → SELECT * FROM properties LIMIT 5
    Summarisation          → "Here are your results."
    Action classification  → configurable via constructor
    """

    def __init__(self, action: str = "refine_search") -> None:
        self._action = action
        self._call_count = 0

    async def invoke(self, messages, **kwargs) -> str:
        self._call_count += 1
        system = messages[0]["content"] if messages else ""

        # Action classifier
        if "conversation classifier" in system.lower():
            return json.dumps({"action": self._action})

        # Intent classifier
        if "query classifier" in system.lower():
            return json.dumps({"intent": "filter_search"})

        # Constraint extractor
        if "parameter extractor" in system.lower():
            return json.dumps({"city": "London"})

        # SQL generator
        if "postgresql expert" in system.lower():
            return "SELECT * FROM properties WHERE city = 'London' LIMIT 5"

        # Clarification
        if "clarification" in system.lower():
            return "Which city are you interested in?"

        # Summariser
        return "Here are some properties in London."

    async def invoke_json(self, messages, **kwargs) -> dict:
        raw = await self.invoke(messages, **kwargs)
        return json.loads(raw)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _initial_state(
    user_message: str,
    memory: dict | None = None,
) -> AgentState:
    """Build a standard initial state matching ChatService.process_message."""
    return {
        "session_id": "test-integration",
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


# ---------------------------------------------------------------------------
# Tests: action appears in final state
# ---------------------------------------------------------------------------

class TestClassifyActionInGraph:
    """Verify the classify_action node is wired in and its output is in state."""

    @pytest.mark.asyncio
    async def test_conversation_action_present_in_state(self):
        """The final state must contain conversation_action."""
        graph = build_graph()
        llm = _MockLLM(action="refine_search")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        state = _initial_state("Only apartments")
        result = await graph.ainvoke(state, config=config)

        assert "conversation_action" in result
        assert result["conversation_action"] == "refine_search"

    @pytest.mark.asyncio
    async def test_refine_search_action(self):
        graph = build_graph()
        llm = _MockLLM(action="refine_search")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        result = await graph.ainvoke(
            _initial_state("Only 2 bedrooms"), config=config,
        )
        assert result["conversation_action"] == ConversationAction.REFINE_SEARCH.value

    @pytest.mark.asyncio
    async def test_modify_search_action(self):
        graph = build_graph()
        llm = _MockLLM(action="modify_search")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        result = await graph.ainvoke(
            _initial_state("Switch to Berlin"), config=config,
        )
        assert result["conversation_action"] == ConversationAction.MODIFY_SEARCH.value

    @pytest.mark.asyncio
    async def test_new_search_action(self):
        graph = build_graph()
        llm = _MockLLM(action="new_search")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        result = await graph.ainvoke(
            _initial_state("Properties with modern in title"), config=config,
        )
        assert result["conversation_action"] == ConversationAction.NEW_SEARCH.value

    @pytest.mark.asyncio
    async def test_general_chat_action(self):
        graph = build_graph()
        llm = _MockLLM(action="general_chat")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        result = await graph.ainvoke(
            _initial_state("Tell me about Berlin neighborhoods"), config=config,
        )
        assert result["conversation_action"] == ConversationAction.GENERAL_CHAT.value

    @pytest.mark.asyncio
    async def test_need_clarification_action(self):
        graph = build_graph()
        llm = _MockLLM(action="need_clarification")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        result = await graph.ainvoke(
            _initial_state("Find me a property"), config=config,
        )
        assert result["conversation_action"] == ConversationAction.NEED_CLARIFICATION.value


# ---------------------------------------------------------------------------
# Tests: logging output
# ---------------------------------------------------------------------------

class TestClassifyActionLogging:
    """Verify the node produces the expected log records."""

    @pytest.mark.asyncio
    async def test_log_contains_action_and_message(self, caplog):
        """The structured log line must contain user_message, action,
        and current_context."""
        graph = build_graph()
        llm = _MockLLM(action="refine_search")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        with caplog.at_level(logging.INFO, logger="app.agents.free_chat.nodes.classify_action"):
            await graph.ainvoke(
                _initial_state("Only apartments"), config=config,
            )

        # Find the log record from our node
        action_logs = [
            r for r in caplog.records
            if "conversation_action" in r.message
        ]
        assert len(action_logs) >= 1, "Expected at least one conversation_action log record"

        log_msg = action_logs[0].message
        assert "Only apartments" in log_msg
        assert "refine_search" in log_msg
        assert "current_context=" in log_msg

    @pytest.mark.asyncio
    async def test_log_with_existing_context(self, caplog):
        """When a search context exists, it should appear in the log."""
        graph = build_graph()
        llm = _MockLLM(action="modify_search")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        memory = {
            "search_context": {
                "city": "London",
                "intent": "rent",
            },
        }

        with caplog.at_level(logging.INFO, logger="app.agents.free_chat.nodes.classify_action"):
            await graph.ainvoke(
                _initial_state("Switch to Berlin", memory=memory),
                config=config,
            )

        action_logs = [
            r for r in caplog.records
            if "conversation_action" in r.message
        ]
        assert len(action_logs) >= 1
        log_msg = action_logs[0].message
        assert "modify_search" in log_msg
        assert "Switch to Berlin" in log_msg


# ---------------------------------------------------------------------------
# Tests: execution flow unchanged
# ---------------------------------------------------------------------------

class TestExecutionFlowUnchanged:
    """Verify the graph still produces the same outputs as before —
    the classify_action node is purely observational."""

    @pytest.mark.asyncio
    async def test_intent_still_classified(self):
        """Intent classification must still work."""
        graph = build_graph()
        llm = _MockLLM(action="refine_search")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        result = await graph.ainvoke(
            _initial_state("Show me apartments in London"), config=config,
        )
        assert result.get("intent") == "filter_search"

    @pytest.mark.asyncio
    async def test_assistant_message_produced(self):
        """An assistant message must still be generated."""
        graph = build_graph()
        llm = _MockLLM(action="refine_search")
        config = {"configurable": {"llm": llm, "db_engine": None}}

        result = await graph.ainvoke(
            _initial_state("Apartments in Paris"), config=config,
        )
        assert result.get("assistant_message")

    @pytest.mark.asyncio
    async def test_graph_does_not_crash_on_classifier_error(self):
        """Even if the action classifier LLM call fails internally,
        the graph should still complete — NEED_CLARIFICATION fallback."""

        class _FailingActionLLM(_MockLLM):
            """Fails only on the action classifier prompt."""

            async def invoke(self, messages, **kwargs) -> str:
                system = messages[0]["content"] if messages else ""
                if "conversation classifier" in system.lower():
                    raise RuntimeError("Simulated failure")
                return await super().invoke(messages, **kwargs)

            async def invoke_json(self, messages, **kwargs) -> dict:
                system = messages[0]["content"] if messages else ""
                if "conversation classifier" in system.lower():
                    raise RuntimeError("Simulated failure")
                return await super().invoke_json(messages, **kwargs)

        graph = build_graph()
        config = {"configurable": {"llm": _FailingActionLLM(), "db_engine": None}}

        result = await graph.ainvoke(
            _initial_state("Show me houses"), config=config,
        )
        # Graph must complete without crashing
        assert result.get("assistant_message")
        # Fallback action should be need_clarification
        assert result["conversation_action"] == ConversationAction.NEED_CLARIFICATION.value
