from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.services.rag import RAGService

router = APIRouter(prefix="/rag", tags=["rag"])


def get_rag(request: Request) -> RAGService:
    return request.app.state.rag


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    answer: str
    top_score: float
    sources: list[dict]


@router.post("/query", response_model=QueryResponse)
async def rag_query(body: QueryRequest, rag: RAGService = Depends(get_rag)) -> QueryResponse:
    result = await rag.answer(body.question)
    return QueryResponse(**result)