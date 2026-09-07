"""Tests for T22 — ActiveSearchSession (canonical search object).

Covers the four required scenarios from the ticket plus a suite of
regression guards to confirm no existing behaviour changed.

Required scenarios
------------------
1. Create search             — fresh state produces a valid ActiveSearchSession.
2. Modify city               — search_id is PRESERVED; city updates.
3. Modify intent             — search_id is PRESERVED; intent updates.
4. Modify radius             — search_id is PRESERVED; radius_km updates.
5. NEW_SEARCH resets id      — reset_search_context generates a FRESH search_id.
6. active_search authoritative — active_search fields match what was extracted.

Regression guards
-----------------
R1. search_context still written — backward compat not broken.
R2. constraints dict still written — downstream SQL nodes unaffected.
R3. modify_search_context preserves non-modified fields in both objects.
R4. reset_search_context clears old fields in both objects.
R5. load_memory migrates pre-T22 sessions (no active_search in memory).
R6. load_memory restores persisted active_search from post-T22 memory.
R7. update_memory_node persists active_search into memory.
R8. bathrooms extracted and mapped to active_search.bathrooms.

All tests are pure unit tests — no running LLM or database required.
"""

import json
import pytest

from app.agents.free_chat.nodes.extract_constraints import extract_constraints_node
from app.agents.free_chat.nodes.modify_search_context import modify_search_context_node
from app.agents.free_chat.nodes.reset_search_context import reset_search_context_node
from app.agents.free_chat.nodes.load_memory import load_memory_node
from app.agents.free_chat.nodes.update_memory import update_memory_node
from app.domain.chat.schemas import ActiveSearchSession, SearchContext, SessionMemory
from app.infrastructure.llm.base import LLMProvider


# ---------------------------------------------------------------------------
# Mock LLM — returns empty extraction so regex results are deterministic
# ---------------------------------------------------------------------------

class _EmptyLLM(LLMProvider):
    """Returns empty JSON for all LLM calls — only regex path fires."""

    async def invoke(self, messages, **kwargs) -> str:
        return json.dumps({})

    async def invoke_json(self, messages, **kwargs) -> dict:
        return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CFG_EMPTY = {"configurable": {}}
_CFG_LLM = {"configurable": {"llm": _EmptyLLM()}}


def _paris_rent_context() -> dict:
    """Rich context to verify preservation / clearing behaviour."""
    return {
        "city": "Paris",
        "intent": "rent",
        "property_type": "apartment",
        "bedrooms": 2,
        "bathrooms": 1,
        "max_price": 1500.0,
        "radius_km": 10.0,
        "sort_by": "price",
        "sort_order": "asc",
        "limit": 20,
        "last_result_count": 8,
    }


def _existing_active_search(search_id: str = "FIXED-UUID-1234") -> dict:
    """Pre-existing active_search dict with a known search_id."""
    return {
        "search_id": search_id,
        "city": "Paris",
        "intent": "rent",
        "property_type": "apartment",
        "bedrooms": 2,
        "bathrooms": 1,
        "budget": 1500.0,
        "radius_km": 10.0,
    }


# ===========================================================================
# 1. Create search — extract_constraints_node
# ===========================================================================

class TestCreateSearch:
    """Scenario 1: fresh state → valid ActiveSearchSession is created."""

    @pytest.mark.asyncio
    async def test_active_search_created_from_empty_state(self):
        """Starting with no prior state produces a valid active_search."""
        state = {
            "user_message": "I want to rent in London",
            "conversation_action": "refine_search",
        }
        result = await extract_constraints_node(state, _CFG_LLM)

        assert "active_search" in result, "active_search key missing from result"
        a = result["active_search"]

        # Required schema keys present
        for key in ("search_id", "city", "intent", "property_type",
                     "bedrooms", "bathrooms", "budget", "radius_km"):
            assert key in a, f"active_search missing key: {key}"

        # search_id is a non-empty string
        assert isinstance(a["search_id"], str) and a["search_id"], \
            "search_id must be a non-empty string"

        # Extracted fields correct
        assert a["city"] == "London", f"Expected city='London', got '{a['city']}'"
        assert a["intent"] == "rent", f"Expected intent='rent', got '{a['intent']}'"

    @pytest.mark.asyncio
    async def test_active_search_budget_maps_from_max_price(self):
        """budget in active_search = max_price from SearchContext."""
        state = {
            "user_message": "apartments under 500k to buy in Berlin",
            "conversation_action": "refine_search",
        }
        result = await extract_constraints_node(state, _CFG_LLM)

        a = result["active_search"]
        ctx = result["search_context"]

        assert a["budget"] == ctx["max_price"], \
            f"budget {a['budget']} != max_price {ctx['max_price']}"

    @pytest.mark.asyncio
    async def test_active_search_search_id_is_uuid_format(self):
        """Generated search_id looks like a UUID (8-4-4-4-12 hex)."""
        import re
        state = {
            "user_message": "houses to buy in Rome",
            "conversation_action": "refine_search",
        }
        result = await extract_constraints_node(state, _CFG_LLM)
        sid = result["active_search"]["search_id"]
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        assert uuid_pattern.match(sid), f"search_id '{sid}' is not UUID-format"


