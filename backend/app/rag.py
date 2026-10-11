from __future__ import annotations

import time
from uuid import uuid4
import logging
import httpx

from .config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from .models import ChatTurn
from .store import KnowledgeStore

logger = logging.getLogger(__name__)


def split_text(text: str, chunk_size: int = 700, overlap: int = 120) -> list[str]:
    text = " ".join(text.split())
    if not text:
        return []
    return [text[start:start + chunk_size] for start in range(0, len(text), chunk_size - overlap)]


def build_context(results: list[dict]) -> str:
    return "\n\n".join(
        f"[{i + 1}] 来源：{item['document_name']}，第 {item['page']} 页\n内容：{item['content']}"
        for i, item in enumerate(results)
    )


def select_evidence(results: list[dict], limit: int = 3) -> list[dict]:
    """Remove low-relevance chunks before they can distract the generator."""
    if not results or results[0]["rerank_score"] < 0.055:
        return []
    threshold = max(0.055, results[0]["rerank_score"] * 0.45)
    return [item for item in results if item["rerank_score"] >= threshold][:limit]


SYSTEM_PROMPT = """你是严谨、自然的中文企业知识助手。你的工作是只使用检索到的材料回答用户。

回答规则：
1. 先直接回答问题，不要机械复述“根据知识库”或“已完成检索”。
2. 只陈述材料明确支持的事实；材料没有覆盖时，直接说明“现有资料不足以判断”，不要凭常识补全。
3. 每条来自材料的关键结论都要在句末标注对应的 [序号]。不要引用无关材料，也不要罗列所有资料。
4. 问题简单时用 1—3 段自然语言回答；问题包含多个要点时，使用“结论 / 依据 / 建议”的简短结构。避免空泛套话、重复和夸张承诺。
5. 历史对话只用于理解指代，不可作为事实来源；事实依据必须来自本轮给出的检索材料。
6. 不要编造文档、页码、指标、系统功能或操作结果。"""

GENERAL_SYSTEM_PROMPT = """你是专业、自然的中文 AI 助手。请直接解决用户的问题：先给出清晰结论，再按需要补充简短理由、步骤或示例。

规则：
1. 语言要具体、自然、少套话；不要把普通回答伪装成“知识库结论”。
2. 若提供了补充资料，可参考它们并用 [序号] 标注；资料并非唯一事实来源。
3. 不确定、缺乏关键信息或存在明显风险时，要说明边界并提出下一步需要的信息。
4. 不编造数据、文件、操作结果、引用或已完成的动作。"""


async def ask_llm(question: str, context: str, history: list[ChatTurn], response_mode: str) -> str | None:
    if not all((LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)):
        return None
    messages = [{"role": "system", "content": SYSTEM_PROMPT if response_mode == "knowledge" else GENERAL_SYSTEM_PROMPT}]
    messages.extend({"role": turn.role, "content": turn.content} for turn in history[-6:])
    prompt = (
        f"检索材料（仅以下内容可作为事实依据）：\n{context}\n\n当前问题：{question}"
        if response_mode == "knowledge"
        else f"可选的知识库补充材料：\n{context or '（本轮没有匹配材料）'}\n\n当前问题：{question}"
    )
    messages.append({"role": "user", "content": prompt})
    body = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.15,
        "max_tokens": 700,
    }
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(f"{LLM_BASE_URL}/chat/completions", headers={"Authorization": f"Bearer {LLM_API_KEY}"}, json=body)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        logger.warning("LLM upstream rejected request: status=%s body=%s", exc.response.status_code, exc.response.text[:500])
        return None
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        logger.warning("LLM request failed: %s", type(exc).__name__)
        return None


async def answer(
    question: str,
    store: KnowledgeStore,
    top_k: int,
    history: list[ChatTurn] | None = None,
    response_mode: str = "knowledge",
) -> dict:
    started = time.perf_counter()
    results = store.search(question, top_k)
    evidence = select_evidence(results)
    context = build_context(evidence)
    llm_answer = await ask_llm(question, context, history or [], response_mode) if (evidence or response_mode == "general") else None
    if llm_answer:
        text, mode = llm_answer, "llm"
    elif evidence:
        snippets = "；".join(item["content"][:92] for item in evidence[:2])
        text = f"与“{question}”最相关的材料是：{snippets}。请结合下方引用页码核验。"
        mode = "demo"
    elif response_mode == "general":
        text, mode = "模型服务暂时不可用，无法生成通用回答。请稍后重试。", "demo"
    else:
        text, mode = "现有知识库没有检索到足够相关的材料，暂时无法给出可靠结论。请上传或补充相关文档后重试。", "demo"
    citations = [{"chunk_id": item["id"], "document_name": item["document_name"], "page": item["page"], "score": round(item["rerank_score"], 4), "content": item["content"]} for item in evidence]
    return {"answer": text, "citations": citations, "trace_id": f"trace_{uuid4().hex[:12]}", "mode": mode, "answer_scope": response_mode, "elapsed_ms": int((time.perf_counter() - started) * 1000)}
