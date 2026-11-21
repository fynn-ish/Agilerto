from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import config
from ..db import get_db
from ..rag import llm
from ..rag.pipeline import answer_question

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=config.QUESTION_MAX_CHARS)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


@router.post("/chat")
def chat(req: ChatRequest, db=Depends(get_db)):
    """Ask a question. Answers come only from saved records and always carry citations and an 'as of' time."""
    if not req.question.strip():
        raise HTTPException(422, "Question is empty")
    # look up llm.chat at call time so tests (and later changes) can replace it
    return answer_question(db, req.question, req.lat, req.lng, llm_chat=lambda msgs: llm.chat(msgs))


@router.get("/ai/status")
def ai_status():
    """Is Ollama running and is the model installed? Used for the AI badge in the chat panel."""
    return llm.status()