# ===========================================================================
# 2. Modify city — modify_search_context_node
# ===========================================================================

class TestModifyCity:
    """Scenario 2: changing city → search_id preserved, city updated."""

    @pytest.mark.asyncio
    async def test_city_updated_search_id_preserved(self):
        """Paris → London: city changes, search_id stays the same."""
        fixed_id = "FIXED-UUID-CITY"
        state = {
            "user_message": "Switch to London",
            "conversation_action": "modify_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(fixed_id),
            "constraints": {},
        }
        result = await modify_search_context_node(state, _CFG_EMPTY)

        a = result["active_search"]
        assert a["search_id"] == fixed_id, \
            f"search_id changed! Expected '{fixed_id}', got '{a['search_id']}'"
        assert a["city"] == "London", \
            f"Expected city='London', got '{a['city']}'"

    @pytest.mark.asyncio
    async def test_non_city_fields_preserved_in_active_search(self):
        """When only city changes, intent/property_type/etc stay the same."""
        state = {
            "user_message": "Switch to Amsterdam",
            "conversation_action": "modify_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(),
            "constraints": {},
        }
        result = await modify_search_context_node(state, _CFG_EMPTY)

        a = result["active_search"]
        assert a["intent"] == "rent", "intent should be preserved"
        assert a["property_type"] == "apartment", "property_type should be preserved"
        assert a["bedrooms"] == 2, "bedrooms should be preserved"
        assert a["budget"] == 1500.0, "budget should be preserved"
        assert a["radius_km"] == 10.0, "radius_km should be preserved"


# ===========================================================================
# 3. Modify intent — modify_search_context_node
# ===========================================================================

class TestModifyIntent:
    """Scenario 3: changing intent → search_id preserved, intent updated."""

    @pytest.mark.asyncio
    async def test_intent_updated_search_id_preserved(self):
        """rent → buy: intent changes, search_id stays the same."""
        fixed_id = "FIXED-UUID-INTENT"
        state = {
            "user_message": "Actually I want to buy",
            "conversation_action": "modify_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(fixed_id),
            "constraints": {},
        }
        result = await modify_search_context_node(state, _CFG_EMPTY)

        a = result["active_search"]
        assert a["search_id"] == fixed_id, \
            f"search_id changed! Expected '{fixed_id}', got '{a['search_id']}'"
        assert a["intent"] == "buy", \
            f"Expected intent='buy', got '{a['intent']}'"

    @pytest.mark.asyncio
    async def test_intent_change_does_not_affect_city(self):
        """City stays unchanged when only intent is modified."""
        state = {
            "user_message": "Now looking to buy",
            "conversation_action": "modify_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(),
            "constraints": {},
        }
        result = await modify_search_context_node(state, _CFG_EMPTY)

        a = result["active_search"]
        assert a["city"] == "Paris", "city should be preserved when only intent changes"


# ===========================================================================
# 4. Modify radius — modify_search_context_node
# ===========================================================================

