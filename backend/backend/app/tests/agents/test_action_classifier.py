"""Unit tests for conversation action classifier.

Tests cover:
- LLM-based classification via a mock LLMProvider
- Text-fallback parsing (``_parse_action_from_text``)
- All eight required test cases from the specification

These tests do NOT require a database or running LLM.
"""

import json
from unittest.mock import AsyncMock

import pytest

from app.conversation.action_classifier import (
    ConversationAction,
    _parse_action_from_text,
    determine_action,
)
from app.infrastructure.llm.base import LLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockLLM(LLMProvider):
    """Deterministic mock that returns a pre-configured action JSON."""

    def __init__(self, action: str) -> None:
        self._action = action

    async def invoke(self, messages, **kwargs) -> str:
        return json.dumps({"action": self._action})

    async def invoke_json(self, messages, **kwargs) -> dict:
        return {"action": self._action}


def _context_with_city_rent() -> dict:
    """Simulates an active search: renting in London."""
    return {
        "city": "London",
        "intent": "rent",
        "property_type": None,
        "bedrooms": None,
        "max_price": None,
        "radius_km": None,
        "sort_by": None,
        "sort_order": None,
        "limit": None,
    }


def _context_with_city_buy() -> dict:
    """Simulates an active search: buying in London."""
    return {
        "city": "London",
        "intent": "buy",
        "property_type": None,
        "bedrooms": None,
        "max_price": None,
        "radius_km": None,
        "sort_by": None,
        "sort_order": None,
        "limit": None,
    }


# ---------------------------------------------------------------------------
# 1. Required specification test cases (LLM-powered)
# ---------------------------------------------------------------------------

class TestDetermineActionSpecification:
    """The eight required test scenarios from the task spec.

    Each test uses a mock LLM that returns the expected action so we
    validate the end-to-end wiring without a real model.
    """

    @pytest.mark.asyncio
    async def test_only_apartments_is_refine(self):
        """'Only apartments' => REFINE_SEARCH"""
        llm = _MockLLM("refine_search")
        result = await determine_action(
            "Only apartments", _context_with_city_rent(), llm=llm,
        )
        assert result == ConversationAction.REFINE_SEARCH

    @pytest.mark.asyncio
    async def test_only_2_bedrooms_is_refine(self):
        """'Only 2 bedrooms' => REFINE_SEARCH"""
        llm = _MockLLM("refine_search")
        result = await determine_action(
            "Only 2 bedrooms", _context_with_city_rent(), llm=llm,
        )
        assert result == ConversationAction.REFINE_SEARCH

    @pytest.mark.asyncio
    async def test_switch_to_berlin_is_modify(self):
        """'Switch to Berlin' => MODIFY_SEARCH"""
        llm = _MockLLM("modify_search")
        result = await determine_action(
            "Switch to Berlin", _context_with_city_rent(), llm=llm,
        )
        assert result == ConversationAction.MODIFY_SEARCH

    @pytest.mark.asyncio
    async def test_now_i_want_to_buy_is_modify(self):
        """'Now I want to buy' => MODIFY_SEARCH"""
        llm = _MockLLM("modify_search")
        result = await determine_action(
            "Now I want to buy", _context_with_city_rent(), llm=llm,
        )
        assert result == ConversationAction.MODIFY_SEARCH

    @pytest.mark.asyncio
    async def test_properties_with_modern_in_title_is_new_search(self):
        """'Properties with modern in title' => NEW_SEARCH"""
        llm = _MockLLM("new_search")
        result = await determine_action(
            "Properties with modern in title", None, llm=llm,
        )
        assert result == ConversationAction.NEW_SEARCH

    @pytest.mark.asyncio
    async def test_find_me_a_property_is_need_clarification(self):
        """'Find me a property' => NEED_CLARIFICATION"""
        llm = _MockLLM("need_clarification")
        result = await determine_action(
            "Find me a property", None, llm=llm,
        )
        assert result == ConversationAction.NEED_CLARIFICATION

    @pytest.mark.asyncio
    async def test_something_affordable_is_need_clarification(self):
        """'I want something affordable' => NEED_CLARIFICATION"""
        llm = _MockLLM("need_clarification")
        result = await determine_action(
            "I want something affordable", None, llm=llm,
        )
        assert result == ConversationAction.NEED_CLARIFICATION

    @pytest.mark.asyncio
    async def test_berlin_neighbourhoods_is_general_chat(self):
        """'Tell me about Berlin neighborhoods' => GENERAL_CHAT"""
        llm = _MockLLM("general_chat")
        result = await determine_action(
            "Tell me about Berlin neighborhoods", None, llm=llm,
        )
        assert result == ConversationAction.GENERAL_CHAT


