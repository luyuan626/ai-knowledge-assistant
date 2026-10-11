from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1500)


class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    knowledge_base: str = "通用知识库"
    top_k: int = Field(default=5, ge=1, le=10)
    history: list[ChatTurn] = Field(default_factory=list, max_length=6)
    response_mode: Literal["knowledge", "general"] = "knowledge"


class Citation(BaseModel):
    chunk_id: str
    document_name: str
    page: int
    score: float
    content: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    trace_id: str
    mode: Literal["demo", "llm"]
    answer_scope: Literal["knowledge", "general"]
    elapsed_ms: int


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=10)


class ChunkRecord(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page: int
    content: str
    keyword_score: float
    vector_score: float
    rrf_score: float
    rerank_score: float


class VisionResult(BaseModel):
    task_id: str
    defect_type: str
    confidence: float = Field(ge=0, le=1)
    position: str
    recommendation: str


class Detection(BaseModel):
    defect_type: str
    confidence: float = Field(ge=0, le=1)
    position: str
    bbox_xyxy: list[float] | None = None


class VisionInferenceResponse(BaseModel):
    model_path: str
    image_name: str
    width: int
    height: int
    detections: list[Detection]


class InspectionRequest(BaseModel):
    detections: list[Detection] = Field(min_length=1, max_length=50)
    question: str = "请基于检测结果和知识库给出缺陷分析、处置建议与依据。"
    top_k: int = Field(default=5, ge=1, le=10)


class DocumentMetadata(BaseModel):
    device_type: str | None = None
    defect_type: str | None = None
    document_version: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class DocumentSummary(BaseModel):
    id: str
    name: str
    source_type: str
    chunks: int
    created_at: datetime
