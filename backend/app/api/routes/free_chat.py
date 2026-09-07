"""Real-estate conversational search endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.dependencies import get_current_user
from app.domain.auth.models import User
from app.domain.chat.schemas import ChatRequest, ChatResponse, ChatSessionSchema, ChatMessageSchema
from app.domain.chat.service import ChatService
from app.infrastructure.database.connection import engine
from app.infrastructure.database.session import get_db
from app.infrastructure.llm.factory import get_llm_provider

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_chat_service(session: AsyncSession = Depends(get_db)) -> ChatService:
    return ChatService(session=session, engine=engine, llm=get_llm_provider())


@router.post("", response_model=ChatResponse, summary="Real-estate conversational assistant")
async def free_chat(request: ChatRequest, user: User = Depends(get_current_user), service: ChatService = Depends(_get_chat_service)) -> ChatResponse:
    try:
        return await service.process_message(session_id=request.session_id, user_id=user.id, user_message=request.message)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/sessions", response_model=list[ChatSessionSchema])
async def list_chat_sessions(user: User = Depends(get_current_user), service: ChatService = Depends(_get_chat_service)):
    return await service.list_sessions(user.id)

@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageSchema])
async def list_chat_messages(session_id: str, user: User = Depends(get_current_user), service: ChatService = Depends(_get_chat_service)):
    return await service.list_messages(session_id, user.id)

@router.delete("/sessions/{session_id}")
async def delete_chat_session(session_id: str, user: User = Depends(get_current_user), service: ChatService = Depends(_get_chat_service)):
    ok = await service.delete_session(session_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"deleted": True}
