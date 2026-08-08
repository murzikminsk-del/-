import base64
import io
from typing import Any

import httpx
from docx import Document
from pypdf import PdfReader


async def media_to_part(content: bytes, mime: str, openai_client: Any) -> dict:
    if mime.startswith("image/"):
        b64 = base64.b64encode(content).decode()
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        }

    if mime.startswith("audio/"):
        transcription = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.ogg", io.BytesIO(content), mime),
        )
        return {"type": "text", "text": f"[Транскрипция аудио]: {transcription.text}"}

    if mime == "application/pdf":
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return {"type": "text", "text": f"[Содержимое PDF]:\n{text}"}

    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = Document(io.BytesIO(content))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        return {"type": "text", "text": f"[Содержимое документа]:\n{text}"}

    return {"type": "text", "text": f"[Файл {mime} — формат не поддерживается]"}
