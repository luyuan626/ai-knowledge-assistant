from __future__ import annotations

import re
from pathlib import Path
import fitz


def _is_heading(text: str) -> bool:
    value = text.strip()
    return bool(re.match(r"^(第[一二三四五六七八九十\d]+[章节]|[0-9]+(?:\.[0-9]+){0,4}\s+|[一二三四五六七八九十]+、)", value)) or (len(value) <= 34 and not value.endswith(("。", "；", ".")))


def split_children(text: str, chunk_size: int = 700, overlap: int = 120) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    sentences = re.split(r"(?<=[。！？；.!?])", text)
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) > chunk_size and current:
            chunks.append(current.strip())
            current = current[-overlap:] + sentence
        else:
            current += sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _table_text(page: fitz.Page) -> str:
    try:
        tables = page.find_tables().tables
    except Exception:
        return ""
    rendered = []
    for table in tables:
        rows = table.extract()
        if not rows:
            continue
        for row in rows:
            rendered.append(" | ".join(str(cell or "").strip() for cell in row))
    return "\n".join(line for line in rendered if line.strip())


def parse_document(file_path: Path) -> list[dict]:
    """Return parent-heading-aware child chunks with page provenance."""
    if file_path.suffix.lower() != ".pdf":
        return [{"page": 1, "heading": "正文", "content": part} for part in split_children(file_path.read_text(encoding="utf-8", errors="ignore"))]
    document = fitz.open(file_path)
    output: list[dict] = []
    current_heading = "未命名章节"
    for number, page in enumerate(document, start=1):
        lines = [line.strip() for line in page.get_text("text").splitlines() if line.strip()]
        body = []
        for line in lines:
            if _is_heading(line):
                current_heading = line
            else:
                body.append(line)
        table_text = _table_text(page)
        merged = "\n".join(body + ([table_text] if table_text else []))
        for child_index, part in enumerate(split_children(merged), start=1):
            output.append({"page": number, "heading": current_heading, "content": f"[{current_heading}]\n{part}", "child_index": child_index})
    return output
