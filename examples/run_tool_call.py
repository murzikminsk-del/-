from app.llm.client import ask_assistant


test_queries = [
    "Найди договор с Альфой и извлеки из него ключевые поля.",
    "Объясни простыми словами, что такое RAG.",
    "Есть ли у нас документы про персональные данные?",
]


for index, query in enumerate(test_queries, start=1):
    print(f"\n--- Запрос {index} ---")
    print(query)

    answer = ask_assistant(query)

    print("\nОтвет:")
    print(answer)