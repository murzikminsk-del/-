import argparse
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings

settings = get_settings()


JUDGE_PROMPT = """Ты эксперт по оценке качества ответов ИИ-ассистента.

Вопрос: {question}
Эталонный ответ: {expected_answer}
Ответ ассистента: {answer}

Оцени ответ ассистента по трём критериям от 1 до 5.
Верни ТОЛЬКО валидный JSON в точно таком формате:
{{
  "reasoning": "твои рассуждения здесь",
  "scores": {{
    "relevance": <число 1-5>,
    "correctness": <число 1-5>,
    "completeness": <число 1-5>
  }},
  "explanation": "одна строка итога"
}}"""


async def get_assistant_answer(client: httpx.AsyncClient, question: str) -> str:
    response = await client.post(
        "http://localhost:8000/chat",
        json={
            "messages": [{"role": "user", "content": question}],
            "temperature": 0,
        },
    )
    
    return response.json()["content"]


async def judge_answer(openai: AsyncOpenAI, question: str, expected: str, answer: str, judge_model: str) -> dict:
    prompt = JUDGE_PROMPT.format(question=question, expected_answer=expected, answer=answer)
    result = await openai.chat.completions.create(
        model=judge_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(result.choices[0].message.content)


async def main(golden_path: str, judge_model: str, out_path: str):
    with open(golden_path, encoding="utf-8") as f:
        golden = json.load(f)

    openai = AsyncOpenAI(
    api_key=settings.llm.openai_api_key.get_secret_value(),
    http_client=httpx.AsyncClient(trust_env=False, verify=False),
)
    items_out = []

    async with httpx.AsyncClient(timeout=120, trust_env=False) as http:
        for item in golden["items"]:
            print(f"  {item['id']}: {item['question'][:60]}...")
            answer = await get_assistant_answer(http, item["question"])
            verdict = await judge_answer(openai, item["question"], item["expected_answer"], answer, judge_model)
            items_out.append({
                "id": item["id"],
                "question": item["question"],
                "answer": answer,
                "scores": verdict["scores"],
                "reasoning": verdict["reasoning"],
                "explanation": verdict["explanation"],
            })

    scores_all = [i["scores"]["correctness"] for i in items_out]
    run = {
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "model_under_test": settings.llm.default_model,
        "judge_model": judge_model,
        "golden_version": golden["version"],
        "items": items_out,
        "aggregates": {
            "relevance_avg": sum(i["scores"]["relevance"] for i in items_out) / len(items_out),
            "correctness_avg": sum(scores_all) / len(scores_all),
            "completeness_avg": sum(i["scores"]["completeness"] for i in items_out) / len(items_out),
            "min_correctness": min(scores_all),
        },
    }

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=2)
    print(f"\nГотово: {out_path}")
    print(f"correctness_avg = {run['aggregates']['correctness_avg']:.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", required=True)
    parser.add_argument("--judge", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    asyncio.run(main(args.golden, args.judge, args.out))