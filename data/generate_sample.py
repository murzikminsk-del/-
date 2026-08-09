import json
from datetime import datetime, timedelta
from pathlib import Path
from docx import Document

def get_category(filename: str) -> str:
    if "КС" in filename or "концесс" in filename.lower():
        return "concession"
    if "подряд" in filename.lower() or "Договор" in filename:
        return "legal"
    if "Политика" in filename or "обработ" in filename.lower():
        return "compliance"
    return "corporate"


        
def main() -> None:
    docs_dir = Path("data/docs")
    output = Path("data/sample_kb.jsonl")
    
    base_dates = {
        "concession": datetime(2024, 1, 15),
        "legal": datetime(2024, 3, 10),
        "compliance": datetime(2024, 6, 1),
        "corporate": datetime(2023, 11, 20),
    }
    
    total = 0
    with output.open("w", encoding="utf-8") as f:
        for path in sorted(docs_dir.glob("*.docx")):
            category = get_category(path.name)
            base_date = base_dates[category]
            doc = Document(path)
            chunk_index = 0
            for para in doc.paragraphs:
                text = para.text.strip()
                if len(text) < 40:
                    continue
                record = {
                    "source": path.name,
                    "chunk_index": chunk_index,
                    "text": text,
                    "category": category,
                    "created_at": (base_date + timedelta(hours=chunk_index)).isoformat(),
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                chunk_index += 1
                total += 1
    
    print(f"Записано {total} чанков в data/sample_kb.jsonl")


if __name__ == "__main__":
    main()