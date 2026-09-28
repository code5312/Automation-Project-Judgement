from __future__ import annotations


def recall_at_k(ranked_ids: list[str], gold_ids: set[str], k: int) -> float:
    if not gold_ids:
        return 0.0
    retrieved = set(ranked_ids[:k])
    return len(retrieved & gold_ids) / len(gold_ids)


def reciprocal_rank(ranked_ids: list[str], gold_ids: set[str]) -> float:
    for idx, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in gold_ids:
            return 1.0 / idx
    return 0.0


def evaluate_cases(case_results: list[dict], ks: tuple[int, ...] = (1, 3, 5, 10, 20)) -> dict:
    if not case_results:
        raise ValueError("case_results must not be empty")

    aggregate = {f"recall@{k}": 0.0 for k in ks}
    aggregate["mrr"] = 0.0

    per_case = []
    for result in case_results:
        ranked_ids = result["ranked_ids"]
        gold_ids = set(result["gold_doc_ids"])

        metrics = {f"recall@{k}": recall_at_k(ranked_ids, gold_ids, k) for k in ks}
        metrics["rr"] = reciprocal_rank(ranked_ids, gold_ids)
        aggregate["mrr"] += metrics["rr"]
        for k in ks:
            aggregate[f"recall@{k}"] += metrics[f"recall@{k}"]

        per_case.append({
            "case_id": result["case_id"],
            "query": result["query"],
            "gold_doc_ids": sorted(gold_ids),
            "top_ids": ranked_ids[:20],
            "metrics": metrics,
        })

    n = len(case_results)
    aggregate = {key: value / n for key, value in aggregate.items()}
    return {"aggregate": aggregate, "cases": per_case}