class TestModifyRadius:
    """Scenario 4: changing radius → search_id preserved, radius_km updated."""

    @pytest.mark.asyncio
    async def test_radius_updated_search_id_preserved(self):
        """10km → 25km: radius_km changes, search_id stays."""
        fixed_id = "FIXED-UUID-RADIUS"
        state = {
            "user_message": "Expand to 25km",
            "conversation_action": "modify_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(fixed_id),
            "constraints": {},
        }
        result = await modify_search_context_node(state, _CFG_EMPTY)

        a = result["active_search"]
        assert a["search_id"] == fixed_id, \
            f"search_id changed! Expected '{fixed_id}', got '{a['search_id']}'"
        assert a["radius_km"] == 25.0, \
            f"Expected radius_km=25.0, got '{a['radius_km']}'"

    @pytest.mark.asyncio
    async def test_radius_change_preserves_all_other_fields(self):
        """City/intent/budget are unchanged when only radius changes."""
        state = {
            "user_message": "within 5km",
            "conversation_action": "modify_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(),
            "constraints": {},
        }
        result = await modify_search_context_node(state, _CFG_EMPTY)

        a = result["active_search"]
        assert a["city"] == "Paris"
        assert a["intent"] == "rent"
        assert a["budget"] == 1500.0
        assert a["radius_km"] == 5.0


# ===========================================================================
# 5. NEW_SEARCH resets search_id — reset_search_context_node
# ===========================================================================

class TestNewSearchResetsId:
    """Scenario 5: NEW_SEARCH produces a fresh search_id."""

    @pytest.mark.asyncio
    async def test_new_search_id_is_different(self):
        """After NEW_SEARCH the search_id must differ from the prior one."""
        old_id = "OLD-SEARCH-ID"
        state = {
            "user_message": "Find apartments to buy in Berlin",
            "conversation_action": "new_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(old_id),
        }
        result = await reset_search_context_node(state, _CFG_LLM)

        a = result["active_search"]
        assert a["search_id"] != old_id, \
            f"search_id was NOT regenerated — still '{a['search_id']}'"

    @pytest.mark.asyncio
    async def test_new_search_clears_old_fields(self):
        """Paris/rent context is wiped; only new message fields survive."""
        state = {
            "user_message": "Find houses to buy in Berlin",
            "conversation_action": "new_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(),
        }
        result = await reset_search_context_node(state, _CFG_LLM)

        a = result["active_search"]
        # Old Paris/rent values should be gone
        assert a["city"] != "Paris", "Old city should have been cleared"
        assert a["intent"] != "rent", "Old intent should have been cleared"
        # New values present
        assert a["city"] == "Berlin", f"Expected 'Berlin', got '{a['city']}'"
        assert a["intent"] == "buy", f"Expected 'buy', got '{a['intent']}'"

    @pytest.mark.asyncio
    async def test_new_search_id_is_uuid_format(self):
        """New search_id is still a valid UUID string."""
        import re
        state = {
            "user_message": "Houses to rent in Amsterdam",
            "conversation_action": "new_search",
            "search_context": {},
            "active_search": {},
        }
        result = await reset_search_context_node(state, _CFG_LLM)

        sid = result["active_search"]["search_id"]
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        assert uuid_re.match(sid), f"New search_id '{sid}' is not UUID-format"


# ===========================================================================
# 6. active_search is authoritative — fields match extraction
# ===========================================================================

class TestActiveSearchAuthoritative:
    """Scenario 6: active_search stays in sync with what was extracted."""

    @pytest.mark.asyncio
    async def test_active_search_matches_search_context(self):
        """budget == max_price and all shared fields agree with search_context."""
        state = {
            "user_message": "3 bed apartments to rent in London under 3000k",
            "conversation_action": "refine_search",
        }
        result = await extract_constraints_node(state, _CFG_LLM)

        a = result["active_search"]
        ctx = result["search_context"]

        assert a["city"] == ctx["city"]
        assert a["intent"] == ctx["intent"]
        assert a["property_type"] == ctx["property_type"]
        assert a["bedrooms"] == ctx["bedrooms"]
        assert a["budget"] == ctx["max_price"]
        assert a["radius_km"] == ctx["radius_km"]

    @pytest.mark.asyncio
    async def test_modify_active_search_matches_context(self):
        """After modify, active_search and search_context agree on all fields."""
        state = {
            "user_message": "Switch to Berlin",
            "conversation_action": "modify_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(),
            "constraints": {},
        }
        result = await modify_search_context_node(state, _CFG_EMPTY)

        a = result["active_search"]
        ctx = result["search_context"]

        assert a["city"] == ctx["city"]
        assert a["intent"] == ctx["intent"]
        assert a["budget"] == ctx["max_price"]
        assert a["radius_km"] == ctx["radius_km"]

    @pytest.mark.asyncio
    async def test_reset_active_search_matches_context(self):
        """After new_search, active_search and search_context agree."""
        state = {
            "user_message": "houses to buy in Rome",
            "conversation_action": "new_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(),
        }
        result = await reset_search_context_node(state, _CFG_LLM)

        a = result["active_search"]
        ctx = result["search_context"]

        assert a["city"] == ctx["city"]
        assert a["intent"] == ctx["intent"]
        assert a["budget"] == ctx.get("max_price")


