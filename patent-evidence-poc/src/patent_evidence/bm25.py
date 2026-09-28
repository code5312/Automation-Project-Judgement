from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Deterministic baseline tokenizer."""
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


@dataclass(frozen=True)
class RankedDocument:
    doc_id: str
    score: float


class BM25Index:
    def __init__(self, documents: list[dict], k1: float = 1.5, b: float = 0.75):
        if not documents:
            raise ValueError("documents must not be empty")
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(self._text(d)) for d in documents]
        self.doc_tf = [Counter(tokens) for tokens in self.doc_tokens]
        self.doc_len = [len(tokens) for tokens in self.doc_tokens]
        self.avgdl = sum(self.doc_len) / len(self.doc_len)

        df: Counter[str] = Counter()
        for tokens in self.doc_tokens:
            df.update(set(tokens))
        self.df = df
        self.n_docs = len(documents)

    @staticmethod
    def _text(doc: dict) -> str:
        fields = [
            doc.get("title", ""),
            doc.get("abstract", ""),
            doc.get("independent_claim", ""),
            " ".join(doc.get("ipc", [])),
            " ".join(doc.get("cpc", [])),
        ]
        return " ".join(fields)

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.n_docs - n + 0.5) / (n + 0.5))

    def score(self, query: str, doc_idx: int) -> float:
        query_terms = tokenize(query)
        tf = self.doc_tf[doc_idx]
        dl = self.doc_len[doc_idx]
        score = 0.0
        for term in query_terms:
            freq = tf.get(term, 0)
            if not freq:
                continue
            denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            score += self._idf(term) * (freq * (self.k1 + 1)) / denom
        return score

    def search(self, query: str, top_k: int | None = None) -> list[RankedDocument]:
        ranked = [
            RankedDocument(doc_id=doc["doc_id"], score=self.score(query, idx))
            for idx, doc in enumerate(self.documents)
        ]
        ranked.sort(key=lambda item: (-item.score, item.doc_id))
        return ranked if top_k is None else ranked[:top_k]
