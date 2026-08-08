import re
import logging

import structlog
from openai import AsyncOpenAI

from app.moderation.domain import ModerationResult
from app.observability.pii import redact_pii, prompt_hash

log = structlog.get_logger("moderation")

DEFAULT_BLOCKLIST: list[str] = [
    r"(?i)\b(как\s+(сделать|собрать|изготовить|купить))\s+(бомб[уы]|взрывчатк)",
]

class ModerationService:
    def __init__(
        self,
        llm_client: AsyncOpenAI,
        use_openai: bool = True,
        blocklist: list[str] | None = None,
    ):
        self.llm = llm_client
        self.use_openai = use_openai
        patterns = blocklist if blocklist is not None else DEFAULT_BLOCKLIST
        self._patterns = [re.compile(p) for p in patterns]
        
    def _log_incident(self, text: str, result: ModerationResult) -> None:
        log.warning(
            "moderation_block",
            text_hash=prompt_hash(text),
            masked_text=redact_pii(text)[:100],
            categories=result.categories,
            layer=result.layer,
        )

    async def check_input(self, text: str, owner_external_id: str | None = None) -> ModerationResult:
        if not text:
            return ModerationResult(allowed=True, layer="passed")

        # Слой 1: regex
        for pat in self._patterns:
            if pat.search(text):
                result = ModerationResult(allowed=False, categories=["custom_blocklist"], layer="regex")
                self._log_incident(text, result)
                return result

        # Слой 2: OpenAI (fail-open)
        if self.use_openai:
            try:
                resp = await self.llm.moderations.create(
                    model="omni-moderation-latest", input=text
                )
                r = resp.results[0]
                if r.flagged:
                    flagged = [c for c, on in r.categories.model_dump().items() if on]
                    result = ModerationResult(allowed=False, categories=flagged, layer="openai")
                    self._log_incident(text, result)
                    return result
            except Exception as exc:
                log.warning("moderation_api_failed", error=str(exc))

        return ModerationResult(allowed=True, layer="passed")        