# ===========================================================================
# Regression guards
# ===========================================================================

class TestRegressions:
    """R-series: existing behaviour must be unchanged."""

    # R1: search_context still written
    @pytest.mark.asyncio
    async def test_R1_search_context_still_present(self):
        """search_context key is still returned (backward compat)."""
        state = {
            "user_message": "apartments to rent in London",
            "conversation_action": "refine_search",
        }
        result = await extract_constraints_node(state, _CFG_LLM)
        assert "search_context" in result, "search_context missing — backward compat broken"

    # R2: constraints dict still written
    @pytest.mark.asyncio
    async def test_R2_constraints_still_present(self):
        """constraints key is still returned for downstream SQL nodes."""
        state = {
            "user_message": "apartments to rent in London",
            "conversation_action": "refine_search",
        }
        result = await extract_constraints_node(state, _CFG_LLM)
        assert "constraints" in result, "constraints key missing"

    # R3: modify preserves non-modified fields
    @pytest.mark.asyncio
    async def test_R3_modify_preserves_non_modified_fields(self):
        """MODIFY_SEARCH only changes the explicitly mentioned field."""
        state = {
            "user_message": "Switch to Berlin",
            "conversation_action": "modify_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(),
            "constraints": {},
        }
        result = await modify_search_context_node(state, _CFG_EMPTY)
        ctx = result["search_context"]

        assert ctx["intent"] == "rent", "intent should not be cleared by city change"
        assert ctx["bedrooms"] == 2, "bedrooms should not be cleared"
        assert ctx["max_price"] == 1500.0, "max_price should not be cleared"
        assert ctx["radius_km"] == 10.0, "radius_km should not be cleared"

    # R4: reset clears old fields
    @pytest.mark.asyncio
    async def test_R4_reset_clears_old_context(self):
        """NEW_SEARCH wipes Paris/rent from search_context."""
        state = {
            "user_message": "Houses to buy in Berlin",
            "conversation_action": "new_search",
            "search_context": _paris_rent_context(),
            "active_search": _existing_active_search(),
        }
        result = await reset_search_context_node(state, _CFG_LLM)
        ctx = result["search_context"]

        assert ctx.get("city") != "Paris", "city=Paris should have been cleared"
        assert ctx.get("intent") != "rent", "intent=rent should have been cleared"

    # R5: load_memory migrates pre-T22 sessions
    @pytest.mark.asyncio
    async def test_R5_load_memory_migrates_pre_t22_session(self):
        """load_memory generates active_search even when memory has no active_search key."""
        pre_t22_memory = {
            "search_context": {
                "city": "Paris",
                "intent": "rent",
                "bedrooms": 2,
                "max_price": 1500.0,
                "radius_km": None,
                "property_type": None,
                "bathrooms": None,
                "sort_by": None,
                "sort_order": None,
                "limit": None,
                "last_result_count": None,
            }
            # NOTE: no "active_search" key — simulates pre-T22 persisted memory
        }
        state = {"memory": pre_t22_memory}
        result = await load_memory_node(state, _CFG_EMPTY)

        assert "active_search" in result, "load_memory must produce active_search"
        a = result["active_search"]
        assert a["city"] == "Paris"
        assert a["intent"] == "rent"
        assert a["budget"] == 1500.0
        assert a["search_id"], "search_id must be set"

    # R6: load_memory restores persisted active_search
    @pytest.mark.asyncio
    async def test_R6_load_memory_restores_persisted_active_search(self):
        """load_memory preserves the search_id stored in post-T22 memory."""
        persisted_id = "PERSISTED-SEARCH-ID"
        post_t22_memory = {
            "search_context": {
                "city": "London",
                "intent": "buy",
                "bedrooms": 3,
                "bathrooms": 2,
                "max_price": 400000.0,
                "radius_km": 5.0,
                "property_type": "house",
                "sort_by": None,
                "sort_order": None,
                "limit": None,
                "last_result_count": None,
            },
            "active_search": {
                "search_id": persisted_id,
                "city": "London",
                "intent": "buy",
                "property_type": "house",
                "bedrooms": 3,
                "bathrooms": 2,
                "budget": 400000.0,
                "radius_km": 5.0,
            },
        }
        state = {"memory": post_t22_memory}
        result = await load_memory_node(state, _CFG_EMPTY)

        a = result["active_search"]
        assert a["search_id"] == persisted_id, \
            f"Expected persisted_id '{persisted_id}', got '{a['search_id']}'"

    # R7: update_memory persists active_search
    @pytest.mark.asyncio
    async def test_R7_update_memory_persists_active_search(self):
        """update_memory_node stores active_search in the memory dict."""
        active = _existing_active_search("PERSIST-ME")
        state = {
            "search_context": _paris_rent_context(),
            "active_search": active,
            "memory": {},
            "result_count": 5,
            "generated_sql": "SELECT 1",
            "intent": "filter_search",
        }
        result = await update_memory_node(state, _CFG_EMPTY)

        memory_dict = result["memory"]
        assert "active_search" in memory_dict, \
            "active_search missing from persisted memory"
        assert memory_dict["active_search"]["search_id"] == "PERSIST-ME"

    # R8: bathrooms extracted and mapped
    @pytest.mark.asyncio
    async def test_R8_bathrooms_extracted_and_mapped(self):
        """bathrooms from message appears in both search_context and active_search."""
        state = {
            "user_message": "3 bed 2 bath apartments to rent in Paris",
            "conversation_action": "refine_search",
        }
        result = await extract_constraints_node(state, _CFG_LLM)

        ctx = result["search_context"]
        a = result["active_search"]

        assert ctx.get("bathrooms") == 2, \
            f"search_context.bathrooms should be 2, got {ctx.get('bathrooms')}"
        assert a.get("bathrooms") == 2, \
            f"active_search.bathrooms should be 2, got {a.get('bathrooms')}"


