 # выполнение tools в Python

import json
from pathlib import Path


DATA_PATH = Path(__file__).parents[2] / "data" / "documents.json"


# Функция читает data/documents.json,
# превращает JSON-текст в список словарей и возвращает его.
def load_documents() -> list[dict]:
    text = DATA_PATH.read_text(encoding="utf-8")
    return json.loads(text)


def extract_key_fields(document_id: str) -> dict:
    documents = load_documents()

    for document in documents:
        if document["document_id"] == document_id:
            return {
                "document_id": document["document_id"],
                "title": document["title"],
                "date": document["date"],
                "parties": document["parties"],
                "amount": document["amount"],
                "risks": document["risks"],
            }

    return {"error": f"Документ с document_id={document_id} не найден."}


def search_documents(query: str, department: str, doc_type: str) -> dict:
    documents = load_documents()
    query_lower = query.lower()

    results = []

    for document in documents:
        title = document["title"].lower()
        summary = document["summary"].lower()

        matches_query = query_lower in title or query_lower in summary
        matches_department = department == "any" or document["department"] == department
        matches_doc_type = doc_type == "any" or document["doc_type"] == doc_type

        if matches_query and matches_department and matches_doc_type:
            results.append(
                {
                    "document_id": document["document_id"],
                    "title": document["title"],
                    "department": document["department"],
                    "doc_type": document["doc_type"],
                    "summary": document["summary"],
                }
            )

    return {
        "query": query,
        "department": department,
        "doc_type": doc_type,
        "results": results,
    }


def call_tool(name: str, arguments: dict) -> dict:
    if name == "extract_key_fields":
        return extract_key_fields(**arguments)

    if name == "search_documents":
        return search_documents(**arguments)

    return {"error": f"Неизвестный инструмент {name}."}