"""Repository for chat sessions and messages with user scoping."""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chat.models import ChatMessage, ChatSession
from app.domain.chat.schemas import ChatMessageSchema, ChatSessionSchema, SessionMemory


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_session(self, session_id: str, user_id: str) -> ChatSessionSchema | None:
        stmt = select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return ChatSessionSchema.model_validate(row) if row else None

    async def create_session(self, session_id: str, user_id: str) -> ChatSessionSchema:
        session = ChatSession(session_id=session_id, user_id=user_id, memory={})
        self._session.add(session)
        await self._session.flush()
        return ChatSessionSchema.model_validate(session)

    async def update_session_memory(self, session_id: str, user_id: str, memory: SessionMemory) -> None:
        stmt = select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            row.memory = memory.model_dump(exclude_none=False)
            row.last_active = datetime.now(timezone.utc)
            await self._session.flush()

    async def get_session_memory(self, session_id: str, user_id: str) -> SessionMemory:
        stmt = select(ChatSession).where(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row and row.memory:
            return SessionMemory(**row.memory)
        return SessionMemory()

    async def add_message(
        self, session_id: str, user_id: str, role: str, content: str,
        intent: str | None = None, generated_sql: str | None = None,
        result_count: int | None = None,
    ) -> ChatMessageSchema:
        session_check = await self.get_session(session_id, user_id)
        if not session_check:
            raise ValueError("Chat session does not belong to user")
        msg = ChatMessage(session_id=session_id, role=role, content=content,
                          intent=intent, generated_sql=generated_sql, result_count=result_count)
        self._session.add(msg)
        await self._session.flush()
        return ChatMessageSchema.model_validate(msg)

    async def get_recent_messages(self, session_id: str, user_id: str, limit: int = 10) -> list[ChatMessageSchema]:
        stmt = (
            select(ChatMessage)
            .join(ChatSession, ChatSession.session_id == ChatMessage.session_id)
            .where(ChatMessage.session_id == session_id, ChatSession.user_id == user_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [ChatMessageSchema.model_validate(r) for r in reversed(rows)]


    async def list_sessions(self, user_id: str, limit: int = 50) -> list[ChatSessionSchema]:
        stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.last_active.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return [ChatSessionSchema.model_validate(row) for row in result.scalars().all()]

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        result = await self._session.execute(delete(ChatSession).where(ChatSession.session_id == session_id, ChatSession.user_id == user_id))
        await self._session.flush()
        return bool(result.rowcount)