# ===========================================================================
# Schema unit tests (no async / no nodes needed)
# ===========================================================================

class TestActiveSearchSessionSchema:
    """Direct unit tests for the ActiveSearchSession model."""

    def test_default_search_id_is_generated(self):
        """Two instances without explicit search_id get different UUIDs."""
        a1 = ActiveSearchSession()
        a2 = ActiveSearchSession()
        assert a1.search_id != a2.search_id, "Each instance must get a unique search_id"

    def test_from_search_context_maps_budget(self):
        """max_price → budget mapping is correct."""
        ctx = SearchContext(max_price=250000.0)
        a = ActiveSearchSession.from_search_context(ctx)
        assert a.budget == 250000.0

    def test_from_search_context_preserves_search_id(self):
        """Passing an explicit search_id keeps it unchanged."""
        ctx = SearchContext(city="Rome")
        a = ActiveSearchSession.from_search_context(ctx, search_id="KEEP-ME")
        assert a.search_id == "KEEP-ME"

    def test_from_search_context_new_id_when_none(self):
        """Passing None generates a fresh UUID."""
        ctx = SearchContext(city="Amsterdam")
        a = ActiveSearchSession.from_search_context(ctx, search_id=None)
        assert a.search_id and a.search_id != "None"

    def test_all_fields_nullable(self):
        """ActiveSearchSession can be created with all Nones (empty search)."""
        a = ActiveSearchSession(search_id="test")
        assert a.city is None
        assert a.intent is None
        assert a.property_type is None
        assert a.bedrooms is None
        assert a.bathrooms is None
        assert a.budget is None
        assert a.radius_km is None

    def test_session_memory_persists_active_search(self):
        """SessionMemory now stores active_search field."""
        ctx = SearchContext(city="Berlin")
        a = ActiveSearchSession.from_search_context(ctx)
        m = SessionMemory(search_context=ctx, active_search=a.model_dump())
        dumped = m.model_dump()
        assert "active_search" in dumped
        assert dumped["active_search"]["city"] == "Berlin"
