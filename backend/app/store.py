"""Persistent hybrid retrieval: SQLite metadata + BM25 + BGE-M3/Milvus + BGE reranker."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sqlite3
from pathlib import Path
from uuid import uuid4

from rank_bm25 import BM25Okapi

from .config import DB_PATH, MILVUS_COLLECTION, MILVUS_URI, RAG_DEVICE, RAG_EMBEDDING_MODEL, RAG_RERANKER_MODEL, RECALL_CANDIDATES


def tokenize(text: str) -> list[str]:
    pairs = [text[i:i + 2] for i in range(max(0, len(text) - 1)) if all("\u4e00" <= char <= "\u9fff" for char in text[i:i + 2])]
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]*", text.lower())
    return pairs + words or [text[:1]]


class HybridKnowledgeStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path, self._embedder, self._reranker, self._milvus = db_path, None, None, None
        self._init_db()
        self.seed_if_empty()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.connect() as conn:
            conn.executescript("""
              CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, name TEXT NOT NULL, source_type TEXT NOT NULL, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}');
              CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, document_id TEXT NOT NULL, page INTEGER NOT NULL, content TEXT NOT NULL, heading TEXT NOT NULL DEFAULT '', child_index INTEGER NOT NULL DEFAULT 1, milvus_id INTEGER, FOREIGN KEY(document_id) REFERENCES documents(id));
              CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
            """)
            for table, column, declaration in (("documents", "metadata_json", "TEXT NOT NULL DEFAULT '{}'"), ("chunks", "heading", "TEXT NOT NULL DEFAULT ''"), ("chunks", "child_index", "INTEGER NOT NULL DEFAULT 1"), ("chunks", "milvus_id", "INTEGER")):
                if column not in {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")

    def seed_if_empty(self):
        with self.connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]:
                return
        self.add_document("工业视觉质检知识库示例", "seed", [
            {"page": 1, "heading": "系统追溯", "content": "[系统追溯] 视觉质检系统通常由数据采集、模型推理、缺陷复核和报告生成组成。部署时应记录模型版本、输入来源、置信度阈值和处理时间，以保证结果可追溯。"},
            {"page": 2, "heading": "检索策略", "content": "[检索策略] RAG 的检索链路可采用关键词检索与向量检索并行召回。使用 Reciprocal Rank Fusion（RRF）融合候选列表，再用重排序模型提升高相关片段的位置。"},
            {"page": 3, "heading": "元数据", "content": "[元数据] 知识库入库应保存文档名称、页码、版本、设备型号和缺陷类别等元数据。回答中返回证据片段和页码，能够帮助使用者核验结论来源。"},
        ], {"device_type": "工业视觉", "document_version": "demo-v1"})

    def add_document(self, name: str, source_type: str, chunks: list[dict], metadata: dict | None = None) -> dict:
        doc_id, created_at = str(uuid4()), datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute("INSERT INTO documents (id,name,source_type,created_at,metadata_json) VALUES (?,?,?,?,?)", (doc_id, name, source_type, created_at, json.dumps(metadata or {}, ensure_ascii=False)))
            for index, chunk in enumerate(chunks, start=1):
                conn.execute("INSERT INTO chunks (id,document_id,page,content,heading,child_index) VALUES (?,?,?,?,?,?)", (str(uuid4()), doc_id, int(chunk["page"]), chunk["content"], chunk.get("heading", "正文"), int(chunk.get("child_index", index))))
        return {"id": doc_id, "chunks": len(chunks), "indexed": False}

    def list_documents(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT d.id,d.name,d.source_type,d.created_at,COUNT(c.id) chunks FROM documents d LEFT JOIN chunks c ON d.id=c.document_id GROUP BY d.id ORDER BY d.created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def _load_models(self):
        if self._embedder is None:
            try:
                from FlagEmbedding import BGEM3FlagModel, FlagReranker
            except ImportError as exc:
                raise RuntimeError("缺少 FlagEmbedding 依赖，请按 backend/requirements.txt 安装后重试。") from exc
            fp16 = RAG_DEVICE.startswith("cuda")
            devices = [RAG_DEVICE] if RAG_DEVICE and RAG_DEVICE != "auto" else None
            self._embedder = BGEM3FlagModel(RAG_EMBEDDING_MODEL, use_fp16=fp16, devices=devices)
            self._reranker = FlagReranker(RAG_RERANKER_MODEL, use_fp16=fp16, devices=devices)

    def _milvus_client(self):
        if self._milvus is not None:
            return self._milvus
        try:
            from pymilvus import DataType, MilvusClient
        except ImportError as exc:
            raise RuntimeError("缺少 pymilvus[milvus-lite] 依赖，请按 requirements 安装后重试。") from exc
        client = MilvusClient(uri=MILVUS_URI)
        if not client.has_collection(MILVUS_COLLECTION):
            schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
            schema.add_field("id", DataType.INT64, is_primary=True)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=1024)
            indexes = client.prepare_index_params()
            indexes.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="IP")
            client.create_collection(collection_name=MILVUS_COLLECTION, schema=schema, index_params=indexes)
        self._milvus = client
        return client

    @staticmethod
    def _numeric_id(chunk_id: str) -> int:
        return int(chunk_id.replace("-", "")[:15], 16) % (2**63 - 1)

    def _rows(self, filters: dict | None = None) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT c.id,c.document_id,c.page,c.content,c.heading,c.milvus_id,d.name document_name,d.metadata_json FROM chunks c JOIN documents d ON c.document_id=d.id").fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            if filters and any(value and str(item["metadata"].get(key, "")).lower() != str(value).lower() for key, value in filters.items()):
                continue
            output.append(item)
        return output

    def _ensure_index(self, rows: list[dict]):
        pending = [row for row in rows if row["milvus_id"] is None]
        if not pending:
            return
        self._load_models()
        vectors = self._embedder.encode([row["content"] for row in pending], batch_size=8, max_length=8192)["dense_vecs"]
        inserts = []
        for row, vector in zip(pending, vectors):
            row["milvus_id"] = self._numeric_id(row["id"])
            inserts.append({"id": row["milvus_id"], "vector": vector.tolist(), "chunk_id": row["id"]})
        self._milvus_client().insert(collection_name=MILVUS_COLLECTION, data=inserts)
        with self.connect() as conn:
            conn.executemany("UPDATE chunks SET milvus_id=? WHERE id=?", [(row["milvus_id"], row["id"]) for row in pending])

    @staticmethod
    def _normalise(values: list[float]) -> list[float]:
        if not values:
            return []
        low, high = min(values), max(values)
        return [1.0 if high == low and high > 0 else ((value - low) / (high - low) if high != low else 0.0) for value in values]

    def search(self, query: str, top_k: int = 5, filters: dict | None = None) -> list[dict]:
        rows = self._rows(filters)
        if not rows:
            return []
        self._ensure_index(rows)
        self._load_models()
        bm25_scores = BM25Okapi([tokenize(row["content"]) for row in rows]).get_scores(tokenize(query)).tolist()
        bm25_order = sorted(range(len(rows)), key=lambda i: bm25_scores[i], reverse=True)[:RECALL_CANDIDATES]
        query_vec = self._embedder.encode([query], batch_size=1, max_length=8192)["dense_vecs"][0].tolist()
        hits = self._milvus_client().search(collection_name=MILVUS_COLLECTION, data=[query_vec], limit=max(50, RECALL_CANDIDATES * 3), output_fields=["chunk_id"])[0]
        allowed, vector_ids, vector_raw = {row["id"] for row in rows}, [], {}
        for hit in hits:
            chunk_id = hit.get("entity", {}).get("chunk_id")
            if chunk_id in allowed and chunk_id not in vector_raw:
                vector_ids.append(chunk_id); vector_raw[chunk_id] = float(hit["distance"])
            if len(vector_ids) >= RECALL_CANDIDATES:
                break
        bm25_ids = [rows[i]["id"] for i in bm25_order]
        candidate_ids = list(dict.fromkeys(bm25_ids + vector_ids))
        by_id = {row["id"]: row for row in rows}
        bm25_norm = dict(zip([row["id"] for row in rows], self._normalise(bm25_scores)))
        vector_norm = dict(zip(vector_raw.keys(), self._normalise(list(vector_raw.values()))))
        bm25_rank, vector_rank = {key: i + 1 for i, key in enumerate(bm25_ids)}, {key: i + 1 for i, key in enumerate(vector_ids)}
        scores = self._reranker.compute_score([[query, by_id[key]["content"]] for key in candidate_ids], normalize=True)
        if isinstance(scores, float):
            scores = [scores]
        output = []
        for key, rerank in zip(candidate_ids, scores):
            rrf = (1 / (60 + bm25_rank[key]) if key in bm25_rank else 0) + (1 / (60 + vector_rank[key]) if key in vector_rank else 0)
            output.append({**by_id[key], "keyword_score": round(bm25_norm.get(key, 0.0), 6), "vector_score": round(vector_norm.get(key, 0.0), 6), "rrf_score": round(rrf, 8), "rerank_score": round(float(rerank), 6)})
        return sorted(output, key=lambda item: item["rerank_score"], reverse=True)[:top_k]


KnowledgeStore = HybridKnowledgeStore
