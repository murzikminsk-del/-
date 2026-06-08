# описание tools для LLM

from app.prompts.loader import render_prompt


# Читаем описания инструментов из файлов-промптов.
EXTRACT_KEY_FIELDS_DESCRIPTION = render_prompt("tools/extract_key_fields.md")
SEARCH_DOCUMENTS_DESCRIPTION = render_prompt("tools/search_documents.md")


EXTRACT_KEY_FIELDS_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_key_fields",
        "description": EXTRACT_KEY_FIELDS_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Уникальный идентификатор документа, например contract_001.",
                }
            },
            "required": ["document_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


SEARCH_DOCUMENTS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": SEARCH_DOCUMENTS_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос пользователя.",
                },
                "department": {
                    "type": "string",
                    "description": "Отдел, к которому относятся документы. Если отдел не ясен, используй any.",
                    "enum": ["any", "legal", "hr", "finance", "it"],
                },
                "doc_type": {
                    "type": "string",
                    "description": "Тип документа. Если тип документа не ясен, используй any.",
                    "enum": ["any", "contract", "policy", "claim", "report"],
                },
            },
            "required": ["query", "department", "doc_type"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}


TOOLS = [
    EXTRACT_KEY_FIELDS_TOOL,
    SEARCH_DOCUMENTS_TOOL,
]