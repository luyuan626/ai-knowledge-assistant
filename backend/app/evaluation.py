from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import quantiles
from time import perf_counter

from .config import DATA_DIR

DATASET_PATH = Path(__file__).with_name("seed_eval.json")
RESULT_PATH = DATA_DIR / "evaluation_latest.json"


def run_retrieval_evaluation(store, top_k: int = 5) -> dict:
    cases = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    recalls, reciprocal_ranks, citation_hits, citation_total, latencies = [], [], 0, 0, []
    for case in cases:
        started = perf_counter()
        results = store.search(case["question"], top_k=top_k)
        latencies.append((perf_counter() - started) * 1000)
        expected = {(target["document_name"], target["page"]) for target in case["relevant_sources"]}
        ranks = [i + 1 for i, result in enumerate(results) if (result["document_name"], result["page"]) in expected]
        recalls.append(float(bool(ranks)))
        reciprocal_ranks.append(1 / ranks[0] if ranks else 0.0)
        citation_hits += sum((result["document_name"], result["page"]) in expected for result in results)
        citation_total += len(results)
    report = {"dataset": DATASET_PATH.name, "samples": len(cases), "top_k": top_k,
              "retrieval_recall_at_5": round(sum(recalls) / len(recalls), 4),
              "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 4),
              "citation_precision": round(citation_hits / citation_total, 4) if citation_total else 0.0,
              "p95_retrieval_ms": round(quantiles(latencies, n=100, method="inclusive")[94], 2) if len(latencies) > 1 else round(latencies[0], 2),
              "message": "基于固定人工标注的演示评测集计算；仅代表当前数据集与模型配置，不代表通用工业场景。",
              "updated_at": datetime.now(timezone.utc).isoformat()}
    RESULT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def load_evaluation() -> dict:
    if RESULT_PATH.is_file():
        return json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    return {"retrieval_recall_at_5": None, "mrr": None, "citation_precision": None, "p95_retrieval_ms": None, "message": "尚未运行评测。请完成模型索引后调用 POST /api/evaluation/run。", "updated_at": None}
