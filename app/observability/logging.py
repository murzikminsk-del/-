import structlog

from app.observability.pii import redact_pii  # добавлено


def _redact_event_processor(logger, method_name, event_dict):
    """structlog processor: маскирует PII в текстовых полях лога.

    Критерий самопроверки задания: маскер должен работать на исходящих
    логах ответов LLM, а не только на входах.
    """
    for key, value in event_dict.items():
        if isinstance(value, str):
            event_dict[key] = redact_pii(value)
    return event_dict


def setup_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_event_processor,  # добавлено — до JSONRenderer
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )