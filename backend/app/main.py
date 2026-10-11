from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import CORS_ORIGINS, ROOT_DIR, UPLOAD_DIR
from .models import InspectionRequest, QueryRequest, QueryResponse, RetrievalRequest, ChunkRecord, VisionInferenceResponse, VisionResult, DocumentSummary
from .rag import answer
from .store import KnowledgeStore
from .document_parser import parse_document
from .evaluation import load_evaluation, run_retrieval_evaluation
from .vision import infer_image

app = FastAPI(title="RAG 智能问答助手", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
store = KnowledgeStore()


@app.get("/health")
def health():
    return {"status": "ok", "service": "rag-knowledge-assistant"}


@app.get("/api/documents", response_model=list[DocumentSummary])
def documents():
    return store.list_documents()


@app.post("/api/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), device_type: str | None = Form(None), defect_type: str | None = Form(None), document_version: str | None = Form(None)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise HTTPException(400, "仅支持 PDF、TXT、MD 文档")
    target = UPLOAD_DIR / f"{uuid4().hex}{suffix}"
    target.write_bytes(await file.read())
    chunks = [chunk for chunk in parse_document(target) if len(chunk["content"].strip()) > 30]
    if not chunks:
        raise HTTPException(400, "未从文档中解析到可用文本")
    return store.add_document(file.filename or target.name, suffix.lstrip("."), chunks, {"device_type": device_type or "", "defect_type": defect_type or "", "document_version": document_version or ""})


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


@app.post("/api/vision/infer", response_model=VisionInferenceResponse)
async def infer_vision(file: UploadFile = File(...), confidence: float = Form(0.25)):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "仅支持图像文件")
    try:
        return infer_image(file.filename or "image.jpg", await file.read(), confidence)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/reports/inspection", response_model=QueryResponse)
async def inspection_report(request: InspectionRequest):
    categories = sorted({item.defect_type for item in request.detections})
    visual_context = "\n".join(f"- 类别：{item.defect_type}；置信度：{item.confidence:.2%}；位置：{item.position}" for item in request.detections)
    filters = {"defect_type": categories[0]} if len(categories) == 1 else None
    return await answer(request.question, store, request.top_k, [], "knowledge", filters=filters, visual_context=visual_context)


@app.get("/api/evaluation/summary")
def evaluation_summary():
    return load_evaluation()


@app.post("/api/evaluation/run")
def run_evaluation():
    return run_retrieval_evaluation(store)


# The production package copies the Vite build here, so one Uvicorn process can
# serve both the UI and API without requiring Node.js or an extra web server.
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
