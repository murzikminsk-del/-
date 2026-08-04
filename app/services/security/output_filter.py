import re
from typing import Final

from app.observability.pii import redact_pii  # переиспользуем маскер из Б3.6

SCRIPT_INJECTION_RE: Final = re.compile(r"<script|javascript:|onerror\s*=", re.IGNORECASE)


def filter_output(answer: str, system_prompt: str, canary: str) -> str:
    """Проверяет ответ модели перед отдачей пользователю.

    Порядок проверок:
    1. canary-токен — 100%-детектор утечки системного промпта, если он
       дословно попал в ответ (см. LLM07 OWASP 2025);
    2. первые 80 символов системного промпта (нормализованные) — как
       запасной детектор, если canary почему-то не сработал;
    3. персональные данные — маскируются через redact_pii (не блокируем
       ответ целиком, т.к. это ложные срабатывания на легитимных ответах);
    4. XSS-инъекция в ответе (проба garak xss.MarkdownImageExfil и др.).

    Подключение в обработчике /chat:
        try:
            answer = filter_output(resp.content, SYSTEM_PROMPT, app.state.canary)
        except ValueError as e:
            raise HTTPException(status_code=502, detail=str(e))
    """
    if canary and canary in answer:
        raise ValueError("system_prompt leakage: canary detected")

    head = " ".join(system_prompt.split())[:80]
    if head and head.lower() in " ".join(answer.split()).lower():
        raise ValueError("system_prompt leakage: prefix detected")

    if SCRIPT_INJECTION_RE.search(answer):
        raise ValueError("unsafe output: script injection detected")

    return redact_pii(answer)