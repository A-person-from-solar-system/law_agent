"""对外 HTTP 服务：封装 Hybrid RAG / 检索能力。

启动（在工程根目录、rag 环境）：
    python scripts/serve_api.py
    # 或
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000

接口：
    GET  /health
    POST /ask       完整问答（检索 + LLM）
    POST /retrieve  仅检索证据（不调 LLM，适合其他 Agent 自己生成）
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src.models import RAGAnswer, RetrievalHit
from src.rag import RAGPipeline
from src.storage.chroma_store import ALL_KINDS, KIND_CHUNK


_pipeline: Optional[RAGPipeline] = None


def get_pipeline() -> RAGPipeline:
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="RAG 服务未就绪")
    return _pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline
    logger.info("正在初始化 RAGPipeline（连接 PG / 向量库 / Neo4j）...")
    pipe = RAGPipeline()
    pipe.ready()
    _pipeline = pipe
    logger.success("RAG API 已就绪")
    yield
    _pipeline = None
    logger.info("RAG API 已关闭")


app = FastAPI(
    title="律所知识库 RAG API",
    description="基于 PostgreSQL + 向量检索的 Hybrid 法律问答服务（CAIL 样本库）",
    version="0.1.0",
    lifespan=lifespan,
)


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, description="自然语言问题")
    mode: str = Field(
        "hybrid",
        description="检索模式：hybrid（推荐）| local | global | auto | graphrag",
    )
    evidence_limit: int = Field(8, ge=1, le=20, description="返回证据条数上限")


class HitOut(BaseModel):
    hit_id: str
    text: str
    score: float = 0.0
    source_type: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AskResponse(BaseModel):
    query: str
    answer: str
    mode: str
    intent: Optional[Dict[str, Any]] = None
    evidence: List[HitOut] = Field(default_factory=list)


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)
    mode: str = Field("hybrid")
    top_k: int = Field(8, ge=1, le=20)


class RetrieveResponse(BaseModel):
    query: str
    mode: str
    intent: Optional[Dict[str, Any]] = None
    evidence: List[HitOut] = Field(default_factory=list)
    buckets: Dict[str, int] = Field(default_factory=dict)


class SourceRequest(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=256)


def _hit_to_out(hit: RetrievalHit, text_limit: int = 2000) -> HitOut:
    text = hit.text or ""
    if len(text) > text_limit:
        text = text[:text_limit] + "…"
    return HitOut(
        hit_id=hit.hit_id,
        text=text,
        score=float(hit.score or 0.0),
        source_type=hit.source_type or "",
        metadata=dict(hit.metadata or {}),
    )


def _answer_to_response(answer: RAGAnswer, mode: str, evidence_limit: int) -> AskResponse:
    intent_dump = None
    if answer.intent is not None:
        intent_dump = answer.intent.model_dump()
    return AskResponse(
        query=answer.query,
        answer=answer.answer,
        mode=mode,
        intent=intent_dump,
        evidence=[_hit_to_out(h) for h in (answer.evidence or [])[:evidence_limit]],
    )


def _source_from_vector(pipe: RAGPipeline, source_id: str) -> Optional[RetrievalHit]:
    """Resolve a source ID exactly without embeddings or fuzzy retrieval."""
    vector = pipe.store.vector
    vector._ensure()

    for kind in ALL_KINDS:
        bucket = vector._mock.get(kind) or {}
        ids = list(bucket.get("ids") or [])
        if source_id in ids:
            index = ids.index(source_id)
            documents = list(bucket.get("documents") or [])
            metadatas = list(bucket.get("metadatas") or [])
            return RetrievalHit(
                hit_id=source_id,
                text=str(documents[index] if index < len(documents) else ""),
                score=1.0,
                source_type=kind,
                metadata=dict(metadatas[index] if index < len(metadatas) else {}),
            )

    chunk_bucket = vector._mock.get(KIND_CHUNK) or {}
    rows = []
    for index, metadata in enumerate(chunk_bucket.get("metadatas") or []):
        if str((metadata or {}).get("doc_id") or "") == source_id:
            rows.append((int((metadata or {}).get("order") or 0), index, metadata or {}))
    if rows:
        rows.sort(key=lambda item: item[0])
        documents = list(chunk_bucket.get("documents") or [])
        text = "\n\n".join(
            str(documents[index]) for _, index, _ in rows if index < len(documents)
        )
        metadata = dict(rows[0][2])
        metadata["resolved_chunk_count"] = len(rows)
        return RetrievalHit(
            hit_id=source_id,
            text=text,
            score=1.0,
            source_type=KIND_CHUNK,
            metadata=metadata,
        )

    if vector._use_chroma:
        for kind, collection in vector._collections.items():
            result = collection.get(
                ids=[source_id], include=["documents", "metadatas"]
            )
            ids = list(result.get("ids") or [])
            if ids:
                documents = list(result.get("documents") or [])
                metadatas = list(result.get("metadatas") or [])
                return RetrievalHit(
                    hit_id=source_id,
                    text=str(documents[0] if documents else ""),
                    score=1.0,
                    source_type=kind,
                    metadata=dict(metadatas[0] if metadatas else {}),
                )

        collection = vector._collections.get(KIND_CHUNK)
        if collection is not None:
            result = collection.get(
                where={"doc_id": source_id}, include=["documents", "metadatas"]
            )
            documents = list(result.get("documents") or [])
            metadatas = list(result.get("metadatas") or [])
            if documents:
                rows = sorted(
                    zip(documents, metadatas),
                    key=lambda item: int((item[1] or {}).get("order") or 0),
                )
                metadata = dict(rows[0][1] or {})
                metadata["resolved_chunk_count"] = len(rows)
                return RetrievalHit(
                    hit_id=source_id,
                    text="\n\n".join(str(document) for document, _ in rows),
                    score=1.0,
                    source_type=KIND_CHUNK,
                    metadata=metadata,
                )
    return None


@app.get("/health")
def health() -> Dict[str, Any]:
    ready = _pipeline is not None
    return {"status": "ok" if ready else "starting", "rag_ready": ready}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """完整 Hybrid 问答：检索 + 绑 meta + LLM 生成。"""
    pipe = get_pipeline()
    try:
        answer = pipe.ask(req.query.strip(), search_mode=req.mode)
    except Exception as exc:
        logger.exception("ask 失败")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return _answer_to_response(answer, req.mode, req.evidence_limit)


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(req: RetrieveRequest) -> RetrieveResponse:
    """仅检索融合证据，不调用 LLM（供其他 Agent / 业务自行生成）。"""
    pipe = get_pipeline()
    try:
        intent = pipe.parser.parse(req.query.strip())
        mode = (req.mode or "hybrid").strip().lower()
        intent.search_mode = mode
        if mode in {"local", "global", "auto", "graphrag"}:
            if mode == "graphrag":
                intent.search_mode = "auto"
            buckets = pipe.graphrag.retrieve(intent)
        else:
            buckets = pipe.hybrid.retrieve(intent)
        fused = pipe.fusion.fuse(buckets)[: req.top_k]
    except Exception as exc:
        logger.exception("retrieve 失败")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return RetrieveResponse(
        query=req.query,
        mode=mode,
        intent=intent.model_dump(),
        evidence=[_hit_to_out(h) for h in fused],
        buckets={k: len(v or []) for k, v in buckets.items()},
    )


@app.post("/source", response_model=HitOut)
def source(req: SourceRequest) -> HitOut:
    """Return the complete stored text for an exact source ID."""
    pipe = get_pipeline()
    try:
        hit = _source_from_vector(pipe, req.source_id.strip())
    except Exception as exc:
        logger.exception("source lookup 失败")
        raise HTTPException(status_code=500, detail="source lookup failed") from exc
    if hit is None or not hit.text:
        raise HTTPException(status_code=404, detail="source not found")
    return HitOut(
        hit_id=req.source_id,
        text=hit.text,
        score=1.0,
        source_type=hit.source_type,
        metadata=dict(hit.metadata or {}),
    )
