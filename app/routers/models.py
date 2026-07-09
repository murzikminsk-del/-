# Future model endpoints: /models.
# Смысл: здесь позже можно будет отдавать список доступных моделей и провайдеров.


from fastapi import APIRouter

router = APIRouter()

@router.get("/models")
async def models():
    return [
    {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini"},
    {"id": "gpt-4o", "name": "GPT-4o"},
]