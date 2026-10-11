from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", ROOT_DIR / "uploads"))
DB_PATH = Path(os.getenv("DATABASE_PATH", DATA_DIR / "assistant.db"))

for directory in (DATA_DIR, UPLOAD_DIR):
    directory.mkdir(parents=True, exist_ok=True)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")

# Hybrid retrieval is intentionally explicit: SQLite owns source metadata,
# while Milvus Lite owns dense BGE-M3 vectors.
RAG_EMBEDDING_MODEL = os.getenv("RAG_EMBEDDING_MODEL", "BAAI/bge-m3")
RAG_RERANKER_MODEL = os.getenv("RAG_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RAG_DEVICE = os.getenv("RAG_DEVICE", "cuda")
MILVUS_URI = os.getenv("MILVUS_URI", str(DATA_DIR / "milvus.db"))
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "knowledge_chunks")
RECALL_CANDIDATES = int(os.getenv("RECALL_CANDIDATES", "20"))
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "")
YOLO_DEVICE = os.getenv("YOLO_DEVICE", "0")
