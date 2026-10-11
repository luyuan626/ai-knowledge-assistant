"""Small, dependency-light knowledge store.

It keeps the local demo runnable without external services. Production adapters can
replace this module with Milvus + BGE-M3 while retaining the retrieval contract.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re
import sqlite3
from pathlib import Path
from uuid import uuid4

from .config import DB_PATH


def tokenize(text: str) -> list[str]:
    chinese = re.findall(r"[\u4e00-\u9fff]{1,4}", text)
    english = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", text.lower())
    chars = [text[i:i + 2] for i in range(max(0, len(text) - 1)) if "\u4e00" <= text[i] <= "\u9fff"]
    return chinese + english + chars


def overlap_score(query: str, content: str) -> float:
    query_tokens = Counter(tokenize(query))
    content_tokens = Counter(tokenize(content))
    if not query_tokens:
        return 0.0
    return sum(min(count, content_tokens[token]) for token, count in query_tokens.items()) / sum(query_tokens.values())


class KnowledgeStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
        self.seed_if_empty()

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self):
        with self.connect() as conn:
            conn.executescript("""
              CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL,
                created_at TEXT NOT NULL
              );
              CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL, page INTEGER NOT NULL,
                content TEXT NOT NULL, FOREIGN KEY(document_id) REFERENCES documents(id)
              );
            """)

    def seed_if_empty(self):
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        if count:
            return
        self.add_document("工业视觉质检知识库示例", "seed", [
            (1, "视觉质检系统通常由数据采集、模型推理、缺陷复核和报告生成组成。部署时应记录模型版本、输入来源、置信度阈值和处理时间，以保证结果可追溯。"),
            (2, "RAG 的检索链路可采用关键词检索与向量检索并行召回。使用 Reciprocal Rank Fusion（RRF）融合候选列表，再用重排序模型提升高相关片段的位置。"),
            (3, "知识库入库应保存文档名称、页码、版本、设备型号和缺陷类别等元数据。回答中返回证据片段和页码，能够帮助使用者核验结论来源。"),
        ])

    def add_document(self, name: str, source_type: str, chunks: list[tuple[int, str]]) -> dict:
        document_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute("INSERT INTO documents VALUES (?, ?, ?, ?)", (document_id, name, source_type, created_at))
            for page, content in chunks:
                conn.execute("INSERT INTO chunks VALUES (?, ?, ?, ?)", (str(uuid4()), document_id, page, content))
        return {"id": document_id, "chunks": len(chunks)}

    def list_documents(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("""
              SELECT d.id, d.name, d.source_type, d.created_at, COUNT(c.id) chunks
              FROM documents d LEFT JOIN chunks c ON d.id = c.document_id
              GROUP BY d.id ORDER BY d.created_at DESC
            """).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("""
              SELECT c.id, c.document_id, c.page, c.content, d.name document_name
              FROM chunks c JOIN documents d ON c.document_id = d.id
            """).fetchall()
        ranked = []
        for row in rows:
            keyword = overlap_score(query, row["content"])
            # Deterministic local proxy for semantic score; replace with BGE-M3 in production.
            vector = min(1.0, keyword * 0.82 + 0.12 if keyword else 0.03)
            rrf = 1 / (60 + max(1, int((1 - keyword) * 10 + 1)))
            rerank = min(1.0, 0.65 * keyword + 0.35 * vector)
            ranked.append({**dict(row), "keyword_score": keyword, "vector_score": vector, "rrf_score": rrf, "rerank_score": rerank})
        return sorted(ranked, key=lambda item: item["rerank_score"], reverse=True)[:top_k]
