import asyncio
import time
from app.services.embeddings import embed_texts

TEXT = ["Договор может быть расторгнут в одностороннем порядке"]

async def main():
    t = time.perf_counter()
    await embed_texts(TEXT)
    print(f"Вызов: {time.perf_counter() - t:.2f}s")

asyncio.run(main())