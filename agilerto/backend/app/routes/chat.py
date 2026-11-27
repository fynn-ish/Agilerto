from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import config
from ..db import get_db
from ..ratelimit import RateLimiter
from ..rag import guardrails as G
from ..rag import llm
from ..rag.pipeline import answer_question

router = APIRouter()
limiter = RateLimiter(config.CHAT_RATE_LIMIT, config.CHAT_RATE_WINDOW_SECONDS)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=config.QUESTION_MAX_CHARS)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


@router.post("/chat")
def chat(req: ChatRequest, request: Request, db=Depends(get_db)):
    """Ask a question. Answers come only from saved records and always carry citations and an 'as of' time."""
    if not req.question.strip():
        raise HTTPException(422, "Question is empty")
    # Too many questions from one device are slowed down, but never someone in danger or distress.
    if G.classify(req.question)[0] not in ("emergency", "distress"):
        allowed, wait = limiter.check(request.client.host if request.client else "unknown")
        if not allowed:
            raise HTTPException(429, f"Too many questions. Please wait {wait} seconds.", headers={"Retry-After": str(wait)})
    # look up llm.chat at call time so tests (and later changes) can replace it
    return answer_question(db, req.question, req.lat, req.lng, llm_chat=lambda msgs: llm.chat(msgs))


@router.get("/ai/status")
def ai_status():
    """Is Ollama running and is the model installed? Used for the AI badge in the chat panel."""
    return llm.status()
