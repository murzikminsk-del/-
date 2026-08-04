"""
Извлекает примеры успешных атак (пробитий) из JSONL-отчёта garak.

Использование:
    uv run python extract_hits.py <путь_к_report.jsonl> [--limit N]

Критерий пробития (см. задание Б3.8):
    entry_type == "attempt", status == 2, detector_results[<любой>][0] >= 0.5
"""
import json
import sys
import argparse


def extract_text(value):
    """Достаёт текст из prompt/output, независимо от формата (строка, dict с turns, list)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # частые варианты структуры: {"text": "..."} или {"turns": [{"content": {"text": "..."}}]}
        if "text" in value:
            return extract_text(value["text"])
        if "turns" in value:
            parts = [extract_text(t) for t in value["turns"]]
            return " ".join(p for p in parts if p)
        if "content" in value:
            return extract_text(value["content"])
        # fallback — просто сериализуем
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts = [extract_text(v) for v in value]
        return " ".join(p for p in parts if p)
    return str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report_path")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--probe", type=str, default=None, help="фильтр по подстроке в имени пробы")
    args = parser.parse_args()

    hits = []
    with open(args.report_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("entry_type") != "attempt":
                continue
            if entry.get("status") != 2:
                continue

            detector_results = entry.get("detector_results", {})
            hit_detectors = []
            for det_name, scores in detector_results.items():
                numeric_scores = [s for s in (scores or []) if s is not None]
                if numeric_scores and max(numeric_scores) >= 0.5:
                    hit_detectors.append((det_name, max(numeric_scores)))

            if not hit_detectors:
                continue

            prompt = extract_text(entry.get("prompt", ""))
            outputs = entry.get("outputs", [])
            raw_output = outputs[0] if outputs else ""
            output = extract_text(raw_output)
            probe = entry.get("probe_classname", "")
            if args.probe and args.probe not in probe:
                continue

            hits.append({
                "probe": probe,
                "detectors": hit_detectors,
                "prompt": prompt,
                "output": output,
            })

    print(f"Всего пробитий найдено: {len(hits)}\n")
    print(f"Показываю первые {min(args.limit, len(hits))}:\n")
    print("=" * 80)

    for i, hit in enumerate(hits[: args.limit], 1):
        print(f"\n### Пример {i}")
        print(f"Проба: {hit['probe']}")
        print(f"Сработавшие детекторы: {hit['detectors']}")
        print(f"\nЗапрос (input):\n{hit['prompt'][:500]}")
        print(f"\nОтвет модели (output):\n{hit['output'][:500]}")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()