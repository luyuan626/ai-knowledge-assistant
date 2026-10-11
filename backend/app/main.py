from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4
import fitz
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, ROOT_DIR, UPLOAD_DIR
from .models import QueryRequest, QueryResponse, RetrievalRequest, ChunkRecord, VisionResult, DocumentSummary
from .rag import answer, split_text
from .store import KnowledgeStore

app = FastAPI(title="RAG 智能问答助手", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
store = KnowledgeStore()


def extract_pages(file_path: Path) -> list[tuple[int, str]]:
    if file_path.suffix.lower() == ".pdf":
        document = fitz.open(file_path)
        return [(number + 1, page.get_text("text")) for number, page in enumerate(document)]
    return [(1, file_path.read_text(encoding="utf-8", errors="ignore"))]


@app.get("/health")
def health():
    return {"status": "ok", "service": "rag-knowledge-assistant"}


@app.get("/api/documents", response_model=list[DocumentSummary])
def documents():
    return store.list_documents()


@app.post("/api/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise HTTPException(400, "仅支持 PDF、TXT、MD 文档")
    target = UPLOAD_DIR / f"{uuid4().hex}{suffix}"
    target.write_bytes(await file.read())
    chunks = []
    for page, text in extract_pages(target):
        chunks.extend((page, part) for part in split_text(text) if len(part.strip()) > 30)
    if not chunks:
        raise HTTPException(400, "未从文档中解析到可用文本")
    return store.add_document(file.filename or target.name, suffix.lstrip("."), chunks)


@app.post("/api/chat", response_model=QueryResponse)
async def chat(request: QueryRequest):
    return await answer(request.question, store, request.top_k, request.history, request.response_mode)


@app.post("/api/retrieval", response_model=list[ChunkRecord])
def retrieval(request: RetrievalRequest):
    return [{"chunk_id": item["id"], "document_id": item["document_id"], "document_name": item["document_name"], "page": item["page"], "content": item["content"], "keyword_score": round(item["keyword_score"], 4), "vector_score": round(item["vector_score"], 4), "rrf_score": round(item["rrf_score"], 5), "rerank_score": round(item["rerank_score"], 4)} for item in store.search(request.query, request.top_k)]


@app.post("/api/vision/analyze", response_model=VisionResult)
def analyze_vision(result: VisionResult):
    """Accept structured detector output so vision results can become RAG context."""
    return result


@app.get("/api/evaluation/summary")
def evaluation_summary():
    return {"retrieval_recall_at_5": None, "mrr": None, "citation_precision": None, "message": "指标需要基于人工标注的评测集计算；当前页面不伪造离线评测结果。", "updated_at": datetime.now().isoformat()}


# The production package copies the Vite build here, so one Uvicorn process can
# serve both the UI and API without requiring Node.js or an extra web server.
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
