"""Chat service — orchestrates the deterministic real-estate agent and persistence."""

import uuid
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.agents.free_chat.graph import free_chat_graph
from app.domain.chat.repository import ChatRepository
from app.domain.chat.schemas import ChatResponse, PropertyResult, SessionMemory
from app.infrastructure.llm.base import LLMProvider


class ChatService:
    def __init__(self, session: AsyncSession, engine: AsyncEngine, llm: LLMProvider) -> None:
        self._session = session
        self._engine = engine
        self._llm = llm
        self._repo = ChatRepository(session)

    async def list_sessions(self, user_id: str):
        return await self._repo.list_sessions(user_id)

    async def list_messages(self, session_id: str, user_id: str):
        if not await self._repo.get_session(session_id, user_id):
            raise PermissionError("Chat session does not belong to the authenticated user")
        return await self._repo.get_recent_messages(session_id, user_id, limit=200)

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        return await self._repo.delete_session(session_id, user_id)

    async def process_message(self, session_id: str | None, user_id: str, user_message: str) -> ChatResponse:
        if not session_id:
            session_id = str(uuid.uuid4())
            await self._repo.create_session(session_id, user_id)
        elif not await self._repo.get_session(session_id, user_id):
            raise PermissionError("Chat session does not belong to the authenticated user")

        memory = await self._repo.get_session_memory(session_id, user_id)

        # Recent dialogue (prior turns only) so the agent can converse naturally.
        try:
            prior = await self._repo.get_recent_messages(session_id, user_id, limit=8)
            history = [{"role": m.role, "content": m.content} for m in prior]
        except Exception:
            history = []
        initial_state = {
            "session_id": session_id,
            "user_id": user_id,
            "user_message": user_message,
            "history": history,
            "memory": memory.model_dump(),
            "search_context": {},
            "active_search": {},
            "constraints": {},
            "retry_count": 0,
            "sql_valid": False,
            "sql_error": "",
            "properties": [],
            "result_count": 0,
            "query_results": [],
        }

        config = {"configurable": {"llm": self._llm, "db_engine": self._engine}}
        final_state = await free_chat_graph.ainvoke(initial_state, config=config)

        await self._repo.add_message(session_id, user_id, "user", user_message)
        await self._repo.add_message(
            session_id, user_id, "assistant", final_state.get("assistant_message", ""),
            intent=final_state.get("intent"),
            generated_sql=final_state.get("generated_sql"),
            result_count=final_state.get("result_count", 0),
        )

        updated_memory = final_state.get("memory") or memory.model_dump()
        await self._repo.update_session_memory(session_id, user_id, SessionMemory(**updated_memory))

        properties = []
        currency_map = {"london": "GBP", "paris": "EUR", "berlin": "EUR", "amsterdam": "EUR", "rome": "EUR"}
        for raw in final_state.get("properties", []):
            try:
                item = dict(raw)
                item["property_url"] = f"/properties/{item['id']}"
                item["currency"] = currency_map.get(str(item.get("city", "")).lower(), "USD")
                properties.append(PropertyResult(**item))
            except Exception:
                continue

        active = final_state.get("active_search") or {}
        more_results_url = self._build_more_results_url(active) if final_state.get("result_count", 0) > 5 else None

        return ChatResponse(
            session_id=session_id,
            user_message=user_message,
            assistant_message=final_state.get("assistant_message", ""),
            intent=final_state.get("intent"),
            generated_sql=final_state.get("generated_sql"),
            properties=properties,
            clarification_needed=final_state.get("clarification_needed", False),
            clarification_question=final_state.get("clarification_question"),
            result_count=final_state.get("result_count", 0),
            error_message=final_state.get("error_message"),
            fallback_applied=final_state.get("fallback_applied", False),
            fallback_message=final_state.get("fallback_message"),
            more_results_url=more_results_url,
        )

    @staticmethod
    def _build_more_results_url(active: dict) -> str | None:
        keys = ["city", "neighbourhood", "property_type", "rent_or_buy", "bedrooms", "bathrooms", "min_budget", "budget", "radius_km"]
        mapping = {"rent_or_buy": "intent", "min_budget": "min_price", "budget": "max_price"}
        params = {(mapping.get(k, k)): active[k] for k in keys if active.get(k) is not None}
        return f"/properties?{urlencode(params)}&limit=50&offset=0" if params else "/properties?limit=50&offset=0"
