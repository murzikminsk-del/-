import asyncio
import time

from app.services.llm_client import AsyncLLMClient 
from app.services.llm import ask_assistant 

PROMPTS = [f'Объясни одним абзацем сущность документа {i}' for i in range(1, 21)]

def run_sync():
    start = time.perf_counter()
    for prompt in PROMPTS:
        ask_assistant(prompt)
    duration = time.perf_counter() - start
    print(f"sync: {duration:.1f} сек")
    
    
async def run_async(concurrency: int):
    client = AsyncLLMClient(concurrency=concurrency)
    start = time.perf_counter()
    await client.batch_chat(PROMPTS)
    duration = time.perf_counter() - start
    print(f"async concurrency={concurrency}: {duration:.1f} сек")
    
async def main():
    run_sync()
    await run_async(concurrency=1)
    await run_async(concurrency=5)
    await run_async(concurrency=10)
    
asyncio.run(main())
    
    