# ---------------------------------------------------------------------------
# 2. Text-fallback parsing (no LLM involved)
# ---------------------------------------------------------------------------

class TestParseActionFromText:
    """Validate the robust fallback parser independently."""

    def test_valid_json(self):
        assert _parse_action_from_text('{"action": "refine_search"}') == ConversationAction.REFINE_SEARCH

    def test_valid_json_whitespace(self):
        assert _parse_action_from_text('  {"action": "modify_search"}  ') == ConversationAction.MODIFY_SEARCH

    def test_json_embedded_in_prose(self):
        text = 'Based on analysis, {"action": "new_search"} is the result.'
        assert _parse_action_from_text(text) == ConversationAction.NEW_SEARCH

    def test_plain_label(self):
        assert _parse_action_from_text("general_chat") == ConversationAction.GENERAL_CHAT

    def test_plain_label_with_period(self):
        assert _parse_action_from_text("need_clarification.") == ConversationAction.NEED_CLARIFICATION

    def test_plain_label_with_whitespace(self):
        assert _parse_action_from_text("  refine_search  ") == ConversationAction.REFINE_SEARCH

    def test_label_in_sentence(self):
        assert _parse_action_from_text("This is a modify_search request") == ConversationAction.MODIFY_SEARCH

    def test_all_valid_actions_from_json(self):
        for action in ConversationAction:
            result = _parse_action_from_text(f'{{"action": "{action.value}"}}')
            assert result == action, f"Failed for {action.value}"

    def test_invalid_text_returns_need_clarification(self):
        assert _parse_action_from_text("gibberish xyz 12345") == ConversationAction.NEED_CLARIFICATION

    def test_empty_returns_need_clarification(self):
        assert _parse_action_from_text("") == ConversationAction.NEED_CLARIFICATION

    def test_wrong_json_key(self):
        assert _parse_action_from_text('{"intent": "filter_search"}') == ConversationAction.NEED_CLARIFICATION


# ---------------------------------------------------------------------------
# 3. Edge cases for determine_action
# ---------------------------------------------------------------------------

class TestDetermineActionEdgeCases:
    """Edge cases: LLM failures, None context, etc."""

    @pytest.mark.asyncio
    async def test_none_context_handled(self):
        """None context should not crash."""
        llm = _MockLLM("new_search")
        result = await determine_action("Search for houses", None, llm=llm)
        assert result == ConversationAction.NEW_SEARCH

    @pytest.mark.asyncio
    async def test_empty_context_handled(self):
        """Empty dict context should not crash."""
        llm = _MockLLM("need_clarification")
        result = await determine_action("Help me", {}, llm=llm)
        assert result == ConversationAction.NEED_CLARIFICATION

    @pytest.mark.asyncio
    async def test_llm_json_failure_falls_back_to_invoke(self):
        """When invoke_json raises, fall back to invoke (plain text)."""

        class _FailJsonLLM(LLMProvider):
            async def invoke(self, messages, **kwargs) -> str:
                return '{"action": "general_chat"}'

            async def invoke_json(self, messages, **kwargs) -> dict:
                raise ValueError("Simulated JSON failure")

        result = await determine_action(
            "Tell me about Paris", None, llm=_FailJsonLLM(),
        )
        assert result == ConversationAction.GENERAL_CHAT

    @pytest.mark.asyncio
    async def test_both_llm_methods_fail_returns_need_clarification(self):
        """When both invoke_json AND invoke raise, return NEED_CLARIFICATION."""

        class _FullyBrokenLLM(LLMProvider):
            async def invoke(self, messages, **kwargs) -> str:
                raise RuntimeError("Simulated total failure")

            async def invoke_json(self, messages, **kwargs) -> dict:
                raise RuntimeError("Simulated total failure")

        result = await determine_action(
            "Some message", None, llm=_FullyBrokenLLM(),
        )
        assert result == ConversationAction.NEED_CLARIFICATION


# ---------------------------------------------------------------------------
# 4. Enum completeness
# ---------------------------------------------------------------------------

class TestConversationActionEnum:
    """Ensure the enum has exactly the five required members."""

    def test_has_five_members(self):
        assert len(ConversationAction) == 5

    def test_member_names(self):
        expected = {
            "REFINE_SEARCH", "MODIFY_SEARCH", "NEW_SEARCH",
            "GENERAL_CHAT", "NEED_CLARIFICATION",
        }
        assert {e.name for e in ConversationAction} == expected

    def test_values_are_lowercase(self):
        for action in ConversationAction:
            assert action.value == action.value.lower()
